#!/usr/bin/env python3
"""
Phase 3 — IAM Simulation Groups

Creates the simulated LDAP/SailPoint/SSCAM groups under iam-sim/.
These are empty containers — membership is added in Phase 4.

Usage: python3 phase_03_iam_groups.py
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 3 — IAM Simulation Groups")

    gl = GitLabClient()
    iam_base = f"{config.TOP_GROUP}/{config.IAM_SIM_GROUP}"

    # Three subfolders
    for sub in ["sscam", "sailpoint", "p2p"]:
        step(f"Ensuring {iam_base}/{sub}")
        gl.ensure_group(f"{iam_base}/{sub}", visibility="private")
        done(f"{iam_base}/{sub}")

    # SSCAM groups (Approach 1)
    step("Creating SSCAM groups (Approach 1 project-level)…")
    for g in config.SSCAM_GROUPS:
        path = f"{iam_base}/sscam/{g}"
        gl.ensure_group(path, visibility="private")
        done(path)

    # SailPoint groups (Approach 2)
    step("Creating SailPoint groups (Approach 2 domain-level)…")
    for g in config.SAILPOINT_GROUPS:
        path = f"{iam_base}/sailpoint/{g}"
        gl.ensure_group(path, visibility="private")
        done(path)

    # P2P DevOps groups
    step("Creating P2P DevOps groups…")
    for g in config.P2P_GROUPS:
        path = f"{iam_base}/p2p/{g}"
        gl.ensure_group(path, visibility="private")
        done(path)

    banner("PHASE 3 COMPLETE", char="-")
    done("IAM simulation groups created (empty).")
    done("Next: run phase_04_users.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
