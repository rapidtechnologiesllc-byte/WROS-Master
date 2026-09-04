"""Unit tests for employee conversion service"""
import pytest
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.user import Users
from app.services.employee_conversion_service import EmployeeConversionService, InvalidCandidateState
import logging
from app.core.security import get_password_hash

@pytest.fixture
def candidate_data():
    return {
        "candidateID": "CAND-001",
        "candidateEmail": "john@example.com",
        "candidateFirstName": "John",
        "candidateLastName": "Doe",
        "candidateMobile": "555-1234",
        "tenant_id": 1,
        "candidatePassword": get_password_hash("test123"),
    }

@pytest.fixture
def candidate(db_session, candidate_data):
    cand = Candidate(**candidate_data)
    db_session.add(cand)
    db_session.commit()
    return cand

def test_create_employee_account(db_session):
    """Test creating employee account"""
    user = EmployeeConversionService.create_employee_account(
        db=db_session,
        employee_name="Jane Smith",
        employee_email="jane@example.com",
        business_unit_id=1,
        tenant_id=1
    )
    
    assert user is not None
    assert user.UserEmail == "jane@example.com"
    assert user.UserName == "Jane Smith"
    assert user.business_unit_id == 1

def test_create_account_duplicate_email(db_session):
    """Test duplicate email prevention"""
    EmployeeConversionService.create_employee_account(
        db=db_session,
        employee_name="Jane Smith",
        employee_email="jane@example.com",
        business_unit_id=1,
        tenant_id=1
    )
    
    with pytest.raises(ValueError):
        EmployeeConversionService.create_employee_account(
            db=db_session,
            employee_name="Jane Doe",
            employee_email="jane@example.com",
            business_unit_id=1,
            tenant_id=1
        )

def test_convert_candidate_to_employee(db_session, candidate):
    """Test candidate to employee conversion"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=db_session,
        candidate=candidate,
        joining_date=date.today(),
        business_unit_id=1
    )
    
    assert user is not None
    assert employee is not None
    assert employee.candidate_id == candidate.candidateID
    assert employee.delivery_engine == "SPECIALITY"
    assert employee.status == "PRE_JOINING"
    assert user.UserEmail == candidate.candidateEmail

def test_convert_candidate_already_converted(db_session, candidate):
    """Test preventing double conversion"""
    candidate.status = "CONVERTED_TO_EMPLOYEE"
    db_session.commit()
    
    with pytest.raises(InvalidCandidateState):
        EmployeeConversionService.convert_candidate_to_employee(
            db=db_session,
            candidate=candidate,
            joining_date=date.today(),
            business_unit_id=1
        )

def test_convert_with_role_assignment(db_session, candidate):
    """Test conversion with role assignment"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=db_session,
        candidate=candidate,
        joining_date=date.today(),
        business_unit_id=1,
        role_ids=[1, 2]
    )
    
    assert len(user.user_roles) == 2

def test_convert_with_custom_details(db_session, candidate):
    """Test conversion with custom details"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=db_session,
        candidate=candidate,
        joining_date=date(2026, 9, 1),
        business_unit_id=1,
        first_name="Custom",
        last_name="Name",
        employment_type="CONTRACT"
    )
    
    assert employee.first_name == "Custom"
    assert employee.last_name == "Name"
    assert employee.employment_type == "CONTRACT"
    assert employee.joining_date == date(2026, 9, 1)

def test_send_welcome_email_success(db_session, candidate):
    """Test welcome email sending"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=db_session,
        candidate=candidate,
        joining_date=date.today(),
        business_unit_id=1
    )
    
    result = EmployeeConversionService.send_welcome_email(
        db=db_session,
        employee_user=user,
        employee_record=employee,
        temporary_password="TempPass123!"
    )
    
    assert isinstance(result, bool)

def test_endpoint_conversion_request(client, candidate):
    """Test REST endpoint for conversion"""
    response = client.post(
        "/employees/convert-candidate",
        json={
            "candidate_id": candidate.candidateID,
            "employee_email": "converted@example.com",
            "joining_date": "2026-09-01",
            "business_unit_id": 1
        }
    )
    
    assert response.status_code in (200, 201)
    data = response.json()
    assert data["status"] == "success"
    assert data["employee_id"] is not None

def test_endpoint_create_account(client):
    """Test REST endpoint for account creation"""
    response = client.post(
        "/employees/create-account",
        json={
            "employee_name": "New Employee",
            "employee_email": "new@example.com",
            "business_unit_id": 1,
            "tenant_id": 1
        }
    )
    
    assert response.status_code in (200, 201)
    data = response.json()
    assert data["user_id"] is not None
    assert data["employee_email"] == "new@example.com"

def test_endpoint_send_welcome_email(client, candidate):
    """Test REST endpoint for welcome email"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=client.db_session,
        candidate=candidate,
        joining_date=date.today(),
        business_unit_id=1
    )
    
    response = client.post(
        "/employees/send-welcome-email",
        json={
            "employee_id": employee.id
        }
    )
    
    assert response.status_code in (200, 201)
    data = response.json()
    assert "email_sent" in data

def test_employee_status_retrieval(client, candidate):
    """Test getting employee status"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=client.db_session,
        candidate=candidate,
        joining_date=date.today(),
        business_unit_id=1
    )
    
    response = client.get(f"/employees/status/{employee.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == employee.id
    assert data["status"] == "PRE_JOINING"

def test_employee_update(client, candidate):
    """Test updating employee"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=client.db_session,
        candidate=candidate,
        joining_date=date.today(),
        business_unit_id=1
    )
    
    response = client.put(
        f"/employees/update/{employee.id}",
        json={"current_title": "Senior Developer"}
    )
    
    assert response.status_code == 200

def test_employee_deletion(client, candidate):
    """Test deleting employee"""
    user, employee = EmployeeConversionService.convert_candidate_to_employee(
        db=client.db_session,
        candidate=candidate,
        joining_date=date.today(),
        business_unit_id=1
    )
    
    response = client.delete(f"/employees/delete/{employee.id}")
    assert response.status_code == 200
    
    response = client.get(f"/employees/status/{employee.id}")
    assert response.status_code == 404
