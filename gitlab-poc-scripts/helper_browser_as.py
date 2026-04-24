#!/usr/bin/env python3
"""
helper_browser_as.py — Tools for a solo operator to browse GitLab as different users.

Options:
    # Print the admin impersonation URL for a user (opens as that user)
    python3 helper_browser_as.py --impersonate poc-alice

    # Print credentials table (username + password) for all test users
    python3 helper_browser_as.py --creds

    # Print all browser-profile URLs (handy for bookmarking)
    python3 helper_browser_as.py --all

Admin impersonation:
    GitLab admins can impersonate any user via:
        <GITLAB_URL>/admin/users/<username>/impersonate

    This creates a session as that user without knowing their password.
    A banner appears in the UI to make the impersonation visible.
    Click "Stop impersonating" at the top to return to admin.

    This is the FASTEST way for a single operator to simulate 8 users:
    just click Impersonate in a new browser tab for each.
"""
import argparse
import json
from pathlib import Path
import config
from gitlab_client import GitLabClient, banner, step, done, warn, require_admin_token


def print_creds_table():
    banner("Test User Credentials", char="-")
    print(f"    Password for all users: {config.TEST_USER_DEFAULT_PASSWORD}")
    print()
    print(f"    {'Username':<12}  {'Persona'}")
    print(f"    {'-'*12}  {'-'*40}")
    for u in config.TEST_USERS:
        print(f"    {u['username']:<12}  {u['name']}")
    print()


def print_impersonation_urls():
    banner("Admin Impersonation URLs", char="-")
    print("    Click any of these while logged in as admin to browse as that user.")
    print("    An orange banner will confirm impersonation. Click 'Stop impersonating' to exit.")
    print()
    for u in config.TEST_USERS:
        url = f"{config.GITLAB_URL}/admin/users/{u['username']}/impersonate"
        print(f"    {u['username']:<12}  {url}")
    print()


def impersonate_one(username):
    url = f"{config.GITLAB_URL}/admin/users/{username}/impersonate"
    print()
    print(f"Open this URL in your browser while logged in as admin:")
    print()
    print(f"    {url}")
    print()
    print(f"You will be redirected to the GitLab home page as {username}.")
    print(f"An orange banner will confirm impersonation. Click 'Stop impersonating'")
    print(f"at the top to return to your admin session.")
    print()


def print_tokens_file_hint():
    tokens_json = Path("tokens.json")
    if not tokens_json.exists():
        warn("tokens.json not found — run setup_test_users.py first to generate PATs.")
        return
    data = json.loads(tokens_json.read_text())
    banner("Token reference", char="-")
    print(f"    Base email:  {data.get('base_email')}")
    print(f"    Password:    {data.get('password')}")
    print()
    print(f"    PATs written to .env.tokens — source it to export as env vars:")
    print(f"        source .env.tokens")
    print()


def main():
    parser = argparse.ArgumentParser(description="Solo-operator browser helper")
    parser.add_argument("--impersonate", metavar="USERNAME",
                        help="Print impersonation URL for a specific user")
    parser.add_argument("--creds", action="store_true",
                        help="Print the username/password table for all test users")
    parser.add_argument("--all", action="store_true",
                        help="Print impersonation URLs for all test users")
    parser.add_argument("--tokens", action="store_true",
                        help="Show hint about .env.tokens file")
    args = parser.parse_args()

    if not any([args.impersonate, args.creds, args.all, args.tokens]):
        # Default: show everything
        args.creds = True
        args.all = True
        args.tokens = True

    if args.creds:
        print_creds_table()
    if args.all:
        print_impersonation_urls()
    if args.impersonate:
        impersonate_one(args.impersonate)
    if args.tokens:
        print_tokens_file_hint()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
