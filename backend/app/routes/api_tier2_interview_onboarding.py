"""
TIER 2 APIs: Interview Workflows (10) + Onboarding (6) = 16 endpoints
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from ..services.interview_service import InterviewService
from ..services.onboarding_service import OnboardingService
from ..services.calendar_service import CalendarService
from ..middleware.auth import require_tenant_context

api_tier2_bp = Blueprint('api_tier2', __name__, url_prefix='/api/v1')

# INTERVIEW ENDPOINTS (10)

@api_tier2_bp.route('/interviews/availability', methods=['GET', 'POST'])
@jwt_required()
@require_tenant_context
def interview_availability(tenant_id):
    """Get/set interview availability slots"""
    try:
        if request.method == 'GET':
            candidate_id = request.args.get('candidate_id')
            service = InterviewService()
            availability = service.get_availability(candidate_id, tenant_id)
            return jsonify(availability), 200
        else:
            data = request.json
            service = InterviewService()
            slot = service.add_availability_slot(
                candidate_id=data.get('candidate_id'),
                date=data.get('date'),
                time=data.get('time'),
                tenant_id=tenant_id
            )
            return jsonify(slot), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/interviews/<int:interview_id>/confirm', methods=['POST'])
@jwt_required()
@require_tenant_context
def interview_confirmation(tenant_id, interview_id):
    """Confirm interview"""
    try:
        data = request.json
        service = InterviewService()
        result = service.confirm_interview(
            interview_id=interview_id,
            confirmed=data.get('confirm', True),
            tenant_id=tenant_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/interviews/<int:interview_id>/remind', methods=['POST'])
@jwt_required()
@require_tenant_context
def interview_reminder(tenant_id, interview_id):
    """Send interview reminder"""
    try:
        service = InterviewService()
        result = service.send_reminder(interview_id, tenant_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/interviews/<int:interview_id>/reschedule', methods=['POST'])
@jwt_required()
@require_tenant_context
def interview_reschedule(tenant_id, interview_id):
    """Reschedule interview"""
    try:
        data = request.json
        service = InterviewService()
        result = service.reschedule_interview(
            interview_id=interview_id,
            new_date=data.get('new_date'),
            new_time=data.get('new_time'),
            tenant_id=tenant_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/calendar/match', methods=['POST'])
@jwt_required()
@require_tenant_context
def calendar_matching(tenant_id):
    """Find matching calendar slots for interviews"""
    try:
        data = request.json
        service = CalendarService()
        matches = service.find_matching_slots(
            interviewer_ids=data.get('interviewer_ids', []),
            candidate_id=data.get('candidate_id'),
            tenant_id=tenant_id
        )
        return jsonify(matches), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/engagement/email', methods=['POST'])
@jwt_required()
@require_tenant_context
def email_engagement(tenant_id):
    """Send first engagement email"""
    try:
        data = request.json
        service = InterviewService()
        result = service.send_engagement_email(
            candidate_id=data.get('candidate_id'),
            template=data.get('template', 'default'),
            tenant_id=tenant_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/followup', methods=['POST'])
@jwt_required()
@require_tenant_context
def followup_create(tenant_id):
    """Create follow-up action"""
    try:
        data = request.json
        service = InterviewService()
        followup = service.create_followup(
            candidate_id=data.get('candidate_id'),
            action_type=data.get('action_type'),
            due_date=data.get('due_date'),
            tenant_id=tenant_id
        )
        return jsonify(followup), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/followup/schedule', methods=['POST'])
@jwt_required()
@require_tenant_context
def followup_scheduler(tenant_id):
    """Schedule follow-ups"""
    try:
        data = request.json
        service = InterviewService()
        result = service.schedule_followups(
            candidate_id=data.get('candidate_id'),
            schedule=data.get('schedule', []),
            tenant_id=tenant_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/conversations/<int:conversation_id>/state', methods=['GET'])
@jwt_required()
@require_tenant_context
def conversation_state(tenant_id, conversation_id):
    """Get conversation state"""
    try:
        service = InterviewService()
        state = service.get_conversation_state(conversation_id, tenant_id)
        return jsonify(state), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Additional interview endpoint
@api_tier2_bp.route('/interviews', methods=['GET'])
@jwt_required()
@require_tenant_context
def list_interviews(tenant_id):
    """List all interviews"""
    try:
        candidate_id = request.args.get('candidate_id')
        service = InterviewService()
        interviews = service.list_interviews(candidate_id, tenant_id)
        return jsonify(interviews), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ONBOARDING ENDPOINTS (6)

@api_tier2_bp.route('/onboarding/start', methods=['POST'])
@jwt_required()
@require_tenant_context
def onboarding_start(tenant_id):
    """Start onboarding process"""
    try:
        data = request.json
        service = OnboardingService()
        onboarding = service.start_onboarding(
            employee_id=data.get('employee_id'),
            tenant_id=tenant_id
        )
        return jsonify(onboarding), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/onboarding/documents', methods=['GET', 'POST'])
@jwt_required()
@require_tenant_context
def document_task(tenant_id):
    """Manage onboarding documents"""
    try:
        if request.method == 'GET':
            employee_id = request.args.get('employee_id')
            service = OnboardingService()
            documents = service.list_documents(employee_id, tenant_id)
            return jsonify(documents), 200
        else:
            data = request.json
            service = OnboardingService()
            doc = service.add_document(
                employee_id=data.get('employee_id'),
                document_type=data.get('document_type'),
                document_url=data.get('document_url'),
                tenant_id=tenant_id
            )
            return jsonify(doc), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/onboarding/portal/<int:employee_id>', methods=['GET'])
@jwt_required()
@require_tenant_context
def onboarding_portal(tenant_id, employee_id):
    """Get onboarding portal access"""
    try:
        service = OnboardingService()
        portal_data = service.get_portal_data(employee_id, tenant_id)
        return jsonify(portal_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/onboarding/buddy/graduate', methods=['POST'])
@jwt_required()
@require_tenant_context
def buddy_program_graduation(tenant_id):
    """Graduate from buddy program"""
    try:
        data = request.json
        service = OnboardingService()
        result = service.graduate_from_buddy_program(
            employee_id=data.get('employee_id'),
            tenant_id=tenant_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/onboarding/checkins', methods=['GET', 'POST'])
@jwt_required()
@require_tenant_context
def checkin_cadence(tenant_id):
    """Manage check-in schedule"""
    try:
        if request.method == 'GET':
            employee_id = request.args.get('employee_id')
            service = OnboardingService()
            checkins = service.get_checkins(employee_id, tenant_id)
            return jsonify(checkins), 200
        else:
            data = request.json
            service = OnboardingService()
            result = service.set_checkin_cadence(
                employee_id=data.get('employee_id'),
                frequency=data.get('frequency'),
                tenant_id=tenant_id
            )
            return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/onboarding/notify', methods=['POST'])
@jwt_required()
@require_tenant_context
def onboarding_notify(tenant_id):
    """Send onboarding notifications"""
    try:
        data = request.json
        service = OnboardingService()
        result = service.send_notification(
            employee_id=data.get('employee_id'),
            step=data.get('step'),
            tenant_id=tenant_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier2_bp.route('/onboarding/progress', methods=['GET'])
@jwt_required()
@require_tenant_context
def onboarding_progress(tenant_id):
    """Get onboarding progress"""
    try:
        employee_id = request.args.get('employee_id')
        service = OnboardingService()
        progress = service.get_progress(employee_id, tenant_id)
        return jsonify(progress), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
