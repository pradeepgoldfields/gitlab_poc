#!/usr/bin/env python3
"""
PoC cleanup — delete only what the PoC scripts created.

Scope (read from config.py, not from the live instance):
  1. Project + group shares carrying member_role_id (so deleting roles is clean)
  2. Test users listed in TEST_USERS (and any forks they own)
  3. Top-level group TOP_GROUP — recursive cascade, permanently_remove=true
  4. Instance-level custom roles named in CUSTOM_ROLES
  5. Local artifacts: .pocenv, api-calls.jsonl, poc-final-report.html
     (only with --remove-local-files)

Dry-run by default. Use --confirm to actually delete. Every DELETE call is
logged to the same api-calls.jsonl as a build run, so the cleanup is itself
auditable.

Examples:
  python3 cleanup.py                       # dry-run plan
  python3 cleanup.py --confirm             # delete with defaults
  python3 cleanup.py --confirm --keep-roles
  python3 cleanup.py --confirm --keep-users
  python3 cleanup.py --confirm --remove-local-files
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import quote

import config
import api_call_log
import session
from gitlab_client import GitLabClient, GitLabError, banner, step, done, warn, fail


# Force UTF-8 on Windows consoles.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# --- discovery --------------------------------------------------------------

def discover_top_group(gl: GitLabClient) -> dict | None:
    return gl.find_group(config.TOP_GROUP)


def discover_users(gl: GitLabClient) -> list[dict]:
    found = []
    for u in config.TEST_USERS:
        existing = gl.find_user_by_username(u["username"])
        if existing:
            found.append(existing)
    return found


def discover_user_owned_projects(gl: GitLabClient, user: dict) -> list[dict]:
    """Find projects in the user's personal namespace (forks)."""
    try:
        return gl.get_paginated(f"/users/{user['id']}/projects")
    except GitLabError:
        return []


def discover_custom_roles(gl: GitLabClient) -> list[dict]:
    try:
        all_roles = gl.list_member_roles()
    except GitLabError:
        return []
    wanted = {r["name"] for r in config.CUSTOM_ROLES}
    return [r for r in all_roles if r.get("name") in wanted]


# --- planning ---------------------------------------------------------------

def build_plan(gl: GitLabClient, args: argparse.Namespace) -> dict:
    plan = {
        "top_group": None,
        "users": [],
        "user_forks": [],   # list of (owner_username, project)
        "custom_roles": [],
        "local_files": [],
    }

    plan["top_group"] = discover_top_group(gl)

    if not args.keep_users:
        users = discover_users(gl)
        plan["users"] = users
        for u in users:
            for p in discover_user_owned_projects(gl, u):
                plan["user_forks"].append((u["username"], p))

    if not args.keep_roles:
        plan["custom_roles"] = discover_custom_roles(gl)

    if args.remove_local_files:
        for f in [".pocenv", "api-calls.jsonl", "poc-final-report.html",
                  "poc-final-report.txt", ".env.tokens", "tokens.json"]:
            if os.path.exists(f):
                plan["local_files"].append(f)

    return plan


def print_plan(plan: dict, dry_run: bool) -> int:
    title = "Plan (dry-run; no deletions performed)" if dry_run else "Executing plan"
    banner(title)

    n_actions = 0

    # 1. forks (deleted via user hard_delete, but we list them so the user
    #    sees what disappears with the user)
    if plan["user_forks"]:
        print("  Personal-namespace projects (forks) — deleted with their owner:")
        for owner, p in plan["user_forks"]:
            print(f"    - [{owner}] {p['path_with_namespace']}")
        print()

    # 2. users
    if plan["users"]:
        print(f"  Users to hard-delete ({len(plan['users'])}):")
        for u in plan["users"]:
            print(f"    - {u['username']:<12}  id={u['id']:<3}  {u.get('name', '')}")
            n_actions += 1
        print()

    # 3. top group
    tg = plan["top_group"]
    if tg:
        print("  Top-level group to delete (cascade — every subgroup, project, "
              "branch/tag/env protection, variable, schedule, runner, and group "
              "share underneath comes with it):")
        print(f"    - {tg['full_path']:<20}  id={tg['id']}  visibility={tg.get('visibility')}")
        n_actions += 1
        print()

    # 4. custom roles
    if plan["custom_roles"]:
        print(f"  Instance-level custom roles to delete ({len(plan['custom_roles'])}):")
        for r in plan["custom_roles"]:
            print(f"    - {r['name']:<18}  id={r['id']}  base={r.get('base_access_level')}")
            n_actions += 1
        print()

    # 5. local files
    if plan["local_files"]:
        print(f"  Local files to remove ({len(plan['local_files'])}):")
        for f in plan["local_files"]:
            print(f"    - {f}")
            n_actions += 1
        print()

    if n_actions == 0:
        warn("Nothing to clean up. Nothing in TEST_USERS, TOP_GROUP, or "
             "CUSTOM_ROLES exists on the instance.")
    else:
        print(f"  Total actions: {n_actions}")

    if dry_run and n_actions > 0:
        print()
        print("  Re-run with --confirm to perform these deletions.")

    return n_actions


# --- execution --------------------------------------------------------------

def delete_users(gl: GitLabClient, users: list[dict]) -> tuple[int, int]:
    ok = ko = 0
    for u in users:
        step(f"Hard-deleting user {u['username']} (id={u['id']})")
        try:
            # hard_delete=true also removes their personal projects (forks).
            gl.delete(f"/users/{u['id']}?hard_delete=true")
            done(f"Deleted user {u['username']}")
            ok += 1
        except GitLabError as e:
            fail(f"Failed to delete user {u['username']}: {e}")
            ko += 1
    return ok, ko


def delete_top_group(gl: GitLabClient, group: dict) -> bool:
    step(f"Deleting top-level group {group['full_path']} "
         "(permanently_remove=true, full_path required for confirmation)")
    encoded = quote(group["full_path"], safe="")
    try:
        # GitLab requires both flags + the full_path echo for a permanent
        # delete on the same request.
        gl.delete(
            f"/groups/{encoded}?permanently_remove=true"
            f"&full_path={quote(group['full_path'], safe='')}"
        )
        done(f"Deleted group {group['full_path']}")
        return True
    except GitLabError as e:
        # Fallback: soft-delete (the group will be permanently removed after
        # the retention window).
        warn(f"Permanent delete failed ({e}); falling back to soft delete")
        try:
            gl.delete(f"/groups/{encoded}")
            warn(f"Soft-deleted {group['full_path']} — will be permanently "
                 "removed after the retention window (typically 7 days)")
            return True
        except GitLabError as e2:
            fail(f"Soft delete also failed: {e2}")
            return False


def delete_custom_roles(gl: GitLabClient, roles: list[dict]) -> tuple[int, int]:
    ok = ko = 0
    for r in roles:
        step(f"Deleting custom role {r['name']} (id={r['id']})")
        try:
            gl.delete(f"/member_roles/{r['id']}")
            done(f"Deleted role {r['name']}")
            ok += 1
        except GitLabError as e:
            fail(f"Failed to delete role {r['name']}: {e}")
            ko += 1
    return ok, ko


def remove_local_files(paths: list[str]) -> tuple[int, int]:
    ok = ko = 0
    for p in paths:
        step(f"Removing local file {p}")
        try:
            os.remove(p)
            done(f"Removed {p}")
            ok += 1
        except OSError as e:
            fail(f"Failed to remove {p}: {e}")
            ko += 1
    return ok, ko


# --- main -------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true",
                        help="Actually perform the deletions. Without this flag, "
                             "cleanup runs in dry-run mode and only prints the plan.")
    parser.add_argument("--keep-roles", action="store_true",
                        help="Preserve the instance-level custom roles (Promoter, "
                             "Operator, Security Manager). They may be in use by "
                             "other groups.")
    parser.add_argument("--keep-users", action="store_true",
                        help="Preserve the test users (and their forks).")
    parser.add_argument("--remove-local-files", action="store_true",
                        help="Also remove .pocenv, api-calls.jsonl, "
                             "poc-final-report.html, .env.tokens, tokens.json.")
    parser.add_argument("--log", default="api-calls.jsonl",
                        help="Append cleanup API calls to this JSONL file "
                             "(default: api-calls.jsonl)")
    parser.add_argument("--url", help="Override GitLab URL")
    parser.add_argument("--token", help="Override admin PAT")
    args = parser.parse_args()

    # Pick up URL/token from .pocenv if not on CLI
    session.load_into_env()
    if args.url:
        config.GITLAB_URL = args.url
        os.environ["GITLAB_URL"] = args.url
    if args.token:
        config.GITLAB_ADMIN_TOKEN = args.token
        os.environ["GITLAB_ADMIN_TOKEN"] = args.token

    if not config.GITLAB_ADMIN_TOKEN:
        print("ERROR: no admin PAT available. Pass --token, set "
              "GITLAB_ADMIN_TOKEN, or run run_poc.py once to create .pocenv.",
              file=sys.stderr)
        return 2

    # Append cleanup calls to the existing log if it exists; otherwise start a
    # fresh one. We use a separate phase id so the report can group them.
    if not os.path.exists(args.log):
        api_call_log.init(args.log)
    else:
        # Re-arm the in-memory list so phase markers/steps are recorded; the
        # file is opened in append mode by _append.
        api_call_log._log_path = args.log  # noqa: SLF001
    api_call_log.begin_phase("CLEANUP", "Cleanup — delete what the PoC created")

    banner("PoC Cleanup")
    print(f"  Instance      : {config.GITLAB_URL}")
    print(f"  Mode          : {'CONFIRM (deletions will happen)' if args.confirm else 'DRY-RUN (no deletions)'}")
    print(f"  Keep roles    : {args.keep_roles}")
    print(f"  Keep users    : {args.keep_users}")
    print(f"  Remove files  : {args.remove_local_files}")
    print()

    gl = GitLabClient()

    # Build the plan
    step("Discovering live state…")
    plan = build_plan(gl, args)
    n = print_plan(plan, dry_run=not args.confirm)

    if not args.confirm:
        api_call_log.end_phase("CLEANUP", status="ok",
                               note=f"dry-run; {n} action(s) planned")
        return 0

    if n == 0:
        api_call_log.end_phase("CLEANUP", status="ok",
                               note="nothing to delete")
        return 0

    # Execute. Order matters:
    #   forks delete *with* their owner (hard_delete=true), so users go first;
    #   group cascade handles everything beneath; custom roles last (they may
    #   be referenced by group shares which are deleted by the group cascade).
    banner("Executing cleanup")
    total_ok = total_ko = 0

    if plan["users"]:
        ok, ko = delete_users(gl, plan["users"])
        total_ok += ok
        total_ko += ko

    if plan["top_group"]:
        if delete_top_group(gl, plan["top_group"]):
            total_ok += 1
        else:
            total_ko += 1

    if plan["custom_roles"]:
        ok, ko = delete_custom_roles(gl, plan["custom_roles"])
        total_ok += ok
        total_ko += ko

    if plan["local_files"]:
        ok, ko = remove_local_files(plan["local_files"])
        total_ok += ok
        total_ko += ko

    banner("Cleanup complete")
    print(f"  Successful actions : {total_ok}")
    print(f"  Failed actions     : {total_ko}")
    if total_ko == 0:
        done("Everything PoC-related was removed (or scheduled for removal).")
    else:
        warn("Some actions failed. Re-run --confirm after addressing the errors.")

    api_call_log.end_phase(
        "CLEANUP",
        status="ok" if total_ko == 0 else "fail",
        note=f"{total_ok} ok / {total_ko} failed",
    )

    return 0 if total_ko == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
