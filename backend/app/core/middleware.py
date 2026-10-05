"""
Request-level middleware.

- RequestContextMiddleware: assigns a correlation id to every request,
  logs method/path/status/duration, and attaches security headers to
  every response.
- SimpleRateLimiter: in-memory token-bucket limiter keyed by client IP.
  This is a real, working limiter for local/single-instance deployment.
  In a multi-instance production deployment this should be swapped for
  a Redis-backed limiter — the interface is identical, so that's a
  drop-in change, not a redesign.
"""
import logging
import time
import uuid
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger("quantumfinguard.request")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # HSTS only makes sense behind TLS; harmless to declare, enforced at the edge.
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        response: Response
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "unhandled_exception",
                extra={"request_id": request_id},
            )
            raise
        else:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)",
                extra={"request_id": request_id},
            )

        response.headers["X-Request-ID"] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


class SimpleRateLimiter(BaseHTTPMiddleware):
    """Fixed-window per-IP rate limiter. Adequate for a single-instance
    API; documented above as swappable for Redis in multi-instance prod."""

    def __init__(self, app):
        super().__init__(app)
        self._window_seconds = 60
        self._limit = settings.RATE_LIMIT_PER_MINUTE
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        window_start = now - self._window_seconds
        self._hits[client_ip] = [t for t in self._hits[client_ip] if t > window_start]

        if len(self._hits[client_ip]) >= self._limit:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again shortly."}',
                status_code=429,
                media_type="application/json",
            )

        self._hits[client_ip].append(now)
        return await call_next(request)
