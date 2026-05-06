"""
Time-of-day context boosts for POI categories — soft multipliers on top of base scores.

Matching is **substring-based** on normalized ``category_clean``-style strings so labels like
``historic_architecture`` still pick up ``historic`` without maintaining an exhaustive enum.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Mapping

import numpy as np
import pandas as pd

from recommendation.data_loader import COL_CATEGORY

# Canonical buckets (extend by adding keys here + defaults below).
BUCKET_MORNING: Final[str] = "morning"
BUCKET_AFTERNOON: Final[str] = "afternoon"
BUCKET_EVENING: Final[str] = "evening"
BUCKET_NIGHT: Final[str] = "night"

_TIME_BUCKETS: Final[tuple[str, ...]] = (
    BUCKET_MORNING,
    BUCKET_AFTERNOON,
    BUCKET_EVENING,
    BUCKET_NIGHT,
)

# Default keyword → boost in [-1, 1]. Only used when keyword appears as substring in category.
# Callers can merge overrides without copying this entire structure.
_DEFAULT_KEYWORD_BOOSTS: Final[dict[str, dict[str, float]]] = {
    BUCKET_MORNING: {
        "cafe": 0.35,
        "coffee": 0.35,
        "bakery": 0.25,
        "breakfast": 0.25,
        "brunch": 0.3,
        "landmark": 0.3,
        "monument": 0.25,
        "historic": 0.2,
        "museum": 0.2,
        "park": 0.15,
        "viewpoint": 0.25,
        "walking": 0.15,
    },
    BUCKET_AFTERNOON: {
        "museum": 0.25,
        "gallery": 0.22,
        "art": 0.15,
        "park": 0.2,
        "garden": 0.15,
        "landmark": 0.2,
        "cultural": 0.18,
        "shopping": 0.12,
        "market": 0.12,
    },
    BUCKET_EVENING: {
        "restaurant": 0.35,
        "dining": 0.28,
        "food": 0.22,
        "bar": 0.38,
        "pub": 0.32,
        "nightlife": 0.42,
        "club": 0.35,
        "theater": 0.22,
        "theatre": 0.22,
        "cinema": 0.18,
        "viewpoint": 0.18,
        "seafood": 0.2,
    },
    BUCKET_NIGHT: {
        "bar": 0.4,
        "pub": 0.35,
        "nightlife": 0.45,
        "club": 0.38,
        "hotel": 0.12,
        "late": 0.15,
        "music": 0.18,
        "live": 0.12,
    },
}


def infer_time_bucket_from_datetime(dt: datetime | None) -> str | None:
    """Map wall-clock time to a bucket; ``None`` input → ``None``."""
    if dt is None:
        return None
    h = int(dt.hour)
    if 5 <= h < 12:
        return BUCKET_MORNING
    if 12 <= h < 17:
        return BUCKET_AFTERNOON
    if 17 <= h < 23:
        return BUCKET_EVENING
    return BUCKET_NIGHT


def normalize_time_bucket(
    time_of_day: str | datetime | None,
) -> str | None:
    """
    Normalize ``time_of_day`` to a canonical bucket name, or ``None`` if unknown / neutral.

    Accepts :func:`infer_time_bucket_from_datetime` output, or strings like ``"evening"``.
    """
    if time_of_day is None:
        return None
    if isinstance(time_of_day, datetime):
        return infer_time_bucket_from_datetime(time_of_day)
    s = str(time_of_day).strip().lower()
    if s in _TIME_BUCKETS:
        return s
    return None


def merge_keyword_boosts(
    base: Mapping[str, Mapping[str, float]],
    overrides: Mapping[str, Mapping[str, float]] | None,
) -> dict[str, dict[str, float]]:
    """Shallow-merge per bucket: defaults then overrides for that bucket."""
    out: dict[str, dict[str, float]] = {}
    for bucket in _TIME_BUCKETS:
        merged = dict(base.get(bucket, {}))
        if overrides and bucket in overrides:
            merged.update(dict(overrides[bucket]))
        if merged:
            out[bucket] = merged
    return out


def _normalize_category(category: object) -> str:
    if category is None or (isinstance(category, float) and pd.isna(category)):
        return ""
    return str(category).strip().lower()


def get_context_boost(
    category: object,
    time_of_day: str | datetime | None,
    *,
    keyword_boosts: Mapping[str, Mapping[str, float]] | None = None,
) -> float:
    """
    Context multiplier boost for one category and time bucket.

    Returns a value in ``[-1, 1]`` suitable for::

        final_score = score * (1 + beta * boost)

    Parameters
    ----------
    category
        Typically ``category_clean`` (substring matching against keywords).
    time_of_day
        Bucket name (``\"morning\"``, …) or a :class:`~datetime.datetime` (hour-based).
    keyword_boosts
        Optional per-bucket keyword → boost maps merged over :data:`_DEFAULT_KEYWORD_BOOSTS`.

    Returns
    -------
    float
        ``0.0`` when the bucket is unknown or no keyword matches.
    """
    bucket = normalize_time_bucket(time_of_day)
    if bucket is None:
        return 0.0

    table = merge_keyword_boosts(_DEFAULT_KEYWORD_BOOSTS, keyword_boosts)
    keywords = table.get(bucket, {})
    if not keywords:
        return 0.0

    cat = _normalize_category(category)
    if not cat:
        return 0.0

    best = 0.0
    for kw, boost in keywords.items():
        if kw in cat:
            best = max(best, float(boost))
    return float(np.clip(best, -1.0, 1.0))


def context_boost_series(
    categories: pd.Series,
    time_of_day: str | datetime | None,
    *,
    keyword_boosts: Mapping[str, Mapping[str, float]] | None = None,
) -> pd.Series:
    """Vectorized :func:`get_context_boost` (row-wise map; fine for candidate-sized frames)."""
    return categories.map(
        lambda c: get_context_boost(c, time_of_day, keyword_boosts=keyword_boosts)
    ).astype(np.float64)


def apply_context_score_multiplier(
    df: pd.DataFrame,
    *,
    score_column: str = "score",
    category_column: str = COL_CATEGORY,
    time_of_day: str | datetime | None,
    beta: float,
    keyword_boosts: Mapping[str, Mapping[str, float]] | None = None,
) -> pd.DataFrame:
    """
    ``df[score_column] *= (1 + beta * context_boost)`` per row.

    No-op when ``beta <= 0``, ``time_of_day`` does not resolve to a bucket, or
    ``category_column`` is missing.
    """
    out = df.copy()
    if out.empty or beta <= 0 or not np.isfinite(beta):
        return out
    if normalize_time_bucket(time_of_day) is None:
        return out
    if category_column not in out.columns:
        return out

    boosts = context_boost_series(
        out[category_column], time_of_day, keyword_boosts=keyword_boosts
    )
    base = pd.to_numeric(out[score_column], errors="coerce").fillna(0.0).to_numpy(np.float64)
    mult = 1.0 + float(beta) * boosts.to_numpy(dtype=np.float64)
    mult = np.maximum(mult, 1e-9)
    out[score_column] = base * mult
    return out


def apply_context_boost(
    df: pd.DataFrame,
    *,
    score_column: str = "score",
    category_column: str = COL_CATEGORY,
    time_of_day: str | datetime | None = None,
    beta: float,
    keyword_boosts: Mapping[str, Mapping[str, float]] | None = None,
) -> pd.DataFrame:
    """
    Readable alias for :func:`apply_context_score_multiplier` (ranking pipeline step 3).

    Applies ``score *= (1 + beta * context_boost(category, time_of_day))``.
    """
    return apply_context_score_multiplier(
        df,
        score_column=score_column,
        category_column=category_column,
        time_of_day=time_of_day,
        beta=beta,
        keyword_boosts=keyword_boosts,
    )
