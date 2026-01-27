# model.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func, Boolean
from sqlalchemy.orm import relationship
from database import Base

class Users(Base):
    __tablename__ = "users"
    UserID = Column(String(50), primary_key=True, index=True)
    UserRole = Column(String(50), nullable=False)
    UserName = Column(String(150), nullable=True)
    UserEmail = Column(String(200), unique=True, nullable=False, index=True)
    UserPassword = Column(String(200), nullable=False)
    CreatedAt = Column(DateTime(timezone=False), server_default=func.now())

class Jobs(Base):
    __tablename__ = "jobs"
    jobID = Column(String(50), primary_key=True, index=True)
    jobTitle = Column(String(200), nullable=False)
    jobDescription = Column(Text, nullable=False)
    jobSkills = Column(Text, nullable=False)
    jobExperience = Column(String(50), nullable=False)
    jobLocation = Column(String(50), nullable=False)
    jobCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    companyType = Column(String(50), nullable=False)
    companyName = Column(String(50), nullable=False)
    contactPerson = Column(String(100), nullable=True)
    jobStatus = Column(String(50), nullable=False)
    noOfPositions = Column(Integer, nullable=False)
    startDate = Column(Date, nullable=True)
    endDate = Column(Date, nullable=True)
    hiringManagerID = Column(String(50), ForeignKey("users.UserID"), nullable=False)

class Candidate(Base):
    __tablename__ = "candidates"
    candidateID = Column(String(50), primary_key=True, index=True)
    candidateRole = Column(String(50), nullable=True, default="Candidate")
    candidateFirstName = Column(String(150), nullable=True)
    candidateMiddleName = Column(String(150), nullable=True)
    candidateLastName = Column(String(150), nullable=True)
    candidateEmail = Column(String(200), unique=True, nullable=False, index=True)
    candidateMobile = Column(String(20), nullable=True)
    candidateGender = Column(String(10), nullable=True)
    candidateDateOfBirth = Column(Date, nullable=True)
    candidateSource = Column(String(50), nullable=True)
    candidateExperience = Column(String(50), nullable=True)
    candidateSkills = Column(Text, nullable=True)
    candidateJoiningDate = Column(Date, nullable=True)
    candidateExpectedSalary = Column(String(50), nullable=True)
    candidateCurrentSalary = Column(String(50), nullable=True)
    candidateCurrentLocation = Column(String(200), nullable=True)
    candidatePassword = Column(String(200), nullable=False)
    candidateIsVerified = Column(Boolean, nullable=True)
    candidateCreatedAt = Column(DateTime(timezone=False), server_default=func.now())

class CandidateAssignment(Base):
    __tablename__ = "candidate_assignments"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)

    hiring_manager_id = Column(String(50), ForeignKey("users.UserID"))
    reporting_manager_id = Column(String(50), ForeignKey("users.UserID"))

    hiring_manager = relationship("Users", foreign_keys=[hiring_manager_id])
    reporting_manager = relationship("Users", foreign_keys=[reporting_manager_id])

    created_at = Column(DateTime, default=datetime.utcnow)

class InterviewPanel(Base):
    __tablename__ = "interview_panels"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"))
    round_name = Column(String(50))  # HR, Tech, Manager

    created_at = Column(DateTime, default=datetime.utcnow)

class PanelMember(Base):
    __tablename__ = "panel_members"

    id = Column(Integer, primary_key=True)
    panel_id = Column(Integer, ForeignKey("interview_panels.id"))
    interviewer_id = Column(String(50), ForeignKey("users.UserID"))

    interviewer = relationship("Users")

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True)
    panel_id = Column(Integer, ForeignKey("interview_panels.id"))
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"))

    start_time = Column(DateTime)
    end_time = Column(DateTime)
    meeting_link = Column(Text)
    outlook_event_id = Column(Text)

    status = Column(String(50))  # Scheduled, Completed, Cancelled

class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"))
    interviewer_id = Column(String(50), ForeignKey("users.UserID"))

    technical_score = Column(Integer)
    communication_score = Column(Integer)
    problem_solving_score = Column(Integer)
    culture_fit_score = Column(Integer)

    comments = Column(Text)
    recommendation = Column(String(20))  # Hire / Hold / Reject

    submitted_at = Column(DateTime, default=datetime.utcnow)

class CandidateInfoForm(Base):
    __tablename__ = "candidate_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    position = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    dob = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    marital_status = Column(String(10), nullable=True)
    nationality = Column(String(10), nullable=True)
    current_address = Column(Text, nullable=True)
    permanent_address = Column(Text, nullable=True)
    submittedAt = Column(Date, nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")


class CandidateEducationForm(Base):
    __tablename__ = "candidate_education_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    education_institute = Column(String(255), nullable=True)
    degree = Column(String(255), nullable=True)
    field_of_study = Column(String(255), nullable=True)
    starting_year = Column(String(4), nullable=True)
    year_of_passing = Column(String(4), nullable=True)
    percentage = Column(String(10), nullable=True)
    submittedAt = Column(Date, nullable=True)
    document_is_submitted = Column(Boolean, nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidateExperienceForm(Base):
    __tablename__ = "candidate_experience_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    company_name = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    year_of_experience = Column(String(4), nullable=True)
    document_is_submitted = Column(Boolean, nullable=True)
    submittedAt = Column(Date, nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidateAadharForm(Base):
    __tablename__ = "candidate_aadhar_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    aadhar = Column(String(12), nullable=True)
    name_in_aadhar = Column(String(100), nullable=True)
    enrollment_number = Column(String(20), nullable=True)
    aadhar_is_submitted = Column(Boolean, nullable=True)
    submittedAt = Column(Date, nullable=True)
    is_verified = Column(Boolean, nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidatePanForm(Base):
    __tablename__ = "candidate_pan_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    pan = Column(String(10), nullable=True)
    name_in_pan = Column(String(100), nullable=True)
    father_name_in_pan = Column(String(100), nullable=True)
    pan_is_submitted = Column(Boolean, nullable=True)
    submittedAt = Column(Date, nullable=True)
    is_verified = Column(Boolean, nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")   