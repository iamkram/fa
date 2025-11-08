"""
FastAPI Middleware for System Status Checks

Intercepts all requests to check if system is operational.
Returns 503 Service Unavailable if system is in maintenance mode.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from src.shared.utils.system_status import system_status_manager

logger = logging.getLogger(__name__)


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """
    Check system status before processing requests

    This middleware runs on every request to ensure the system is operational.
    If the kill switch is activated (maintenance mode), all requests except
    admin and health check endpoints return a 503 error with maintenance message.
    """

    # Endpoints that bypass maintenance mode
    BYPASS_PATHS = {
        "/health",
        "/admin/status",
        "/admin/kill-switch",
        "/admin/metrics",
        "/admin/audit-history",
        "/docs",
        "/redoc",
        "/openapi.json"
    }

    async def dispatch(self, request: Request, call_next):
        """
        Process each request and check system status

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/route handler

        Returns:
            Response or 503 if in maintenance mode
        """
        # Allow health checks and admin endpoints
        if any(request.url.path.startswith(path) for path in self.BYPASS_PATHS):
            return await call_next(request)

        # Check system status
        try:
            if not system_status_manager.check_system_operational():
                status = system_status_manager.get_status()

                logger.warning(f"Request blocked - system in maintenance mode: {request.url.path}")

                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Service Temporarily Unavailable",
                        "status": "maintenance",
                        "message": status.maintenance_message or "The system is currently undergoing maintenance. Please try again later.",
                        "expected_restoration": status.expected_restoration.isoformat() if status.expected_restoration else None,
                        "reason": status.reason,
                        "initiated_by": status.initiated_by,
                        "initiated_at": status.initiated_at.isoformat()
                    },
                    headers={
                        "Retry-After": "300"  # Suggest retry after 5 minutes
                    }
                )
        except Exception as e:
            # If status check fails, allow request through (fail-open for availability)
            logger.error(f"Failed to check system status: {e}")
            # In production, you might want to fail-closed instead (return 503)

        # System operational, process request
        return await call_next(request)
