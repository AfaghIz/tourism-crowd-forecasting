"""
External crowd model integration for the pandas recommendation pipeline.

Register a :class:`CrowdScoreProvider` once at process startup; :func:`attach_crowd_scores`
fills ``crowd_pressure_index`` on candidate frames before ranking. No pipeline logic
changes when swapping models — only the registered provider.

Public surface:

- :func:`get_crowd_score` — ``(poi_id, timestamp?, fallback_mock=…)``; provider → CSV mock → deterministic,
  then **time-aware heuristic** on the fallback path when ``timestamp`` is set (see :mod:`crowd_time_heuristic`).
- :func:`fallback_mock_from_row` — reads ``predicted_crowd_index_mock`` for the mock fallback
- :func:`set_crowd_score_provider` — register an ML-backed object implementing ``get_crowd_score``
- :data:`ATTR_CROWD_TIMESTAMP` — optional ``df.attrs`` key for time-aware models in :func:`~recommendation.feature_engineering.compute_features`
- :func:`attach_crowd_scores` — fills ``crowd_pressure_index`` on a frame (same resolution rules)
"""

from __future__ import annotations

import zlib
import math
from datetime import datetime
from typing import Final, Protocol, runtime_checkable

import pandas as pd

from recommendation.crowd_time_heuristic import time_aware_crowd_multiplier
from recommendation.data_loader import COL_MOCK_CROWD

# Canonical column produced for rankers / explanations (first choice in ranker resolution).
COL_CROWD_PRESSURE: Final[str] = "crowd_pressure_index"

# Optional ``df.attrs`` key read by :func:`compute_features` when ``timestamp`` is omitted.
ATTR_CROWD_TIMESTAMP: Final[str] = "crowd_timestamp"


@runtime_checkable
class CrowdScoreProvider(Protocol):
    """Implement ``get_crowd_score``; return a busyness score in ``[0, 1]`` (higher = busier)."""

    def get_crowd_score(self, poi_id: str, timestamp: datetime | None = None) -> float:
        ...


_provider: CrowdScoreProvider | None = None


def set_crowd_score_provider(provider: CrowdScoreProvider | None) -> None:
    """
    Register the external model (or ``None`` to clear — pipeline uses CSV/mock fallback only).

    Example::

        class MySklearnWrapper:
            def get_crowd_score(self, poi_id: str, timestamp: datetime | None = None) -> float:
                return float(self.model.predict_proba(...)[0, 1])

        set_crowd_score_provider(MySklearnWrapper())
    """
    global _provider
    _provider = provider


def get_registered_provider() -> CrowdScoreProvider | None:
    """Return the active provider, if any."""
    return _provider


def fallback_mock_from_row(row: pd.Series) -> float | None:
    """
    Numeric ``predicted_crowd_index_mock`` from a POI row when present — used when no ML
    provider answers (same source as :func:`attach_crowd_scores`).
    """
    if COL_MOCK_CROWD not in row.index:
        return None
    try:
        v = pd.to_numeric(row[COL_MOCK_CROWD], errors="coerce")
        if pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def get_crowd_score(
    poi_id: str,
    timestamp: datetime | None = None,
    *,
    fallback_mock: float | None = None,
) -> float:
    """
    Resolve a crowd / busyness score in ``[0, 1]`` (**higher = busier**) for ``poi_id``.

    Resolution order:

    1. Registered :class:`CrowdScoreProvider` — ``get_crowd_score(poi_id, timestamp)`` when
       ``poi_id`` is non-empty (ML output is returned as-is; no extra time heuristic).
    2. Baseline from ``fallback_mock`` — typically :func:`fallback_mock_from_row` /
       ``predicted_crowd_index_mock`` when no model is registered or the provider raises.
    3. Else :func:`deterministic_fallback_score` — stable hash-based value.
    4. On this **fallback path only**, if ``timestamp`` is not ``None``, multiply by
       :func:`~recommendation.crowd_time_heuristic.time_aware_crowd_multiplier` (diurnal,
       weekend, seasonal placeholder, time-slot). Ranking then applies an extra peak-time
       penalty in :func:`~recommendation.feature_engineering.compute_features`.

    This is the single abstraction for ML-backed prediction later; callers (including
    :func:`compute_features`) do not import model code.
    """
    pid = str(poi_id or "").strip()
    if _provider is not None and pid:
        try:
            return _clip01(float(_provider.get_crowd_score(pid, timestamp)))
        except Exception:
            pass

    base = deterministic_fallback_score(pid)
    if fallback_mock is not None:
        try:
            mf = float(fallback_mock)
            if math.isfinite(mf):
                base = _clip01(mf)
        except (TypeError, ValueError):
            pass

    if timestamp is not None:
        base = _clip01(base * time_aware_crowd_multiplier(timestamp))
    return base


def deterministic_fallback_score(poi_id: str) -> float:
    """Stable pseudo-random score in ``(0, 1)`` when no model or row fallback exists."""
    if not poi_id or not str(poi_id).strip():
        return 0.5
    return (zlib.adler32(str(poi_id).strip().encode("utf-8")) % 10001) / 10001.0


def attach_crowd_scores(
    df: pd.DataFrame,
    *,
    timestamp: datetime | None = None,
    output_column: str = COL_CROWD_PRESSURE,
) -> pd.DataFrame:
    """
    Add ``output_column`` (default ``crowd_pressure_index``) using the registered provider.

    Fallback order per row:

    1. Registered provider ``get_crowd_score(poi_id, timestamp)`` if registered and succeeds.
    2. ``predicted_crowd_index_mock`` from the row when present (from :func:`load_poi_data`).
    3. :func:`deterministic_fallback_score` from ``poi_id``.
    """
    if df.empty:
        out = df.copy()
        out[output_column] = pd.Series(dtype=float)
        return out

    out = df.copy()
    scores: list[float] = []
    for _, row in out.iterrows():
        pid = str(row.get("poi_id", "") or "").strip()
        mock = fallback_mock_from_row(row)
        scores.append(get_crowd_score(pid, timestamp, fallback_mock=mock))
    out[output_column] = scores
    return out


def _clip01(x: float) -> float:
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return 0.5
    if not math.isfinite(xf):
        return 0.5
    return max(0.0, min(1.0, xf))
