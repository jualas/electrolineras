"""Parse heurístico de itinerarios en texto libre → hitos geocodificados."""

from __future__ import annotations

import re
from dataclasses import dataclass

from api.routing.nominatim import GeocodingError, geocode_address

MAX_LEGS = 5

_HOME_RE = re.compile(
    r"\b(casa|vuelta\s+a\s+casa|regreso(\s+a\s+casa)?|volver\s+a\s+casa|home)\b",
    re.IGNORECASE,
)
_SOC_RE = re.compile(
    r"(?:al|a\s+la|salida\s+al|salgo\s+al|partir\s+al|con)\s*(\d{2,3})\s*%|"
    r"(\d{2,3})\s*%\s*(?:de\s+)?(?:bater[ií]a|soc|carga)?",
    re.IGNORECASE,
)
_NIGHTS_RE = re.compile(
    r"(\d+)\s*noches?|pernocta(?:r)?|dormir|overnight|pasar\s+la\s+noche",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(
    r"\s*(?:→|->|=>|/|;|\n+|,\s*(?=y\s)|(?<=\.)\s+|\bluego\b|\bdespués\b|\bdespues\b|"
    r"\by\s+de\s+ah[ií]\b|\bdesde\s+ah[ií]\b)\s*",
    re.IGNORECASE,
)
_STRIP_PREFIX_RE = re.compile(
    r"^(?:salgo\s+(?:de\s+)?(?:casa\s+)?(?:al\s+\d+%\s*)?|"
    r"desde\s+(?:casa\s+)?|"
    r"viernes|s[aá]bado|domingo|lunes|martes|mi[eé]rcoles|jueves|"
    r"mañana|tarde|noche|por\s+la\s+(?:mañana|tarde|noche)|"
    r"ir\s+a|vamos\s+a|pasar\s+por|parar\s+en|hacia)\s+",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\([^)]*\)")
_FILLER_RE = re.compile(
    r"\b(zona\s+con\s+poca\s+carga(?:\s+r[aá]pida)?|poca\s+carga(?:\s+r[aá]pida)?|"
    r"fin\s+de\s+semana|pocos?\s+d[ií]as?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedPlaceHint:
    raw: str
    overnight: bool
    nights: int | None
    is_home: bool


@dataclass(frozen=True)
class GeocodedItineraryStop:
    order: int
    raw: str
    label: str
    lat: float
    lon: float
    overnight: bool
    nights: int | None
    is_home: bool
    confidence: str  # high | low


@dataclass(frozen=True)
class ParsedItinerary:
    departure_soc_percent: float | None
    stops: list[GeocodedItineraryStop]
    warnings: list[str]
    return_home: bool


def extract_departure_soc(text: str) -> float | None:
    match = _SOC_RE.search(text)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    if value is None:
        return None
    soc = float(value)
    if 5 <= soc <= 100:
        return soc
    return None


def _clean_segment(segment: str) -> str:
    cleaned = _PAREN_RE.sub(" ", segment)
    cleaned = _FILLER_RE.sub(" ", cleaned)
    cleaned = _STRIP_PREFIX_RE.sub("", cleaned.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    return cleaned


def _segment_meta(segment: str) -> ParsedPlaceHint:
    overnight = False
    nights: int | None = None
    nights_match = _NIGHTS_RE.search(segment)
    if nights_match:
        overnight = True
        if nights_match.group(1):
            nights = max(1, int(nights_match.group(1)))
        else:
            nights = 1
    is_home = bool(_HOME_RE.search(segment))
    # Remove night phrases from place name
    place = _NIGHTS_RE.sub(" ", segment)
    place = _HOME_RE.sub(" casa ", place) if is_home else place
    place = _clean_segment(place)
    if is_home and (not place or place.lower() in {"casa", "home"}):
        place = "casa"
    return ParsedPlaceHint(raw=segment.strip(), overnight=overnight, nights=nights, is_home=is_home)


def _is_non_place_segment(text: str) -> bool:
    cleaned = _clean_segment(text)
    cleaned = _SOC_RE.sub(" ", cleaned)
    cleaned = _FILLER_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    if not cleaned:
        return True
    if re.fullmatch(r"\d{2,3}\s*%?", cleaned):
        return True
    if re.fullmatch(
        r"(salgo|salida|partir|parto|desde)(\s+de)?(\s+casa)?(\s+al)?(\s+\d{2,3}\s*%)?",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return True
    return False


def split_itinerary_segments(text: str) -> list[ParsedPlaceHint]:
    trimmed = _SOC_RE.sub(" ", text.strip())
    trimmed = re.sub(r"\s+", " ", trimmed).strip()
    if not trimmed:
        return []
    # Prefer arrow / newline splits; also split sentences with "a X"
    parts = [p for p in _SPLIT_RE.split(trimmed) if p and p.strip()]
    if len(parts) <= 1:
        # Fallback: "a Place" chunks
        a_parts = re.split(r"\s+\ba\s+(?=[A-ZÁÉÍÓÚÑ])", trimmed)
        if len(a_parts) > 1:
            parts = a_parts
    hints: list[ParsedPlaceHint] = []
    for part in parts:
        if _is_non_place_segment(part):
            continue
        hint = _segment_meta(part)
        if not hint.raw:
            continue
        cleaned = _clean_segment(hint.raw)
        cleaned = _SOC_RE.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
        if not cleaned and not hint.is_home:
            continue
        if re.fullmatch(r"\d{2,3}\s*%?", cleaned or ""):
            continue
        hints.append(hint)
    return hints


def parse_and_geocode_itinerary(
    text: str,
    *,
    home_lat: float | None = None,
    home_lon: float | None = None,
    home_label: str = "Casa",
    max_legs: int = MAX_LEGS,
) -> ParsedItinerary:
    warnings: list[str] = []
    departure_soc = extract_departure_soc(text)
    return_home = bool(_HOME_RE.search(text))
    hints = split_itinerary_segments(text)

    stops: list[GeocodedItineraryStop] = []
    for hint in hints:
        if hint.is_home:
            if home_lat is None or home_lon is None:
                warnings.append("Se menciona «casa» pero no hay origen del coche para geocodificarla.")
                continue
            stops.append(
                GeocodedItineraryStop(
                    order=len(stops) + 1,
                    raw=hint.raw,
                    label=home_label,
                    lat=home_lat,
                    lon=home_lon,
                    overnight=False,
                    nights=None,
                    is_home=True,
                    confidence="high",
                )
            )
            continue

        place_query = _clean_segment(hint.raw)
        place_query = _NIGHTS_RE.sub(" ", place_query)
        place_query = _SOC_RE.sub(" ", place_query)
        place_query = re.sub(r"\s+", " ", place_query).strip(" .,-")
        if not place_query or _is_non_place_segment(place_query):
            continue
        try:
            lat, lon, label = geocode_address(place_query)
            confidence = "high"
        except GeocodingError as exc:
            warnings.append(str(exc))
            continue
        stops.append(
            GeocodedItineraryStop(
                order=len(stops) + 1,
                raw=hint.raw,
                label=label,
                lat=lat,
                lon=lon,
                overnight=hint.overnight,
                nights=hint.nights,
                is_home=False,
                confidence=confidence,
            )
        )

    # If return home requested but last stop isn't home, append home
    if return_home and home_lat is not None and home_lon is not None:
        if not stops or not stops[-1].is_home:
            stops.append(
                GeocodedItineraryStop(
                    order=len(stops) + 1,
                    raw="casa",
                    label=home_label,
                    lat=home_lat,
                    lon=home_lon,
                    overnight=False,
                    nights=None,
                    is_home=True,
                    confidence="high",
                )
            )

    if len(stops) > max_legs:
        warnings.append(f"Se limitó el itinerario a {max_legs} destinos (había {len(stops)}).")
        stops = stops[:max_legs]
        # renumber
        stops = [
            GeocodedItineraryStop(
                order=i + 1,
                raw=s.raw,
                label=s.label,
                lat=s.lat,
                lon=s.lon,
                overnight=s.overnight,
                nights=s.nights,
                is_home=s.is_home,
                confidence=s.confidence,
            )
            for i, s in enumerate(stops)
        ]

    if not stops:
        warnings.append("No se pudo interpretar ningún destino. Prueba con «A → B → casa».")

    # Mark overnight on non-home intermediate stops if only one stay implied
    if len(stops) >= 2 and not any(s.overnight for s in stops):
        for s in stops[:-1]:
            if not s.is_home:
                # Soft default: first non-home is overnight for round trips
                if return_home:
                    stops = [
                        GeocodedItineraryStop(
                            order=x.order,
                            raw=x.raw,
                            label=x.label,
                            lat=x.lat,
                            lon=x.lon,
                            overnight=True if x.order == s.order else x.overnight,
                            nights=1 if x.order == s.order else x.nights,
                            is_home=x.is_home,
                            confidence=x.confidence,
                        )
                        for x in stops
                    ]
                break

    return ParsedItinerary(
        departure_soc_percent=departure_soc,
        stops=stops,
        warnings=warnings,
        return_home=return_home,
    )
