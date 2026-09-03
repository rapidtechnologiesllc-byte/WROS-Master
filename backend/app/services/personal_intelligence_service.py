"""
import logging
Personal Intelligence Service - 200+ Data Points for Deep Relationship Building

Captures comprehensive personal profile to make genuine human connection:
- Personal interests (games, food, entertainment, hobbies)
- Lifestyle preferences (location, travel, climate, urban vs rural)
- Career aspirations (not just current role, but dream goals)
- Life milestones (family plans, education goals, life events)
- Values & beliefs (what matters to them)
- Social signals (communities, groups, networks they value)
- Financial goals & mindset
- Health & wellness interests
- Learning style & intellectual interests
- Communication preferences
- Work-life balance desires
- Growth areas & insecurities
- Hidden motivations (fear of, dreams of, wishes for)

Goal: Create 360° personal profile that enables authentic, meaningful connection
Strategy: Use this to personalize every interaction - emails, calls, offers, communications
Result: Candidate feels genuinely known and valued (not like a transaction)

Reports to: Relation Building Agent (for personalization)
Used by: Thunder, Interview Scheduler, Offer Generator (for authentic engagement)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from enum import Enum

from app.core.logging import logger
from app.models.candidate import Candidate
from app.services.candidate_memory_service import upsert_fact, get_memory

logger = logging.getLogger(__name__)

class PersonalDataCategory(str, Enum):
    """200+ personal data dimensions"""
    # Gaming & Entertainment (10 points)
    FAVORITE_GAMES = "favorite_games"
    GAMING_PLATFORMS = "gaming_platforms"
    ENTERTAINMENT_PREFERENCES = "entertainment_preferences"
    MOVIE_GENRES = "movie_genres"
    TV_SHOW_PREFERENCES = "tv_show_preferences"
    MUSIC_GENRES = "music_genres"
    PODCAST_TOPICS = "podcast_topics"
    BOOK_GENRES = "book_genres"
    STREAMING_SERVICES = "streaming_services"
    ESPORTS_INTEREST = "esports_interest"

    # Food & Dining (10 points)
    FAVORITE_CUISINES = "favorite_cuisines"
    DIETARY_RESTRICTIONS = "dietary_restrictions"
    RESTAURANT_TYPES = "restaurant_types"
    COOKING_INTEREST = "cooking_interest"
    COFFEE_ORDER = "coffee_order"
    ALCOHOL_PREFERENCES = "alcohol_preferences"
    SNACK_preferences = "snack_preferences"
    MEAL_TIMING = "meal_timing"
    FOOD_ADVENTURE_LEVEL = "food_adventure_level"
    FAVORITE_RESTAURANTS = "favorite_restaurants"

    # Travel & Location (15 points)
    CURRENT_LOCATION = "current_location"
    PREFERRED_CLIMATES = "preferred_climates"
    URBAN_VS_RURAL = "urban_vs_rural"
    TRAVEL_FREQUENCY = "travel_frequency"
    BUCKET_LIST_DESTINATIONS = "bucket_list_destinations"
    FAVORITE_CITIES = "favorite_cities"
    DREAM_COUNTRIES = "dream_countries"
    TRAVEL_STYLE = "travel_style"
    ADVENTURE_LEVEL = "adventure_level"
    FAMILY_TRAVEL_IMPORTANCE = "family_travel_importance"
    REMOTE_WORK_DESIRE = "remote_work_desire"
    RELOCATION_OPENNESS = "relocation_openness"
    NEIGHBORHOOD_PREFERENCES = "neighborhood_preferences"
    COMMUTE_TOLERANCE = "commute_tolerance"
    TIMEZONE_FLEXIBILITY = "timezone_flexibility"

    # Career Aspirations (20 points)
    DREAM_JOB_TITLE = "dream_job_title"
    DREAM_COMPANY = "dream_company"
    INDUSTRY_ASPIRATIONS = "industry_aspirations"
    LEADERSHIP_ASPIRATIONS = "leadership_aspirations"
    IMPACT_GOALS = "impact_goals"
    FINANCIAL_GOALS = "financial_goals"
    LEARNING_AMBITIONS = "learning_ambitions"
    SKILL_BUILDING_FOCUS = "skill_building_focus"
    BOARD_PARTICIPATION_DESIRE = "board_participation_desire"
    FOUNDER_ASPIRATIONS = "founder_aspirations"
    CONSULTING_INTEREST = "consulting_interest"
    SPEAKING_INTEREST = "speaking_interest"
    AUTHOR_ASPIRATIONS = "author_aspirations"
    MENTORSHIP_INTEREST = "mentorship_interest"
    THOUGHT_LEADER_DESIRE = "thought_leader_desire"
    WORK_AUTONOMY_NEEDS = "work_autonomy_needs"
    TEAM_SIZE_PREFERENCE = "team_size_preference"
    INDUSTRY_SWITCHING_OPENNESS = "industry_switching_openness"
    ROLE_FLEXIBILITY = "role_flexibility"
    LEGACY_GOALS = "legacy_goals"

    # Personal Life & Family (15 points)
    RELATIONSHIP_STATUS = "relationship_status"
    FAMILY_PLANS = "family_plans"
    CHILDREN_PLANS = "children_plans"
    PARENTING_PHILOSOPHY = "parenting_philosophy"
    SPOUSE_CAREER_IMPORTANCE = "spouse_career_importance"
    FAMILY_SUPPORT_SYSTEM = "family_support_system"
    AGING_PARENT_CARE = "aging_parent_care"
    CLOSE_RELATIONSHIPS = "close_relationships"
    FAMILY_TRADITIONS = "family_traditions"
    WORK_LIFE_BALANCE_PRIORITY = "work_life_balance_priority"
    FLEXIBILITY_NEEDS = "flexibility_needs"
    CAREGIVING_RESPONSIBILITIES = "caregiving_responsibilities"
    TIME_WITH_FAMILY = "time_with_family"
    SABBATICAL_INTEREST = "sabbatical_interest"
    LIFE_STAGE = "life_stage"

    # Values & Beliefs (15 points)
    CORE_VALUES = "core_values"
    ETHICAL_STANDARDS = "ethical_standards"
    ENVIRONMENTAL_COMMITMENT = "environmental_commitment"
    SOCIAL_CAUSES = "social_causes"
    DIVERSITY_INCLUSION_COMMITMENT = "diversity_inclusion_commitment"
    POLITICAL_LEANING = "political_leaning"
    RELIGIOUS_BELIEFS = "religious_beliefs"
    SPIRITUALITY_LEVEL = "spirituality_level"
    COMMUNITY_INVOLVEMENT = "community_involvement"
    CHARITABLE_FOCUS = "charitable_focus"
    TRANSPARENCY_IMPORTANCE = "transparency_importance"
    AUTHENTICITY_IMPORTANCE = "authenticity_importance"
    GROWTH_MINDSET = "growth_mindset"
    RISK_TOLERANCE = "risk_tolerance"
    SOCIAL_RESPONSIBILITY = "social_responsibility"

    # Health & Wellness (10 points)
    FITNESS_LEVEL = "fitness_level"
    EXERCISE_PREFERENCES = "exercise_preferences"
    SPORTS_INTERESTS = "sports_interests"
    NUTRITION_FOCUS = "nutrition_focus"
    MENTAL_HEALTH_PRIORITY = "mental_health_priority"
    SLEEP_HABITS = "sleep_habits"
    STRESS_MANAGEMENT = "stress_management"
    WELLNESS_INTERESTS = "wellness_interests"
    ENERGY_PATTERNS = "energy_patterns"
    HEALTH_CHALLENGES = "health_challenges"

    # Learning & Growth (12 points)
    LEARNING_STYLE = "learning_style"
    PREFERRED_LEARNING_FORMAT = "preferred_learning_format"
    SKILL_GAPS = "skill_gaps"
    CURIOSITY_AREAS = "curiosity_areas"
    CONFERENCE_INTEREST = "conference_interest"
    COURSE_TAKING = "course_taking"
    CERTIFICATION_GOALS = "certification_goals"
    MENTORSHIP_SOUGHT = "mentorship_sought"
    KNOWLEDGE_SEEKING = "knowledge_seeking"
    CHALLENGE_PREFERENCE = "challenge_preference"
    INNOVATION_INTEREST = "innovation_interest"
    EXPERIMENTATION_COMFORT = "experimentation_comfort"

    # Financial (10 points)
    SALARY_EXPECTATIONS = "salary_expectations"
    EQUITY_INTEREST = "equity_interest"
    BENEFITS_PRIORITIES = "benefits_priorities"
    FINANCIAL_INDEPENDENCE_GOAL = "financial_independence_goal"
    INVESTMENT_INTEREST = "investment_interest"
    WEALTH_BUILDING_FOCUS = "wealth_building_focus"
    SPENDING_STYLE = "spending_style"
    SAVING_RATE = "saving_rate"
    LUXURY_VS_PRACTICAL = "luxury_vs_practical"
    FINANCIAL_SECURITY_LEVEL = "financial_security_level"

    # Social & Community (12 points)
    SOCIAL_CIRCLE_SIZE = "social_circle_size"
    NETWORKING_COMFORT = "networking_comfort"
    COMMUNITY_GROUPS = "community_groups"
    PROFESSIONAL_NETWORKS = "professional_networks"
    FRIEND_GROUP_TYPE = "friend_group_type"
    EXTROVERSION_LEVEL = "extroversion_level"
    COLLABORATION_STYLE = "collaboration_style"
    FRIENDSHIP_DEPTH = "friendship_depth"
    SOCIAL_MEDIA_USAGE = "social_media_usage"
    INFLUENCER_INTEREST = "influencer_interest"
    COMMUNITY_LEADERSHIP = "community_leadership"
    TEAM_CULTURE_FIT = "team_culture_fit"

    # Work Preferences (10 points)
    OFFICE_VS_REMOTE = "office_vs_remote"
    COMMUNICATION_STYLE = "communication_style"
    MEETING_PREFERENCES = "meeting_preferences"
    FEEDBACK_STYLE = "feedback_style"
    MANAGEMENT_STYLE_PREFERENCE = "management_style_preference"
    AUTONOMY_VS_STRUCTURE = "autonomy_vs_structure"
    PROCESS_ORIENTATION = "process_orientation"
    CREATIVITY_IMPORTANCE = "creativity_importance"
    RISK_TAKING_AT_WORK = "risk_taking_at_work"
    COLLABORATION_PREFERENCE = "collaboration_preference"

    # Personal Quirks & Characteristics (10 points)
    HUMOR_STYLE = "humor_style"
    PERSONALITY_TYPE = "personality_type"
    COMMUNICATION_TONE = "communication_tone"
    DECISION_MAKING_STYLE = "decision_making_style"
    TIME_MANAGEMENT_STYLE = "time_management_style"
    ORGANIZATION_LEVEL = "organization_level"
    SPONTANEITY_LEVEL = "spontaneity_level"
    COMPETITIVENESS = "competitiveness"
    PERFECTIONISM_LEVEL = "perfectionism_level"
    UNIQUE_QUIRKS = "unique_quirks"

    # Hidden Motivations & Fears (15 points)
    BIGGEST_FEAR = "biggest_fear"
    IMPOSTOR_SYNDROME_LEVEL = "impostor_syndrome_level"
    APPROVAL_NEED = "approval_need"
    AUTONOMY_NEED = "autonomy_need"
    BELONGING_NEED = "belonging_need"
    ACHIEVEMENT_DRIVE = "achievement_drive"
    POWER_SEEKING = "power_seeking"
    SIGNIFICANCE_SEEKING = "significance_seeking"
    SECURITY_NEED = "security_need"
    ADVENTURE_SEEKING = "adventure_seeking"
    ESCAPE_DESIRES = "escape_desires"
    UNFULFILLED_DREAMS = "unfulfilled_dreams"
    REGRETS = "regrets"
    ASPIRATIONAL_SELF = "aspirational_self"
    AUTHENTICITY_GAPS = "authenticity_gaps"

    # Side Interests & Hobbies (10 points)
    HOBBIES = "hobbies"
    SIDE_PROJECTS = "side_projects"
    CREATIVE_INTERESTS = "creative_interests"
    OUTDOOR_ACTIVITIES = "outdoor_activities"
    INDOOR_ACTIVITIES = "indoor_activities"
    COLLECTING_INTERESTS = "collecting_interests"
    SPORTS_FANDOM = "sports_fandom"
    VOLUNTEER_INTERESTS = "volunteer_interests"
    ARTISTIC_PURSUITS = "artistic_pursuits"
    MAKER_INTERESTS = "maker_interests"

    # Communication & Connection (8 points)
    PREFERRED_COMMUNICATION = "preferred_communication"
    RESPONSE_TIME_EXPECTATIONS = "response_time_expectations"
    MEETING_FREQUENCY_PREFERENCE = "meeting_frequency_preference"
    DEEP_CONVERSATION_INTEREST = "deep_conversation_interest"
    SMALL_TALK_COMFORT = "small_talk_comfort"
    VULNERABILITY_COMFORT = "vulnerability_comfort"
    FEEDBACK_RECEIVING = "feedback_receiving"
    RELATIONSHIP_BUILDING_PACE = "relationship_building_pace"

class PersonalIntelligenceService:
    """
    Build 200+ data point personal profile for authentic relationship building.

    This is about understanding the PERSON, not just the professional.
    Goal: Make them feel genuinely known and valued.
    """

    @staticmethod
    async def extract_personal_profile(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        data_sources: Dict[str, Any],  # LinkedIn, GitHub, social, conversation, email
    ) -> Dict[str, Any]:
        """
        Extract comprehensive personal profile from all data sources.

        Data sources:
        - LinkedIn: Profile, interests, endorsements, activity
        - GitHub: Projects, interests, activity patterns
        - Social media: Twitter, Instagram, Facebook signals
        - Email/chat: Tone, personality signals
        - Conversation: What they say about themselves
        - Resume: Implicit interests from choices

        Returns: 200+ dimensional personal profile
        """
        try:
            profile = {
                "candidate_id": candidate_id,
                "extracted_at": datetime.now().isoformat(),
                "data_points": {},
                "completeness_score": 0.0,
            }

            # Extract from each data source
            linkedin_data = PersonalIntelligenceService._extract_from_linkedin(
                data_sources.get("linkedin", {})
            )
            github_data = PersonalIntelligenceService._extract_from_github(
                data_sources.get("github", {})
            )
            social_data = PersonalIntelligenceService._extract_from_social(
                data_sources.get("social", {})
            )
            conversation_data = PersonalIntelligenceService._extract_from_conversation(
                data_sources.get("conversation", "")
            )
            email_data = PersonalIntelligenceService._extract_from_email(
                data_sources.get("emails", [])
            )

            # Merge all sources
            profile["data_points"] = {
                **linkedin_data,
                **github_data,
                **social_data,
                **conversation_data,
                **email_data,
            }

            # Store all personal facts in memory
            facts_stored = await PersonalIntelligenceService._store_personal_facts(
                candidate_id, tenant_id, db, profile["data_points"]
            )

            profile["data_points_extracted"] = len(profile["data_points"])
            profile["facts_stored"] = facts_stored
            profile["completeness_score"] = min(
                1.0, len(profile["data_points"]) / 200  # Goal: 200 data points
            )

            return {
                "status": "success",
                "profile": profile,
                "summary": PersonalIntelligenceService._generate_profile_summary(
                    profile["data_points"]
                ),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Personal profile extraction error: {str(e)}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _extract_from_linkedin(linkedin_data: Dict) -> Dict[str, Any]:
        """Extract personal insights from LinkedIn profile."""
        points = {}

        # Career aspirations from profile
        if "headline" in linkedin_data:
            headline = linkedin_data["headline"].lower()
            if "founder" in headline or "entrepreneur" in headline:
                points["founder_aspirations"] = "high"
            if "leader" in headline or "director" in headline:
                points["leadership_aspirations"] = "high"

        # Interests from activity
        if "interests" in linkedin_data:
            points["professional_interests"] = linkedin_data["interests"]

        # Endorsements reveal skills they care about
        if "endorsements" in linkedin_data:
            top_skills = linkedin_data["endorsements"][:5]
            points["valued_skills"] = top_skills

        # Location preference
        if "location" in linkedin_data:
            points["current_location"] = linkedin_data["location"]

        # Education interests
        if "education" in linkedin_data:
            points["educational_background"] = linkedin_data["education"]

        return points

    @staticmethod
    def _extract_from_github(github_data: Dict) -> Dict[str, Any]:
        """Extract personal interests from GitHub activity."""
        points = {}

        # Starred repos reveal interests
        if "starred_repos" in github_data:
            interests = []
            for repo in github_data["starred_repos"][:20]:
                # Categorize by topic
                if "game" in repo.lower():
                    interests.append("gaming_interest")
                if "ai" in repo.lower() or "ml" in repo.lower():
                    interests.append("ai_interest")
                if "music" in repo.lower():
                    interests.append("music_interest")
                if "art" in repo.lower():
                    interests.append("creative_interest")

            points["github_interests"] = list(set(interests))

        # Contribution patterns
        if "contributions_per_day" in github_data:
            points["work_rhythm"] = github_data["contributions_per_day"]

        # Personal projects
        if "personal_repos" in github_data:
            points["side_projects"] = github_data["personal_repos"]

        return points

    @staticmethod
    def _extract_from_social(social_data: Dict) -> Dict[str, Any]:
        """Extract personal personality from social media."""
        points = {}

        # Twitter bio
        if "twitter_bio" in social_data:
            bio = social_data["twitter_bio"].lower()
            if "gaming" in bio or "gamer" in bio:
                points["gaming_passion"] = "high"
            if "travel" in bio:
                points["travel_passion"] = "high"
            if "foodie" in bio or "food" in bio:
                points["food_passion"] = "high"
            if "parent" in bio:
                points["family_focused"] = True
            if "coffee" in bio:
                points["coffee_culture"] = "enthusiast"

        # Tweet patterns reveal personality
        if "tweet_topics" in social_data:
            points["social_interests"] = social_data["tweet_topics"]

        # Instagram interests
        if "instagram_bio" in social_data:
            points["instagram_identity"] = social_data["instagram_bio"]

        return points

    @staticmethod
    def _extract_from_conversation(conversation_text: str) -> Dict[str, Any]:
        """Extract personal details from what they say about themselves."""
        points = {}
        text_lower = conversation_text.lower()

        # Travel
        if any(w in text_lower for w in ["travel", "trip", "visit", "explore", "adventure"]):
            points["travel_interest"] = "high"
        if any(w in text_lower for w in ["remote", "anywhere", "location independent"]):
            points["remote_work_desire"] = True

        # Family/relationships
        if any(w in text_lower for w in ["family", "kids", "children", "spouse", "partner"]):
            points["family_focused"] = True
        if "married" in text_lower or "relationship" in text_lower:
            points["relationship_status"] = "committed"

        # Career goals
        if any(w in text_lower for w in ["impact", "meaningful", "mission"]):
            points["impact_motivated"] = True
        if any(w in text_lower for w in ["learn", "grow", "develop"]):
            points["learning_focused"] = True
        if any(w in text_lower for w in ["lead", "manage", "team"]):
            points["leadership_interested"] = True

        # Hobbies
        if any(w in text_lower for w in ["game", "gaming", "esports"]):
            points["gaming_interest"] = "mentioned"
        if any(w in text_lower for w in ["run", "marathon", "fitness", "yoga"]):
            points["fitness_interest"] = "active"
        if any(w in text_lower for w in ["read", "book", "author"]):
            points["reading_interest"] = "strong"
        if any(w in text_lower for w in ["music", "instrument", "play"]):
            points["music_interest"] = "active"
        if any(w in text_lower for w in ["cook", "food", "recipe"]):
            points["cooking_interest"] = "active"

        # Values
        if any(w in text_lower for w in ["environment", "sustainable", "green"]):
            points["environmental_values"] = "high"
        if any(w in text_lower for w in ["diversity", "inclusion", "equality"]):
            points["social_justice_values"] = "high"

        return points

    @staticmethod
    def _extract_from_email(emails: List[str]) -> Dict[str, Any]:
        """Extract personality from email writing style."""
        points = {}

        if not emails:
            return points

        # Aggregate email characteristics
        avg_length = sum(len(e.split()) for e in emails) / len(emails)
        all_emails = " ".join(emails).lower()

        # Writing style
        if avg_length > 300:
            points["communication_style"] = "detailed"
        elif avg_length < 100:
            points["communication_style"] = "concise"
        else:
            points["communication_style"] = "balanced"

        # Tone
        if "!" in all_emails:
            points["enthusiasm_level"] = "high"
        if "?" in all_emails:
            points["curiosity_level"] = "high"

        # Personality hints
        if ":)" in all_emails or "😊" in all_emails:
            points["warmth_level"] = "high"
        if "FYI" in all_emails or "ASAP" in all_emails:
            points["professional_tone"] = "formal"

        return points

    @staticmethod
    async def _store_personal_facts(
        candidate_id: str, tenant_id: str, db: Session, data_points: Dict[str, Any]
    ) -> int:
        """Store all personal data points in candidate memory."""
        facts_stored = 0

        try:
            for category, value in data_points.items():
                if value is None or value == "":
                    continue

                upsert_fact(
                    db,
                    candidate_id,
                    tenant_id,
                    fact_category="PERSONAL",
                    fact_key=category,
                    fact_value=str(value),
                    confidence=0.8,  # Personal data is lower confidence (inferred)
                )
                facts_stored += 1

            db.commit()

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error storing personal facts: {str(e)}")
            db.rollback()

        return facts_stored

    @staticmethod
    def _generate_profile_summary(data_points: Dict[str, Any]) -> str:
        """Generate human-readable summary of personal profile."""
        summary = []

        # Interest highlights
        interests = []
        if data_points.get("gaming_interest"):
            interests.append("gaming")
        if data_points.get("travel_passion"):
            interests.append("travel")
        if data_points.get("cooking_interest"):
            interests.append("cooking")
        if data_points.get("fitness_interest"):
            interests.append("fitness")

        if interests:
            summary.append(f"Interests: {', '.join(interests)}")

        # Career
        if data_points.get("leadership_interested"):
            summary.append("Leadership-focused career aspirations")
        if data_points.get("learning_focused"):
            summary.append("Continuous learner and growth-seeker")
        if data_points.get("impact_motivated"):
            summary.append("Impact and meaning-driven")

        # Lifestyle
        if data_points.get("family_focused"):
            summary.append("Family-oriented")
        if data_points.get("remote_work_desire"):
            summary.append("Values location flexibility")
        if data_points.get("environmental_values") == "high":
            summary.append("Environmental values matter")

        # Personality
        communication = data_points.get("communication_style", "")
        if communication:
            summary.append(f"Communication style: {communication}")
        if data_points.get("enthusiasm_level") == "high":
            summary.append("Enthusiastic personality")

        return " | ".join(summary) if summary else "Personal profile extracted"

# ============== PERSONALIZATION ENGINE ==============

class PersonalizationEngine:
    """
    Use 200+ personal data points to customize every interaction.
    Goal: Make every email, call, offer feel personally tailored.
    """

    @staticmethod
    def generate_personalized_email_opening(
        candidate_data: Dict[str, Any], email_type: str
    ) -> str:
        """
        Generate personalized email opening based on their personal interests.

        email_type: "initial_outreach", "follow_up", "offer", "welcome"
        """
        # Use their interests to create genuine connection
        interests = []

        if candidate_data.get("gaming_interest"):
            interests.append("gaming")
        if candidate_data.get("travel_passion"):
            interests.append("travel")
        if candidate_data.get("learning_focused"):
            interests.append("growth")

        if not interests:
            return f"Hi {candidate_data.get('name', 'there')},"

        # Create personal connection
        if email_type == "initial_outreach":
            return (
                f"Hi {candidate_data.get('name', 'there')},\n\n"
                f"I saw your interest in {interests[0]} and your impressive track record in growth—"
                f"thought you'd be perfect for this opportunity."
            )
        elif email_type == "follow_up":
            return (
                f"Hi {candidate_data.get('name', 'there')},\n\n"
                f"Still excited about the possibility of working together. "
                f"I think you'd love our team's culture."
            )
        elif email_type == "offer":
            return (
                f"Hi {candidate_data.get('name', 'there')},\n\n"
                f"We've put together an offer that honors your {interests[0]}-focused goals "
                f"and values."
            )

        return f"Hi {candidate_data.get('name', 'there')},"

    @staticmethod
    def generate_personalized_offer_package(
        candidate_data: Dict[str, Any], base_offer: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Customize offer based on their personal values and needs.

        Use their data points to personalize:
        - Work schedule and flexibility
        - Remote vs office balance
        - Professional development budget
        - Team structure
        - Impact opportunity
        """
        offer = base_offer.copy()

        # If travel-focused: emphasize remote flexibility
        if candidate_data.get("travel_passion"):
            offer["remote_flexibility"] = "4 days/week remote, 1 flexible day"
            offer["travel_allowance"] = 5000  # Annual travel budget
            offer["sabbatical_policy"] = "3 weeks every 3 years"

        # If family-focused: emphasize flexibility
        if candidate_data.get("family_focused"):
            offer["parental_leave"] = "6 months full pay"
            offer["flexible_hours"] = True
            offer["school_calendar_aligned"] = True

        # If learning-focused: emphasize growth
        if candidate_data.get("learning_focused"):
            offer["education_budget"] = 10000  # Annual learning budget
            offer["conference_budget"] = 5000
            offer["mentorship_program"] = True
            offer["skill_development_path"] = True

        # If leadership-interested: emphasize growth trajectory
        if candidate_data.get("leadership_interested"):
            offer["leadership_track"] = "Path to director in 3 years"
            offer["team_to_manage"] = 3
            offer["strategy_participation"] = True

        # If impact-motivated: emphasize mission
        if candidate_data.get("impact_motivated"):
            offer["impact_metrics"] = "Direct measure of customer impact"
            offer["mission_alignment"] = True
            offer["social_impact_day"] = "2 days/year for causes"

        return offer

    @staticmethod
    def get_personalized_talking_points(
        candidate_data: Dict[str, Any],
    ) -> List[str]:
        """
        Get personalized talking points for interview/call.
        Use their personal interests to build rapport.
        """
        points = []

        # Gaming connection
        if candidate_data.get("gaming_interest"):
            points.append(
                "Talk about team collaboration/strategy - parallels to gaming communities"
            )

        # Travel
        if candidate_data.get("travel_passion"):
            points.append("Mention company's distributed team and remote-first culture")

        # Learning
        if candidate_data.get("learning_focused"):
            points.append(
                "Emphasize continuous learning culture and skill development opportunities"
            )

        # Family
        if candidate_data.get("family_focused"):
            points.append(
                "Share stories about team members' family moments and work-life balance"
            )

        # Leadership
        if candidate_data.get("leadership_interested"):
            points.append(
                "Walk through leadership development program and mentorship from executives"
            )

        # Impact
        if candidate_data.get("impact_motivated"):
            points.append(
                "Share customer impact stories and how this role directly affects outcomes"
            )

        return points if points else ["Build on their career growth aspirations"]
