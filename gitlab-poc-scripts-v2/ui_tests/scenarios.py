"""
v2 UI evidence scenarios — one entry per use case in poc-overview-v2.html.

The v2 model has THREE trees (apps / orgs / iam-sim) and a two-hop access
flow. Scenarios are organised the same way:
  Part 1   Hierarchy     — top group, apps tree, orgs tree, iam-sim
  Part 2   Hop 1         — IAM-sim → Organisation tree (with dual SSCAM+SailPoint feed)
  Part 3   Hop 2         — Organisation → Application
  Part 4-6 Same as v1    — protected branches/tags/envs, inner source, audit
  Part 7   Org flows     — joiner / mover / promotion / reorg / sec sweep proofs
"""
from __future__ import annotations

# Path constants — define once, use everywhere.
APPS         = "{top}/applications"
DOMAIN_A     = f"{APPS}/domain-a"
SUB_A        = f"{DOMAIN_A}/subdomain-a"
PROJ_1       = f"{SUB_A}/proj-1"
PROJ_2       = f"{SUB_A}/proj-2"
PROJ_3       = f"{SUB_A}/proj-3"
RESTRICTED   = f"{SUB_A}/restricted"
RESTRICTED_PROJ = f"{RESTRICTED}/restricted-proj-1"
DOMAIN_B     = f"{APPS}/domain-b"
SUB_B        = f"{DOMAIN_B}/subdomain-b"
PROJ_4       = f"{SUB_B}/proj-4"

ORGS         = "{top}/organisations"
PLATFORM_OWNERS = f"{ORGS}/platform-owners"
TRIBE_1      = f"{ORGS}/tribe-1"
TRIBE_LEADS  = f"{TRIBE_1}/tribe-leads"
SEC_PARTNERS = f"{TRIBE_1}/security-partners"
SQUAD_1      = f"{TRIBE_1}/squad-1"
SQUAD_1_DEVS = f"{SQUAD_1}/developers"
SQUAD_1_LEADS = f"{SQUAD_1}/squad-leads"
SQUAD_1_OPS  = f"{SQUAD_1}/operators"
SQUAD_1_PROMOTERS = f"{SQUAD_1}/promoters"

IAM          = "{top}/iam-sim"
SAILPOINT    = f"{IAM}/sailpoint"
SSCAM        = f"{IAM}/sscam"

CI_TEMPLATES = "{top}/platform/ci-templates"
DAN_FORK     = "v2-dan/proj-1"


SCENARIOS: list[dict] = [
    # ===== Part 1 — Hierarchy =====
    {
        "id": "01-hierarchy-top",
        "phase": "02",
        "section": "Part 1 — Hierarchy",
        "title": "Top-level group + four peer subgroups",
        "persona": "root",
        "shots": [
            {"label": "Top group members + overview",
             "path": "/groups/{top}/-/group_members"},
            {"label": "Top tree (apps / orgs / platform / iam-sim)",
             "path": "/groups/{top}"},
            {"label": "Applications tree (domain-a, domain-b)",
             "path": f"/groups/{APPS}"},
            {"label": "Organisations tree (tribes, role groups)",
             "path": f"/groups/{ORGS}"},
        ],
    },
    {
        "id": "02-iam-sim",
        "phase": "03",
        "section": "Part 1 — Hierarchy",
        "title": "IAM-sim — both SailPoint (modern) and SSCAM (legacy)",
        "persona": "root",
        "shots": [
            {"label": "iam-sim/ Private container",
             "path": f"/groups/{IAM}"},
            {"label": "SailPoint groups (org-aligned naming)",
             "path": f"/groups/{SAILPOINT}"},
            {"label": "SSCAM groups (legacy project-level naming)",
             "path": f"/groups/{SSCAM}"},
        ],
    },

    # ===== Part 2 — Hop 1 (IAM → Org) =====
    {
        "id": "03-hop1-sailpoint",
        "phase": "04",
        "section": "Part 2 — Hop 1: IAM-sim → Organisation",
        "title": "SailPoint LDAP group shares with squad-1/developers",
        "persona": "root",
        "shots": [
            {"label": "squad-1/developers — Members → Groups tab shows the LDAP feed",
             "path": f"/groups/{SQUAD_1_DEVS}/-/group_members"},
            {"label": "The source LDAP group (gl-squad-1-developers)",
             "path": f"/groups/{SAILPOINT}/gl-squad-1-developers"},
        ],
    },
    {
        "id": "04-hop1-dual-feed",
        "phase": "04",
        "section": "Part 2 — Hop 1: IAM-sim → Organisation",
        "title": "Dual feed — squad-1/squad-leads fed by BOTH SailPoint and SSCAM",
        "persona": "root",
        "shots": [
            {"label": "squad-1/squad-leads — Members → Groups shows two LDAP origins",
             "path": f"/groups/{SQUAD_1_LEADS}/-/group_members"},
            {"label": "Modern: SailPoint gl-squad-1-squad-leads",
             "path": f"/groups/{SAILPOINT}/gl-squad-1-squad-leads"},
            {"label": "Legacy: SSCAM proj-1_w (Bitbucket-era app-team write group)",
             "path": f"/groups/{SSCAM}/proj-1_w"},
        ],
    },

    # ===== Part 3 — Hop 2 (Org → App) =====
    {
        "id": "05-hop2-org-to-app",
        "phase": "05",
        "section": "Part 3 — Hop 2: Organisation → Application",
        "title": "Org subgroups shared with the application scope",
        "persona": "root",
        "shots": [
            {"label": "subdomain-a — Members → Groups shows squad-1's role groups",
             "path": f"/groups/{SUB_A}/-/group_members"},
            {"label": "proj-3 — Members shows squad-2/developers (project-level share)",
             "path": f"/{PROJ_3}/-/project_members"},
            {"label": "domain-a — Members shows tribe-1/tribe-leads (Maintainer) + tribe-1/security-partners (Sec Mgr)",
             "path": f"/groups/{DOMAIN_A}/-/group_members"},
        ],
    },
    {
        "id": "06-app-tree-purity",
        "phase": "05",
        "section": "Part 3 — Hop 2: Organisation → Application",
        "title": "Apps carry NO direct IAM shares — proof of org-driven model",
        "persona": "root",
        "shots": [
            {"label": "proj-1 Members — shows ONLY org subgroups (no iam-sim/* paths)",
             "path": f"/{PROJ_1}/-/project_members"},
        ],
    },

    # ===== Part 4 — Baseline access (org-driven) =====
    {
        "id": "07-baseline-alice",
        "phase": "05",
        "section": "Part 4 — Baseline Access (org-driven)",
        "title": "Alice (squad-1 developer via SailPoint) has Developer on subdomain-a",
        "persona": "v2-alice",
        "shots": [
            {"label": "proj-1 as Alice (Developer access)",
             "path": f"/{PROJ_1}"},
            {"label": "ci-templates as Alice (Internal — visible)",
             "path": f"/{CI_TEMPLATES}"},
        ],
    },

    # ===== Part 5 — Branch / Tag / Env Protection =====
    {
        "id": "08-protected-branch",
        "phase": "07",
        "section": "Part 5 — Protections",
        "title": "Protected main on proj-1 (Maintainer-merge, codeowner approval)",
        "persona": "root",
        "shots": [
            {"label": "Protected branches config",
             "path": f"/{PROJ_1}/-/settings/repository"},
            {"label": "MR settings (approval rules)",
             "path": f"/{PROJ_1}/-/settings/merge_requests"},
            {"label": "CODEOWNERS file",
             "path": f"/{PROJ_1}/-/blob/main/CODEOWNERS"},
        ],
    },
    {
        "id": "09-protected-env",
        "phase": "07",
        "section": "Part 5 — Protections",
        "title": "Prod environment gated to Carol (Operator) with Bob's approval",
        "persona": "root",
        "shots": [
            {"label": "Environments list",
             "path": f"/{PROJ_1}/-/environments"},
            {"label": "Protected env config",
             "path": f"/{PROJ_1}/-/settings/ci_cd"},
        ],
    },

    # ===== Part 6 — Inner sourcing =====
    {
        "id": "10-inner-source",
        "phase": "10",
        "section": "Part 6 — Inner Sourcing",
        "title": "Dan discovers + reads + forks without any squad membership",
        "persona": "v2-dan",
        "shots": [
            {"label": "Explore as Dan",
             "path": "/explore/projects"},
            {"label": "proj-1 as Dan (Internal — readable)",
             "path": f"/{PROJ_1}"},
            {"label": "Dan's fork in personal namespace",
             "path": f"/{DAN_FORK}"},
        ],
    },
    {
        "id": "11-restricted-isolation",
        "phase": "10",
        "section": "Part 6 — Inner Sourcing",
        "title": "Alice cannot reach the Private restricted-proj-1",
        "persona": "v2-alice",
        "shots": [
            {"label": "restricted-proj-1 as Alice — should 404",
             "path": f"/{RESTRICTED_PROJ}",
             "expected_status": 404},
        ],
    },

    # ===== Part 7 — Audit + denial =====
    {
        "id": "12-audit",
        "phase": "13",
        "section": "Part 7 — Audit",
        "title": "Audit events captured at all three levels",
        "persona": "root",
        "shots": [
            {"label": "Top-level audit events",
             "path": "/groups/{top}/-/audit_events"},
            {"label": "Project-level audit events for proj-1",
             "path": f"/{PROJ_1}/-/audit_events"},
        ],
    },
    {
        "id": "13-cicd-denial-alice",
        "phase": "07",
        "section": "Part 7 — Denial proofs",
        "title": "Alice (Developer) denied CI/CD settings access",
        "persona": "v2-alice",
        "shots": [
            {"label": "proj-1 CI/CD settings as Alice — should 404",
             "path": f"/{PROJ_1}/-/settings/ci_cd",
             "expected_status": 404},
        ],
    },
    {
        "id": "14-cicd-bob-allowed",
        "phase": "07",
        "section": "Part 7 — Denial proofs",
        "title": "Bob (squad-1 lead, Maintainer) has full CI/CD access",
        "persona": "v2-bob",
        "shots": [
            {"label": "proj-1 CI/CD settings as Bob (full access)",
             "path": f"/{PROJ_1}/-/settings/ci_cd"},
        ],
    },
]
