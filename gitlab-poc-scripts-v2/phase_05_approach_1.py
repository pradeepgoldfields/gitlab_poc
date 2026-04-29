#!/usr/bin/env python3
"""
Phase 5 (v2) — Hop 2: Organisation → Application

Shares each role-bearing organisation subgroup with the application scope it
owns. Each share carries either a default GitLab role (Developer / Maintainer
/ Reporter / Owner) or a custom role (Promoter / Operator / Security Manager)
attached via member_role_id.

The application tree itself stays empty of direct shares — every grant
flows through this hop.

Idempotent.
"""
from urllib.parse import quote
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 5 (v2) — Hop 2: Organisation → Application")
    gl = GitLabClient()

    # Look up custom-role IDs once (used when ORG_TO_APP_SHARES entry uses
    # `role_name` instead of `role`).
    role_id_by_name = {}
    try:
        roles = gl.list_member_roles() or []
        role_id_by_name = {r["name"]: r["id"] for r in roles}
    except Exception as e:
        warn(f"Could not list custom roles ({e}); custom-role shares will fail.")

    # Apply each org→app share.
    ok = ko = 0
    for share in config.ORG_TO_APP_SHARES:
        org_full = f"{config.TOP_GROUP}/{share['org_path']}"
        app_full = f"{config.TOP_GROUP}/{share['app_path']}"

        # Determine if the share is built-in role or custom role
        is_custom = "role_name" in share
        role_label = share.get("role_name") or share["role"]

        step(f"{org_full}  →  {app_full}  (as {role_label}{' [custom]' if is_custom else ''})")

        # Find target — could be a project or a group
        target_project = gl.find_project(app_full)
        target_group   = None if target_project else gl.find_group(app_full)
        source_group   = gl.find_group(org_full)

        if not source_group:
            fail(f"  source group not found: {org_full}")
            ko += 1
            continue
        if not target_project and not target_group:
            fail(f"  target not found: {app_full}")
            ko += 1
            continue

        # Compute payload
        if is_custom:
            mid = role_id_by_name.get(role_label)
            if mid is None:
                fail(f"  custom role '{role_label}' not found on instance — was Phase 1 run?")
                ko += 1
                continue
            payload = {"group_id": source_group["id"],
                       "group_access": config.ROLE["reporter"],
                       "member_role_id": mid}
        else:
            payload = {"group_id": source_group["id"],
                       "group_access": config.ROLE[role_label]}

        # POST the share. share_*_with_group helpers don't carry member_role_id,
        # so do it manually for both branches for symmetry.
        try:
            if target_project:
                # Idempotency: unshare first if already present
                try:
                    gl.unshare_project_from_group(app_full, org_full)
                except Exception:
                    pass
                enc = quote(app_full, safe="")
                gl.post(f"/projects/{enc}/share", json_body=payload)
            else:
                # Group share — check existing, then POST
                enc = quote(app_full, safe="")
                existing = gl.get(f"/groups/{enc}") or {}
                already = any(
                    link.get("group_id") == source_group["id"]
                    for link in existing.get("shared_with_groups", []) or []
                )
                if already:
                    warn("  already shared — skipping")
                    continue
                gl.post(f"/groups/{enc}/share", json_body=payload)
            done("  share created")
            ok += 1
        except Exception as e:
            fail(f"  share failed: {e}")
            ko += 1

    # Top-level Owner share (e.g. organisations/platform-owners → top group)
    if getattr(config, "TOP_LEVEL_SHARES", None):
        step("Applying top-level group shares (Owner mapping)…")
        for share in config.TOP_LEVEL_SHARES:
            shared = f"{config.TOP_GROUP}/{share['shared_group']}"
            try:
                result = gl.share_group_with_group(
                    config.TOP_GROUP, shared, config.ROLE[share["role"]])
                if result is None:
                    warn(f"  {shared} already shared — skipping")
                else:
                    done(f"  Shared {shared} → {config.TOP_GROUP} as {share['role']}")
                ok += 1
            except Exception as e:
                fail(f"  failed: {e}")
                ko += 1

    banner("PHASE 5 COMPLETE", char="-")
    done(f"{ok} org→app shares applied, {ko} failed.")
    done("Apps now have the access flowing exclusively from the org tree.")
    done("Next: run phase_07_protection.py (Phase 6 is a no-op in v2).")
    return 0 if ko == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
