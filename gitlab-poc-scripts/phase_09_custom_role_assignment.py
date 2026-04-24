#!/usr/bin/env python3
"""
Phase 9 — Custom Role Assignment

Assigns the three custom roles (Promoter, Operator, Security Manager) to their
P2P IAM groups on domain-a/proj-1, then shares those groups with the project
using the custom role IDs.

Note: the Operator layered restriction requires protected environment/branch
allow-lists, which were set up in Phase 7. This phase completes the Custom Role
assignment layer.

Usage: python3 phase_09_custom_role_assignment.py
"""
import config
from config import _suffix  # noqa: PLC2701  (test-suite-style internal util)
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


# Mapping from Custom Role name -> P2P IAM group that should hold that role.
# Names flow through _suffix so they pick up POC_PREFIX (matching config.py).
CUSTOM_ROLE_ASSIGNMENTS = [
    {
        "custom_role_name": _suffix("Promoter"),
        "iam_group": "iam-sim/p2p/IAM_DevOps_domain-a_Promoter",
        "target_project": "live-production/domain-a/proj-1",
    },
    {
        "custom_role_name": _suffix("Operator"),
        "iam_group": "iam-sim/p2p/IAM_DevOps_domain-a_Operator",
        "target_project": "live-production/domain-a/proj-1",
    },
    {
        "custom_role_name": _suffix("Security Manager"),
        "iam_group": "iam-sim/p2p/IAM_DevOps_domain-a_SecurityManager",
        "target_project": "live-production/domain-a/proj-1",
    },
]


def main():
    require_admin_token()
    banner("PHASE 9 — Custom Role Assignment")

    gl = GitLabClient()

    # Fetch existing member roles to get their IDs
    step("Fetching existing custom roles…")
    roles = gl.list_member_roles()
    role_map = {r["name"]: r for r in roles}
    missing = [a["custom_role_name"] for a in CUSTOM_ROLE_ASSIGNMENTS
               if a["custom_role_name"] not in role_map]
    if missing:
        fail(f"Custom roles not found on instance: {missing}")
        fail("Run phase_01_custom_roles.py first.")
        return 1

    for name in [_suffix("Promoter"), _suffix("Operator"), _suffix("Security Manager")]:
        done(f"Found custom role '{name}' (id={role_map[name]['id']})")

    # Share each IAM group with the target project at base Reporter level,
    # and attach the member_role_id so the custom abilities apply.
    for assignment in CUSTOM_ROLE_ASSIGNMENTS:
        target = f"{config.TOP_GROUP}/{assignment['target_project']}"
        shared = f"{config.TOP_GROUP}/{assignment['iam_group']}"
        role_info = role_map[assignment["custom_role_name"]]
        step(f"Sharing {shared} with {target} as {assignment['custom_role_name']} "
             f"(base access reporter + member_role_id={role_info['id']})")

        project = gl.find_project(target)
        shared_group = gl.find_group(shared)
        if not project or not shared_group:
            fail(f"Missing: project={project} group={shared_group}")
            continue

        from urllib.parse import quote
        encoded = quote(target, safe="")
        # Remove existing share to make idempotent
        try:
            gl.unshare_project_from_group(target, shared)
        except Exception:
            pass

        try:
            result = gl.post(
                f"/projects/{encoded}/share",
                json_body={
                    "group_id": shared_group["id"],
                    "group_access": config.ROLE["reporter"],
                    "member_role_id": role_info["id"],
                },
            )
            done(f"Share created with custom role attached")
        except Exception as e:
            fail(f"Share failed for {assignment['custom_role_name']}: {e}")

    banner("PHASE 9 COMPLETE", char="-")
    done("Custom roles are assigned on domain-a/proj-1.")
    done("Manual tests required for full validation — see execution guide Phase 9.")
    done("Next: run phase_10_inner_source.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
