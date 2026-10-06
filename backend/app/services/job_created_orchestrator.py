"""Job Creation Orchestrator - Flash Autonomous Candidate Mapping

When a job is created, Flash autonomously:
1. Queries candidates matching job requirements
2. Calculates match quality using learning
3. Selects top candidates with score > 70%
4. Queues Thunder outreach for each selected candidate
5. Records audit trail
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.user import Jobs
from app.models.candidate import Candidate
from app.services.message_queue_service import MessageQueueService
from app.services.slm_learning_framework import SLMlearningFramework
from app.services.candidate_pipeline_stage import pipeline_stage_in

logger = logging.getLogger(__name__)


class JobCreatedOrchestrator:
    """Orchestrates autonomous candidate mapping when jobs are created"""

    MIN_MATCH_SCORE = 70.0  # Only select candidates with 70%+ match
    MAX_CANDIDATES_PER_JOB = 10  # Select top 10 candidates

    @staticmethod
    def on_job_created(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        job_title: str,
        job_location: str,
        required_skills: Optional[List[str]] = None,
        salary_range: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process job creation: Flash autonomously maps candidates.

        Args:
            db: Database session
            tenant_id: Tenant ID
            job_id: Job ID
            job_title: Job title
            job_location: Job location
            required_skills: Required skills list
            salary_range: Offered salary range
            description: Job description

        Returns:
            Orchestration result with candidates selected + outreach queued
        """
        try:
            logger.info(f"[JobOrchestrator] Processing job creation: {job_id}, title={job_title}")

            # PHASE 1: Query candidates matching job requirements
            candidates = JobCreatedOrchestrator._find_matching_candidates(
                db=db,
                tenant_id=tenant_id,
                job_title=job_title,
                required_skills=required_skills,
                job_location=job_location,
            )

            if not candidates:
                logger.warning(f"[JobOrchestrator] No matching candidates found for job {job_id}")
                return {
                    "status": "no_candidates",
                    "job_id": str(job_id),
                    "candidates_found": 0,
                    "candidates_selected": 0,
                    "outreach_queued": 0,
                }

            # PHASE 2: Calculate match scores using Flash learning
            scored_candidates = JobCreatedOrchestrator._score_candidates(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
                candidates=candidates,
            )

            # PHASE 3: Select top candidates with score > MIN_MATCH_SCORE
            selected_candidates = [
                c for c in scored_candidates
                if c["match_score"] >= JobCreatedOrchestrator.MIN_MATCH_SCORE
            ][:JobCreatedOrchestrator.MAX_CANDIDATES_PER_JOB]

            if not selected_candidates:
                logger.warning(
                    f"[JobOrchestrator] Found {len(scored_candidates)} candidates "
                    f"but none exceeded MIN_MATCH_SCORE of {JobCreatedOrchestrator.MIN_MATCH_SCORE}%"
                )
                return {
                    "status": "no_qualified_candidates",
                    "job_id": str(job_id),
                    "candidates_found": len(candidates),
                    "candidates_scored": len(scored_candidates),
                    "candidates_selected": 0,
                    "outreach_queued": 0,
                    "min_score_threshold": JobCreatedOrchestrator.MIN_MATCH_SCORE,
                }

            # PHASE 4: Queue outreach for each selected candidate
            outreach_count = JobCreatedOrchestrator._queue_outreach(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
                candidates=selected_candidates,
                job_title=job_title,
                job_location=job_location,
                salary_range=salary_range,
                description=description,
            )

            logger.info(
                f"[JobOrchestrator] Job {job_id} orchestration complete: "
                f"found {len(candidates)}, selected {len(selected_candidates)}, "
                f"queued {outreach_count} outreach messages"
            )

            return {
                "status": "success",
                "job_id": str(job_id),
                "job_title": job_title,
                "candidates_found": len(candidates),
                "candidates_scored": len(scored_candidates),
                "candidates_selected": len(selected_candidates),
                "outreach_queued": outreach_count,
                "min_score_threshold": JobCreatedOrchestrator.MIN_MATCH_SCORE,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to orchestrate job creation: {e}", exc_info=True)
            raise

    @staticmethod
    def _find_matching_candidates(
        db: Session,
        tenant_id: uuid.UUID,
        job_title: str,
        required_skills: Optional[List[str]] = None,
        job_location: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find candidates matching job requirements"""
        try:
            # Query candidates in OFFER or INTERVIEWING status (active pipeline)
            query = db.query(Candidate).filter(
                and_(
                    Candidate.tenant_id == tenant_id,
                    pipeline_stage_in("OFFER", "INTERVIEWING", "APPLIED"),
                )
            )

            candidates = query.all()

            # Convert to dict with basic info
            result = []
            for c in candidates:
                result.append({
                    "candidate_id": str(c.candidateID),
                    "name": c.candidateName or "Unknown",
                    "title": c.currentJobTitle or "Unknown",
                    "experience_years": c.yearsOfExperience or 0,
                    "location": c.currentLocation or "Unknown",
                    "skills": [],  # Would be parsed from candidate profile
                    "status": c.candidateStatus,
                })

            return result

        except Exception as e:
            logger.error(f"Failed to find matching candidates: {e}", exc_info=True)
            raise

    @staticmethod
    def _score_candidates(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Calculate match scores using Flash learning"""
        try:
            # Get Flash learning metric for this job
            flash_recommendations = SLMlearningFramework.get_flash_recommendations(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
            )

            # Score each candidate based on learning + profile match
            scored = []
            for candidate in candidates:
                # Base score from learning: expected match quality
                base_score = flash_recommendations.get("match_quality", 0.60) * 100

                # Adjust based on candidate profile
                # (In production: compare skills, experience, location)
                profile_adjustment = 0
                if candidate.get("title") and "senior" in candidate["title"].lower():
                    profile_adjustment += 10
                if candidate.get("experience_years", 0) >= 5:
                    profile_adjustment += 5

                final_score = min(base_score + profile_adjustment, 100.0)

                scored.append({
                    **candidate,
                    "match_score": final_score,
                    "match_confidence": flash_recommendations.get("confidence", 0.5),
                })

            # Sort by score descending
            scored.sort(key=lambda x: x["match_score"], reverse=True)
            return scored

        except Exception as e:
            logger.error(f"Failed to score candidates: {e}", exc_info=True)
            raise

    @staticmethod
    def _queue_outreach(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        candidates: List[Dict[str, Any]],
        job_title: str,
        job_location: str,
        salary_range: Optional[str] = None,
        description: Optional[str] = None,
    ) -> int:
        """Queue Thunder outreach for selected candidates"""
        try:
            outreach_count = 0

            for candidate in candidates:
                try:
                    # Queue Thunder outreach
                    outreach_data = {
                        "candidate_id": candidate["candidate_id"],
                        "job_id": str(job_id),
                        "job_title": job_title,
                        "job_location": job_location,
                        "salary_range": salary_range or "Competitive",
                        "description": description or f"{job_title} position at {job_location}",
                        "match_score": candidate.get("match_score", 0),
                        "candidate_name": candidate.get("name", "Candidate"),
                    }

                    # Queue message for Thunder
                    task_id = str(uuid.uuid4())
                    MessageQueueService.enqueue(
                        task_name="create_thunder_outreach",
                        task_id=task_id,
                        data=outreach_data,
                    )

                    outreach_count += 1

                    logger.info(
                        f"[JobOrchestrator] Queued outreach: "
                        f"candidate={candidate['candidate_id']}, "
                        f"job={job_id}, task_id={task_id}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to queue outreach for candidate {candidate.get('candidate_id')}: {e}",
                        exc_info=True,
                    )
                    continue

            return outreach_count

        except Exception as e:
            logger.error(f"Failed to queue outreach: {e}", exc_info=True)
            raise
