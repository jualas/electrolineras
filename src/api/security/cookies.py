from __future__ import annotations

from fastapi import Request

from api.config import settings


def session_cookie_secure(request: Request) -> bool:
    """Secure flag para la cookie de sesión.

    En staging conviven HTTP LAN (:8016) y HTTPS vía túnel (electro-test).
    Si `SESSION_COOKIE_SECURE=false` pero el cliente llega por HTTPS detrás del proxy
    (Cloudflare/nginx), forzamos Secure para que el navegador guarde la cookie.
    """
    if settings.session_cookie_secure:
        return True
    if settings.api_trust_proxy_headers:
        proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        if proto == "https":
            return True
    return False
