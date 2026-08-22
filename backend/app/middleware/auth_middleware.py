"""
Authentication Middleware for HRMS Onboarding Application.
Handles JWT token validation and user authentication for protected routes.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import time

from app.core.security import decode_access_token
from app.core.logging import logger, log_security_event


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle JWT authentication for protected routes.
    Validates tokens and attaches user information to request state.
    """
    
    # Routes that don't require authentication. Kept in sync with the
    # ACTUAL registered paths in app/api/v1/endpoints/ -- these had
    # drifted (e.g. "/auth/v1/login" and "/auth/candidate/login" listed
    # here didn't match any real route; login is now the single unified
    # POST /auth/login). Found and fixed while building HRMS-0114's
    # route-permission audit tool; verify against app.api.v1.routes
    # again if endpoints move.
    PUBLIC_ROUTES = [
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/static",
        "/auth/v1/signup",
        "/auth/login",
        "/msgraph/auth/signin",
        # OAuth redirect target -- called by Microsoft's servers before any
        # app-level session exists. Structurally cannot require a bearer
        # token; its security is the OAuth state parameter, not this list.
        "/msgraph/auth/callback",
        # Public candidate-facing Thunder chat widget (careers page / job
        # listing) -- a real intake channel, no auth possible since the
        # visitor has no account yet. See app.services.public_chat_service.
        "/public/thunder-chat/start",
        "/public/thunder-chat/message",
        "/public/thunder-chat/history",
        # S-002/HRMS-0402 -- Meta calls this directly, no bearer token
        # possible. Security is Meta's own hub.verify_token handshake
        # (GET) and X-Hub-Signature-256 HMAC (POST) -- see
        # app.services.whatsapp_webhook_service.
        "/webhooks/whatsapp",
    ]

    # Route TEMPLATES (FastAPI's {param} syntax) that are public, for
    # paths with a variable segment. Matched segment-by-segment against
    # the real incoming path in _is_public_route -- NOT a plain string
    # match, since request.url.path is the resolved path (e.g.
    # "/jobs/abc123/apply"), never the literal "{job_id}" placeholder.
    PUBLIC_ROUTE_TEMPLATES = [
        # Explicitly documented as public in its own route summary --
        # external candidates applying from a public job board. Per Phase 1
        # B4 this needs rate limiting (not yet enabled anywhere in this
        # app -- see the developer handoff), since it's exactly the kind
        # of public candidate-facing intake B4 calls out by name.
        "/jobs/{job_id}/apply",
        # Career site API -- external candidates (careers.blitzenx.com)
        "/careers/jobs",
        "/careers/jobs/{job_id}",
        "/careers/applications/by-email/{email}",
        "/careers/analyze-resume",
        "/careers/applications",
        "/careers/clarifications/generate",
        "/careers/applications/{app_id}/clarifications/{clarification_id}/answer",
        "/careers/conversations/save",
        # Candidate check-returning for welcome-back feature (career site)
        "/candidates/check-returning",
    ]
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Process each request and validate authentication.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            Response from the next handler or error response
        """
        start_time = time.time()
        path = request.url.path
        
        # Skip authentication for public routes
        if self._is_public_route(path):
            response = await call_next(request)
            return response
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            log_security_event(
                "MISSING_AUTH_HEADER",
                details=f"Path: {path}"
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing"}
            )
        
        # Validate Bearer token format
        if not auth_header.startswith("Bearer "):
            log_security_event(
                "INVALID_AUTH_FORMAT",
                details=f"Path: {path}"
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization format. Use 'Bearer <token>'"}
            )
        
        # Extract token
        token = auth_header.split(" ")[1]
        
        try:
            # Decode and validate token
            payload = decode_access_token(token)
            
            # Attach user info to request state
            request.state.user_email = payload.get("sub")
            request.state.user_type = payload.get("type")
            request.state.user_name = payload.get("name")
            
            # Log successful authentication
            logger.debug(
                f"Authenticated request | User: {request.state.user_email} | "
                f"Type: {request.state.user_type} | Path: {path}"
            )
            
            # Process request
            response = await call_next(request)
            
            # Log response time
            process_time = (time.time() - start_time) * 1000
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            
            return response
            
        except HTTPException as e:
            # Token validation failed
            log_security_event(
                "INVALID_TOKEN",
                details=f"Path: {path} | Error: {e.detail}"
            )
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
            
        except Exception as e:
            # Unexpected error
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            log_security_event(
                "AUTH_ERROR",
                details=f"Path: {path} | Error: {str(e)}"
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal authentication error"}
            )
    
    # Routes eligible for prefix matching (e.g. "/static/logo.png" under
    # "/static"). Deliberately excludes "/" -- see the bug this replaced:
    # "/" is a valid PREFIX_ROUTE... no wait, "/" is only ever an exact
    # match (below), never a prefix, because every path starts with "/"
    # and a prefix match on it would make every route public.
    PREFIX_ROUTES = ["/static", "/docs", "/redoc"]

    def _is_public_route(self, path: str) -> bool:
        """
        Check if the route is public and doesn't require authentication.

        Args:
            path: Request path

        Returns:
            True if route is public, False otherwise
        """
        # Exact match against the full list (covers "/", "/docs", login
        # endpoints, etc. -- these must NOT be prefix-matched, since "/"
        # as a prefix would match every path in the app).
        if path in self.PUBLIC_ROUTES:
            return True

        # Prefix match only for routes explicitly meant to cover a
        # subtree, like static assets.
        for prefix in self.PREFIX_ROUTES:
            if path.startswith(prefix):
                return True

        # Template match for public routes with a variable segment
        # (e.g. "/jobs/{job_id}/apply" matching "/jobs/abc123/apply").
        for template in self.PUBLIC_ROUTE_TEMPLATES:
            if self._matches_template(path, template):
                return True

        return False

    @staticmethod
    def _matches_template(path: str, template: str) -> bool:
        """
        Segment-by-segment match: a "{...}" segment in the template
        matches exactly one real path segment, anything else must match
        literally. Deliberately not a prefix/substring match -- "/jobs"
        alone must not become public just because "/jobs/{job_id}/apply"
        is public.
        """
        path_parts = path.strip("/").split("/")
        template_parts = template.strip("/").split("/")
        if len(path_parts) != len(template_parts):
            return False
        for p, t in zip(path_parts, template_parts):
            if t.startswith("{") and t.endswith("}"):
                continue
            if p != t:
                return False
        return True


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all incoming requests and responses.
    Useful for debugging and monitoring.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Log request and response details.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            Response from the next handler
        """
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request | {request.method} {request.url.path} | "
            f"Client: {request.client.host if request.client else 'Unknown'}"
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Response | {request.method} {request.url.path} | "
            f"Status: {response.status_code} | Time: {process_time:.2f}ms"
        )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware supporting both in-memory and Redis backends.

    MULTI-WORKER SUPPORT: Automatically detects and uses Redis if available
    for shared state across worker processes. Falls back to in-memory if
    Redis is not configured.

    Configuration:
    - RATE_LIMIT_REDIS_URL: Set to enable Redis backend (e.g., redis://localhost:6379)
    - Falls back to in-memory if not set or connection fails

    Default behavior: 100 requests per 60 seconds per IP
    """

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60, redis_url: str = None):
        """
        Initialize rate limiter with optional Redis backend.

        Args:
            app: FastAPI application
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
            redis_url: Optional Redis URL for shared state (auto-detected from env if not provided)
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_counts = {}  # {ip: [(timestamp, count), ...]} for in-memory mode
        self.redis_client = None
        self.use_redis = False

        # Try to initialize Redis if URL is provided or env var is set
        import os
        redis_url = redis_url or os.getenv("RATE_LIMIT_REDIS_URL")
        if redis_url:
            self._init_redis(redis_url)
    
    def _init_redis(self, redis_url: str):
        """
        Initialize Redis client for shared rate limit state across workers.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
        """
        try:
            import redis
            self.redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
            # Test connection
            self.redis_client.ping()
            self.use_redis = True
            logger.info(f"Rate limiting: Using Redis backend at {redis_url}")
        except Exception as e:
            logger.warning(f"Rate limiting: Redis unavailable ({e}), falling back to in-memory")
            self.redis_client = None
            self.use_redis = False

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Check rate limit and process request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            Response or rate limit error
        """
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean old entries
        self._clean_old_entries(client_ip, current_time)

        # Check rate limit
        if self._is_rate_limited(client_ip, current_time):
            log_security_event(
                "RATE_LIMIT_EXCEEDED",
                details=f"IP: {client_ip} | Path: {request.url.path}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_seconds} seconds."
                }
            )

        # Record request
        self._record_request(client_ip, current_time)

        # Process request
        response = await call_next(request)
        return response
    
    def _clean_old_entries(self, ip: str, current_time: float):
        """Remove entries older than the time window."""
        if self.use_redis:
            # Redis handles expiration via TTL; nothing to do here
            return

        # In-memory cleanup
        if ip in self.request_counts:
            cutoff_time = current_time - self.window_seconds
            self.request_counts[ip] = [
                (ts, count) for ts, count in self.request_counts[ip]
                if ts > cutoff_time
            ]

    def _is_rate_limited(self, ip: str, current_time: float) -> bool:
        """Check if IP has exceeded rate limit."""
        if self.use_redis:
            try:
                key = f"rate_limit:{ip}"
                current_count = int(self.redis_client.get(key) or 0)
                return current_count >= self.max_requests
            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}, using in-memory fallback")
                self.use_redis = False
                # Fall through to in-memory check

        # In-memory check
        if ip not in self.request_counts:
            return False

        total_requests = sum(count for _, count in self.request_counts[ip])
        return total_requests >= self.max_requests

    def _record_request(self, ip: str, current_time: float):
        """Record a new request for the IP."""
        if self.use_redis:
            try:
                key = f"rate_limit:{ip}"
                self.redis_client.incr(key)
                # Set TTL to window_seconds (key will auto-expire)
                self.redis_client.expire(key, self.window_seconds)
                return
            except Exception as e:
                logger.warning(f"Redis request recording failed: {e}, using in-memory fallback")
                self.use_redis = False
                # Fall through to in-memory recording

        # In-memory recording
        if ip not in self.request_counts:
            self.request_counts[ip] = []
        self.request_counts[ip].append((current_time, 1))
