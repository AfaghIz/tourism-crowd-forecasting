"""
Suggest anchor-based, less crowded alternatives.

The original helper ``attach_alternative_suggestions`` is kept for legacy generic ranking.
The new core path is :func:`rank_anchor_alternatives`, which implements the thesis-aligned
alternative-selection mechanism: crowd relief + similarity + practicality.
"""

from __future__ import annotations

from typing import Any, Final

import numpy as np
import pandas as pd

from recommendation.candidate_generator import haversine_km
from recommendation.data_loader import COL_CATEGORY
from recommendation.crowd_signal import resolve_crowd_signal_column
from recommendation.ranker import COL_DISTANCE_KM

COL_POI_ID: Final[str] = "poi_id"
COL_LAT: Final[str] = "lat"
COL_LON: Final[str] = "lon"

SUBTYPE_COLUMNS: Final[tuple[str, ...]] = (
    "is_mosque",
    "is_church",
    "is_synagogue",
    "is_cathedral",
    "is_palace",
    "is_museum",
    "is_monument",
    "is_cemetery",
    "is_fortress",
    "is_tower",
    "is_hamam",
    "is_bridge",
    "is_tekke_or_dergah",
    "is_tomb",
    "is_fountain",
    "is_gate",
)

FAMILY_COLUMNS: Final[tuple[str, ...]] = (
    "family_iconic_landmark",
    "family_religious_monumental",
    "family_museum_cultural",
    "family_viewpoint_scenic",
    "family_palatial_imperial",
    "family_neighborhood_heritage",
)


def choose_alternative_weights(city_demand_score: float) -> dict[str, float]:
    """
    Demand-aware policy weights for alternative recommendation.

    The lower-data setting of this project favors interpretable policy weights over a
    learned ranking model. We increase crowd sensitivity during high citywide demand.
    """
    if city_demand_score >= 0.65:
        return {"crowd_relief": 0.60, "similarity": 0.25, "practicality": 0.15}
    if city_demand_score >= 0.35:
        return {"crowd_relief": 0.45, "similarity": 0.35, "practicality": 0.20}
    return {"crowd_relief": 0.30, "similarity": 0.45, "practicality": 0.25}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(pd.to_numeric(value, errors="coerce"))
        if np.isfinite(v):
            return v
    except (TypeError, ValueError):
        pass
    return float(default)


def _anchor_active_subtypes(anchor_row: pd.Series) -> list[str]:
    active: list[str] = []
    for col in SUBTYPE_COLUMNS:
        if int(_safe_float(anchor_row.get(col, 0), default=0.0)) == 1:
            active.append(col)
    return active


def _anchor_active_families(anchor_row: pd.Series) -> list[str]:
    active: list[str] = []
    for col in FAMILY_COLUMNS:
        if int(_safe_float(anchor_row.get(col, 0), default=0.0)) == 1:
            active.append(col)
    return active


def _requires_prestige_alignment(anchor_row: pd.Series) -> bool:
    """Major hybrid landmarks should prefer other major landmarks as substitutes."""
    family_count = sum(int(_safe_float(anchor_row.get(col, 0), default=0.0)) for col in FAMILY_COLUMNS)
    is_iconic = int(_safe_float(anchor_row.get("family_iconic_landmark", 0), default=0.0)) == 1
    rate = _safe_float(anchor_row.get("rate"), default=0.0)
    wiki_pageviews = _safe_float(anchor_row.get("wiki_pageviews_total"), default=0.0)
    return is_iconic and family_count >= 2 and (rate >= 7.0 or wiki_pageviews >= 100_000)


def _has_family(row: pd.Series, family_col: str) -> bool:
    return int(_safe_float(row.get(family_col, 0), default=0.0)) == 1


def _has_subtype(row: pd.Series, subtype_col: str) -> bool:
    return int(_safe_float(row.get(subtype_col, 0), default=0.0)) == 1


def _anchor_intent(anchor_row: pd.Series) -> str:
    """Map anchors into a small set of recommendation intents."""
    has_iconic = _has_family(anchor_row, "family_iconic_landmark")
    has_religious = _has_family(anchor_row, "family_religious_monumental")
    has_museum = _has_family(anchor_row, "family_museum_cultural")
    has_viewpoint = _has_family(anchor_row, "family_viewpoint_scenic")
    has_palatial = _has_family(anchor_row, "family_palatial_imperial")
    has_heritage = _has_family(anchor_row, "family_neighborhood_heritage")

    if has_iconic and has_religious and has_museum:
        return "iconic_hybrid_landmark"
    if has_iconic and has_viewpoint:
        return "scenic_iconic_landmark"
    if has_iconic and has_religious:
        return "iconic_religious_landmark"
    if has_palatial:
        return "palatial_imperial"
    if has_museum:
        return "museum_cultural"
    if has_religious:
        return "monumental_religious"
    if has_heritage:
        return "neighborhood_heritage"
    return "generic"


def _candidate_passes_compatibility(
    anchor_row: pd.Series,
    row: pd.Series,
    *,
    anchor_subtype_count: int,
    overlap_count: int,
    family_overlap_count: int,
) -> bool:
    """
    Conservative compatibility gate before final reranking.

    Family overlap is the main experience-level compatibility check.
    Subtype overlap refines stricter landmark anchors such as Hagia Sophia.
    """
    anchor_families = _anchor_active_families(anchor_row)
    intent = _anchor_intent(anchor_row)

    if intent == "iconic_hybrid_landmark":
        religious_overlap = (
            (_has_subtype(anchor_row, "is_mosque") and _has_subtype(row, "is_mosque"))
            or (_has_subtype(anchor_row, "is_church") and _has_subtype(row, "is_church"))
            or (_has_subtype(anchor_row, "is_synagogue") and _has_subtype(row, "is_synagogue"))
            or (_has_subtype(anchor_row, "is_cathedral") and _has_subtype(row, "is_cathedral"))
        )
        strong_hybrid_match = (
            _has_family(row, "family_religious_monumental")
            and _has_family(row, "family_museum_cultural")
            and overlap_count >= 2
        )
        if _has_family(row, "family_iconic_landmark"):
            return religious_overlap or family_overlap_count >= 3 or overlap_count >= 2
        return religious_overlap and strong_hybrid_match

    if intent == "scenic_iconic_landmark":
        is_direct_scenic_structure = _has_subtype(row, "is_tower") or _has_subtype(row, "is_bridge")
        is_iconic_scenic_landmark = _has_family(row, "family_iconic_landmark") and _has_family(
            row, "family_viewpoint_scenic"
        )
        return is_direct_scenic_structure or is_iconic_scenic_landmark

    if intent in {"iconic_religious_landmark", "monumental_religious"}:
        if not _has_family(row, "family_religious_monumental"):
            return False
        if intent == "iconic_religious_landmark":
            return _has_family(row, "family_iconic_landmark") or overlap_count >= 1
        return True

    if intent == "palatial_imperial":
        return _has_family(row, "family_palatial_imperial") or _has_family(row, "family_museum_cultural")

    if intent == "museum_cultural":
        return _has_family(row, "family_museum_cultural") or overlap_count >= 1

    if intent == "neighborhood_heritage":
        return _has_family(row, "family_neighborhood_heritage")

    if _requires_prestige_alignment(anchor_row):
        candidate_is_iconic = _has_family(row, "family_iconic_landmark")
        if not candidate_is_iconic:
            return False

    if family_overlap_count <= 0 and overlap_count <= 0:
        return False

    if anchor_subtype_count >= 3:
        return family_overlap_count >= 1 and overlap_count >= 1

    if anchor_families:
        return family_overlap_count >= 1

    return True


def rank_anchor_alternatives(
    anchor_row: pd.Series,
    candidate_pool: pd.DataFrame,
    *,
    origin_lat: float,
    origin_lon: float,
    crowd_signal_column: str | None = None,
    max_anchor_radius_km: float = 3.0,
    max_origin_radius_km: float = 5.0,
    top_k: int = 10,
) -> pd.DataFrame:
    """
    Rank nearby alternatives to an anchor POI using an interpretable three-part score:

    1. crowd relief relative to the anchor
    2. semantic similarity to the anchor
    3. spatial practicality from the anchor/user context
    """
    if candidate_pool.empty:
        return candidate_pool.copy()

    pool = candidate_pool.copy()
    crowd_col = resolve_crowd_signal_column(pool, crowd_signal_column)
    anchor_crowd = _safe_float(anchor_row.get(crowd_col), default=0.5)
    anchor_lat = float(anchor_row[COL_LAT])
    anchor_lon = float(anchor_row[COL_LON])
    anchor_category = _norm(str(anchor_row.get(COL_CATEGORY, "")))
    anchor_subtype_count = max(
        1,
        int(sum(int(_safe_float(anchor_row.get(c, 0), default=0.0)) for c in SUBTYPE_COLUMNS)),
    )
    anchor_family_count = max(
        1,
        int(sum(int(_safe_float(anchor_row.get(c, 0), default=0.0)) for c in FAMILY_COLUMNS)),
    )
    city_demand_score = _safe_float(anchor_row.get("city_demand_score"), default=0.5)
    weights = choose_alternative_weights(city_demand_score)

    pool = pool[pool[COL_POI_ID].astype(str) != str(anchor_row.get(COL_POI_ID))].copy()
    if pool.empty:
        return pool

    pool["distance_to_anchor_km"] = haversine_km(anchor_lat, anchor_lon, pool[COL_LAT], pool[COL_LON])
    pool["distance_to_origin_km"] = haversine_km(origin_lat, origin_lon, pool[COL_LAT], pool[COL_LON])
    pool["same_category"] = (
        pool[COL_CATEGORY].astype("string").fillna("").str.strip().str.lower().eq(anchor_category).astype(int)
    )
    anchor_intent = _anchor_intent(anchor_row)

    crowd_vals = pd.to_numeric(pool[crowd_col], errors="coerce").fillna(0.5)
    pool["crowd_relief"] = np.maximum(0.0, (anchor_crowd - crowd_vals) / max(anchor_crowd, 1e-9))
    pool = pool.loc[pool["crowd_relief"] > 0.0].copy()
    if pool.empty:
        return pool

    keep_mask: list[bool] = []
    family_overlap_counts: list[float] = []
    overlap_counts: list[float] = []
    for _, row in pool.iterrows():
        overlap = 0
        for col in SUBTYPE_COLUMNS:
            if col not in pool.columns or col not in anchor_row.index:
                continue
            a = int(_safe_float(anchor_row.get(col, 0), default=0.0))
            b = int(_safe_float(row.get(col, 0), default=0.0))
            if a == 1 and b == 1:
                overlap += 1

        family_overlap = 0
        for col in FAMILY_COLUMNS:
            if col not in pool.columns or col not in anchor_row.index:
                continue
            a = int(_safe_float(anchor_row.get(col, 0), default=0.0))
            b = int(_safe_float(row.get(col, 0), default=0.0))
            if a == 1 and b == 1:
                family_overlap += 1
        keep_mask.append(
            _candidate_passes_compatibility(
                anchor_row,
                row,
                anchor_subtype_count=anchor_subtype_count,
                overlap_count=overlap,
                family_overlap_count=family_overlap,
            )
        )
        family_overlap_counts.append(float(family_overlap))
        overlap_counts.append(float(overlap))

    pool["passes_anchor_compatibility"] = keep_mask
    pool["family_overlap_count"] = family_overlap_counts
    pool["subtype_overlap_count"] = overlap_counts
    pool = pool.loc[pool["passes_anchor_compatibility"] == True].copy()
    if pool.empty:
        return pool
    pool["family_overlap_ratio"] = pool["family_overlap_count"] / float(anchor_family_count)
    pool["subtype_overlap_ratio"] = pool["subtype_overlap_count"] / float(anchor_subtype_count)
    pool["similarity_score"] = (
        0.45 * pool["family_overlap_ratio"].clip(0.0, 1.0)
        + 0.35 * pool["subtype_overlap_ratio"].clip(0.0, 1.0)
        + 0.20 * pool["same_category"]
    )
    if anchor_intent == "iconic_hybrid_landmark":
        pool["similarity_score"] += 0.10 * pool["family_overlap_ratio"].clip(0.0, 1.0)
        pure_museum_match = (
            pd.to_numeric(pool.get("family_museum_cultural", 0), errors="coerce").fillna(0.0).clip(0.0, 1.0).eq(1.0)
            & pd.to_numeric(pool.get("family_religious_monumental", 0), errors="coerce").fillna(0.0).clip(0.0, 1.0).eq(0.0)
        )
        pool.loc[pure_museum_match, "similarity_score"] -= 0.10
    elif anchor_intent == "scenic_iconic_landmark":
        scenic_flag = pd.to_numeric(pool.get("family_viewpoint_scenic", 0), errors="coerce").fillna(0.0).clip(0.0, 1.0)
        pool["similarity_score"] += 0.10 * scenic_flag
    elif anchor_intent in {"iconic_religious_landmark", "monumental_religious"}:
        religious_flag = pd.to_numeric(pool.get("family_religious_monumental", 0), errors="coerce").fillna(0.0).clip(0.0, 1.0)
        pool["similarity_score"] += 0.10 * religious_flag
    pool["similarity_score"] = pool["similarity_score"].clip(0.0, 1.0)

    anchor_distance_score = 1.0 - (pool["distance_to_anchor_km"] / max(max_anchor_radius_km, 1e-9)).clip(0.0, 1.0)
    origin_distance_score = 1.0 - (pool["distance_to_origin_km"] / max(max_origin_radius_km, 1e-9)).clip(0.0, 1.0)
    pool["practicality_score"] = (0.6 * anchor_distance_score + 0.4 * origin_distance_score).clip(0.0, 1.0)

    pool["alternative_score"] = (
        weights["crowd_relief"] * pool["crowd_relief"]
        + weights["similarity"] * pool["similarity_score"]
        + weights["practicality"] * pool["practicality_score"]
    )
    pool["recommendation_policy"] = (
        f"crowd={weights['crowd_relief']:.2f},"
        f" similarity={weights['similarity']:.2f},"
        f" practicality={weights['practicality']:.2f}"
    )
    return pool.sort_values(
        ["alternative_score", "crowd_relief", "similarity_score", "practicality_score"],
        ascending=False,
    ).head(top_k)


def build_alternative_payload(
    ranked_alternatives: pd.DataFrame,
    anchor_row: pd.Series,
    *,
    crowd_signal_column: str | None = None,
) -> list[dict[str, Any]]:
    """Convert ranked alternative rows into API-ready recommendation objects."""
    if ranked_alternatives.empty:
        return []

    crowd_col = resolve_crowd_signal_column(ranked_alternatives, crowd_signal_column)
    anchor_name = anchor_row.get("display_name_en") or anchor_row.get("name") or "the selected POI"
    anchor_crowd = _safe_float(anchor_row.get(crowd_col), default=0.5)

    items: list[dict[str, Any]] = []
    for _, row in ranked_alternatives.iterrows():
        alt_crowd = _safe_float(row.get(crowd_col), default=0.5)
        crowd_drop = max(0.0, anchor_crowd - alt_crowd)
        name = row.get("display_name_en") or row.get("name")
        item = {
            "poi_id": row.get(COL_POI_ID),
            "name": name,
            "lat": float(row[COL_LAT]),
            "lng": float(row[COL_LON]),
            "score": float(row["alternative_score"]),
            "distance_km": round(float(row.get("distance_to_origin_km", np.nan)), 3),
            "distance_to_anchor_km": round(float(row.get("distance_to_anchor_km", np.nan)), 3),
            "category": row.get(COL_CATEGORY),
            "crowd_signal": round(alt_crowd, 4),
            "crowd_relief": round(float(row.get("crowd_relief", 0.0)), 4),
            "similarity": round(float(row.get("similarity_score", 0.0)), 4),
            "practicality": round(float(row.get("practicality_score", 0.0)), 4),
            "family_overlap_count": int(_safe_float(row.get("family_overlap_count", 0), default=0.0)),
            "subtype_overlap_count": int(_safe_float(row.get("subtype_overlap_count", 0), default=0.0)),
            "alternative_to": anchor_name,
            "explanation": (
                f"{name} is a less crowded alternative to {anchor_name}, "
                f"with crowd pressure lower by {crowd_drop:.2f}, about "
                f"{float(row.get('distance_to_anchor_km', 0.0)):.1f} km from the anchor."
            ),
        }
        items.append(item)
    return items


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
