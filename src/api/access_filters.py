from __future__ import annotations

import re

from models.station import Station

CC_KEYWORDS = (
    "centro comercial",
    "shopping",
    "cc ",
    " c.c.",
    "leroy merlin",
    "ikea",
    "carrefour",
    "el corte ingles",
    "outlet",
    "mall",
    "hipercor",
    "mercadona",
    "walmart",
    "galeria comercial",
    "parque comercial",
    "retail park",
)

PARKING_KEYWORDS = (
    "parking",
    "aparcamiento",
    "garaje",
    "estacionamento",
)


def classify_access(station: Station) -> str:
    text = f"{station.site_name or ''} {station.location.address or ''}".lower()
    normalized = re.sub(r"\s+", " ", text)

    if any(keyword in normalized for keyword in CC_KEYWORDS):
        return "commercial_parking"

    if station.access == "restricted" or station.access == "inBuilding":
        return "indoor"

    if any(keyword in normalized for keyword in PARKING_KEYWORDS):
        return "public_parking"

    if station.access == "public":
        return "public_open"

    return "unknown"


def has_ad_hoc_payment(station: Station) -> bool:
    if not station.payment_methods:
        return True
    ad_hoc_tokens = {"card", "nfc", "creditcard", "debitcard", "credit", "debit"}
    return any(method.lower() in ad_hoc_tokens for method in station.payment_methods)


def passes_access_filters(
    station: Station,
    *,
    public_open_only: bool = False,
    exclude_commercial: bool = False,
    ad_hoc_only: bool = False,
) -> bool:
    access_class = classify_access(station)

    if exclude_commercial and access_class == "commercial_parking":
        return False

    if public_open_only and access_class in {"commercial_parking", "indoor"}:
        return False

    if ad_hoc_only and not has_ad_hoc_payment(station):
        return False

    return True
