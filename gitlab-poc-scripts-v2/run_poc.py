#!/usr/bin/env python3
"""
Enterprise GitLab Access Model PoC — single-entry orchestrator.

Prompts for the GitLab URL and an admin PAT, then runs every phase end to
end against the target instance and writes an HTML report.

The whole run uses one Python process so every API call lands in a single
api-calls.jsonl that phase_14_report.py renders into HTML.

Usage:
    python3 run_poc.py
    python3 run_poc.py --url http://localhost:8929 --token glpat-xxx --yes
    python3 run_poc.py --skip 13 --skip 12        # skip specific phases

Environment:
    GITLAB_URL, GITLAB_ADMIN_TOKEN — used as defaults for the prompts.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import config
import api_call_log
import session

# Force UTF-8 on Windows consoles (unicode in step/done/warn helpers).
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# Phases run in this order. Phases 8, 10, 12 require user-impersonation tokens
# which are minted on demand inside the phase scripts. We run setup phases
# (1-7, 9, 11) by default, then validation phases (10, 12, 13), then the
# report (14). Phase 8 is skipped by default — it depends on the test users
# having SSH keys to push code, which can't be automated here.
PHASES: list[tuple[str, str, str]] = [
    ("01", "Phase 1 — Custom Roles",                       "phase_01_custom_roles"),
    ("02", "Phase 2 — Hierarchy skeleton",                 "phase_02_hierarchy"),
    ("03", "Phase 3 — IAM-sim subgroups",                  "phase_03_iam_groups"),
    ("04", "Phase 4 — Test users + initial membership",    "phase_04_users"),
    ("05", "Phase 5 — Approach 1 (hybrid) sharing",        "phase_05_approach_1"),
    ("06", "Phase 6 — Approach 2 (target) sharing",        "phase_06_approach_2"),
    ("07", "Phase 7 — Branch / tag / environment protection", "phase_07_protection"),
    ("09", "Phase 9 — Custom-role assignments",            "phase_09_custom_role_assignment"),
    ("10", "Phase 10 — Inner sourcing (visibility + fork)", "phase_10_inner_source"),
    ("11", "Phase 11 — Zone-level CI/CD inheritance",      "phase_11_zone_policy"),
    ("12", "Phase 12 — CI/CD scenario setup",              "phase_12_cicd_tests"),
    ("13", "Phase 13 — Approach 1 → 2 migration + break test", "phase_13_migration"),
]


def prompt_for_settings(args: argparse.Namespace) -> tuple[str, str, str]:
    """Resolve URL + token + prefix from CLI args, env, or interactive prompt.

    The prefix is appended to the top-level group name, the test usernames,
    and the custom-role names so the PoC can coexist with other runs on a
    shared instance. Empty prefix = use the canonical names ('acme-poc',
    'poc-alice', 'Promoter', …)."""
    url = (args.url
           or os.environ.get("GITLAB_URL")
           or "http://localhost:8929")
    token = args.token or os.environ.get("GITLAB_ADMIN_TOKEN")
    prefix = (args.prefix
              if args.prefix is not None
              else os.environ.get("POC_PREFIX", ""))

    if not args.yes:
        try:
            ans = input(f"GitLab URL [{url}]: ").strip()
            if ans:
                url = ans
        except EOFError:
            pass

        if not token:
            try:
                token = getpass.getpass("GitLab admin PAT (api scope): ").strip()
            except EOFError:
                token = ""

        if args.prefix is None and not os.environ.get("POC_PREFIX"):
            try:
                ans = input(
                    "PoC name suffix to avoid collisions on shared instances "
                    "[empty = use canonical names]: "
                ).strip()
                if ans:
                    prefix = ans
            except EOFError:
                pass

    if not token:
        print("ERROR: no GitLab PAT provided. Pass --token, set "
              "GITLAB_ADMIN_TOKEN, or run interactively.", file=sys.stderr)
        sys.exit(2)

    # Sanitize prefix: lowercase, only [a-z0-9-]
    if prefix:
        sanitized = "".join(
            c if (c.isalnum() or c == "-") else "-" for c in prefix.lower()
        ).strip("-")
        if sanitized != prefix:
            print(f"NOTE: prefix sanitized from {prefix!r} to {sanitized!r} "
                  "(GitLab path/username rules).", file=sys.stderr)
        prefix = sanitized

    return url, token, prefix


def banner_big(text: str) -> None:
    bar = "#" * 78
    print(f"\n{bar}\n#  {text}\n{bar}")


def run_one_phase(phase_id: str, title: str, module_name: str) -> tuple[bool, str]:
    """Import the phase module and call its main(). Returns (ok, note)."""
    api_call_log.begin_phase(phase_id, title)
    started = time.monotonic()
    try:
        # Re-import in case a previous phase already imported it (no-op in
        # practice, but harmless).
        mod = __import__(module_name)
        rc = mod.main()
        if rc not in (None, 0):
            note = f"phase main() returned exit code {rc}"
            api_call_log.end_phase(phase_id, status="fail", note=note)
            return False, note
    except SystemExit as e:
        if e.code in (0, None):
            api_call_log.end_phase(phase_id, status="ok",
                                   note=f"completed in {time.monotonic() - started:.1f}s")
            return True, ""
        note = f"SystemExit({e.code})"
        api_call_log.end_phase(phase_id, status="fail", note=note)
        return False, note
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc(limit=4)
        note = f"{type(e).__name__}: {e}"
        print(tb, file=sys.stderr)
        api_call_log.end_phase(phase_id, status="fail", note=note)
        return False, note

    elapsed = time.monotonic() - started
    api_call_log.end_phase(phase_id, status="ok", note=f"completed in {elapsed:.1f}s")
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="GitLab base URL (e.g. http://localhost:8929 or "
                                       "https://gitlab.example.com)")
    parser.add_argument("--token", help="PAT with api scope. Admin scope is required for "
                                          "phases 1 + 4 (custom roles, user creation).")
    parser.add_argument("--prefix", default=None,
                        help="Suffix appended to TOP_GROUP, test usernames and custom-role "
                             "names so the PoC can coexist with other runs on a shared "
                             "instance. Empty = canonical names (acme-poc, poc-alice, …). "
                             "Lowercased; non-alphanumeric chars become '-'.")
    parser.add_argument("--no-verify-ssl", action="store_true",
                        help="Disable TLS certificate verification (only useful for "
                             "self-signed hosts).")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip interactive prompts; use defaults / env")
    parser.add_argument("--skip", action="append", default=[],
                        help="Skip a phase id (e.g. --skip 13). Repeat to skip many.")
    parser.add_argument("--only", action="append", default=[],
                        help="Run only these phase ids (repeat). Overrides --skip.")
    parser.add_argument("--log", default="api-calls.jsonl",
                        help="Path for the per-call JSONL log")
    parser.add_argument("--report", default="poc-final-report.html",
                        help="Path for the final HTML report")
    parser.add_argument("--keep-going", action="store_true",
                        help="Continue to next phase if one fails")
    parser.add_argument("--no-save", action="store_true",
                        help="Don't persist the URL/token to .pocenv after prompting")
    parser.add_argument("--forget", action="store_true",
                        help="Delete .pocenv before prompting (force re-prompt)")
    parser.add_argument("--no-ui-evidence", action="store_true",
                        help="Skip the integrated UI screenshot capture between phases. "
                             "Use this if Playwright isn't installed or you only want the API run.")
    parser.add_argument("--headed", action="store_true",
                        help="Run the integrated UI evidence with a visible browser. "
                             "Default is headless (much faster).")
    parser.add_argument("--ui-creds", default="ui_tests/test_users.properties",
                        help="Credentials file for UI evidence (default: ui_tests/test_users.properties)")
    parser.add_argument("--ui-timeout", type=int, default=30,
                        help="Per-page navigation timeout in seconds for UI evidence (default 30)")
    args = parser.parse_args()

    if args.forget:
        session.clear()
        print("Cleared saved session (.pocenv).")

    url, token, prefix = prompt_for_settings(args)

    # Set the env vars FIRST, since config.py reads POC_PREFIX at import time
    # to compute TOP_GROUP, test users and custom role names.
    os.environ["GITLAB_URL"] = url
    os.environ["GITLAB_ADMIN_TOKEN"] = token
    if prefix:
        os.environ["POC_PREFIX"] = prefix
    elif "POC_PREFIX" in os.environ:
        # Empty prefix from CLI/prompt explicitly means "canonical names" —
        # respect that even if the env had something else.
        del os.environ["POC_PREFIX"]

    # SSL verification: default ON for https, OFF for http; CLI / env override.
    if args.no_verify_ssl:
        verify = False
    else:
        env_v = os.environ.get("GITLAB_VERIFY_SSL")
        verify = (bool(int(env_v)) if env_v is not None
                  else url.startswith("https"))
    os.environ["GITLAB_VERIFY_SSL"] = "1" if verify else "0"

    # Now override config singletons (in case config was already imported
    # above — these are the live values phase scripts will see).
    config.GITLAB_URL = url
    config.GITLAB_ADMIN_TOKEN = token
    config.VERIFY_SSL = verify
    # Re-derive TOP_GROUP and TEST_USERS so a changed prefix takes effect
    # within this Python process, not just on next start.
    import importlib  # noqa: PLC0415
    importlib.reload(config)

    # Persist for future runs / direct phase invocations (so the user is
    # prompted only once). Skip if --no-save.
    if not args.no_save:
        try:
            persisted = {
                "GITLAB_URL": url,
                "GITLAB_ADMIN_TOKEN": token,
                "GITLAB_VERIFY_SSL": "1" if verify else "0",
            }
            if prefix:
                persisted["POC_PREFIX"] = prefix
            saved = session.save(persisted)
            print(f"Saved settings to {saved} (chmod 600 on POSIX). "
                  "Re-run with --forget to drop it.")
        except OSError as e:
            print(f"WARNING: could not save session: {e}", file=sys.stderr)

    # Initialise the call log (orchestrator owns the file).
    api_call_log.init(args.log)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    api_call_log.step(f"PoC run started for {url} at {started_at}", level="info")

    # Choose which phases to run.
    if args.only:
        wanted = set(args.only)
        phases = [p for p in PHASES if p[0] in wanted]
    else:
        skip = set(args.skip)
        phases = [p for p in PHASES if p[0] not in skip]

    # Optional: start a UI evidence session that persists across phases.
    # The session lazily opens a browser on the first scenario, so if
    # Playwright is missing we only fail when a phase actually has scenarios.
    evidence_sess = None
    if not args.no_ui_evidence:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ui_tests"))
            from ui_tests import evidence as _ev  # noqa: PLC0415
            creds = _ev.load_creds(Path(args.ui_creds))
            evidence_sess = _ev.start(
                url, creds,
                headless=not args.headed,
                timeout_s=args.ui_timeout,
            )
            print(f"  UI evidence  : enabled ({'headed' if args.headed else 'headless'}, "
                  f"{len(creds)} credentials loaded from {args.ui_creds})")
        except FileNotFoundError as e:
            print(f"  UI evidence  : DISABLED — {e}", file=sys.stderr)
            print("                 (use --no-ui-evidence to silence this; "
                  "or create the file from the template)", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"  UI evidence  : DISABLED — {e}", file=sys.stderr)

    banner_big(f"Enterprise GitLab Access Model PoC — running {len(phases)} phase(s)")
    print(f"  Instance     : {url}")
    print(f"  Top group    : {config.TOP_GROUP}")
    print(f"  Verify TLS   : {verify}")
    if prefix:
        print(f"  Prefix       : {prefix}  (test users: {config.TEST_USERS[0]['username']}, …)")
    print()

    failures: list[tuple[str, str, str]] = []
    try:
        for phase_id, title, module_name in phases:
            banner_big(f"{title}  [{module_name}.py]")
            ok, note = run_one_phase(phase_id, title, module_name)
            if not ok:
                failures.append((phase_id, title, note))
                if not args.keep_going:
                    print(f"\nPhase {phase_id} failed ({note}). "
                          "Use --keep-going to continue past failures.", file=sys.stderr)
                    break

            # Capture UI evidence for this phase (best-effort: log + continue
            # on any UI failure, never block the API pipeline).
            if evidence_sess is not None and ok:
                try:
                    from ui_tests import evidence as _ev  # noqa: PLC0415
                    n = len(_ev.run_for_phase(evidence_sess, phase_id))
                    if n:
                        print(f"  → captured {n} UI evidence scenario(s) for phase {phase_id}")
                except Exception as e:  # noqa: BLE001
                    print(f"  ! UI evidence for phase {phase_id} failed: {e}",
                          file=sys.stderr)
    finally:
        if evidence_sess is not None:
            try:
                from ui_tests import evidence as _ev  # noqa: PLC0415
                _ev.close(evidence_sess)
            except Exception:  # noqa: BLE001
                pass

    # Always run the report (phase 14) at the end, regardless.
    banner_big("Phase 14 — Final HTML Report  [phase_14_report.py]")
    api_call_log.begin_phase("14", "Phase 14 — Final HTML Report")
    saved_argv = sys.argv
    sys.argv = ["phase_14_report.py", "--in", args.log, "--out", args.report]
    try:
        from phase_14_report import main as report_main
        rc = report_main()
        api_call_log.end_phase("14", status="ok" if rc == 0 else "fail",
                               note=f"report main() rc={rc}")
    except SystemExit as e:
        api_call_log.end_phase("14", status="ok" if e.code in (0, None) else "fail",
                               note=f"SystemExit({e.code})")
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc(limit=4)
        print(tb, file=sys.stderr)
        api_call_log.end_phase("14", status="fail", note=str(e))
        failures.append(("14", "Phase 14 — Final HTML Report", str(e)))
    finally:
        sys.argv = saved_argv

    banner_big("PoC run finished")
    print(f"  Call log : {args.log}")
    print(f"  Report   : {args.report}")
    if failures:
        print(f"\n  Phase failures: {len(failures)}")
        for pid, title, note in failures:
            print(f"    - [{pid}] {title}: {note}")
        return 1
    print("\n  All phases completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
