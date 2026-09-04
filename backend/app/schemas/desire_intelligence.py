"""
Pydantic Schemas -- S-350/HRMS-P120 HR Intelligence Briefing.
"""
from datetime import datetime
import logging
from typing import List, Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class DesireRankingItem(BaseModel):
    category: str
    score: float
    signal_count: int
    direction: str

class MotivationHistoryItem(BaseModel):
    id: int
    trigger_type: str
    desire_category_targeted: Optional[str] = None
    message_preview: str
    sent_at: Optional[datetime] = None
    response_within_24h: Optional[bool] = None
    offer_accepted: Optional[bool] = None

class DesireIntelligenceResponse(BaseModel):
    candidate_id: str
    has_profile: bool  # False = no desire signals recorded yet at all
    top_desire_category: Optional[str] = None
    top_desire_score: Optional[float] = None
    desire_ranking: List[DesireRankingItem] = []
    primary_fear: Optional[str] = None
    primary_fear_score: Optional[float] = None
    engagement_level: Optional[str] = None
    has_competing_offer: bool = False
    decision_urgency: Optional[str] = None
    narrative_summary: Optional[str] = None
    narrative_updated_at: Optional[datetime] = None
    talking_points: List[str] = []
    profile_updated_at: Optional[datetime] = None
    motivation_history: List[MotivationHistoryItem] = []
