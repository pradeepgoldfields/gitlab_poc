"""
Enterprise GitLab Access Model PoC v2 — Organisation-Driven Configuration

This is the v2 PoC. The current v1 stays at gitlab-poc-scripts/.

Difference from v1
==================
v1 grants access to applications by sharing IAM-sim subgroups DIRECTLY with
the application projects. Each application carries an explicit list of LDAP
shares. When a person moves teams in IAM, they keep access to the old apps
until the share is rewritten.

v2 introduces a THREE-TIER separation of duties:

    IAM-sim                     Organisation tree              Application tree
    (LDAP groups)               (people grouped by team        (apps grouped by
                                 with role-bearing subgroups)   domain)
    ─────────                   ─────────────────────────       ───────────────
    gl-squad-1-developers ─→    tribe-1/squad-1/developers ─→   apps/domain-a/
                                                                  sub-a/proj-1
                                                                  (Developer role)

  * IAM groups feed people INTO organisations (Hop 1).
  * Organisations grant access TO applications (Hop 2).
  * Applications carry NO direct shares — all access flows from the org.
  * When IAM moves a person from one squad to another, they automatically
    lose old-app access and gain new-app access. Zero changes at the
    application tree.

The org tree itself uses **role-bearing subgroups** at each altitude:
  - top-level: platform-owners        (Owner on whole top group)
  - tribe   : tribe-leads             (Maintainer across tribe's apps)
              security-partners       (custom Security Manager across tribe)
  - squad   : squad-leads             (Maintainer on squad's apps)
              operators               (custom Operator on squad's apps)
              promoters               (custom Promoter on squad's apps)
              developers              (Developer on squad's apps)
              reporters               (Reporter on squad's apps)
"""
import os

import session as _session  # noqa: E402
_session.load_into_env()


def _suffix(base: str) -> str:
    """Append POC_PREFIX (if set) to a base identifier, separated by '-'."""
    p = (os.environ.get("POC_PREFIX") or "").strip().strip("-")
    return f"{base}-{p}" if p else base


# ---------------------------------------------------------------------------
# GitLab connection
# ---------------------------------------------------------------------------
GITLAB_URL = os.environ.get("GITLAB_URL", "http://localhost:8929")
GITLAB_ADMIN_TOKEN = os.environ.get("GITLAB_ADMIN_TOKEN", "")

_verify_env = os.environ.get("GITLAB_VERIFY_SSL")
if _verify_env is not None:
    VERIFY_SSL = bool(int(_verify_env))
else:
    VERIFY_SSL = GITLAB_URL.startswith("https")
REQUEST_TIMEOUT = int(os.environ.get("GITLAB_REQUEST_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# Top-level PoC group (default acme-poc-v2 so it coexists with v1's acme-poc)
# ---------------------------------------------------------------------------
TOP_GROUP = _suffix(os.environ.get("POC_TOP_GROUP", "acme-poc-v2"))
TOP_GROUP_VISIBILITY = os.environ.get("POC_TOP_GROUP_VISIBILITY", "internal")

# ---------------------------------------------------------------------------
# The four top-level peer subgroups under acme-poc-v2.
# ---------------------------------------------------------------------------
APPS_GROUP        = "applications"     # Internal — the application tree
ORGS_GROUP        = "organisations"    # Internal — the org tree (role-bearing)
PLATFORM_GROUP    = "platform"         # Internal — shared CI templates
IAM_SIM_GROUP     = "iam-sim"          # Private — simulated LDAP groups

# ---------------------------------------------------------------------------
# Application tree shape: applications/<domain>/<subdomain>/<projects>
# ---------------------------------------------------------------------------
# Apps carry NO direct shares in v2. All access flows from organisations.
# `restricted/` subgroups stay Private (visibility-only confidentiality).
APPLICATIONS = {
    "domain-a/subdomain-a":            ["proj-1", "proj-2", "proj-3"],
    "domain-a/subdomain-a/restricted": ["restricted-proj-1"],
    "domain-b/subdomain-b":            ["proj-4", "proj-5", "proj-6"],
    "domain-b/subdomain-b/restricted": ["restricted-proj-2"],
}

# Platform projects (separate top-level group, not under applications/)
PLATFORM_PROJECTS = ["ci-templates"]

# ---------------------------------------------------------------------------
# Organisation tree shape: organisations/{tribe-N/{squad-N/{role-subgroups}}}
# Each role-bearing subgroup is empty by default; Phase 4 adds users via
# IAM-sim shares.
# ---------------------------------------------------------------------------
TOP_LEVEL_ROLE_GROUPS = ["platform-owners"]
TRIBE_ROLE_GROUPS     = ["tribe-leads", "security-partners"]
SQUAD_ROLE_GROUPS     = ["squad-leads", "operators", "promoters", "developers", "reporters"]

ORGANISATIONS = {
    "tribe-1": ["squad-1", "squad-2"],
    "tribe-2": ["squad-3"],
}

# ---------------------------------------------------------------------------
# Test users
# ---------------------------------------------------------------------------
_EMAIL_DOMAIN = os.environ.get("POC_USER_EMAIL_DOMAIN", "example.com")
_PFX = (os.environ.get("POC_PREFIX") or "").strip().strip("-")


def _user_email(local: str) -> str:
    return f"{local}+{_PFX}@{_EMAIL_DOMAIN}" if _PFX else f"{local}@{_EMAIL_DOMAIN}"


_RAW_USERS = [
    ("v2-alice", "Alice (Squad-1 Developer)"),
    ("v2-bob",   "Bob (Squad-1 Lead, Maintainer)"),
    ("v2-carol", "Carol (Squad-1 Operator)"),
    ("v2-paul",  "Paul (Squad-1 Promoter)"),
    ("v2-rita",  "Rita (Squad-1 Reporter)"),
    ("v2-ed",    "Ed (Squad-2 Developer)"),
    ("v2-fred",  "Fred (Squad-3 Developer)"),
    ("v2-tina",  "Tina (Tribe-1 Lead, Maintainer)"),
    ("v2-sam",   "Sam (Tribe-1 Security Partner)"),
    ("v2-pat",   "Pat (Platform Owner)"),
    ("v2-dan",   "Dan (Inner-source contributor — no squad)"),
    ("v2-con",   "Con (Restricted reader)"),
]
TEST_USERS = [
    {"username": _suffix(u), "name": n, "email": _user_email(u)}
    for u, n in _RAW_USERS
]
USER_BY_SHORT = {
    raw.replace("v2-", ""): _suffix(raw) for raw, _ in _RAW_USERS
}
TEST_USER_DEFAULT_PASSWORD = os.environ.get(
    "POC_TEST_USER_PASSWORD", "PocTestP@ssw0rd!2026")

# ---------------------------------------------------------------------------
# IAM-sim — TWO simulated LDAP origins coexist in v2:
#   * SailPoint = the strategic, org-aligned origin (every new grant)
#   * SSCAM     = the legacy, project-level origin (kept for partial-migration
#                 fidelity — same org subgroup can be fed by both)
# Each LDAP group still flows through Hop 1 → an org subgroup; the org
# subgroup is what shares with apps. Apps NEVER see IAM groups directly.
# ---------------------------------------------------------------------------
SAILPOINT_GROUPS = (
    ["gl-acme-platform-owners"]
    + [f"gl-{tribe}-leads"     for tribe in ORGANISATIONS]
    + [f"gl-{tribe}-security"  for tribe in ORGANISATIONS]
    + [f"gl-{squad}-{role}"
       for tribe, squads in ORGANISATIONS.items()
       for squad in squads
       for role in SQUAD_ROLE_GROUPS]
    + ["gl-restricted-read"]
)

# SSCAM (legacy) — Bitbucket-era project-level _w/_r groups, kept verbatim.
# A given _w group feeds the OWNING squad's squad-leads; the matching _r
# group feeds the same squad's reporters. Mirrors the partial-migration
# state where some apps are still on legacy IAM naming.
SSCAM_GROUPS = [
    "proj-1_w", "proj-1_r",     # owned by squad-1
    "proj-2_w", "proj-2_r",     # owned by squad-1
    "proj-4_w", "proj-4_r",     # owned by squad-3
]

# ---------------------------------------------------------------------------
# Hop 1: IAM-sim → Organisation tree
# ---------------------------------------------------------------------------
# Each LDAP group is shared with exactly one org subgroup at Developer level.
# (The actual privilege onto apps comes at Hop 2 via org→app share.)
_U = USER_BY_SHORT
IAM_TO_ORG_SHARES = [
    # Top-level
    {"iam_group": "iam-sim/sailpoint/gl-acme-platform-owners",
     "org_path":  "organisations/platform-owners"},

    # Tribe-1
    {"iam_group": "iam-sim/sailpoint/gl-tribe-1-leads",
     "org_path":  "organisations/tribe-1/tribe-leads"},
    {"iam_group": "iam-sim/sailpoint/gl-tribe-1-security",
     "org_path":  "organisations/tribe-1/security-partners"},

    # Tribe-1 / Squad-1
    {"iam_group": "iam-sim/sailpoint/gl-squad-1-squad-leads",
     "org_path":  "organisations/tribe-1/squad-1/squad-leads"},
    {"iam_group": "iam-sim/sailpoint/gl-squad-1-operators",
     "org_path":  "organisations/tribe-1/squad-1/operators"},
    {"iam_group": "iam-sim/sailpoint/gl-squad-1-promoters",
     "org_path":  "organisations/tribe-1/squad-1/promoters"},
    {"iam_group": "iam-sim/sailpoint/gl-squad-1-developers",
     "org_path":  "organisations/tribe-1/squad-1/developers"},
    {"iam_group": "iam-sim/sailpoint/gl-squad-1-reporters",
     "org_path":  "organisations/tribe-1/squad-1/reporters"},

    # Tribe-1 / Squad-2 (developers only — proves project-level org→app share)
    {"iam_group": "iam-sim/sailpoint/gl-squad-2-developers",
     "org_path":  "organisations/tribe-1/squad-2/developers"},

    # Tribe-2 / Squad-3
    {"iam_group": "iam-sim/sailpoint/gl-squad-3-developers",
     "org_path":  "organisations/tribe-2/squad-3/developers"},

    # --- SSCAM (legacy origin) ---
    # _w groups feed the squad-leads of the owning squad (Maintainer-level
    # via org); _r groups feed the same squad's reporters. Demonstrates
    # that a single org subgroup can be fed by multiple LDAP origins
    # during partial migration off legacy IAM naming.
    {"iam_group": "iam-sim/sscam/proj-1_w",
     "org_path":  "organisations/tribe-1/squad-1/squad-leads"},
    {"iam_group": "iam-sim/sscam/proj-1_r",
     "org_path":  "organisations/tribe-1/squad-1/reporters"},
    {"iam_group": "iam-sim/sscam/proj-2_w",
     "org_path":  "organisations/tribe-1/squad-1/squad-leads"},
    {"iam_group": "iam-sim/sscam/proj-2_r",
     "org_path":  "organisations/tribe-1/squad-1/reporters"},
    {"iam_group": "iam-sim/sscam/proj-4_w",
     "org_path":  "organisations/tribe-2/squad-3/developers"},
    {"iam_group": "iam-sim/sscam/proj-4_r",
     "org_path":  "organisations/tribe-2/squad-3/developers"},
]

# Initial people seeded into IAM groups (Phase 4 inserts these).
IAM_MEMBERSHIPS = {
    "iam-sim/sailpoint/gl-acme-platform-owners":   [_U["pat"]],
    "iam-sim/sailpoint/gl-tribe-1-leads":          [_U["tina"]],
    "iam-sim/sailpoint/gl-tribe-1-security":       [_U["sam"]],
    "iam-sim/sailpoint/gl-squad-1-squad-leads":    [_U["bob"]],
    "iam-sim/sailpoint/gl-squad-1-operators":      [_U["carol"]],
    "iam-sim/sailpoint/gl-squad-1-promoters":      [_U["paul"]],
    "iam-sim/sailpoint/gl-squad-1-developers":     [_U["alice"]],
    "iam-sim/sailpoint/gl-squad-1-reporters":      [_U["rita"]],
    "iam-sim/sailpoint/gl-squad-2-developers":     [_U["ed"]],
    "iam-sim/sailpoint/gl-squad-3-developers":     [_U["fred"]],
    "iam-sim/sailpoint/gl-restricted-read":        [_U["con"]],

    # SSCAM (legacy) — same person in two origins to demonstrate dual-IAM
    # feeding the same org subgroup. Bob is in both gl-squad-1-squad-leads
    # AND proj-1_w (legacy app-team write group); Rita is in both
    # gl-squad-1-reporters AND proj-1_r.
    "iam-sim/sscam/proj-1_w":                      [_U["bob"]],
    "iam-sim/sscam/proj-1_r":                      [_U["rita"]],
    # The other SSCAM groups exist as empty containers for the demo.
}

TOP_LEVEL_MINIMAL_ACCESS_USERS = [_U["dan"]]

# ---------------------------------------------------------------------------
# Built-in role IDs
# ---------------------------------------------------------------------------
ROLE = {
    "no_access":  0,
    "minimal":    5,
    "guest":     10,
    "planner":   15,
    "reporter":  20,
    "developer": 30,
    "maintainer": 40,
    "owner":     50,
}

# ---------------------------------------------------------------------------
# Custom role definitions (Phase 1)
# ---------------------------------------------------------------------------
CUSTOM_ROLES = [
    {
        "name": _suffix("Promoter"),
        "description": "Triggers promotion pipelines; manages release CI variables",
        "base_role": "reporter",
        "abilities": ["admin_cicd_variables"],
    },
    {
        "name": _suffix("Operator"),
        "description": "Manages prod env + release branches",
        "base_role": "reporter",
        "abilities": [
            "admin_protected_environments",
            "admin_cicd_variables",
            "read_runners",
            "admin_runners",
        ],
    },
    {
        "name": _suffix("Security Manager"),
        "description": "Manages vulnerability waivers and approves security MRs",
        "base_role": "reporter",
        "abilities": [
            "read_vulnerability",
            "admin_vulnerability",
            "admin_merge_request",
        ],
    },
]

# ---------------------------------------------------------------------------
# Hop 2: Organisation → Application
# ---------------------------------------------------------------------------
# Each entry shares one ORG subgroup with one APP scope at a given role.
# Use `role` for built-in roles or `role_name` for a custom role.
ORG_TO_APP_SHARES = [
    # === Tribe-1 (broad, cross-squad) ===
    {"org_path": "organisations/tribe-1/tribe-leads",
     "app_path": "applications/domain-a",
     "role": "maintainer"},
    {"org_path": "organisations/tribe-1/security-partners",
     "app_path": "applications/domain-a",
     "role_name": "Security Manager"},

    # === Tribe-1 / Squad-1 — owns subdomain-a (group-level shares) ===
    {"org_path": "organisations/tribe-1/squad-1/squad-leads",
     "app_path": "applications/domain-a/subdomain-a",
     "role": "maintainer"},
    {"org_path": "organisations/tribe-1/squad-1/operators",
     "app_path": "applications/domain-a/subdomain-a",
     "role_name": "Operator"},
    {"org_path": "organisations/tribe-1/squad-1/promoters",
     "app_path": "applications/domain-a/subdomain-a",
     "role_name": "Promoter"},
    {"org_path": "organisations/tribe-1/squad-1/developers",
     "app_path": "applications/domain-a/subdomain-a",
     "role": "developer"},
    {"org_path": "organisations/tribe-1/squad-1/reporters",
     "app_path": "applications/domain-a/subdomain-a",
     "role": "reporter"},

    # === Tribe-1 / Squad-2 — owns proj-3 only (project-level share) ===
    {"org_path": "organisations/tribe-1/squad-2/developers",
     "app_path": "applications/domain-a/subdomain-a/proj-3",
     "role": "developer"},

    # === Tribe-2 / Squad-3 — owns subdomain-b ===
    {"org_path": "organisations/tribe-2/squad-3/developers",
     "app_path": "applications/domain-b/subdomain-b",
     "role": "developer"},

    # === Restricted-read share (the only "direct from IAM" exception) ===
    {"org_path": "iam-sim/sailpoint/gl-restricted-read",
     "app_path": "applications/domain-a/subdomain-a/restricted",
     "role": "reporter"},
]

# Top-level Owner share — platform-owners org subgroup → top group as Owner
TOP_LEVEL_SHARES = [
    {"shared_group": "organisations/platform-owners", "role": "owner"},
]

# ---------------------------------------------------------------------------
# Protection plan (Phase 7)
# ---------------------------------------------------------------------------
PROTECTION_PLAN = {
    "protected_branches": [
        {
            "project": "applications/domain-a/subdomain-a/proj-1",
            "name": "main",
            "push_access_level": 0,
            "merge_access_level": 40,
            "code_owner_approval_required": True,
        },
        {
            "project": "applications/domain-b/subdomain-b/proj-4",
            "name": "main",
            "push_access_level": 0,
            "merge_access_level": 40,
            "code_owner_approval_required": True,
        },
    ],
    "protected_tags": [
        {"project": "applications/domain-a/subdomain-a/proj-1", "name": "v*", "create_access_level": 40},
        {"project": "applications/domain-b/subdomain-b/proj-4", "name": "v*", "create_access_level": 40},
    ],
    "protected_environments": [
        {
            "project": "applications/domain-a/subdomain-a/proj-1",
            "name": "staging",
            "deploy_access_levels": [{"access_level": 30}],
            "approval_rules": [],
        },
        {
            "project": "applications/domain-a/subdomain-a/proj-1",
            "name": "prod",
            "deploy_access_users": [_U["carol"]],
            "approval_rules": [
                {"required_approvals": 1, "group_path": None, "username": _U["bob"]},
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# CI samples
# ---------------------------------------------------------------------------
SAMPLE_CI_YAML = """\
stages: [build, deploy]
build:
  stage: build
  script: ['echo "Building"']
deploy_staging:
  stage: deploy
  script: ['echo "Deploying to staging"']
  environment: { name: staging }
  rules: [{ if: '$CI_COMMIT_BRANCH == "main"' }]
deploy_prod:
  stage: deploy
  script:
    - echo "Deploying to PROD"
    - echo "Token is ${PROD_DEPLOY_TOKEN:-empty}"
  environment: { name: prod }
  rules: [{ if: '$CI_COMMIT_TAG' }]
  when: manual
"""

SAMPLE_CODEOWNERS = f"""\
*                @{TOP_GROUP}/organisations/tribe-1/squad-1/squad-leads
/infra/          @{TOP_GROUP}/organisations/tribe-1/security-partners
/.gitlab-ci.yml  @{TOP_GROUP}/organisations/tribe-1/squad-1/squad-leads
"""

ZONE_VARIABLES = [
    {
        "group": "applications/domain-a/subdomain-a",
        "key": "PROD_DEPLOY_TOKEN",
        "value": "subdomain-a-prod-secret",
        "protected": True,
        "masked": True,
        "environment_scope": "prod",
    },
]
