#!/usr/bin/env python3
"""
Phase 2 — Hierarchy Skeleton

Creates the deployment-zone hierarchy:
  acme-poc/
    live-production/payments/{api,ui,batch} + restricted/payments-secrets
    live-production/trade/{orders,settlements,reconciliation}
    live-cloud-landing-zone/payments
    non-live-enterprise/payments
    iam-sim/     (Private)
    platform/ci-templates

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

    # Deployment zones
    for zone in config.DEPLOYMENT_ZONES:
        path = f"{config.TOP_GROUP}/{zone['path']}"
        step(f"Ensuring zone: {path}")
        gl.ensure_group(path, visibility=zone["visibility"])
        done(path)

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

    # Domains
    for zone, domains in config.DOMAINS.items():
        for domain in domains:
            path = f"{config.TOP_GROUP}/{zone}/{domain}"
            step(f"Ensuring domain: {path}")
            gl.ensure_group(path, visibility="internal")
            done(path)

    # Restricted subgroups (always Private)
    for rpath in ["live-production/payments/restricted", "live-production/trade/restricted"]:
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
