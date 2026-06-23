from db.connection import database_path_from_url


def test_database_path_is_repo_relative() -> None:
    path = database_path_from_url("sqlite:///data/db/stations.db")
    assert path.name == "stations.db"
    assert path.parent.name == "db"
    assert "Electrolineras" in path.as_posix()
