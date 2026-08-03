"""Parse heurístico de itinerarios en texto libre → hitos geocodificados."""

from __future__ import annotations

import re
from dataclasses import dataclass

from api.routing.nominatim import GeocodingError, geocode_address

MAX_LEGS = 5

_HOME_RE = re.compile(
    r"\b(casa|vuelta\s+a\s+casa|regreso(\s+a\s+casa)?|volver\s+a\s+casa|"
    r"volvemos\s+a\s+casa|volveremos\s+a\s+casa|home)\b",
    re.IGNORECASE,
)
_RETURN_HOME_TAIL_RE = re.compile(
    r"\s+(?:y\s+)?(?:"
    r"volvemos(?:\s+a\s+casa)?|"
    r"volver(?:emos)?(?:\s+a\s+casa)?|"
    r"vuelta(?:\s+a\s+casa)?|"
    r"regresamos(?:\s+a\s+casa)?|"
    r"regreso(?:\s+a\s+casa)?|"
    r"regresaremos(?:\s+a\s+casa)?"
    r")\b.*$",
    re.IGNORECASE,
)
_SOC_RE = re.compile(
    r"(?:al|a\s+la|salida\s+al|salgo\s+al|salimos\s+(?:cargados?\s+)?al|partir\s+al|"
    r"cargados?\s+al|con)\s*(\d{2,3})\s*%|"
    r"(\d{2,3})\s*%\s*(?:de\s+)?(?:bater[ií]a|soc|carga)?",
    re.IGNORECASE,
)
_NIGHTS_RE = re.compile(
    r"(\d+)\s*noches?|pernocta(?:r)?|dormir|overnight|pasar\s+la\s+noche",
    re.IGNORECASE,
)
_WEEKEND_OVERNIGHT_RE = re.compile(
    r"s[aá]bado.+\bdomingo\b|\bdomingo.+\bs[aá]bado\b|"
    r"viernes.+\bdomingo\b|\bdomingo.+\bviernes\b|"
    r"viernes.+\bs[aá]bado\b",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(
    r"\s*(?:→|->|=>|/|;|\n+|\bluego\b|\bdespués\b|\bdespues\b|"
    r"\by\s+de\s+ah[ií]\b|\bdesde\s+ah[ií]\b)\s*",
    re.IGNORECASE,
)
# Destino tras "a/hacia/hasta" (minúsculas incluidas: camping, pueblo…)
_GO_TO_RE = re.compile(
    r"(?:^|[\s,;])(?:vamos|voy|iremos|ir[eé]|salimos|iremos|pasar(?:emos)?|"
    r"parar(?:emos)?|llegamos|nos\s+vamos)?"
    r"(?:\s+el|\s+la|\s+los|\s+las)?"
    r"(?:\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo))?"
    r"(?:\s+por\s+la\s+(?:mañana|tarde|noche))?"
    r"\s+(?:a|hacia|hasta)\s+(.+)$",
    re.IGNORECASE,
)
_STRIP_PREFIX_RE = re.compile(
    r"^(?:salgo\s+(?:de\s+)?(?:casa\s+)?(?:al\s+\d+%\s*)?|"
    r"desde\s+(?:casa\s+)?|"
    r"(?:el\s+|la\s+)?(?:viernes|s[aá]bado|domingo|lunes|martes|mi[eé]rcoles|jueves)\s+|"
    r"mañana|tarde|noche|por\s+la\s+(?:mañana|tarde|noche)|"
    r"ir\s+a|vamos\s+a|pasar\s+por|parar\s+en|hacia)\s*",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\([^)]*\)")
_FILLER_RE = re.compile(
    r"\b(zona\s+con\s+poca\s+carga(?:\s+r[aá]pida)?|poca\s+carga(?:\s+r[aá]pida)?|"
    r"fin\s+de\s+semana|pocos?\s+d[ií]as?|en\s+principio)\b",
    re.IGNORECASE,
)
_DAY_ONLY_RE = re.compile(
    r"^(?:el\s+|la\s+)?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)$",
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
    cleaned = _SOC_RE.sub(" ", cleaned)
    cleaned = _STRIP_PREFIX_RE.sub("", cleaned.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    return cleaned


def _place_query_from_hint(raw: str) -> str:
    place = _PAREN_RE.sub(" ", raw)
    place = _RETURN_HOME_TAIL_RE.sub(" ", place)
    place = _NIGHTS_RE.sub(" ", place)
    place = _HOME_RE.sub(" ", place)
    place = _SOC_RE.sub(" ", place)
    place = _FILLER_RE.sub(" ", place)
    place = _STRIP_PREFIX_RE.sub("", place.strip())
    # Quitar días sueltos al final ("el domingo")
    place = re.sub(
        r"\s+(?:el\s+|la\s+)?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s*$",
        "",
        place,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", place).strip(" .,-")


def _segment_meta(segment: str, *, force_overnight: bool = False) -> ParsedPlaceHint:
    overnight = force_overnight
    nights: int | None = 1 if force_overnight else None
    nights_match = _NIGHTS_RE.search(segment)
    if nights_match:
        overnight = True
        if nights_match.group(1):
            nights = max(1, int(nights_match.group(1)))
        else:
            nights = 1
    is_home = bool(_HOME_RE.search(segment)) and not _place_query_from_hint(segment)
    return ParsedPlaceHint(raw=segment.strip(), overnight=overnight, nights=nights, is_home=is_home)


def _is_non_place_segment(text: str) -> bool:
    cleaned = _place_query_from_hint(text)
    if not cleaned:
        return True
    if _DAY_ONLY_RE.fullmatch(cleaned):
        return True
    if re.fullmatch(r"\d{2,3}\s*%?", cleaned):
        return True
    if re.fullmatch(
        r"(salgo|salida|partir|parto|desde|vamos|voy)(\s+de)?(\s+casa)?",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return True
    return False


def _extract_go_to_destinations(text: str, *, overnight_default: bool) -> list[ParsedPlaceHint]:
    """Extrae destinos de frases tipo «vamos el sábado a X y volvemos a casa»."""
    working = _PAREN_RE.sub(" ", text)
    working = _SOC_RE.sub(" ", working)
    working = re.sub(r"\s+", " ", working).strip()

    return_home = bool(_HOME_RE.search(working) or _RETURN_HOME_TAIL_RE.search(working))
    before_return = _RETURN_HOME_TAIL_RE.sub("", working).strip()

    hints: list[ParsedPlaceHint] = []

    # Varios «a X luego a Y»
    chunks = _SPLIT_RE.split(before_return)
    candidates: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        go = _GO_TO_RE.search(f" {chunk}")
        if go:
            candidates.append(go.group(1).strip())
            continue
        # «a camping…» sin verbo al inicio del chunk
        simple = re.search(r"(?:^|[\s,;])(?:a|hacia|hasta)\s+(.+)$", chunk, flags=re.IGNORECASE)
        if simple:
            candidates.append(simple.group(1).strip())
            continue
        # Último recurso: el propio chunk si parece un lugar
        cleaned = _place_query_from_hint(chunk)
        if cleaned and not _is_non_place_segment(cleaned) and not _HOME_RE.fullmatch(cleaned):
            candidates.append(cleaned)

    for cand in candidates:
        place = _place_query_from_hint(cand)
        if not place or _is_non_place_segment(place):
            continue
        hints.append(
            ParsedPlaceHint(
                raw=place,
                overnight=overnight_default or bool(_NIGHTS_RE.search(cand)),
                nights=1 if (overnight_default or _NIGHTS_RE.search(cand)) else None,
                is_home=False,
            )
        )

    if return_home:
        hints.append(ParsedPlaceHint(raw="casa", overnight=False, nights=None, is_home=True))

    return hints


def split_itinerary_segments(text: str) -> list[ParsedPlaceHint]:
    trimmed = text.strip()
    if not trimmed:
        return []

    overnight_default = bool(_WEEKEND_OVERNIGHT_RE.search(trimmed) or _NIGHTS_RE.search(trimmed))

    # 1) Frases naturales con vuelta a casa / «vamos a …»
    natural = _extract_go_to_destinations(trimmed, overnight_default=overnight_default)
    non_home = [h for h in natural if not h.is_home]
    if non_home:
        return natural

    # 2) Splits explícitos (flechas, luego, newlines)
    working = _PAREN_RE.sub(" ", trimmed)
    working = _SOC_RE.sub(" ", working)
    working = re.sub(r"\s+", " ", working).strip()
    parts = [p for p in _SPLIT_RE.split(working) if p and p.strip()]
    if len(parts) <= 1:
        a_parts = re.split(r"\s+\ba\s+", working, flags=re.IGNORECASE)
        if len(a_parts) > 1:
            parts = a_parts[1:]  # descartar preámbulo antes del primer «a»

    hints: list[ParsedPlaceHint] = []
    for part in parts:
        if _is_non_place_segment(part):
            continue
        place = _place_query_from_hint(part)
        if not place:
            if _HOME_RE.search(part):
                hints.append(ParsedPlaceHint(raw="casa", overnight=False, nights=None, is_home=True))
            continue
        if _HOME_RE.fullmatch(place) or place.lower() in {"casa", "home"}:
            hints.append(ParsedPlaceHint(raw="casa", overnight=False, nights=None, is_home=True))
            continue
        hints.append(
            ParsedPlaceHint(
                raw=place,
                overnight=overnight_default or bool(_NIGHTS_RE.search(part)),
                nights=1 if (overnight_default or _NIGHTS_RE.search(part)) else None,
                is_home=False,
            )
        )

    if bool(_HOME_RE.search(trimmed)) and (not hints or not hints[-1].is_home):
        hints.append(ParsedPlaceHint(raw="casa", overnight=False, nights=None, is_home=True))

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
    return_home = bool(_HOME_RE.search(text) or _RETURN_HOME_TAIL_RE.search(text))
    overnight_default = bool(_WEEKEND_OVERNIGHT_RE.search(text))
    hints = split_itinerary_segments(text)

    stops: list[GeocodedItineraryStop] = []
    for hint in hints:
        if hint.is_home:
            if home_lat is None or home_lon is None:
                warnings.append("Se menciona «casa» pero no hay origen del coche para geocodificarla.")
                continue
            # Evitar casa como único/primer destino sin hitos previos
            if not stops:
                warnings.append("No se detectó el destino del viaje antes de «casa»; revisa el texto.")
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

        place_query = _place_query_from_hint(hint.raw)
        if not place_query or _is_non_place_segment(place_query):
            continue
        try:
            lat, lon, label = geocode_address(place_query)
            confidence = "high"
        except GeocodingError as exc:
            warnings.append(str(exc))
            continue
        overnight = hint.overnight or (overnight_default and return_home)
        stops.append(
            GeocodedItineraryStop(
                order=len(stops) + 1,
                raw=hint.raw,
                label=label,
                lat=lat,
                lon=lon,
                overnight=overnight,
                nights=hint.nights or (1 if overnight else None),
                is_home=False,
                confidence=confidence,
            )
        )

    # Si return home y el último no es casa, añadir casa
    if return_home and home_lat is not None and home_lon is not None:
        if stops and not stops[-1].is_home:
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
            for i, s in enumerate(stops[:max_legs])
        ]

    # Filtrar itinerario inútil: solo casa
    if stops and all(s.is_home for s in stops):
        warnings.append(
            "Solo se interpretó «casa». Indica el destino (ej.: «vamos a Camping X y volvemos a casa»)."
        )
        stops = []

    if not stops:
        warnings.append(
            "No se pudo interpretar ningún destino. Prueba: «Vamos el sábado a Camping Garrote Gordo y volvemos a casa el domingo»."
        )

    # Pernocta por defecto en ida-vuelta
    if len(stops) >= 2 and return_home and not any(s.overnight for s in stops if not s.is_home):
        stops = [
            GeocodedItineraryStop(
                order=x.order,
                raw=x.raw,
                label=x.label,
                lat=x.lat,
                lon=x.lon,
                overnight=True if (not x.is_home and x.order == next(s.order for s in stops if not s.is_home)) else x.overnight,
                nights=1 if (not x.is_home and x.order == next(s.order for s in stops if not s.is_home)) else x.nights,
                is_home=x.is_home,
                confidence=x.confidence,
            )
            for x in stops
        ]

    return ParsedItinerary(
        departure_soc_percent=departure_soc,
        stops=stops,
        warnings=warnings,
        return_home=return_home,
    )
