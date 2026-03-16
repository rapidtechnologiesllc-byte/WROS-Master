from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import (
    SessionLocal,
    engine,
    check_candidate,
    check_user,
    get_db,
    authenticate_user,
    authenticate_candidate
)
from app.core.security import (
    verify_password,
    create_access_token,
    get_password_hash,
)
from app.core.dependencies import get_current_candidate, get_current_hr_or_admin
from app.models.candidate import Candidate
from app.models.user import Users
from app.schemas.auth import SignupRequest, SignupResponse, LoginRequest, LoginResponse, CandidateLoginRequest, CandidateLoginResponse
from app.utils.uniq_id_generator import candidate_id_generator, generate_password, user_id_generator

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/v1/signup", response_model=SignupResponse)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new user account
    
    Args:
        request: SignupRequest containing user details
        db: Database session
        
    Returns:
        SignupResponse with success message
        
    Raises:
        HTTPException: If user with email already exists
    """
    # Check if user already exists
    existing = check_user(db, request.user_email)
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Account already exists with email {request.user_email}"
        )
    
    # Generate unique ID and hash password
    user_id = user_id_generator()
    hashed_password = get_password_hash(request.user_password)
    
    # Create new user with correct field names matching Users model
    user = Users(
        UserID=user_id,
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=hashed_password,
        UserRole=request.user_role
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return SignupResponse(response="User created successfully")
    



@router.post("/v1/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    User login endpoint
    
    Args:
        request: LoginRequest containing email and password
        db: Database session
        
    Returns:
        LoginResponse with user details and access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    user = authenticate_user(db, request.UserEmail, request.UserPassword)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user.UserEmail,
            "type": user.UserRole,
            "name": user.UserName
        }
    )
    
    # Return user info and token
    return LoginResponse(
        user_role=user.UserRole,
        user_name=user.UserName or "",
        user_email=user.UserEmail,
        is_first_time=False,  # Assuming existing users are not first time
        access_token=access_token
    )

@router.post("/candidate/login", response_model=CandidateLoginResponse)
def candidate_login(request: CandidateLoginRequest, db : Session = Depends(get_db)):
    """
    Candidate login endpoint
    
    Args:
        request: CandidateLoginRequest containing email and password
        db: Database session
        
    Returns:
        CandidateLoginResponse with candidate details and access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate candidate
    candidate = authenticate_candidate(db, request.candidate_email, request.candidate_password)
    
    if not candidate:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": candidate.candidateID,
            "type": "candidate"
        }
    )
    
    # Construct full name from name fields
    name_parts = [
        candidate.candidateFirstName,
        candidate.candidateMiddleName,
        candidate.candidateLastName
    ]
    candidate_name = " ".join(filter(None, name_parts)) or ""
    
    # Return candidate info and token
    return CandidateLoginResponse(
        candidate_id=candidate.candidateID,
        candidate_role=candidate.candidateRole or "Candidate",
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        candidate_mobile=candidate.candidateMobile,
        is_first_time=not candidate.candidateIsVerified if candidate.candidateIsVerified is not None else True,
        access_token=access_token
    )

