#!/usr/bin/env python3
"""
UI evidence run for the Enterprise GitLab Access Model PoC.

Drives a real browser through every "Verify in UI" link from
gitlab-access-model-poc-report.html, takes a full-page screenshot of each one,
and writes a self-contained HTML report.

Evidence-only: scenarios always "pass" unless Playwright errors or the page
returns 4xx/5xx — no functional assertions.

Quick start
-----------
    pip install -r requirements.txt
    python -m playwright install chromium

    # Either set GITLAB_URL + run an API PoC first (so .pocenv is populated),
    # or pass --url here. Credentials come from test_users.properties.
    python ui_tests/run_ui_tests.py

Output
------
    ui_tests/screenshots/<scenario-id>__<n>__<label>.png
    ui_tests/ui-test-report.html

Flags
-----
    --headed / --headless         Default: --headed
    --creds PATH                  test_users.properties (default: ui_tests/test_users.properties)
    --only ID --only ID           Run only the listed scenario IDs
    --url URL                     Override GITLAB_URL
    --timeout SECONDS             Per-page navigation timeout (default 20)
    --slow-mo MS                  Pause between Playwright actions (default 0)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import sys
from pathlib import Path
from urllib.parse import urlparse

# Make sibling modules importable when this file is run as a script.
_THIS_DIR = Path(__file__).resolve().parent
_PARENT_DIR = _THIS_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

import config  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Page
except ImportError:
    print("ERROR: playwright is not installed.\n"
          "  pip install playwright\n"
          "  python -m playwright install chromium",
          file=sys.stderr)
    raise SystemExit(2)


# Force UTF-8 on Windows consoles.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# --- credential loading -----------------------------------------------------

def load_creds(path: Path) -> dict[str, str]:
    """Read a `key=value` properties file. Comments (`#`) and blanks ignored."""
    if not path.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {path}\n"
            f"  Copy ui_tests/test_users.properties.example or set --creds.")
    creds: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        creds[k.strip()] = v.strip()
    return creds


# --- login --------------------------------------------------------------------

def gitlab_login(page: Page, base_url: str, username: str, password: str,
                 timeout_ms: int) -> None:
    """Form-login on the GitLab sign-in page. Robust against:
      - selector drift on the submit button (we press Enter instead),
      - GitLab's mandatory first-login password reset (we re-submit the same
        password to /users/edit/password and continue),
      - the post-reset re-login (GitLab logs the user out after a reset).

    Input names (`user[login]` / `user[password]`) are stable across 14.x→18.x.
    """
    def submit_signin(uname: str, pw: str) -> None:
        page.goto(f"{base_url}/users/sign_in", timeout=timeout_ms,
                  wait_until="domcontentloaded")
        page.fill('input[name="user[login]"]', uname)
        page.fill('input[name="user[password]"]', pw)
        with page.expect_navigation(timeout=timeout_ms, wait_until="domcontentloaded"):
            page.press('input[name="user[password]"]', 'Enter')

    submit_signin(username, password)

    if "/users/sign_in" in page.url:
        raise RuntimeError(
            f"login appears to have failed — still on {page.url}. "
            "Wrong password, or the account is locked / requires confirmation."
        )

    # GitLab forces a password change after an admin-reset. The redirect
    # target on 18.x is /-/user_settings/password/new with field layout:
    #   user[password]              = current password
    #   user[new_password]          = new password
    #   user[password_confirmation] = confirm new password
    # We satisfy the flow by re-entering the same password as both old and new.
    if "/password/new" in page.url or "/edit/password" in page.url:
        page.fill('input[name="user[password]"]', password)
        page.fill('input[name="user[new_password]"]', password)
        page.fill('input[name="user[password_confirmation]"]', password)
        with page.expect_navigation(timeout=timeout_ms, wait_until="domcontentloaded"):
            page.press('input[name="user[password_confirmation]"]', 'Enter')
        # Post-reset, GitLab signs the user out — sign in again with the same pw.
        if "/users/sign_in" in page.url:
            submit_signin(username, password)
            if "/users/sign_in" in page.url or "/password/new" in page.url:
                raise RuntimeError(
                    f"second login after forced password reset failed — at {page.url}")


# --- screenshot capture -------------------------------------------------------

def expand(path_template: str, top: str) -> str:
    return path_template.format(top=top)


def capture(page: Page, base_url: str, path: str, out_file: Path,
            timeout_ms: int, expected_status: int | None = None) -> tuple[bool, str]:
    """Navigate + full-page screenshot. Returns (ok, note).

    By default any 2xx/3xx response is "ok". Pass expected_status (e.g. 404
    for "this persona should be denied") to flip the meaning — only the
    matching status counts as a pass."""
    url = base_url + path
    try:
        resp = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    except PWTimeout:
        return False, f"navigation timed out after {timeout_ms} ms"
    except Exception as e:  # noqa: BLE001
        return False, f"navigation error: {e}"

    # Wait a touch for late-loading SPA content (members lists, pipeline rows).
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeout:
        pass  # Some GitLab pages keep polling — continue anyway.

    status = resp.status if resp else None
    note = f"HTTP {status}" if status is not None else "no response"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(out_file), full_page=True)
    except Exception as e:  # noqa: BLE001
        return False, f"{note}; screenshot failed: {e}"

    if expected_status is not None:
        ok = status == expected_status
        if not ok:
            note = f"{note} (expected {expected_status})"
        else:
            note = f"{note} (as expected — denial)"
    else:
        ok = status is not None and 200 <= status < 400
    return ok, note


# --- scenario loop ------------------------------------------------------------

def slug(text: str) -> str:
    out = []
    for c in text.lower():
        if c.isalnum():
            out.append(c)
        elif c in (" ", "-", "_", "."):
            out.append("-")
    s = "".join(out).strip("-")
    return s[:60] or "shot"


def run_scenario(page: Page, scenario: dict, base_url: str, top: str,
                 shots_dir: Path, timeout_ms: int) -> dict:
    """Drive one scenario; return a result dict for the report."""
    print(f"  · {scenario['id']:<26}  {scenario['title']}")
    shot_results = []
    overall_ok = True
    for i, shot in enumerate(scenario["shots"], 1):
        rel_url = expand(shot["path"], top)
        out = shots_dir / f"{scenario['id']}__{i:02d}__{slug(shot['label'])}.png"
        ok, note = capture(page, base_url, rel_url, out, timeout_ms,
                            expected_status=shot.get("expected_status"))
        if not ok:
            overall_ok = False
        shot_results.append({
            "label": shot["label"],
            "url": base_url + rel_url,
            "file": out.relative_to(_THIS_DIR).as_posix(),
            "ok": ok,
            "note": note,
        })
        marker = "OK " if ok else "FAIL"
        print(f"      [{marker}] {note:<14} {shot['label']}")
    return {
        "id": scenario["id"],
        "section": scenario["section"],
        "title": scenario["title"],
        "persona": scenario["persona"],
        "ok": overall_ok,
        "shots": shot_results,
    }


# --- HTML report --------------------------------------------------------------

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
       max-width: 1200px; margin: 2em auto; padding: 0 1.5em; color: #000; background: #fff;
       line-height: 1.55; }
h1 { font-size: 2em; border-bottom: 2px solid #0052cc; padding-bottom: 0.3em; }
h2 { font-size: 1.4em; margin-top: 2em; border-bottom: 1px solid #dfe1e6; padding-bottom: 0.2em; }
h3 { font-size: 1.1em; margin-top: 1.5em; color: #172b4d; }
.muted { color: #5e6c84; font-size: 0.9em; }
.pass  { color: #00875a; font-weight: 600; }
.fail  { color: #de350b; font-weight: 600; }
.persona { display: inline-block; background: #f4f5f7; border: 1px solid #dfe1e6;
           border-radius: 3px; padding: 0.05em 0.5em; font-family: monospace;
           font-size: 0.85em; }
.callout-success { border-left: 4px solid #00875a; background: #e3fcef; padding: 0.65em 1em; margin: 1em 0; }
.callout-danger  { border-left: 4px solid #de350b; background: #ffebe6; padding: 0.65em 1em; margin: 1em 0; }
.shot { border: 1px solid #dfe1e6; border-radius: 4px; padding: 0.7em; margin: 0.7em 0;
        background: #fafbfc; }
.shot img { max-width: 100%; border: 1px solid #dfe1e6; border-radius: 3px;
            display: block; margin-top: 0.5em; }
.shot .url { font-family: monospace; font-size: 0.82em; word-break: break-all; }
.toc { background: #f4f5f7; border: 1px solid #dfe1e6; padding: 0.6em 1.2em; border-radius: 3px; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #dfe1e6; padding: 0.45em 0.7em; text-align: left; vertical-align: top; }
th { background: #f4f5f7; font-weight: 600; }
"""


def _h(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def render_report(results: list[dict], base_url: str, started_at: str,
                  finished_at: str, out_path: Path) -> None:
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed
    overall_class = "callout-success" if failed == 0 else "callout-danger"

    # Group by section so the report mirrors the source HTML doc.
    by_section: dict[str, list[dict]] = {}
    for r in results:
        by_section.setdefault(r["section"], []).append(r)

    sections_html = []
    for section, items in by_section.items():
        rows = []
        for r in items:
            rows.append(
                f'<tr><td><a href="#{_h(r["id"])}">{_h(r["title"])}</a></td>'
                f'<td><span class="persona">{_h(r["persona"])}</span></td>'
                f'<td>{len(r["shots"])}</td>'
                f'<td>{"<span class=pass>PASS</span>" if r["ok"] else "<span class=fail>FAIL</span>"}</td>'
                f'</tr>'
            )
        sections_html.append(
            f'<h2>{_h(section)}</h2>'
            '<table><thead><tr><th>Scenario</th><th>Logged in as</th>'
            '<th>Shots</th><th>Result</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    detail_blocks = []
    for r in results:
        shot_html = []
        for s in r["shots"]:
            status_cls = "pass" if s["ok"] else "fail"
            status_lbl = "OK" if s["ok"] else "FAIL"
            shot_html.append(
                f'<div class="shot">'
                f'<div><strong>{_h(s["label"])}</strong> '
                f'&nbsp;<span class="{status_cls}">{status_lbl}</span> '
                f'<span class="muted">({_h(s["note"])})</span></div>'
                f'<div class="url">{_h(s["url"])}</div>'
                f'<img src="{_h(s["file"])}" alt="{_h(s["label"])}" loading="lazy">'
                f'</div>'
            )
        detail_blocks.append(
            f'<h3 id="{_h(r["id"])}">{_h(r["section"])} — {_h(r["title"])}</h3>'
            f'<p class="muted">Logged in as <span class="persona">{_h(r["persona"])}</span></p>'
            + "".join(shot_html)
        )

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>GitLab Access Model PoC — UI Evidence Report</title>
<style>{CSS}</style></head><body>
<h1>UI Evidence Report</h1>
<p class="muted">Instance: <code>{_h(base_url)}</code> &middot;
  Started: <code>{_h(started_at)}</code> &middot;
  Finished: <code>{_h(finished_at)}</code></p>

<div class="{overall_class}"><strong>Result:</strong> {passed}/{total} scenarios captured cleanly
({failed} with at least one failed shot).</div>

<h2>Summary by section</h2>
{''.join(sections_html)}

<h2>Evidence — full screenshots</h2>
{''.join(detail_blocks)}

</body></html>
"""
    out_path.write_text(body, encoding="utf-8")


# --- main ---------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--creds", default=str(_THIS_DIR / "test_users.properties"),
                        help="Path to the credentials properties file.")
    parser.add_argument("--url", default=None,
                        help="GitLab base URL. Defaults to config.GITLAB_URL "
                             "(set by run_poc.py / .pocenv / env).")
    parser.add_argument("--only", action="append", default=[],
                        help="Run only the listed scenario ids (repeat).")
    parser.add_argument("--headed", dest="headed", action="store_true", default=True,
                        help="Run with a visible browser (default).")
    parser.add_argument("--headless", dest="headed", action="store_false",
                        help="Run headless (faster, no window).")
    parser.add_argument("--timeout", type=int, default=20,
                        help="Per-page navigation timeout in seconds (default 20).")
    parser.add_argument("--slow-mo", type=int, default=0,
                        help="Pause this many ms between Playwright actions (debugging).")
    parser.add_argument("--out", default=str(_THIS_DIR / "ui-test-report.html"),
                        help="Output report path.")
    parser.add_argument("--shots-dir", default=str(_THIS_DIR / "screenshots"),
                        help="Directory for PNG screenshots.")
    args = parser.parse_args()

    base_url = (args.url or config.GITLAB_URL).rstrip("/")
    if not base_url:
        print("ERROR: no GitLab URL. Pass --url or run run_poc.py first to "
              "populate .pocenv.", file=sys.stderr)
        return 2

    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        print(f"ERROR: invalid URL: {base_url!r}", file=sys.stderr)
        return 2

    creds = load_creds(Path(args.creds))
    print(f"Loaded {len(creds)} credential(s) from {args.creds}")

    # Filter scenarios.
    scenarios = SCENARIOS
    if args.only:
        wanted = set(args.only)
        scenarios = [s for s in scenarios if s["id"] in wanted]
        if not scenarios:
            print(f"ERROR: --only filtered out everything (ids: {sorted(wanted)})",
                  file=sys.stderr)
            return 2

    # Verify every persona we're going to use has a password on file.
    needed = {s["persona"] for s in scenarios}
    missing = [p for p in needed if not creds.get(p)]
    if missing:
        print(f"ERROR: no credentials for persona(s): {missing}\n"
              f"  Add them to {args.creds} (format: username=password).",
              file=sys.stderr)
        return 2

    shots_dir = Path(args.shots_dir)
    shots_dir.mkdir(parents=True, exist_ok=True)

    top = config.TOP_GROUP
    timeout_ms = args.timeout * 1000

    started_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    print(f"\nGitLab : {base_url}")
    print(f"Top    : {top}")
    print(f"Mode   : {'headed' if args.headed else 'headless'}")
    print(f"Output : {args.out}\n")

    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed, slow_mo=args.slow_mo)
        try:
            # One context (and one cookie jar) per persona, reused across all
            # scenarios that use that persona — login is the slow part.
            ctx_for: dict[str, "Page"] = {}
            for persona in sorted(needed):
                print(f"Logging in as {persona}…")
                ctx = browser.new_context(ignore_https_errors=not config.VERIFY_SSL,
                                            viewport={"width": 1440, "height": 900})
                page = ctx.new_page()
                try:
                    gitlab_login(page, base_url, persona, creds[persona], timeout_ms)
                    print(f"  ok — logged in as {persona}")
                except Exception as e:  # noqa: BLE001
                    print(f"  FAIL — login as {persona}: {e}", file=sys.stderr)
                    # Capture a screenshot of the failed login page for triage.
                    fail_shot = shots_dir / f"_login_failed__{persona}.png"
                    try:
                        page.screenshot(path=str(fail_shot), full_page=True)
                    except Exception:  # noqa: BLE001
                        pass
                    ctx.close()
                    continue
                ctx_for[persona] = page

            # Walk scenarios in source order.
            for sc in scenarios:
                page = ctx_for.get(sc["persona"])
                if page is None:
                    print(f"  · {sc['id']:<26}  SKIPPED (no logged-in session for {sc['persona']})")
                    results.append({
                        "id": sc["id"], "section": sc["section"], "title": sc["title"],
                        "persona": sc["persona"], "ok": False,
                        "shots": [{"label": "login prerequisite",
                                   "url": "(skipped)",
                                   "file": "",
                                   "ok": False,
                                   "note": "no session — login failed earlier"}],
                    })
                    continue
                results.append(run_scenario(page, sc, base_url, top, shots_dir, timeout_ms))

        finally:
            browser.close()

    finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    out_path = Path(args.out)
    render_report(results, base_url, started_at, finished_at, out_path)

    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed
    print(f"\nUI evidence: {passed}/{len(results)} scenarios passed")
    print(f"Report     : {out_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
