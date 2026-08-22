"""Tests for all 11 advanced feature stories (S-352 through S-383)"""
import pytest
from datetime import datetime

class TestCoreEligibility:
    """S-352: Core Eligibility Gate"""
    def test_initiate_review(self):
        from app.services.core_eligibility_service import initiate_core_eligibility_review
        result = initiate_core_eligibility_review(None, "emp_001", "user_001")
        assert result["status"] == "AI_PENDING"
        assert result["employee_id"] == "emp_001"

class TestAIAssessor:
    """S-357: Core Eligibility AI Assessment"""
    def test_assess_eligibility(self):
        from app.services.ai_assessor_service import assess_core_eligibility
        result = assess_core_eligibility(None, "emp_001", {})
        assert result["ai_recommendation"] == "ELIGIBLE"
        assert result["confidence_score"] == 85

class TestPeerTrustPulse:
    """S-368: Peer Trust Pulse Survey"""
    def test_create_survey(self):
        from app.services.peer_trust_pulse_service import create_peer_survey
        result = create_peer_survey(None, "emp_001", 6)
        assert result["week"] == 6
        assert result["status"] == "ACTIVE"

class TestCurtisRule:
    """S-371: Curtis Rule — Partner Intent ML Engine"""
    def test_evaluate_partner(self):
        from app.services.curtis_rule_engine_service import evaluate_partner_intent
        result = evaluate_partner_intent(None, "partner_001")
        assert result["risk_category"] == "MODERATE"
        assert result["intent_score"] == 0.78

class TestEmployeeScorecard:
    """S-375: Individual Employee Scorecard — 35 KPI Live View"""
    def test_calculate_scorecard(self):
        from app.services.employee_scorecard_service import calculate_employee_scorecard
        result = calculate_employee_scorecard(None, "emp_001")
        assert result["overall_score"] == 82
        assert "billable_utilization" in result["kpis"]

class TestPredictiveDemand:
    """S-376: Predictive Demand ML Engine"""
    def test_forecast_demand(self):
        from app.services.predictive_demand_service import forecast_demand
        result = forecast_demand(None, 1, 90)
        assert result["total_predicted_demand"] == 45
        assert result["confidence_interval"] == 0.85

class TestSpecialtyRelease:
    """S-378: Specialty Client Release Approval Workflow"""
    def test_request_release(self):
        from app.services.specialty_release_service import request_specialty_release
        result = request_specialty_release(None, "emp_001", "cli_001", "Resource reallocation")
        assert result["status"] == "PENDING"
        assert result["employee_id"] == "emp_001"

class TestM365SSO:
    """S-379: Microsoft 365 SSO & Embedded Application Shell"""
    def test_initiate_sso(self):
        from app.services.m365_sso_service import initiate_m365_sso
        result = initiate_m365_sso(None, "user@company.com")
        assert "auth_url" in result
        assert "session_id" in result

class TestOutlookIntegration:
    """S-380: Embedded Outlook Email & Calendar Tab"""
    def test_send_email(self):
        from app.services.outlook_mail_service import send_outlook_email
        result = send_outlook_email(None, "user@company.com", "Test", "Message")
        assert result["status"] == "SENT"
        assert result["to"] == "user@company.com"

class TestTeamsIntegration:
    """S-381: Embedded Teams Chat Dock & Notification Center"""
    def test_send_message(self):
        from app.services.teams_chat_service import send_teams_message
        result = send_teams_message(None, "user_001", "Hello", "general")
        assert result["status"] == "DELIVERED"
        assert result["channel"] == "general"

class TestCheckInCadence:
    """S-383: Check-In Cadence Configuration by Org Level"""
    def test_configure_cadence(self):
        from app.services.checkin_cadence_service import configure_checkin_cadence
        result = configure_checkin_cadence(None, "BU_HEAD", 14, True)
        assert result["org_level"] == "BU_HEAD"
        assert result["frequency_days"] == 14
        assert result["enabled"] == True
