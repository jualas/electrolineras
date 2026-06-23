from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings

app = FastAPI(
    title="Electrolineras API",
    version="0.1.0",
    description="API REST para consulta de puntos de recarga en la península ibérica.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/meta/stats")
def meta_stats() -> dict[str, str]:
    """Placeholder hasta implementar persistencia (#6026)."""
    return {"message": "Sin datos ingestados aún", "stations": "0"}


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
