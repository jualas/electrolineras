from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth.private_access import private_totp_auth_configured
from api.config import settings
from api.routes.agent_tools import router as agent_tools_router
from api.routes.along_route import router as along_route_router
from api.routes.auth import router as auth_router
from api.routes.charging_plan import router as charging_plan_router
from api.routes.nearby import router as nearby_router
from api.routes.private_stack import router as private_stack_router
from api.routes.stations import router as stations_router
from api.security.docs_auth import DocsBasicAuthMiddleware
from api.security.headers import SecurityHeadersMiddleware
from api.security.rate_limit import RateLimitMiddleware
from api.security.request_limits import MaxBodySizeMiddleware
from api.static import web_dist_directory

logger = logging.getLogger(__name__)


def _warn_if_password_hash_invalid() -> None:
    if not settings.private_stack_enabled or not private_totp_auth_configured():
        return
    h = settings.private_auth_password_hash.strip()
    if len(h) < 50 or not h.startswith("$2"):
        logger.warning(
            "PRIVATE_AUTH_PASSWORD_HASH parece truncado (%d chars). "
            "En .env de docker-compose duplica cada $ del hash bcrypt ($$).",
            len(h),
        )


def create_app() -> FastAPI:
    docs_enabled = settings.docs_enabled()
    app = FastAPI(
        title="Electrolineras API",
        version="0.1.0",
        description="API REST para consulta de puntos de recarga en la península ibérica.",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods(),
        allow_headers=settings.cors_allow_headers(),
    )
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=settings.api_max_request_body_bytes,
    )
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.rate_limit_active(),
        trust_proxy_headers=settings.api_trust_proxy_headers,
        window_seconds=settings.api_rate_limit_window_seconds,
        default_limit=settings.api_rate_limit_default_per_minute,
        api_limit=settings.api_rate_limit_api_per_minute,
        routing_limit=settings.api_rate_limit_routing_per_minute,
        geocode_limit=settings.api_rate_limit_geocode_per_minute,
        auth_limit=settings.api_rate_limit_auth_per_minute,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        enabled=settings.security_headers_active(),
        hsts=settings.hsts_enabled(),
    )
    if docs_enabled and settings.docs_basic_auth_configured():
        app.add_middleware(
            DocsBasicAuthMiddleware,
            username=settings.api_docs_basic_auth_user,
            password=settings.api_docs_basic_auth_password,
        )

    if settings.is_production() and "*" in settings.cors_origins_list():
        logger.warning("API_CORS_ORIGINS incluye '*' en producción; restringe al dominio público.")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(along_route_router)
    app.include_router(auth_router)
    app.include_router(agent_tools_router)
    app.include_router(private_stack_router)
    app.include_router(charging_plan_router)
    app.include_router(nearby_router)
    app.include_router(stations_router)

    _warn_if_password_hash_invalid()

    if settings.serve_web_static:
        dist_dir = web_dist_directory(settings.web_dist_path)
        if dist_dir.is_dir():
            from fastapi.staticfiles import StaticFiles

            app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="web")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )


if __name__ == "__main__":
    run()
