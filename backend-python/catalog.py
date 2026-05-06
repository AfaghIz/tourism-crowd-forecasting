from __future__ import annotations

from typing import Any

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

POIS: list[dict[str, Any]] = [
    {
        "id": "blue-mosque",
        "name": "Blue Mosque",
        "category": "Landmark",
        "lat": 41.0055,
        "lng": 28.9768,
        "blurb": "Iconic architecture and timeless silhouettes.",
    },
    {
        "id": "hagia-sophia",
        "name": "Hagia Sophia",
        "category": "Museum",
        "lat": 41.0086,
        "lng": 28.9802,
        "blurb": "A masterpiece of history, light, and scale.",
    },
    {
        "id": "galata-tower",
        "name": "Galata Tower",
        "category": "Viewpoint",
        "lat": 41.025,
        "lng": 28.9744,
        "blurb": "Climb for skyline views across Istanbul.",
    },
    {
        "id": "grand-bazaar",
        "name": "Grand Bazaar",
        "category": "Shopping",
        "lat": 41.0117,
        "lng": 28.9682,
        "blurb": "A maze of craft, textiles, and souvenirs.",
    },
    {
        "id": "spice-bazaar",
        "name": "Spice Bazaar",
        "category": "Market",
        "lat": 41.0179,
        "lng": 28.965,
        "blurb": "Smells, spices, and vibrant vendor stalls.",
    },
    {
        "id": "istiklal",
        "name": "İstiklal Street",
        "category": "Street",
        "lat": 41.0364,
        "lng": 28.9822,
        "blurb": "Tram rides, boutiques, and late-night energy.",
    },
    {
        "id": "maiden-tower",
        "name": "Maiden’s Tower",
        "category": "Landmark",
        "lat": 41.0445,
        "lng": 29.0516,
        "blurb": "A romantic island icon on the Bosphorus.",
    },
]


def _normalize(input_str: str | None) -> str:
    return "" if input_str is None else input_str.strip().lower()


def _includes(haystack: str | None, query: str) -> bool:
    return haystack is not None and query in haystack.lower()


def list_hotels() -> list[dict[str, Any]]:
    return HOTELS


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
    if not q:
        return POIS[:lim]
    out: list[dict[str, Any]] = []
    for p in POIS:
        hay = f'{p["name"]} {p["category"]}'
        if _includes(hay, q):
            out.append(p)
            if len(out) >= lim:
                break
    return out


def search_everything(query: str, limit: int) -> list[dict[str, Any]]:
    lim = max(1, limit)
    q = _normalize(query)

    if not q:
        results: list[dict[str, Any]] = []
        for h in HOTELS[: min(4, lim)]:
            results.append({"kind": "hotel", "hotel": h})
        remaining = lim - len(results)
        for p in POIS[: min(6, max(0, remaining))]:
            results.append({"kind": "poi", "poi": p})
        return results[:lim]

    results = []
    for h in HOTELS:
        hay = f'{h["name"]} {h["district"]} {" ".join(h["tags"])}'
        if _includes(hay, q):
            results.append({"kind": "hotel", "hotel": h})
    for p in POIS:
        hay = f'{p["name"]} {p["category"]}'
        if _includes(hay, q):
            results.append({"kind": "poi", "poi": p})

    results.sort(key=lambda r: r["kind"])
    return results[:lim]
