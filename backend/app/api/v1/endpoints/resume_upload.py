"""CYCLE 11: Resume Upload and Storage Service"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from typing import Dict
import os

router = APIRouter(prefix="/resume", tags=["Resume"])


@router.post("/upload/{candidate_id}", response_model=Dict)
async def upload_resume(
    candidate_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """Upload resume file for candidate"""
    try:
        if not file.filename.endswith(('.pdf', '.docx', '.doc')):
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files allowed")

        # Save file
        file_path = f"/storage/resumes/{candidate_id}/{file.filename}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "status": "uploaded",
            "file_path": file_path,
            "file_size": len(content),
            "candidate_id": candidate_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{candidate_id}", response_model=Dict)
def download_resume(
    candidate_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """Get candidate's resume"""
    return {"status": "success", "candidate_id": candidate_id}
