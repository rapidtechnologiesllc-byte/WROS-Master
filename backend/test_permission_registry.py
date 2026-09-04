#!/usr/bin/env python
"""
Test permission registry for completeness.
Verifies all resources, actions, and constants are properly defined.
"""

from app.core.permission_registry import RESOURCES, Permissions, validate_resource, validate_permission, get_all_permissions

def test_all_resources_defined():
    """Verify all RESOURCES have required fields."""
    required_fields = {'display_name', 'module', 'actions', 'description'}

    for resource_name, config in RESOURCES.items():
        assert required_fields.issubset(config.keys()), f"Resource '{resource_name}' missing fields"
        assert len(config['actions']) > 0, f"Resource '{resource_name}' has no actions"
        print(f"[OK] {resource_name}: {len(config['actions'])} actions")

    print(f"\n[OK] Total Resources: {len(RESOURCES)}")

def test_all_permissions_constants():
    """Verify Permissions class constants."""
    expected_count = 0
    for resource_name, config in RESOURCES.items():
        expected_count += len(config['actions'])

    # Get all constants from Permissions class
    constants = [attr for attr in dir(Permissions) if not attr.startswith('_')]

    print(f"\n[OK] Permissions Constants: {len(constants)}")
    print(f"[OK] Expected (resources × actions): {expected_count}")

    # Sample some constants
    assert Permissions.CANDIDATES_VIEW == ("candidates", "can_view")
    assert Permissions.JOBS_CREATE == ("jobs", "can_create")
    assert Permissions.AGENTS_VIEW == ("agents", "can_view")
    assert Permissions.DASHBOARDS_EDIT == ("dashboards", "can_edit")
    print("\n[OK] Sample permission constants verified")

def test_validation_functions():
    """Test validation functions."""
    # Test resource validation
    assert validate_resource("candidates") == True
    assert validate_resource("invalid_resource") == False

    # Test permission validation
    assert validate_permission("candidates", "can_view") == True
    assert validate_permission("candidates", "invalid_action") == False
    assert validate_permission("invalid_resource", "can_view") == False

    print("\n[OK] Validation functions working")

def test_all_permissions():
    """Test get_all_permissions function."""
    all_perms = get_all_permissions()
    assert len(all_perms) > 0
    print(f"\n[OK] get_all_permissions() returned {len(all_perms)} permissions")

    # Verify all returned permissions are valid
    for resource, action in all_perms:
        assert validate_permission(resource, action), f"Invalid permission: ({resource}, {action})"

def main():
    print("=" * 60)
    print("PERMISSION REGISTRY VALIDATION TEST")
    print("=" * 60)

    try:
        test_all_resources_defined()
        test_all_permissions_constants()
        test_validation_functions()
        test_all_permissions()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
