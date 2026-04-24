# Enterprise GitLab Access Model PoC — Automation Scripts

Python scripts that drive every phase of the Enterprise GitLab Access Model
PoC end-to-end against any GitLab EE Ultimate instance (local Docker,
self-managed remote, or air-gapped). Every API call is logged. After each
phase the orchestrator drives a real Chromium browser through the matching
"Verify in UI" callouts and captures full-page screenshots. A single HTML
report at the end ties API calls and screenshots together per phase.

The PoC validates the design described in
`gitlab_poc/enterprise-gitlab-poc-execution-guide.html` (14 phases:
hierarchy, custom roles, hybrid + target authorization approaches,
branch/tag/env protection, inner sourcing, zone-level CI/CD inheritance,
migration, verification).

This README is meant as a self-contained operator's manual — you should be
able to follow it on a machine with no AI assistant in the loop.

---

## TL;DR

```bash
pip install -r requirements.txt
python -m playwright install chromium
# Open ui_tests/test_users.properties and replace PUT-ROOT-PASSWORD-HERE
python3 run_poc.py
# Open poc-final-report.html in a browser
```

> **Windows note.** Replace every `python3` in this README with `py -3`
> (the Python launcher). Out of the box, `python3` on Windows triggers
> the Microsoft Store stub and exits with the message *"Python was not
> found"*. The `py` launcher ships with the official Python.org
> installer and works in PowerShell, cmd, and Git Bash. Examples:
> ```powershell
> py -3 -m pip install -r requirements.txt
> py -3 -m playwright install chromium
> py -3 run_poc.py
> ```

Default flow runs against `http://localhost:8929` with all 13 phases plus
~20 UI evidence captures (~50 screenshots). Total runtime: 5–8 minutes.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | `python3 --version` to check. The scripts use `from __future__ import annotations` so 3.10 is the floor. |
| `pip` | Comes with Python; used for `requests` and `playwright`. |
| Chromium browser binary | Downloaded one-time via `python -m playwright install chromium` (~150 MB). Required only if you want UI evidence — the API run alone has no browser dependency. |
| Network access to the GitLab instance | Scripts make REST API calls and (for UI evidence) HTTP requests through Chromium. No SSH or git operations. |
| GitLab EE Ultimate, 15.6+ (18.x recommended) | Required for Custom Roles, group audit events, deploy approvals. Community Edition will not pass Phase 1. |
| **Admin** Personal Access Token, scope `api` | Custom Roles, user creation, hard-delete all need admin. Without admin you can still run a partial flow — see [Running on a non-admin token / GitLab.com](#running-on-a-non-admin-token--gitlabcom). |

### Don't have a GitLab instance yet?

The fastest local option is GitLab Docker EE Ultimate. From any host with
Docker:

```bash
docker run --detach --hostname gitlab \
  --publish 8929:8929 --publish 2289:22 \
  --name gitlab \
  --restart always \
  --env GITLAB_OMNIBUS_CONFIG="external_url 'http://localhost:8929'; gitlab_rails['gitlab_shell_ssh_port'] = 2289;" \
  --shm-size 256m \
  gitlab/gitlab-ee:latest
```

Wait ~5 min for the container to become healthy (`docker ps` shows
`(healthy)`). Get the auto-generated root password:

```bash
docker exec gitlab cat /etc/gitlab/initial_root_password
# Linux/macOS — Git Bash on Windows needs MSYS_NO_PATHCONV=1 prefix:
MSYS_NO_PATHCONV=1 docker exec gitlab cat /etc/gitlab/initial_root_password
```

Add a license: log in to `http://localhost:8929` as `root`, go to
**Admin → Subscription**, paste your trial / dev license. Custom Roles
(Phase 1) require Ultimate; without it Phase 1 will fail.

---

## Step 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs `requests` (HTTP client for the API run) and `playwright`
(browser automation for UI evidence). Then download the browser binary:

```bash
python -m playwright install chromium
```

Skip the Chromium install only if you plan to always run with
`--no-ui-evidence`.

---

## Step 2 — Mint a Personal Access Token

The PoC needs an admin PAT for phases 1 (custom roles) and 4 (user
creation). Hard-delete during cleanup also needs admin.

1. Log in to your GitLab as an admin user (e.g. `root` on a fresh
   install).
2. Go to **User Settings → Access Tokens** (or
   `https://<your-gitlab>/-/user_settings/personal_access_tokens`).
3. Create a token with:
   - **Scopes**: `api`
   - **Expiration**: a date far enough out to cover the run (~30 days is
     comfortable).
4. Copy the token immediately — GitLab only shows it once. It looks like
   `glpat-xxxxxxxxxxxxxxxxxxxx`.

---

## Step 3 — Prepare the UI-test credentials file

UI evidence logs in as the test personas (Alice, Bob, Dan, etc.) plus
`root`. Open `ui_tests/test_users.properties` in any text editor.

The file ships with sandbox defaults:

```properties
root=PUT-ROOT-PASSWORD-HERE
poc-alice=PocTestP@ssw0rd!2026
poc-bob=PocTestP@ssw0rd!2026
...
```

You **must** replace `PUT-ROOT-PASSWORD-HERE` with the actual root
password (see Step 0 above for the Docker case). The `poc-*` passwords
are fine to leave at the default — Phase 4 creates the users with this
password, and the runner handles GitLab's mandatory first-login password
reset transparently.

If you don't intend to run UI evidence (you want the API-only flow),
skip this step and add `--no-ui-evidence` to the run command in Step 4.

---

## Step 4 — Run the PoC

Default — interactive prompt for URL + PAT + optional prefix:

```bash
python3 run_poc.py
```

Or fully non-interactive:

```bash
python3 run_poc.py \
    --url http://localhost:8929 \
    --token glpat-xxxxxxxxxxxxxxxxxxxx \
    --yes
```

`--url` and `--token` are persisted to `.pocenv` (chmod 600 on POSIX,
gitignored) on first run, so subsequent invocations don't need them.

You should see a banner per phase, API calls streaming, and after each
phase a line like:

```
  → captured 3 UI evidence scenario(s) for phase 07
```

Total runtime is 5–8 minutes for the full flow (13 phases + ~20 UI
captures).

---

## Step 5 — Open the report

```
poc-final-report.html
```

Open it in any browser (the file is fully self-contained; no server
needed). It has four sections:

1. **Summary** — total API calls, error count, live verification
   pass/fail, UI evidence pass/fail, screenshot count.
2. **Live verification** — re-runs read-only assertions against the
   live instance to prove the report still matches reality.
3. **Per-phase timeline** — every API call grouped by phase with
   click-to-expand request/response bodies, **plus the UI evidence
   screenshots inline** for each phase. Click any screenshot to open
   it full-size in a new tab.
4. **About** — provenance / source-of-truth notes.

The accompanying files:

- `api-calls.jsonl` — one JSON record per API call (machine-readable).
- `ui_tests/screenshots/*.png` — the raw PNGs (the report references
  them by relative path — keep them next to the report).

---

## All `run_poc.py` flags

The minimal commands above cover most cases. Full reference for
scripted / CI use:

| Flag | Purpose |
|---|---|
| `--url URL` | GitLab base URL. |
| `--token TOKEN` | PAT (admin scope for phases 1 + 4). |
| `--prefix STR` | Suffix appended to TOP_GROUP / test usernames / custom-role names so the PoC can coexist with other runs on a shared instance. Empty = canonical names. Lowercased; non-alphanumeric chars become `-`. |
| `--no-verify-ssl` | Disable TLS certificate verification (only useful for self-signed hosts). |
| `--yes`, `-y` | Skip interactive prompts. |
| `--no-save` | Don't persist settings to `.pocenv`. |
| `--forget` | Delete `.pocenv` before prompting. |
| `--skip 13` | Skip a specific phase id. Repeat to skip many. |
| `--only 02 --only 03` | Run only the listed phases. Phase 14 (report) always runs. |
| `--keep-going` | Continue past phase failures. |
| `--log PATH` | JSONL log path (default `api-calls.jsonl`). |
| `--report PATH` | HTML report path (default `poc-final-report.html`). |

Environment variables: `GITLAB_URL`, `GITLAB_ADMIN_TOKEN`, `POC_PREFIX`,
`POC_TOP_GROUP` (default `acme-poc`), `POC_USER_EMAIL_DOMAIN`
(default `example.com`), `POC_TEST_USER_PASSWORD`,
`GITLAB_VERIFY_SSL` (`1` to force on, `0` to force off; defaults to ON for
https, OFF for http), `GITLAB_REQUEST_TIMEOUT` (seconds, default 30).

---

## Running on any GitLab instance

The scripts make REST API calls only — no Docker, SSH, or repository clones
in the orchestrator path. Anything reachable from your machine works:
local Docker, a self-managed remote, an air-gapped EE Ultimate cluster, or
GitLab.com SaaS.

### Running on a shared instance

Group paths, usernames, emails and instance-level custom-role names are all
**globally unique** on a GitLab instance. If two people run the PoC against
the same shared cluster without coordination they will collide on
`acme-poc`, `poc-alice`, `Promoter`, etc.

Use `--prefix` to namespace your run. Pass any short identifier (your
initials, ticket number, run timestamp). Names become:

| Default          | With `--prefix mr1` |
|------------------|---------------------|
| `acme-poc`       | `acme-poc-mr1`      |
| `poc-alice`      | `poc-alice-mr1`     |
| `poc-alice@example.com` | `poc-alice+mr1@example.com` |
| `Promoter`       | `Promoter-mr1`      |

```bash
python3 run_poc.py --url https://gitlab.example.com --prefix mr1
# … and later …
python3 cleanup.py --confirm    # reads .pocenv, only deletes mr1's stuff
```

`cleanup.py` reads the same `.pocenv` and only touches what your prefix
created. Two runs with different prefixes can coexist and be torn down
independently.

### Running on a non-admin token / GitLab.com

Some PoC steps require admin scope on a self-managed instance, or are simply
unavailable on GitLab.com SaaS. They are clearly isolated:

| Step                      | Needs admin? | Behaviour without it |
|---------------------------|--------------|----------------------|
| Phase 1 — custom roles    | Yes          | Phase fails. Either skip with `--skip 01` (downstream Phase 9 share will fail), or have an admin pre-create the three custom roles named under your prefix. |
| Phase 4 — user creation   | Yes          | Pre-provision the test users matching `config.TEST_USERS` (with the prefix you chose) and re-run. The script picks them up by username. |
| `setup_test_users.py` impersonation tokens | Yes | Mint PATs manually for each persona, paste them into `.env.tokens`. |
| `cleanup.py` hard-delete  | Yes          | Falls back to soft-delete (group is queued for permanent removal after the retention window — typically 7 days). |
| `phase_14_report.py` license check | Yes / EE | Marked **SKIP** in the report, doesn't fail. |
| Phases 2-3, 5-13          | No           | Run as the owner of `acme-poc-<prefix>`. |

For GitLab.com, set `--url https://gitlab.com` and create a personal-namespace
or group token with `api` scope. Pre-create the test users and the custom
roles, then run with `--skip 01 --skip 04`.

### TLS

`https://` URLs verify the server certificate by default. If your instance
uses a self-signed cert and you can't add the CA, pass `--no-verify-ssl` —
or set `GITLAB_VERIFY_SSL=0`.

---

## What the orchestrator runs

| Phase | Script | What it does | Idempotent on re-run? |
|---|---|---|:-:|
| 1 | `phase_01_custom_roles.py` | Creates Promoter, Operator, Security Manager custom roles (instance-level). Uses 18.x ability names. | yes |
| 2 | `phase_02_hierarchy.py` | Top-level `acme-poc` group, 5 zone subgroups, 4 domains, 2 `restricted/` subgroups, 8 projects. | yes |
| 3 | `phase_03_iam_groups.py` | 20 IAM-sim groups under `iam-sim/{sscam,sailpoint,devops-tooling}`. | yes |
| 4 | `phase_04_users.py` | 8 test users; assigns each to the right IAM-sim groups. Default password `PocTestP@ssw0rd!2026`. | yes |
| 5 | `phase_05_approach_1.py` | Hybrid sharing: project-level SSCAM + optional domain SailPoint. | yes |
| 6 | `phase_06_approach_2.py` | Target sharing: pure SailPoint group-level on `trade` domain. | yes |
| 7 | `phase_07_protection.py` | Protect `main` (Maintainer-merge, no push, code-owner approval), `v*` tags, `staging`/`prod` environments. Commits sample `.gitlab-ci.yml` + CODEOWNERS. | yes |
| 9 | `phase_09_custom_role_assignment.py` | Shares DevOps Tooling groups with `payments/api` carrying `member_role_id` for the custom roles. | yes |
| 10 | `phase_10_inner_source.py` | Verifies Internal visibility; Dan forks `payments/api`. | yes |
| 11 | `phase_11_zone_policy.py` | Zone-level `PROD_DEPLOY_TOKEN` (env-scoped to prod, protected, masked). | yes |
| 12 | `phase_12_cicd_tests.py` | Triggers test pipelines on feature branch & tags. | yes |
| 13 | `phase_13_migration.py` | Approach 1 → 2 migration on `payments/api` + break test (remove Alice from `gl-payments-dev`, verify access loss, restore). Set `RUN_BREAK_TEST=0` to skip the break test. | yes |
| 14 | `phase_14_report.py` | Live verification + HTML report from `api-calls.jsonl`. Always runs last. | yes |

Phase 8 (`phase_08_tests.py`) is **not** in the orchestrator pipeline because
it expects test users to have SSH keys to push code, which can't be
automated end-to-end here. Run it manually after setting up keys, or use
the manual flow below.

All phase scripts can also be run individually:

```bash
python3 phase_05_approach_1.py
```

They auto-load the URL + token from `.pocenv`.

---

## UI evidence capture (screenshots)

`run_poc.py` integrates UI screenshot capture directly into the PoC run.
After each phase finishes, a Playwright-driven Chromium navigates through
every "Verify in UI" callout that belongs to that phase, takes a full-page
screenshot, and the unified `poc-final-report.html` shows the screenshots
inline beside the API trace for that phase.

Evidence is captured **headless by default** (no visible browser, faster).
A separate standalone runner (`ui_tests/run_ui_tests.py`) still exists if
you want to re-capture evidence without re-running the API phases.

### One-time setup

```bash
pip install -r requirements.txt          # installs requests + playwright
python -m playwright install chromium    # downloads the browser binary (~150 MB)
```

Then edit `ui_tests/test_users.properties`:

- Replace `PUT-ROOT-PASSWORD-HERE` with your `root` password. For a fresh
  local Docker GitLab, get it with:

  ```bash
  MSYS_NO_PATHCONV=1 docker exec gitlab \
    cat /etc/gitlab/initial_root_password
  ```

  (Adjust `gitlab` to whatever your container is named — `docker ps` will
  show you.)

- The `poc-*` users default to `PocTestP@ssw0rd!2026` (the value of
  `config.TEST_USER_DEFAULT_PASSWORD`). If GitLab forces a password
  reset on first login (default for admin-created accounts), the runner
  handles it transparently. If you used `--prefix mr1` when running the
  PoC, append `-mr1` to each username, e.g.:

  ```properties
  poc-alice-mr1=PocTestP@ssw0rd!2026
  ```

### Running the integrated PoC + UI evidence

```bash
python3 run_poc.py
```

That's it. The orchestrator:

1. Runs each phase script (API calls).
2. After the phase finishes, opens a Chromium tab per persona and walks
   the URLs tagged for that phase, capturing one PNG per shot.
3. Continues to the next phase.
4. Phase 14 writes a single `poc-final-report.html` containing API calls
   **and** UI evidence interleaved per phase.

Screenshots land in `ui_tests/screenshots/`. The folder is **wiped at
the start of every run** so the report only ever shows fresh evidence.

### Flags relevant to UI evidence (on `run_poc.py`)

| Flag | Purpose |
|---|---|
| `--no-ui-evidence` | Skip UI capture entirely (API-only run). |
| `--headed` | Run with a visible browser window (slower, useful for debugging). |
| `--ui-creds PATH` | Override the credentials file (default: `ui_tests/test_users.properties`). |
| `--ui-timeout 30` | Per-page navigation timeout in seconds (default 30). |

### Standalone UI runner

If the PoC state is already in place and you only want to refresh the
screenshots (e.g. you noticed something in the UI mid-run), you can still
invoke the runner directly:

```bash
python3 ui_tests/run_ui_tests.py            # all 21 scenarios, headed
python3 ui_tests/run_ui_tests.py --headless # same, no window
python3 ui_tests/run_ui_tests.py --only 04-protected-branch --only 05-protected-env
```

It writes `ui_tests/ui-test-report.html` (separate from the unified
`poc-final-report.html`).

### Common gotchas

- **`UI evidence : DISABLED — Credentials file not found`** — the
  properties file is missing. Create it from the template under
  `ui_tests/test_users.properties` and replace `PUT-ROOT-PASSWORD-HERE`.
- **`UI: login failed for root`** — the placeholder password is still in
  the properties file. Drop in the real one.
- **`UI: login failed for poc-*`** — either Phase 4 didn't run (no test
  users on the instance), or the username in the properties file doesn't
  match `--prefix`. The runner saves a `_login_failed__<persona>.png` into
  the screenshot dir for triage.
- **Pages keep returning 404 in screenshots** — the API PoC didn't
  actually create the underlying groups/projects yet, or you're pointing
  at a different instance via `--url` than the PoC ran against.
- **Run takes longer than expected** — full integrated run with all 13
  phases + ~50 screenshots is ~5–7 min. Use `--no-ui-evidence` for the
  API-only flow if you need a quick sanity check.

---

## The HTML report

Sections:

1. **Summary** — total API calls, calls returning ≥ 400, calls by method,
   pass/fail of live verification, phase count.
2. **Live verification** — re-runs read-only assertions against the
   instance (license is Ultimate, hierarchy intact, branch protection
   correct, env protection correct, post-migration shares are gone, custom
   role groups are shared, audit events recorded). Each row links a check
   to its actual underlying state.
3. **Per-phase timeline** — every API call grouped by phase. Click any
   row to expand the request and response bodies. Tokens, passwords, and
   any `value` fields in JSON bodies are redacted before they hit disk.
4. **About** — provenance and source-of-truth notes.

The report is self-contained HTML with inline CSS — no external assets,
no network calls. Open in any browser.

---

## File map

```
.
├── run_poc.py                 ← single entry point — start here
├── config.py                  ← all hardcoded names, paths, role defs
├── session.py                 ← .pocenv persistence (URL + token)
├── api_call_log.py            ← structured per-call recorder
├── gitlab_client.py           ← thin requests wrapper, idempotent helpers
├── phase_01_custom_roles.py
├── phase_02_hierarchy.py
├── phase_03_iam_groups.py
├── phase_04_users.py
├── phase_05_approach_1.py
├── phase_06_approach_2.py
├── phase_07_protection.py
├── phase_08_tests.py          ← API role enforcement tests (manual run)
├── phase_09_custom_role_assignment.py
├── phase_10_inner_source.py
├── phase_11_zone_policy.py
├── phase_12_cicd_tests.py
├── phase_13_migration.py
├── phase_14_report.py         ← HTML report generator
├── run_setup_all.py           ← legacy: subprocess-runs phases 1-7,9,11
├── setup_test_users.py        ← one-off test user + PAT minting
├── helper_browser_as.py       ← prints impersonation URLs for browser use
├── ui_tests/
│   ├── evidence.py            ← reusable Playwright session API used by run_poc.py
│   ├── scenarios.py           ← list of 21 UI scenarios + their phase mapping
│   ├── run_ui_tests.py        ← standalone CLI for ad-hoc evidence runs
│   ├── test_users.properties  ← username=password for each persona
│   └── screenshots/           ← PNGs (regenerated every run; gitignored)
├── requirements.txt
├── .gitignore                 ← excludes secrets, logs, screenshots, reports
└── README.md                  ← this file
```

After a run you'll also have:

```
.pocenv                          ← saved URL + admin token (chmod 600, gitignored)
api-calls.jsonl                  ← every API call + UI evidence record (JSONL)
poc-final-report.html            ← unified HTML report
ui_tests/screenshots/*.png       ← raw PNGs referenced by the report
```

---

## Cleaning up

`cleanup.py` removes everything the PoC scripts created and nothing else.

```bash
python3 cleanup.py                 # dry-run — prints the plan, deletes nothing
python3 cleanup.py --confirm       # delete with defaults
```

What it removes (read from `config.py`, not the live state, so the scope is
predictable):

1. The 8 test users in `TEST_USERS`, hard-deleted (cascades any forks they
   own — e.g. Dan's `poc-dan/api` fork goes with him).
2. The top-level group `TOP_GROUP` (default `acme-poc`), permanently
   removed. The cascade takes every subgroup, project, branch/tag/env
   protection, CI variable, schedule, group runner, and group share
   underneath it.
3. The 3 instance-level custom roles named in `CUSTOM_ROLES` (Promoter,
   Operator, Security Manager).

What it does NOT touch:
- The `root` admin user, the GitLab Duo bot user, or any other user not in
  `TEST_USERS`.
- Any group, project, or role outside `TOP_GROUP` / `CUSTOM_ROLES`.
- The Docker container, gitlab-runner container, networks, or volumes.
- Local files (`.pocenv`, `api-calls.jsonl`, `poc-final-report.html`)
  unless `--remove-local-files` is passed.

| Flag | Purpose |
|---|---|
| `--confirm` | Required to actually delete. Default is dry-run. |
| `--keep-roles` | Preserve the custom roles (use this if other groups on the same instance share them). |
| `--keep-users` | Preserve the test users and their forks. |
| `--remove-local-files` | Also remove `.pocenv`, `api-calls.jsonl`, `poc-final-report.html`, `.env.tokens`, `tokens.json`. |
| `--log PATH` | Append cleanup API calls to this JSONL log (default `api-calls.jsonl`). The cleanup itself is auditable in the next HTML report. |
| `--url`, `--token` | Override saved values. |

If the permanent group delete fails (it requires Premium/Ultimate), the
script falls back to a soft delete and warns — the group is renamed
`<name>-deletion_scheduled-N` and removed permanently after GitLab's
retention window (typically 7 days).

## Customizing for a different environment

Open `config.py`. Everything that varies between deployments is there:

- `TOP_GROUP` (default `acme-poc`).
- `DEPLOYMENT_ZONES`, `DOMAINS`, `PROJECTS` — the hierarchy.
- `TEST_USERS`, `IAM_MEMBERSHIPS` — who exists and where they go.
- `CUSTOM_ROLES` — role names, base level, abilities. Note the comment
  block describing the 18.x ability substitutions vs. the original design
  (`admin_pipeline` → none, `admin_environment` → `admin_protected_environments`,
  `approve_merge_request` → `admin_merge_request`).
- `APPROACH_1_SHARES`, `APPROACH_2_SHARES` — sharing plans.
- `PROTECTION_PLAN` — protected branches/tags/environments.
- `SAMPLE_CI_YAML`, `SAMPLE_CODEOWNERS` — sample files committed to
  `payments/api` to enable CI tests.
- `ZONE_VARIABLES` — group-level CI/CD variables.

All values are read by phase scripts at runtime; you do not need to edit
phase scripts directly to change names.

---

## Troubleshooting

- **`No GitLab token set`** at startup: pass `--token`, set
  `GITLAB_ADMIN_TOKEN`, or run interactively.
- **`HTTP 401` on the first call**: PAT is invalid or expired. Mint a new
  one in **User Settings → Access Tokens** with scope `api`.
- **Custom role create returns `Read runners has to be enabled`**: the
  Operator role's `admin_runners` ability requires `read_runners` as a
  prerequisite. The shipped `config.py` already does this; if you edit
  abilities, keep this dependency.
- **`405 Method Not Allowed` on MR merge**: the project's approval rule
  blocks self-author approval. The orchestrator handles this by minting an
  impersonation token for the test Maintainer (Bob); for ad-hoc runs, you
  may need a separate maintainer account.
- **Git Bash on Windows mangles container paths**: this only affects the
  separate Docker / `gitlab-runner` setup; not the Python scripts.
- **Live verification skips `Approach 1 SSCAM project shares removed`**:
  this check requires phase 13 (the Approach 1 → 2 migration) to have run.
  When you skip phase 13 the report marks the check **SKIP** instead of
  FAIL, since the SSCAM shares are still present by design. Re-run with
  phase 13 included to flip this to PASS.
- **`UI evidence : DISABLED — Credentials file not found`** at startup:
  `ui_tests/test_users.properties` is missing or moved. Either restore it
  (use the version checked in to the repo as a template) or pass
  `--no-ui-evidence` if you don't need screenshots.
- **`UI evidence : DISABLED — playwright is not installed`**: run
  `pip install -r requirements.txt && python -m playwright install chromium`,
  or pass `--no-ui-evidence`.
- **`UI: login failed for root`**: the placeholder
  `PUT-ROOT-PASSWORD-HERE` in `test_users.properties` was never replaced.
- **`UI: login failed for poc-*`**: Phase 4 didn't run (test users don't
  exist on the instance), or you used `--prefix mr1` and the usernames in
  `test_users.properties` are still the un-prefixed ones. The runner saves
  a `_login_failed__<persona>.png` into the screenshot dir for triage.
- **Screenshots show "404: Page not found"**: the persona genuinely can't
  reach that URL. For some scenarios (Alice viewing CI/CD settings, Dan
  viewing protected restricted content) this is the **expected** evidence
  and the scenario is marked `expected_status: 404` in `ui_tests/scenarios.py`
  — it shows up as a green PASS in the report. For other scenarios it
  means the API PoC didn't actually create the underlying object yet.
- **Run takes much longer than expected**: full integrated run takes
  ~5–8 min. Use `--no-ui-evidence` for an API-only sanity check (~3 min).

---

## Manual flow (legacy)

The original per-phase flow still works for users who want to pause and
inspect between steps:

```bash
pip install -r requirements.txt
export GITLAB_URL=http://localhost:8929
export GITLAB_ADMIN_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx

python3 setup_test_users.py             # creates test users + their PATs
source .env.tokens
python3 run_setup_all.py                # phases 1-7, 9, 11 via subprocess
python3 phase_08_tests.py
python3 phase_10_inner_source.py
python3 phase_12_cicd_tests.py
python3 phase_13_migration.py
python3 phase_14_report.py              # HTML report
```

`run_setup_all.py` uses subprocesses, so each phase has its own Python
process; the call log is still appended (each process appends to the same
JSONL), but the in-memory phase grouping is less precise. Prefer
`run_poc.py` unless you specifically need the manual checkpoints.

---

## Security notes

- The `.pocenv` file holds a long-lived admin PAT. It's chmod 600 on POSIX.
  On Windows, NTFS ACLs aren't touched — rely on your profile's default
  ACL, or store the PAT in a secrets manager and pass via `--token`.
- The call log redacts `token`, `password`, `private_token`, `access_token`,
  and `value` fields in JSON bodies, plus literal `glpat-`, `glrt-`,
  `gloas-`, `glsoat-` tokens anywhere in URLs or bodies. The redaction is
  pattern-based; review the log if you commit it anywhere.
- `setup_test_users.py` writes a `.env.tokens` and `tokens.json` containing
  per-user PATs. Both are gitignored. Rotate when no longer needed.
