---
name: gitlab-setup
description: Verifies GitLab REST API credentials, detects the project, and records defaults in .claude/gitlab.env. Run once per repo before using the other gitlab-* skills.
---

# /gitlab-setup

Run this first. It checks that `GITLAB_URL` and `GITLAB_TOKEN` are present, confirms the token works, resolves the project ID for the current repo, and writes defaults the other skills will read.

## Steps

1. **Check env vars.**
   - Require `GITLAB_URL` (e.g. `https://gitlab.com`) and `GITLAB_TOKEN` (PAT with `api` scope).
   - If missing, tell the user exactly which one and how to set it. Do not prompt for the token inline — instruct them to export it in their shell.

2. **Verify the token.**
   ```bash
   curl -sS -o /dev/null -w "%{http_code}" \
     --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "$GITLAB_URL/api/v4/user"
   ```
   Expect `200`. If `401`, the token is bad — stop. If `200`, fetch the user to confirm identity and report `username`.

3. **Resolve the project.**
   - If the repo has a `origin` remote pointing at GitLab, parse the path from it (`git config --get remote.origin.url`).
   - Otherwise, ask the user for the project path (e.g. `mygroup/myrepo`).
   - URL-encode the path and confirm it resolves:
     ```bash
     curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
       "$GITLAB_URL/api/v4/projects/$ENCODED_PATH" | jq '{id, path_with_namespace, default_branch}'
     ```

4. **Write `.claude/gitlab.env`** (gitignored) with the resolved defaults:
   ```
   GITLAB_PROJECT=<url-encoded path>
   GITLAB_PROJECT_ID=<numeric id>
   GITLAB_DEFAULT_BRANCH=<main or master>
   ```
   If `.claude/gitlab.env` already exists, diff the new values against it and only rewrite on confirmation.

5. **Append `gitlab.env` to `.gitignore`** if not already present. Never commit tokens — this file holds IDs only, but keep it local as a convention.

6. **Summarize**: report the authenticated user, project path, project ID, and default branch in 4 lines.

## What this skill does NOT do
- It does not store the token anywhere. The token stays in the user's shell env.
- It does not modify the GitLab project.
