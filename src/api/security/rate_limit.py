from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.security.client_ip import client_ip


class RateLimitStore:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def allow(self, key: str, *, limit: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - now))
                return False, retry_after
            bucket.append(now)
            return True, 0


def rate_limit_bucket(path: str) -> str:
    if path.startswith("/api/v1/auth/"):
        return "auth"
    if path in {
        "/api/v1/stations/along-route",
        "/api/v1/stations/charging-plan",
    } or path.startswith("/api/v1/agent/") or path.startswith("/api/v1/private/"):
        return "routing"
    if path in {"/api/v1/stations/nearby", "/api/v1/meta/geocode"}:
        return "geocode"
    if path.startswith("/api/"):
        return "api"
    return "default"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool,
        trust_proxy_headers: bool,
        window_seconds: float,
        default_limit: int,
        routing_limit: int,
        geocode_limit: int,
        auth_limit: int,
        api_limit: int,
        store: RateLimitStore | None = None,
        bucket_for_path: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.trust_proxy_headers = trust_proxy_headers
        self.window_seconds = window_seconds
        self.limits = {
            "default": default_limit,
            "api": api_limit,
            "routing": routing_limit,
            "geocode": geocode_limit,
            "auth": auth_limit,
        }
        self.store = store or RateLimitStore()
        self.bucket_for_path = bucket_for_path or rate_limit_bucket

    def _limit_for_bucket(self, bucket: str) -> int:
        return self.limits.get(bucket, self.limits["default"])

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path == "/health":
            return await call_next(request)

        bucket = self.bucket_for_path(path)
        ip = client_ip(request, trust_proxy_headers=self.trust_proxy_headers)
        key = f"{ip}:{bucket}"
        limit = self._limit_for_bucket(bucket)
        allowed, retry_after = self.store.allow(
            key,
            limit=limit,
            window_seconds=self.window_seconds,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Demasiadas solicitudes. Inténtalo de nuevo más tarde.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Policy"] = bucket
        return response
