from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///data/db/stations.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = True
    api_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_seconds: float = 30.0
    route_corridor_km_default: float = 10.0
    route_behind_margin_km_default: float = 2.0
    route_wrong_side_penalty_km_default: float = 5.0
    route_results_limit_default: int = 10

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


settings = Settings()
