"""
Ranking API: POI scoring pipeline lives in :mod:`ranking_pipeline`.

Crowd column resolution is implemented in :mod:`crowd_signal` and re-exported here for
backward-compatible imports.
"""

from __future__ import annotations

from typing import Final

from recommendation.crowd_signal import CROWD_COLUMN_CANDIDATES, resolve_crowd_signal_column
from recommendation.ranking_pipeline import rank_candidates

COL_DISTANCE_KM: Final[str] = "distance_km"
COL_SCORE: Final[str] = "score"

_WEIGHT_DISTANCE: Final[str] = "distance"
_WEIGHT_CALM: Final[str] = "calm"
_WEIGHT_QUALITY: Final[str] = "quality"
_WEIGHT_CATEGORY: Final[str] = "category"
_WEIGHT_EXPLORATION: Final[str] = "exploration"

# Back-compat for modules that referenced ranker's tuple name.
_CROWD_COLUMN_CANDIDATES: tuple[str, ...] = CROWD_COLUMN_CANDIDATES

__all__ = [
    "COL_DISTANCE_KM",
    "COL_SCORE",
    "CROWD_COLUMN_CANDIDATES",
    "_CROWD_COLUMN_CANDIDATES",
    "rank_candidates",
    "resolve_crowd_signal_column",
]
