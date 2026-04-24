#!/usr/bin/env python3
"""
Run all SETUP phases (1-7, 9, 11) in sequence — builds the PoC environment.

Skips test phases (8, 10, 12, 13, 14) which should be run individually after
the environment is in place, so you can pause and inspect.

Usage: python3 run_setup_all.py
"""
import subprocess
import sys

PHASES = [
    "phase_01_custom_roles.py",
    "phase_02_hierarchy.py",
    "phase_03_iam_groups.py",
    "phase_04_users.py",
    "phase_05_approach_1.py",
    "phase_06_approach_2.py",
    "phase_07_protection.py",
    "phase_09_custom_role_assignment.py",
    "phase_11_zone_policy.py",
]


def main():
    for script in PHASES:
        print(f"\n{'#' * 72}")
        print(f"#  Running {script}")
        print(f"{'#' * 72}\n")
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            print(f"\n✗ {script} failed with exit code {result.returncode}")
            print("  Stopping. Fix the issue and re-run this orchestrator or the individual phase.")
            return result.returncode
    print(f"\n{'#' * 72}")
    print(f"#  ALL SETUP PHASES COMPLETE")
    print(f"{'#' * 72}\n")
    print("Now run the test phases individually:")
    print("  - phase_08_tests.py    (API role enforcement tests, needs user tokens)")
    print("  - phase_10_inner_source.py (inner source tests)")
    print("  - phase_12_cicd_tests.py   (CI/CD scenarios)")
    print("  - phase_13_migration.py    (migration drill)")
    print("  - phase_14_report.py       (final report)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
