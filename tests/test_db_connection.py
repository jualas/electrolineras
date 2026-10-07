from pathlib import Path

from db.connection import database_path_from_url

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_database_path_is_repo_relative() -> None:
    path = database_path_from_url("sqlite:///data/db/stations.db")
    assert path == REPO_ROOT / "data" / "db" / "stations.db"
