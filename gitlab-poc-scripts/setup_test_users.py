#!/usr/bin/env python3
"""
setup_test_users.py — Bootstrap 8 test users for the solo operator

This script solves the "I am one person, I need 8 identities" problem.

What it does:
  1. Takes your real email as input (e.g., you@example.com).
  2. Creates 8 GitLab users using plus-addressed emails
     (you+poc-alice@example.com, etc.) — all mail lands in your inbox.
  3. Sets a known password on each (from config.TEST_USER_DEFAULT_PASSWORD).
  4. Creates a Personal Access Token (PAT) for each user with `api` scope.
  5. Writes all 8 PATs to `.env.tokens` which you can `source` to make them
     available to phase_08 / phase_10 / phase_12 scripts.
  6. Creates impersonation tokens you can use to browse GitLab as each user
     via URL (see helper_login_urls.py).

Requires admin token (GITLAB_ADMIN_TOKEN).

Usage:
    export GITLAB_ADMIN_TOKEN=glpat-xxxx
    python3 setup_test_users.py

You will be prompted for your real email. Plus-addressing must be supported
by your mail system (Gmail, Outlook, most enterprise Exchange all support it).

After running:
    source .env.tokens
    python3 phase_04_users.py       # adds them to IAM groups
    python3 phase_08_tests.py       # run tests as each user

Alternative — if plus-addressing is blocked by your mail system:
  Use distinct real mailboxes (e.g., personal Gmail + work) or ask your
  admin to pre-create accounts and edit config.TEST_USERS to match.
"""
import os
import sys
import json
from pathlib import Path
import config
from gitlab_client import GitLabClient, banner, step, done, warn, fail, require_admin_token


def build_email(base_email, suffix):
    """Convert you@example.com + 'poc-alice' into you+poc-alice@example.com."""
    if "@" not in base_email:
        raise ValueError(f"Invalid email: {base_email}")
    local, domain = base_email.split("@", 1)
    return f"{local}+{suffix}@{domain}"


def main():
    require_admin_token()
    banner("SETUP — Test Users for Solo Operator")

    # Get user's real email
    base_email = os.environ.get("POC_BASE_EMAIL")
    if not base_email:
        base_email = input("Enter your real email address (plus-addressing will be applied): ").strip()
    if not base_email or "@" not in base_email:
        fail("Invalid email.")
        return 1

    step(f"Using base email: {base_email}")
    step(f"Users will be created as: {build_email(base_email, 'poc-alice')}, etc.")

    gl = GitLabClient()

    tokens = {}
    impersonation = {}

    # Create each user
    for u in config.TEST_USERS:
        username = u["username"]
        suffix = username  # e.g. 'poc-alice'
        email = build_email(base_email, suffix)

        existing = gl.find_user_by_username(username)
        if existing:
            done(f"User {username} already exists (id={existing['id']}) — skipping creation")
            user = existing
        else:
            step(f"Creating user {username} with email {email}")
            try:
                user = gl.post(
                    "/users",
                    json_body={
                        "username": username,
                        "email": email,
                        "name": u["name"],
                        "password": config.TEST_USER_DEFAULT_PASSWORD,
                        "skip_confirmation": True,
                        "force_random_password": False,
                    },
                )
                done(f"Created {username} (id={user['id']})")
            except Exception as e:
                fail(f"Failed to create {username}: {e}")
                fail("If the error mentions 'email' restrictions, your instance may block")
                fail("plus-addressing or require an allow-listed domain. Ask your admin to")
                fail("pre-create these users and re-run.")
                continue

        # Create PAT for the user (admin-impersonated)
        step(f"Creating Personal Access Token for {username}")
        try:
            pat = gl.post(
                f"/users/{user['id']}/personal_access_tokens",
                json_body={
                    "name": "poc-automation",
                    "scopes": ["api", "read_repository", "write_repository"],
                    # No expires_at = default max (30 days on many instances)
                },
            )
            tokens[username] = pat.get("token")
            done(f"PAT created for {username}")
        except Exception as e:
            warn(f"Could not create PAT for {username}: {e}")
            warn("You can create one manually by logging in as the user.")

        # Create an impersonation token (admin-only, used for browser SSO-less access)
        step(f"Creating impersonation token for {username}")
        try:
            imp = gl.post(
                f"/users/{user['id']}/impersonation_tokens",
                json_body={
                    "name": "poc-browser-impersonation",
                    "scopes": ["api", "read_user"],
                },
            )
            impersonation[username] = imp.get("token")
            done(f"Impersonation token created")
        except Exception as e:
            warn(f"Could not create impersonation token: {e}")

    # Write .env.tokens
    env_file = Path(".env.tokens")
    lines = ["# Generated by setup_test_users.py — source this file:",
             "#     source .env.tokens",
             ""]
    for username, token in tokens.items():
        var = f"POC_{username.upper().replace('-', '_').replace('POC_', '')}_TOKEN"
        # username like 'poc-alice' → 'POC_ALICE_TOKEN'
        var = username.upper().replace("-", "_") + "_TOKEN"
        lines.append(f"export {var}={token}")
    env_file.write_text("\n".join(lines) + "\n")
    env_file.chmod(0o600)

    # Write tokens.json (for programmatic reference)
    tokens_json = Path("tokens.json")
    tokens_json.write_text(json.dumps({
        "base_email": base_email,
        "password": config.TEST_USER_DEFAULT_PASSWORD,
        "pats": tokens,
        "impersonation_tokens": impersonation,
    }, indent=2))
    tokens_json.chmod(0o600)

    banner("SETUP COMPLETE", char="-")
    done(f"Wrote {env_file} — source this to export test user tokens:")
    print()
    print(f"    source {env_file}")
    print()
    done(f"Wrote {tokens_json} — full reference (includes impersonation tokens)")
    print()
    done("Users created. You can now run:")
    print("    python3 phase_04_users.py    # add users to IAM groups")
    print("    python3 phase_08_tests.py    # run role enforcement tests")
    print()
    done("To log into GitLab as each user in your browser:")
    print(f"    Username: poc-alice (or poc-bob, etc.)")
    print(f"    Password: {config.TEST_USER_DEFAULT_PASSWORD}")
    print()
    done("Or use helper_browser_as.py to generate one-shot browser URLs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
