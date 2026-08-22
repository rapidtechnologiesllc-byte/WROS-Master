#!/usr/bin/env python3
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal
from app.models.career import CareerJob
import uuid

jobs_data = [
    {
        "title": "Business Delivery Consultant",
        "description": "Lead customer implementations and drive business outcomes. We're looking for an experienced consultant to manage complex customer engagements.",
        "skills_required": [
            {"skill": "Project Management", "years_required": 3, "level": "advanced"},
            {"skill": "Client Relations", "years_required": 3, "level": "advanced"},
            {"skill": "Business Analysis", "years_required": 2, "level": "intermediate"}
        ],
        "experience_years_required": 5,
        "location": "San Francisco, CA",
        "salary_range_min_usd_cents": 8000000,
        "salary_range_max_usd_cents": 12000000,
    },
    {
        "title": "Senior Software Engineer",
        "description": "Build and scale our platform. Mentor junior engineers and contribute to architectural decisions.",
        "skills_required": [
            {"skill": "Python", "years_required": 5, "level": "advanced"},
            {"skill": "System Design", "years_required": 3, "level": "advanced"},
            {"skill": "PostgreSQL", "years_required": 3, "level": "intermediate"}
        ],
        "experience_years_required": 7,
        "location": "Remote",
        "salary_range_min_usd_cents": 12000000,
        "salary_range_max_usd_cents": 18000000,
    },
    {
        "title": "Product Manager",
        "description": "Define product strategy and roadmap. Work with engineering and design to build amazing products.",
        "skills_required": [
            {"skill": "Product Strategy", "years_required": 3, "level": "advanced"},
            {"skill": "Data Analysis", "years_required": 2, "level": "intermediate"},
            {"skill": "Stakeholder Management", "years_required": 3, "level": "advanced"}
        ],
        "experience_years_required": 4,
        "location": "San Francisco, CA",
        "salary_range_min_usd_cents": 9000000,
        "salary_range_max_usd_cents": 14000000,
    },
]

try:
    db = SessionLocal()

    for job_data in jobs_data:
        job = CareerJob(
            id=str(uuid.uuid4()),
            **job_data,
            is_published=True,
            is_active=True,
            tenant_id=1
        )
        db.add(job)

    db.commit()
    print(f"Successfully seeded {len(jobs_data)} jobs")
    db.close()
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
