# GitLab Agents & Skills

Project-scoped Claude Code bundle for working with GitLab via the REST API. No `glab` CLI required.

## Layout

```
.claude/
├── agents/
│   ├── gitlab-mr-reviewer/        # structured MR reviews
│   ├── gitlab-pipeline-debugger/  # diagnose CI failures
│   ├── gitlab-issue-triager/      # label/assignee/severity suggestions
│   └── gitlab-release-manager/    # draft release notes from merged MRs
└── skills/
    ├── gitlab-setup/     # /gitlab-setup — run once per repo
    ├── gitlab-mr/        # /gitlab-mr list|view|review|comment|approve|merge|create
    ├── gitlab-pipeline/  # /gitlab-pipeline list|status|log|debug|retry|cancel|for-mr
    ├── gitlab-issue/     # /gitlab-issue list|view|create|comment|label|assign|close|triage
    └── gitlab-release/   # /gitlab-release draft|publish|list|view
```

## One-time setup

1. Create a GitLab personal access token with `api` scope.
2. Export it in your shell (do not commit it):
   ```bash
   export GITLAB_URL="https://gitlab.com"       # or your self-hosted URL
   export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxx"
   ```
3. Run `/gitlab-setup` in this repo. It verifies the token, resolves the project, and writes `.claude/gitlab.env` (gitignored) with the project ID and default branch.

## Typical flows

- **Review an MR:** `/gitlab-mr review 42` → delegates to `gitlab-mr-reviewer`, returns a structured review. Post it with `/gitlab-mr comment 42 "..."` if you want.
- **Debug a failed pipeline:** `/gitlab-pipeline debug 12345` → `gitlab-pipeline-debugger` classifies the failure and proposes a fix.
- **Triage an issue:** `/gitlab-issue triage 88` → `gitlab-issue-triager` suggests labels, severity, assignee, and duplicates.
- **Cut a release:** `/gitlab-release draft v1.3.0 main v1.4.0` → draft notes. Then `/gitlab-release publish v1.4.0` after you've approved them.

## Safety posture

Agents and skills never post comments, approve, merge, retry, cancel, close, label, assign, tag, or publish without an in-turn user confirmation. Read operations run freely; write operations always ask first.

## Extending

- New skill: add a directory under `skills/<name>/` with a `SKILL.md` starting with a `---` frontmatter block (`name`, `description`).
- New agent: add a directory under `agents/<name>/` with an `AGENT.md` frontmatter block (`name`, `description`, `model`, `tools`).
