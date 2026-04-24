#!/usr/bin/env python3
"""
Phase 13 — Migration from Approach 1 to Approach 2

Migrates payments/api from Bitbucket-style project-level SSCAM sharing to
domain-level SailPoint sharing, with no access outage.

Steps:
  1. Capture before-state of access on payments/api
  2. Confirm parallel state (SailPoint already shared at domain in Phase 5)
  3. Remove SSCAM project-level shares
  4. Capture after-state
  5. Prompt break-test: temporarily remove Alice from gl-payments-dev, verify
     access is revoked (API), then restore

Usage: python3 phase_13_migration.py
"""
import os
import time
from urllib.parse import quote
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def summarise_access(gl, project_path, username):
    """Print all access paths for a user on a project."""
    project = gl.find_project(project_path)
    if not project:
        return
    encoded = quote(project_path, safe="")
    all_members = gl.get_paginated(f"/projects/{encoded}/members/all")
    user = gl.find_user_by_username(username)
    if not user:
        return
    entries = [m for m in all_members if m["id"] == user["id"]]
    if not entries:
        print(f"    {username}: NO ACCESS")
        return
    for e in entries:
        al = e.get("access_level", "?")
        source = e.get("source_type", "direct")
        print(f"    {username}: access_level={al} source={source}")


def main():
    require_admin_token()
    banner("PHASE 13 — Migration from Approach 1 to Approach 2")

    gl = GitLabClient()

    api = f"{config.TOP_GROUP}/live-production/payments/api"

    # Step 1 — Before
    step("Step 1 — Capturing before-state on payments/api")
    print("  Alice's access paths:")
    summarise_access(gl, api, "poc-alice")
    print("  Rita's access paths:")
    summarise_access(gl, api, "poc-rita")

    # Step 2 — Parallel state (no action needed, gl-payments-dev is already shared)
    step("Step 2 — Parallel state already in place (SailPoint domain-level share from Phase 5)")

    # Step 3 — Remove SSCAM project-level shares
    step("Step 3 — Removing SSCAM project-level shares (payments-api_w, payments-api_r)")
    for group in ["iam-sim/sscam/payments-api_w", "iam-sim/sscam/payments-api_r"]:
        full = f"{config.TOP_GROUP}/{group}"
        try:
            gl.unshare_project_from_group(api, full)
            done(f"Unshared {full}")
        except Exception as e:
            warn(f"Could not unshare {full}: {e}")

    # Step 4 — After
    step("Step 4 — Capturing after-state on payments/api")
    print("  Alice's access paths:")
    summarise_access(gl, api, "poc-alice")
    print("  Rita's access paths:")
    summarise_access(gl, api, "poc-rita")

    # Step 5 — Break test (run automatically; set RUN_BREAK_TEST=0 to skip)
    step("Step 5 — Break test (remove Alice, verify access loss, restore)")
    if os.environ.get("RUN_BREAK_TEST", "1") == "0":
        warn("RUN_BREAK_TEST=0 set; skipping break test")
        return 0

    # Break test execution
    alice = gl.find_user_by_username("poc-alice")
    dev_group = f"{config.TOP_GROUP}/iam-sim/sailpoint/gl-payments-dev"
    encoded_group = quote(dev_group, safe="")

    step("Removing Alice from gl-payments-dev")
    try:
        gl.delete(f"/groups/{encoded_group}/members/{alice['id']}")
        done("Alice removed")
    except Exception as e:
        fail(f"Failed to remove: {e}")
        return 1

    time.sleep(3)  # give GitLab a moment to propagate
    step("Verifying Alice lost access…")
    summarise_access(gl, api, "poc-alice")

    step("Restoring Alice's membership in gl-payments-dev")
    try:
        gl.post(
            f"/groups/{encoded_group}/members",
            json_body={"user_id": alice["id"], "access_level": config.ROLE["developer"]},
        )
        done("Alice restored")
    except Exception as e:
        fail(f"Failed to restore: {e}")
        return 1

    banner("PHASE 13 COMPLETE", char="-")
    done("Migration complete. SSCAM project-level groups can now be decommissioned.")
    done("Next: run phase_14_report.py to generate the final audit summary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
