"""
HR Assignments API
==================
Routes (prefix: /hr-assignments, tag: hr-assignments):

  POST   /hr-assignments/                          â€” Create a new HR assignment
  GET    /hr-assignments/my-candidates             â€” Get candidates assigned to the calling HR/Recruiter
  GET    /hr-assignments/by-candidate/{candidate_id} â€” Get HR assignment for a specific candidate
  PATCH  /hr-assignments/by-candidate/{candidate_id} â€” Update HR assignment for a candidate
  DELETE /hr-assignments/by-candidate/{candidate_id} â€” Delete HR assignment for a candidate
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, get_current_user, require_resource_permission
from app.models.candidate import Candidate
from app.models.hr_assignment import HRAssignment
from app.models.user import Users
from app.schemas.hr_assignment import (
    HRAssignmentCreate,
    HRAssignmentUpdate,
    HRAssignmentResponse,
    HRAssignmentListResponse,
    UserSummary,
)


router = APIRouter(prefix="/hr-assignments", tags=["hr-assignments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate_name(c: Candidate) -> Optional[str]:
    """Return space-joined full name or None."""
    parts = [c.candidateFirstName, c.candidateMiddleName, c.candidateLastName]
    return " ".join(p for p in parts if p) or None


def _user_summary(u: Optional[Users]) -> Optional[UserSummary]:
    """Build a lightweight UserSummary from a Users ORM object."""
    if u is None:
        return None
    return UserSummary(
        user_id=u.UserID,
        user_name=u.UserName,
        user_email=u.UserEmail,
    )


def _to_response(row: HRAssignment, db: Session) -> HRAssignmentResponse:
    """Convert an HRAssignment ORM row into the full response shape."""
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == row.candidate_id
    ).first()

    hr1 = db.query(Users).filter(Users.UserID == row.hr1_id).first() if row.hr1_id else None
    hr2 = db.query(Users).filter(Users.UserID == row.hr2_id).first() if row.hr2_id else None
    assigner = db.query(Users).filter(Users.UserID == row.assigned_by).first() if row.assigned_by else None

    return HRAssignmentResponse(
        id=row.id,
        candidate_id=row.candidate_id,
        candidate_name=_candidate_name(candidate) if candidate else None,
        candidate_email=candidate.candidateEmail if candidate else None,
        hr1=_user_summary(hr1),
        hr2=_user_summary(hr2),
        assigned_by=_user_summary(assigner),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ---------------------------------------------------------------------------
# POST /hr-assignments/  â€” Create HR assignment
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=HRAssignmentResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Create a new HR assignment for a candidate",
)
def create_hr_assignment(
    body: HRAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Assign one or two HR / Recruiter users to a candidate for the recruitment process.

    - **hr1_id** (required): Primary HR / Recruiter
    - **hr2_id** (optional): Secondary HR / Recruiter

    Only one active assignment per candidate is allowed. Use the PATCH endpoint to
    update an existing assignment.

    **Required permission:** `candidate.edit`
    """
    # Validate candidate exists
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == body.candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{body.candidate_id}' not found.")

    # Prevent duplicate assignments
    existing = db.query(HRAssignment).filter(
        HRAssignment.candidate_id == body.candidate_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"An HR assignment already exists for candidate '{body.candidate_id}'. "
                "Use PATCH /hr-assignments/by-candidate/{candidate_id} to update it."
            ),
        )

    # Validate hr1 user
    hr1 = db.query(Users).filter(Users.UserID == body.hr1_id).first()
    if not hr1:
        raise HTTPException(status_code=404, detail=f"HR user '{body.hr1_id}' not found.")

    # Validate optional hr2 user
    if body.hr2_id:
        hr2 = db.query(Users).filter(Users.UserID == body.hr2_id).first()
        if not hr2:
            raise HTTPException(status_code=404, detail=f"HR user '{body.hr2_id}' not found.")

    assignment = HRAssignment(
        candidate_id=body.candidate_id,
        hr1_id=body.hr1_id,
        hr2_id=body.hr2_id,
        assigned_by=current_user.UserID,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return _to_response(assignment, db)


# ---------------------------------------------------------------------------
# GET /hr-assignments/candidates  â€” Get all candidates (for dashboard/admin)
# ---------------------------------------------------------------------------

@router.get(
    "/candidates",
    response_model=HRAssignmentListResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get all candidates (for dashboard display)",
)
def get_all_candidates(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Returns all candidates in the system with their HR assignments.
    Used for dashboard displays and admin views that show all candidates.

    **Required permission:** `candidate.view`
    """
    query = db.query(HRAssignment)
    total = query.count()
    rows = query.order_by(HRAssignment.created_at.desc()).offset(skip).limit(limit).all()

    return HRAssignmentListResponse(
        total=total,
        assignments=[_to_response(r, db) for r in rows],
    )


# ---------------------------------------------------------------------------
# GET /hr-assignments/my-candidates  â€” Get my assigned candidates (as HR)
# ---------------------------------------------------------------------------

@router.get(
    "/my-candidates",
    response_model=HRAssignmentListResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get all candidates assigned to me (as HR / Recruiter)",
)
def get_my_candidates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Returns all candidates where the calling user is either **hr1** or **hr2**.

    Useful for an HR/Recruiter to see their own workload / candidate queue.

    **Required permission:** `candidate.view`
    """
    query = db.query(HRAssignment).filter(
        (HRAssignment.hr1_id == current_user.UserID)
        | (HRAssignment.hr2_id == current_user.UserID)
    )

    total = query.count()
    rows = query.order_by(HRAssignment.created_at.desc()).offset(skip).limit(limit).all()

    return HRAssignmentListResponse(
        total=total,
        assignments=[_to_response(r, db) for r in rows],
    )


# ---------------------------------------------------------------------------
# GET /hr-assignments/by-candidate/{candidate_id}  â€” Get HR by candidate ID
# ---------------------------------------------------------------------------

@router.get(
    "/by-candidate/{candidate_id}",
    response_model=HRAssignmentResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get HR assignment for a specific candidate",
)
def get_hr_by_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Returns the HR/Recruiter assignment details for the given candidate.

    **Required permission:** `candidate.view`
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    assignment = db.query(HRAssignment).filter(
        HRAssignment.candidate_id == candidate_id
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail=f"No HR assignment found for candidate '{candidate_id}'.",
        )

    return _to_response(assignment, db)


# ---------------------------------------------------------------------------
# PATCH /hr-assignments/by-candidate/{candidate_id}  â€” Update HR assignment
# ---------------------------------------------------------------------------

@router.patch(
    "/by-candidate/{candidate_id}",
    response_model=HRAssignmentResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Update HR assignment for a candidate",
)
def update_hr_assignment(
    candidate_id: str,
    body: HRAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Update the HR1 and/or HR2 assigned to a candidate.

    - Provide **hr1_id** to change the primary HR/Recruiter.
    - Provide **hr2_id** to change the secondary HR/Recruiter.
    - Set **clear_hr2 = true** to explicitly remove the secondary HR (sets hr2 to null).

    **Required permission:** `candidate.edit`
    """
    assignment = db.query(HRAssignment).filter(
        HRAssignment.candidate_id == candidate_id
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail=f"No HR assignment found for candidate '{candidate_id}'. Use POST to create one.",
        )

    # Update hr1 if provided
    if body.hr1_id is not None:
        hr1 = db.query(Users).filter(Users.UserID == body.hr1_id).first()
        if not hr1:
            raise HTTPException(status_code=404, detail=f"HR user '{body.hr1_id}' not found.")
        assignment.hr1_id = body.hr1_id

    # Update hr2 if provided, or clear if requested
    if body.clear_hr2:
        assignment.hr2_id = None
    elif body.hr2_id is not None:
        hr2 = db.query(Users).filter(Users.UserID == body.hr2_id).first()
        if not hr2:
            raise HTTPException(status_code=404, detail=f"HR user '{body.hr2_id}' not found.")
        assignment.hr2_id = body.hr2_id

    # Track who last modified the assignment
    assignment.assigned_by = current_user.UserID

    db.commit()
    db.refresh(assignment)

    return _to_response(assignment, db)


# ---------------------------------------------------------------------------
# DELETE /hr-assignments/by-candidate/{candidate_id}  â€” Delete HR assignment
# ---------------------------------------------------------------------------

@router.delete(
    "/by-candidate/{candidate_id}",
    status_code=200,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Delete HR assignment for a candidate",
)
def delete_hr_assignment(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Permanently removes the HR/Recruiter assignment for a candidate.

    **Required permission:** `candidate.edit`
    """
    assignment = db.query(HRAssignment).filter(
        HRAssignment.candidate_id == candidate_id
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail=f"No HR assignment found for candidate '{candidate_id}'.",
        )

    db.delete(assignment)
    db.commit()

    return {
        "message": f"HR assignment for candidate '{candidate_id}' has been deleted.",
        "candidate_id": candidate_id,
    }
