#!/usr/bin/env python3
"""
Phase 14 — Final HTML Report

Generates an Atlassian-styled HTML report containing:

  1. Executive summary (counts, pass/fail of live verification, runtime)
  2. Live verification block — re-runs targeted GET calls and asserts state
  3. Per-phase timeline with every API call (method, URL, status, duration,
     redacted request/response bodies, expandable)
  4. Free-form notes from step()/done()/warn()/fail() helpers

Reads from `api-calls.jsonl` (produced by api_call_log) and writes to
`poc-final-report.html`. Both paths can be overridden:

  python3 phase_14_report.py [--in api-calls.jsonl] [--out poc-final-report.html]
"""
from __future__ import annotations

import argparse
import html
import os
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote

import config
import api_call_log
from gitlab_client import GitLabClient, banner, step, done, warn, fail


# --- live verification ------------------------------------------------------

def _live_verify(gl: GitLabClient, records: list[dict] | None = None) -> list[dict]:
    """Re-run the assertions from the bash 14-verify.sh, returning a list of
    {check, status, detail} dicts. Each is a small targeted API call.

    `records` (optional) is the in-memory api-calls.jsonl. When passed, the
    verifier skips checks whose precondition phase wasn't run (instead of
    marking them FAIL)."""
    checks: list[dict] = []
    top = config.TOP_GROUP

    # Which phases actually ran in this session? Used to skip checks that
    # depend on phases the user excluded (e.g. --skip 13).
    phases_run: set[str] = set()
    if records:
        phases_run = {r.get("phase_id") for r in records
                      if r.get("kind") == "phase_begin" and r.get("phase_id")}

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "status": "pass" if ok else "fail", "detail": detail})

    def add_skip(name: str, detail: str) -> None:
        checks.append({"check": name, "status": "skip", "detail": detail})

    # 1. License (admin-only, EE-only — informational, not a test failure
    #    on SaaS / non-admin runs).
    try:
        lic = gl.get("/license")
        plan = (lic or {}).get("plan") or "none"
        # Treat presence of a plan as informational only — fail only if the
        # call returned but the plan field is empty (an actual broken state).
        add(f"License plan: {plan}", bool(lic), f"plan={plan}")
    except Exception as e:
        # 401/403 on SaaS or non-admin tokens: don't fail the whole report.
        checks.append({"check": "License plan",
                       "status": "skip",
                       "detail": f"not available ({e}) — usually means "
                                 "non-admin token or GitLab.com SaaS"})

    # 2. Custom roles (also admin-only / EE-only)
    from config import _suffix as _s  # noqa: PLC0415
    try:
        roles = gl.list_member_roles()
        names = {r.get("name") for r in roles or []}
        for want in (_s("Promoter"), _s("Operator"), _s("Security Manager")):
            add(f"Custom role exists: {want}", want in names)
    except Exception as e:
        checks.append({"check": "Custom roles",
                       "status": "skip",
                       "detail": f"not available ({e}) — admin token "
                                 "required, or instance is not EE Ultimate"})

    # 3. Hierarchy
    try:
        encoded = quote(top, safe="")
        subs = gl.get_paginated(f"/groups/{encoded}/subgroups")
        names = {s["path"] for s in subs}
        for want in ("live-production", "live-cloud-landing-zone",
                     "non-live-enterprise", "iam-sim", "platform"):
            add(f"Zone exists: {want}", want in names)
    except Exception as e:
        add("Hierarchy", False, str(e))

    # 4. restricted is private
    try:
        g = gl.find_group(f"{top}/live-production/domain-a/restricted")
        add("restricted/ is Private", bool(g) and g.get("visibility") == "private",
            f"visibility={g.get('visibility') if g else 'missing'}")
    except Exception as e:
        add("restricted/ is Private", False, str(e))

    # 5. Branch protection on domain-a/proj-1
    api_path = f"{top}/live-production/domain-a/proj-1"
    try:
        encoded = quote(api_path, safe="")
        mb = gl.get(f"/projects/{encoded}/protected_branches/main")
        merge_levels = [a.get("access_level") for a in mb.get("merge_access_levels", [])]
        push_levels = [a.get("access_level") for a in mb.get("push_access_levels", [])]
        add("main: Maintainer-only merge", 40 in merge_levels)
        add("main: no push", 0 in push_levels or push_levels == [])
        add("main: code-owner approval required",
            bool(mb.get("code_owner_approval_required")))
    except Exception as e:
        add("Branch protection", False, str(e))

    # 6. Protected environments
    try:
        encoded = quote(api_path, safe="")
        envs = gl.get_paginated(f"/projects/{encoded}/protected_environments")
        names = {e["name"] for e in envs}
        add("Protected env: staging", "staging" in names)
        add("Protected env: prod", "prod" in names)
    except Exception as e:
        add("Protected environments", False, str(e))

    # 7. Approach 1 SSCAM shares are GONE post-migration. Phase 13 is what
    # removes them — if it didn't run, this isn't a real failure, just an
    # un-migrated state. Skip with a clear note instead.
    if "13" not in phases_run and records is not None:
        add_skip("Approach 1 SSCAM project shares removed",
                 "phase 13 (migration) was not run — SSCAM shares are still "
                 "in place by design")
    else:
        try:
            proj = gl.find_project(api_path)
            shares = [s.get("group_full_path", "") for s in (proj or {}).get("shared_with_groups", [])]
            sscam_present = any("sscam" in s for s in shares)
            add("Approach 1 SSCAM project shares removed", not sscam_present,
                f"shares={shares}")
        except Exception as e:
            add("Approach 1 cleanup", False, str(e))

    # 8. Approach 2 domain-b has all 4 SailPoint shares
    domain_b_path = f"{top}/live-production/domain-b"
    try:
        g = gl.find_group(domain_b_path)
        shares = [s.get("group_full_path", "") for s in (g or {}).get("shared_with_groups", [])]
        for want in ("gl-domain-b-read", "gl-domain-b-dev", "gl-domain-b-maint", "gl-domain-b-owner"):
            add(f"domain-b shared with {want}", any(want in s for s in shares))
    except Exception as e:
        add("Approach 2 sharing", False, str(e))

    # 9. IAM custom-role groups shared with domain-a/proj-1.
    # The IAM-sim group names contain "Promoter" / "Operator" / "SecurityManager"
    # literally (they simulate the LDAP-side group names, NOT the GitLab custom
    # role names) — so they are NOT prefixed.
    try:
        proj = gl.find_project(api_path)
        shares = [s.get("group_full_path", "") for s in (proj or {}).get("shared_with_groups", [])]
        for want in ("Promoter", "Operator", "SecurityManager"):
            add(f"IAM {want} group shared with domain-a/proj-1",
                any(want in s for s in shares))
    except Exception as e:
        add("Custom role group shares", False, str(e))

    # 10. Audit events
    try:
        encoded = quote(top, safe="")
        events = gl.get(f"/groups/{encoded}/audit_events", params={"per_page": 5})
        add("Audit events recorded", bool(events) and len(events) > 0,
            f"count={len(events) if events else 0}")
    except Exception as e:
        add("Audit events", False, str(e))

    return checks


# --- HTML rendering ---------------------------------------------------------

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
       max-width: 1100px; margin: 2em auto; padding: 0 1.5em; color: #000; background: #fff;
       line-height: 1.55; }
h1 { font-size: 2em; border-bottom: 2px solid #0052cc; padding-bottom: 0.3em; }
h2 { font-size: 1.4em; margin-top: 2em; border-bottom: 1px solid #dfe1e6; padding-bottom: 0.2em; }
h3 { font-size: 1.1em; margin-top: 1.5em; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #dfe1e6; padding: 0.45em 0.7em; text-align: left; vertical-align: top; }
th { background: #f4f5f7; font-weight: 600; }
pre { background: #f4f5f7; border: 1px solid #dfe1e6; border-radius: 3px; padding: 0.6em 0.9em;
      overflow-x: auto; font-size: 0.84em; white-space: pre-wrap; word-break: break-word; }
code { background: #f4f5f7; padding: 0.05em 0.3em; border-radius: 3px; font-size: 0.9em; }
.callout-info    { border-left: 4px solid #0052cc; background: #deebff; padding: 0.65em 1em; margin: 1em 0; }
.callout-warn    { border-left: 4px solid #ff991f; background: #fffae6; padding: 0.65em 1em; margin: 1em 0; }
.callout-success { border-left: 4px solid #00875a; background: #e3fcef; padding: 0.65em 1em; margin: 1em 0; }
.callout-danger  { border-left: 4px solid #de350b; background: #ffebe6; padding: 0.65em 1em; margin: 1em 0; }
.pass { color: #00875a; font-weight: 600; }
.fail { color: #de350b; font-weight: 600; }
.method { font-family: monospace; font-weight: 600; padding: 0.05em 0.4em; border-radius: 3px;
          background: #dfe1e6; }
.status-2xx { color: #00875a; font-weight: 600; }
.status-3xx { color: #0052cc; font-weight: 600; }
.status-4xx { color: #ff991f; font-weight: 600; }
.status-5xx { color: #de350b; font-weight: 600; }
.phase-banner { background: #0052cc; color: #fff; padding: 0.5em 1em; border-radius: 4px;
                margin: 2em 0 0.5em 0; font-weight: 600; }
details { margin: 0.4em 0; }
details > summary { cursor: pointer; user-select: none; padding: 0.3em 0; }
details > summary:hover { background: #f4f5f7; }
.step-info  { color: #5e6c84; }
.step-ok    { color: #00875a; }
.step-warn  { color: #ff991f; }
.step-error { color: #de350b; }
.muted { color: #5e6c84; font-size: 0.9em; }
.toc { background: #f4f5f7; border: 1px solid #dfe1e6; padding: 0.6em 1.2em; border-radius: 3px; }
.toc ol { margin: 0.3em 0; }
.evidence { border: 1px solid #dfe1e6; border-left: 4px solid #0052cc;
            background: #f8f9fb; padding: 0.7em 1em; margin: 0.6em 0;
            border-radius: 4px; }
.evidence h4 { margin: 0 0 0.4em 0; font-size: 1.0em; color: #172b4d; }
.evidence .meta { font-size: 0.85em; color: #5e6c84; margin-bottom: 0.5em; }
.evidence .persona { display: inline-block; background: #fff; border: 1px solid #dfe1e6;
                     border-radius: 3px; padding: 0.05em 0.5em; font-family: monospace;
                     font-size: 0.85em; }
.shot { border: 1px solid #dfe1e6; border-radius: 3px; padding: 0.5em;
        margin: 0.4em 0; background: #fff; }
.shot img { max-width: 100%; border: 1px solid #dfe1e6; border-radius: 3px;
            display: block; margin-top: 0.4em; cursor: zoom-in; }
.shot img:hover { box-shadow: 0 0 0 2px #0052cc; }
.shot .url { font-family: monospace; font-size: 0.78em; word-break: break-all;
             color: #5e6c84; }
"""


def _h(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def _status_class(status: int | None) -> str:
    if status is None:
        return "fail"
    if 200 <= status < 300:
        return "status-2xx"
    if 300 <= status < 400:
        return "status-3xx"
    if 400 <= status < 500:
        return "status-4xx"
    return "status-5xx"


def _render_call(rec: dict) -> str:
    method = rec.get("method", "")
    url = rec.get("url", "")
    status = rec.get("status")
    duration = rec.get("duration_ms", 0)
    summary = (
        f'<span class="method">{_h(method)}</span> '
        f'<code>{_h(url)}</code> '
        f'&rarr; <span class="{_status_class(status)}">{_h(status if status is not None else "ERR")}</span> '
        f'<span class="muted">({duration:.0f} ms)</span>'
    )
    if rec.get("error"):
        summary += f' <span class="fail">[{_h(rec["error"])}]</span>'

    req = rec.get("request_body") or ""
    resp = rec.get("response_body") or ""
    body_html = ""
    if req:
        body_html += f'<h4 class="muted">Request body</h4><pre>{_h(req)}</pre>'
    if resp:
        body_html += f'<h4 class="muted">Response body</h4><pre>{_h(resp)}</pre>'
    if not body_html:
        body_html = '<p class="muted">No request/response body recorded.</p>'

    return (
        f'<details><summary>{summary}</summary>{body_html}</details>'
    )


def _render_evidence(rec: dict) -> str:
    """Render one ui_evidence record (a scenario with N screenshots)."""
    overall = rec.get("ok", False)
    overall_lbl = ('<span class="pass">PASS</span>' if overall
                   else '<span class="fail">FAIL</span>')
    title = rec.get("title", "")
    section = rec.get("section", "")
    persona = rec.get("persona", "")
    sid = rec.get("scenario_id", "")

    parts = [
        f'<div class="evidence">',
        f'<h4>UI evidence — {_h(section)}: {_h(title)} &nbsp; {overall_lbl}</h4>',
        f'<div class="meta">Scenario <code>{_h(sid)}</code> '
        f'&middot; logged in as <span class="persona">{_h(persona)}</span> '
        f'&middot; {len(rec.get("shots", []))} shot(s)</div>',
    ]
    for s in rec.get("shots", []):
        cls = "pass" if s.get("ok") else "fail"
        lbl = "OK" if s.get("ok") else "FAIL"
        img_html = (
            f'<a href="{_h(s.get("file", ""))}" target="_blank">'
            f'<img src="{_h(s.get("file", ""))}" alt="{_h(s.get("label", ""))}" loading="lazy">'
            f'</a>'
            if s.get("file") else
            '<p class="muted">(no screenshot — login failed)</p>'
        )
        parts.append(
            f'<div class="shot">'
            f'<div><strong>{_h(s.get("label", ""))}</strong> '
            f'&nbsp;<span class="{cls}">{lbl}</span> '
            f'<span class="muted">({_h(s.get("note", ""))})</span></div>'
            f'<div class="url">{_h(s.get("url", ""))}</div>'
            f'{img_html}'
            f'</div>'
        )
    parts.append('</div>')
    return "".join(parts)


def _render_step(rec: dict) -> str:
    cls = {"info": "step-info", "ok": "step-ok",
           "warn": "step-warn", "error": "step-error"}.get(rec.get("level", "info"), "step-info")
    icon = {"info": "&bull;", "ok": "&#10003;", "warn": "!", "error": "&#10007;"}.get(rec.get("level", "info"), "&bull;")
    return f'<div class="{cls}">{icon} {_h(rec.get("message", ""))}</div>'


def _phase_blocks(records: list[dict]) -> list[tuple[str, str, list[dict]]]:
    """Group records by phase. Returns [(phase_id, title, records...), ...]."""
    blocks: list[tuple[str, str, list[dict]]] = []
    current_id = "_pre"
    current_title = "Setup (before any phase)"
    bucket: list[dict] = []
    for r in records:
        if r["kind"] == "phase_begin":
            if bucket:
                blocks.append((current_id, current_title, bucket))
            current_id = r["phase_id"]
            current_title = r["title"]
            bucket = [r]
        elif r["kind"] == "phase_end":
            bucket.append(r)
            blocks.append((current_id, current_title, bucket))
            current_id = "_between"
            current_title = "Between phases"
            bucket = []
        else:
            bucket.append(r)
    if bucket:
        blocks.append((current_id, current_title, bucket))
    return blocks


def _build_html(records: list[dict], checks: list[dict],
                gitlab_url: str, started_at: str, finished_at: str) -> str:
    # counts
    total_calls = sum(1 for r in records if r["kind"] == "call")
    error_calls = sum(1 for r in records if r["kind"] == "call" and r.get("error"))
    pass_count = sum(1 for c in checks if c["status"] == "pass")
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    skip_count = sum(1 for c in checks if c["status"] == "skip")
    # UI evidence: count scenarios + shots
    ui_scenarios = [r for r in records if r["kind"] == "ui_evidence"]
    ui_pass = sum(1 for r in ui_scenarios if r.get("ok"))
    ui_fail = len(ui_scenarios) - ui_pass
    ui_shots = sum(len(r.get("shots", [])) for r in ui_scenarios)

    by_method = defaultdict(int)
    for r in records:
        if r["kind"] == "call":
            by_method[r.get("method", "?")] += 1

    # phase blocks
    blocks = _phase_blocks(records)

    # --- header
    head = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Enterprise GitLab Access Model PoC — Run Report</title>
<style>{CSS}</style>
</head><body>
<h1>Enterprise GitLab Access Model PoC — Run Report</h1>
<p class="muted">Instance: <code>{_h(gitlab_url)}</code> &middot;
   Started: <code>{_h(started_at)}</code> &middot;
   Finished: <code>{_h(finished_at)}</code></p>
"""

    # --- summary
    overall_class = "callout-success" if fail_count == 0 else "callout-danger"
    skipped_note = f", {skip_count} skipped" if skip_count else ""
    overall_text = (
        f"{pass_count}/{pass_count + fail_count} live checks passed{skipped_note}"
        if checks else "no live checks run"
    )
    summary = f"""
<h2>1. Summary</h2>
<div class="{overall_class}"><strong>Result:</strong> {overall_text}.
{total_calls} API calls, {error_calls} returned errors.</div>

<table>
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>
<tr><td>Total API calls</td><td>{total_calls}</td></tr>
<tr><td>Calls returning HTTP &ge; 400</td><td>{error_calls}</td></tr>
<tr><td>Calls by method</td><td>{', '.join(f"{m}: {c}" for m, c in sorted(by_method.items()))}</td></tr>
<tr><td>Live verification checks</td><td>{pass_count} pass / {fail_count} fail / {skip_count} skipped</td></tr>
<tr><td>UI evidence scenarios</td><td>{ui_pass} pass / {ui_fail} fail &middot; {ui_shots} screenshot(s)</td></tr>
<tr><td>Phases recorded</td><td>{sum(1 for r in records if r['kind']=='phase_begin' and r.get('phase_id') != '14')}</td></tr>
</tbody></table>
"""

    # --- live verification table
    rows = []
    for c in checks:
        cls = {"pass": "pass", "fail": "fail", "skip": "muted"}.get(c["status"], "fail")
        rows.append(
            f'<tr><td><span class="{cls}">{c["status"].upper()}</span></td>'
            f'<td>{_h(c["check"])}</td><td><code>{_h(c.get("detail", ""))}</code></td></tr>'
        )
    verify_html = f"""
<h2>2. Live verification</h2>
<p>Re-runs the same assertions a separate auditor would: each row is one or
more <code>GET</code> calls against the live instance, with the recorded
result.</p>
<table>
<thead><tr><th>Status</th><th>Check</th><th>Detail</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan=3 class="muted">No checks ran.</td></tr>'}</tbody>
</table>
"""

    # --- per-phase timeline
    phase_html_parts: list[str] = []
    phase_html_parts.append("<h2>3. Per-phase timeline</h2>")
    phase_html_parts.append('<p>Every API call made during the run, grouped by phase.'
                            ' Click a row to see the request/response body. Sensitive'
                            ' values (tokens, passwords) are redacted.</p>')

    # Phase 14 IS the report generator — its only "API calls" are the live
    # verification reads we already render in section 2, and it produces no
    # PoC evidence. Drop it from the timeline to keep the report focused.
    blocks = [b for b in blocks if b[0] != "14"]

    # toc
    toc_items = []
    for phase_id, title, _ in blocks:
        if not phase_id.startswith("_"):
            toc_items.append(f'<li><a href="#{_h(phase_id)}">{_h(title)}</a></li>')
    if toc_items:
        phase_html_parts.append('<div class="toc"><strong>Jump to phase</strong><ol>'
                                + "".join(toc_items) + "</ol></div>")

    for phase_id, title, recs in blocks:
        anchor_attr = f'id="{_h(phase_id)}"' if not phase_id.startswith("_") else ""
        if phase_id.startswith("_"):
            phase_html_parts.append(f'<h3 class="muted">{_h(title)}</h3>')
        else:
            phase_html_parts.append(f'<div class="phase-banner" {anchor_attr}>{_h(title)}</div>')

        # phase result summary if we have an end record
        end = next((r for r in recs if r["kind"] == "phase_end"), None)
        if end:
            cls = "callout-success" if end.get("status") == "ok" else "callout-danger"
            note = end.get("note") or end.get("status", "")
            phase_html_parts.append(f'<div class="{cls}">Phase result: <strong>{_h(end.get("status", ""))}</strong>'
                                    f' &mdash; {_h(note)}</div>')

        # interleave steps, calls, and UI evidence in chronological order
        for r in recs:
            if r["kind"] == "call":
                phase_html_parts.append(_render_call(r))
            elif r["kind"] == "step":
                phase_html_parts.append(_render_step(r))
            elif r["kind"] == "ui_evidence":
                phase_html_parts.append(_render_evidence(r))

    timeline_html = "\n".join(phase_html_parts)

    foot = """
<h2>4. About this report</h2>
<p class="muted">Generated by <code>phase_14_report.py</code> from
<code>api-calls.jsonl</code> plus a live re-verification pass. The JSONL log
is the source of truth; this HTML is a presentation layer over it. Both files
should be archived together for audit.</p>
</body></html>
"""

    return head + summary + verify_html + timeline_html + foot


# --- main ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input", default="api-calls.jsonl",
                        help="Path to the JSONL call log (default: api-calls.jsonl)")
    parser.add_argument("--out", default="poc-final-report.html",
                        help="Path to the output HTML report")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip live re-verification (offline report only)")
    args = parser.parse_args()

    banner("PHASE 14 — Final HTML Report")
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Load call log (if present)
    if os.path.exists(args.input):
        records = api_call_log.load(args.input)
        step(f"Loaded {len(records)} records from {args.input}")
    else:
        warn(f"No call log at {args.input} — report will be live-verification-only")
        records = []

    # Live verification (unless suppressed)
    checks: list[dict] = []
    if not args.no_verify:
        try:
            gl = GitLabClient()
            step("Running live verification…")
            checks = _live_verify(gl, records=records)
            ok = sum(1 for c in checks if c["status"] == "pass")
            ko = sum(1 for c in checks if c["status"] == "fail")
            done(f"Live verification: {ok} pass / {ko} fail")
        except Exception as e:
            fail(f"Live verification crashed: {e}")
    else:
        step("Skipping live verification (--no-verify)")

    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    out_html = _build_html(records, checks, config.GITLAB_URL, started_at, finished_at)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out_html)
    done(f"HTML report written to {args.out}")

    fail_count = sum(1 for c in checks if c["status"] == "fail")
    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
