# crud.py
from sqlalchemy.orm import Session
from model import Users, Candidates, CandidateForm
from schema import UserCreate
from passlib.context import CryptContext
from typing import Optional
from sqlalchemy import desc

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user_by_email(db: Session, email: str) -> Optional[Users]:
    return db.query(Users).filter(Users.UserEmail == email).first()

def generate_candidate_id(db: Session) -> str:
    last = db.query(Candidates).order_by(desc(Candidates.CandidateID)).first()
    if not last:
        return "CAND-001"
    try:
        last_num = int(last.CandidateID.split("-")[1])
    except Exception:
        # Fallback if CandidateID format differs
        last_num = 0
    new_num = last_num + 1
    return f"CAND-{new_num:03d}"

def create_user(db: Session, user_in: UserCreate) -> Users:
    hashed = get_password_hash(user_in.UserPassword)
    db_user = Users(
        UserRole=user_in.UserRole,
        UserName=user_in.UserName,
        UserEmail=user_in.UserEmail,
        UserPassword=hashed
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    if user_in.UserRole.lower() == "candidate":
        cand_id = generate_candidate_id(db)
        candidate = Candidates(
            CandidateID=cand_id,
            UserID=db_user.UserID,
            UserRole=db_user.UserRole,
            UserName=db_user.UserName,
            UserEmail=db_user.UserEmail,
            UserPassword=db_user.UserPassword,
            CreatedAt=db_user.CreatedAt
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

    return db_user

def authenticate_user(db: Session, email: str, password: str, role: str):
    user = get_user_by_email(db, email)
    if not user:
        return {"status": False, "reason": "not_found"}
    if user.UserRole != role:
        return {"status": False, "reason": "role_mismatch", "user_role": user.UserRole}
    if not verify_password(password, user.UserPassword):
        return {"status": False, "reason": "invalid_password"}
    return {"status": True, "user": user}

# CandidateForm CRUD
def get_candidate_by_userid(db: Session, user_id: int) -> Optional[Candidates]:
    return db.query(Candidates).filter(Candidates.UserID == user_id).first()

def create_or_update_candidate_form(db: Session, user_id: int, form_in) -> CandidateForm:
    """
    Looks up Candidate by user_id.
    If a form already exists, updates it. Otherwise, creates new.
    """
    candidate = get_candidate_by_userid(db, user_id)
    if not candidate:
        raise ValueError("No candidate found for the given user")

    existing_form = db.query(CandidateForm).filter(CandidateForm.CandidateID == candidate.CandidateID).first()

    if existing_form:
        # Update existing form
        existing_form.JoiningDate = form_in.JoiningDate
        existing_form.Position = form_in.Position
        existing_form.Department = form_in.Department
        existing_form.DOB = form_in.DOB
        existing_form.Aadhar = form_in.Aadhar
        existing_form.PAN = form_in.PAN
        existing_form.Address = form_in.Address
        existing_form.SubmittedAt = form_in.SubmittedAt
        db.commit()
        db.refresh(existing_form)
        return existing_form
    else:
        # Create new form
        cf = CandidateForm(
            CandidateID=candidate.CandidateID,
            JoiningDate=form_in.JoiningDate,
            Position=form_in.Position,
            Department=form_in.Department,
            DOB=form_in.DOB,
            Aadhar=form_in.Aadhar,
            PAN=form_in.PAN,
            Address=form_in.Address,
            SubmittedAt=form_in.SubmittedAt
        )
        db.add(cf)
        db.commit()
        db.refresh(cf)
        return cf

def get_form_for_candidate(db: Session, candidate_id: str) -> Optional[CandidateForm]:
    return db.query(CandidateForm).filter(CandidateForm.CandidateID == candidate_id).first()

def get_forms_for_candidate(db: Session, candidate_id: str):
    return db.query(CandidateForm).filter(CandidateForm.CandidateID == candidate_id).all()

