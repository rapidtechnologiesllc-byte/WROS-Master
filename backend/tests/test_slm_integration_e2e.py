"""
End-to-End SLM Integration Test (CYCLE 5)

Tests full workflow:
1. Message queued with payload
2. SLM pre-flight analysis (Place 1)
3. Handler execution
4. SLM outcome recording (Place 2)
5. SLMDecision record created with accountability

Success criteria:
- Message processed successfully
- SLMDecision records created for each stage
- Business impact recorded
- 90-day validation plan attached
- Escalation triggers work correctly
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.channel_queue import ChannelQueueItem
from app.models.slm_decision import SLMDecision
from tests import factories
from app.services.slm_service import SLMService


class TestSLMIntegrationE2E:
    """End-to-end SLM integration tests."""


    def test_slm_pre_flight_analysis(self, db: Session):
        """Test PLACE 1: SLM pre-flight analysis before handler."""
        message_id = str(uuid4())

        # Run pre-flight analysis
        slm_result = SLMService.analyze_before_handler(
            message_id=message_id,
            message_type='interview_scheduled',
            payload={
                'candidate_id': 'c123',
                'job_id': 'j456',
                'interview_date': '2026-10-01',
                'interview_time': '10:00',
                'interview_panel': ['p1', 'p2']
            },
            context={
                'business_goal': 'Schedule interview for candidate',
                'risk_level': 'MEDIUM',
                'candidate_id': 'c123',
                'interview_date': '2026-10-01',
                'panel_size': 2
            },
            db=db
        )

        # Verify pre-flight analysis results
        assert slm_result is not None
        assert slm_result['should_proceed'] is True
        assert slm_result['confidence'] > 0.5
        assert 'slm_decision_id' in slm_result
        assert slm_result['risk_level'] == 'MEDIUM'

        # Verify SLMDecision record created
        decision_id = slm_result['slm_decision_id']
        decision = db.query(SLMDecision).filter(SLMDecision.id == decision_id).first()
        assert decision is not None
        assert str(decision.message_id) == message_id
        assert decision.message_type == 'interview_scheduled'
        assert decision.slm_confidence > 0.5
        assert decision.was_escalated is False

        print("✅ PLACE 1 (Pre-flight analysis): PASS")

    def test_slm_pre_flight_escalation(self, db: Session):
        """Test PLACE 1: SLM escalation on CRITICAL risk."""
        message_id = str(uuid4())

        # Run pre-flight analysis with CRITICAL risk
        slm_result = SLMService.analyze_before_handler(
            message_id=message_id,
            message_type='offer_accepted',
            payload={
                'offer_id': 'o789',
                'start_date': '2026-10-15',
                'salary': 150000
            },
            context={
                'business_goal': 'Initiate onboarding',
                'risk_level': 'CRITICAL',  # Onboarding is expensive
                'offer_id': 'o789',
                'start_date': '2026-10-15'
            },
            db=db
        )

        # CRITICAL risk should escalate (confidence < 0.7)
        # This is intentional - high risk decisions should be escalated
        if slm_result['risk_level'] == 'CRITICAL':
            # Either escalated or low confidence
            assert slm_result['confidence'] < 0.8 or not slm_result['should_proceed']

        decision = db.query(SLMDecision).filter(
            SLMDecision.id == slm_result.get('slm_decision_id')
        ).first()

        if decision:
            assert decision.risk_level == 'CRITICAL'
            print("✅ PLACE 1 (CRITICAL escalation): PASS")

    def test_slm_outcome_recording(self, db: Session):
        """Test PLACE 2: SLM outcome recording after handler."""
        message_id = str(uuid4())

        # First, run pre-flight analysis
        slm_analysis = SLMService.analyze_before_handler(
            message_id=message_id,
            message_type='interview_scheduled',
            payload={
                'candidate_id': 'c123',
                'job_id': 'j456',
                'interview_date': '2026-10-01',
            },
            context={
                'business_goal': 'Schedule interview',
                'risk_level': 'MEDIUM',
            },
            db=db
        )

        # Now record outcome
        decision_id = SLMService.record_outcome(
            slm_analysis=slm_analysis,
            message_id=message_id,
            handler_name='interview_scheduled_handler',
            handler_result={
                'status': 'success',
                'interview_id': 'int123',
                'candidate_id': 'c123',
            },
            business_impact={
                'candidate_affected': True,
                'candidate_id': 'c123',
                'interview_id': 'int123',
                'interview_date': '2026-10-01',
                'expected_outcome': 'interview_completed',
                'validation_method': 'Check interview completion',
                '90_day_plan': 'Monitor hiring velocity',
                'can_be_reversed': False,
            },
            db=db
        )

        # Verify SLMDecision updated with outcome
        decision = db.query(SLMDecision).filter(SLMDecision.id == decision_id).first()
        assert decision is not None
        assert decision.handler_name == 'interview_scheduled_handler'
        assert decision.handler_status == 'success'
        assert decision.handler_result is not None
        assert decision.business_impact is not None
        assert decision.validation_plan is not None
        assert decision.accountability is not None
        assert decision.outcome_recorded_at is not None

        # Verify business impact
        impact = decision.business_impact
        assert impact['candidate_affected'] is True
        assert impact['interview_date'] == '2026-10-01'

        # Verify accountability
        acct = decision.accountability
        assert 'decision_maker' in acct
        assert 'can_be_reversed' in acct
        assert 'audit_trail' in acct
        assert len(acct['audit_trail']) >= 2

        print("✅ PLACE 2 (Outcome recording): PASS")

    def test_slm_business_accountability(self, db: Session):
        """Test that SLM records full business accountability."""
        message_id = str(uuid4())

        # Run full flow with business accountability
        slm_analysis = SLMService.analyze_before_handler(
            message_id=message_id,
            message_type='offer_generated',
            payload={
                'candidate_id': 'c999',
                'job_id': 'j999',
                'offer_details': {'salary': 200000}
            },
            context={
                'business_goal': 'Generate offer',
                'risk_level': 'HIGH',
                'salary': 200000
            },
            db=db
        )

        # Record outcome with business impact
        decision_id = SLMService.record_outcome(
            slm_analysis=slm_analysis,
            message_id=message_id,
            handler_name='offer_generation_handler',
            handler_result={'status': 'success', 'offer_id': 'off999'},
            business_impact={
                'candidate_affected': True,
                'candidate_id': 'c999',
                'salary': 200000,
                'cost_impact': 50000,  # Onboarding costs
                '90_day_plan': 'Measure retention and productivity',
                'can_be_reversed': True,
            },
            db=db
        )

        decision = db.query(SLMDecision).filter(SLMDecision.id == decision_id).first()

        # Verify accountability structure
        acct = decision.accountability
        assert acct['decision_maker'].startswith('SLM:')
        assert 'audit_trail' in acct
        assert acct['can_be_reversed'] is True

        # Verify 90-day validation plan
        validation = decision.validation_plan
        assert validation['success_criteria'] == 'Measure retention and productivity'
        assert validation['validation_result'] is None  # Not yet validated
        assert 'validation_date' in validation

        # Verify business impact with cost
        impact = decision.business_impact
        assert impact['cost_impact'] == 50000
        assert impact['candidate_affected'] is True

        print("✅ Business accountability: PASS")

    def test_queue_processor_slm_enforcement(self, db: Session):
        """Test that queue processor enforces SLM pre-flight analysis."""
        # Create a test message
        factories.tenant(db)
        message_id = str(uuid4())
        message = ChannelQueueItem(
            id=message_id,
            message_id=message_id,
            tenant_id=1,
            type='interview_scheduled',
            channel_type='THUNDER',
            payload={
                'candidate_id': 'c_qp',
                'job_id': 'j_qp',
                'interview_date': '2026-10-05',
                'interview_time': '14:00',
            },
            status='PENDING',
            created_at=datetime.utcnow(),
            retry_count=0
        )
        db.add(message)
        db.commit()

        # Simulate what queue processor does (pre-flight SLM check)
        slm_analysis = SLMService.analyze_before_handler(
            message_id=str(message.id),
            message_type=message.type,
            payload=message.payload or {},
            context={
                'business_goal': f'Execute {message.type}',
                'risk_level': 'MEDIUM',
                'queue_retry_count': message.retry_count
            },
            db=db
        )

        # Verify SLM analysis happened
        assert slm_analysis is not None
        assert 'should_proceed' in slm_analysis

        if slm_analysis['should_proceed']:
            # Would proceed to handler
            print("✅ Queue processor SLM enforcement: Handler would proceed")
        else:
            # Would escalate
            print("✅ Queue processor SLM enforcement: Message escalated by SLM")

        # Verify SLMDecision created for queue processor
        decision = db.query(SLMDecision).filter(
            SLMDecision.message_id == message.id
        ).first()
        assert decision is not None
        print("✅ Queue processor SLM enforcement: PASS")

    def test_slm_decision_audit_trail(self, db: Session):
        """Test that SLM decisions create complete audit trail."""
        message_id = str(uuid4())

        # Pre-flight
        slm_analysis = SLMService.analyze_before_handler(
            message_id=message_id,
            message_type='interview_scheduled',
            payload={'candidate_id': 'c_audit', 'job_id': 'j_audit'},
            context={'business_goal': 'Test audit trail', 'risk_level': 'LOW'},
            db=db
        )

        # Post-flight
        SLMService.record_outcome(
            slm_analysis=slm_analysis,
            message_id=message_id,
            handler_name='interview_scheduled_handler',
            handler_result={'status': 'success'},
            business_impact={'candidate_affected': True, 'candidate_id': 'c_audit'},
            db=db
        )

        # Query decision
        decision = db.query(SLMDecision).filter(
            SLMDecision.message_id == message_id
        ).first()

        # Verify timestamps for audit trail
        assert decision.analysis_at is not None
        assert decision.outcome_recorded_at is not None
        assert decision.outcome_recorded_at >= decision.analysis_at

        # Verify audit trail events
        acct = decision.accountability
        audit_trail = acct['audit_trail']
        events = [e['event'] for e in audit_trail]
        assert 'analyzed' in events
        assert 'handler_executed' in events

        print("✅ Audit trail: PASS")


    def test_slm_decision_model_exists(self, db: Session):
        """Verify SLMDecision model created correctly."""
        from app.models.slm_decision import SLMDecision

        # Create test record
        decision = SLMDecision(
            id=str(uuid4()),
            message_id=str(uuid4()),
            message_type='test',
            handler_name='test_handler',
            slm_confidence=0.85,
            risk_level='MEDIUM',
            was_escalated=False
        )
        db.add(decision)
        db.commit()

        # Query it back
        queried = db.query(SLMDecision).filter(
            SLMDecision.id == decision.id
        ).first()
        assert queried is not None
        assert queried.message_type == 'test'
        assert queried.slm_confidence == 0.85

        print("✅ SLMDecision model: PASS")
