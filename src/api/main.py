from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routes.along_route import router as along_route_router
from api.routes.nearby import router as nearby_router
from api.routes.stations import router as stations_router
from api.static import web_dist_directory


def create_app() -> FastAPI:
    app = FastAPI(
        title="Electrolineras API",
        version="0.1.0",
        description="API REST para consulta de puntos de recarga en la península ibérica.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(along_route_router)
    app.include_router(nearby_router)
    app.include_router(stations_router)

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
