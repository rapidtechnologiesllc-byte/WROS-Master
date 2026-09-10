"""Seed default business units and clients for testing"""
from sqlalchemy.orm import Session
from app.models.business_unit import BusinessUnit


def seed_business_units(db: Session):
    """Create default business units if none exist"""
    try:
        # Check if any business units exist
        existing_count = db.query(BusinessUnit).filter(BusinessUnit.active == True).count()
        if existing_count > 0:
            return {"seeded": False, "message": "Business units already exist"}

        # Create default business units for multi-region support
        default_bus = [
            BusinessUnit(
                name="North America",
                display_name="North America (NA)",
                bu_code="NA",
                description="North American operations",
                active=True
            ),
            BusinessUnit(
                name="Europe",
                display_name="Europe (EU)",
                bu_code="EU",
                description="European operations",
                active=True
            ),
            BusinessUnit(
                name="Asia Pacific",
                display_name="Asia Pacific (APAC)",
                bu_code="APAC",
                description="Asia-Pacific operations",
                active=True
            ),
            BusinessUnit(
                name="India",
                display_name="India (IN)",
                bu_code="IN",
                description="India operations",
                active=True
            ),
        ]

        for bu in default_bus:
            db.add(bu)

        db.commit()
        return {"seeded": True, "message": f"Business units seeded successfully ({len(default_bus)} BUs created)"}
    except Exception as e:
        db.rollback()
        return {"seeded": False, "error": str(e)}
