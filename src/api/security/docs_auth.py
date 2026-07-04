from __future__ import annotations

import base64
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class DocsBasicAuthMiddleware(BaseHTTPMiddleware):
    PROTECTED_PATHS = {"/docs", "/redoc", "/openapi.json"}

    def __init__(self, app, *, username: str, password: str) -> None:
        super().__init__(app)
        self.username = username
        self.password = password

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path not in self.PROTECTED_PATHS:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Basic "):
            return self._challenge()

        try:
            decoded = base64.b64decode(auth[6:], validate=True).decode("utf-8")
            user, _, pwd = decoded.partition(":")
        except (ValueError, UnicodeDecodeError):
            return self._challenge()

        if not (
            secrets.compare_digest(user, self.username)
            and secrets.compare_digest(pwd, self.password)
        ):
            return self._challenge()

        return await call_next(request)

    @staticmethod
    def _challenge() -> Response:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Electrolineras API docs"'},
            content="Autenticación requerida",
            media_type="text/plain",
        )
