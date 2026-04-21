from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func, Boolean, Index
from sqlalchemy.orm import relationship
from app.models.base import Base


class Candidate(Base):
    __tablename__ = "candidates"
    candidateID = Column(String(50), primary_key=True, index=True)
    candidateRole = Column(String(50), nullable=True, default="Candidate")
    candidateJobTitle = Column(String(50), nullable=True)
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
    # Job mapping — which job this candidate applied for / was assigned to
    job_id = Column(String(50), ForeignKey("jobs.jobID"), nullable=True, index=True)

    # Relationships
    documents = relationship("CandidateDocument", back_populates="candidate", foreign_keys="CandidateDocument.candidate_id")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select", back_populates="candidates")


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
    starting_year = Column(String(50), nullable=True)
    year_of_passing = Column(String(50), nullable=True)
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
    year_of_experience = Column(String(50), nullable=True)
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


class CandidateStatus(Base):
    __tablename__ = "candidate_status"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    piplineStatus = Column(String(50), nullable=True, default="Applied")
    status = Column(String(50), nullable=True, default="Active")
    createdAt = Column(DateTime(timezone=False), server_default=func.now())
    updatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")
