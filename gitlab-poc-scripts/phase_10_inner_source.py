#!/usr/bin/env python3
"""
Phase 10 — Inner Source & Confidential Tests

Verifies via API:
  - Dan (top-level Minimal Access) can see Internal projects
  - Dan cannot see projects under Private restricted/ subgroup
  - Dan can fork an Internal project
  - Con can see payments-secrets but not api/ui/batch (depending on visibility)

Requires user tokens: POC_DAN_TOKEN, POC_CON_TOKEN

Usage: python3 phase_10_inner_source.py
"""
import os
from urllib.parse import quote
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail


def client_for_env(var):
    token = os.environ.get(var)
    return GitLabClient(token=token) if token else None


def main():
    banner("PHASE 10 — Inner Source & Confidential Tests")

    api_project = f"{config.TOP_GROUP}/live-production/payments/api"
    secrets_project = f"{config.TOP_GROUP}/live-production/payments/restricted/payments-secrets"

    dan = client_for_env("POC_DAN_TOKEN")
    con = client_for_env("POC_CON_TOKEN")

    # T10.1 — Dan sees api (Internal)
    if dan:
        try:
            proj = dan.find_project(api_project)
            if proj:
                done("T10.1 PASS — Dan can see payments/api (Internal)")
            else:
                fail("T10.1 FAIL — Dan cannot see payments/api")
        except Exception as e:
            fail(f"T10.1 FAIL — {e}")
    else:
        warn("T10.1 SKIP — POC_DAN_TOKEN not set")

    # T10.2 — Dan cannot see payments-secrets (Private via restricted)
    if dan:
        proj = dan.find_project(secrets_project)
        if proj is None:
            done("T10.2 PASS — Dan correctly cannot see payments-secrets")
        else:
            fail("T10.2 FAIL — Dan unexpectedly saw payments-secrets")
    else:
        warn("T10.2 SKIP — POC_DAN_TOKEN not set")

    # T10.3 — Dan can fork payments/api
    if dan:
        try:
            proj = dan.find_project(api_project)
            if proj:
                fork_path = f"poc-dan/api"
                existing_fork = dan.find_project(fork_path)
                if existing_fork:
                    warn("T10.3 — fork already exists, cleaning up")
                    dan.delete(f"/projects/{existing_fork['id']}")
                encoded = quote(api_project, safe="")
                fork = dan.post(f"/projects/{encoded}/fork", json_body={})
                done(f"T10.3 PASS — Dan forked to {fork.get('path_with_namespace')}")
        except Exception as e:
            fail(f"T10.3 FAIL — fork failed: {e}")

    # T10.4 — Con can see payments-secrets
    if con:
        proj = con.find_project(secrets_project)
        if proj:
            done("T10.4 PASS — Con can see payments-secrets")
        else:
            fail("T10.4 FAIL — Con cannot see payments-secrets")
    else:
        warn("T10.4 SKIP — POC_CON_TOKEN not set")

    banner("PHASE 10 COMPLETE", char="-")
    done("Manual MR flow from Dan's fork still needs to be tested via browser.")
    done("Next: run phase_11_zone_policy.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
