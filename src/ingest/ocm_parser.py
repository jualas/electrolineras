from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

OCM_SOURCE = "open-charge-map"

_COUNTRY_ISO_TO_CODE = {
    "ES": "ES",
    "ESP": "ES",
    "PT": "PT",
    "PRT": "PT",
}


@dataclass
class OcmUserComment:
    rating: int | None
    comment: str | None
    username: str | None
    created_at: datetime | None
    checkin_label: str | None


@dataclass
class OcmReviewProfile:
    ocm_poi_id: int
    country: str | None
    lat: float
    lon: float
    rating_avg: float | None
    rating_count: int
    comments: list[OcmUserComment] = field(default_factory=list)

    @property
    def has_reviews(self) -> bool:
        return self.rating_count > 0 or len(self.comments) > 0


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _country_code(address_info: dict[str, Any]) -> str | None:
    country = address_info.get("Country")
    if isinstance(country, dict):
        iso = country.get("ISOCode")
        if isinstance(iso, str):
            return _COUNTRY_ISO_TO_CODE.get(iso.upper())
    return None


def _parse_comment(raw: dict[str, Any]) -> OcmUserComment | None:
    comment_text = raw.get("Comment")
    text = comment_text.strip() if isinstance(comment_text, str) else None
    rating = _parse_int(raw.get("Rating"))
    if rating is not None and not 1 <= rating <= 5:
        rating = None
    checkin = raw.get("CheckinStatusType")
    checkin_label = None
    if isinstance(checkin, dict) and isinstance(checkin.get("Title"), str):
        checkin_label = checkin["Title"].strip() or None
    username = raw.get("UserName")
    if not isinstance(username, str):
        user = raw.get("User")
        if isinstance(user, dict) and isinstance(user.get("Username"), str):
            username = user["Username"]
    username = username.strip() if isinstance(username, str) and username.strip() else None
    if not text and rating is None and not checkin_label:
        return None
    return OcmUserComment(
        rating=rating,
        comment=text,
        username=username,
        created_at=_parse_datetime(raw.get("DateCreated")),
        checkin_label=checkin_label,
    )


def poi_to_review_profile(poi: dict[str, Any], *, max_comments: int = 8) -> OcmReviewProfile | None:
    poi_id = _parse_int(poi.get("ID"))
    address_info = poi.get("AddressInfo")
    if poi_id is None or not isinstance(address_info, dict):
        return None
    lat = _parse_float(address_info.get("Latitude"))
    lon = _parse_float(address_info.get("Longitude"))
    if lat is None or lon is None:
        return None

    parsed_comments: list[OcmUserComment] = []
    ratings: list[int] = []
    for raw in poi.get("UserComments") or []:
        if not isinstance(raw, dict):
            continue
        parsed = _parse_comment(raw)
        if parsed is None:
            continue
        parsed_comments.append(parsed)
        if parsed.rating is not None:
            ratings.append(parsed.rating)

    parsed_comments.sort(
        key=lambda item: item.created_at or datetime.min,
        reverse=True,
    )
    recent_comments = parsed_comments[:max_comments]

    rating_avg = round(sum(ratings) / len(ratings), 2) if ratings else None
    return OcmReviewProfile(
        ocm_poi_id=poi_id,
        country=_country_code(address_info),
        lat=lat,
        lon=lon,
        rating_avg=rating_avg,
        rating_count=len(ratings),
        comments=recent_comments,
    )


def comments_to_json(comments: list[OcmUserComment]) -> list[dict[str, Any]]:
    return [
        {
            "rating": comment.rating,
            "comment": comment.comment,
            "username": comment.username,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "checkin_label": comment.checkin_label,
        }
        for comment in comments
    ]
