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

import math
import os
import zlib
from datetime import datetime
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

import pandas as pd

from recommendation.crowd_time_heuristic import time_aware_crowd_multiplier
from recommendation.data_loader import COL_MOCK_CROWD

# Canonical column produced for rankers / explanations (first choice in ranker resolution).
COL_CROWD_PRESSURE: Final[str] = "crowd_pressure_index"

# Optional ``df.attrs`` key read by :func:`compute_features` when ``timestamp`` is omitted.
ATTR_CROWD_TIMESTAMP: Final[str] = "crowd_timestamp"
ATTR_CITY_DEMAND_SCORE: Final[str] = "city_demand_score"
ATTR_CROWD_BASIS_DATE: Final[str] = "crowd_basis_date"

DEFAULT_WORKFLOW_CSV: Final[str] = "otm_crowdindex_xgb__rf_weekly.csv"
MANUAL_POI_CROWD_PROXIES: Final[dict[str, tuple[str, float]]] = {
    # Grand Bazaar was restored from the raw POI source after the workflow matrix
    # was generated. Use Spice Bazaar as the nearest modeled historic-market proxy.
    # Keep the multiplier neutral so the value remains a conservative proxy.
    "manual_303807317": ("otm_N4591192493", 1.0),
}


@runtime_checkable
class CrowdScoreProvider(Protocol):
    """Implement ``get_crowd_score``; return a busyness score in ``[0, 1]`` (higher = busier)."""

    def get_crowd_score(self, poi_id: str, timestamp: datetime | None = None) -> float:
        ...


_provider: CrowdScoreProvider | None = None
_default_provider: "WorkflowCrowdScoreProvider | None" = None


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
    """Return the active provider, falling back to the workflow CSV provider when available."""
    global _default_provider
    if _provider is not None:
        return _provider
    if _default_provider is not None:
        return _default_provider
    try:
        _default_provider = WorkflowCrowdScoreProvider(resolve_default_workflow_csv_path())
    except Exception:
        _default_provider = None
    return _default_provider


def resolve_default_workflow_csv_path() -> Path:
    """
    Resolve the default workflow crowdedness table used by the backend.

    The app can override this with ``RECOMMENDATION_CROWD_CSV``. Otherwise we use the
    integrated workflow variant ``xgb__rf`` because it currently balances the best
    temporal model with the strongest Part B model in the repo.
    """
    env = os.environ.get("RECOMMENDATION_CROWD_CSV")
    if env:
        return Path(env).expanduser().resolve()

    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "processed" / DEFAULT_WORKFLOW_CSV


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


class WorkflowCrowdScoreProvider:
    """
    Crowd score provider backed by the notebook-generated POI-time crowdedness table.

    The raw workflow matrix already contains the full ``D(t) * A(p)`` interaction, so
    using only a per-date normalization flattens away most of the temporal movement.
    We therefore blend:

    - a global absolute normalization of ``crowdindex_poi``
    - a within-date relative ranking term
    - a city-demand term

    This keeps POIs comparable within a week while still letting low-, medium-, and
    high-demand modeled periods produce visibly different crowd scores.
    """

    def __init__(self, csv_path: str | Path) -> None:
        path = Path(csv_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Workflow crowdedness CSV not found: {path}")

        df = pd.read_csv(path, parse_dates=["date"])
        required = {"poi_id", "date", "crowdindex_poi", "city_demand_score"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"Workflow crowdedness CSV missing columns: {sorted(missing)}")
        if df.empty:
            raise ValueError(f"Workflow crowdedness CSV is empty: {path}")

        work = df.copy()
        work["date_key"] = work["date"].dt.strftime("%Y-%m-%d")
        global_min = float(work["crowdindex_poi"].min())
        global_max = float(work["crowdindex_poi"].max())
        global_range = max(global_max - global_min, 1e-9)
        max_per_date = work.groupby("date_key")["crowdindex_poi"].transform("max").replace(0.0, 1.0)
        city_demand_max = max(float(work["city_demand_score"].max()), 1e-9)

        work["crowd_pressure_absolute"] = (
            (work["crowdindex_poi"] - global_min) / global_range
        ).clip(lower=0.0, upper=1.0)
        work["crowd_pressure_relative"] = (
            work["crowdindex_poi"] / max_per_date
        ).clip(lower=0.0, upper=1.0)
        work["city_demand_norm"] = (
            work["city_demand_score"] / city_demand_max
        ).clip(lower=0.0, upper=1.0)
        work["crowd_pressure_norm"] = (
            0.60 * work["crowd_pressure_absolute"]
            + 0.25 * work["crowd_pressure_relative"]
            + 0.15 * work["city_demand_norm"]
        ).clip(lower=0.0, upper=1.0)

        self._dates = pd.to_datetime(sorted(work["date"].dropna().unique()))
        self._latest_date = self._dates[-1].to_pydatetime()
        self._score_lookup: dict[tuple[str, str], float] = {}
        self._city_demand_lookup: dict[str, float] = {}

        for row in work.itertuples(index=False):
            date_key = getattr(row, "date_key")
            poi_id = str(getattr(row, "poi_id") or "").strip()
            if not poi_id:
                continue
            self._score_lookup[(poi_id, date_key)] = float(getattr(row, "crowd_pressure_norm"))
            self._city_demand_lookup[date_key] = float(getattr(row, "city_demand_score"))

    def _resolve_timestamp(self, timestamp: datetime | None) -> datetime:
        if timestamp is None:
            return self._latest_date
        ts = pd.Timestamp(timestamp)
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
        ts_py = ts.to_pydatetime()
        nearest_idx = int(
            (abs(self._dates - pd.Timestamp(ts_py))).argmin()
        )
        return self._dates[nearest_idx].to_pydatetime()

    def _date_key(self, timestamp: datetime | None) -> str:
        return self._resolve_timestamp(timestamp).strftime("%Y-%m-%d")

    def get_crowd_score(self, poi_id: str, timestamp: datetime | None = None) -> float:
        pid = str(poi_id or "").strip()
        if not pid:
            return 0.5
        date_key = self._date_key(timestamp)
        direct = self._score_lookup.get((pid, date_key))
        if direct is not None:
            return float(direct)
        proxy_pid = MANUAL_POI_CROWD_PROXIES.get(pid)
        if proxy_pid:
            source_pid, multiplier = proxy_pid
            proxy_score = float(self._score_lookup.get((source_pid, date_key), 0.5))
            return min(1.0, max(0.0, proxy_score * multiplier))
        return 0.5

    def get_city_demand_score(self, timestamp: datetime | None = None) -> float:
        date_key = self._date_key(timestamp)
        return float(self._city_demand_lookup.get(date_key, 0.5))

    def get_basis_date(self, timestamp: datetime | None = None) -> str:
        return self._date_key(timestamp)


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
    provider = get_registered_provider()
    if provider is not None and pid:
        try:
            return _clip01(float(provider.get_crowd_score(pid, timestamp)))
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
    provider = get_registered_provider()
    scores: list[float] = []
    for _, row in out.iterrows():
        pid = str(row.get("poi_id", "") or "").strip()
        mock = fallback_mock_from_row(row)
        scores.append(get_crowd_score(pid, timestamp, fallback_mock=mock))
    out[output_column] = scores
    if provider is not None and hasattr(provider, "get_city_demand_score"):
        try:
            city_score = float(getattr(provider, "get_city_demand_score")(timestamp))
            basis_date = str(getattr(provider, "get_basis_date")(timestamp))
            out.attrs = {
                **out.attrs,
                ATTR_CITY_DEMAND_SCORE: city_score,
                ATTR_CROWD_BASIS_DATE: basis_date,
            }
            out[ATTR_CITY_DEMAND_SCORE] = city_score
            out[ATTR_CROWD_BASIS_DATE] = basis_date
        except Exception:
            pass
    return out


def _clip01(x: float) -> float:
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return 0.5
    if not math.isfinite(xf):
        return 0.5
    return max(0.0, min(1.0, xf))
