"""
Google Places API (New) — Text Search + Place Photo media.

Requires GOOGLE_MAPS_API_KEY with Places API (New) enabled.
https://developers.google.com/maps/documentation/places/web-service/place-photos
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote, urlparse

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"


def safe_fallback_url(url: str | None) -> str | None:
    """Only allow https redirects to Wikimedia (bundled fallbacks from the frontend)."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u.startswith("https://"):
        return None
    host = urlparse(u).hostname or ""
    if host == "upload.wikimedia.org" or host.endswith(".wikimedia.org"):
        return u
    return None


def fetch_place_photo_jpeg(
    api_key: str,
    display_name: str,
    lat: float | None,
    lng: float | None,
    max_px: int = 400,
) -> tuple[bytes, str] | None:
    """
    Find a place via Text Search, then download the first photo as JPEG (or webp) bytes.
    Returns (body, content_type) or None.
    """
    q = f"{display_name.strip()}, Istanbul, Turkey"
    body: dict[str, Any] = {"textQuery": q, "maxResultCount": 1}
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": 20000.0,
            }
        }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.photos",
    }

    try:
        r = requests.post(SEARCH_URL, headers=headers, json=body, timeout=20)
    except requests.RequestException as e:
        logger.warning("Places searchText request failed: %s", e)
        return None

    if r.status_code != 200:
        logger.warning("Places searchText HTTP %s: %s", r.status_code, r.text[:500])
        return None

    try:
        data = r.json()
    except ValueError:
        return None

    places = data.get("places") or []
    if not places:
        return None

    photos = places[0].get("photos") or []
    if not photos:
        return None

    photo_name = photos[0].get("name")
    if not photo_name or not isinstance(photo_name, str):
        return None

    media_url = f"https://places.googleapis.com/v1/{quote(photo_name, safe='/')}/media"
    try:
        mr = requests.get(
            media_url,
            params={"maxWidthPx": max_px, "maxHeightPx": max_px, "key": api_key},
            timeout=25,
        )
    except requests.RequestException as e:
        logger.warning("Places photo media failed: %s", e)
        return None

    if mr.status_code != 200:
        logger.warning("Places photo media HTTP %s", mr.status_code)
        return None

    ctype = mr.headers.get("Content-Type", "image/jpeg")
    if "image" not in ctype:
        ctype = "image/jpeg"
    return (mr.content, ctype)


