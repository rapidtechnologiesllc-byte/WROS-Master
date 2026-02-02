from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, security
from app.models.user import Users
from app.models.candidate import Candidate


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials containing JWT token
        db: Database session
        
    Returns:
        User or Candidate object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "candidate")  # Default to candidate
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Import here to avoid circular dependency
    if user_type == "user":
        user = db.query(Users).filter(Users.UserID == user_id).first()
    else:
        user = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


async def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated candidate from JWT token.
    Ensures the user is a candidate.
    
    Args:
        credentials: HTTP Bearer credentials containing JWT token
        db: Database session
        
    Returns:
        Candidate object
        
    Raises:
        HTTPException: If token is invalid, user not found, or not a candidate
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    user_type: str = payload.get("type")
    
    if not user_id or user_type != "candidate":
        raise HTTPException(status_code=403, detail="Not authorized as candidate")
    
    candidate = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
    
    if not candidate:
        raise HTTPException(status_code=401, detail="Candidate not found")
    
    return candidate


async def get_current_hr_or_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated HR or Admin user from JWT token.
    Ensures the user has HR or Admin role.
    
    Args:
        credentials: HTTP Bearer credentials containing JWT token
        db: Database session
        
    Returns:
        Users object with HR or Admin role
        
    Raises:
        HTTPException: If token is invalid, user not found, or not HR/Admin
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    user_type: str = payload.get("type")
    
    user_type = user_type.lower()
    # Accept 'user', 'hr', or 'admin' types
    if not user_id or user_type not in ["user", "hr", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # For Microsoft SSO users, 'sub' contains email, not UserID
    user = db.query(Users).filter(Users.UserEmail == user_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if user.UserRole.lower() not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Requires HR or Admin role")
    
    return user
