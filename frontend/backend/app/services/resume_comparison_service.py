"""
Resume Comparison Service - Detect changes between candidate resume versions

Enables detection of:
1. Resume inflation (exaggerating experience)
2. Resume tailoring (matching exact job requirements suspiciously well)
3. Resume inconsistencies (contradictory dates, roles)
4. Ghosting (candidate claims experience that disappeared in later version)

Used by Thunder to assess resume authenticity before scheduling interviews.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_resume_parsed import CandidateResumeParsed


class ResumeChangeAnalysis:
    """Analysis of changes between two resume versions"""

    def __init__(self, old_version: CandidateResumeParsed, new_version: CandidateResumeParsed):
        self.old = old_version
        self.new = new_version

        # Detect changes
        self.skill_additions = self._detect_skill_additions()
        self.experience_inflation = self._detect_experience_inflation()
        self.job_gaps_removed = self._detect_gap_removal()
        self.title_upgrades = self._detect_title_upgrades()
        self.inconsistencies = self._detect_inconsistencies()

        # Compute suspicion score (0-100)
        self.suspicion_score = self._calculate_suspicion()

    def _detect_skill_additions(self) -> Tuple[List[str], float]:
        """Detect new skills added (could indicate tailoring for specific job)"""
        old_skills = set(self.old.skills or [])
        new_skills = set(self.new.skills or [])

        added_skills = new_skills - old_skills
        removed_skills = old_skills - new_skills

        # Score: High suspicion if many skills added, low suspicion if gradual growth
        # Formula: (added_skills - removed_skills) / total_skills
        total_skills = len(new_skills) if len(new_skills) > 0 else 1
        skill_change_ratio = len(added_skills) / total_skills if total_skills > 0 else 0

        suspicion = skill_change_ratio * 0.3  # Weight: 30% of total
        logger.debug(f"Skill analysis: +{len(added_skills)}, -{len(removed_skills)}, ratio={skill_change_ratio:.2f}")

        return list(added_skills), suspicion

    def _detect_experience_inflation(self) -> Tuple[int, float]:
        """Detect sudden jumps in reported experience"""
        old_months = self.old.total_experience_months or 0
        new_months = self.new.total_experience_months or 0

        # Experience should only increase (or stay same), never decrease significantly
        month_diff = new_months - old_months

        # Suspicious if:
        # 1. Claims 12+ months more experience in <6 months
        # 2. Suddenly claims experience in fields not mentioned before
        suspicion = 0.0

        if month_diff < 0:
            # Experience decreased - possible data error or resume fraud
            suspicion = 0.5  # High suspicion
        elif month_diff > 24:
            # Claims 24+ months more experience in short timeframe - suspicious
            suspicion = 0.3

        logger.debug(f"Experience analysis: {old_months}mo → {new_months}mo, delta={month_diff}mo")
        return month_diff, suspicion * 0.25  # Weight: 25% of total

    def _detect_gap_removal(self) -> Tuple[List[str], float]:
        """Detect removed jobs or employment gaps being filled"""
        old_jobs = set((j.get('employer'), j.get('title')) for j in (self.old.work_history or []))
        new_jobs = set((j.get('employer'), j.get('title')) for j in (self.new.work_history or []))

        removed_jobs = old_jobs - new_jobs

        # High suspicion if jobs are removed from history
        suspicion = len(removed_jobs) * 0.2  # Each removed job: 20% suspicion

        if removed_jobs:
            logger.warning(f"Gap analysis: {len(removed_jobs)} jobs removed from resume - SUSPICIOUS")

        return list(removed_jobs), suspicion  # Weight: 30% of total

    def _detect_title_upgrades(self) -> Tuple[List[Tuple[str, str]], float]:
        """Detect retroactive changes to job titles"""
        old_jobs = {(j.get('employer'), j.get('start_date')): j.get('title') for j in (self.old.work_history or [])}
        new_jobs = {(j.get('employer'), j.get('start_date')): j.get('title') for j in (self.new.work_history or [])}

        title_changes = []
        for job_key, old_title in old_jobs.items():
            new_title = new_jobs.get(job_key)
            if new_title and new_title != old_title:
                title_changes.append((old_title or "Unknown", new_title or "Unknown"))

        # High suspicion: retroactively upgrading titles (e.g., "Junior Dev" → "Senior Architect")
        suspicion = 0.0
        for old_title, new_title in title_changes:
            # Detect suspicious patterns
            if self._is_suspicious_upgrade(old_title, new_title):
                suspicion += 0.25

        if title_changes:
            logger.warning(f"Title upgrade analysis: {len(title_changes)} retroactive title changes - SUSPICIOUS")

        return title_changes, suspicion  # Weight: 20% of total

    @staticmethod
    def _is_suspicious_upgrade(old_title: str, new_title: str) -> bool:
        """Detect suspicious title upgrades"""
        suspicious_patterns = [
            ("Junior", "Senior"),
            ("Associate", "Manager"),
            ("Analyst", "Director"),
            ("Developer", "Architect"),
            ("Coordinator", "Lead"),
        ]

        old_lower = old_title.lower()
        new_lower = new_title.lower()

        for junior, senior in suspicious_patterns:
            if junior.lower() in old_lower and senior.lower() in new_lower:
                return True

        return False

    def _detect_inconsistencies(self) -> Tuple[List[str], float]:
        """Detect contradictions in resume versions"""
        issues = []
        suspicion = 0.0

        # Check: Current employer inconsistency
        if self.old.current_employer and self.new.current_employer:
            if self.old.current_employer != self.new.current_employer:
                issues.append(f"Current employer changed: {self.old.current_employer} → {self.new.current_employer}")
                suspicion += 0.15

        # Check: Education field changes
        old_education = {(e.get('institution'), e.get('degree')) for e in (self.old.education or [])}
        new_education = {(e.get('institution'), e.get('degree')) for e in (self.new.education or [])}

        if old_education != new_education:
            removed_education = old_education - new_education
            if removed_education:
                issues.append(f"Education entries removed: {removed_education}")
                suspicion += 0.2  # Removing education is suspicious

        # Check: Date inconsistencies
        old_jobs_by_employer = {j.get('employer'): j.get('start_date') for j in (self.old.work_history or [])}
        new_jobs_by_employer = {j.get('employer'): j.get('start_date') for j in (self.new.work_history or [])}

        for employer in old_jobs_by_employer:
            if employer in new_jobs_by_employer:
                if old_jobs_by_employer[employer] != new_jobs_by_employer[employer]:
                    issues.append(f"Start date changed for {employer}: {old_jobs_by_employer[employer]} → {new_jobs_by_employer[employer]}")
                    suspicion += 0.25

        return issues, suspicion  # Weight: 25% of total

    def _calculate_suspicion(self) -> float:
        """
        Calculate overall suspicion score (0-100).

        0 = Completely authentic resume
        100 = Obvious fraud/tailoring
        """
        total_suspicion = (
            self.skill_additions[1] +
            self.experience_inflation[1] +
            self.job_gaps_removed[1] +
            self.title_upgrades[1] +
            self.inconsistencies[1]
        )

        # Normalize to 0-100
        score = min(total_suspicion * 100, 100)

        # Thresholds
        if score < 20:
            self.risk_level = "LOW"
            self.risk_description = "Minor updates, normal resume evolution"
        elif score < 40:
            self.risk_level = "MEDIUM"
            self.risk_description = "Notable changes, possibly tailored for job"
        elif score < 60:
            self.risk_level = "HIGH"
            self.risk_description = "Suspicious pattern detected, consider verification"
        else:
            self.risk_level = "CRITICAL"
            self.risk_description = "Strong indicators of resume inflation/fraud"

        return score

    def get_summary(self) -> Dict:
        """Get human-readable summary of resume changes"""
        return {
            "suspicion_score": self.suspicion_score,
            "risk_level": self.risk_level,
            "risk_description": self.risk_description,
            "skills_added": self.skill_additions[0][:5],  # Top 5
            "skills_added_count": len(self.skill_additions[0]),
            "experience_delta_months": self.experience_inflation[0],
            "jobs_removed": len(self.job_gaps_removed[0]),
            "title_changes": len(self.title_upgrades[0]),
            "inconsistencies": self.inconsistencies[0][:3],  # Top 3
            "recommendation": self._get_recommendation(),
        }

    def _get_recommendation(self) -> str:
        """Get recommendation for recruiter/Thunder"""
        if self.suspicion_score >= 60:
            return "HOLD: Verify resume authenticity before interview"
        elif self.suspicion_score >= 40:
            return "CAUTION: Ask about resume changes in interview"
        elif self.suspicion_score >= 20:
            return "OK: Normal resume updates"
        else:
            return "OK: Resume unchanged, no concerns"


class ResumeComparisonService:
    """Service for comparing candidate resume versions"""

    @staticmethod
    def get_resume_versions(db: Session, candidate_id: str) -> List[CandidateResumeParsed]:
        """Get all resume versions for a candidate, ordered by date"""
        versions = db.query(CandidateResumeParsed).filter(
            CandidateResumeParsed.candidate_id == candidate_id
        ).order_by(desc(CandidateResumeParsed.parsed_at)).all()

        return versions

    @staticmethod
    def compare_versions(
        db: Session,
        candidate_id: str
    ) -> Optional[ResumeChangeAnalysis]:
        """
        Compare the two most recent resume versions for a candidate.
        Returns analysis of changes and suspicion score.
        """
        versions = ResumeComparisonService.get_resume_versions(db, candidate_id)

        if len(versions) < 2:
            return None  # Only one version, no comparison possible

        # Compare most recent two versions
        new_version = versions[0]
        old_version = versions[1]

        return ResumeChangeAnalysis(old_version, new_version)

    @staticmethod
    def flag_suspicious_resume(
        db: Session,
        candidate: Candidate,
        analysis: ResumeChangeAnalysis
    ) -> None:
        """
        Flag a candidate's resume as suspicious for recruiter review.
        """
        if analysis.suspicion_score >= 40:
            from app.models.internal_note import InternalNote

            note = InternalNote(
                candidate_id=candidate.candidateID,
                noted_by_user_id=candidate.tenant_id,
                note_type="RESUME_AUTHENTICITY_FLAG",
                note_content=f"Resume suspicion score: {analysis.suspicion_score}/100\n"
                            f"Risk Level: {analysis.risk_level}\n"
                            f"Details:\n"
                            f"- Skills added: {len(analysis.skill_additions[0])}\n"
                            f"- Experience inflation: +{analysis.experience_inflation[0]} months\n"
                            f"- Title changes: {len(analysis.title_upgrades[0])}\n"
                            f"\nRecommendation: {analysis._get_recommendation()}",
                is_internal=True,
            )
            db.add(note)
            db.flush()

            logger.warning(
                f"[ResumeComparison] Flagged suspicious resume for candidate {candidate.candidateID} "
                f"(score: {analysis.suspicion_score}, risk: {analysis.risk_level})"
            )

    @staticmethod
    def detect_tailoring_for_job(
        db: Session,
        candidate_id: str,
        job_description: str,
        job_requirements: List[str]
    ) -> Tuple[float, str]:
        """
        Detect if candidate's latest resume appears tailored for a specific job.

        Returns: (tailoring_score, recommendation)
        tailoring_score: 0-100 (higher = more likely tailored)
        """
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            return 0.0, "Candidate not found"

        latest_resume = db.query(CandidateResumeParsed).filter(
            CandidateResumeParsed.candidate_id == candidate_id
        ).order_by(desc(CandidateResumeParsed.parsed_at)).first()

        if not latest_resume:
            return 0.0, "No resume found"

        # Check if resume skills suspiciously match job requirements exactly
        resume_skills = set(latest_resume.skills or [])
        job_skills_lower = set(s.lower() for s in job_requirements)
        resume_skills_lower = set(s.lower() for s in resume_skills)

        matching_skills = resume_skills_lower & job_skills_lower
        match_ratio = len(matching_skills) / len(job_skills_lower) if job_skills_lower else 0

        tailoring_score = 0.0

        # Suspicion triggers:
        # 1. 90%+ of job requirements exactly match resume skills → tailored
        # 2. New skills added that match job description
        # 3. Current title matches job title exactly

        if match_ratio > 0.9:
            tailoring_score += 40

        if latest_resume.current_title and any(req.lower() in latest_resume.current_title.lower() for req in job_requirements):
            tailoring_score += 30

        # Check for "too perfect" match in work history
        job_keywords = job_description.lower().split()
        for job in (latest_resume.work_history or []):
            description = job.get('description', '').lower()
            if description:
                keyword_count = sum(1 for kw in job_keywords if kw in description)
                if keyword_count > len(job_keywords) * 0.7:
                    tailoring_score += 20  # Multiple job keywords in description

        tailoring_score = min(tailoring_score, 100)

        # Recommendation based on score
        if tailoring_score > 70:
            recommendation = "VERIFY: Resume appears tailored for this job - verify authenticity"
        elif tailoring_score > 50:
            recommendation = "CAUTION: Resume may have been tailored - normal for active job seekers"
        else:
            recommendation = "OK: No evidence of suspicious tailoring"

        return tailoring_score, recommendation
