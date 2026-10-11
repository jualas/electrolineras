from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, Request

from api.auth.session import SESSION_COOKIE_NAME, decode_session, verify_session_value
from api.config import settings


def _configured_private_token() -> str:
    return settings.private_api_token.strip() or settings.agent_api_token.strip()


def private_totp_auth_configured() -> bool:
    return bool(settings.auth_users())


def private_stack_configured() -> bool:
    if not settings.private_stack_enabled:
        return False
    return private_totp_auth_configured() or bool(_configured_private_token())


def session_authenticated(request: Request) -> bool:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    return bool(cookie and verify_session_value(cookie))


def session_username(request: Request) -> str | None:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie:
        return None
    data = decode_session(cookie)
    return data.get("username") if data else None


def require_private_access(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_agent_token: Annotated[str | None, Header(alias="X-Agent-Token")] = None,
    x_private_token: Annotated[str | None, Header(alias="X-Private-Token")] = None,
) -> None:
    """Sesión TOTP (navegador) o token de servicio (scripts de agente)."""
    # Con el stack privado desactivado (valor por defecto) estas rutas no existen:
    # así un despliegue con TeslaMate configurado no las deja abiertas por olvido.
    if not settings.private_stack_enabled:
        raise HTTPException(status_code=404, detail="Not Found")

    if session_authenticated(request):
        return

    expected = _configured_private_token()
    if expected:
        presented: str | None = None
        if authorization and authorization.lower().startswith("bearer "):
            presented = authorization[7:].strip()
        elif x_private_token:
            presented = x_private_token.strip()
        elif x_agent_token:
            presented = x_agent_token.strip()
        if presented and hmac.compare_digest(presented.encode(), expected.encode()):
            return

    if not private_totp_auth_configured() and not expected:
        raise HTTPException(
            status_code=503,
            detail="Stack privado sin credenciales: configura TOTP o PRIVATE_API_TOKEN",
        )

    raise HTTPException(status_code=401, detail="Acceso privado denegado")
