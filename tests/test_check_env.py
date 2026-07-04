from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_env",
    ROOT / "scripts" / "env" / "check_env.py",
)
assert _spec and _spec.loader
check_env = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_env)
parse_env_file = check_env.parse_env_file
validate = check_env.validate


def test_parse_env_file_ignores_comments_and_blanks(tmp_path):
    env = tmp_path / "test.env"
    env.write_text(
        """
# comment
DATABASE_URL=sqlite:///data/db/stations.db

API_CORS_ORIGINS=https://example.test
""",
        encoding="utf-8",
    )
    values = parse_env_file(env)
    assert values["DATABASE_URL"] == "sqlite:///data/db/stations.db"
    assert values["API_CORS_ORIGINS"] == "https://example.test"


def test_validate_prod_ok_minimal():
    values = {
        "DATABASE_URL": "sqlite:////app/data/db/stations.db",
        "API_CORS_ORIGINS": "https://electro.jualas.es",
        "OSRM_BASE_URL": "http://127.0.0.1:5000",
        "NOMINATIM_USER_AGENT": "Electrolineras/0.1 (https://electro.jualas.es; contact: a@b.c)",
        "API_ENVIRONMENT": "production",
        "API_RELOAD": "false",
    }
    messages = validate(values, strict_secrets=False)
    assert not any(not msg.startswith("AVISO:") for msg in messages)


def test_validate_prod_rejects_dev_reload():
    values = {
        "DATABASE_URL": "sqlite:////app/data/db/stations.db",
        "API_CORS_ORIGINS": "https://electro.jualas.es",
        "OSRM_BASE_URL": "http://127.0.0.1:5000",
        "NOMINATIM_USER_AGENT": "Electrolineras/0.1 (https://electro.jualas.es; contact: a@b.c)",
        "API_ENVIRONMENT": "production",
        "API_RELOAD": "true",
    }
    messages = validate(values, strict_secrets=False)
    assert any("API_RELOAD" in msg and not msg.startswith("AVISO:") for msg in messages)


def test_validate_private_stack_requires_secrets():
    values = {
        "DATABASE_URL": "sqlite:////app/data/db/stations.db",
        "API_CORS_ORIGINS": "https://electro.jualas.es",
        "OSRM_BASE_URL": "http://127.0.0.1:5000",
        "NOMINATIM_USER_AGENT": "Electrolineras/0.1 (https://electro.jualas.es; contact: a@b.c)",
        "API_ENVIRONMENT": "production",
        "API_RELOAD": "false",
        "PRIVATE_STACK_ENABLED": "true",
    }
    messages = validate(values, strict_secrets=False)
    assert any("SESSION_SECRET" in msg and not msg.startswith("AVISO:") for msg in messages)


def test_production_example_template_passes_validation():
    example = ROOT / ".env.production.example"
    values = parse_env_file(example)
    errors = [msg for msg in validate(values, strict_secrets=False) if not msg.startswith("AVISO:")]
    assert errors == [], f"Plantilla inválida: {errors}"
