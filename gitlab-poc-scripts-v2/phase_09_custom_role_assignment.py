#!/usr/bin/env python3
"""
Phase 9 (v2) — No-op.

In v2 the three custom roles (Promoter, Operator, Security Manager) are
bound to their org subgroups directly inside Phase 5 (org→app), via the
member_role_id parameter on the share call. There's no separate custom-role
assignment phase.

This file is kept so the orchestrator's phase list still finds a module
named `phase_09_custom_role_assignment`. It just prints a banner and exits.
"""
from gitlab_client import banner, done


def main():
    banner("PHASE 9 (v2) — No-op (custom roles bound in Phase 5)")
    done("v2 binds custom roles via member_role_id on the org→app share.")
    done("Next: run phase_10_inner_source.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
