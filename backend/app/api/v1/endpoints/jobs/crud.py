"""Jobs CRUD operations"""
from typing import List
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role_template_permission
from app.models.jobs import Job

router = APIRouter()

@router.get("/all", dependencies=[Depends(require_role_template_permission("jobs", "can_view"))])
def get_all_jobs(db: Session = Depends(get_db)):
    """Get all jobs"""
    try:
        jobs = db.query(Job).filter(Job.tenant_id == 1).all()
        return {
            "total_jobs": len(jobs),
            "jobs": [
                {
                    "id": j.id,
                    "title": j.title,
                    "description": j.description,
                    "status": j.status,
                } for j in jobs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
