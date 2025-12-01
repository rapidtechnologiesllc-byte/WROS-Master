# main.py
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import model, crud, schema
from database import SessionLocal, engine, Base
from typing import Optional

# create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Onboarding Auth API")

# set appropriate origins for your frontend dev server
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # add your deployed frontend domain here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/signup", response_model=schema.UserRead)
def signup(user_in: schema.UserCreate, db: Session = Depends(get_db)):
    existing = crud.get_user_by_email(db, user_in.UserEmail)
    if existing:
        raise HTTPException(status_code=400, detail=f"Account already exists with email {user_in.UserEmail}")
    user = crud.create_user(db, user_in)
    return user

@app.post("/login")
def login(login_req: schema.LoginRequest, db: Session = Depends(get_db)):
    result = crud.authenticate_user(db, login_req.UserEmail, login_req.UserPassword, login_req.UserRole)
    if not result["status"]:
        reason = result.get("reason")
        if reason == "not_found":
            return {"success": False, "message": "Account does not exist. Please sign up."}
        if reason == "role_mismatch":
            return {"success": False, "message": f"Role mismatch. Account exists with role {result.get('user_role')}."}
        if reason == "invalid_password":
            return {"success": False, "message": "Invalid credentials. Password incorrect."}
    user = result["user"]
    # Return the minimal user object (no password)
    return {
        "success": True,
        "message": "Login successful",
        "user": {
            "UserID": user.UserID,
            "UserRole": user.UserRole,
            "UserName": user.UserName,
            "UserEmail": user.UserEmail
        }
    }

# Create candidate form endpoint
@app.post("/candidate-form", response_model=schema.CandidateFormRead)
def create_or_update_candidate_form_endpoint(
    form_in: schema.CandidateFormCreate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")

    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-ID header value")

    user = db.query(model.Users).filter(model.Users.UserID == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    candidate = crud.get_candidate_by_userid(db, user_id)
    if not candidate:
        raise HTTPException(status_code=403, detail="User is not a candidate or candidate record missing")

    try:
        created_or_updated = crud.create_or_update_candidate_form(db, user_id, form_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return created_or_updated

@app.get("/candidate-form", response_model=Optional[schema.CandidateFormRead])
def get_candidate_form(db: Session = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")
    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-ID header value")
    candidate = crud.get_candidate_by_userid(db, user_id)
    if not candidate:
        raise HTTPException(status_code=403, detail="User is not a candidate or candidate record missing")
    
    form = crud.get_form_for_candidate(db, candidate.CandidateID)
    return form

# Optional: get all forms for the current candidate
@app.get("/candidate-forms")
def get_my_forms(db: Session = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")
    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-ID header value")
    candidate = crud.get_candidate_by_userid(db, user_id)
    if not candidate:
        raise HTTPException(status_code=403, detail="User is not a candidate or candidate record missing")
    forms = crud.get_forms_for_candidate(db, candidate.CandidateID)
    return {"success": True, "forms": forms}
