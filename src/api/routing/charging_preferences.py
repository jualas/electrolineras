from __future__ import annotations

from dataclasses import dataclass

STRATEGY_PREFERRED_OPERATOR = "preferred_operator"


@dataclass(frozen=True)
class ChargingPreferences:
    preferred_operators: tuple[str, ...] = ()
    max_price_eur_kwh: float | None = None


def normalize_operator(name: str) -> str:
    return " ".join(name.strip().lower().split())


def parse_preferred_operators(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return ()
    seen: set[str] = set()
    operators: list[str] = []
    for part in raw.split(","):
        normalized = normalize_operator(part)
        if normalized and normalized not in seen:
            seen.add(normalized)
            operators.append(normalized)
    return tuple(operators)


def operator_matches(station_operator: str | None, preferred: tuple[str, ...]) -> bool:
    if not preferred:
        return False
    if not station_operator:
        return False
    operator = normalize_operator(station_operator)
    return any(pref in operator or operator in pref for pref in preferred)


def operator_preference_rank(
    station_operator: str | None,
    preferred: tuple[str, ...],
) -> float:
    if not preferred:
        return 0.0
    if operator_matches(station_operator, preferred):
        return 0.0
    return 2.0


def price_preference_rank(
    price_eur_kwh: float | None,
    max_price_eur_kwh: float | None,
) -> float:
    if max_price_eur_kwh is None:
        return 0.0
    if price_eur_kwh is None:
        return 1.0
    if price_eur_kwh <= max_price_eur_kwh:
        return 0.0
    return 1.5 + (price_eur_kwh - max_price_eur_kwh) * 5.0


def rank_stop_tuple(
    *,
    classification_order: float,
    deviation_km: float,
    soc_arrival_pct: float,
    status_penalty: float,
    price_key: float,
    station_operator: str | None,
    preferences: ChargingPreferences | None,
) -> tuple[float, float, float, float, float, float, float]:
    prefs = preferences or ChargingPreferences()
    return (
        classification_order,
        operator_preference_rank(station_operator, prefs.preferred_operators),
        price_preference_rank(
            price_key if price_key < 900 else None,
            prefs.max_price_eur_kwh,
        ),
        deviation_km,
        -soc_arrival_pct,
        status_penalty,
        price_key,
    )
