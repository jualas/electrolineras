from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///data/db/stations.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = True
    api_environment: str = "development"
    api_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    api_docs_enabled: bool | None = None
    api_docs_basic_auth_user: str = ""
    api_docs_basic_auth_password: str = ""
    api_rate_limit_enabled: bool = True
    api_rate_limit_window_seconds: float = 60.0
    api_rate_limit_default_per_minute: int = 120
    api_rate_limit_api_per_minute: int = 90
    api_rate_limit_routing_per_minute: int = 30
    api_rate_limit_geocode_per_minute: int = 45
    api_rate_limit_auth_per_minute: int = 15
    api_max_request_body_bytes: int = 65536
    api_trust_proxy_headers: bool = False
    api_security_headers_enabled: bool = True
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_shortest_base_url: str = ""
    osrm_timeout_seconds: float = 30.0
    osrm_use_multi_profile: bool = False
    osrm_profile_fastest: str = "driving"
    osrm_profile_shortest: str = "shortest"
    osrm_profile_conventional: str = "driving"
    osrm_shortest_directness_penalty: float = 0.35
    osrm_fastest_request_alternatives: bool = True
    # OSRM acepta alternatives=true|N (máx. 3 en backend Iberia). N>1 saca más corredores.
    osrm_fastest_alternatives_count: int = 3
    osrm_fastest_alternative_tolerance: float = 0.05
    # Multiplica la velocidad efectiva OSRM (duration /= factor). >1 acerca tiempos a
    # Google/autovía real; 1.0 = bruto OSM. Rango útil ~1.10–1.25 (#6153).
    osrm_speed_factor: float = 1.15

    def osrm_shortest_url(self) -> str:
        return self.osrm_shortest_base_url.strip() or self.osrm_base_url
    route_corridor_km_default: float = 10.0
    route_behind_margin_km_default: float = 2.0
    route_wrong_side_penalty_km_default: float = 5.0
    route_results_limit_default: int = 10
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_fallback_base_url: str = ""
    nominatim_public_emergency_fallback: bool = True
    nominatim_user_agent: str = "Electrolineras/0.1.0 (dev; contact: local)"
    nominatim_country_codes: str = "es,pt"
    nominatim_timeout_seconds: float = 15.0
    nominatim_cache_enabled: bool = True
    nominatim_cache_ttl_seconds: float = 86400.0
    nominatim_cache_max_entries: int = 2048
    nearby_radius_m_default: float = 1000.0
    nearby_radius_m_max: float = 10000.0
    serve_web_static: bool = False
    web_dist_path: str = "src/web/dist"
    charging_agent_enabled: bool = True
    agent_api_token: str = ""
    private_stack_enabled: bool = False
    private_api_token: str = ""
    private_auth_password_hash: str = ""  # obsoleto; login solo usuario + TOTP
    # Multiusuario: "usuario1:SECRETO1,usuario2:SECRETO2". Generar con
    # scripts/auth/setup_private_auth.py --username <nombre> --apply .env
    private_auth_users: str = ""
    # Legacy (pre-multiusuario): usados como fallback si private_auth_users está vacío.
    private_auth_username: str = "electrolineras"
    private_totp_secret: str = ""
    session_secret: str = ""
    auth_session_max_age_seconds: int = 604800
    session_cookie_secure: bool = False
    teslamate_api_base_url: str = ""
    teslamate_api_token: str = ""
    teslamate_car_id: int = 1
    teslamate_car_display_name: str = "The Ship"
    teslamate_timeout_seconds: float = 15.0
    teslamate_data_source: str = "auto"
    teslamate_mqtt_host: str = ""
    teslamate_mqtt_port: int = 1883
    teslamate_mqtt_username: str = ""
    teslamate_mqtt_password: str = ""
    teslamate_mqtt_topic_prefix: str = "teslamate/cars"
    teslamate_mqtt_timeout_seconds: float = 3.0
    # Consumo / capacidad reales TeslaMate (cars.efficiency, cargas → kWh útiles).
    # Si están: se deriva capacidad/rated. Ver docs PHASE3 / INTEGRACION_APPS.
    teslamate_efficiency_kwh_per_km: float | None = None
    teslamate_usable_capacity_kwh: float | None = None

    dify_api_base_url: str = ""
    dify_trip_workflow_api_key: str = ""
    dify_timeout_seconds: float = 90.0

    def auth_users(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for chunk in self.private_auth_users.split(","):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            username, secret = chunk.split(":", 1)
            username = username.strip()
            secret = secret.strip()
            if username and secret:
                pairs.append((username, secret))
        if pairs:
            return pairs
        legacy_username = self.private_auth_username.strip()
        legacy_secret = self.private_totp_secret.strip()
        if legacy_username and legacy_secret:
            return [(legacy_username, legacy_secret)]
        return []

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    def is_production(self) -> bool:
        return self.api_environment.strip().lower() == "production"

    def docs_enabled(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return not self.is_production()

    def docs_basic_auth_configured(self) -> bool:
        return bool(self.api_docs_basic_auth_user and self.api_docs_basic_auth_password)

    def cors_allow_methods(self) -> list[str]:
        if self.is_production():
            return ["GET", "POST", "OPTIONS"]
        return ["*"]

    def cors_allow_headers(self) -> list[str]:
        if self.is_production():
            return ["Authorization", "Content-Type", "Accept"]
        return ["*"]

    def rate_limit_active(self) -> bool:
        return self.api_rate_limit_enabled

    def security_headers_active(self) -> bool:
        return self.api_security_headers_enabled

    def hsts_enabled(self) -> bool:
        return self.is_production() and self.api_trust_proxy_headers


settings = Settings()
