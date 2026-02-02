# login schemas
from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from datetime import datetime, date

class SignupRequest(BaseModel):
    user_name: str
    user_email: EmailStr
    user_password: str
    user_role: str


class SignupResponse(BaseModel):
    response: str = "User created successfully"


class LoginRequest(BaseModel):
    UserEmail: EmailStr
    UserPassword: str

class LoginResponse(BaseModel):
    user_role: str
    user_name: str
    user_email: EmailStr
    is_first_time: bool
    access_token: str

class CandidateLoginRequest(BaseModel):
    candidate_email: EmailStr
    candidate_password: str

class CandidateLoginResponse(BaseModel):
    candidate_id: str
    candidate_role: str
    candidate_name: str
    candidate_email: EmailStr
    candidate_mobile: str
    is_first_time: bool
    access_token: str
