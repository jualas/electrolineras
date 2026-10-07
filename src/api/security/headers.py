from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool, hsts: bool) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if not self.enabled:
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(self), microphone=(), camera=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # cross-origin: permite fetch desde WebView Capacitor (https://localhost)
        # y orígenes CORS explícitos; same-site bloqueaba la APK Android.
        response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")

        if self.hsts:
            forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
            scheme = forwarded_proto or request.url.scheme
            if scheme == "https":
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )

        return response
