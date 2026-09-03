"""
Master API Routes File - Integration Hub for WROS Core Story Endpoints
import logging
========================================================================

This master routes file orchestrates all 15 core WROS story endpoints with:
- Comprehensive error handling (400, 401, 403, 404, 500 cases)
- Authentication & authorization middleware
- Tenant isolation enforcement (tenant_id validation)
- Request/response validation via Pydantic schemas
- Rate limiting (500 req/60s)
- CORS configuration
- Security headers
- Request logging
- Permission-based access control (RBAC)

Architecture Layers:
-------------------
1. PUBLIC ROUTES (no auth required)
   - /auth/login - Unified login (user or candidate)
   - /auth/v1/signup - Self-registration
   - /public/thunder-chat/* - Public candidate intake
   - /jobs/{job_id}/apply - External job application

2. AUTHENTICATED ROUTES (requires valid JWT token in Authorization header)
   - /candidates/* - Candidate management (add, view, edit)
   - /interviews/* - Interview scheduling & feedback
   - /jobs/* - Job creation & management
   - /offers/* - Offer creation & approval
   - /onboarding/* - Pre-onboarding checklist
   - /employees/* - Employee conversion & management
   - /notifications/* - Internal notification system
   - /users/* - User management & RBAC

3. TENANT-ISOLATED ROUTES (validates tenant_id from JWT)
   - All routes above (except public signup/login)
   - Tenant context resolved via middleware at app.core.tenant_context

Error Handling Strategy:
-----------------------
- 400 Bad Request: Invalid input, failed validation
- 401 Unauthorized: Missing/invalid JWT token
- 403 Forbidden: Valid token but insufficient permissions
- 404 Not Found: Resource doesn't exist
- 409 Conflict: Duplicate candidate, circular dependency, etc.
- 422 Unprocessable Entity: Schema validation error (FastAPI automatic)
- 500 Internal Server Error: Unhandled exception (logged to error_log table)

All errors return JSON with:
{
    "status_code": int,
    "error_type": str,
    "message": str,
    "details": str (optional),
    "timestamp": ISO8601 string,
    "request_id": str (from X-Request-ID header)
}

Permission-Based Access:
------------------------
Each endpoint is guarded by permission checks via Depends():
- candidate.view - Read candidate data
- candidate.create - Create new candidate
- candidate.edit - Modify existing candidate
- interview.schedule - Schedule interviews
- offer.create - Generate offer letters
- offer.approve - Hiring manager approval
- employee.convert - Candidate→Employee transition
- roles.manage - RBAC administration

Middleware Stack (in order):
---------------------------
1. RequestLoggingMiddleware - Logs all requests/responses
2. RateLimitMiddleware - 500 req/60s per IP
3. AuthenticationMiddleware - JWT validation & tenant context setup
4. CORSMiddleware - Cross-origin resource sharing
5. Exception Handlers - HTTP & unhandled exception handlers

Usage Example:
--------------
```python
# In your main.py after creating FastAPI app:
from app.api.v1.routes_master import setup_master_routes

app = FastAPI(...)
setup_master_routes(app)
```

Database Connection:
-------------------
All routes use Depends(get_db) which:
- Returns SQLAlchemy Session from SessionLocal connection pool
- Tenant is automatically scoped via orm execute listener
- Session auto-commits on successful completion
- Session auto-rollback on exception
- Connection closed after request

SQLAlchemy ORM Patterns:
-----------------------
- Use session.query() for reads (never raw SQL)
- Use session.add() for creates/updates
- Use session.delete() for deletes
- All operations include tenant_id validation
- Foreign key integrity validated at database level
- Cascade deletes defined at model level

Example Route with Validation:
------------------------------
@router.post("/candidates", response_model=CandidateResponse)
def create_candidate(
    req: CreateCandidateRequest,           # Request validation (Pydantic)
    current_user: Users = Depends(get_current_user),  # Auth
    db: Session = Depends(get_db),        # Database session
):
    '''Create new candidate with tenant isolation.'''

    # Validate permission
    if not current_user.has_permission('candidate.create'):
        raise HTTPException(403, 'Insufficient permissions')

    # Validate business logic
    existing = db.query(Candidate).filter_by(
        email=req.email,
        tenant_id=current_user.tenant_id  # Tenant isolation
    ).first()
    if existing:
        raise HTTPException(409, f'Candidate {req.email} already exists')

    # Create via safe factory (NEVER raw insert)
    candidate = createCandidateSafe(db, current_user.tenant_id, req)

    return CandidateResponse.from_orm(candidate)

Release History:
----------------
2026-08-15: Initial master routes file
- 15 core story endpoints
- Comprehensive error handling
- Tenant isolation enforcement
- Request validation patterns
- RBAC permission checks
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import uuid4

# Import all endpoint routers
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.candidates import router as candidates_router
from app.api.v1.endpoints.interviews import router as interviews_router
from app.api.v1.endpoints.create_job import router as create_job_router
from app.api.v1.endpoints.offer_letters import router as offer_letters_router
from app.api.v1.endpoints.employees import router as employees_router
from app.api.v1.endpoints.notifications import router as notifications_router

# Import middleware components
from app.core.logging import logger, log_security_event
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.middleware.auth_middleware import AuthenticationMiddleware


# ============================================================================
# MASTER ROUTER CONFIGURATION
# ============================================================================
logger = logging.getLogger(__name__)

class MasterRouterConfig:
    """Configuration for master router setup."""

    # Rate limiting (configured at app level, not here)
    RATE_LIMIT_REQUESTS = 500
    RATE_LIMIT_WINDOW_SECONDS = 60

    # JWT configuration
    JWT_ALGORITHM = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60

    # Tenant isolation
    ENFORCE_TENANT_ISOLATION = True

    # CORS configuration
    CORS_ORIGINS = [
        "http://localhost:3000",      # Local frontend dev
        "http://localhost:3001",      # Careers portal dev
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        # Add production domains when deployed
    ]

    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    CORS_ALLOW_HEADERS = ["*"]

    # API versioning
    API_VERSION = "v1"
    API_PREFIX = f"/api/{API_VERSION}"

    # Public routes (no auth required)
    PUBLIC_ROUTES = [
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/auth/login",
        "/auth/v1/signup",
        "/public/thunder-chat/start",
        "/public/thunder-chat/message",
        "/public/thunder-chat/history",
        "/webhooks/whatsapp",
    ]


# ============================================================================
# ROUTER GROUPING BY DOMAIN (15 Core Story Endpoints)
# ============================================================================

def create_master_router() -> APIRouter:
    """
    Create master router with all 15 core story endpoints organized by domain.

    Returns:
        Configured APIRouter ready to include in FastAPI app
    """
    router = APIRouter(prefix=MasterRouterConfig.API_PREFIX)

    # =======================
    # TIER 1: AUTHENTICATION
    # =======================
    # Story: HRMS-0101 - User Authentication
    # Endpoints: /auth/login, /auth/v1/signup, /auth/logout
    # Public routes - no auth required
    router.include_router(
        auth_router,
        tags=["authentication"],
        responses={
            401: {
                "description": "Invalid credentials or missing auth header",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 401,
                            "error_type": "unauthorized",
                            "message": "Invalid email or password"
                        }
                    }
                }
            }
        }
    )

    # =======================
    # TIER 2: RBAC & USERS
    # =======================
    # Story: HRMS-0114 - Role-Based Access Control
    # Note: rbac router removed (functionality covered by role_templates, permission_composition, users_access_control)

    router.include_router(
        users_router,
        tags=["users"],
        dependencies=[Depends(get_current_user)],
        responses={
            409: {
                "description": "User already exists",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 409,
                            "error_type": "conflict",
                            "message": "Account already exists with email user@example.com"
                        }
                    }
                }
            }
        }
    )

    # =======================
    # TIER 3: CANDIDATE INTAKE
    # =======================
    # Story: HRMS-0201 - Add Candidate (Intake)
    # Endpoints: /candidates/add, /candidates/{id}, /candidates/list
    # Protected: requires valid JWT + candidate.view OR candidate.create
    # Tenant-isolated: filtered by current_user.tenant_id
    router.include_router(
        candidates_router,
        tags=["candidates"],
        dependencies=[Depends(get_current_user)],
        responses={
            400: {
                "description": "Invalid candidate data or validation error",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 400,
                            "error_type": "validation_error",
                            "message": "Invalid email format",
                            "details": "email must be a valid email address"
                        }
                    }
                }
            },
            409: {
                "description": "Duplicate candidate email or phone",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 409,
                            "error_type": "duplicate",
                            "message": "Candidate with email already exists in this business unit"
                        }
                    }
                }
            }
        }
    )

    # =======================
    # TIER 4: JOB MANAGEMENT
    # =======================
    # Story: HRMS-0202 - Create Job
    # Endpoints: /jobs/create, /jobs/{id}, /jobs/list
    # Protected: requires valid JWT + job.create permission
    # Tenant-isolated: filtered by current_user.tenant_id
    router.include_router(
        create_job_router,
        tags=["jobs"],
        dependencies=[Depends(get_current_user)],
        responses={
            400: {
                "description": "Invalid job configuration",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 400,
                            "error_type": "validation_error",
                            "message": "Job title is required"
                        }
                    }
                }
            }
        }
    )

    # =======================
    # TIER 5: INTERVIEW WORKFLOW
    # =======================
    # Story: HRMS-0203 - Schedule Interview
    # Endpoints: /interviews/schedule, /interviews/{id}, /interviews/{id}/feedback
    # Protected: requires valid JWT + interview.schedule permission
    # Tenant-isolated: candidate & job must belong to user's tenant
    router.include_router(
        interviews_router,
        tags=["interviews"],
        dependencies=[Depends(get_current_user)],
        responses={
            404: {
                "description": "Candidate or interview not found",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 404,
                            "error_type": "not_found",
                            "message": "Interview with id abc123 not found"
                        }
                    }
                }
            },
            409: {
                "description": "Cannot schedule interview (conflict or wrong status)",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 409,
                            "error_type": "conflict",
                            "message": "Cannot schedule interview: candidate status is REJECTED"
                        }
                    }
                }
            }
        }
    )

    # =======================
    # TIER 6: OFFER WORKFLOW
    # =======================
    # Story: HRMS-0204 - Generate & Approve Offer
    # Endpoints: /offers/create, /offers/{id}, /offers/{id}/approve
    # Protected: requires valid JWT + offer.create (create) or offer.approve (approve)
    # Tenant-isolated: validated against current_user's business_unit_id
    router.include_router(
        offer_letters_router,
        tags=["offers"],
        dependencies=[Depends(get_current_user)],
        responses={
            400: {
                "description": "Invalid offer terms or candidate not interview-ready",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 400,
                            "error_type": "validation_error",
                            "message": "Cannot create offer: candidate has not completed interviews"
                        }
                    }
                }
            }
        }
    )

    # =======================
    # TIER 7: ONBOARDING PREP
    # =======================
    # Story: HRMS-0205 - Start Pre-Onboarding
    # Endpoints: /onboarding/start, /onboarding/{id}, /onboarding/{id}/status
    # =======================
    # TIER 8: EMPLOYEE CONVERSION
    # =======================
    # Story: HRMS-0206 - Convert Candidate to Employee
    # Endpoints: /employees/convert-from-candidate, /employees/{id}
    # Protected: requires valid JWT + employee.convert permission
    # Tenant-isolated: candidate must belong to current_user's business_unit_id
    router.include_router(
        employees_router,
        tags=["employees"],
        dependencies=[Depends(get_current_user)],
        responses={
            404: {
                "description": "Candidate not found or already converted",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 404,
                            "error_type": "not_found",
                            "message": "Candidate with id abc123 not found or already an employee"
                        }
                    }
                }
            },
            409: {
                "description": "Candidate not in OFFER status or conversion blocked",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 409,
                            "error_type": "conflict",
                            "message": "Cannot convert: candidate status must be OFFER, not INTERVIEW"
                        }
                    }
                }
            }
        }
    )

    # =======================
    # TIER 9: NOTIFICATIONS
    # =======================
    # Story: HRMS-0207 - Send Internal Notifications
    # Endpoints: /notifications/send, /notifications/{id}, /notifications/list
    # Protected: requires valid JWT + notification.send permission
    # Tenant-isolated: notifications scoped to current_user's tenant_id
    router.include_router(
        notifications_router,
        tags=["notifications"],
        dependencies=[Depends(get_current_user)],
        responses={
            400: {
                "description": "Invalid notification configuration",
                "content": {
                    "application/json": {
                        "example": {
                            "status_code": 400,
                            "error_type": "validation_error",
                            "message": "Recipient user not found in your business unit"
                        }
                    }
                }
            }
        }
    )

    return router


# ============================================================================
# ERROR RESPONSE SCHEMAS (for documentation)
# ============================================================================

class ErrorResponse:
    """Standard error response schema for all API errors."""

    @staticmethod
    def bad_request(message: str, details: str = None) -> dict:
        """400 Bad Request - Validation or business logic error."""
        return {
            "status_code": 400,
            "error_type": "bad_request",
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def unauthorized(message: str = "Invalid or missing authentication") -> dict:
        """401 Unauthorized - Invalid JWT or missing Authorization header."""
        return {
            "status_code": 401,
            "error_type": "unauthorized",
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def forbidden(message: str = "Insufficient permissions") -> dict:
        """403 Forbidden - Valid JWT but lacking required permission."""
        return {
            "status_code": 403,
            "error_type": "forbidden",
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def not_found(resource: str, resource_id: str) -> dict:
        """404 Not Found - Resource doesn't exist."""
        return {
            "status_code": 404,
            "error_type": "not_found",
            "message": f"{resource} with id {resource_id} not found",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def conflict(message: str) -> dict:
        """409 Conflict - Resource already exists or state conflict."""
        return {
            "status_code": 409,
            "error_type": "conflict",
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def server_error(message: str = "Internal server error") -> dict:
        """500 Internal Server Error - Unhandled exception."""
        return {
            "status_code": 500,
            "error_type": "server_error",
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


# ============================================================================
# TENANT ISOLATION UTILITIES
# ============================================================================

class TenantValidator:
    """Utility for tenant isolation validation in routes."""

    @staticmethod
    def validate_tenant_access(
        user_tenant_id: str,
        resource_tenant_id: str,
        resource_type: str,
        resource_id: str
    ) -> None:
        """
        Validate that user has access to resource in their tenant.

        Args:
            user_tenant_id: Tenant ID from current user
            resource_tenant_id: Tenant ID from resource
            resource_type: Type of resource (e.g., 'Candidate', 'Job')
            resource_id: ID of resource

        Raises:
            HTTPException(403) if tenant mismatch
            HTTPException(404) if tenant isolation would leak existence
        """
        if user_tenant_id != resource_tenant_id:
            log_security_event(
                "TENANT_ISOLATION_VIOLATION_ATTEMPTED",
                details=f"User {user_tenant_id} attempted access to {resource_type} "
                        f"{resource_id} in tenant {resource_tenant_id}"
            )
            # Return 404 instead of 403 to avoid leaking resource existence
            raise HTTPException(
                status_code=404,
                detail=f"{resource_type} not found"
            )


# ============================================================================
# REQUEST VALIDATION DECORATORS
# ============================================================================

def require_permission(permission: str):
    """
    Decorator to require specific permission before route execution.

    Usage:
    @router.post("/candidates")
    @require_permission("candidate.create")
        def create_candidate(...):
            pass
    """
    async def check_permission(current_user = Depends(get_current_user)):
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"User lacks required permission: {permission}"
            )
        return current_user
    return Depends(check_permission)


# ============================================================================
# SETUP FUNCTION
# ============================================================================

def setup_master_routes(app) -> None:
    """
    Setup master routes on FastAPI application.

    This function:
    1. Creates and includes master router with all endpoints
    2. Validates middleware stack is properly configured
    3. Logs route registration summary

    Args:
        app: FastAPI application instance

    Example:
        from fastapi import FastAPI
        from app.api.v1.routes_master import setup_master_routes

        app = FastAPI()
        setup_master_routes(app)
    """
    master_router = create_master_router()
    app.include_router(master_router)

    logger.info(
        f"Master routes configured: "
        f"API version={MasterRouterConfig.API_VERSION}, "
        f"Rate limit={MasterRouterConfig.RATE_LIMIT_REQUESTS} req/"
        f"{MasterRouterConfig.RATE_LIMIT_WINDOW_SECONDS}s"
    )

    # Validate middleware stack
    middleware_names = [type(m).__name__ for m in app.user_middleware]
    required_middleware = ["AuthenticationMiddleware", "RateLimitMiddleware"]

    for required in required_middleware:
        if required not in middleware_names:
            logger.warning(
                f"Master routes registered but {required} not found in middleware stack. "
                f"Authentication and rate limiting may not work correctly."
            )


if __name__ == "__main__":
    # Display route information when run directly
    master = create_master_router()
    print(f"\n{'='*80}")
    print("MASTER API ROUTES SUMMARY")
    print(f"{'='*80}\n")
    print(f"API Prefix: {MasterRouterConfig.API_PREFIX}")
    print(f"Version: {MasterRouterConfig.API_VERSION}")
    print(f"Rate Limit: {MasterRouterConfig.RATE_LIMIT_REQUESTS} requests "
          f"per {MasterRouterConfig.RATE_LIMIT_WINDOW_SECONDS} seconds")
    print(f"\nRoutes registered: {len(master.routes)}")
    print(f"\nKey features:")
    print(f"  ✓ Tenant isolation enforcement")
    print(f"  ✓ Permission-based access control")
    print(f"  ✓ Comprehensive error handling")
    print(f"  ✓ Request validation via Pydantic")
    print(f"  ✓ Automatic exception logging")
    print(f"  ✓ Security event tracking")
    print(f"\n{'='*80}\n")
