#!/usr/bin/env python3
"""
Phase 3 (v2) — IAM Simulation Groups

v2 keeps BOTH simulated LDAP origins:
  * sailpoint/  — strategic, org-aligned naming (every new grant)
  * sscam/      — legacy, project-level _w/_r naming (kept for partial-
                  migration fidelity; multiple origins can feed the same
                  org subgroup)

Each LDAP group is later (Phase 4) shared with exactly one role-bearing
org subgroup. These containers are empty here — Phase 4 fills them.
"""
import config
from gitlab_client import GitLabClient, banner, step, done, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 3 (v2) — IAM Simulation Groups")
    gl = GitLabClient()

    iam_base = f"{config.TOP_GROUP}/{config.IAM_SIM_GROUP}"

    for sub in ("sailpoint", "sscam"):
        step(f"Ensuring {iam_base}/{sub}")
        gl.ensure_group(f"{iam_base}/{sub}", visibility="private")
        done(f"{iam_base}/{sub}")

    step(f"Creating {len(config.SAILPOINT_GROUPS)} SailPoint LDAP groups…")
    for g in config.SAILPOINT_GROUPS:
        path = f"{iam_base}/sailpoint/{g}"
        gl.ensure_group(path, visibility="private")
        done(path)

    step(f"Creating {len(config.SSCAM_GROUPS)} SSCAM (legacy) LDAP groups…")
    for g in config.SSCAM_GROUPS:
        path = f"{iam_base}/sscam/{g}"
        gl.ensure_group(path, visibility="private")
        done(path)

    banner("PHASE 3 COMPLETE", char="-")
    done("IAM simulation groups created (empty).")
    done("Next: run phase_04_users.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
