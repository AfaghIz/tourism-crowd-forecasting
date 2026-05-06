"""
End-to-end recommendation API.

Orchestration and stage functions live in :mod:`recommendation.recommendation_pipeline`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from recommendation.recommendation_pipeline import DEFAULT_WEIGHTS, run_recommendation_pipeline


def recommend(
    origin_lat: float,
    origin_lon: float,
    timestamp: datetime | None = None,
    user_profile: Mapping[str, Any] | None = None,
    *,
    radius_km: float = 5.0,
    top_k: int = 10,
    include_itinerary: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Full pipeline: candidates → time-aware crowd → features & personalization → non-linear score
    → optional context → **MMR** → explanations; optionally an ordered **itinerary**.

    Parameters
    ----------
    origin_lat, origin_lon
        Search origin (WGS84 degrees).
    timestamp
        Visit instant for crowd heuristics / models and feature engineering.
    user_profile
        Personalization mapping for :func:`~recommendation.personalization.compute_preference_score`
        (explicit prefs, implicit feedback, budget, travel style). Travel style maps to itinerary
        pace when ``include_itinerary=True``.
    radius_km, top_k
        Spatial radius and number of returned recommendations.
    include_itinerary
        When ``True``, builds an optimized route over the top-k POI rows and sets ``itinerary``.
    **kwargs
        Forwarded to :func:`~recommendation.recommendation_pipeline.run_recommendation_pipeline`
        (``csv_path``, ``weights``, ``alpha``, ``lambda_mmr``, ``context_beta``, …).

    Returns
    -------
    dict
        ``{"recommendations": [...], "itinerary": [...] | None}``
        — ``itinerary`` is ``None`` unless ``include_itinerary`` is ``True``.
    """
    return run_recommendation_pipeline(
        origin_lat,
        origin_lon,
        timestamp,
        user_profile,
        radius_km=radius_km,
        top_k=top_k,
        include_itinerary=include_itinerary,
        **kwargs,
    )


def recommend_with_legacy_list_return(
    origin_lat: float,
    origin_lon: float,
    timestamp: datetime | None = None,
    user_profile: Mapping[str, Any] | None = None,
    *,
    radius_km: float = 5.0,
    top_k: int = 10,
    include_itinerary: bool = False,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Same as :func:`recommend`, but returns only the ``recommendations`` list."""
    out = recommend(
        origin_lat,
        origin_lon,
        timestamp,
        user_profile,
        radius_km=radius_km,
        top_k=top_k,
        include_itinerary=include_itinerary,
        **kwargs,
    )
    return out["recommendations"]


__all__ = [
    "DEFAULT_WEIGHTS",
    "recommend",
    "recommend_with_legacy_list_return",
]
