"""Pydantic schemas for employee conversion"""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, EmailStr

class EmployeeConversionRequest(BaseModel):
    candidate_id: str
    employee_email: str
    joining_date: date
    business_unit_id: int
    role_ids: Optional[List[int]] = None
    employment_type: str = "PERMANENT"
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class EmployeeAccountRequest(BaseModel):
    employee_name: str
    employee_email: EmailStr
    business_unit_id: int
    tenant_id: int
    role_ids: Optional[List[int]] = None
    phone: Optional[str] = None

class WelcomeEmailRequest(BaseModel):
    employee_id: str
    temporary_password: Optional[str] = None
    include_onboarding_link: bool = True

class EmployeeConversionResponse(BaseModel):
    status: str
    employee_id: str
    employee_email: str
    user_id: str
    roles_assigned: int

class EmployeeAccountResponse(BaseModel):
    user_id: str
    employee_email: str
    employee_name: str
    roles_assigned: int

class WelcomeEmailResponse(BaseModel):
    status: str
    email_sent: bool
    employee_email: str
