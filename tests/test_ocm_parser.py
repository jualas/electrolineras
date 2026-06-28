from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest.ocm_parser import poi_to_review_profile

FIXTURES = Path(__file__).parent / "fixtures"


def load_sample_poi() -> dict:
    return json.loads((FIXTURES / "ocm_poi_sample.json").read_text(encoding="utf-8"))


def test_poi_to_review_profile_aggregates_ratings() -> None:
    profile = poi_to_review_profile(load_sample_poi(), max_comments=5)
    assert profile is not None
    assert profile.ocm_poi_id == 123456
    assert profile.country == "ES"
    assert profile.rating_count == 2
    assert profile.rating_avg == pytest.approx(4.5)
    assert len(profile.comments) == 3
    assert profile.comments[0].comment == "Carga lenta pero fiable."
