"""
Vectorized feature construction for POI ranking: distance, crowd, rating, preferences, novelty.

All transforms use **batch** min–max scaling (within ``df``). For category preferences, set
``df.attrs["preference_categories"]`` to an iterable of allowed ``category_clean`` values
before calling :func:`compute_features`.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from recommendation.candidate_generator import COL_DISTANCE_KM
from recommendation.crowd_scores import (
    ATTR_CROWD_TIMESTAMP,
    fallback_mock_from_row,
    get_crowd_score,
)
from recommendation.crowd_time_heuristic import visit_peak_strength
from recommendation.data_loader import (
    COL_CATEGORY,
    COL_LAT,
    COL_LON,
    COL_POPULARITY,
    COL_POPULARITY_NORM,
    COL_RATE,
    COL_RATE_NORM,
)
from recommendation.crowd_signal import resolve_crowd_signal_column
from recommendation.geo import pairwise_haversine_km

# Output feature column names
COL_DISTANCE_SCORE: str = "distance_score"
COL_CROWD_SCORE: str = "crowd_score"
COL_RATING_SCORE: str = "rating_score"
COL_PREFERENCE_SCORE: str = "preference_score"
COL_NOVELTY_SCORE: str = "novelty_score"

# Extra OTM columns used when primary popularity is absent
COL_WIKI_PAGEVIEWS_TOTAL: str = "wiki_pageviews_total"
COL_CANDIDATE_COUNT_SAME_KEY: str = "candidate_count_same_key"

_ATTR_PREFERENCE_CATS: str = "preference_categories"
_ATTR_NOVELTY_JITTER: str = "novelty_jitter"
_ATTR_NOVELTY_SEED: str = "novelty_random_seed"
_ATTR_NOVELTY_DAMPEN: str = "novelty_dampen"

# Blend novelty toward 0.5 so it rarely dominates rankers (tunable via attrs / kwargs).
_DEFAULT_NOVELTY_DAMPEN: float = 0.82

# Relative crowd vs local neighborhood (see :func:`_crowd_scores_relative`).
_ATTR_REL_RADIUS_KM: str = "relative_crowd_radius_km"
_ATTR_REL_MIN_NEIGHBORS: str = "relative_crowd_min_neighbors"
_ATTR_REL_STRENGTH: str = "relative_crowd_strength"
_ATTR_REL_DISABLED: str = "relative_crowd_disabled"

# Extra calm penalty when visiting at peak times (busy POIs dragged down more).
_ATTR_PEAK_VISIT_PENALTY: str = "peak_visit_penalty_strength"
_DEFAULT_PEAK_VISIT_PENALTY: float = 0.52

_DEFAULT_REL_RADIUS_KM: float = 1.0
_DEFAULT_REL_MIN_NEIGHBORS: int = 2
_DEFAULT_REL_STRENGTH: float = 0.14


def compute_features(
    df: pd.DataFrame,
    *,
    crowd_signal_column: str | None = None,
    timestamp: datetime | None = None,
    novelty_jitter: float | None = None,
    novelty_dampen: float | None = None,
) -> pd.DataFrame:
    """
    Compute normalized, ranking-ready features (fully vectorized).

    **Required columns**

    - ``distance_km`` — from :mod:`candidate_generator`.

    **Crowd** — resolved per row via :func:`~recommendation.crowd_scores.get_crowd_score`
    (registered ML provider when set — uses ``timestamp`` as returned by the model; otherwise
    baseline from ``predicted_crowd_index_mock`` or deterministic fallback, then **time-aware
    modulation** when ``timestamp`` / ``df.attrs['crowd_timestamp']`` is set: diurnal curve,
    weekend uplift, seasonal placeholder, time-slot weights). After relative-neighborhood
    adjustment, if a timestamp is present, an extra **peak-visit penalty** reduces calm more for
    POIs that are busy when :func:`~recommendation.crowd_time_heuristic.visit_peak_strength`
    is high (weekend afternoons, etc.). Tunable via ``df.attrs['peak_visit_penalty_strength']``
    in ``[0, 1]``. Requires ``poi_id``; if missing, falls back to reading a static crowd column
    through :func:`~recommendation.crowd_signal.resolve_crowd_signal_column`.

    **Optional columns**

    - ``rate`` or ``rate_normalized`` for rating.
    - ``wiki_popularity_score`` or ``wiki_popularity_normalized`` for novelty.
    - ``category_clean`` for :attr:`preference_categories` in ``df.attrs``.

    **Transformations** (per requirements)

    - ``distance_score = 1 - minmax(distance_km)``
    - ``crowd_score`` starts as ``1 - minmax(crowd_signal)``, then adjusts for **relative** calm:
      POIs calmer than other candidates within ``relative_crowd_radius_km`` (pairwise Haversine)
      get a boost; busier-than-local-average spots are penalized. Tunable via ``df.attrs``
      (radius, min neighbors for a stable local mean, strength). If ``lat``/``lon`` are missing,
      the neighborhood step is skipped. Small neighborhoods fall back to the global mean crowd
      as the reference average.
    - ``rating_score = minmax(rating)`` (raw ``rate`` preferred; else ``rate_normalized``)
    - ``preference_score`` — ``1.0`` if ``category_clean`` is in ``attrs['preference_categories']``,
      ``0.0`` otherwise; ``0.5`` neutral when unset / empty.
    - ``novelty_score`` rewards **less popular / less obvious** places:

      - Prefer ``wiki_popularity_score`` or ``wiki_popularity_normalized``: ``1 - normalized(pop)``.
      - Else ``wiki_pageviews_total`` (log-scaled): ``1 - minmax(log1p(views))``.
      - Else ``candidate_count_same_key`` (higher = more duplicated listings): ``1 - minmax(count)``.
      - Else inverse of ``rate`` / ``rate_normalized``.
      - Result is **damped** toward ``0.5`` (default blend 82% signal / 18% neutral) to avoid
        novelty dominating.
      - Optional **jitter** (see ``novelty_jitter`` / ``df.attrs['novelty_jitter']``) adds small
        uniform noise in ``[-jitter, jitter]`` for exploration, then clips to ``[0, 1]``.

    Parameters
    ----------
    df
        Candidate POI rows (typically after spatial filter and crowd attachment).
    crowd_signal_column
        If set, passed to :func:`~recommendation.crowd_signal.resolve_crowd_signal_column`
        when ``poi_id`` is absent (legacy column path).
    timestamp
        Forwarded to :func:`~recommendation.crowd_scores.get_crowd_score` for time-aware models.
        If ``None``, uses ``df.attrs[ATTR_CROWD_TIMESTAMP]`` when present
        (:data:`~recommendation.crowd_scores.ATTR_CROWD_TIMESTAMP`).
    novelty_jitter
        If not ``None``, overrides ``df.attrs['novelty_jitter']``. Typical values: ``0`` (default)
        or ``0.02``–``0.04``.
    novelty_dampen
        If not ``None``, overrides ``df.attrs['novelty_dampen']``. In ``(0, 1]`` — fraction of
        the damped value that comes from the raw novelty signal (rest blends toward ``0.5``).

    Notes
    -----
    Optional ``df.attrs['peak_visit_penalty_strength']`` (default ``0.52``) scales the
    peak-time × busyness interaction when ``timestamp`` or ``df.attrs['crowd_timestamp']`` is set.

    Returns
    -------
    pandas.DataFrame
        Copy of ``df`` with five new score columns.
    """
    if df.empty:
        out = df.copy()
        for col in (
            COL_DISTANCE_SCORE,
            COL_CROWD_SCORE,
            COL_RATING_SCORE,
            COL_PREFERENCE_SCORE,
            COL_NOVELTY_SCORE,
        ):
            out[col] = pd.Series(dtype=np.float64)
        return out

    if COL_DISTANCE_KM not in df.columns:
        raise ValueError(f"compute_features requires a '{COL_DISTANCE_KM}' column.")

    out = df.copy()

    # --- distance_score = 1 - normalized(distance) ---
    dist = pd.to_numeric(out[COL_DISTANCE_KM], errors="coerce")
    dist_mm = _min_max_series(dist)
    out[COL_DISTANCE_SCORE] = 1.0 - dist_mm

    # --- crowd_score = base calm score + relative-local adjustment ---
    ts = timestamp if timestamp is not None else out.attrs.get(ATTR_CROWD_TIMESTAMP)
    if "poi_id" in out.columns:
        crowd_vals: list[float] = []
        for _, row in out.iterrows():
            pid = str(row.get("poi_id", "") or "").strip()
            mock = fallback_mock_from_row(row)
            crowd_vals.append(float(get_crowd_score(pid, ts, fallback_mock=mock)))
        crowd = pd.Series(crowd_vals, index=out.index, dtype=np.float64)
    else:
        crowd_col = resolve_crowd_signal_column(out, crowd_signal_column)
        crowd = pd.to_numeric(out[crowd_col], errors="coerce").fillna(0.5)
    crowd_mm = _min_max_series(crowd)
    base_calm = (1.0 - crowd_mm).to_numpy(dtype=np.float64)
    crowd_arr = crowd.to_numpy(dtype=np.float64)

    disabled = bool(out.attrs.get(_ATTR_REL_DISABLED, False))
    if (
        disabled
        or COL_LAT not in out.columns
        or COL_LON not in out.columns
        or len(out) < 2
    ):
        out[COL_CROWD_SCORE] = np.clip(base_calm, 0.0, 1.0)
    else:
        lat_imputed, lon_imputed = _impute_lat_lon(
            pd.to_numeric(out[COL_LAT], errors="coerce"),
            pd.to_numeric(out[COL_LON], errors="coerce"),
        )
        radius_km = float(
            out.attrs.get(_ATTR_REL_RADIUS_KM, _DEFAULT_REL_RADIUS_KM)
        )
        min_neighbors = int(
            out.attrs.get(_ATTR_REL_MIN_NEIGHBORS, _DEFAULT_REL_MIN_NEIGHBORS)
        )
        strength = float(
            out.attrs.get(_ATTR_REL_STRENGTH, _DEFAULT_REL_STRENGTH)
        )
        radius_km = max(radius_km, 1e-6)
        strength = float(np.clip(strength, 0.0, 0.5))

        out[COL_CROWD_SCORE] = _crowd_scores_relative(
            crowd_arr=crowd_arr,
            base_calm=base_calm,
            lat=lat_imputed,
            lon=lon_imputed,
            radius_km=radius_km,
            min_neighbors=max(1, min_neighbors),
            strength=strength,
        )

    # Peak-visit ranking penalty: lower calm more for busy POIs when visit instant is crowded.
    if ts is not None:
        pv = float(visit_peak_strength(ts))
        coeff = float(out.attrs.get(_ATTR_PEAK_VISIT_PENALTY, _DEFAULT_PEAK_VISIT_PENALTY))
        coeff = float(np.clip(coeff, 0.0, 1.0))
        busyness = crowd_mm.to_numpy(dtype=np.float64)
        penalty = coeff * pv * busyness
        calm = np.asarray(out[COL_CROWD_SCORE], dtype=np.float64)
        out[COL_CROWD_SCORE] = np.clip(calm - penalty, 0.0, 1.0)

    # --- rating_score = normalized rating ---
    if COL_RATE in out.columns:
        rate_mm = _min_max_series(pd.to_numeric(out[COL_RATE], errors="coerce"))
        out[COL_RATING_SCORE] = rate_mm.fillna(0.5)
    elif COL_RATE_NORM in out.columns:
        out[COL_RATING_SCORE] = pd.to_numeric(
            out[COL_RATE_NORM], errors="coerce"
        ).fillna(0.5)
    else:
        out[COL_RATING_SCORE] = pd.Series(
            np.float64(0.5), index=out.index, dtype=np.float64
        )

    # --- preference_score (optional via attrs) ---
    prefs = out.attrs.get(_ATTR_PREFERENCE_CATS)
    if prefs is not None and len(list(prefs)) > 0 and COL_CATEGORY in out.columns:
        allow = {str(x).strip().lower() for x in prefs if str(x).strip()}
        cats = out[COL_CATEGORY].astype("string").fillna("").str.strip().str.lower()
        out[COL_PREFERENCE_SCORE] = cats.isin(allow).astype(np.float64)
    else:
        out[COL_PREFERENCE_SCORE] = pd.Series(
            np.float64(0.5), index=out.index, dtype=np.float64
        )

    # --- novelty_score: less popular / less obvious → higher; damped + optional jitter ---
    raw_nov = _novelty_raw_series(out)
    damp = (
        float(novelty_dampen)
        if novelty_dampen is not None
        else float(out.attrs.get(_ATTR_NOVELTY_DAMPEN, _DEFAULT_NOVELTY_DAMPEN))
    )
    damp = float(np.clip(damp, 1e-6, 1.0))
    blended = damp * raw_nov.astype(np.float64) + (1.0 - damp) * 0.5

    jit = (
        float(novelty_jitter)
        if novelty_jitter is not None
        else float(out.attrs.get(_ATTR_NOVELTY_JITTER, 0.0))
    )
    jit = float(np.clip(jit, 0.0, 0.25))

    if jit > 0:
        seed = out.attrs.get(_ATTR_NOVELTY_SEED)
        rng = (
            np.random.default_rng(int(seed))
            if seed is not None
            else np.random.default_rng()
        )
        noise = rng.uniform(-jit, jit, size=len(blended))
        blended = np.clip(blended.to_numpy(dtype=np.float64) + noise, 0.0, 1.0)
        out[COL_NOVELTY_SCORE] = blended
    else:
        out[COL_NOVELTY_SCORE] = np.clip(blended, 0.0, 1.0)

    return out


def _impute_lat_lon(
    lat: pd.Series,
    lon: pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    la = lat.to_numpy(dtype=np.float64)
    lo = lon.to_numpy(dtype=np.float64)
    ok_la = np.isfinite(la)
    ok_lo = np.isfinite(lo)
    med_la = float(np.nanmedian(la[ok_la])) if np.any(ok_la) else np.nan
    med_lo = float(np.nanmedian(lo[ok_lo])) if np.any(ok_lo) else np.nan
    if not np.isfinite(med_la) or not np.isfinite(med_lo):
        return la, lo
    la = np.where(ok_la, la, med_la)
    lo = np.where(ok_lo, lo, med_lo)
    return la, lo


def _crowd_scores_relative(
    *,
    crowd_arr: np.ndarray,
    base_calm: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    radius_km: float,
    min_neighbors: int,
    strength: float,
) -> np.ndarray:
    """
    Boost calm score when ``crowd < local_avg``, penalize when ``crowd > local_avg``.

    Local average is the mean crowd of other POIs within ``radius_km``. If there are fewer than
    ``min_neighbors`` such POIs, use the global mean crowd in this batch as the reference.
    """
    if not np.all(np.isfinite(lat)) or not np.all(np.isfinite(lon)):
        return np.clip(base_calm, 0.0, 1.0)

    dist_km = pairwise_haversine_km(lat, lon)
    pair_mask = (dist_km <= radius_km) & (dist_km > 1e-6)
    neighbor_cnt = pair_mask.sum(axis=1).astype(np.float64)
    neighbor_sum = (pair_mask * crowd_arr[np.newaxis, :]).sum(axis=1)
    gmean = float(np.mean(crowd_arr))

    use_local = neighbor_cnt >= float(min_neighbors)
    local_mean = neighbor_sum / np.maximum(neighbor_cnt, 1.0)
    local_avg = np.where(use_local, local_mean, gmean)

    relative = crowd_arr - local_avg
    std = float(np.nanstd(relative))
    if std <= 1e-12:
        rel_scaled = np.zeros_like(relative, dtype=np.float64)
    else:
        rel_scaled = np.clip(relative / std, -4.0, 4.0)

    adjustment = -strength * np.tanh(rel_scaled)
    return np.clip(base_calm + adjustment, 0.0, 1.0)


def _novelty_raw_series(df: pd.DataFrame) -> pd.Series:
    """
    Raw novelty in [0, 1] before dampening: higher = more obscure / less mainstream.

    Priority: wiki popularity → normalized popularity column → pageviews (log) →
    duplicate-key count → inverse rating.
    """
    idx = df.index

    if COL_POPULARITY in df.columns:
        pop = pd.to_numeric(df[COL_POPULARITY], errors="coerce").fillna(0.0)
        pop_mm = _min_max_series(pop)
        return 1.0 - pop_mm

    if COL_POPULARITY_NORM in df.columns:
        popn = pd.to_numeric(df[COL_POPULARITY_NORM], errors="coerce").fillna(0.5)
        return 1.0 - np.clip(popn, 0.0, 1.0)

    if COL_WIKI_PAGEVIEWS_TOTAL in df.columns:
        views = pd.to_numeric(df[COL_WIKI_PAGEVIEWS_TOTAL], errors="coerce").fillna(0.0)
        views_log = np.log1p(np.maximum(views.to_numpy(dtype=np.float64), 0.0))
        v_mm = _min_max_series(pd.Series(views_log, index=idx))
        return 1.0 - v_mm

    if COL_CANDIDATE_COUNT_SAME_KEY in df.columns:
        cnt = pd.to_numeric(df[COL_CANDIDATE_COUNT_SAME_KEY], errors="coerce").fillna(0.0)
        c_mm = _min_max_series(cnt)
        return 1.0 - c_mm

    if COL_RATE in df.columns:
        rate_mm = _min_max_series(pd.to_numeric(df[COL_RATE], errors="coerce"))
        return (1.0 - rate_mm).fillna(0.5)

    if COL_RATE_NORM in df.columns:
        rn = pd.to_numeric(df[COL_RATE_NORM], errors="coerce").fillna(0.5)
        return (1.0 - np.clip(rn, 0.0, 1.0))

    return pd.Series(np.float64(0.5), index=idx, dtype=np.float64)


def _min_max_series(series: pd.Series) -> pd.Series:
    """Min–max to [0, 1]; constant inputs → 0.5 (vectorized)."""
    v = pd.to_numeric(series, errors="coerce")
    mn = np.asarray(v.min(skipna=True))
    mx = np.asarray(v.max(skipna=True))
    span = mx - mn
    if not np.isfinite(span) or float(span) <= 1e-12:
        return pd.Series(np.float64(0.5), index=v.index, dtype=np.float64)
    return ((v - mn) / span).astype(np.float64)
