"""
UI-test scenarios — one entry per use case in
gitlab-access-model-poc-report.html.

Each scenario captures one or more screenshots from the live GitLab UI.
This is **evidence-only** — there are no assertions. A scenario "passes" if
every URL loaded without an HTTP 4xx/5xx; otherwise the failed shot is
flagged red in the report (still captured as evidence).

URL paths are templates. {top} expands to config.TOP_GROUP at run time
(picks up POC_PREFIX automatically).

PATH MAPPING — design report ↔ actual API-PoC layout
====================================================
The reference report uses narrative names (`acme/verticals/payments/service-a`).
The API PoC creates groups by deployment-zone and domain instead. The
mapping below makes the two consistent so the screenshots line up with the
verify-ui callouts in the report:

  Design narrative                   →  Actual PoC path
  ─────────────────────────────────────────────────────────
  acme                               →  acme-poc                       (top)
  acme/verticals/payments            →  acme-poc/live-production/payments
  acme/verticals/payments/service-a  →  acme-poc/live-production/payments/api
  acme/verticals/payments/service-b  →  acme-poc/live-production/payments/ui
  acme/verticals/identity            →  acme-poc/live-production/trade
  acme/verticals/identity/service-x  →  acme-poc/live-production/trade/orders
  acme/platform/ci-templates         →  acme-poc/platform/ci-templates
  dan/service-a                      →  poc-dan/api                    (fork)
"""
from __future__ import annotations

# Convenience templates — define once, reuse across scenarios.
PAYMENTS = "{top}/live-production/payments"
PAY_API = f"{PAYMENTS}/api"            # was: service-a
PAY_UI = f"{PAYMENTS}/ui"              # was: service-b
PAY_RESTRICTED = f"{PAYMENTS}/restricted/payments-secrets"
SIBLING = "{top}/live-production/trade"      # sibling vertical = trade
SIBLING_PROJ = f"{SIBLING}/orders"           # was: identity/service-x
CI_TEMPLATES = "{top}/platform/ci-templates"
DAN_FORK = "poc-dan/api"                     # fork lands in personal namespace

# Phase mapping — which scenarios produce evidence for which API-PoC phase.
# `phase` matches the phase ids used in run_poc.py (`02`, `04`, `07`, …).
# The orchestrator calls evidence.run_for_phase(phase_id) right after that
# phase finishes, so the screenshots reflect what the phase just built.
SCENARIOS: list[dict] = [
    # --- Part 1 — Hierarchy ------------------------------------------------
    {
        "id": "01-hierarchy-top",
        "phase": "02",  # Phase 2 builds the hierarchy
        "section": "Part 1 — Hierarchy",
        "title": "Top-level group tree",
        "persona": "root",
        "shots": [
            {"label": "Top group members + overview",
             "path": "/groups/{top}/-/group_members"},
            {"label": "Live-production zone tree",
             "path": "/groups/{top}/live-production"},
            {"label": "Pilot project (payments/api)",
             "path": f"/{PAY_API}"},
            {"label": "Shared CI templates project",
             "path": f"/{CI_TEMPLATES}"},
        ],
    },

    # --- Part 2 — User invitation -----------------------------------------
    {
        "id": "02-user-membership",
        "phase": "04",  # Phase 4 creates users + assigns memberships
        "section": "Part 2 — User Invitation and Access Assignment",
        "title": "Members across the tree (Dan top-level Guest, Carol elevated)",
        "persona": "root",
        "shots": [
            {"label": "Top-level acme members (Dan as Guest)",
             "path": "/groups/{top}/-/group_members"},
            {"label": "Payments subgroup members",
             "path": f"/groups/{PAYMENTS}/-/group_members"},
            {"label": "payments/api members (direct + inherited)",
             "path": f"/{PAY_API}/-/project_members"},
            {"label": "Admin → Users (impersonate from here)",
             "path": "/admin/users"},
        ],
    },

    # --- Part 3 — Baseline access ------------------------------------------
    {
        "id": "03-baseline-access",
        "phase": "06",  # baseline becomes meaningful once Approach 2 shares are in
        "section": "Part 3 — Baseline Access Enforcement",
        "title": "Alice's view of payments/api (no Settings, no Delete)",
        "persona": "poc-alice",
        "shots": [
            {"label": "payments/api project as Alice (Developer)",
             "path": f"/{PAY_API}"},
            {"label": "ci-templates as Alice (Internal — visible, not writable)",
             "path": f"/{CI_TEMPLATES}"},
        ],
    },

    # --- Part 4 — Protected branch + MR flow -------------------------------
    {
        "id": "04-protected-branch",
        "phase": "07",  # Phase 7 sets up branch protection + CODEOWNERS
        "section": "Part 4 — Protected Branch and Merge Flow",
        "title": "Branch protection, approval rules, MR list",
        "persona": "root",
        "shots": [
            {"label": "Protected branches config (main → Maintainer-merge, no push)",
             "path": f"/{PAY_API}/-/settings/repository"},
            {"label": "MR settings (approval rules)",
             "path": f"/{PAY_API}/-/settings/merge_requests"},
            {"label": "Merge requests list",
             "path": f"/{PAY_API}/-/merge_requests?scope=all&state=all"},
            {"label": "CODEOWNERS file in repo root",
             "path": f"/{PAY_API}/-/blob/main/CODEOWNERS"},
        ],
    },

    # --- Part 5 — Protected env + deployment -------------------------------
    {
        "id": "05-protected-env",
        "phase": "07",  # Phase 7 also creates protected environments
        "section": "Part 5 — Protected Environment and Deployment",
        "title": "Environments, deployment approvals, manual gating",
        "persona": "root",
        "shots": [
            {"label": "Environments list",
             "path": f"/{PAY_API}/-/environments"},
            {"label": "Protected environments config",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "Pipeline list (deploy_prod manual + gated)",
             "path": f"/{PAY_API}/-/pipelines"},
        ],
    },

    # --- Part 6 — Protected tags -------------------------------------------
    {
        "id": "06-protected-tags",
        "phase": "07",  # Phase 7 also protects v* tags
        "section": "Part 6 — Protected Tags",
        "title": "v* tag pattern restricted to Maintainers",
        "persona": "root",
        "shots": [
            {"label": "Protected tags config",
             "path": f"/{PAY_API}/-/settings/repository"},
            {"label": "Tag list",
             "path": f"/{PAY_API}/-/tags"},
        ],
    },

    # --- Part 7 — Inner source --------------------------------------------
    {
        "id": "07-inner-source",
        "phase": "10",  # Phase 10 sets visibility + Dan's fork
        "section": "Part 7 — Inner Source Contribution",
        "title": "Dan discovers + forks + opens MR with no upstream role",
        "persona": "poc-dan",
        "shots": [
            {"label": "Explore projects as Dan (Internal projects visible)",
             "path": "/explore/projects"},
            {"label": "payments/api as Dan (Internal — readable, not writable)",
             "path": f"/{PAY_API}"},
            {"label": "Dan's fork in his personal namespace",
             "path": f"/{DAN_FORK}"},
            {"label": "MR list (Dan's contribution from fork)",
             "path": f"/{PAY_API}/-/merge_requests?scope=all&state=all"},
        ],
    },

    # --- Part 8 — Inheritance ----------------------------------------------
    {
        "id": "08-inheritance",
        "phase": "06",  # inheritance proves itself once Approach 2 shares exist
        "section": "Part 8 — Inheritance and Sovereignty",
        "title": "Inherited access on sibling project, raised access elsewhere",
        "persona": "root",
        "shots": [
            {"label": "payments/ui members (inherited from payments)",
             "path": f"/{PAY_UI}/-/project_members"},
            {"label": "payments/api members (raised access)",
             "path": f"/{PAY_API}/-/project_members"},
            {"label": "live-production tree at a glance",
             "path": "/groups/{top}/live-production"},
        ],
    },
    {
        "id": "08b-sibling-isolation",
        "phase": "06",
        "section": "Part 8 — Inheritance and Sovereignty",
        "title": "Alice has no access to a Private restricted project",
        "persona": "poc-alice",
        # NOTE: trade/orders is Internal — Alice can read it via inner-source
        # visibility, so we can't use it for an isolation test. The
        # payments/restricted/payments-secrets project is Private and Alice
        # is NOT a member of payments/restricted, so this is a true 404.
        "shots": [
            {"label": "payments-secrets (Private) as Alice — should 404",
             "path": f"/{PAY_RESTRICTED}",
             "expected_status": 404},
        ],
    },

    # --- Part 9 — Audit ----------------------------------------------------
    {
        "id": "09-audit",
        "phase": "13",  # audit picks up everything; capture after migration phase
        "section": "Part 9 — Audit and Review",
        "title": "Top-level + project-level audit events",
        "persona": "root",
        "shots": [
            {"label": "Top-level group audit events",
             "path": "/groups/{top}/-/audit_events"},
            {"label": "Project-level audit events for payments/api",
             "path": f"/{PAY_API}/-/audit_events"},
            {"label": "Instance-wide audit events (admin)",
             "path": "/admin/audit_logs"},
            {"label": "Members CSV export source — payments subgroup",
             "path": f"/groups/{PAYMENTS}/-/group_members"},
        ],
    },

    # --- Part 10 — CI/CD scenarios -----------------------------------------
    # 13.1 Scenario A — Protected variables on feature vs protected branches
    {
        "id": "10a-protected-vars",
        "phase": "12",  # Phase 12 sets up the CI variable scenarios
        "section": "Scenario A — Protected variables",
        "title": "Protected/masked secret with environment scope",
        "persona": "root",
        "shots": [
            {"label": "CI/CD variables list (protected + env-scoped to prod)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "Pipelines (compare logs across feature vs main)",
             "path": f"/{PAY_API}/-/pipelines"},
        ],
    },

    # 13.2 Scenario B — Manual job authorization
    {
        "id": "10b-manual-jobs",
        "phase": "12",
        "section": "Scenario B — Manual Job Authorization",
        "title": "deploy_prod gated to Carol, run_adhoc open to any Developer",
        "persona": "root",
        "shots": [
            {"label": "Latest pipeline showing manual jobs",
             "path": f"/{PAY_API}/-/pipelines"},
            {"label": "Protected environments (prod allowed list = Carol only)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
        ],
    },

    # 13.3 Scenario C — Fork pipeline isolation
    {
        "id": "10c-fork-isolation",
        "phase": "12",
        "section": "Scenario C — Fork Pipeline Isolation",
        "title": "Fork pipeline runs but cannot see protected variables",
        "persona": "root",
        "shots": [
            {"label": "MR list including fork-sourced MR",
             "path": f"/{PAY_API}/-/merge_requests?scope=all&state=all"},
            {"label": "MR settings — fork pipeline approval flag",
             "path": f"/{PAY_API}/-/settings/merge_requests"},
        ],
    },
    {
        "id": "10c2-fork-as-dan",
        "phase": "12",
        "section": "Scenario C — Fork Pipeline Isolation",
        "title": "Dan attempts to view upstream CI/CD settings — blocked",
        "persona": "poc-dan",
        "shots": [
            {"label": "Upstream payments/api CI/CD settings as Dan (should be denied)",
             "path": f"/{PAY_API}/-/settings/ci_cd",
             "expected_status": 404},
        ],
    },

    # 13.4 Scenario D — CI_JOB_TOKEN scoping
    {
        "id": "10d-job-token",
        "phase": "12",
        "section": "Scenario D — CI_JOB_TOKEN Scoping",
        "title": "Inbound job-token allowlist on payments/api",
        "persona": "root",
        "shots": [
            {"label": "Job token allowlist on payments/api (target of inbound calls)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "payments/ui pipeline (clone success/fail history)",
             "path": f"/{PAY_UI}/-/pipelines"},
        ],
    },

    # 13.5 Scenario E — Runner scoping
    {
        "id": "10e-runner-scoping",
        "phase": "11",  # Phase 11 sets up runners + zone policy
        "section": "Scenario E — Runner Scoping",
        "title": "Group-scoped runner only picks up payments + protected refs",
        "persona": "root",
        "shots": [
            {"label": "Group-level runners on payments",
             "path": f"/groups/{PAYMENTS}/-/runners"},
            {"label": "Project runner availability for payments/api",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "Sibling trade/orders pipelines (jobs stay pending)",
             "path": f"/{SIBLING_PROJ}/-/pipelines"},
        ],
    },

    # 13.6 Scenario F — CI/CD settings access
    {
        "id": "10f-cicd-settings-alice",
        "phase": "06",
        "section": "Scenario F — CI/CD Settings Access",
        "title": "Alice (Developer) cannot edit CI/CD settings",
        "persona": "poc-alice",
        "shots": [
            {"label": "payments/api CI/CD settings as Alice (denied — Developer can't read settings)",
             "path": f"/{PAY_API}/-/settings/ci_cd",
             "expected_status": 404},
            {"label": "Repository / Protected branches as Alice (denied)",
             "path": f"/{PAY_API}/-/settings/repository",
             "expected_status": 404},
        ],
    },
    {
        "id": "10f2-cicd-settings-bob",
        "phase": "06",
        "section": "Scenario F — CI/CD Settings Access",
        "title": "Bob (Maintainer) can edit CI/CD settings",
        "persona": "poc-bob",
        "shots": [
            {"label": "payments/api CI/CD settings as Bob (full access)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
        ],
    },

    # 13.7 Scenario G — Scheduled pipeline ownership
    {
        "id": "10g-schedules",
        "phase": "12",
        "section": "Scenario G — Scheduled Pipeline Ownership",
        "title": "Pipeline schedules + owner column",
        "persona": "root",
        "shots": [
            {"label": "Pipeline schedules (owner column, Take ownership control)",
             "path": f"/{PAY_API}/-/pipeline_schedules"},
            {"label": "Pipeline history filtered to scheduled runs",
             "path": f"/{PAY_API}/-/pipelines?scope=all&source=schedule"},
        ],
    },

    # 13.8 Scenario H — Variable inheritance and override
    {
        "id": "10h-variable-inheritance",
        "phase": "11",
        "section": "Scenario H — Variable Inheritance and Override",
        "title": "Group-level variable inherited; project-level overrides",
        "persona": "root",
        "shots": [
            {"label": "Group-level variables on payments",
             "path": f"/groups/{PAYMENTS}/-/settings/ci_cd"},
            {"label": "Project-level variable on payments/api (override)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "Sibling trade group variables (not visible to payments jobs)",
             "path": f"/groups/{SIBLING}/-/settings/ci_cd"},
        ],
    },

    # 13.9 Scenario I — Environment-scoped variables
    {
        "id": "10i-env-scoped-vars",
        "phase": "11",
        "section": "Scenario I — Environment-Scoped Variables",
        "title": "Same key, different values per environment scope",
        "persona": "root",
        "shots": [
            {"label": "payments/api CI/CD variables (env-scoped entries)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "Latest pipeline (deploy_staging vs deploy_prod logs)",
             "path": f"/{PAY_API}/-/pipelines"},
            {"label": "Environments (staging + prod)",
             "path": f"/{PAY_API}/-/environments"},
        ],
    },
]
