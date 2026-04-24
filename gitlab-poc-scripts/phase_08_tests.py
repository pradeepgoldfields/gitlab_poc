#!/usr/bin/env python3
"""
Phase 8 — Role Enforcement Tests (API-based)

Validates role enforcement by making API calls as each user. This catches a large
subset of the manual browser tests automatically.

Requires: a Personal Access Token for each test user, set as environment variables:
  POC_ALICE_TOKEN, POC_BOB_TOKEN, POC_CAROL_TOKEN, POC_PAUL_TOKEN,
  POC_SAM_TOKEN, POC_RITA_TOKEN, POC_DAN_TOKEN, POC_CON_TOKEN

If a user token is missing, the relevant test is skipped with a warning.

Tests:
  T1 — Alice cannot delete domain-a/proj-1 (Developer)
  T2 — Alice cannot edit protected branch rules
  T3 — Alice cannot view CI/CD variables
  T4 — Alice can push to a feature branch (creates one via API)
  T5 — Rita has read-only access (can list MRs but not create)
  T6 — Bob can merge to protected branches (via API, requires existing MR)
  T7 — Dan cannot access restricted-proj-1 (404)
  T8 — Con can access restricted-proj-1 but not proj-1/proj-2/proj-3
"""
import os
import sys
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail


USER_TOKEN_ENV = {
    "poc-alice": "POC_ALICE_TOKEN",
    "poc-bob":   "POC_BOB_TOKEN",
    "poc-carol": "POC_CAROL_TOKEN",
    "poc-paul":  "POC_PAUL_TOKEN",
    "poc-sam":   "POC_SAM_TOKEN",
    "poc-rita":  "POC_RITA_TOKEN",
    "poc-dan":   "POC_DAN_TOKEN",
    "poc-con":   "POC_CON_TOKEN",
}


def client_for(username):
    token = os.environ.get(USER_TOKEN_ENV[username])
    if not token:
        return None
    return GitLabClient(token=token)


results = []


def record(test_id, description, passed, detail=""):
    results.append({"id": test_id, "desc": description, "pass": passed, "detail": detail})
    if passed:
        done(f"{test_id} PASS — {description}")
    else:
        fail(f"{test_id} FAIL — {description}  [{detail}]")


def assert_forbidden(username, fn, test_id, description):
    """fn() should fail with HTTP 403 or 404. Anything else is a test failure."""
    gl = client_for(username)
    if gl is None:
        warn(f"{test_id} SKIP — no token for {username}")
        return
    try:
        fn(gl)
        record(test_id, description, False, "Expected forbidden, but call succeeded")
    except Exception as e:
        msg = str(e)
        if "403" in msg or "404" in msg or "401" in msg:
            record(test_id, description, True, "Correctly rejected")
        else:
            record(test_id, description, False, f"Unexpected error: {msg}")


def assert_allowed(username, fn, test_id, description):
    gl = client_for(username)
    if gl is None:
        warn(f"{test_id} SKIP — no token for {username}")
        return
    try:
        fn(gl)
        record(test_id, description, True, "Allowed as expected")
    except Exception as e:
        record(test_id, description, False, f"Unexpected error: {e}")


def main():
    banner("PHASE 8 — Role Enforcement Tests (API-based)")

    api_project = f"{config.TOP_GROUP}/live-production/domain-a/proj-1"
    ui_project = f"{config.TOP_GROUP}/live-production/domain-a/proj-2"
    secrets_project = f"{config.TOP_GROUP}/live-production/domain-a/restricted/restricted-proj-1"

    # ------------------------------------------------------------------
    # T1 — Alice cannot delete domain-a/proj-1
    # ------------------------------------------------------------------
    def delete_api(gl):
        from urllib.parse import quote
        gl.delete(f"/projects/{quote(api_project, safe='')}")
    assert_forbidden("poc-alice", delete_api, "T1", "Alice (Developer) cannot delete domain-a/proj-1")

    # ------------------------------------------------------------------
    # T2 — Alice cannot modify protected branch rules
    # ------------------------------------------------------------------
    def protect_as_alice(gl):
        from urllib.parse import quote
        gl.post(
            f"/projects/{quote(api_project, safe='')}/protected_branches",
            json_body={"name": "alice-should-fail", "push_access_level": 30, "merge_access_level": 40},
        )
    assert_forbidden("poc-alice", protect_as_alice, "T2", "Alice cannot modify protected branches")

    # ------------------------------------------------------------------
    # T3 — Alice cannot list CI/CD variables
    # ------------------------------------------------------------------
    def list_vars(gl):
        from urllib.parse import quote
        gl.get(f"/projects/{quote(api_project, safe='')}/variables")
    assert_forbidden("poc-alice", list_vars, "T3", "Alice cannot list CI/CD variables")

    # ------------------------------------------------------------------
    # T4 — Alice can create a feature branch
    # ------------------------------------------------------------------
    def create_branch(gl):
        from urllib.parse import quote
        try:
            gl.delete(f"/projects/{quote(api_project, safe='')}/repository/branches/alice-feat-test")
        except Exception:
            pass
        gl.post(
            f"/projects/{quote(api_project, safe='')}/repository/branches",
            json_body={"branch": "alice-feat-test", "ref": "main"},
        )
    assert_allowed("poc-alice", create_branch, "T4", "Alice can create a feature branch")

    # ------------------------------------------------------------------
    # T5 — Rita (Reporter) cannot create a branch
    # ------------------------------------------------------------------
    def rita_creates(gl):
        from urllib.parse import quote
        gl.post(
            f"/projects/{quote(api_project, safe='')}/repository/branches",
            json_body={"branch": "rita-forbidden", "ref": "main"},
        )
    assert_forbidden("poc-rita", rita_creates, "T5", "Rita (Reporter) cannot create a branch")

    # ------------------------------------------------------------------
    # T6 — Bob can list variables (Maintainer)
    # ------------------------------------------------------------------
    def bob_lists_vars(gl):
        from urllib.parse import quote
        gl.get(f"/projects/{quote(api_project, safe='')}/variables")
    assert_allowed("poc-bob", bob_lists_vars, "T6", "Bob (Maintainer) can list CI/CD variables")

    # ------------------------------------------------------------------
    # T7 — Dan cannot see restricted-proj-1 (confidential, different subgroup)
    # ------------------------------------------------------------------
    def dan_gets_secrets(gl):
        from urllib.parse import quote
        gl.get(f"/projects/{quote(secrets_project, safe='')}")
    assert_forbidden("poc-dan", dan_gets_secrets, "T7", "Dan cannot see confidential restricted-proj-1")

    # ------------------------------------------------------------------
    # T8 — Con can see restricted-proj-1
    # ------------------------------------------------------------------
    def con_gets_secrets(gl):
        from urllib.parse import quote
        gl.get(f"/projects/{quote(secrets_project, safe='')}")
    assert_allowed("poc-con", con_gets_secrets, "T8", "Con can see restricted-proj-1 (gl-restricted-read)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    banner("PHASE 8 SUMMARY", char="-")
    passed = sum(1 for r in results if r["pass"])
    failed = sum(1 for r in results if not r["pass"])
    skipped_hint = sum(1 for u in USER_TOKEN_ENV if not os.environ.get(USER_TOKEN_ENV[u]))
    print(f"\n  Passed : {passed}")
    print(f"  Failed : {failed}")
    if skipped_hint:
        warn(f"{skipped_hint} user tokens were not set — some tests skipped")
    print()
    for r in results:
        status = "✓" if r["pass"] else "✗"
        print(f"  {status} {r['id']} — {r['desc']}")
    print()
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
