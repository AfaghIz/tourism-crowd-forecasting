from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

HOTELS: list[dict[str, Any]] = [
    {
        "id": "sultanahmet-ottoman-suites",
        "name": "Ottoman Tiles Suites",
        "district": "Sultanahmet",
        "lat": 41.0049,
        "lng": 28.9769,
        "rating": 4.7,
        "priceFrom": 95,
        "tags": ["heritage", "sea view", "tram nearby"],
        "blurb": "A calm, design-forward stay within walking distance of the historic core.",
    },
    {
        "id": "grand-bazaar-heritage",
        "name": "Grand Bazaar Heritage House",
        "district": "Fatih",
        "lat": 41.0116,
        "lng": 28.9683,
        "rating": 4.6,
        "priceFrom": 82,
        "tags": ["shopping", "cafes", "family friendly"],
        "blurb": "Mosaic interiors, quick access to spice, souvenirs, and old Istanbul streets.",
    },
    {
        "id": "galata-aurora",
        "name": "Galata Aurora Hotel",
        "district": "Beyoğlu",
        "lat": 41.0263,
        "lng": 28.9734,
        "rating": 4.8,
        "priceFrom": 110,
        "tags": ["nightlife", "view", "boutique"],
        "blurb": "Bright rooms and skyline vibes—perfect for exploring Galata after sunset.",
    },
    {
        "id": "karakoy-harbor",
        "name": "Karaköy Harbor Boutique",
        "district": "Karaköy",
        "lat": 41.0259,
        "lng": 28.9652,
        "rating": 4.5,
        "priceFrom": 89,
        "tags": ["waterfront", "cafes", "romantic"],
        "blurb": "Modern comfort with a waterfront mood; ideal starting point for Bosphorus walks.",
    },
    {
        "id": "besiktas-bosphorus-view",
        "name": "Bosphorus View Residence",
        "district": "Beşiktaş",
        "lat": 41.0462,
        "lng": 29.0139,
        "rating": 4.6,
        "priceFrom": 103,
        "tags": ["bosphorus", "parking", "quiet rooms"],
        "blurb": "A sleek base with easy transit access and gentle evening light.",
    },
    {
        "id": "uskudar-riverside",
        "name": "Üsküdar Riverside Lodge",
        "district": "Üsküdar",
        "lat": 41.0291,
        "lng": 29.0556,
        "rating": 4.4,
        "priceFrom": 76,
        "tags": ["riverside", "ferries", "local"],
        "blurb": "Wander along the coast, grab breakfast by the water, and enjoy slower Istanbul.",
    },
    {
        "id": "kadikoy-moda-sea-breeze",
        "name": "Moda Sea Breeze Hotel",
        "district": "Kadıköy",
        "lat": 40.9843,
        "lng": 29.0428,
        "rating": 4.7,
        "priceFrom": 92,
        "tags": ["lifestyle", "food", "fashion"],
        "blurb": "Style meets comfort in the heart of Kadıköy’s creative energy.",
    },
    {
        "id": "nisantasi-muse",
        "name": "Nişantaşı Muse Suites",
        "district": "Nişantaşı",
        "lat": 41.0573,
        "lng": 28.9935,
        "rating": 4.6,
        "priceFrom": 118,
        "tags": ["luxury", "shopping", "design"],
        "blurb": "Upscale details, refined interiors, and a short walk to boutiques.",
    },
    {
        "id": "ortakoy-sunset-house",
        "name": "Ortaköy Sunset House",
        "district": "Ortaköy",
        "lat": 41.0415,
        "lng": 29.0348,
        "rating": 4.5,
        "priceFrom": 88,
        "tags": ["bosphorus", "views", "art"],
        "blurb": "Sunset-facing charm near the water and culture spots.",
    },
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_POI_DATASET = PROJECT_ROOT / "data" / "processed" / "otm_pois_model_ready_with_nlp_features_exclusions.csv"
LEGACY_POI_DATASET = PROJECT_ROOT / "backend-python" / "otm_pois_model_ready.csv"


def _normalize(input_str: str | None) -> str:
    return "" if input_str is None else input_str.strip().lower()


def _includes(haystack: str | None, query: str) -> bool:
    return haystack is not None and query in haystack.lower()


def _choose_poi_dataset() -> Path | None:
    if REAL_POI_DATASET.is_file():
        return REAL_POI_DATASET
    if LEGACY_POI_DATASET.is_file():
        return LEGACY_POI_DATASET
    return None


def _poi_blurb(row: pd.Series) -> str:
    parts: list[str] = []
    category = str(row.get("category_clean", "") or "").strip()
    area = str(row.get("query_area", "") or "").strip()
    kinds = str(row.get("kinds", "") or "").strip()
    if category:
        parts.append(category.replace("_", " "))
    if area:
        parts.append(area)
    elif kinds:
        parts.append(kinds.split(",")[0].replace("_", " "))
    return " · ".join(parts) if parts else "Istanbul point of interest."


def _poi_record(row: pd.Series) -> dict[str, Any] | None:
    excluded = pd.to_numeric(row.get("exclude_from_recommendation"), errors="coerce")
    if not pd.isna(excluded) and int(excluded) == 1:
        return None

    poi_id = str(row.get("poi_id", "") or "").strip()
    if not poi_id:
        return None

    lat = pd.to_numeric(row.get("lat"), errors="coerce")
    lon = pd.to_numeric(row.get("lon"), errors="coerce")
    if pd.isna(lat) or pd.isna(lon):
        return None

    display_name = str(row.get("display_name_en", "") or "").strip()
    base_name = str(row.get("name", "") or "").strip()
    name = display_name or base_name
    if not name:
        return None

    category = str(row.get("category_clean", "") or "").strip()
    category_label = category.replace("_", " ").title() if category else "Attraction"

    return {
        "id": poi_id,
        "name": name,
        "category": category_label,
        "lat": float(lat),
        "lng": float(lon),
        "blurb": _poi_blurb(row),
    }


@lru_cache(maxsize=1)
def _real_pois() -> list[dict[str, Any]]:
    dataset = _choose_poi_dataset()
    if dataset is None:
        return []

    df = pd.read_csv(dataset)
    sort_cols: list[str] = []
    ascending: list[bool] = []
    for col, asc in [
        ("has_direct_wiki_signal", False),
        ("wiki_pageviews_total", False),
        ("wiki_popularity_score", False),
        ("rate", False),
        ("dist_from_query_center_m", True),
    ]:
        if col in df.columns:
            sort_cols.append(col)
            ascending.append(asc)
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=ascending, na_position="last").reset_index(drop=True)

    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        record = _poi_record(row)
        if record is not None:
            records.append(record)
    return records


def list_hotels() -> list[dict[str, Any]]:
    return HOTELS


def list_pois(limit: int) -> list[dict[str, Any]]:
    return _real_pois()[: max(1, limit)]


def search_hotels(query: str, limit: int) -> list[dict[str, Any]]:
    q = _normalize(query)
    lim = max(1, limit)
    if not q:
        return HOTELS[:lim]
    out: list[dict[str, Any]] = []
    for h in HOTELS:
        hay = f'{h["name"]} {h["district"]} {" ".join(h["tags"])}'
        if _includes(hay, q):
            out.append(h)
            if len(out) >= lim:
                break
    return out


def search_pois(query: str, limit: int) -> list[dict[str, Any]]:
    q = _normalize(query)
    lim = max(1, limit)
    pois = _real_pois()
    if not q:
        return pois[:lim]
    out: list[dict[str, Any]] = []
    for p in pois:
        hay = f'{p["name"]} {p["category"]} {p["blurb"]}'
        if _includes(hay, q):
            out.append(p)
            if len(out) >= lim:
                break
    return out


def search_everything(query: str, limit: int) -> list[dict[str, Any]]:
    lim = max(1, limit)
    q = _normalize(query)
    pois = _real_pois()

    if not q:
        return [{"kind": "poi", "poi": p} for p in pois[:lim]]

    results: list[dict[str, Any]] = []
    for p in pois:
        hay = f'{p["name"]} {p["category"]} {p["blurb"]}'
        if _includes(hay, q):
            results.append({"kind": "poi", "poi": p})
            if len(results) >= lim:
                break
    return results[:lim]
