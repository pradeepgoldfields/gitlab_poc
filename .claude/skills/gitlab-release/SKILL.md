---
name: gitlab-release
description: Draft and publish GitLab releases. Delegates changelog generation to the gitlab-release-manager agent, then creates the tag and release on confirmation.
---

# /gitlab-release

End-to-end release flow. Drafts notes via the `gitlab-release-manager` agent, then (only on confirmation) creates the tag and release.

## Preconditions
- `.claude/gitlab.env` present; env vars exported.
- `set -a; source .claude/gitlab.env; set +a`
- Clean working tree on the target branch.

## Intents

### `draft <from> <to> <tag>` — generate notes only
- `<from>` = previous tag (e.g. `v1.3.0`)
- `<to>` = ref to release from (usually the default branch or a new tag name)
- `<tag>` = the new tag to create (e.g. `v1.4.0`)

Delegate to `gitlab-release-manager`. Return the draft changelog. Do not tag or publish.

### `publish <tag>` — create tag + release from a previously approved draft
Expects a draft prepared in the current conversation (or a `--notes-file path`).

```bash
# Create the annotated tag
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --data-urlencode "tag_name=$TAG" \
  --data-urlencode "ref=$REF" \
  --data-urlencode "message=Release $TAG" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/repository/tags"

# Create the release
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data "$(jq -n --arg t "$TAG" --arg n "$TAG" --arg d "$NOTES" \
            '{name:$n, tag_name:$t, description:$d}')" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/releases"
```

### `list` — recent releases
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/releases?per_page=10" \
  | jq -r '.[] | "\(.tag_name)\t\(.released_at)\t\(.name)"'
```

### `view <tag>`
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/releases/$TAG"
```

## Safety
- `publish` is externally visible — require explicit user confirmation showing the exact tag, ref, and notes.
- If the tag already exists (409), stop. Never force-overwrite a tag.
- If the default branch is protected and the user lacks maintainer rights, the tag call will fail — report and stop rather than working around it.
- Do not run `publish` inside a merge-freeze window unless the user says the release is the reason for breaking it.
