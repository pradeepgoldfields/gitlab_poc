#!/usr/bin/env python3
"""
Phase 4 — Test Users and IAM Group Membership

1. Ensures 8 test users exist (creates if admin allows, otherwise expects them
   to be pre-provisioned).
2. Adds users to the simulated IAM groups per IAM_MEMBERSHIPS.
3. Adds Dan to the top-level group with Minimal Access.
4. Shares the IAM_DevOps_Owner group with the top group as Owner
   (TOP_LEVEL_SHARES) so the design's Owner mapping is fully wired.

Usage: python3 phase_04_users.py
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 4 — Test Users and IAM Memberships")

    gl = GitLabClient()

    # 1. Ensure users exist
    step("Ensuring 8 test user accounts exist…")
    user_cache = {}
    for u in config.TEST_USERS:
        existing = gl.find_user_by_username(u["username"])
        if existing:
            done(f"{u['username']} exists (id={existing['id']})")
            user_cache[u["username"]] = existing
            continue
        step(f"Creating {u['username']}…")
        try:
            created = gl.ensure_user(
                username=u["username"],
                email=u["email"],
                name=u["name"],
                password=config.TEST_USER_DEFAULT_PASSWORD,
            )
            done(f"Created {u['username']} (id={created['id']})")
            user_cache[u["username"]] = created
        except Exception as e:
            fail(f"Cannot create {u['username']}: {e}")
            fail("Pre-provision the user manually, or use an admin token.")
            return 1

    # 2. Add users to IAM-sim groups
    step("Assigning IAM group memberships…")
    for group_rel_path, usernames in config.IAM_MEMBERSHIPS.items():
        full_path = f"{config.TOP_GROUP}/{group_rel_path}"
        for username in usernames:
            user = user_cache.get(username)
            if not user:
                warn(f"User {username} not cached — skipping")
                continue
            try:
                result = gl.add_group_member(
                    full_path, user["id"], config.ROLE["developer"]
                )
                if result is None:
                    warn(f"{username} already in {full_path}")
                else:
                    done(f"Added {username} → {full_path}")
            except Exception as e:
                fail(f"Failed to add {username} to {full_path}: {e}")

    # 3. Minimal Access at top-level
    step("Adding top-level Minimal Access users (for inner-source contributors)…")
    for username in config.TOP_LEVEL_MINIMAL_ACCESS_USERS:
        user = user_cache.get(username)
        if not user:
            warn(f"User {username} not cached — skipping")
            continue
        try:
            result = gl.add_group_member(
                config.TOP_GROUP, user["id"], config.ROLE["minimal"]
            )
            if result is None:
                warn(f"{username} already has top-level access")
            else:
                done(f"Added {username} → {config.TOP_GROUP} (Minimal Access)")
        except Exception as e:
            fail(f"Failed to add {username}: {e}")

    # 4. Top-level group shares (e.g. IAM_DevOps_Owner → Owner on top group).
    if getattr(config, "TOP_LEVEL_SHARES", None):
        step("Applying top-level group shares (design's TOBE Owner mapping)…")
        for share in config.TOP_LEVEL_SHARES:
            shared = f"{config.TOP_GROUP}/{share['shared_group']}"
            role = share["role"]
            access_level = config.ROLE[role]
            try:
                result = gl.share_group_with_group(
                    config.TOP_GROUP, shared, access_level)
                if result is None:
                    warn(f"{shared} already shared with {config.TOP_GROUP}")
                else:
                    done(f"Shared {shared} → {config.TOP_GROUP} as {role}")
            except Exception as e:
                fail(f"Failed to share {shared}: {e}")

    banner("PHASE 4 COMPLETE", char="-")
    done("All test users are in their simulated IAM groups.")
    done("Next: run phase_05_approach_1.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
