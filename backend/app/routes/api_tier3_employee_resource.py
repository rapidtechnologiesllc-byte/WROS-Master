"""
TIER 3 APIs: Employee Core (8) + Resource Management (10) = 18 endpoints
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..services.employee_service import EmployeeService
from ..services.resource_service import ResourceService
from ..services.allocation_service import AllocationService
from ..middleware.auth import require_tenant_context

api_tier3_bp = Blueprint('api_tier3', __name__, url_prefix='/api/v1')

# EMPLOYEE ENDPOINTS (8)

@api_tier3_bp.route('/employees', methods=['GET', 'POST'])
@jwt_required()
@require_tenant_context
def employee_crud(tenant_id):
    """Employee CRUD operations"""
    try:
        if request.method == 'GET':
            service = EmployeeService()
            employees = service.list_employees(tenant_id)
            return jsonify(employees), 200
        else:
            data = request.json
            service = EmployeeService()
            employee = service.create_employee(data, tenant_id)
            return jsonify(employee), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/employees/<int:employee_id>/allocate', methods=['POST'])
@jwt_required()
@require_tenant_context
def employee_allocation(tenant_id, employee_id):
    """Allocate employee to project"""
    try:
        data = request.json
        service = AllocationService()
        allocation = service.allocate_employee(
            employee_id=employee_id,
            project_id=data.get('project_id'),
            percentage=data.get('percentage', 100),
            tenant_id=tenant_id
        )
        return jsonify(allocation), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/employees/<int:employee_id>/milestones', methods=['GET'])
@jwt_required()
@require_tenant_context
def employee_milestone(tenant_id, employee_id):
    """Get employee milestones"""
    try:
        service = EmployeeService()
        milestones = service.get_milestones(employee_id, tenant_id)
        return jsonify(milestones), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/employees/<int:employee_id>/availability', methods=['GET'])
@jwt_required()
@require_tenant_context
def availability_scoring(tenant_id, employee_id):
    """Calculate availability score"""
    try:
        service = AllocationService()
        score = service.calculate_availability_score(employee_id, tenant_id)
        return jsonify(score), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/allocate/recommend', methods=['POST'])
@jwt_required()
@require_tenant_context
def allocation_engine(tenant_id):
    """Get allocation recommendations"""
    try:
        data = request.json
        service = AllocationService()
        recommendations = service.get_recommendations(
            project_id=data.get('project_id'),
            skills_required=data.get('skills_required', []),
            tenant_id=tenant_id
        )
        return jsonify(recommendations), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/allocations', methods=['GET', 'POST'])
@jwt_required()
@require_tenant_context
def allocation_task(tenant_id):
    """Manage allocations"""
    try:
        if request.method == 'GET':
            service = AllocationService()
            allocations = service.list_allocations(tenant_id)
            return jsonify(allocations), 200
        else:
            data = request.json
            service = AllocationService()
            allocation = service.create_allocation(data, tenant_id)
            return jsonify(allocation), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/resources/match', methods=['POST'])
@jwt_required()
@require_tenant_context
def resource_matching(tenant_id):
    """Match resources to roles"""
    try:
        data = request.json
        service = ResourceService()
        matches = service.match_resources(
            role_id=data.get('role_id'),
            skills=data.get('skills', []),
            tenant_id=tenant_id
        )
        return jsonify(matches), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/employees/<int:employee_id>/refer', methods=['POST'])
@jwt_required()
@require_tenant_context
def employee_referral(tenant_id, employee_id):
    """Employee referral"""
    try:
        data = request.json
        service = EmployeeService()
        result = service.create_referral(
            employee_id=employee_id,
            referred_candidate_id=data.get('referred_candidate_id'),
            tenant_id=tenant_id
        )
        return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# RESOURCE MANAGEMENT ENDPOINTS (10)

@api_tier3_bp.route('/resources/availability', methods=['GET'])
@jwt_required()
@require_tenant_context
def resource_availability(tenant_id):
    """Get resource availability"""
    try:
        filters = request.args.to_dict()
        service = ResourceService()
        availability = service.get_availability(filters, tenant_id)
        return jsonify(availability), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/resources/pool', methods=['GET'])
@jwt_required()
@require_tenant_context
def resource_pool(tenant_id):
    """Get resource pool with filters"""
    try:
        filters = request.args.to_dict()
        service = ResourceService()
        pool = service.get_pool(filters, tenant_id)
        return jsonify(pool), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/skills/match', methods=['POST'])
@jwt_required()
@require_tenant_context
def skill_match(tenant_id):
    """Match skills to roles"""
    try:
        data = request.json
        service = ResourceService()
        matches = service.match_skills(
            required_skills=data.get('required_skills', []),
            tenant_id=tenant_id
        )
        return jsonify(matches), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/demand/forecast', methods=['GET'])
@jwt_required()
@require_tenant_context
def demand_forecast(tenant_id):
    """Forecast demand"""
    try:
        weeks_ahead = request.args.get('weeks_ahead', 12, type=int)
        service = ResourceService()
        forecast = service.forecast_demand(weeks_ahead, tenant_id)
        return jsonify(forecast), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/bench', methods=['GET'])
@jwt_required()
@require_tenant_context
def bench_tracking(tenant_id):
    """Get bench tracking data"""
    try:
        service = ResourceService()
        bench = service.get_bench_data(tenant_id)
        return jsonify(bench), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/utilization', methods=['GET'])
@jwt_required()
@require_tenant_context
def utilization_tracking(tenant_id):
    """Get utilization metrics"""
    try:
        filters = request.args.to_dict()
        service = ResourceService()
        utilization = service.get_utilization(filters, tenant_id)
        return jsonify(utilization), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/capacity', methods=['GET'])
@jwt_required()
@require_tenant_context
def capacity_planning(tenant_id):
    """Get capacity planning data"""
    try:
        service = ResourceService()
        capacity = service.get_capacity_plan(tenant_id)
        return jsonify(capacity), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/assign/optimize', methods=['POST'])
@jwt_required()
@require_tenant_context
def assignment_optimization(tenant_id):
    """Get assignment optimization recommendations"""
    try:
        data = request.json
        service = AllocationService()
        optimizations = service.optimize_assignments(
            constraints=data.get('constraints', {}),
            tenant_id=tenant_id
        )
        return jsonify(optimizations), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/core-pull/conflict', methods=['GET'])
@jwt_required()
@require_tenant_context
def core_pull_conflict(tenant_id):
    """Resolve core vs pull conflicts"""
    try:
        service = ResourceService()
        conflicts = service.resolve_core_pull_conflicts(tenant_id)
        return jsonify(conflicts), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/demand/gap', methods=['GET'])
@jwt_required()
@require_tenant_context
def demand_gap(tenant_id):
    """Get demand-supply gap analysis"""
    try:
        service = ResourceService()
        gaps = service.analyze_demand_gaps(tenant_id)
        return jsonify(gaps), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_tier3_bp.route('/employees/<int:employee_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
@require_tenant_context
def employee_detail(tenant_id, employee_id):
    """Get/update/delete employee"""
    try:
        service = EmployeeService()
        if request.method == 'GET':
            employee = service.get_employee(employee_id, tenant_id)
            return jsonify(employee), 200
        elif request.method == 'PUT':
            employee = service.update_employee(employee_id, request.json, tenant_id)
            return jsonify(employee), 200
        else:
            service.delete_employee(employee_id, tenant_id)
            return '', 204
    except Exception as e:
        return jsonify({'error': str(e)}), 500
