"""Candidate skills and certifications entered on the HR profile.

Structured rows (the profile's Skills / Certifications modals). Kept apart
from CandidateSkillTag, which holds resume-extracted canonical skills.
Candidate.candidateSkills (comma list) is kept in sync with skill names
by the save endpoint, since matching and list views read it.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base


class CandidateProfileSkill(Base):
    __tablename__ = "candidate_profile_skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    years_of_experience = Column(String(20), nullable=True)
    last_used_date = Column(Date, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())


class CandidateCertification(Base):
    __tablename__ = "candidate_certifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    organization = Column(String(255), nullable=True)
    issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    credential_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
