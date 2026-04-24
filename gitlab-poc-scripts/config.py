"""
Enterprise GitLab Access Model PoC - Configuration

Edit this file to match your GitLab instance before running any phase script.
All other scripts import from here so there is one source of truth.

The orchestrator (run_poc.py) overrides GITLAB_URL, GITLAB_ADMIN_TOKEN and
POC_PREFIX at startup based on user input or CLI flags, so command-line runs
can leave the defaults alone.

PORTABILITY
-----------
The same script suite runs against any GitLab instance (local Docker,
self-managed remote, or GitLab.com SaaS). The differences are:

  * URL/token: pass via --url / --token to run_poc.py, or set GITLAB_URL +
    GITLAB_ADMIN_TOKEN.
  * Naming collisions on shared instances: set POC_PREFIX (or pass
    --prefix to run_poc.py) so TOP_GROUP, test users, and custom roles get
    a unique suffix and can coexist with other people's runs.
  * SaaS / non-admin tokens: user creation, custom roles and hard-delete
    require admin. On gitlab.com you must pre-provision the test users
    (see README, "Running on GitLab.com").
"""
import os

# Auto-load any saved settings from .pocenv (set by run_poc.py on first run).
# Env vars already set by the user take precedence.
import session as _session  # noqa: E402
_session.load_into_env()


def _suffix(base: str) -> str:
    """Append POC_PREFIX (if set) to a base identifier, separated by '-'.
    Used to avoid collisions on shared GitLab instances."""
    p = (os.environ.get("POC_PREFIX") or "").strip().strip("-")
    return f"{base}-{p}" if p else base


# ---------------------------------------------------------------------------
# GitLab connection
# ---------------------------------------------------------------------------
# The base URL of the GitLab instance. run_poc.py prompts and overrides.
GITLAB_URL = os.environ.get("GITLAB_URL", "http://localhost:8929")

# Personal access token with `api` scope. Admin scope is required for:
#   - creating instance-level custom roles (Phase 1)
#   - creating users + minting impersonation tokens (Phases 4, setup_test_users.py)
#   - hard_delete / permanently_remove (cleanup.py)
# Without admin you can still run the read-only verification and any phase
# that only operates on groups/projects you own.
GITLAB_ADMIN_TOKEN = os.environ.get("GITLAB_ADMIN_TOKEN", "")

# SSL verification. Defaults to ON for https URLs (the safe default for any
# real instance) and OFF for plain http (local Docker). Override either way
# with GITLAB_VERIFY_SSL=0 / =1.
_verify_env = os.environ.get("GITLAB_VERIFY_SSL")
if _verify_env is not None:
    VERIFY_SSL = bool(int(_verify_env))
else:
    VERIFY_SSL = GITLAB_URL.startswith("https")

# Request timeout in seconds
REQUEST_TIMEOUT = int(os.environ.get("GITLAB_REQUEST_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# Top-level PoC group
# ---------------------------------------------------------------------------
# POC_PREFIX (set via env or --prefix) is appended so the same instance can
# host multiple parallel PoC runs without colliding. Default: "acme-poc".
TOP_GROUP = _suffix(os.environ.get("POC_TOP_GROUP", "acme-poc"))
TOP_GROUP_VISIBILITY = os.environ.get("POC_TOP_GROUP_VISIBILITY", "internal")   # internal | private | public

# ---------------------------------------------------------------------------
# Deployment-zone subgroups (from the design)
# ---------------------------------------------------------------------------
DEPLOYMENT_ZONES = [
    {"path": "live-production",           "visibility": "internal"},
    {"path": "live-cloud-landing-zone",   "visibility": "internal"},
    {"path": "non-live-enterprise", "visibility": "internal"},
]

# Simulated IAM container (Private, holds the simulated LDAP groups)
IAM_SIM_GROUP = "iam-sim"

# Platform group (shared CI templates, runners, etc.)
PLATFORM_GROUP = "platform"

# ---------------------------------------------------------------------------
# Domains created under live-production (for the PoC)
# ---------------------------------------------------------------------------
DOMAINS = {
    "live-production": ["domain-a", "domain-b"],
    "live-cloud-landing-zone": ["domain-a"],
    "non-live-enterprise": ["domain-a"],
}

# Projects per domain (only for the main test domains; extend as needed)
PROJECTS = {
    "live-production/domain-a":            ["proj-1", "proj-2", "proj-3"],
    "live-production/domain-a/restricted": ["restricted-proj-1"],
    "live-production/domain-b":            ["proj-1", "proj-2", "proj-3"],
    "platform":                            ["ci-templates"],
}

# ---------------------------------------------------------------------------
# Test users
# ---------------------------------------------------------------------------
# The PoC needs 8 test accounts. If the instance allows user creation via API
# (admin token), Phase 4 will create them. Otherwise pre-provision them and
# make sure the usernames here match.
#
# Usernames and emails are globally unique on the instance, so we apply
# POC_PREFIX. With POC_PREFIX="alice-run1" you get usernames like
# "poc-alice-alice-run1" and emails "poc-alice+alice-run1@example.com" —
# safe to coexist with anyone else's run.
#
# POC_USER_EMAIL_DOMAIN lets you point at a domain you actually own, so any
# real notification mail goes somewhere you control (default: example.com).
_EMAIL_DOMAIN = os.environ.get("POC_USER_EMAIL_DOMAIN", "example.com")
_PFX = (os.environ.get("POC_PREFIX") or "").strip().strip("-")


def _user_email(local: str) -> str:
    return f"{local}+{_PFX}@{_EMAIL_DOMAIN}" if _PFX else f"{local}@{_EMAIL_DOMAIN}"


_RAW_USERS = [
    ("poc-alice", "Alice (PoC Developer)"),
    ("poc-bob",   "Bob (PoC Maintainer)"),
    ("poc-carol", "Carol (PoC Operator)"),
    ("poc-paul",  "Paul (PoC Promoter)"),
    ("poc-sam",   "Sam (PoC Security Manager)"),
    ("poc-rita",  "Rita (PoC Reporter)"),
    ("poc-dan",   "Dan (PoC Inner Source)"),
    ("poc-con",   "Con (PoC Confidential)"),
]
TEST_USERS = [
    {"username": _suffix(u), "name": n, "email": _user_email(u)}
    for u, n in _RAW_USERS
]

# Lookup table from canonical short name (alice, bob, …) to actual username.
# Phase scripts use this so they can reference users by their well-known short
# name regardless of the prefix.
USER_BY_SHORT = {
    raw.replace("poc-", ""): _suffix(raw) for raw, _ in _RAW_USERS
}

# Default password for auto-created users. ONLY used for sandbox instances.
# Real instances should provision via SSO/SCIM.
TEST_USER_DEFAULT_PASSWORD = os.environ.get(
    "POC_TEST_USER_PASSWORD", "PocTestP@ssw0rd!2026")

# ---------------------------------------------------------------------------
# Simulated IAM group structure (SSCAM / SailPoint / P2P)
# ---------------------------------------------------------------------------
SSCAM_GROUPS = [
    "domain-a-proj-1_w",
    "domain-a-proj-1_r",
    "domain-a-proj-2_w",
    "domain-a-proj-2_r",
]

SAILPOINT_GROUPS = [
    "gl-domain-a-read",
    "gl-domain-a-dev",
    "gl-domain-a-maint",
    "gl-domain-a-owner",
    "gl-domain-b-read",
    "gl-domain-b-dev",
    "gl-domain-b-maint",
    "gl-domain-b-owner",
    "gl-restricted-read",
]

P2P_GROUPS = [
    "IAM_DevOps_domain-a_Promoter",
    "IAM_DevOps_domain-a_Operator",
    "IAM_DevOps_domain-a_SecurityManager",
    "IAM_DevOps_domain-a_Maintainer",
    "IAM_DevOps_domain-a_Developer",
    "IAM_DevOps_domain-a_Reporter",
    "IAM_DevOps_Owner",
]

# ---------------------------------------------------------------------------
# Which user goes into which IAM group (for Phase 4)
# ---------------------------------------------------------------------------
# Username values flow through USER_BY_SHORT so they pick up POC_PREFIX.
_U = USER_BY_SHORT
IAM_MEMBERSHIPS = {
    # SSCAM (Approach 1)
    "iam-sim/sscam/domain-a-proj-1_w": [_U["alice"]],
    "iam-sim/sscam/domain-a-proj-1_r": [_U["rita"]],

    # SailPoint (Approach 2)
    "iam-sim/sailpoint/gl-domain-a-dev":    [_U["alice"]],
    "iam-sim/sailpoint/gl-domain-a-read":   [_U["rita"]],
    "iam-sim/sailpoint/gl-domain-a-maint":  [_U["bob"]],
    "iam-sim/sailpoint/gl-domain-b-dev":    [_U["alice"]],
    "iam-sim/sailpoint/gl-restricted-read": [_U["con"]],

    # P2P DevOps (renamed from P2P_GS_DevOps_* to IAM_DevOps_*)
    "iam-sim/p2p/IAM_DevOps_domain-a_Promoter":        [_U["paul"]],
    "iam-sim/p2p/IAM_DevOps_domain-a_Operator":        [_U["carol"]],
    "iam-sim/p2p/IAM_DevOps_domain-a_SecurityManager": [_U["sam"]],
    "iam-sim/p2p/IAM_DevOps_domain-a_Maintainer":      [_U["bob"]],
    "iam-sim/p2p/IAM_DevOps_domain-a_Developer":       [_U["alice"]],
    "iam-sim/p2p/IAM_DevOps_domain-a_Reporter":        [_U["rita"]],
}

# Users granted Minimal Access at the top-level group
TOP_LEVEL_MINIMAL_ACCESS_USERS = [_U["dan"]]

# ---------------------------------------------------------------------------
# GitLab role IDs (built-in)
# ---------------------------------------------------------------------------
ROLE = {
    "no_access":     0,
    "minimal":       5,
    "guest":        10,
    "planner":      15,
    "reporter":     20,
    "developer":    30,
    "maintainer":   40,
    "owner":        50,
}

# ---------------------------------------------------------------------------
# Custom role definitions (Phase 1)
# ---------------------------------------------------------------------------
# Ability names must match GitLab's member role ability keys.
# Reference: https://docs.gitlab.com/api/member_roles/
#
# Substitutions for GitLab 18.x EE — the API does not expose the abilities
# named in the original design (admin_pipeline / admin_environment /
# approve_merge_request). The closest 18.x equivalents are used instead and
# documented in the execution guide:
#   - admin_pipeline           -> (no equivalent; pipeline trigger flows
#                                  through base Reporter + protected branch
#                                  allow-list, not a custom ability)
#   - admin_environment        -> admin_protected_environments
#   - approve_merge_request    -> admin_merge_request
# Operator's admin_runners requires read_runners as a prerequisite — the API
# rejects the create otherwise.
# Custom-role names also pick up POC_PREFIX so they don't collide on a shared
# instance (instance-level custom roles are unique by name).
CUSTOM_ROLES = [
    {
        "name": _suffix("Promoter"),
        "description": "Triggers promotion pipelines; no write access",
        "base_role": "reporter",
        "abilities": [
            "admin_cicd_variables",
        ],
    },
    {
        "name": _suffix("Operator"),
        "description": "Manages prod env and release branches (scoped via protected env allow-lists)",
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
        "description": "Manages vulnerability waivers and approves security-sensitive MRs",
        "base_role": "reporter",
        "abilities": [
            "read_vulnerability",
            "admin_vulnerability",
            "admin_merge_request",
        ],
    },
]

# ---------------------------------------------------------------------------
# Approach 1 (Hybrid) — sharing plan
# ---------------------------------------------------------------------------
APPROACH_1_SHARES = [
    # Share SSCAM project-level groups with domain-a/proj-1
    {
        "target": "live-production/domain-a/proj-1",
        "shared_group": "iam-sim/sscam/domain-a-proj-1_w",
        "role": "developer",
    },
    {
        "target": "live-production/domain-a/proj-1",
        "shared_group": "iam-sim/sscam/domain-a-proj-1_r",
        "role": "reporter",
    },
    # Optional product-level share
    {
        "target": "live-production/domain-a",
        "shared_group": "iam-sim/sailpoint/gl-domain-a-dev",
        "role": "developer",
    },
    # Restricted reader
    {
        "target": "live-production/domain-a/restricted",
        "shared_group": "iam-sim/sailpoint/gl-restricted-read",
        "role": "reporter",
    },
    # Maintainer group on domain-a domain
    {
        "target": "live-production/domain-a",
        "shared_group": "iam-sim/p2p/IAM_DevOps_domain-a_Maintainer",
        "role": "maintainer",
    },
]

# ---------------------------------------------------------------------------
# Approach 2 (Target) — sharing plan
# ---------------------------------------------------------------------------
APPROACH_2_SHARES = [
    {"target": "live-production/domain-b", "shared_group": "iam-sim/sailpoint/gl-domain-b-read",  "role": "reporter"},
    {"target": "live-production/domain-b", "shared_group": "iam-sim/sailpoint/gl-domain-b-dev",   "role": "developer"},
    {"target": "live-production/domain-b", "shared_group": "iam-sim/sailpoint/gl-domain-b-maint", "role": "maintainer"},
    {"target": "live-production/domain-b", "shared_group": "iam-sim/sailpoint/gl-domain-b-owner", "role": "owner"},
]

# ---------------------------------------------------------------------------
# Protection plan (Phase 7)
# ---------------------------------------------------------------------------
PROTECTION_PLAN = {
    "protected_branches": [
        {
            "project": "live-production/domain-a/proj-1",
            "name": "main",
            "push_access_level": 0,           # No one
            "merge_access_level": 40,         # Maintainer
            "code_owner_approval_required": True,
        },
        {
            "project": "live-production/domain-b/proj-1",
            "name": "main",
            "push_access_level": 0,
            "merge_access_level": 40,
            "code_owner_approval_required": True,
        },
    ],
    "protected_tags": [
        {"project": "live-production/domain-a/proj-1", "name": "v*", "create_access_level": 40},
        {"project": "live-production/domain-b/proj-1", "name": "v*", "create_access_level": 40},
    ],
    # Protected environments require the env to exist first — the script handles that.
    "protected_environments": [
        {
            "project": "live-production/domain-a/proj-1",
            "name": "staging",
            "deploy_access_levels": [{"access_level": 30}],   # Developer+
            "approval_rules": [],
        },
        {
            "project": "live-production/domain-a/proj-1",
            "name": "prod",
            # Deploy restricted to Carol only (user-specific); will be set by username lookup
            "deploy_access_users": [_U["carol"]],
            "approval_rules": [
                {"required_approvals": 1, "group_path": None, "username": _U["bob"]},
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Sample .gitlab-ci.yml for domain-a/proj-1 (Phase 7 bootstraps this)
# ---------------------------------------------------------------------------
SAMPLE_CI_YAML = """\
stages:
  - build
  - deploy

build:
  stage: build
  script:
    - echo "Building..."

deploy_staging:
  stage: deploy
  script:
    - echo "Deploying to staging"
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy_prod:
  stage: deploy
  script:
    - echo "Deploying to PROD"
    - echo "Token is ${PROD_DEPLOY_TOKEN:-empty}"
  environment:
    name: prod
  rules:
    - if: $CI_COMMIT_TAG
  when: manual

promote_to_staging:
  stage: deploy
  script:
    - echo "Promoting artifact"
  environment:
    name: staging
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

adhoc_task:
  stage: deploy
  script:
    - echo "ad-hoc"
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
"""

SAMPLE_CODEOWNERS = f"""\
*                @{TOP_GROUP}/iam-sim/p2p/IAM_DevOps_domain-a_Maintainer
/infra/          @{TOP_GROUP}/iam-sim/p2p/IAM_DevOps_domain-a_SecurityManager
/.gitlab-ci.yml  @{TOP_GROUP}/iam-sim/p2p/IAM_DevOps_domain-a_Maintainer
"""

# ---------------------------------------------------------------------------
# Zone-level variables (Phase 11)
# ---------------------------------------------------------------------------
ZONE_VARIABLES = [
    {
        "group": "live-production",
        "key": "PROD_DEPLOY_TOKEN",
        "value": "zone-secret-value-live-prod",
        "protected": True,
        "masked": True,
        "environment_scope": "prod",
    },
]
