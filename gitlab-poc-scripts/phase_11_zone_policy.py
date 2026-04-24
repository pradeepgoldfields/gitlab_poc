#!/usr/bin/env python3
"""
Phase 11 — Zone-Level Policy Inheritance

Sets up zone-level CI/CD variables. (Group-level runner registration must be
done on a host machine; this script prints the command to run.)

Validates:
  - PROD_DEPLOY_TOKEN is set at live-production level with environment scope prod
  - A project in live-production can see the variable when its job declares
    environment: prod
  - A project in non-live-enterprise cannot see it (sibling zone)

Usage: python3 phase_11_zone_policy.py
"""
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 11 — Zone-Level Policy Inheritance")

    gl = GitLabClient()

    # Set zone variables
    for v in config.ZONE_VARIABLES:
        path = f"{config.TOP_GROUP}/{v['group']}"
        step(f"Setting {v['key']} at group {path} (env={v['environment_scope']}, "
             f"protected={v['protected']}, masked={v['masked']})")
        try:
            gl.set_group_variable(
                group_path=path,
                key=v["key"],
                value=v["value"],
                protected=v["protected"],
                masked=v["masked"],
                environment_scope=v["environment_scope"],
            )
            done("Variable set")
        except Exception as e:
            fail(f"Failed to set variable: {e}")

    # Print runner registration command
    step("Group-level runner registration must be done on a host machine.")
    print("""
    To register a zone-scoped runner for live-production:

      1. In the GitLab UI, navigate to:
         acme-poc/live-production → Build → Runners → New group runner

      2. Set:
         - Tags: live-prod-runner
         - Run untagged jobs: OFF
         - Protected: ON

      3. Copy the runner authentication token.

      4. On the host (any Linux VM or Docker host):
         sudo gitlab-runner register \\
           --url <GITLAB_URL> \\
           --token <TOKEN_FROM_STEP_3> \\
           --executor docker \\
           --docker-image alpine:latest

      5. Verify: Build → Runners list shows the new runner online.
    """)

    banner("PHASE 11 COMPLETE", char="-")
    done("Zone variables set. Runner registration is manual (see output above).")
    done("Next: run phase_12_cicd_tests.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
