from __future__ import annotations

from fastapi import HTTPException, Query

from api.schemas import DEFAULT_STATIONS_LIMIT, MAX_OPERATORS_LIMIT, MAX_STATIONS_LIMIT


def parse_country_list(country: str | None) -> list[str] | None:
    if not country:
        return None
    countries = [part.strip().upper() for part in country.split(",") if part.strip()]
    if not countries:
        return None
    for code in countries:
        if len(code) != 2 or not code.isalpha():
            raise HTTPException(
                status_code=422,
                detail=f"Código de país inválido: {code!r}. Use ISO 3166-1 alpha-2 (ES, PT).",
            )
    return countries


def parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    parts = [part.strip() for part in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=422,
            detail="bbox debe tener 4 valores: west,south,east,north",
        )
    try:
        west, south, east, north = (float(value) for value in parts)
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox contiene valores no numéricos") from None

    if west > east:
        raise HTTPException(status_code=422, detail="bbox: west debe ser <= east")
    if south > north:
        raise HTTPException(status_code=422, detail="bbox: south debe ser <= north")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise HTTPException(status_code=422, detail="bbox: longitudes fuera de rango [-180, 180]")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise HTTPException(status_code=422, detail="bbox: latitudes fuera de rango [-90, 90]")

    return west, south, east, north


def stations_limit_query(
    limit: int = Query(
        DEFAULT_STATIONS_LIMIT,
        ge=1,
        le=MAX_STATIONS_LIMIT,
        description="Número máximo de estaciones en la respuesta",
    ),
) -> int:
    return limit


def stations_offset_query(
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
) -> int:
    return offset


def operators_limit_query(
    limit: int = Query(
        10,
        ge=1,
        le=MAX_OPERATORS_LIMIT,
        description="Número máximo de operadores en la respuesta",
    ),
) -> int:
    return limit
