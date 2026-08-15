"""
HRMS-1105 (S-320) -- Candidate Ranking & Scoring REST Endpoints.

Endpoints:
- POST /candidates/ranking/fit-score - Calculate fit score for candidate
- POST /candidates/ranking/rank - Rank all candidates for job
- POST /candidates/ranking/best-match - Identify best candidate for job
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.candidate_ranking import (
    CalculateFitScoreRequest,
    CalculateFitScoreResponse,
    RankCandidatesRequest,
    RankCandidatesResponse,
    IdentifyBestMatchRequest,
    IdentifyBestMatchResponse,
)
from app.services.candidate_scoring_service import CandidateScoringService

router = APIRouter(prefix="/candidates/ranking", tags=["candidate-ranking"])
scoring_service = CandidateScoringService()


@router.post(
    "/fit-score",
    response_model=CalculateFitScoreResponse,
    summary="Calculate candidate fit score",
    description="Calculate how well a candidate matches a specific job demand (0-100 scale)"
)
def calculate_fit_score(
    request: CalculateFitScoreRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Calculate fit score for a candidate against a job demand.

    **Request Body:**
    - `candidate_id`: Candidate ID
    - `demand_id`: Demand (job) ID

    **Response:**
    - `fit_score`: 0-100 overall score
    - `components`: Score breakdown (skills, experience, location, resume)
    - `recommendation`: STRONG_MATCH | GOOD_MATCH | FAIR_MATCH | WEAK_MATCH
    - `weights`: Component weights used in calculation

    **Scoring Formula:**
    - Skills match: 40%
    - Experience level: 35%
    - Location match: 15%
    - Resume completeness: 10%
    """
    # Get tenant from current user
    tenant_id = getattr(current_user, 'tenant_id', 1)

    result = scoring_service.calculate_fit_score(
        db=db,
        candidate_id=request.candidate_id,
        demand_id=request.demand_id,
        tenant_id=tenant_id
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Could not calculate fit score")
        )

    return result


@router.post(
    "/rank",
    response_model=RankCandidatesResponse,
    summary="Rank candidates for a job",
    description="Rank all candidates for a specific job demand by fit score"
)
def rank_candidates(
    request: RankCandidatesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Rank all candidates for a specific job demand.

    **Request Body:**
    - `demand_id`: Demand (job) ID
    - `limit`: Maximum candidates to evaluate (default 50, max 1000)

    **Response:**
    - `ranked_candidates`: List of candidates sorted by fit_score (descending)
    - `total_candidates_evaluated`: Number of candidates scored

    **Each ranked candidate includes:**
    - `rank`: Position in ranking (1 = best match)
    - `fit_score`: Overall score 0-100
    - `recommendation`: Match quality
    - `components`: Score breakdown
    """
    # Get tenant from current user
    tenant_id = getattr(current_user, 'tenant_id', 1)

    result = scoring_service.rank_candidates(
        db=db,
        demand_id=request.demand_id,
        tenant_id=tenant_id,
        limit=request.limit
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Could not rank candidates")
        )

    return result


@router.post(
    "/best-match",
    response_model=IdentifyBestMatchResponse,
    summary="Identify best candidate for a job",
    description="Find the top-ranked candidate for a specific job demand"
)
def identify_best_match(
    request: IdentifyBestMatchRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Identify the best matching candidate for a job demand.

    **Request Body:**
    - `demand_id`: Demand (job) ID

    **Response:**
    - `best_match_candidate_id`: Top candidate's ID
    - `best_match_candidate_name`: Candidate's name
    - `best_match_candidate_email`: Candidate's email
    - `fit_score`: Overall score 0-100
    - `recommendation`: Match quality
    - `ready_to_interview`: True if fit_score >= 70

    **Use this to:**
    - Auto-assign top candidates for interviews
    - Recommend next candidates to reach out to
    - Identify candidates ready for hiring pipeline
    """
    # Get tenant from current user
    tenant_id = getattr(current_user, 'tenant_id', 1)

    result = scoring_service.identify_best_match(
        db=db,
        demand_id=request.demand_id,
        tenant_id=tenant_id
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Could not identify best match")
        )

    return result
