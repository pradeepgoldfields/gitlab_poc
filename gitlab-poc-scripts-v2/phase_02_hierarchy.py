#!/usr/bin/env python3
"""
Phase 2 (v2) — Hierarchy Skeleton

Creates the v2 three-tier hierarchy:

  acme-poc-v2/
    applications/
      domain-a/subdomain-a/{proj-1,proj-2,proj-3} + restricted/restricted-proj-1
      domain-b/subdomain-b/{proj-4,proj-5,proj-6} + restricted/restricted-proj-2
    organisations/
      platform-owners                              (top-level role group)
      tribe-1/
        tribe-leads, security-partners
        squad-1/{squad-leads, operators, promoters, developers, reporters}
        squad-2/{squad-leads, operators, promoters, developers, reporters}
      tribe-2/
        tribe-leads, security-partners
        squad-3/{squad-leads, operators, promoters, developers, reporters}
    platform/ci-templates
    iam-sim/sailpoint/...    (Private — simulated LDAP groups; Phase 3 fills it)

Idempotent — safe to re-run.
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 2 (v2) — Hierarchy Skeleton")
    gl = GitLabClient()

    # Top-level group
    step(f"Ensuring top-level group: {config.TOP_GROUP}")
    top = gl.ensure_group(config.TOP_GROUP, visibility=config.TOP_GROUP_VISIBILITY)
    done(f"{config.TOP_GROUP} (id={top['id']})")

    # iam-sim (Private)
    iam_path = f"{config.TOP_GROUP}/{config.IAM_SIM_GROUP}"
    step(f"Ensuring IAM-sim container: {iam_path} (Private)")
    gl.ensure_group(iam_path, visibility="private")
    done(iam_path)

    # platform (Internal)
    plat_path = f"{config.TOP_GROUP}/{config.PLATFORM_GROUP}"
    step(f"Ensuring platform group: {plat_path}")
    gl.ensure_group(plat_path, visibility="internal")
    done(plat_path)

    # applications root + tree
    apps_root = f"{config.TOP_GROUP}/{config.APPS_GROUP}"
    step(f"Ensuring applications root: {apps_root}")
    gl.ensure_group(apps_root, visibility="internal")
    done(apps_root)

    # Walk APPLICATIONS keys to create every domain / subdomain / restricted/
    seen_groups = set()
    for parent_rel in config.APPLICATIONS:
        parts = parent_rel.split("/")
        for i in range(1, len(parts) + 1):
            path = f"{config.APPS_GROUP}/{'/'.join(parts[:i])}"
            if path in seen_groups:
                continue
            seen_groups.add(path)
            full = f"{config.TOP_GROUP}/{path}"
            visibility = "private" if path.endswith("/restricted") else "internal"
            step(f"Ensuring app subgroup: {full} ({visibility})")
            gl.ensure_group(full, visibility=visibility)
            done(full)

    # Application projects
    # Visibility note: GitLab defaults new projects to Private, but in v2
    # we want non-restricted projects to be Internal so the inner-source
    # discoverability works AND so the deep org→app inheritance chain
    # resolves correctly at the API permission layer (Private + transitive
    # share-of-share has known evaluation gaps).
    for parent_rel, projects in config.APPLICATIONS.items():
        is_restricted = "/restricted" in parent_rel
        proj_visibility = "private" if is_restricted else "internal"
        for proj_name in projects:
            full_proj_path = f"{config.TOP_GROUP}/{config.APPS_GROUP}/{parent_rel}/{proj_name}"
            step(f"Ensuring project: {full_proj_path} ({proj_visibility})")
            existing = gl.find_project(full_proj_path)
            if existing:
                warn(f"Already exists: {full_proj_path}")
            else:
                gl.ensure_project(full_proj_path, initialize_readme=True,
                                   visibility=proj_visibility)
                done(f"Created {full_proj_path}")

    # Platform projects
    for proj_name in config.PLATFORM_PROJECTS:
        full = f"{config.TOP_GROUP}/{config.PLATFORM_GROUP}/{proj_name}"
        step(f"Ensuring platform project: {full}")
        existing = gl.find_project(full)
        if existing:
            warn(f"Already exists: {full}")
        else:
            gl.ensure_project(full, initialize_readme=True)
            done(f"Created {full}")

    # ------------------------------------------------------------------
    # organisations/ tree — the role-bearing org subgroups.
    # ------------------------------------------------------------------
    orgs_root = f"{config.TOP_GROUP}/{config.ORGS_GROUP}"
    step(f"Ensuring organisations root: {orgs_root}")
    gl.ensure_group(orgs_root, visibility="internal")
    done(orgs_root)

    for rg in config.TOP_LEVEL_ROLE_GROUPS:
        path = f"{config.TOP_GROUP}/{config.ORGS_GROUP}/{rg}"
        step(f"Ensuring top-level role group: {path}")
        gl.ensure_group(path, visibility="internal")
        done(path)

    for tribe, squads in config.ORGANISATIONS.items():
        tribe_path = f"{config.TOP_GROUP}/{config.ORGS_GROUP}/{tribe}"
        step(f"Ensuring tribe: {tribe_path}")
        gl.ensure_group(tribe_path, visibility="internal")
        done(tribe_path)
        for trg in config.TRIBE_ROLE_GROUPS:
            path = f"{tribe_path}/{trg}"
            step(f"Ensuring tribe role group: {path}")
            gl.ensure_group(path, visibility="internal")
            done(path)
        for squad in squads:
            squad_path = f"{tribe_path}/{squad}"
            step(f"Ensuring squad: {squad_path}")
            gl.ensure_group(squad_path, visibility="internal")
            done(squad_path)
            for srg in config.SQUAD_ROLE_GROUPS:
                path = f"{squad_path}/{srg}"
                step(f"Ensuring squad role group: {path}")
                gl.ensure_group(path, visibility="internal")
                done(path)

    banner("PHASE 2 COMPLETE", char="-")
    done("v2 hierarchy is in place: applications/, organisations/, iam-sim/, platform/.")
    done("Next: run phase_03_iam_groups.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
