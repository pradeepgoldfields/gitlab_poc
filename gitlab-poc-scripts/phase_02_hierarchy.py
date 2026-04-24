#!/usr/bin/env python3
"""
Phase 2 — Hierarchy Skeleton

Creates the analysis-aligned hierarchy:
  acme-poc/
    business-unit-a/
      domain-a/{proj-1,proj-2,proj-3} + restricted/restricted-proj-1
      domain-b/{proj-1,proj-2,proj-3}
    iam-sim/     (Private — simulated LDAP groups)
    platform/ci-templates

Deployment-model isolation (live-prod / non-live / cloud landing zone) is
NOT a group-nesting concern in this hierarchy. It's expressed instead via:
  * environment-scoped CI variables (Phase 11)
  * protected environments named after the zone (Phase 7)
  * group-level runners tagged by zone (Phase 11 manual step)

Idempotent — safe to re-run.

Usage: python3 phase_02_hierarchy.py
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 2 — Hierarchy Skeleton")

    gl = GitLabClient()

    # Top-level group
    step(f"Ensuring top-level group: {config.TOP_GROUP}")
    top = gl.ensure_group(config.TOP_GROUP, visibility=config.TOP_GROUP_VISIBILITY)
    done(f"{config.TOP_GROUP} (id={top['id']})")

    # IAM simulation container (Private)
    iam_path = f"{config.TOP_GROUP}/{config.IAM_SIM_GROUP}"
    step(f"Ensuring IAM simulation container: {iam_path} (Private)")
    gl.ensure_group(iam_path, visibility="private")
    done(iam_path)

    # Platform group
    plat_path = f"{config.TOP_GROUP}/{config.PLATFORM_GROUP}"
    step(f"Ensuring platform group: {plat_path}")
    gl.ensure_group(plat_path, visibility="internal")
    done(plat_path)

    # Business-unit subgroup (single-BU PoC; multi-BU = repeat this loop).
    bu_path = f"{config.TOP_GROUP}/{config.BUSINESS_UNIT_GROUP}"
    step(f"Ensuring business-unit subgroup: {bu_path}")
    gl.ensure_group(bu_path, visibility="internal")
    done(bu_path)

    # Business domains — sit under business-unit-a/
    for domain in config.DOMAINS:
        path = f"{config.TOP_GROUP}/{domain}"
        step(f"Ensuring domain: {path}")
        gl.ensure_group(path, visibility="internal")
        done(path)

    # Restricted subgroups (always Private). Created on demand for any
    # domain that has a `<domain>/restricted` entry in PROJECTS.
    restricted_paths = sorted({
        parent for parent in config.PROJECTS
        if parent.endswith("/restricted")
    })
    for rpath in restricted_paths:
        full = f"{config.TOP_GROUP}/{rpath}"
        step(f"Ensuring restricted subgroup (Private): {full}")
        gl.ensure_group(full, visibility="private")
        done(full)

    # Projects
    for parent_rel_path, projects in config.PROJECTS.items():
        for proj_name in projects:
            full_proj_path = f"{config.TOP_GROUP}/{parent_rel_path}/{proj_name}"
            step(f"Ensuring project: {full_proj_path}")
            existing = gl.find_project(full_proj_path)
            if existing:
                warn(f"Already exists: {full_proj_path}")
            else:
                gl.ensure_project(full_proj_path, initialize_readme=True)
                done(f"Created {full_proj_path}")

    banner("PHASE 2 COMPLETE", char="-")
    done("Hierarchy is in place.")
    done("Next: run phase_03_iam_groups.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
