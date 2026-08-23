from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from api.auth.credentials import find_user_secret
from api.auth.private_access import (
    private_totp_auth_configured,
    session_authenticated,
    session_username,
)
from api.auth.session import SESSION_COOKIE_NAME, create_session_value
from api.auth.totp import verify_totp_code
from api.config import settings
from api.schemas import AuthConfigResponse, AuthSessionResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, description="Usuario de la zona privada")
    totp_code: str = Field(min_length=6, max_length=8, description="Código de 6 dígitos (Authenticator)")


class LoginResponse(BaseModel):
    ok: bool = True


@router.get("/config")
def auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(
        private_stack_enabled=settings.private_stack_enabled,
        login_enabled=settings.private_stack_enabled and private_totp_auth_configured(),
        token_fallback_enabled=bool(
            settings.private_api_token.strip() or settings.agent_api_token.strip()
        ),
    )


@router.get("/session")
def auth_session(request: Request) -> AuthSessionResponse:
    authenticated = session_authenticated(request)
    return AuthSessionResponse(
        authenticated=authenticated,
        private_stack_enabled=settings.private_stack_enabled,
        login_enabled=settings.private_stack_enabled and private_totp_auth_configured(),
        username=session_username(request) if authenticated else None,
    )


@router.post("/login")
def auth_login(body: LoginRequest, response: Response) -> LoginResponse:
    if not settings.private_stack_enabled:
        raise HTTPException(status_code=503, detail="Stack privado desactivado")
    if not private_totp_auth_configured():
        raise HTTPException(status_code=503, detail="Login TOTP no configurado en el servidor")
    if not settings.session_secret.strip():
        raise HTTPException(status_code=503, detail="Falta SESSION_SECRET en el servidor")

    secret = find_user_secret(body.username)
    totp_ok = verify_totp_code(secret, body.totp_code)
    if not totp_ok:
        raise HTTPException(status_code=401, detail="Usuario o código incorrectos")

    token = create_session_value(body.username.strip())
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_max_age_seconds,
        path="/",
    )
    return LoginResponse()


@router.post("/logout")
def auth_logout(response: Response) -> LoginResponse:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return LoginResponse()
