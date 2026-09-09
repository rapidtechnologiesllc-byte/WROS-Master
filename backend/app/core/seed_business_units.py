"""Seed default business units and clients for testing"""
from sqlalchemy.orm import Session
from sqlalchemy import text


def seed_business_units(db: Session):
    """Create default business unit if it doesn't exist"""
    try:
        # Check if any business units exist
        result = db.execute(text("SELECT COUNT(*) as count FROM business_units")).fetchone()
        if result and result[0] > 0:
            return  # Already seeded

        # Create default business unit
        db.execute(
            text("""
                INSERT INTO business_units (name, region, continent, created_at)
                VALUES ('Technology Solutions', 'North America', 'North America', NOW())
            """)
        )
        db.commit()
        return {"seeded": True, "message": "Business units seeded successfully"}
    except Exception as e:
        db.rollback()
        return {"seeded": False, "error": str(e)}
