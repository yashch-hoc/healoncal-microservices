"""
Performance Metrics Middleware

This middleware automatically tracks request metrics for all API endpoints.
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.metrics_service import metrics_service

logger = logging.getLogger(__name__)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics."""
        start_time = time.time()
        
        # Extract user_id and session_id from request if available
        user_id = None
        session_id = None
        
        try:
            # Try to get from query params
            user_id = request.query_params.get("user_id")
            session_id = request.query_params.get("session_id")
            
            # Try to get from path params
            if not session_id:
                session_id = request.path_params.get("session_id")
            if not user_id:
                user_id = request.path_params.get("user_id")
            
            # Try to get from request body (for POST requests)
            if request.method == "POST":
                try:
                    body = await request.body()
                    if body:
                        import json
                        body_data = json.loads(body)
                        user_id = body_data.get("user_id") or user_id
                        session_id = body_data.get("session_id") or session_id
                except:
                    pass
        except Exception as e:
            logger.debug(f"Could not extract user/session ID: {e}")
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            status_code = 500
            error = str(e)
            raise
        finally:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record metric
            await metrics_service.record_request(
                endpoint=request.url.path,
                method=request.method,
                duration_ms=duration_ms,
                status_code=status_code,
                user_id=user_id,
                session_id=session_id,
                error=error
            )
        
        return response
