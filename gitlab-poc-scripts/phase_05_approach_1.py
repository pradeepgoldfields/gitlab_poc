#!/usr/bin/env python3
"""
Phase 5 — Approach 1 (Hybrid) Configuration

Shares SSCAM project-level groups with payments/api plus optional product-level
SailPoint share at domain level, per APPROACH_1_SHARES.

Usage: python3 phase_05_approach_1.py
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 5 — Approach 1 (Hybrid) Configuration")

    gl = GitLabClient()

    for share in config.APPROACH_1_SHARES:
        target = f"{config.TOP_GROUP}/{share['target']}"
        shared = f"{config.TOP_GROUP}/{share['shared_group']}"
        role = share["role"]
        access_level = config.ROLE[role]

        step(f"Sharing: {shared}  →  {target}  (as {role})")

        # Determine if target is a project or a group
        project = gl.find_project(target)
        try:
            if project:
                result = gl.share_project_with_group(target, shared, access_level)
            else:
                result = gl.share_group_with_group(target, shared, access_level)
            if result is None:
                warn("Already shared — skipping")
            else:
                done("Share created")
        except Exception as e:
            fail(f"Failed: {e}")
            return 1

    banner("PHASE 5 COMPLETE", char="-")
    done("Approach 1 (hybrid) shares are in place on payments/api.")
    done("Next: run phase_06_approach_2.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
