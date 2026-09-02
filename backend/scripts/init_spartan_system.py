#!/usr/bin/env python
import logging
"""Master Initialization Script for Spartan System

Runs all initialization steps in correct order:
1. Organizational Hierarchy (from existing users/roles)
2. System Decision Policies
3. Policy verification

Usage:
  python backend/scripts/init_spartan_system.py

This must be run AFTER:
  - Database is created and migrated
  - Users are created with roles assigned
  - BusinessUnits exist
"""

import sys
import subprocess
from pathlib import Path

# Get script directory
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent

def run_script(script_name: str, description: str) -> bool:
    """Run an initialization script"""
    script_path = SCRIPT_DIR / script_name

    print(f"\n{'=' * 70}")
    print(f"STEP: {description}")
    print(f"{'=' * 70}")
    print(f"Running: {script_path}\n")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(BACKEND_DIR),
            check=True,
            capture_output=False,
        )
        print(f"\n✓ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {description} - FAILED")
        print(f"Exit code: {e.returncode}")
        return False
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"\n✗ {description} - ERROR: {e}")
        return False


def main():
    """Run all initialization steps"""
    print("\n" + "=" * 70)
    print("SPARTAN AUTONOMOUS ORGANISM - SYSTEM INITIALIZATION")
    print("=" * 70)

    steps = [
        ("init_org_hierarchy.py", "1. Organizational Hierarchy Initialization"),
        ("init_policies.py", "2. System Decision Policies Initialization"),
    ]

    results = []
    for script, description in steps:
        success = run_script(script, description)
        results.append((description, success))

    # Summary
    print("\n" + "=" * 70)
    print("INITIALIZATION SUMMARY")
    print("=" * 70)

    all_success = True
    for description, success in results:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{status} - {description}")
        if not success:
            all_success = False

    print("=" * 70)

    if all_success:
        print("\n✓ ALL INITIALIZATION STEPS COMPLETED SUCCESSFULLY")
        print("\nSpartan System is now ready to operate:")
        print("  • Organization hierarchy established")
        print("  • Decision policies enforced")
        print("  • Escalation chains active")
        print("  • Forecasting system enabled")
        print("\nYou can now:")
        print("  1. Start the backend: uvicorn app.main:app --reload --port 8080")
        print("  2. Access MessageQueueDashboard → Autonomous Forecasting tab")
        print("  3. Create task scenarios to test escalations")
        print("\n")
        return 0
    else:
        print("\n✗ SOME INITIALIZATION STEPS FAILED")
        print("\nFix the errors above and re-run this script.")
        print("\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
