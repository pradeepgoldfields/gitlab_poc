---
name: gitlab-issue
description: Work with GitLab issues — list, view, create, comment, label, assign, close, or triage. Delegates triage to the gitlab-issue-triager agent.
---

# /gitlab-issue

Entry point for issue work. Triage delegates to `gitlab-issue-triager`.

## Preconditions
- `.claude/gitlab.env` present; env vars exported.
- `set -a; source .claude/gitlab.env; set +a`

## Intents

### `list` — open issues
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/issues?state=opened&per_page=20" \
  | jq -r '.[] | "#\(.iid) [\(.labels|join(","))] \(.title)"'
```
Useful filters: `labels=bug`, `assignee_username=<user>`, `search=<term>`.

### `view <iid>` — issue detail + notes
Fetch the issue and its notes. Render title, state, labels, assignees, description, and the last few comments.

### `create`
Collect `title` (required) and `description`. Confirm before creating.
```bash
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data "$(jq -n --arg t "$TITLE" --arg d "$DESC" '{title:$t, description:$d}')" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/issues"
```

### `comment <iid> "<text>"`
Show the text before posting.
```bash
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data "$(jq -n --arg b "$TEXT" '{body:$b}')" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/issues/$IID/notes"
```

### `label <iid> +foo,+bar -baz` — add/remove labels
```bash
curl -sS --request PUT --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --data "add_labels=foo,bar&remove_labels=baz" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/issues/$IID"
```

### `assign <iid> <user>` — set assignee
Look up the user id first:
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/users?username=$USERNAME" | jq '.[0].id'
```
Then:
```bash
curl -sS --request PUT --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --data "assignee_ids=$UID" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/issues/$IID"
```

### `close <iid>` / `reopen <iid>`
```bash
curl -sS --request PUT --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --data "state_event=close" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/issues/$IID"
```

### `triage <iid>` — delegate
Spawn `gitlab-issue-triager`. Return its structured triage output. Apply suggested labels/assignee only on confirmation.

### `triage-inbox` — batch triage unlabeled issues
List open issues with no labels (or filter by `~needs-triage`), then hand each one to the agent. Summarize suggestions in a table and apply only after the user says yes.

## Safety
- Confirm before closing, applying labels, or assigning on behalf of the user.
- Never invent labels that don't exist in the project — fetch `/labels` first.
