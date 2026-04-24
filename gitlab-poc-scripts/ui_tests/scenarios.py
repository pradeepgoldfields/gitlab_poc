"""
UI-test scenarios — one entry per use case in
gitlab-access-model-poc-report.html.

Each scenario captures one or more screenshots from the live GitLab UI.
This is **evidence-only** — there are no assertions. A scenario "passes" if
every URL loaded without an HTTP 4xx/5xx; otherwise the failed shot is
flagged red in the report (still captured as evidence).

URL paths are templates. {top} expands to config.TOP_GROUP at run time
(picks up POC_PREFIX automatically).

PATH MAPPING — generic PoC layout
=================================
All identifiers in the PoC are intentionally generic (no business names).
The same Path constants are reused across scenarios via f-strings, so a
rename here propagates automatically:

  domain-a    = primary domain (used for Approach 1 hybrid + custom roles)
  domain-b    = sibling domain (used for Approach 2 group-centric)
  proj-1/2/3  = generic projects under each domain
  restricted-proj-1 = the Private project under domain-a/restricted/
  poc-dan/proj-1    = Dan's fork (personal namespace preserves project name)
"""
from __future__ import annotations

# Convenience templates — define once, reuse across scenarios.
PAYMENTS = "{top}/business-unit-a/domain-a"
PAY_API = f"{PAYMENTS}/proj-1"
PAY_UI = f"{PAYMENTS}/proj-2"
PAY_RESTRICTED = f"{PAYMENTS}/restricted/restricted-proj-1"
SIBLING = "{top}/business-unit-a/domain-b"   # sibling domain
SIBLING_PROJ = f"{SIBLING}/proj-1"
CI_TEMPLATES = "{top}/platform/ci-templates"
DAN_FORK = "poc-dan/proj-1"                  # fork lands in personal namespace

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
            {"label": "Top group tree (flat domains)",
             "path": "/groups/{top}"},
            {"label": "Pilot project (domain-a/proj-1)",
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
            {"label": "domain-a subgroup members",
             "path": f"/groups/{PAYMENTS}/-/group_members"},
            {"label": "domain-a/proj-1 members (direct + inherited)",
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
        "title": "Alice's view of domain-a/proj-1 (no Settings, no Delete)",
        "persona": "poc-alice",
        "shots": [
            {"label": "domain-a/proj-1 project as Alice (Developer)",
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
            {"label": "domain-a/proj-1 as Dan (Internal — readable, not writable)",
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
            {"label": "domain-a/proj-2 members (inherited from payments)",
             "path": f"/{PAY_UI}/-/project_members"},
            {"label": "domain-a/proj-1 members (raised access)",
             "path": f"/{PAY_API}/-/project_members"},
            {"label": "Top group tree at a glance",
             "path": "/groups/{top}"},
        ],
    },
    {
        "id": "08b-sibling-isolation",
        "phase": "06",
        "section": "Part 8 — Inheritance and Sovereignty",
        "title": "Alice has no access to a Private restricted project",
        "persona": "poc-alice",
        # NOTE: domain-b/proj-1 is Internal — Alice can read it via inner-source
        # visibility, so we can't use it for an isolation test. The
        # domain-a/restricted/restricted-proj-1 project is Private and Alice
        # is NOT a member of domain-a/restricted, so this is a true 404.
        "shots": [
            {"label": "restricted-proj-1 (Private) as Alice — should 404",
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
            {"label": "Project-level audit events for domain-a/proj-1",
             "path": f"/{PAY_API}/-/audit_events"},
            {"label": "Instance-wide audit events (admin)",
             "path": "/admin/audit_logs"},
            {"label": "Members CSV export source — domain-a subgroup",
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
            {"label": "Upstream domain-a/proj-1 CI/CD settings as Dan (should be denied)",
             "path": f"/{PAY_API}/-/settings/ci_cd",
             "expected_status": 404},
        ],
    },

    # 13.4 Scenario D — CI_JOB_TOKEN scoping
    {
        "id": "10d-job-token",
        "phase": "12",
        "section": "Scenario D — CI_JOB_TOKEN Scoping",
        "title": "Inbound job-token allowlist on domain-a/proj-1",
        "persona": "root",
        "shots": [
            {"label": "Job token allowlist on domain-a/proj-1 (target of inbound calls)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "domain-a/proj-2 pipeline (clone success/fail history)",
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
            {"label": "Project runner availability for domain-a/proj-1",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "Sibling domain-b/proj-1 pipelines (jobs stay pending)",
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
            {"label": "domain-a/proj-1 CI/CD settings as Alice (denied — Developer can't read settings)",
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
            {"label": "domain-a/proj-1 CI/CD settings as Bob (full access)",
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
            {"label": "Project-level variable on domain-a/proj-1 (override)",
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
            {"label": "domain-a/proj-1 CI/CD variables (env-scoped entries)",
             "path": f"/{PAY_API}/-/settings/ci_cd"},
            {"label": "Latest pipeline (deploy_staging vs deploy_prod logs)",
             "path": f"/{PAY_API}/-/pipelines"},
            {"label": "Environments (staging + prod)",
             "path": f"/{PAY_API}/-/environments"},
        ],
    },
]
