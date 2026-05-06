"""
Composable recommendation orchestration.

Stages (each callable may be swapped or wrapped by tests / extensions):

1. **Candidates** — load POIs, optional category filter, spatial neighbors.
2. **Crowd column** — :func:`~recommendation.crowd_scores.attach_crowd_scores` (time-aware via ``timestamp``).
3. **Rank pool** — :func:`~recommendation.ranking_pipeline.rank_candidates`: feature computation,
   personalization, non-linear :func:`~recommendation.scoring.compute_score`, context boost,
   **MMR** diversity.
4. **Top-k** — optional per-category cap via :func:`~recommendation.diversity.diversify`.
5. **Explanations** — :func:`~recommendation.explanation_engine.generate_explanations`.
6. **Itinerary** (optional) — :func:`~recommendation.itinerary.generate_itinerary` on the ranked slice.

The public entry point for HTTP / demos is :func:`recommendation.pipeline.recommend`.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Mapping

import pandas as pd
import numpy as np

from recommendation.alternatives import (
    attach_alternative_suggestions,
    build_alternative_payload,
    rank_anchor_alternatives,
)
from recommendation.candidate_generator import get_candidates
from recommendation.category_filter import filter_by_categories
from recommendation.crowd_scores import ATTR_CROWD_TIMESTAMP, attach_crowd_scores
from recommendation.data_loader import load_poi_data
from recommendation.diversity import diversify
from recommendation.explanation_engine import (
    enrich_explanations_alternative_clause,
    generate_explanations,
)
from recommendation.itinerary import TripStyle, generate_itinerary
from recommendation.ranker import rank_candidates

DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "distance": 0.38,
    "calm": 0.42,
    "quality": 0.20,
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(pd.to_numeric(value, errors="coerce"))
        if np.isfinite(v):
            return v
    except (TypeError, ValueError):
        pass
    return float(default)


def validate_origin(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise ValueError(
            "origin_lat must be in [-90, 90] and origin_lon in [-180, 180] (degrees)."
        )


def resolve_default_csv_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    project_root = root.parent
    candidates = (
        project_root / "data" / "processed" / "otm_pois_model_ready_with_nlp_features_exclusions.csv",
        project_root / "data" / "processed" / "otm_pois_model_ready_with_nlp_features.csv",
        project_root / "data" / "processed" / "otm_pois_model_ready_wiki_reviewed.csv",
        root / "data" / "otm_pois_model_ready.csv",
        root / "otm_pois_model_ready.csv",
    )
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


def stage_load_and_filter_candidates(
    origin_lat: float,
    origin_lon: float,
    radius_km: float,
    *,
    csv_path: str | None,
    allowed_categories: list[str] | None,
) -> pd.DataFrame:
    """Load POI table (CSV) and return spatial candidates within ``radius_km``."""
    resolved = csv_path or os.environ.get("RECOMMENDATION_POI_CSV") or str(resolve_default_csv_path())
    poi_df = load_poi_data(str(resolved))
    poi_df = filter_by_categories(poi_df, allowed_categories)
    return get_candidates(poi_df, origin_lat, origin_lon, radius_km=radius_km)


def stage_load_full_poi_table(
    *,
    csv_path: str | None,
    allowed_categories: list[str] | None,
) -> pd.DataFrame:
    resolved = csv_path or os.environ.get("RECOMMENDATION_POI_CSV") or str(resolve_default_csv_path())
    poi_df = load_poi_data(str(resolved))
    return filter_by_categories(poi_df, allowed_categories)


def stage_attach_time_aware_crowd(
    candidates: pd.DataFrame,
    timestamp: datetime | None,
) -> pd.DataFrame:
    """Populate ``crowd_pressure_index``; ``timestamp`` drives time-aware scoring downstream."""
    out = attach_crowd_scores(candidates, timestamp=timestamp)
    if timestamp is not None:
        out.attrs = {**out.attrs, ATTR_CROWD_TIMESTAMP: timestamp}
    return out


def stage_find_anchor_frame(
    poi_df: pd.DataFrame,
    anchor_poi_id: str,
    *,
    timestamp: datetime | None,
) -> pd.DataFrame:
    anchor = poi_df[poi_df["poi_id"].astype("string") == str(anchor_poi_id)].copy()
    if anchor.empty:
        raise ValueError(f"anchor_poi_id not found in POI dataset: {anchor_poi_id}")
    return stage_attach_time_aware_crowd(anchor, timestamp)


def stage_rank_with_diversity_pipeline(
    candidates: pd.DataFrame,
    *,
    weights: Mapping[str, float],
    alpha: float,
    lambda_mmr: float,
    context_beta: float,
    rank_pool_k: int,
    timestamp: datetime | None,
    user_profile: Mapping[str, Any] | None,
    preference_price_column: str | None,
    time_of_day: str | datetime | None,
    context_boost_overrides: Mapping[str, Mapping[str, float]] | None,
    crowd_signal_column: str | None,
    novelty_jitter: float | None,
    novelty_dampen: float | None,
) -> pd.DataFrame:
    """
    Full ranking stack: features → personalization → non-linear score → context → **MMR**.

    Delegates to :func:`~recommendation.ranking_pipeline.rank_candidates`.
    """
    return rank_candidates(
        candidates,
        weights,
        alpha,
        lambda_mmr,
        context_beta,
        rank_pool_k,
        time_of_day=time_of_day,
        context_boost_overrides=context_boost_overrides,
        crowd_signal_column=crowd_signal_column,
        timestamp=timestamp,
        user_profile=user_profile,
        preference_price_column=preference_price_column,
        novelty_jitter=novelty_jitter,
        novelty_dampen=novelty_dampen,
    )


def stage_take_top_k(
    ranked: pd.DataFrame,
    top_k: int,
    *,
    max_per_category: int | None,
) -> pd.DataFrame:
    """Apply optional greedy diversity cap, then ``head(top_k)``."""
    if max_per_category is not None:
        return diversify(
            ranked,
            top_k,
            max_per_category=int(max_per_category),
        )
    return ranked.head(top_k)


def itinerary_order_by_poi_id(stops: list[dict[str, Any]]) -> dict[str, int]:
    """Map ``poi_id`` → 1-based stop order for explanation route context."""
    out: dict[str, int] = {}
    for s in stops:
        pid = s.get("poi_id")
        ord_ = s.get("order")
        if pid is not None and str(pid).strip() and ord_ is not None:
            out[str(pid).strip()] = int(ord_)
    return out


def stage_build_recommendation_payload(
    top_frame: pd.DataFrame,
    *,
    ranked_full: pd.DataFrame,
    include_alternatives: bool,
    alternative_crowded_threshold: float,
    timestamp: datetime | None = None,
    user_profile: Mapping[str, Any] | None = None,
    itinerary_poi_order: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Explanations plus optional alternative suggestions."""
    explanations = generate_explanations(
        top_frame,
        user_profile=user_profile,
        timestamp=timestamp,
        itinerary_poi_order=itinerary_poi_order,
    )
    enrich_row_metadata(explanations, top_frame)
    if include_alternatives:
        attach_alternative_suggestions(
            explanations,
            ranked_full,
            crowded_threshold=alternative_crowded_threshold,
        )
        enrich_explanations_alternative_clause(explanations)
    else:
        for it in explanations:
            it["alternative_suggestion"] = None
    return explanations


def enrich_row_metadata(items: list[dict[str, Any]], df: pd.DataFrame) -> None:
    rows = df.to_dict("records")
    for i, rec in enumerate(rows):
        if i >= len(items):
            break
        pid = rec.get("poi_id")
        if pid is not None:
            items[i]["poi_id"] = pid
        lat, lon = rec.get("lat"), rec.get("lon")
        if lat is not None:
            items[i]["lat"] = float(lat)
        if lon is not None:
            items[i]["lng"] = float(lon)
        preview = rec.get("preview_image")
        if preview:
            items[i]["preview_image"] = preview


def _trip_style_from_profile(user_profile: Mapping[str, Any] | None) -> TripStyle | None:
    if not user_profile:
        return None
    raw = str(user_profile.get("travel_style") or "").strip().lower()
    if raw == "explore":
        return "explore"
    if raw in ("efficient", "fast"):
        return "fast"
    return None


def stage_build_itinerary(
    top_frame: pd.DataFrame,
    origin_lat: float,
    origin_lon: float,
    *,
    time_budget_hours: float,
    user_profile: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ordered route stops + summary from ranked POI rows."""
    trip_style = _trip_style_from_profile(user_profile)
    stops, summary = generate_itinerary(
        top_frame,
        origin_lat,
        origin_lon,
        time_budget_hours=time_budget_hours,
        trip_style=trip_style,
    )
    return stops, summary


def default_itinerary_time_budget_hours(top_k: int) -> float:
    """Heuristic visit-day budget from result size (override via kwargs on ``recommend``)."""
    return float(min(12.0, max(2.5, 0.5 * float(top_k))))


def run_recommendation_pipeline(
    origin_lat: float,
    origin_lon: float,
    timestamp: datetime | None = None,
    user_profile: Mapping[str, Any] | None = None,
    *,
    radius_km: float = 5.0,
    top_k: int = 10,
    include_itinerary: bool = False,
    itinerary_time_budget_hours: float | None = None,
    csv_path: str | None = None,
    weights: dict[str, float] | None = None,
    allowed_categories: list[str] | None = None,
    max_per_category: int | None = None,
    crowd_penalty_power: float = 1.0,
    alpha: float = 2.0,
    lambda_mmr: float = 1.0,
    exploration_weight: float = 0.0,
    include_alternatives: bool = False,
    alternative_crowded_threshold: float = 0.55,
    context_beta: float = 0.0,
    time_of_day: str | None = None,
    context_boost_overrides: Mapping[str, Mapping[str, float]] | None = None,
    preference_price_column: str | None = None,
    crowd_signal_column: str | None = None,
    novelty_jitter: float | None = None,
    novelty_dampen: float | None = None,
    anchor_poi_id: str | None = None,
    anchor_radius_km: float = 3.0,
) -> dict[str, Any]:
    """
    Execute pipeline stages and return ``{"recommendations": [...], "itinerary": ...}``.

    ``itinerary`` is ``None`` when ``include_itinerary`` is ``False``.
    """
    validate_origin(origin_lat, origin_lon)
    if radius_km <= 0:
        raise ValueError("radius_km must be positive.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    if anchor_radius_km <= 0:
        raise ValueError("anchor_radius_km must be positive.")

    if anchor_poi_id is not None and str(anchor_poi_id).strip():
        return run_anchor_alternative_pipeline(
            origin_lat,
            origin_lon,
            str(anchor_poi_id).strip(),
            timestamp=timestamp,
            radius_km=radius_km,
            top_k=top_k,
            csv_path=csv_path,
            allowed_categories=allowed_categories,
            crowd_signal_column=crowd_signal_column,
            anchor_radius_km=anchor_radius_km,
        )

    candidates = stage_load_and_filter_candidates(
        origin_lat,
        origin_lon,
        radius_km,
        csv_path=csv_path,
        allowed_categories=allowed_categories,
    )
    if candidates.empty:
        return {
            "recommendations": [],
            "itinerary": [] if include_itinerary else None,
        }

    candidates = stage_attach_time_aware_crowd(candidates, timestamp)

    w = dict(weights if weights is not None else DEFAULT_WEIGHTS)
    if exploration_weight > 0:
        w = {**w, "exploration": float(exploration_weight)}

    ctx_time: datetime | str | None = None
    if context_beta > 0:
        if time_of_day is not None:
            ctx_time = time_of_day
        elif timestamp is not None:
            ctx_time = timestamp

    eff_alpha = float(crowd_penalty_power) if crowd_penalty_power != 1.0 else float(alpha)

    rank_pool_k = (
        min(len(candidates), max(top_k * 8, top_k + 20))
        if max_per_category is not None
        else top_k
    )

    ranked = stage_rank_with_diversity_pipeline(
        candidates,
        weights=w,
        alpha=eff_alpha,
        lambda_mmr=lambda_mmr,
        context_beta=context_beta,
        rank_pool_k=rank_pool_k,
        timestamp=timestamp,
        user_profile=user_profile,
        preference_price_column=preference_price_column,
        time_of_day=ctx_time,
        context_boost_overrides=context_boost_overrides,
        crowd_signal_column=crowd_signal_column,
        novelty_jitter=novelty_jitter,
        novelty_dampen=novelty_dampen,
    )

    top_frame = stage_take_top_k(ranked, top_k, max_per_category=max_per_category)

    itinerary_stops: list[dict[str, Any]] | None = None
    itinerary_poi_order: dict[str, int] | None = None
    if include_itinerary:
        tb = (
            float(itinerary_time_budget_hours)
            if itinerary_time_budget_hours is not None
            else default_itinerary_time_budget_hours(top_k)
        )
        itinerary_stops, _summary = stage_build_itinerary(
            top_frame,
            origin_lat,
            origin_lon,
            time_budget_hours=tb,
            user_profile=user_profile,
        )
        itinerary_poi_order = itinerary_order_by_poi_id(itinerary_stops)

    recommendations = stage_build_recommendation_payload(
        top_frame,
        ranked_full=ranked,
        include_alternatives=include_alternatives,
        alternative_crowded_threshold=alternative_crowded_threshold,
        timestamp=timestamp,
        user_profile=user_profile,
        itinerary_poi_order=itinerary_poi_order,
    )

    return {
        "recommendations": recommendations,
        "itinerary": itinerary_stops if include_itinerary else None,
    }


def run_anchor_alternative_pipeline(
    origin_lat: float,
    origin_lon: float,
    anchor_poi_id: str,
    *,
    timestamp: datetime | None,
    radius_km: float,
    top_k: int,
    csv_path: str | None,
    allowed_categories: list[str] | None,
    crowd_signal_column: str | None,
    anchor_radius_km: float,
) -> dict[str, Any]:
    """
    Anchor-based alternative recommendation:
    find feasible POIs near the user and rerank those near the anchor by crowd relief,
    similarity, and practicality.
    """
    poi_df = stage_load_full_poi_table(csv_path=csv_path, allowed_categories=allowed_categories)
    if poi_df.empty:
        return {"recommendations": [], "itinerary": None, "mode": "alternatives"}

    anchor_frame = stage_find_anchor_frame(poi_df, anchor_poi_id, timestamp=timestamp)
    anchor_row = anchor_frame.iloc[0]

    origin_candidates = get_candidates(poi_df, origin_lat, origin_lon, radius_km=radius_km)
    if origin_candidates.empty:
        return {"recommendations": [], "itinerary": None, "mode": "alternatives"}

    anchor_candidates = get_candidates(
        origin_candidates,
        float(anchor_row["lat"]),
        float(anchor_row["lon"]),
        radius_km=anchor_radius_km,
        distance_column="distance_to_anchor_km",
    )
    if anchor_candidates.empty:
        return {"recommendations": [], "itinerary": None, "mode": "alternatives"}

    candidate_pool = stage_attach_time_aware_crowd(anchor_candidates, timestamp)
    candidate_pool = candidate_pool.copy()
    if "distance_km" in candidate_pool.columns:
        candidate_pool["distance_to_origin_km"] = candidate_pool["distance_km"]

    anchor_series = anchor_row.copy()
    for key, value in candidate_pool.attrs.items():
        if key not in anchor_series.index:
            anchor_series[key] = value

    ranked = rank_anchor_alternatives(
        anchor_series,
        candidate_pool,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        crowd_signal_column=crowd_signal_column,
        max_anchor_radius_km=anchor_radius_km,
        max_origin_radius_km=radius_km,
        top_k=top_k,
    )

    recommendations = build_alternative_payload(
        ranked,
        anchor_series,
        crowd_signal_column=crowd_signal_column,
    )

    anchor_payload = {
        "poi_id": anchor_series.get("poi_id"),
        "name": anchor_series.get("display_name_en") or anchor_series.get("name"),
        "lat": float(anchor_series["lat"]),
        "lng": float(anchor_series["lon"]),
        "category": anchor_series.get("category_clean"),
        "crowd_signal": _safe_float(anchor_series.get("crowd_pressure_index"), default=0.5),
        "city_demand_score": _safe_float(anchor_series.get("city_demand_score"), default=0.5),
        "crowd_basis_date": anchor_series.get("crowd_basis_date"),
    }

    return {
        "recommendations": recommendations,
        "itinerary": None,
        "mode": "alternatives",
        "anchor": anchor_payload,
    }
