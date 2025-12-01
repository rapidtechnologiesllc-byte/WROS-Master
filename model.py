# models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func
from sqlalchemy.orm import relationship
from database import Base

class Users(Base):
    __tablename__ = "users"
    UserID = Column(Integer, primary_key=True, index=True)
    UserRole = Column(String(50), nullable=False)
    UserName = Column(String(150), nullable=True)
    UserEmail = Column(String(200), unique=True, nullable=False, index=True)
    UserPassword = Column(String(200), nullable=False)
    CreatedAt = Column(DateTime(timezone=False), server_default=func.now())

    candidate = relationship("Candidates", back_populates="user", uselist=False)


class Candidates(Base):
    __tablename__ = "candidates"
    CandidateID = Column(String(20), primary_key=True, index=True)
    UserID = Column(Integer, ForeignKey("users.UserID"), nullable=False)
    UserRole = Column(String(50), nullable=False)
    UserName = Column(String(150), nullable=True)
    UserEmail = Column(String(200), nullable=False)
    UserPassword = Column(String(200), nullable=False)
    CreatedAt = Column(DateTime(timezone=False), server_default=func.now())

    user = relationship("Users", back_populates="candidate")
    forms = relationship("CandidateForm", back_populates="candidate")


class CandidateForm(Base):
    __tablename__ = "candidate_forms"
    FormID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    CandidateID = Column(String(20), ForeignKey("candidates.CandidateID"), nullable=False)
    JoiningDate = Column(Date, nullable=True)
    Position = Column(String(255), nullable=True)
    Department = Column(String(100), nullable=True)
    DOB = Column(Date, nullable=True)
    Aadhar = Column(String(12), nullable=True)
    PAN = Column(String(10), nullable=True)
    Address = Column(Text, nullable=True)
    SubmittedAt = Column(Date, nullable=True)
    CreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    UpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    candidate = relationship("Candidates", back_populates="forms")
