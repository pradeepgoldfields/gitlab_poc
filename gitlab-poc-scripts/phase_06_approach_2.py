#!/usr/bin/env python3
"""
Phase 6 — Approach 2 (Target) Configuration

Shares SailPoint groups at the trade domain level only — no project-level
shares. Access flows purely by inheritance.

Usage: python3 phase_06_approach_2.py
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 6 — Approach 2 (Target) Configuration")

    gl = GitLabClient()

    for share in config.APPROACH_2_SHARES:
        target = f"{config.TOP_GROUP}/{share['target']}"
        shared = f"{config.TOP_GROUP}/{share['shared_group']}"
        role = share["role"]
        access_level = config.ROLE[role]

        step(f"Sharing: {shared}  →  {target}  (as {role})")
        try:
            result = gl.share_group_with_group(target, shared, access_level)
            if result is None:
                warn("Already shared — skipping")
            else:
                done("Share created")
        except Exception as e:
            fail(f"Failed: {e}")
            return 1

    banner("PHASE 6 COMPLETE", char="-")
    done("Approach 2 shares on trade/ are in place.")
    done("Verify: any user added to gl-trade-dev should now have Developer on all trade projects.")
    done("Next: run phase_07_protection.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
