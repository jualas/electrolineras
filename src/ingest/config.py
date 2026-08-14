from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class IngestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nap_es_url: str = (
        "https://infocar.dgt.es/datex2/v3/miterd/"
        "EnergyInfrastructureTablePublication/electrolineras.xml"
    )
    nap_pt_url: str = "https://pgm.mobie.pt/integration/nap/evChargingInfra"
    data_raw_dir: Path = Path("data/raw")

    fetch_max_retries: int = 3
    fetch_retry_backoff_seconds: float = 2.0
    fetch_timeout_seconds: float = 120.0
    fetch_pt_timeout_seconds: float = 900.0
    fetch_stream_chunk_size: int = 1024 * 1024
    fetch_user_agent: str = "Electrolineras/0.1 (+https://github.com/electrolineras; NAP ingest)"

    reve_api_key: str = ""
    reve_public_base_url: str = "https://www.mapareve.es/api/public/v1"
    reve_external_base_url: str = "https://www.mapareve.es/api/external/v1"
    # Override explícito de base URL. Si vacío: external si hay REVE_API_KEY, si no public.
    reve_base_url: str = ""
    reve_timeout_seconds: float = 60.0
    reve_user_agent: str = "Electrolineras/0.2 (+https://github.com/electrolineras; REVE sync)"
    reve_sync_per_page: int = 25
    reve_external_page_limit: int = 100
    reve_sync_page_delay_seconds: float = 0.75
    reve_match_radius_m: float = 350.0
    # Empareje por mismo nombre si el NAP y REVE difieren más de radius (p. ej. ~250 m).
    reve_match_name_radius_m: float = 500.0

    def resolved_reve_base_url(self) -> str:
        if self.reve_base_url.strip():
            return self.reve_base_url.rstrip("/")
        if self.reve_api_key.strip():
            return self.reve_external_base_url.rstrip("/")
        return self.reve_public_base_url.rstrip("/")

    ocm_base_url: str = "https://api.openchargemap.io/v3"
    ocm_api_key: str = ""
    ocm_timeout_seconds: float = 60.0
    ocm_user_agent: str = "Electrolineras/0.2 (+https://github.com/electrolineras; OCM sync)"
    ocm_sync_page_size: int = 500
    ocm_match_radius_m: float = 200.0
    ocm_max_comments_stored: int = 8
    ocm_export_dir: Path = Path("data/raw/ocm-export/data")

    @property
    def nap_es_raw_dir(self) -> Path:
        return self.data_raw_dir / "es"

    @property
    def nap_pt_raw_dir(self) -> Path:
        return self.data_raw_dir / "pt"


settings = IngestSettings()
