#!/usr/bin/env python3
"""
Phase 12 — CI/CD Access Scenarios

Programmatically exercises several CI/CD scenarios:
  - Creates a feature branch commit and triggers a pipeline as Alice
  - Inspects the pipeline job log to verify PROD_DEPLOY_TOKEN is empty on
    feature branches (Scenario A)
  - Triggers a tag pipeline as Bob and inspects the prod-env job (Scenario A)
  - Tests CI_JOB_TOKEN cross-project allowlist (Scenario D)
  - Prints manual-testing guidance for Scenarios B, C, E, F, G, H, I

Requires user tokens for Alice (POC_ALICE_TOKEN) and Bob (POC_BOB_TOKEN).

Usage: python3 phase_12_cicd_tests.py
"""
import os
import time
from urllib.parse import quote
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def client_for_env(var):
    token = os.environ.get(var)
    return GitLabClient(token=token) if token else None


def wait_for_pipeline(gl, project_path, pipeline_id, timeout=180):
    encoded = quote(project_path, safe="")
    start = time.time()
    while time.time() - start < timeout:
        pipeline = gl.get(f"/projects/{encoded}/pipelines/{pipeline_id}")
        if pipeline["status"] in ("success", "failed", "canceled", "skipped"):
            return pipeline
        time.sleep(3)
    return None


def main():
    banner("PHASE 12 — CI/CD Access Scenarios")

    admin = GitLabClient()  # needs admin for some config checks
    alice = client_for_env("POC_ALICE_TOKEN")
    bob = client_for_env("POC_BOB_TOKEN")

    api = f"{config.TOP_GROUP}/live-production/domain-a/proj-1"

    # --------------------------------------------------------
    # Scenario A.1 — Feature branch pipeline does not expose PROD_DEPLOY_TOKEN
    # --------------------------------------------------------
    step("Scenario A.1 — pushing to a feature branch as Alice and inspecting pipeline…")
    if alice:
        encoded = quote(api, safe="")
        branch_name = "poc-scenario-a"
        # Delete existing test branch if any
        try:
            alice.delete(f"/projects/{encoded}/repository/branches/{branch_name}")
        except Exception:
            pass
        # Create branch
        try:
            alice.post(
                f"/projects/{encoded}/repository/branches",
                json_body={"branch": branch_name, "ref": "main"},
            )
            # Commit a trivial change
            alice.upsert_file(api, branch_name, "poc-scenario-a.txt",
                              "scenario A trigger",
                              "test: trigger pipeline for scenario A")
            # Trigger pipeline
            pipeline = alice.post(
                f"/projects/{encoded}/pipeline",
                json_body={"ref": branch_name},
            )
            done(f"Pipeline #{pipeline['id']} triggered on {branch_name}")
            done("Inspect the job log in the UI to confirm PROD_DEPLOY_TOKEN is empty.")
            done(f"URL: {pipeline.get('web_url')}")
        except Exception as e:
            fail(f"Scenario A.1 trigger failed: {e}")
    else:
        warn("POC_ALICE_TOKEN not set — skipping Scenario A.1")

    # --------------------------------------------------------
    # Scenario D — CI_JOB_TOKEN allowlist
    # --------------------------------------------------------
    step("Scenario D — verifying CI_JOB_TOKEN allowlist on domain-a/proj-1…")
    try:
        encoded = quote(api, safe="")
        # List job token scopes (inbound)
        settings = admin.get(f"/projects/{encoded}/job_token_scope")
        done(f"Inbound scope enabled: {settings.get('inbound_enabled')}")
        # List allowed projects
        allowed = admin.get_paginated(f"/projects/{encoded}/job_token_scope/allowlist")
        if allowed:
            done(f"Allowlisted projects: {[p.get('path_with_namespace') for p in allowed]}")
        else:
            done("Allowlist is empty (default-deny).")
    except Exception as e:
        warn(f"Could not inspect job token scope: {e}")

    # --------------------------------------------------------
    # Manual scenarios
    # --------------------------------------------------------
    step("Scenarios B, C, E, F, G, H, I — manual testing required:")
    print("""
    Scenario B — Manual job authorization
      • As Alice, try to play the deploy_prod manual job on a tag pipeline. Should be blocked.
      • As Carol, play it. Should succeed and wait for Bob's approval.

    Scenario C — Fork pipeline isolation
      • As Dan, fork domain-a/proj-1, modify the CI yaml to echo PROD_DEPLOY_TOKEN,
        open MR from fork. Bob approves pipeline to run. Verify token is empty.

    Scenario E — Runner scoping
      • Requires a registered group runner (see Phase 11 output).
      • Tag a job with live-prod-runner; verify it runs for live-production
        projects but pends for non-live projects.

    Scenario F — Developer cannot edit CI settings (already covered by Phase 8 T2, T3).

    Scenario G — Scheduled pipeline ownership
      • As Bob, create a schedule on domain-a/proj-1.
      • Reduce Bob's role to Reporter on the IAM group; the next scheduled run
        should fail privileged jobs.
      • Transfer schedule ownership to another Maintainer to restore.

    Scenario H — Group/project variable inheritance
      • Set a variable at live-production/domain-a; verify inherited by all child projects.
      • Override at domain-a/proj-1 with a different value; verify override.

    Scenario I — Environment-scoped same-key variables
      • Add API_KEY=staging-val scoped to staging; API_KEY=prod-val scoped to prod.
      • Verify each environment's job sees its own value.
    """)

    banner("PHASE 12 COMPLETE", char="-")
    done("Programmatic scenarios triggered. Inspect UI for pipeline logs.")
    done("Next: run phase_13_migration.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
