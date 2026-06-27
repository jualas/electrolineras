from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Connector(BaseModel):
    connector_type: str
    power_kw: float
    voltage_v: float | None = None
    current_a: float | None = None
    charging_mode: str | None = None


class StationLocation(BaseModel):
    lat: float
    lon: float
    address: str | None = None


class Station(BaseModel):
    id: str
    source: str
    country: str
    site_name: str | None = None
    operator: str | None = None
    location: StationLocation
    connectors: list[Connector] = Field(default_factory=list)
    max_power_kw: float = 0.0
    access: str | None = None
    payment_methods: list[str] = Field(default_factory=list)
    opening_hours: str | None = None
    raw_ref: str
    fetched_at: datetime | None = None
    source_version: str | None = None
    dynamic_status: str | None = None
    dynamic_price_eur_kwh: float | None = None
    dynamic_updated_at: datetime | None = None


class ParseStats(BaseModel):
    sites_seen: int = 0
    sites_parsed: int = 0
    sites_skipped: int = 0
    skip_reasons: dict[str, int] = Field(default_factory=dict)


class ParseResult(BaseModel):
    stations: list[Station]
    stats: ParseStats
    source: str
    country: str
    source_version: str | None = None
