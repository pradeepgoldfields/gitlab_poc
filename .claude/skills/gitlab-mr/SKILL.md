---
name: gitlab-mr
description: Work with GitLab Merge Requests — list, view, review, comment, approve, or merge. Delegates review to the gitlab-mr-reviewer agent. Uses the REST API directly (no glab CLI needed).
---

# /gitlab-mr

Entry point for MR work. Parses the user's intent and either runs the action directly or delegates to the `gitlab-mr-reviewer` agent.

## Preconditions
- `.claude/gitlab.env` exists (run `/gitlab-setup` first).
- `GITLAB_URL` and `GITLAB_TOKEN` exported in the shell.
- Source the env: `set -a; source .claude/gitlab.env; set +a`

## Intents

### `list` — show open MRs
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/merge_requests?state=opened&per_page=20" \
  | jq -r '.[] | "!\(.iid) [\(.author.username)] \(.title)"'
```

### `view <iid>` — summarize one MR
Fetch the MR, its changes, and its pipeline. Print title, author, target branch, pipeline status, files changed, and the description.

### `review <iid>` — delegate to the agent
Spawn the `gitlab-mr-reviewer` agent. Pass the project, IID, and current working directory so it can cross-reference the diff with the checked-out code. Return its structured review verbatim.

### `comment <iid> "<text>"`
```bash
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data "$(jq -n --arg b "$TEXT" '{body:$b}')" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/merge_requests/$IID/notes"
```
Confirm before posting — comments are visible to the team.

### `approve <iid>` / `unapprove <iid>`
```bash
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/merge_requests/$IID/approve"
```
Always ask before approving.

### `merge <iid>`
```bash
curl -sS --request PUT --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --data "should_remove_source_branch=true&merge_when_pipeline_succeeds=true" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/merge_requests/$IID/merge"
```
High blast radius — require explicit user confirmation. Never merge into a protected branch without the user saying so in the current turn.

### `create` — open a new MR from the current branch
Collect source branch (current), target branch (default branch from env), title (first commit subject), description (commit body + template if present). Show the user the draft and confirm before POSTing.

## Safety rules
- Never `approve` or `merge` without explicit in-turn confirmation.
- Never post comments on someone else's behalf without showing the text first.
- If the MR has unresolved discussions, surface them before merging.
