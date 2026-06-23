from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from lxml import etree

from ingest.config import repo_root
from ingest.fetch_common import extract_publication_time
from models.station import Connector, ParseResult, ParseStats, Station, StationLocation

logger = logging.getLogger(__name__)

SOURCE_BY_COUNTRY = {
    "ES": "es-nap-dgt",
    "PT": "pt-nap-mobie",
}

ACCESS_BY_SITE_TYPE = {
    "openSpace": "public",
    "onstreet": "public",
    "inBuilding": "restricted",
    "other": "unknown",
}

PAYMENT_METHOD_MAP = {
    "debitcard": "card",
    "creditcard": "card",
    "apps": "app",
    "nfc": "nfc",
    "rfid": "rfid",
    "qrcode": "app",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find_child(parent: etree._Element, name: str) -> etree._Element | None:
    for child in parent:
        if local_name(child.tag) == name:
            return child
    return None


def find_first(parent: etree._Element, name: str) -> etree._Element | None:
    for element in parent.iter():
        if local_name(element.tag) == name:
            return element
    return None


def element_text(element: etree._Element | None) -> str | None:
    if element is None:
        return None
    text = (element.text or "").strip()
    return text or None


def find_first_text(parent: etree._Element, name: str) -> str | None:
    return element_text(find_first(parent, name))


def find_site_name(site: etree._Element) -> str | None:
    for child in site:
        if local_name(child.tag) != "name":
            continue
        value = find_first(child, "value")
        if value is not None and value.text:
            return value.text.strip()
    return None


def find_operator(site: etree._Element) -> str | None:
    for element in site.iter():
        if local_name(element.tag) != "operator":
            continue
        value = find_first(element, "value")
        if value is not None and value.text:
            return value.text.strip()
    return None


def find_coordinates(site: etree._Element) -> tuple[float, float] | None:
    lat_text = find_first_text(site, "latitude")
    lon_text = find_first_text(site, "longitude")
    if not lat_text or not lon_text:
        return None
    try:
        lat = float(lat_text)
        lon = float(lon_text)
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def build_address(site: etree._Element) -> str | None:
    lines: list[str] = []
    for element in site.iter():
        if local_name(element.tag) != "addressLine":
            continue
        text_el = find_first(element, "text")
        if text_el is None:
            continue
        value = find_first(text_el, "value")
        if value is not None and value.text:
            line = value.text.strip()
            if line and line not in lines:
                lines.append(line)
    if lines:
        return ", ".join(lines)

    parts: list[str] = []
    for tag in ("postcode", "city", "countryCode"):
        text = find_first_text(site, tag)
        if text:
            parts.append(text)
    return ", ".join(parts) if parts else None


def parse_connectors(site: etree._Element) -> list[Connector]:
    connectors: list[Connector] = []
    for connector_el in site.iter():
        if local_name(connector_el.tag) != "connector":
            continue
        power_w = find_first_text(connector_el, "maxPowerAtSocket")
        if not power_w:
            continue
        try:
            power_kw = float(power_w) / 1000.0
        except ValueError:
            continue
        voltage = find_first_text(connector_el, "voltage")
        current = find_first_text(connector_el, "maximumCurrent")
        connectors.append(
            Connector(
                connector_type=find_first_text(connector_el, "connectorType") or "unknown",
                power_kw=power_kw,
                voltage_v=float(voltage) if voltage else None,
                current_a=float(current) if current else None,
                charging_mode=find_first_text(connector_el, "chargingMode"),
            )
        )
    return connectors


def parse_payment_methods(site: etree._Element) -> list[str]:
    methods: list[str] = []
    for element in site.iter():
        tag = local_name(element.tag)
        if tag == "authenticationAndIdentificationMethods" and element.text:
            mapped = PAYMENT_METHOD_MAP.get(element.text.strip().lower())
            if mapped and mapped not in methods:
                methods.append(mapped)
        if tag == "paymentMethod":
            for brand in element.iter():
                if local_name(brand.tag) == "brandsAccepted" and brand.text:
                    token = brand.text.strip().lower()
                    if token and token not in methods:
                        methods.append(token)
    return methods


def parse_opening_hours(site: etree._Element) -> str | None:
    for element in site.iter():
        if local_name(element.tag) == "operatingHours":
            xsi_type = element.get("{http://www.w3.org/2001/XMLSchema-instance}type") or ""
            if "OpenAllHours" in xsi_type:
                return "24/7"
            label = find_first_text(element, "label")
            if label:
                return label
    return None


def infer_access(site: etree._Element, country: str) -> str | None:
    site_type = find_first_text(site, "typeOfSite")
    if site_type:
        return ACCESS_BY_SITE_TYPE.get(site_type, site_type)
    if country == "PT":
        return "public"
    return None


def detect_country(xml_path: Path, publication_root: etree._Element | None = None) -> str:
    if publication_root is None:
        with xml_path.open("rb") as handle:
            head = handle.read(16384)
        publication_root = etree.fromstring(head)

    country = find_first_text(publication_root, "country")
    if country in {"ES", "PT"}:
        return country

    creator = find_first(publication_root, "publicationCreator")
    if creator is not None:
        country = find_first_text(creator, "country")
        if country in {"ES", "PT"}:
            return country

    path_hint = xml_path.as_posix().lower()
    if "/pt/" in path_hint or path_hint.endswith("/pt"):
        return "PT"
    if "/es/" in path_hint or path_hint.endswith("/es"):
        return "ES"
    raise ValueError(f"No se pudo detectar el país del feed DATEX: {xml_path}")


def extract_source_version(xml_path: Path) -> str | None:
    with xml_path.open("rb") as handle:
        head = handle.read(16384)
    return extract_publication_time(head)


def load_manifest_metadata(raw_dir: Path) -> tuple[datetime | None, str | None]:
    manifest_path = raw_dir / "manifest.json"
    if not manifest_path.exists():
        return None, None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    fetched_at_raw = payload.get("fetched_at")
    fetched_at = datetime.fromisoformat(fetched_at_raw) if fetched_at_raw else None
    source_version = payload.get("publication_time") or payload.get("source_version")
    return fetched_at, source_version


def make_station_id(country: str, source: str, raw_ref: str) -> str:
    source_slug = source.split("-")[-1]
    return f"{country.lower()}-{source_slug}-{raw_ref}"


def parse_site(
    site: etree._Element,
    *,
    country: str,
    source: str,
    fetched_at: datetime | None,
    source_version: str | None,
) -> tuple[Station | None, str | None]:
    raw_ref = site.get("id")
    if not raw_ref:
        return None, "missing_id"

    coordinates = find_coordinates(site)
    if coordinates is None:
        return None, "missing_coordinates"

    connectors = parse_connectors(site)
    if not connectors:
        return None, "missing_connectors"

    lat, lon = coordinates
    max_power_kw = max(connector.power_kw for connector in connectors)

    station = Station(
        id=make_station_id(country, source, raw_ref),
        source=source,
        country=country,
        site_name=find_site_name(site),
        operator=find_operator(site),
        location=StationLocation(lat=lat, lon=lon, address=build_address(site)),
        connectors=connectors,
        max_power_kw=max_power_kw,
        access=infer_access(site, country),
        payment_methods=parse_payment_methods(site),
        opening_hours=parse_opening_hours(site),
        raw_ref=raw_ref,
        fetched_at=fetched_at,
        source_version=source_version,
    )
    return station, None


def iter_sites(xml_path: Path) -> Iterator[etree._Element]:
    context = etree.iterparse(
        xml_path,
        events=("end",),
        tag="{*}energyInfrastructureSite",
        huge_tree=True,
    )
    for _, site in context:
        yield site
        site.clear()
        parent = site.getparent()
        if parent is not None:
            while site.getprevious() is not None:
                del parent[0]


def parse_datex_file(
    xml_path: Path | str,
    *,
    country: str | None = None,
    source: str | None = None,
    fetched_at: datetime | None = None,
    source_version: str | None = None,
) -> ParseResult:
    path = Path(xml_path)
    if not path.is_absolute():
        path = repo_root() / path
    if not path.exists():
        raise FileNotFoundError(path)

    detected_country = country or detect_country(path)
    resolved_source = source or SOURCE_BY_COUNTRY[detected_country]

    if fetched_at is None or source_version is None:
        manifest_fetched_at, manifest_source_version = load_manifest_metadata(path.parent)
        fetched_at = fetched_at or manifest_fetched_at
        source_version = source_version or manifest_source_version
    source_version = source_version or extract_source_version(path)

    stations: list[Station] = []
    skip_reasons: Counter[str] = Counter()

    for site in iter_sites(path):
        station, skip_reason = parse_site(
            site,
            country=detected_country,
            source=resolved_source,
            fetched_at=fetched_at,
            source_version=source_version,
        )
        if station is None:
            skip_reasons[skip_reason or "unknown"] += 1
            continue
        stations.append(station)

    stats = ParseStats(
        sites_seen=sum(skip_reasons.values()) + len(stations),
        sites_parsed=len(stations),
        sites_skipped=sum(skip_reasons.values()),
        skip_reasons=dict(skip_reasons),
    )
    logger.info(
        "Parse DATEX %s: %d estaciones (%d omitidas)",
        path.name,
        stats.sites_parsed,
        stats.sites_skipped,
    )
    return ParseResult(
        stations=stations,
        stats=stats,
        source=resolved_source,
        country=detected_country,
        source_version=source_version,
    )


def parse_latest_raw_feed(country: str) -> ParseResult:
    raw_dir = repo_root() / "data" / "raw" / country.lower()
    manifest_path = raw_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No hay manifest.json en {raw_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    xml_path = raw_dir / manifest["file"]
    return parse_datex_file(xml_path, country=country.upper())
