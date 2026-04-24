#!/usr/bin/env python3
"""
Phase 1 — Custom Roles (instance-level)

Creates Promoter, Operator, and Security Manager custom roles.
Requires an admin token (GITLAB_ADMIN_TOKEN).

Usage: python3 phase_01_custom_roles.py
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 1 — Custom Roles")

    gl = GitLabClient()

    # Verify admin access
    step("Checking instance admin access…")
    try:
        existing = gl.list_member_roles()
    except Exception as e:
        fail(f"Could not list member roles: {e}")
        fail("This script requires an admin PAT. Check GITLAB_ADMIN_TOKEN.")
        return 1

    existing_names = {r.get("name") for r in existing}
    if existing_names:
        step(f"Found existing custom roles: {sorted(existing_names)}")

    for role_def in config.CUSTOM_ROLES:
        name = role_def["name"]
        if name in existing_names:
            warn(f"Role '{name}' already exists — skipping")
            continue
        step(f"Creating custom role: {name}")
        try:
            created = gl.ensure_member_role(
                name=role_def["name"],
                description=role_def["description"],
                base_role=role_def["base_role"],
                abilities=role_def["abilities"],
            )
            done(f"Created '{name}' (id={created.get('id')}) with abilities: {role_def['abilities']}")
        except Exception as e:
            fail(f"Failed to create '{name}': {e}")
            return 1

    banner("PHASE 1 COMPLETE", char="-")
    done("Three custom roles are now available.")
    done("Next: run phase_02_hierarchy.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
