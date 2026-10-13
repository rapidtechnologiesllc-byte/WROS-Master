"""Every resource named in a seeded role's permissions must exist in the
resource catalogue; otherwise initialize_database() raises at startup and
the backend never comes up (regression: 'linkedin-pipeline', an extra page
governed by 'candidates', was listed as a resource for Partner and BU Head)."""
from app.contracts import MODULES_AND_RESOURCES
from app.core.db_contract import LEADERSHIP_ROLES


def test_every_leadership_role_resource_is_in_the_catalogue():
    catalogue = {name for names in MODULES_AND_RESOURCES.values() for name in names}
    unknown = {
        (role, resource)
        for role, spec in LEADERSHIP_ROLES.items()
        for names in spec["permissions"].values()
        for resource in names
        if resource not in catalogue
    }
    assert not unknown, f"Role permissions reference resources that are never seeded: {sorted(unknown)}"
