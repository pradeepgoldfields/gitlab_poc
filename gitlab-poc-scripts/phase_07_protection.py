#!/usr/bin/env python3
"""
Phase 7 — Branch / Tag / Environment Protection + CI bootstrap

- Protects main on domain-a/proj-1 and domain-b/proj-1
- Protects v* tags
- Creates and protects staging and prod environments
- Adds a baseline .gitlab-ci.yml
- Adds a CODEOWNERS file

Usage: python3 phase_07_protection.py
"""
import base64
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def main():
    require_admin_token()
    banner("PHASE 7 — Protection Rules and CI Bootstrap")

    gl = GitLabClient()

    # Commit baseline .gitlab-ci.yml to domain-a/proj-1 and CODEOWNERS
    api_path = f"{config.TOP_GROUP}/live-production/domain-a/proj-1"
    step(f"Committing baseline .gitlab-ci.yml and CODEOWNERS to {api_path}")
    try:
        gl.upsert_file(api_path, "main", ".gitlab-ci.yml", config.SAMPLE_CI_YAML,
                       "chore: add baseline CI pipeline")
        done("Upserted .gitlab-ci.yml")
    except Exception as e:
        warn(f"CI yaml commit failed: {e}")
    try:
        gl.upsert_file(api_path, "main", "CODEOWNERS", config.SAMPLE_CODEOWNERS,
                       "chore: add CODEOWNERS")
        done("Upserted CODEOWNERS")
    except Exception as e:
        warn(f"CODEOWNERS commit failed: {e}")

    # Protected branches
    for rule in config.PROTECTION_PLAN["protected_branches"]:
        proj = f"{config.TOP_GROUP}/{rule['project']}"
        step(f"Protecting branch {rule['name']} on {proj}")
        try:
            gl.protect_branch(
                proj,
                name=rule["name"],
                push_access_level=rule["push_access_level"],
                merge_access_level=rule["merge_access_level"],
                code_owner_approval_required=rule["code_owner_approval_required"],
            )
            done("Protected")
        except Exception as e:
            fail(f"Failed to protect branch: {e}")

    # Protected tags
    for rule in config.PROTECTION_PLAN["protected_tags"]:
        proj = f"{config.TOP_GROUP}/{rule['project']}"
        step(f"Protecting tag pattern {rule['name']} on {proj}")
        try:
            gl.protect_tag(proj, name=rule["name"], create_access_level=rule["create_access_level"])
            done("Protected")
        except Exception as e:
            fail(f"Failed to protect tag: {e}")

    # Protected environments
    for rule in config.PROTECTION_PLAN["protected_environments"]:
        proj = f"{config.TOP_GROUP}/{rule['project']}"
        step(f"Protecting environment {rule['name']} on {proj}")
        try:
            gl.protect_environment(
                proj,
                env_name=rule["name"],
                deploy_access_levels=rule.get("deploy_access_levels"),
                deploy_access_users=rule.get("deploy_access_users"),
                approval_rules=rule.get("approval_rules"),
            )
            done("Protected")
        except Exception as e:
            fail(f"Failed to protect environment {rule['name']}: {e}")

    banner("PHASE 7 COMPLETE", char="-")
    done("Protection rules and CI baseline applied.")
    done("Next: run phase_08_tests.py for automated verification of role enforcement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
