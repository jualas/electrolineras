from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request

from api.auth.session import SESSION_COOKIE_NAME, verify_session_value
from api.config import settings


def _configured_private_token() -> str:
    return settings.private_api_token.strip() or settings.agent_api_token.strip()


def private_totp_auth_configured() -> bool:
    return bool(settings.private_auth_password_hash.strip() and settings.private_totp_secret.strip())


def private_stack_configured() -> bool:
    if not settings.private_stack_enabled:
        return False
    return private_totp_auth_configured() or bool(_configured_private_token())


def session_authenticated(request: Request) -> bool:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    return bool(cookie and verify_session_value(cookie))


def require_private_access(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_agent_token: Annotated[str | None, Header(alias="X-Agent-Token")] = None,
    x_private_token: Annotated[str | None, Header(alias="X-Private-Token")] = None,
) -> None:
    """Sesión TOTP (navegador) o token de servicio (Dify / Cursor CLI)."""
    if not settings.private_stack_enabled:
        return

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
        if presented == expected:
            return

    if not private_totp_auth_configured() and not expected:
        raise HTTPException(
            status_code=503,
            detail="Stack privado sin credenciales: configura TOTP o PRIVATE_API_TOKEN",
        )

    raise HTTPException(status_code=401, detail="Acceso privado denegado")
