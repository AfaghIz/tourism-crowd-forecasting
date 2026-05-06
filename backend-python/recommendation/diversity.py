"""
Greedy diversification so shortlists do not over-repeat the same category (e.g. ten museums).

Also provides Maximal Marginal Relevance (MMR) re-ranking for diversity-aware top-k lists.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Final

import numpy as np
import pandas as pd

from recommendation.data_loader import COL_CATEGORY, COL_LAT, COL_LON
from recommendation.geo import pairwise_haversine_km

# Keep literal here to avoid import cycles with :mod:`ranking_pipeline` → :mod:`diversity`.
COL_SCORE: Final[str] = "score"
DEFAULT_SCORE_COLUMN: Final[str] = COL_SCORE
# Balance category vs geographic redundancy when lat/lon are present.
_DEFAULT_WEIGHT_CATEGORY: Final[float] = 0.65
_DEFAULT_WEIGHT_GEO: Final[float] = 0.35
_DEFAULT_GEO_TAU_KM: Final[float] = 2.0


def diversify(
    df: pd.DataFrame,
    top_k: int,
    *,
    max_per_category: int,
    category_column: str = COL_CATEGORY,
    score_column: str = DEFAULT_SCORE_COLUMN,
) -> pd.DataFrame:
    """
    Build a top-``top_k`` list in descending ``score`` order while capping how many
    times each category may appear.

    Pass one:

    1. **Primary pass** — walk candidates in score order; accept a row if its category
       count is below ``max_per_category``.
    2. **Fill pass** — if fewer than ``top_k`` rows were chosen (categories exhausted),
       append the next-best unused rows without applying the cap.

    Parameters
    ----------
    df
        Ranked or sortable frame; should include ``score_column`` and ``category_column``.
    top_k
        Rows to return at most.
    max_per_category
        Maximum selections sharing the same category in the primary pass (>= 1).

    Returns
    -------
    pandas.DataFrame
        Up to ``top_k`` rows, stable given ties (mergesort order preserved).
    """
    if df.empty or top_k < 1:
        return df.iloc[0:0].copy()

    cap = max(1, int(max_per_category))
    ordered = df.sort_values(score_column, ascending=False, kind="mergesort").reset_index(
        drop=True
    )

    picked_idx: list[int] = []
    cat_counts: dict[str, int] = defaultdict(int)

    for i in range(len(ordered)):
        if len(picked_idx) >= top_k:
            break
        row = ordered.iloc[i]
        cat = _norm_cat(row.get(category_column))
        if cat_counts[cat] >= cap:
            continue
        picked_idx.append(i)
        cat_counts[cat] += 1

    # Second pass: fill remaining slots while still respecting the per-category cap.
    if len(picked_idx) < top_k:
        picked_set = set(picked_idx)
        for i in range(len(ordered)):
            if len(picked_idx) >= top_k:
                break
            if i in picked_set:
                continue
            row = ordered.iloc[i]
            cat = _norm_cat(row.get(category_column))
            if cat_counts[cat] >= cap:
                continue
            picked_idx.append(i)
            picked_set.add(i)
            cat_counts[cat] += 1

    out = ordered.iloc[picked_idx].reset_index(drop=True)
    return out.head(top_k)


def _norm_cat(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "unknown"
    return str(value).strip().lower() or "unknown"


def rerank_with_mmr(
    df: pd.DataFrame,
    lambda_: float,
    top_k: int,
    *,
    score_column: str = COL_SCORE,
    category_column: str = COL_CATEGORY,
    lat_column: str = COL_LAT,
    lon_column: str = COL_LON,
    category_weight: float = _DEFAULT_WEIGHT_CATEGORY,
    geo_weight: float = _DEFAULT_WEIGHT_GEO,
    geo_tau_km: float = _DEFAULT_GEO_TAU_KM,
    use_geo_similarity: bool | None = None,
) -> pd.DataFrame:
    """
    Maximal Marginal Relevance (MMR) re-ranking for diverse POI shortlists.

    Selects ``top_k`` rows by iterating:

    1. Pick the POI with highest ``score`` (pure relevance).
    2. Repeatedly pick the remaining POI that maximizes

       ``lambda_ * relevance - (1 - lambda_) * max_similarity_to_chosen``

    **Similarity** between two POIs combines:

    - **Category**: same ``category_clean`` → strong similarity (binary).
    - **Geography** (optional): pairwise Haversine distance → ``exp(-d_km / tau)`` so nearby
      POIs are more similar.

    Weights ``category_weight`` and ``geo_weight`` mix the two (when geo is enabled); they are
    renormalized if only one signal applies.

    Parameters
    ----------
    df
        Candidate rows; must include ``score_column``.
    lambda_
        Trade-off in ``[0, 1]``: higher values favor relevance over diversity.
    top_k
        Number of rows to return (clamped to the number of rows in ``df``).
    score_column
        Relevance column (higher is better); values are min–max scaled internally for MMR.
    category_column
        Used for same-category similarity when present.
    lat_column, lon_column
        If both exist and ``use_geo_similarity`` is true (default when coords are valid),
        geographic proximity enters similarity.
    category_weight, geo_weight
        Non-negative blend for category vs geo similarity (defaults sum to 1).
    geo_tau_km
        Distance decay for geographic similarity (kilometers).
    use_geo_similarity
        ``True`` / ``False`` to force; ``None`` means auto (use geo when lat/lon columns exist
        and most coordinates are finite).

    Returns
    -------
    pandas.DataFrame
        Up to ``top_k`` rows in MMR order (copy), index reset.

    Raises
    ------
    ValueError
        If ``score_column`` is missing or ``lambda_`` / ``top_k`` are invalid.
    """
    if score_column not in df.columns:
        raise ValueError(f"rerank_with_mmr requires a '{score_column}' column.")
    if not math.isfinite(float(lambda_)):
        raise ValueError("lambda_ must be a finite number.")
    if df.empty or top_k < 1:
        return df.iloc[0:0].copy()

    lam = float(np.clip(lambda_, 0.0, 1.0))
    k = min(int(top_k), len(df))
    work = df.reset_index(drop=True)

    scores = pd.to_numeric(work[score_column], errors="coerce").to_numpy(dtype=np.float64)
    if not np.any(np.isfinite(scores)):
        scores = np.zeros(len(work), dtype=np.float64)
    else:
        scores = np.nan_to_num(scores, nan=np.nanmean(scores))

    rel = _min_max_1d(scores)

    cat_codes = _category_codes(work, category_column)
    geo_sim = _geo_similarity_matrix(work, lat_column, lon_column, geo_tau_km, use_geo_similarity)
    cat_same = cat_codes[:, np.newaxis] == cat_codes[np.newaxis, :]

    wc, wg = float(category_weight), float(geo_weight)
    if geo_sim is None:
        sim_matrix = cat_same.astype(np.float64)
    else:
        wc_n, wg_n = _renorm_pair(wc, wg)
        sim_matrix = wc_n * cat_same.astype(np.float64) + wg_n * geo_sim

    # Iterative MMR; first pick is argmax relevance.
    selected: list[int] = []
    remaining = set(range(len(work)))

    first = int(np.argmax(rel))
    selected.append(first)
    remaining.discard(first)

    while len(selected) < k and remaining:
        best_j = -1
        best_mmr = -np.inf
        # Sorted remaining → deterministic ties (lower row index wins).
        for j in sorted(remaining):
            max_sim = max(float(sim_matrix[j, i]) for i in selected)
            mmr = lam * rel[j] - (1.0 - lam) * max_sim
            if mmr > best_mmr:
                best_mmr = mmr
                best_j = j
        selected.append(best_j)
        remaining.discard(best_j)

    return work.iloc[selected].reset_index(drop=True)


def _min_max_1d(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    mn, mx = np.nanmin(a), np.nanmax(a)
    span = mx - mn
    if not np.isfinite(span) or span <= 1e-12:
        return np.full_like(a, 0.5)
    out = (a - mn) / span
    return np.clip(out, 0.0, 1.0)


def _category_codes(df: pd.DataFrame, category_column: str) -> np.ndarray:
    if category_column not in df.columns:
        return np.zeros(len(df), dtype=np.int64)
    cats = df[category_column].map(_norm_cat)
    codes, _ = pd.factorize(cats, sort=False)
    return np.asarray(codes, dtype=np.int64)


def _geo_similarity_matrix(
    df: pd.DataFrame,
    lat_column: str,
    lon_column: str,
    tau_km: float,
    use_geo: bool | None,
) -> np.ndarray | None:
    if use_geo is False:
        return None
    if lat_column not in df.columns or lon_column not in df.columns:
        return None

    lat = pd.to_numeric(df[lat_column], errors="coerce")
    lon = pd.to_numeric(df[lon_column], errors="coerce")
    if use_geo is None and (lat.isna().mean() > 0.5 or lon.isna().mean() > 0.5):
        return None

    la = lat.to_numpy(dtype=np.float64)
    lo = lon.to_numpy(dtype=np.float64)
    la = np.nan_to_num(la, nan=np.nanmedian(la[~np.isnan(la)]) if np.any(~np.isnan(la)) else 0.0)
    lo = np.nan_to_num(lo, nan=np.nanmedian(lo[~np.isnan(lo)]) if np.any(~np.isnan(lo)) else 0.0)

    dist_km = pairwise_haversine_km(la, lo)
    tau = max(float(tau_km), 1e-6)
    return np.exp(-dist_km / tau)


def _renorm_pair(wc: float, wg: float) -> tuple[float, float]:
    wc = max(wc, 0.0)
    wg = max(wg, 0.0)
    s = wc + wg
    if s <= 0:
        return 1.0, 0.0
    return wc / s, wg / s
