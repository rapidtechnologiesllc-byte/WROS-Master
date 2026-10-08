"""
Demo Data Seeding - Creates Partners, BU Heads, BUs, Clients, Projects, Jobs, and Goals

Run ONCE per environment to set up demo data for end-to-end testing.
Idempotent: Safe to run multiple times (checks for duplicates).

Usage:
    db = SessionLocal()
    seed_demo_data(db)  # Creates all demo data
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def seed_demo_data(db: Session) -> dict:
    """
    Create demo data for testing: Partners, BU Heads, BUs, Clients, Projects, Jobs, Goals.
    Returns: {"status": "success", "created": {...}}
    """
    from app.models.business_unit import BusinessUnit
    from app.models.user import Users
    from app.models.org_chart import OrgChart
    from app.models.client import Client
    from app.models.job import Job
    from app.models.project import Project
    from app.models.goal_target import GoalTarget
    from app.models.tenant import Tenant
    from app.services.email_service import EmailService

    created = {
        "partners": 0,
        "bu_heads": 0,
        "business_units": 0,
        "clients": 0,
        "projects": 0,
        "jobs": 0,
        "goals": 0,
    }

    try:
        # Get/Create tenant
        tenant = db.query(Tenant).filter(Tenant.tenant_name == "BlitzenX").first()
        if not tenant:
            tenant = Tenant(tenant_name="BlitzenX", is_active=True)
            db.add(tenant)
            db.flush()

        tenant_id = tenant.id if hasattr(tenant, 'id') else 1

        # 1. Create Partners (org chart nodes at Partner level)
        logger.info("Creating Partners...")
        troy_partner = db.query(OrgChart).filter(
            OrgChart.node_name == "Troy Partner",
            OrgChart.node_type == "Partner/C-Level"
        ).first()

        if not troy_partner:
            troy_partner = OrgChart(
                node_name="Troy Partner",
                node_type="Partner/C-Level",
                description="Demo partner for testing",
                tenant_id=tenant_id,
                created_at=datetime.utcnow(),
            )
            db.add(troy_partner)
            db.flush()
            created["partners"] += 1
            logger.info(f"Created Partner: Troy Partner")

        # 2. Create BU Heads (users with BU Head role)
        logger.info("Creating BU Heads...")
        bu_head_user = db.query(Users).filter(Users.UserEmail == "bu-head@blitzenx.com").first()

        if not bu_head_user:
            bu_head_user = Users(
                UserEmail="bu-head@blitzenx.com",
                UserName="BU Head Demo",
                tenant_id=tenant_id,
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(bu_head_user)
            db.flush()
            created["bu_heads"] += 1
            logger.info("Created BU Head: bu-head@blitzenx.com")

        # 3. Create Business Units
        logger.info("Creating Business Units...")
        for bu_name in ["BU-Sales", "BU-Engineering", "BU-Operations"]:
            bu = db.query(BusinessUnit).filter(
                BusinessUnit.business_unit_name == bu_name,
                BusinessUnit.tenant_id == tenant_id
            ).first()

            if not bu:
                bu = BusinessUnit(
                    business_unit_name=bu_name,
                    description=f"Demo {bu_name} for testing",
                    manager_id=bu_head_user.UserID if bu_head_user else None,
                    tenant_id=tenant_id,
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                db.add(bu)
                db.flush()
                created["business_units"] += 1
                logger.info(f"Created Business Unit: {bu_name}")

        # 4. Create Clients
        logger.info("Creating Clients...")
        for client_name in ["Acme Corp", "Tech Innovations Ltd", "Global Services Inc"]:
            client = db.query(Client).filter(
                Client.client_name == client_name,
                Client.tenant_id == tenant_id
            ).first()

            if not client:
                client = Client(
                    client_name=client_name,
                    industry="Technology",
                    contract_value=100000,
                    tenant_id=tenant_id,
                    created_at=datetime.utcnow(),
                    is_active=True,
                )
                db.add(client)
                db.flush()
                created["clients"] += 1
                logger.info(f"Created Client: {client_name}")

        # 5. Create Projects
        logger.info("Creating Projects...")
        clients = db.query(Client).filter(Client.tenant_id == tenant_id).limit(3).all()

        for i, client in enumerate(clients):
            project = db.query(Project).filter(
                Project.project_name == f"Project-{client.client_name}",
                Project.tenant_id == tenant_id
            ).first()

            if not project:
                project = Project(
                    project_name=f"Project-{client.client_name}",
                    description=f"Demo project for {client.client_name}",
                    client_id=client.id if hasattr(client, 'id') else None,
                    budget=50000,
                    start_date=datetime.utcnow(),
                    end_date=datetime.utcnow() + timedelta(days=180),
                    tenant_id=tenant_id,
                    created_at=datetime.utcnow(),
                    is_active=True,
                )
                db.add(project)
                db.flush()
                created["projects"] += 1
                logger.info(f"Created Project: Project-{client.client_name}")

        # 6. Create Jobs
        logger.info("Creating Jobs...")
        projects = db.query(Project).filter(Project.tenant_id == tenant_id).limit(3).all()

        for project in projects:
            for role in ["Senior Engineer", "Product Manager", "Data Scientist"]:
                job = db.query(Job).filter(
                    Job.job_title == role,
                    Job.project_id == (project.id if hasattr(project, 'id') else None),
                    Job.tenant_id == tenant_id
                ).first()

                if not job:
                    job = Job(
                        job_title=role,
                        job_description=f"Demo {role} position for {project.project_name}",
                        project_id=project.id if hasattr(project, 'id') else None,
                        status="active",
                        bill_rate=150.00,
                        required_skills=role.lower(),
                        tenant_id=tenant_id,
                        created_at=datetime.utcnow(),
                        is_active=True,
                    )
                    db.add(job)
                    db.flush()
                    created["jobs"] += 1
                    logger.info(f"Created Job: {role} (Project: {project.project_name})")

        # 7. Create FY Goals
        logger.info("Creating FY Goals...")
        goal_configs = [
            {"entity_type": "organization", "entity_id": None, "revenue": 10000000, "headcount": 500},
            {"entity_type": "business_unit", "entity_id": None, "revenue": 3000000, "headcount": 150},
            {"entity_type": "location", "entity_id": None, "revenue": 5000000, "headcount": 250},
        ]

        for config in goal_configs:
            goal = db.query(GoalTarget).filter(
                GoalTarget.entity_type == config["entity_type"],
                GoalTarget.tenant_id == tenant_id
            ).first()

            if not goal:
                goal = GoalTarget(
                    entity_type=config["entity_type"],
                    entity_id=config["entity_id"],
                    metric_type="revenue",
                    target_value=config["revenue"],
                    actual_value=0,
                    fiscal_year=datetime.utcnow().year,
                    tenant_id=tenant_id,
                    created_at=datetime.utcnow(),
                )
                db.add(goal)
                db.flush()
                created["goals"] += 1

                # Also create headcount goal
                goal_hc = GoalTarget(
                    entity_type=config["entity_type"],
                    entity_id=config["entity_id"],
                    metric_type="headcount",
                    target_value=config["headcount"],
                    actual_value=0,
                    fiscal_year=datetime.utcnow().year,
                    tenant_id=tenant_id,
                    created_at=datetime.utcnow(),
                )
                db.add(goal_hc)
                db.flush()
                created["goals"] += 1
                logger.info(f"Created Goal: {config['entity_type']}")

        db.commit()
        logger.info(f"✅ Demo data created successfully: {created}")
        return {"status": "success", "created": created}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to seed demo data: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    from app.core.database import SessionLocal
    db = SessionLocal()
    result = seed_demo_data(db)
    print(result)
    db.close()
