# schema.py
from pydantic import BaseModel, EmailStr, constr
from typing import Optional
from datetime import datetime, date

class UserCreate(BaseModel):
    UserRole: constr(strip_whitespace=True, min_length=1)
    UserName: Optional[str] = None
    UserEmail: EmailStr
    UserPassword: constr(min_length=6)

class UserRead(BaseModel):
    UserID: int
    UserRole: str
    UserName: Optional[str]
    UserEmail: EmailStr
    CreatedAt: datetime

    class Config:
        orm_mode = True

class LoginRequest(BaseModel):
    UserRole: constr(strip_whitespace=True, min_length=1)
    UserEmail: EmailStr
    UserPassword: str

# Candidate Form schemas
class CandidateFormCreate(BaseModel):
    JoiningDate: Optional[date] = None
    Position: Optional[str] = None
    Department: Optional[str] = None
    DOB: Optional[date] = None
    Aadhar: Optional[str] = None
    PAN: Optional[str] = None
    Address: Optional[str] = None
    SubmittedAt: Optional[date] = None

class CandidateFormRead(BaseModel):
    FormID: int
    CandidateID: str
    JoiningDate: Optional[datetime]
    Position: Optional[str]
    Department: Optional[str]
    DOB: Optional[date]
    Aadhar: Optional[str]
    PAN: Optional[str]
    Address: Optional[str]
    SubmittedAt: Optional[datetime]
    CreatedAt: datetime
    UpdatedAt: datetime

    class Config:
        orm_mode = True
