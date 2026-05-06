"""
Resolution of which DataFrame column holds monotonic crowd / busyness for POI rows.

Kept separate from :mod:`ranker` to avoid import cycles with the feature and pipeline stack.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

# Prefer production-oriented names first; mock / loader columns are fallbacks.
CROWD_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "crowd_pressure_index",
    "predicted_crowd_index",
    "predicted_crowd_index_mock",
)


def resolve_crowd_signal_column(
    df: pd.DataFrame,
    explicit: str | None = None,
) -> str:
    """
    Pick the column that carries monotonic crowd / pressure for ranking.

    1. ``explicit`` if provided and present in ``df``.
    2. First existing column among :data:`CROWD_COLUMN_CANDIDATES`.
    """
    if explicit:
        if explicit not in df.columns:
            raise ValueError(f"crowd_signal_column {explicit!r} not in DataFrame.")
        return explicit

    for name in CROWD_COLUMN_CANDIDATES:
        if name in df.columns:
            return name

    raise ValueError(
        "No crowd signal column found. Add one (e.g. crowd_pressure_index), or pass "
        f"crowd_signal_column explicitly. Tried: {CROWD_COLUMN_CANDIDATES}"
    )
