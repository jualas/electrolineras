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
    fetch_user_agent: str = "Electrolineras/0.1 (+https://github.com/electrolineras; NAP ingest)"

    @property
    def nap_es_raw_dir(self) -> Path:
        return self.data_raw_dir / "es"


settings = IngestSettings()
