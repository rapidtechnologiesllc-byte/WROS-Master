"""
S-216/HRMS-0118 -- Shared Activity Timeline & File Attachment Framework.
==================================================================
Prefix: /activity-timeline, /file-uploads
Tags:   activity-timeline, file-uploads

GET  /activity-timeline/{entity_type}/{entity_id}   -- paginated feed, any entity
POST /activity-timeline/{entity_type}/{entity_id}   -- write a real entry
                                                        (system/AI-agent
                                                        callers should call
                                                        write_timeline_entry()
                                                        directly, this HTTP
                                                        path is for real
                                                        user-initiated notes)

POST /file-uploads/{entity_type}/{entity_id}         -- multipart upload
GET  /file-uploads/{entity_type}/{entity_id}         -- list files for an entity
GET  /file-uploads/{file_id}/access-url              -- BR-0118-02 gate:
                                                         null until scan_status=CLEAN
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.schemas.activity_timeline import (
    FileAccessUrlResponse, FileUploadOut, TimelineResponse, WriteTimelineEntryRequest,
)
from app.services.activity_timeline_service import get_timeline_for_entity, write_timeline_entry
from app.services.file_upload_service import get_file_access_url, list_files_for_entity, upload_file

router = APIRouter(tags=["activity-timeline"])


@router.get("/activity-timeline/{entity_type}/{entity_id}", response_model=TimelineResponse)
def get_timeline(
    entity_type: str, entity_id: str, page: int = 1, per_page: int = 25,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    return get_timeline_for_entity(
        db, entity_type, entity_id, tenant_id=current_user.tenant_id, page=page, per_page=per_page,
    )


@router.post("/activity-timeline/{entity_type}/{entity_id}", response_model=TimelineResponse)
def post_timeline_entry(
    entity_type: str, entity_id: str, body: WriteTimelineEntryRequest,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    write_timeline_entry(
        db, tenant_id=current_user.tenant_id, entity_type=entity_type, entity_id=entity_id,
        actor_id=current_user.UserID, actor_type="USER", action=body.action, description=body.description,
    )
    db.commit()
    return get_timeline_for_entity(db, entity_type, entity_id, tenant_id=current_user.tenant_id)


@router.post("/file-uploads/{entity_type}/{entity_id}", response_model=FileUploadOut)
def post_file_upload(
    entity_type: str, entity_id: str,
    file_category: str = "GENERIC",
    file: UploadFile = File(...),
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty.")
    row = upload_file(
        db, tenant_id=current_user.tenant_id, entity_type=entity_type, entity_id=entity_id,
        file_content=content, original_filename=file.filename or "upload",
        file_category=file_category, uploaded_by=current_user.UserID,
    )
    db.commit()
    return FileUploadOut(
        id=row.id, entity_type=row.entity_type, entity_id=row.entity_id, file_category=row.file_category,
        original_filename=row.original_filename, file_size=row.file_size, scan_status=row.scan_status,
        uploaded_by=row.uploaded_by, created_at=row.created_at.isoformat() if row.created_at else None,
    )


@router.get("/file-uploads/{file_id}/access-url", response_model=FileAccessUrlResponse)
def get_access_url(
    file_id: int,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    # Registered BEFORE the /{entity_type}/{entity_id} route below --
    # FastAPI/Starlette matches path routes in registration order, not
    # by specificity, so a literal segment like "access-url" must be
    # declared first or it gets silently swallowed as an entity_id by
    # the more generic route.
    return FileAccessUrlResponse(access_url=get_file_access_url(db, file_id))


@router.get("/file-uploads/{entity_type}/{entity_id}", response_model=list[FileUploadOut])
def get_files_for_entity(
    entity_type: str, entity_id: str,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    rows = list_files_for_entity(db, entity_type, entity_id, tenant_id=current_user.tenant_id)
    return [
        FileUploadOut(
            id=r.id, entity_type=r.entity_type, entity_id=r.entity_id, file_category=r.file_category,
            original_filename=r.original_filename, file_size=r.file_size, scan_status=r.scan_status,
            uploaded_by=r.uploaded_by, created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
