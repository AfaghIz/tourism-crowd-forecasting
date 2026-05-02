"""
Suggest a similar, less crowded POI when a recommendation is comparatively busy.
"""

from __future__ import annotations

from typing import Any, Final

import pandas as pd

from recommendation.candidate_generator import haversine_km
from recommendation.data_loader import COL_CATEGORY
from recommendation.crowd_signal import resolve_crowd_signal_column
from recommendation.ranker import COL_DISTANCE_KM

COL_POI_ID: Final[str] = "poi_id"
COL_LAT: Final[str] = "lat"
COL_LON: Final[str] = "lon"


def attach_alternative_suggestions(
    items: list[dict[str, Any]],
    ranked_pool: pd.DataFrame,
    *,
    crowded_threshold: float = 0.55,
    min_crowd_delta: float = 0.08,
    max_extra_distance_km: float = 2.5,
    crowd_signal_column: str | None = None,
    category_column: str = COL_CATEGORY,
) -> None:
    """
    For each item, if its crowd signal is at or above ``crowded_threshold``, search
    ``ranked_pool`` for another POI with the **same category**, **strictly lower** crowd,
    and within ``max_extra_distance_km`` of the primary POI's distance from origin
    (absolute distance on sphere compared row-wise).

    Mutates each ``items`` dict in place with key ``alternative_suggestion``:
    either ``None`` or a small JSON-serializable dict describing the alternative.

    Parameters
    ----------
    items
        Output rows from the explanation step (must align with the dataframe slice used
        to build them).
    ranked_pool
        Typically the full ranked candidate set (not only top-k) so alternatives can be
        found beyond the displayed list.
    crowded_threshold
        Crowd signal above which we try to attach an alternative (0–1 scale).
    min_crowd_delta
        Alternative must be at least this much lower on the crowd signal.
    max_extra_distance_km
        Alternative's straight-line distance from the primary POI must not exceed this.
    """
    if not items or ranked_pool.empty:
        for it in items:
            it["alternative_suggestion"] = None
        return

    crowd_col = resolve_crowd_signal_column(ranked_pool, crowd_signal_column)
    pool = ranked_pool.reset_index(drop=True)

    for i, it in enumerate(items):
        pid = it.get("poi_id")
        if pid is None:
            it["alternative_suggestion"] = None
            continue

        primary_rows = pool[pool[COL_POI_ID] == pid]
        if primary_rows.empty:
            it["alternative_suggestion"] = None
            continue

        pr = primary_rows.iloc[0]
        try:
            c_pri = float(pd.to_numeric(pr[crowd_col], errors="coerce"))
        except (TypeError, ValueError):
            c_pri = 0.5

        if c_pri < crowded_threshold or pd.isna(pr.get(crowd_col)):
            it["alternative_suggestion"] = None
            continue

        cat = _norm(str(pr.get(category_column, "")))
        plat = float(pr[COL_LAT])
        plon = float(pr[COL_LON])

        best: dict[str, Any] | None = None
        best_score = -1.0

        for _, cand in pool.iterrows():
            if cand[COL_POI_ID] == pid:
                continue
            if _norm(str(cand.get(category_column, ""))) != cat:
                continue
            try:
                c_alt = float(pd.to_numeric(cand[crowd_col], errors="coerce"))
            except (TypeError, ValueError):
                continue
            if c_pri - c_alt < min_crowd_delta:
                continue

            d_sep = haversine_km(
                plat,
                plon,
                float(cand[COL_LAT]),
                float(cand[COL_LON]),
            )
            if d_sep > max_extra_distance_km:
                continue

            calm_gain = c_pri - c_alt
            tie = calm_gain / (1e-6 + d_sep)
            if tie > best_score:
                best_score = tie
                best = {
                    "poi_id": cand[COL_POI_ID],
                    "name": cand.get("display_name_en") or cand.get("name"),
                    "lat": float(cand[COL_LAT]),
                    "lng": float(cand[COL_LON]),
                    "distance_km_from_primary": round(d_sep, 3),
                    "crowd_signal": round(c_alt, 4),
                    "category": str(cand.get(category_column, "")).lower(),
                    "reason": (
                        f"Same category ({cat}), lower crowd signal "
                        f"({c_alt:.2f} vs {c_pri:.2f}), about {d_sep:.1f} km away."
                    ),
                }

        it["alternative_suggestion"] = best

    # Ensure key exists for every row
    for it in items:
        if "alternative_suggestion" not in it:
            it["alternative_suggestion"] = None


def _norm(s: str) -> str:
    return s.strip().lower() or "unknown"
