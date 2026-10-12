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
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.activity_timeline import (
    FileAccessUrlResponse, FileUploadOut, TimelineResponse, WriteTimelineEntryRequest,
)
from app.services.activity_timeline_service import get_timeline_for_entity, write_timeline_entry
from app.services.file_upload_service import get_file_access_url, list_files_for_entity, upload_file

router = APIRouter(tags=["activity-timeline"])


def _ensure_entity_visible(db: Session, user: Users, entity_type: str, entity_id: str) -> None:
    """The timeline and files of a record are as visible as the record itself (CEO 2026-10-12:
    the business unit decides which records a user sees -- app.core.data_scope). A record of a
    business unit outside the caller's scope is 404, the same answer as one that does not exist.
    Entity types with no business unit (a user, a role template, a config) are not narrowed."""
    from app.core import data_scope

    kind = (entity_type or "").lower()
    if kind == "client":
        data_scope.ensure_visible(db, user, data_scope.client_bu_id(db, entity_id), "Client")
    elif kind in ("job", "demand"):
        data_scope.ensure_visible(db, user, data_scope.job_bu_id(db, entity_id), "Job")
    elif kind == "employee":
        from app.models.employee import Employee

        row = db.query(Employee.bu_id).filter(Employee.id == entity_id).first()
        data_scope.ensure_visible(db, user, row[0] if row else None, "Employee")
    elif kind in ("opportunity", "project", "invoice"):
        from app.models.invoice import Invoice
        from app.models.opportunity import Opportunity
        from app.models.project import Project

        model = {"opportunity": Opportunity, "project": Project, "invoice": Invoice}[kind]
        row = db.query(model.client_id).filter(model.id == entity_id).first()
        data_scope.ensure_visible(db, user, data_scope.client_bu_id(db, row[0]) if row else None, kind.title())
    elif kind in ("employee_allocation", "allocation"):
        from app.models.employee_allocation import EmployeeAllocation

        exists = db.query(EmployeeAllocation.id).filter(EmployeeAllocation.id == entity_id)
        if exists.first() and not exists.filter(data_scope.allocation_filter(db, user)).first():
            raise HTTPException(status_code=404, detail="Allocation not found")
    elif kind == "timesheet":
        from app.models.timesheet import Timesheet

        exists = db.query(Timesheet.id).filter(Timesheet.id == entity_id)
        if exists.first() and not exists.filter(data_scope.timesheet_filter(db, user)).first():
            raise HTTPException(status_code=404, detail="Timesheet not found")
    elif kind == "candidate":
        from app.core.bu_scope import get_candidate_by_id_with_bu_scope
        from app.models.candidate import Candidate

        exists = db.query(Candidate.candidateID).filter(Candidate.candidateID == entity_id).first()
        if exists and get_candidate_by_id_with_bu_scope(db, entity_id, user) is None:
            raise HTTPException(status_code=404, detail="Candidate not found")

@router.get(
    "/activity-timeline/{entity_type}/{entity_id}",
    response_model=TimelineResponse,
    dependencies=[Depends(require_resource_permission("activity-feed", "view"))]
)
async def get_timeline(
    entity_type: str, entity_id: str, page: int = 1, per_page: int = 25,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    _ensure_entity_visible(db, current_user, entity_type, entity_id)
    return get_timeline_for_entity(
        db, entity_type, entity_id, tenant_id=current_user.tenant_id, page=page, per_page=per_page,
    )

@router.post(
    "/activity-timeline/{entity_type}/{entity_id}",
    response_model=TimelineResponse,
    dependencies=[Depends(require_resource_permission("activity-feed", "create"))]
)
def post_timeline_entry(
    entity_type: str, entity_id: str, body: WriteTimelineEntryRequest,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    _ensure_entity_visible(db, current_user, entity_type, entity_id)
    try:
        write_timeline_entry(
            db, tenant_id=current_user.tenant_id, entity_type=entity_type, entity_id=entity_id,
            actor_id=current_user.UserID, actor_type="USER", action=body.action, description=body.description,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to write timeline entry: {str(e)}")
    return get_timeline_for_entity(db, entity_type, entity_id, tenant_id=current_user.tenant_id)

@router.post(
    "/file-uploads/{entity_type}/{entity_id}",
    response_model=FileUploadOut,
    dependencies=[Depends(require_resource_permission("candidates", "create"))]
)
def post_file_upload(
    entity_type: str, entity_id: str,
    file_category: str = "GENERIC",
    file: UploadFile = File(...),
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    _ensure_entity_visible(db, current_user, entity_type, entity_id)
    try:
        content = file.file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty.")
        row = upload_file(
            db, tenant_id=current_user.tenant_id, entity_type=entity_type, entity_id=entity_id,
            file_content=content, original_filename=file.filename or "upload",
            file_category=file_category, uploaded_by=current_user.UserID,
        )
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
    return FileUploadOut(
        id=row.id, entity_type=row.entity_type, entity_id=row.entity_id, file_category=row.file_category,
        original_filename=row.original_filename, file_size=row.file_size, scan_status=row.scan_status,
        uploaded_by=row.uploaded_by, created_at=row.created_at.isoformat() if row.created_at else None,
    )

@router.get(
    "/file-uploads/{file_id}/access-url",
    response_model=FileAccessUrlResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))]
)
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
    from app.models.file_upload import FileUpload

    upload = db.query(FileUpload).filter(FileUpload.id == file_id).first()
    if upload is not None:
        if upload.tenant_id is not None and upload.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=404, detail="File not found")
        _ensure_entity_visible(db, current_user, upload.entity_type, upload.entity_id)
    return FileAccessUrlResponse(access_url=get_file_access_url(db, file_id))

@router.get(
    "/file-uploads/{entity_type}/{entity_id}",
    response_model=list[FileUploadOut],
    dependencies=[Depends(require_resource_permission("candidates", "view"))]
)
def get_files_for_entity(
    entity_type: str, entity_id: str,
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    _ensure_entity_visible(db, current_user, entity_type, entity_id)
    rows = list_files_for_entity(db, entity_type, entity_id, tenant_id=current_user.tenant_id)
    return [
        FileUploadOut(
            id=r.id, entity_type=r.entity_type, entity_id=r.entity_id, file_category=r.file_category,
            original_filename=r.original_filename, file_size=r.file_size, scan_status=r.scan_status,
            uploaded_by=r.uploaded_by, created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
