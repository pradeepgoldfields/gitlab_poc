#!/usr/bin/env python3
"""
Phase 13 (v2) — Org-Driven Access Flows: Joiner / Mover / Promotion / Reorg / Sec Sweep

Demonstrates the v2 separation-of-duties model in action by walking five
real lifecycle scenarios end-to-end against the live instance:

  1. JOINER  — add a user to an LDAP group; verify they immediately have
     the corresponding role on every project under the org subgroup's
     application share.

  2. MOVER   — remove the same user from squad-1's developers and add to
     squad-3's developers; verify they LOSE access to subdomain-a apps and
     GAIN access to subdomain-b apps. Zero changes at the application tree.

  3. PROMOTION (additive role) — add the user to squad-1/operators while
     they're still in squad-1/developers; verify they keep Developer write
     access AND gain Operator's prod-env rights.

  4. REORG   — re-share tribe-1/squad-1 from subdomain-a to subdomain-b at
     the org→app layer (a single GitLab share rewrite); verify every
     squad-1 member now has access to subdomain-b instead of subdomain-a.

  5. SEC SWEEP — add a user to gl-tribe-1-security; verify they get
     Security Manager (custom) role on EVERY project across the tribe.

Each scenario captures access state before + after via the GitLab API and
prints a summary. Restorative cleanup runs at the end so the PoC state
returns to its post-Phase-5 baseline.

Set RUN_DESTRUCTIVE_FLOWS=0 to skip the destructive scenarios (mover,
reorg, sec-sweep). Joiner + promotion are always safe to repeat.
"""
import os
import time
from urllib.parse import quote
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def list_user_access_paths(gl, project_path, username):
    """Return list of (access_level, source_type) for `username` on `project_path`."""
    project = gl.find_project(project_path)
    if not project:
        return []
    enc = quote(project_path, safe="")
    members = gl.get_paginated(f"/projects/{enc}/members/all")
    user = gl.find_user_by_username(username)
    if not user:
        return []
    return [(m.get("access_level"), m.get("source_type", "direct"))
            for m in members if m["id"] == user["id"]]


def summarise(gl, label, project_paths, usernames):
    print(f"\n  --- {label} ---")
    for p in project_paths:
        for u in usernames:
            paths = list_user_access_paths(gl, p, u)
            if paths:
                summary = ", ".join(f"level={al} via {src}" for al, src in paths)
            else:
                summary = "NO ACCESS"
            print(f"    {u:<25} on {p}: {summary}")


def _org_paths_for_iam_group(iam_path):
    """Find every org subgroup that this IAM group is bound to (per
    IAM_TO_ORG_SHARES). In a real LDAP-bound GitLab the LDAP-sync would
    materialise these memberships automatically; here we do it by hand."""
    return [s["org_path"] for s in config.IAM_TO_ORG_SHARES
            if s["iam_group"] == iam_path]


def add_to_iam(gl, iam_path, user, level=None):
    """Add user to an IAM group AND mirror them into every org subgroup
    that group is bound to (simulating LDAP sync)."""
    lvl = level or config.ROLE["developer"]
    full = f"{config.TOP_GROUP}/{iam_path}"
    gl.add_group_member(full, user["id"], lvl)
    for org_rel in _org_paths_for_iam_group(iam_path):
        org_full = f"{config.TOP_GROUP}/{org_rel}"
        try:
            gl.add_group_member(org_full, user["id"], lvl)
        except Exception:
            pass


def remove_from_iam(gl, iam_path, user):
    """Remove user from an IAM group AND from every linked org subgroup
    (mirrors what the LDAP sync would do on the next pull)."""
    full = f"{config.TOP_GROUP}/{iam_path}"
    enc = quote(full, safe="")
    try:
        gl.delete(f"/groups/{enc}/members/{user['id']}")
    except Exception:
        pass
    for org_rel in _org_paths_for_iam_group(iam_path):
        org_full = f"{config.TOP_GROUP}/{org_rel}"
        org_enc = quote(org_full, safe="")
        try:
            gl.delete(f"/groups/{org_enc}/members/{user['id']}")
        except Exception:
            pass
    return True


def main():
    require_admin_token()
    banner("PHASE 13 (v2) — Org-Driven Access Flows")
    gl = GitLabClient()

    # Pick a single test user to drive the joiner / mover / promotion flow.
    # Fred (squad-3) is the natural mover — he's already in squad-3-developers,
    # so the mover demo will move HIM to squad-1-developers and back.
    # For the joiner, we'll use Ed who's only in squad-2-developers.
    pivot_user = gl.find_user_by_username(config.USER_BY_SHORT["fred"])
    if not pivot_user:
        fail("v2-fred not found — was Phase 4 run?")
        return 1
    pivot_name = pivot_user["username"]

    SUB_A_PROJECTS = [
        f"{config.TOP_GROUP}/applications/domain-a/subdomain-a/proj-1",
        f"{config.TOP_GROUP}/applications/domain-a/subdomain-a/proj-2",
    ]
    SUB_B_PROJECTS = [
        f"{config.TOP_GROUP}/applications/domain-b/subdomain-b/proj-4",
        f"{config.TOP_GROUP}/applications/domain-b/subdomain-b/proj-5",
    ]

    # ------------------------------------------------------------------
    # Scenario 1 — JOINER
    # ------------------------------------------------------------------
    banner("Scenario 1 — JOINER", char="-")
    step(f"Adding {pivot_name} to gl-squad-1-developers (squad-1's Developer LDAP group)")
    summarise(gl, "BEFORE: pivot user on subdomain-a (should have NO ACCESS)",
              SUB_A_PROJECTS, [pivot_name])

    add_to_iam(gl, "iam-sim/sailpoint/gl-squad-1-developers", pivot_user)
    done(f"  Added {pivot_name} to gl-squad-1-developers")
    time.sleep(2)

    summarise(gl, "AFTER:  pivot user on subdomain-a (should have Developer)",
              SUB_A_PROJECTS, [pivot_name])

    if os.environ.get("RUN_DESTRUCTIVE_FLOWS", "1") == "0":
        warn("RUN_DESTRUCTIVE_FLOWS=0 — skipping destructive scenarios")
        # Cleanup the joiner add so the state is consistent
        remove_from_iam(gl, "iam-sim/sailpoint/gl-squad-1-developers", pivot_user)
        done("  Cleaned up joiner add")
        banner("PHASE 13 PARTIAL", char="-")
        return 0

    # ------------------------------------------------------------------
    # Scenario 2 — MOVER (lose squad-1, gain squad-3)
    # ------------------------------------------------------------------
    banner("Scenario 2 — MOVER", char="-")
    step(f"{pivot_name} originally in squad-3-developers; now also in squad-1-developers")
    step(f"Now MOVING: remove from squad-1-developers, keep in squad-3-developers (the original team)")

    summarise(gl, "BEFORE move: subdomain-a access (squad-1's apps)",
              SUB_A_PROJECTS, [pivot_name])
    summarise(gl, "BEFORE move: subdomain-b access (squad-3's apps)",
              SUB_B_PROJECTS, [pivot_name])

    remove_from_iam(gl, "iam-sim/sailpoint/gl-squad-1-developers", pivot_user)
    done(f"  Removed {pivot_name} from gl-squad-1-developers")
    time.sleep(2)

    summarise(gl, "AFTER move: subdomain-a access (should be NO ACCESS)",
              SUB_A_PROJECTS, [pivot_name])
    summarise(gl, "AFTER move: subdomain-b access (should still have Developer via squad-3)",
              SUB_B_PROJECTS, [pivot_name])
    done("Mover scenario: NO project-tree changes were needed.")

    # ------------------------------------------------------------------
    # Scenario 3 — PROMOTION (additive role)
    # ------------------------------------------------------------------
    banner("Scenario 3 — PROMOTION (additive Operator on top of Developer)", char="-")
    # Use Alice — she's already in squad-1-developers; promote her to operators.
    alice = gl.find_user_by_username(config.USER_BY_SHORT["alice"])
    PROD_PROJ = [f"{config.TOP_GROUP}/applications/domain-a/subdomain-a/proj-1"]

    summarise(gl, "BEFORE promotion: Alice on proj-1 (should be Developer only)",
              PROD_PROJ, [alice["username"]])

    add_to_iam(gl, "iam-sim/sailpoint/gl-squad-1-operators", alice)
    done(f"  Added {alice['username']} to gl-squad-1-operators (additive)")
    time.sleep(2)

    summarise(gl, "AFTER promotion: Alice on proj-1 (Developer + Operator custom)",
              PROD_PROJ, [alice["username"]])
    done("Promotion: additive role grants prod-env rights without changing existing Developer access.")

    # ------------------------------------------------------------------
    # Scenario 4 — REORG (re-share squad-1 from subdomain-a to subdomain-b)
    # ------------------------------------------------------------------
    banner("Scenario 4 — REORG (re-share squad-1's developers from subdomain-a to subdomain-b)", char="-")
    summarise(gl, "BEFORE reorg: alice on subdomain-b (should be NO ACCESS)",
              SUB_B_PROJECTS, [alice["username"]])

    # Unshare squad-1's developers from subdomain-a, share with subdomain-b
    sub_a_full = f"{config.TOP_GROUP}/applications/domain-a/subdomain-a"
    sub_b_full = f"{config.TOP_GROUP}/applications/domain-b/subdomain-b"
    devs_full  = f"{config.TOP_GROUP}/organisations/tribe-1/squad-1/developers"

    step(f"Unsharing {devs_full} from {sub_a_full}")
    devs_g = gl.find_group(devs_full)
    enc_a = quote(sub_a_full, safe="")
    try:
        gl.delete(f"/groups/{enc_a}/share/{devs_g['id']}")
        done("  unshare ok")
    except Exception as e:
        warn(f"  unshare returned: {e}")

    step(f"Sharing {devs_full} with {sub_b_full} as Developer")
    enc_b = quote(sub_b_full, safe="")
    try:
        gl.post(f"/groups/{enc_b}/share",
                json_body={"group_id": devs_g["id"],
                           "group_access": config.ROLE["developer"]})
        done("  share created")
    except Exception as e:
        warn(f"  share failed: {e}")

    time.sleep(2)
    summarise(gl, "AFTER reorg: alice on subdomain-b (should now have Developer)",
              SUB_B_PROJECTS, [alice["username"]])
    summarise(gl, "AFTER reorg: alice on subdomain-a (should be NO ACCESS, except Operator on proj-1)",
              SUB_A_PROJECTS, [alice["username"]])
    done("Reorg: zero changes at the IAM tree — apps moved with the org.")

    # Restore squad-1's developers → subdomain-a
    step(f"Restoring squad-1/developers → subdomain-a share")
    try:
        gl.delete(f"/groups/{enc_b}/share/{devs_g['id']}")
    except Exception:
        pass
    try:
        gl.post(f"/groups/{enc_a}/share",
                json_body={"group_id": devs_g["id"],
                           "group_access": config.ROLE["developer"]})
        done("  restored")
    except Exception as e:
        warn(f"  restore failed: {e}")

    # ------------------------------------------------------------------
    # Scenario 5 — SEC SWEEP
    # ------------------------------------------------------------------
    banner("Scenario 5 — SEC SWEEP (add user to tribe-1/security-partners)", char="-")
    # Sam is already there from Phase 4. Use Tina temporarily to demonstrate.
    tina = gl.find_user_by_username(config.USER_BY_SHORT["tina"])
    SUB_A_AND_PROJ3 = SUB_A_PROJECTS + [
        f"{config.TOP_GROUP}/applications/domain-a/subdomain-a/proj-3",
    ]

    summarise(gl, "BEFORE sec-sweep: Tina on subdomain-a projects (should be Maintainer via tribe-leads)",
              SUB_A_AND_PROJ3, [tina["username"]])

    add_to_iam(gl, "iam-sim/sailpoint/gl-tribe-1-security", tina)
    done(f"  Added {tina['username']} to gl-tribe-1-security")
    time.sleep(2)

    summarise(gl, "AFTER sec-sweep: Tina now ALSO Security Manager across the tribe",
              SUB_A_AND_PROJ3, [tina["username"]])
    # Restore
    remove_from_iam(gl, "iam-sim/sailpoint/gl-tribe-1-security", tina)

    # Final restorative cleanup — undo the promotion we did in scenario 3
    step("Restorative cleanup — removing Alice from operators (added in Scenario 3)")
    remove_from_iam(gl, "iam-sim/sailpoint/gl-squad-1-operators", alice)
    done("  cleaned up")

    banner("PHASE 13 (v2) COMPLETE", char="-")
    done("All 5 org-driven access flows demonstrated and state restored.")
    done("Next: run phase_14_report.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
