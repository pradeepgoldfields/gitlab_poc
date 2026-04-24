---
name: gitlab-pipeline
description: Inspect and act on GitLab CI pipelines — list recent, view status, tail job logs, retry, cancel, or hand off to the gitlab-pipeline-debugger agent for failure diagnosis.
---

# /gitlab-pipeline

Entry point for CI work. For a failed pipeline, delegate to `gitlab-pipeline-debugger` rather than guessing.

## Preconditions
- `.claude/gitlab.env` present; env vars exported.
- `set -a; source .claude/gitlab.env; set +a`

## Intents

### `list` — recent pipelines
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/pipelines?per_page=10" \
  | jq -r '.[] | "\(.id) \(.status) \(.ref) \(.web_url)"'
```

### `status <pipeline_id>` — one pipeline + its jobs
Fetch the pipeline, list jobs with stage + status, highlight failed jobs first.

### `log <job_id>` — print the trace
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/jobs/$JOB_ID/trace"
```
Print the tail (last ~200 lines) by default. Offer the full trace on request.

### `debug <pipeline_id>` — delegate to the agent
Spawn `gitlab-pipeline-debugger`. Pass the pipeline ID. Return its diagnosis verbatim.

### `retry <pipeline_id>` / `retry-job <job_id>`
Ask before retrying. If the failure is a clear code bug (per the debugger), recommend fixing first.

```bash
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/pipelines/$PIPELINE_ID/retry"
```

### `cancel <pipeline_id>`
```bash
curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/pipelines/$PIPELINE_ID/cancel"
```
Confirm first — cancels all in-flight jobs.

### `for-mr <iid>` — pipeline status for an MR
```bash
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT/merge_requests/$IID/pipelines"
```

## Safety
- `retry` and `cancel` affect runner minutes and blocking merges — always confirm.
- Never suggest disabling jobs in `.gitlab-ci.yml` as a fix without explicit user direction.
