"""
TIER 1 CRITICAL APIs: Thunder AI (8) + Candidate Core (12) = 20 endpoints
Launch-critical functionality for candidate management and AI integration
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import and_

# Import services
from ..services.thunder_service import ThunderService
from ..services.candidate_service import CandidateService
from ..services.candidate_memory_service import CandidateMemoryService
from ..services.candidate_scoring_service import CandidateScoringService
from ..services.ai_conversation_service import AIConversationService
from ..services.ai_recruiter_integration_service import AIRecruiterIntegrationService
from ..models.candidate import Candidate
from ..models.candidate_memory import CandidateMemory
from ..models.candidate_score import CandidateScore
from ..middleware.auth import require_tenant_context

# Initialize Blueprint
api_tier1_bp = Blueprint('api_tier1', __name__, url_prefix='/api/v1')

# ============================================================================
# THUNDER AI ENDPOINTS (8)
# ============================================================================

@api_tier1_bp.route('/ai-conversation', methods=['POST'])
@jwt_required()
@require_tenant_context
def ai_conversation(tenant_id):
    """Query Thunder AI conversation engine"""
    try:
        data = request.json
        candidate_id = data.get('candidate_id')
        query = data.get('query')
        context = data.get('context', {})

        service = AIConversationService()
        result = service.query_conversation(
            candidate_id=candidate_id,
            query=query,
            context=context,
            tenant_id=tenant_id
        )

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/ai-recruiter', methods=['POST'])
@jwt_required()
@require_tenant_context
def ai_recruiter_integration(tenant_id):
    """AI recruiter assignment engine"""
    try:
        data = request.json
        candidate_id = data.get('candidate_id')
        available_roles = data.get('available_roles', [])

        service = AIRecruiterIntegrationService()
        assignment = service.assign_recruiter(
            candidate_id=candidate_id,
            available_roles=available_roles,
            tenant_id=tenant_id
        )

        return jsonify(assignment), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/intent/detect', methods=['POST'])
@jwt_required()
@require_tenant_context
def detect_intent(tenant_id):
    """Detect candidate intent from conversation"""
    try:
        data = request.json
        text = data.get('text', '')
        conversation_id = data.get('conversation_id')

        service = AIConversationService()
        intent = service.detect_intent(
            text=text,
            conversation_id=conversation_id,
            tenant_id=tenant_id
        )

        return jsonify({'intent': intent}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/analytics/thunder', methods=['GET'])
@jwt_required()
@require_tenant_context
def thunder_analytics(tenant_id):
    """Thunder AI analytics and metrics"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        service = ThunderService()
        analytics = service.get_analytics(
            start_date=start_date,
            end_date=end_date,
            tenant_id=tenant_id
        )

        return jsonify(analytics), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/explain/<decision_id>', methods=['GET'])
@jwt_required()
@require_tenant_context
def thunder_explanation(tenant_id, decision_id):
    """Explain AI decision rationale"""
    try:
        service = ThunderService()
        explanation = service.explain_decision(
            decision_id=decision_id,
            tenant_id=tenant_id
        )

        return jsonify(explanation), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/ai-recruiter/pause', methods=['POST'])
@jwt_required()
@require_tenant_context
def thunder_pause(tenant_id):
    """Pause/resume AI recruiter"""
    try:
        data = request.json
        pause = data.get('pause', True)

        service = ThunderService()
        result = service.toggle_pause(pause=pause, tenant_id=tenant_id)

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/security/validate', methods=['POST'])
@jwt_required()
@require_tenant_context
def thunder_security(tenant_id):
    """Validate request security and compliance"""
    try:
        data = request.json
        service = ThunderService()
        validation = service.validate_security(
            request_data=data,
            tenant_id=tenant_id
        )

        return jsonify(validation), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/thunder/status', methods=['GET'])
@jwt_required()
@require_tenant_context
def thunder_service_status(tenant_id):
    """Check Thunder service status"""
    try:
        service = ThunderService()
        status = service.get_status(tenant_id=tenant_id)
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# CANDIDATE CORE ENDPOINTS (12)
# ============================================================================

@api_tier1_bp.route('/candidates', methods=['GET', 'POST'])
@jwt_required()
@require_tenant_context
def candidate_crud(tenant_id):
    """Candidate CRUD operations - List or Create"""
    try:
        if request.method == 'GET':
            filters = request.args.to_dict()
            candidates = Candidate.query.filter_by(tenant_id=tenant_id).all()
            return jsonify([c.to_dict() for c in candidates]), 200
        else:  # POST
            data = request.json
            service = CandidateService()
            candidate = service.create_candidate_safe(
                candidate_data=data,
                tenant_id=tenant_id
            )
            return jsonify(candidate.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/memory', methods=['GET', 'POST'])
@jwt_required()
@require_tenant_context
def candidate_memory_endpoint(tenant_id, candidate_id):
    """Get/store candidate memory and notes"""
    try:
        if request.method == 'GET':
            memories = CandidateMemory.query.filter_by(
                candidate_id=candidate_id,
                tenant_id=tenant_id
            ).all()
            return jsonify([m.to_dict() for m in memories]), 200
        else:  # POST
            data = request.json
            service = CandidateMemoryService()
            memory = service.store_memory(
                candidate_id=candidate_id,
                memory_type=data.get('memory_type'),
                content=data.get('content'),
                tenant_id=tenant_id
            )
            return jsonify(memory.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/score', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_scoring_endpoint(tenant_id, candidate_id):
    """Get candidate overall score"""
    try:
        service = CandidateScoringService()
        score = service.get_candidate_score(
            candidate_id=candidate_id,
            tenant_id=tenant_id
        )
        return jsonify(score), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/context', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_context_endpoint(tenant_id, candidate_id):
    """Get candidate context for AI processing"""
    try:
        service = CandidateService()
        context = service.get_candidate_context(
            candidate_id=candidate_id,
            tenant_id=tenant_id
        )
        return jsonify(context), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/pool', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_pool_endpoint(tenant_id):
    """Get candidate pool with filters"""
    try:
        status = request.args.get('status')
        role = request.args.get('role')
        location = request.args.get('location')

        service = CandidateService()
        pool = service.get_candidate_pool(
            tenant_id=tenant_id,
            status=status,
            role=role,
            location=location
        )
        return jsonify(pool), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/isolation', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_isolation_endpoint(tenant_id, candidate_id):
    """Verify tenant isolation for candidate"""
    try:
        candidate = Candidate.query.filter_by(
            id=candidate_id,
            tenant_id=tenant_id
        ).first_or_404()

        return jsonify({
            'candidate_id': candidate_id,
            'tenant_id': tenant_id,
            'isolated': candidate.tenant_id == tenant_id
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/ai', methods=['POST'])
@jwt_required()
@require_tenant_context
def candidate_ai_analysis(tenant_id, candidate_id):
    """Run AI analysis on candidate profile"""
    try:
        data = request.json
        service = CandidateService()
        analysis = service.run_ai_analysis(
            candidate_id=candidate_id,
            analysis_type=data.get('analysis_type', 'full'),
            tenant_id=tenant_id
        )
        return jsonify(analysis), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/abandonment', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_abandonment_endpoint(tenant_id, candidate_id):
    """Get abandonment risk score"""
    try:
        service = CandidateScoringService()
        risk = service.get_abandonment_risk(
            candidate_id=candidate_id,
            tenant_id=tenant_id
        )
        return jsonify(risk), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/desire', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_desire_endpoint(tenant_id, candidate_id):
    """Get candidate desire signals"""
    try:
        service = CandidateService()
        desire = service.get_desire_signals(
            candidate_id=candidate_id,
            tenant_id=tenant_id
        )
        return jsonify(desire), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/desire-profile', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_desire_profile_endpoint(tenant_id, candidate_id):
    """Get candidate desire profile"""
    try:
        service = CandidateService()
        profile = service.get_desire_profile(
            candidate_id=candidate_id,
            tenant_id=tenant_id
        )
        return jsonify(profile), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/drop-risk', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_drop_risk_endpoint(tenant_id, candidate_id):
    """Predict candidate drop risk"""
    try:
        service = CandidateScoringService()
        risk = service.predict_drop_risk(
            candidate_id=candidate_id,
            tenant_id=tenant_id
        )
        return jsonify(risk), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/engagement', methods=['GET'])
@jwt_required()
@require_tenant_context
def candidate_engagement_endpoint(tenant_id, candidate_id):
    """Get candidate engagement metrics"""
    try:
        service = CandidateService()
        metrics = service.get_engagement_metrics(
            candidate_id=candidate_id,
            tenant_id=tenant_id
        )
        return jsonify(metrics), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier1_bp.route('/candidates/<int:candidate_id>/apply', methods=['POST'])
@jwt_required()
@require_tenant_context
def candidate_apply_endpoint(tenant_id, candidate_id):
    """Submit candidate application for role"""
    try:
        data = request.json
        service = CandidateService()
        application = service.submit_application(
            candidate_id=candidate_id,
            role_id=data.get('role_id'),
            tenant_id=tenant_id
        )
        return jsonify(application), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
