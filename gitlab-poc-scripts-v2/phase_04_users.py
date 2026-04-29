#!/usr/bin/env python3
"""
Phase 4 (v2) — Test Users + Hop 1 (IAM-sim → Organisation tree)

1. Ensures the 12 test users exist (creates them if admin allows).
2. Adds users to the simulated IAM-sim/sailpoint/* LDAP groups per
   IAM_MEMBERSHIPS (still the "LDAP membership" hop).
3. Shares each LDAP group with the matching role-bearing org subgroup
   per IAM_TO_ORG_SHARES (this is Hop 1: IAM → Org).
4. Adds Dan to the top-level group with Minimal Access (inner-source
   contributor; deliberately bypasses both the IAM and org trees).

The actual privileges on application projects are wired up in Phase 5
via Hop 2 (org → app).
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 4 (v2) — Test Users + Hop 1 (IAM → Org)")
    gl = GitLabClient()

    # 1. Ensure users exist
    step(f"Ensuring {len(config.TEST_USERS)} test user accounts exist…")
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
            return 1

    # 2. Add users to IAM-sim LDAP groups (the "LDAP membership" half)
    # These memberships are the simulation: in production GitLab's LDAP-sync
    # would pull these from AD/SailPoint and write them down. We populate the
    # IAM-sim subgroups directly so anyone inspecting the IAM-sim tree sees
    # the complete LDAP roster (the design's source-of-truth statement).
    step("Assigning IAM-sim LDAP group memberships…")
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

    # 3. Hop 1 — provision LDAP members into their org subgroups.
    # GitLab's group-sharing mechanism does NOT propagate transitively —
    # if A is shared with B and C is shared with B's projects, A's members
    # don't reach C. So we materialise the LDAP→org membership directly:
    # for every IAM_TO_ORG_SHARES entry, every user in the IAM source group
    # is added as a *direct member* of the target org subgroup. This is
    # exactly what real GitLab LDAP-group-sync does.
    step("Hop 1 — provisioning LDAP members directly into org subgroups…")
    for share in config.IAM_TO_ORG_SHARES:
        iam_rel = share["iam_group"]
        org_full = f"{config.TOP_GROUP}/{share['org_path']}"
        usernames = config.IAM_MEMBERSHIPS.get(iam_rel, [])
        if not usernames:
            done(f"  {iam_rel}: no members to provision")
            continue
        for username in usernames:
            user = user_cache.get(username)
            if not user:
                continue
            try:
                result = gl.add_group_member(
                    org_full, user["id"], config.ROLE["developer"])
                if result is None:
                    warn(f"  {username} already in {org_full}")
                else:
                    done(f"  Provisioned {username} → {org_full}  (via {iam_rel})")
            except Exception as e:
                fail(f"  Failed to provision {username} → {org_full}: {e}")

    # 4. Top-level Minimal Access (inner-source contributor — Dan)
    step("Adding top-level Minimal Access users (inner-source contributors)…")
    for username in config.TOP_LEVEL_MINIMAL_ACCESS_USERS:
        user = user_cache.get(username)
        if not user:
            warn(f"User {username} not cached — skipping")
            continue
        try:
            result = gl.add_group_member(
                config.TOP_GROUP, user["id"], config.ROLE["minimal"])
            if result is None:
                warn(f"{username} already has top-level access")
            else:
                done(f"Added {username} → {config.TOP_GROUP} (Minimal Access)")
        except Exception as e:
            fail(f"Failed to add {username}: {e}")

    banner("PHASE 4 COMPLETE", char="-")
    done("Users are in their LDAP groups; LDAP groups are shared with org subgroups.")
    done("Next: run phase_05_org_to_app.py (Hop 2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
