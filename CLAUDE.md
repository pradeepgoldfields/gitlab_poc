# GitLab PoC — Project Context

## What this project is

A Proof of Concept validating an enterprise GitLab access model for a migration from Bitbucket. The repo contains:

- the reference design (prose),
- HTML PoC reports + an HTML execution guide,
- a Python automation suite ([gitlab-poc-scripts/](gitlab-poc-scripts/)) that drives every PoC phase end-to-end against a live GitLab instance, captures every API call, runs Playwright UI evidence per phase, and emits a unified HTML report,
- `.claude/` agent definitions that interact with the GitLab REST API.

The repo is not a git repository at the top level. Work splits into two modes: editing prose/HTML, and running the Python suite under [gitlab-poc-scripts/](gitlab-poc-scripts/) against the live instance.

## Files

- [analysis](analysis) — Plain-text reference design. Defines the GitLab role mapping (Minimal Access → Owner), the ASIS/TOBE LDAP group naming (`<app>_w`, `P2P_GS_DevOps_<group>_<role>`), the two authorization approaches, grouping criteria, and core principles. **This is the source of truth — reports and the execution guide must stay consistent with it.**
- [enterprise-gitlab-poc-report.html](enterprise-gitlab-poc-report.html) — PoC report covering the enterprise access model: hybrid (Approach 1) vs domain-centric (Approach 2), custom roles (Promoter, Operator, Security Manager), migration path, deployment-zone policy inheritance.
- [enterprise-gitlab-poc-execution-guide.html](enterprise-gitlab-poc-execution-guide.html) — Step-by-step manual UI guide (14 phases) for one platform engineer to execute the PoC end-to-end.
- [gitlab-access-model-poc-report.html](gitlab-access-model-poc-report.html) — Generic GitLab access model PoC report (role hierarchy, branch/tag/environment protection, inner sourcing, CI/CD scenarios). Predates the enterprise-specific work. Each use case ends with a "Verify in UI" callout listing the GitLab URLs that prove the outcome.
- [gitlab-poc-scripts/](gitlab-poc-scripts/) — Python automation suite (entry point: [run_poc.py](gitlab-poc-scripts/run_poc.py)). Idempotent phase scripts, structured JSONL logging, Playwright-driven UI evidence per phase, single unified `poc-final-report.html` output. See [gitlab-poc-scripts/README.md](gitlab-poc-scripts/README.md) for the operator's manual.

All three HTML files share the same inline CSS (Atlassian-style: `#0052cc` headings, `.callout-info/warn/success/danger`, `.scenario`, `.outcome`, `.step`, `.expected`, `.checklist`, `.verify-ui`). Preserve this style when editing.

## Core design vocabulary

When editing, use these terms exactly — they map to the reference design:

- **Approach 1 (Hybrid Transition)** — reuses Bitbucket `_w`/`_r` LDAP groups at project level via SSCAM; minimal GitLab grouping. Temporary onboarding model.
- **Approach 2 (Domain / Product-Line Group-Centric)** — fully GitLab-native, SailPoint-only, access at group level (`gl-<domain>-{read,dev,maint,owner}`), inherited.
- **Custom roles** — Promoter, Operator, Security Manager (defined at instance level, applied at group scope).
- **`restricted/` subgroups** — how confidential projects are isolated from inner-source visibility inheritance.
- **Inner sourcing by default** — authenticated users can read non-confidential code.
- **Deployment-model grouping** — applications grouped by deployment zone (Live - Cloud Landing Zone, Live - Production, Non-live - Enterprise, etc.), not by org structure.

LDAP / SSCAM / SailPoint integration is **simulated** in the PoC via manually-managed GitLab groups under `<top-level>/iam-sim/{sscam,sailpoint,p2p}/`. Real LDAP binding is out of scope.

## Agents available

Defined in [.claude/agents/](.claude/agents/), all read-only by default — they only mutate when explicitly asked:

- `gitlab-mr-reviewer` — fetches MR diff/discussions/pipelines, returns a structured review.
- `gitlab-pipeline-debugger` — pulls pipeline + job traces, classifies the failure (build/test/flaky/config/auth/dependency), proposes a fix.
- `gitlab-issue-triager` — reads issue + notes, suggests labels/severity/assignee, searches for duplicates.

All three expect `GITLAB_URL` and `GITLAB_TOKEN` (PAT with `api` scope) in env, plus a URL-encoded project path and an IID. They use `curl` with `PRIVATE-TOKEN` headers and pipe JSON through `jq`.

The skill directories under [.claude/skills/](.claude/skills/) (`gitlab-issue`, `gitlab-mr`, `gitlab-pipeline`, `gitlab-release`, `gitlab-setup`) are currently empty placeholders.

## Working conventions

- **Don't invent GitLab features or API endpoints** — verify against `https://docs.gitlab.com/` or test via the live instance before documenting.
- **Keep the three HTML docs internally consistent** with [analysis](analysis). If a role name, group convention, or approach description changes there, propagate it.
- When editing HTML, match the existing class vocabulary (`callout-*`, `scenario`/`outcome`, `step`/`expected`, `checklist`) rather than inventing new styles.
- Never commit a token, MR/issue body, or pipeline trace excerpt that contains real project names or user IDs into the HTML files — the reports use generic placeholders (`payments-api`, Alice/Bob/Carol/Dan).
- Mutating GitLab API calls (post comment, approve MR, retry pipeline, change labels, close issue) require explicit user confirmation — agents are configured this way and direct curl calls should follow the same rule.
