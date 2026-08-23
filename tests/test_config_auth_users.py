from __future__ import annotations

from api.config import Settings


def test_auth_users_parses_multiple_pairs() -> None:
    settings = Settings(private_auth_users="juan:SECRETA,maria:SECRETB")
    assert settings.auth_users() == [("juan", "SECRETA"), ("maria", "SECRETB")]


def test_auth_users_trims_whitespace_and_ignores_malformed_entries() -> None:
    settings = Settings(private_auth_users=" juan : SECRETA , malformed , ,maria:SECRETB")
    assert settings.auth_users() == [("juan", "SECRETA"), ("maria", "SECRETB")]


def test_auth_users_falls_back_to_legacy_fields_when_empty() -> None:
    settings = Settings(
        private_auth_users="",
        private_auth_username="electrolineras",
        private_totp_secret="LEGACYSECRET",
    )
    assert settings.auth_users() == [("electrolineras", "LEGACYSECRET")]


def test_auth_users_empty_when_nothing_configured() -> None:
    settings = Settings(private_auth_users="", private_auth_username="", private_totp_secret="")
    assert settings.auth_users() == []
