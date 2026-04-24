"""
UI evidence runner — importable interface for the orchestrator.

Usage from the orchestrator (single Playwright process across all phases):

    from ui_tests import evidence

    sess = evidence.start(base_url, creds, headless=True, timeout_s=30)
    try:
        for phase_id, ... in PHASES:
            ...run phase...
            evidence.run_for_phase(sess, phase_id)
    finally:
        evidence.close(sess)

The runner persists every shot to api-calls.jsonl using
api_call_log.record_evidence() so phase_14_report.py can render the UI
evidence inline beside the API trace.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Make the parent package importable when this file is imported as
# `ui_tests.evidence` from the orchestrator.
_THIS_DIR = Path(__file__).resolve().parent
_PARENT_DIR = _THIS_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

import api_call_log  # noqa: E402
import config  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sync_playwright = None  # noqa: N816
    PWTimeout = Exception


# --- credential loading -----------------------------------------------------

def load_creds(path: Path) -> dict[str, str]:
    """Read a `key=value` properties file. Comments (`#`) and blanks ignored."""
    if not path.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {path}\n"
            f"  See ui_tests/test_users.properties.")
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


# --- session ---------------------------------------------------------------

@dataclass
class Session:
    """Holds the long-lived Playwright handles + per-persona logged-in pages."""
    base_url: str
    creds: dict[str, str]
    timeout_ms: int
    shots_dir: Path
    headless: bool
    playwright: Any = None
    browser: Any = None
    page_for: dict[str, Any] = field(default_factory=dict)
    login_failed: set[str] = field(default_factory=set)
    results: list[dict] = field(default_factory=list)


def _clean_shots_dir(shots_dir: Path) -> int:
    """Wipe any PNGs from a prior run so the report only shows fresh
    evidence. Returns the number of files removed. Subdirectories are left
    alone (in case the user is keeping per-run snapshots elsewhere)."""
    if not shots_dir.exists():
        return 0
    n = 0
    for f in shots_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
    return n


def start(base_url: str, creds: dict[str, str], *,
          headless: bool = True, timeout_s: int = 30,
          shots_dir: Path | None = None,
          cleanup: bool = True) -> Session:
    """Spin up Playwright and return a Session. Browser launches lazily on
    the first scenario — no cost if you never end up calling
    run_for_phase().

    cleanup=True (default) wipes any image files in shots_dir at the start
    of the run, so the report only shows screenshots from this run."""
    if sync_playwright is None:
        raise RuntimeError(
            "playwright is not installed. Install with:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium")
    sd = shots_dir or (_THIS_DIR / "screenshots")
    if cleanup:
        n = _clean_shots_dir(sd)
        if n:
            api_call_log.step(
                f"UI: cleaned up {n} stale screenshot(s) from {sd}",
                level="info",
            )
    return Session(
        base_url=base_url.rstrip("/"),
        creds=creds,
        timeout_ms=timeout_s * 1000,
        shots_dir=sd,
        headless=headless,
    )


def _ensure_browser(sess: Session) -> None:
    if sess.browser is not None:
        return
    sess.shots_dir.mkdir(parents=True, exist_ok=True)
    sess.playwright = sync_playwright().start()
    sess.browser = sess.playwright.chromium.launch(headless=sess.headless)


def close(sess: Session) -> None:
    if sess.browser:
        try:
            sess.browser.close()
        finally:
            sess.browser = None
    if sess.playwright:
        try:
            sess.playwright.stop()
        finally:
            sess.playwright = None


# --- login ------------------------------------------------------------------

def _gitlab_login(page, base_url: str, username: str, password: str,
                  timeout_ms: int) -> None:
    """Form-login + auto-handle GitLab's mandatory first-login password
    reset. Field names are stable across GitLab 14.x → 18.x; the redirect
    target after a forced reset is /-/user_settings/password/new on 18.x
    (was /users/edit/password on 16.x and earlier)."""
    def submit_signin(uname: str, pw: str) -> None:
        page.goto(f"{base_url}/users/sign_in", timeout=timeout_ms,
                  wait_until="domcontentloaded")
        page.fill('input[name="user[login]"]', uname)
        page.fill('input[name="user[password]"]', pw)
        with page.expect_navigation(timeout=timeout_ms,
                                    wait_until="domcontentloaded"):
            page.press('input[name="user[password]"]', 'Enter')

    submit_signin(username, password)
    if "/users/sign_in" in page.url:
        raise RuntimeError(
            f"login failed — still on {page.url}. "
            "Wrong password or the account is locked / unconfirmed.")

    # Mandatory password-reset interstitial (admin-created accounts).
    if "/password/new" in page.url or "/edit/password" in page.url:
        page.fill('input[name="user[password]"]', password)
        page.fill('input[name="user[new_password]"]', password)
        page.fill('input[name="user[password_confirmation]"]', password)
        with page.expect_navigation(timeout=timeout_ms,
                                    wait_until="domcontentloaded"):
            page.press('input[name="user[password_confirmation]"]', 'Enter')
        # GitLab signs the user out after a reset — sign in again.
        if "/users/sign_in" in page.url:
            submit_signin(username, password)
            if "/users/sign_in" in page.url or "/password/new" in page.url:
                raise RuntimeError(
                    f"second login after forced reset failed at {page.url}")


def _ensure_persona_logged_in(sess: Session, persona: str) -> Any | None:
    """Return a logged-in Page for `persona`. Login is lazy + cached. On
    failure, persona is added to sess.login_failed so future scenarios for
    it are skipped instead of retrying."""
    if persona in sess.login_failed:
        return None
    if persona in sess.page_for:
        return sess.page_for[persona]

    pw = sess.creds.get(persona)
    if not pw:
        sess.login_failed.add(persona)
        api_call_log.step(
            f"UI: no credential for persona {persona!r} — scenarios skipped",
            level="warn",
        )
        return None

    _ensure_browser(sess)
    ctx = sess.browser.new_context(
        ignore_https_errors=not config.VERIFY_SSL,
        viewport={"width": 1440, "height": 900},
    )
    page = ctx.new_page()
    try:
        _gitlab_login(page, sess.base_url, persona, pw, sess.timeout_ms)
    except Exception as e:  # noqa: BLE001
        sess.login_failed.add(persona)
        fail_shot = sess.shots_dir / f"_login_failed__{persona}.png"
        try:
            page.screenshot(path=str(fail_shot), full_page=True)
        except Exception:  # noqa: BLE001
            pass
        api_call_log.step(f"UI: login failed for {persona}: {e}", level="error")
        ctx.close()
        return None

    sess.page_for[persona] = page
    api_call_log.step(f"UI: logged in as {persona}", level="ok")
    return page


# --- screenshot capture -----------------------------------------------------

def _slug(text: str) -> str:
    out = []
    for c in text.lower():
        if c.isalnum():
            out.append(c)
        elif c in (" ", "-", "_", "."):
            out.append("-")
    s = "".join(out).strip("-")
    return s[:60] or "shot"


def _expand(path_template: str, top: str) -> str:
    return path_template.format(top=top)


def _capture(page, base_url: str, path: str, out_file: Path,
             timeout_ms: int,
             expected_status: int | None) -> tuple[bool, int | None, str]:
    url = base_url + path
    try:
        resp = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    except PWTimeout:
        return False, None, f"navigation timed out after {timeout_ms} ms"
    except Exception as e:  # noqa: BLE001
        return False, None, f"navigation error: {e}"

    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeout:
        pass

    status = resp.status if resp else None

    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(out_file), full_page=True)
    except Exception as e:  # noqa: BLE001
        return False, status, f"HTTP {status}; screenshot failed: {e}"

    if expected_status is not None:
        ok = status == expected_status
        if ok:
            note = f"HTTP {status} (as expected — denial)"
        else:
            note = f"HTTP {status} (expected {expected_status})"
    else:
        ok = status is not None and 200 <= status < 400
        note = f"HTTP {status}" if status is not None else "no response"
    return ok, status, note


# --- per-phase entry point --------------------------------------------------

def run_for_phase(sess: Session, phase_id: str) -> list[dict]:
    """Run every scenario tagged with `phase_id`. Logs each shot to
    api_call_log as a `ui_evidence` record so the final report can render
    them per phase."""
    scenarios = [s for s in SCENARIOS if s.get("phase") == phase_id]
    if not scenarios:
        return []

    top = config.TOP_GROUP
    started = time.monotonic()
    api_call_log.step(
        f"UI: running {len(scenarios)} evidence scenario(s) for phase {phase_id}",
        level="info",
    )

    phase_results: list[dict] = []
    for sc in scenarios:
        page = _ensure_persona_logged_in(sess, sc["persona"])
        if page is None:
            shot_results = [{
                "label": "login prerequisite",
                "url": "(skipped)",
                "file": "",
                "status": None,
                "ok": False,
                "note": f"no session — login failed earlier for {sc['persona']}",
            }]
            res = {
                "id": sc["id"], "phase": phase_id, "section": sc["section"],
                "title": sc["title"], "persona": sc["persona"],
                "ok": False, "shots": shot_results,
            }
            phase_results.append(res)
            sess.results.append(res)
            api_call_log.record_evidence(res)
            continue

        shot_results = []
        overall_ok = True
        for i, shot in enumerate(sc["shots"], 1):
            rel_url = _expand(shot["path"], top)
            out = sess.shots_dir / f"{sc['id']}__{i:02d}__{_slug(shot['label'])}.png"
            ok, status, note = _capture(
                page, sess.base_url, rel_url, out,
                sess.timeout_ms, shot.get("expected_status"))
            if not ok:
                overall_ok = False
            shot_results.append({
                "label": shot["label"],
                "url": sess.base_url + rel_url,
                "file": str(out.relative_to(_PARENT_DIR).as_posix()),
                "status": status,
                "ok": ok,
                "note": note,
            })
            marker = "OK " if ok else "FAIL"
            api_call_log.step(f"UI [{marker}] {note} — {shot['label']}",
                              level="ok" if ok else "warn")

        res = {
            "id": sc["id"], "phase": phase_id, "section": sc["section"],
            "title": sc["title"], "persona": sc["persona"],
            "ok": overall_ok, "shots": shot_results,
        }
        phase_results.append(res)
        sess.results.append(res)
        api_call_log.record_evidence(res)

    elapsed = time.monotonic() - started
    pa = sum(1 for r in phase_results if r["ok"])
    api_call_log.step(
        f"UI: phase {phase_id} evidence complete — {pa}/{len(phase_results)} "
        f"scenarios captured in {elapsed:.1f}s",
        level="ok" if pa == len(phase_results) else "warn",
    )
    return phase_results
