"""Nearby POI recommendation pipeline (crowd-aware when model is plugged in)."""

from recommendation.alternatives import attach_alternative_suggestions
from recommendation.category_filter import filter_by_categories
from recommendation.context_boost import (
    apply_context_boost,
    apply_context_score_multiplier,
    get_context_boost,
    infer_time_bucket_from_datetime,
    normalize_time_bucket,
)
from recommendation.crowd_time_heuristic import (
    diurnal_crowd_multiplier,
    infer_time_slot,
    seasonal_crowd_multiplier,
    time_aware_crowd_multiplier,
    time_slot_crowd_multiplier,
    visit_peak_strength,
    weekend_crowd_multiplier,
)
from recommendation.crowd_scores import (
    ATTR_CROWD_TIMESTAMP,
    COL_CROWD_PRESSURE,
    attach_crowd_scores,
    fallback_mock_from_row,
    get_crowd_score,
    set_crowd_score_provider,
)
from recommendation.crowd_signal import CROWD_COLUMN_CANDIDATES, resolve_crowd_signal_column
from recommendation.diversity import diversify, rerank_with_mmr
from recommendation.explanation_engine import enrich_explanations_alternative_clause
from recommendation.feature_engineering import compute_features
from recommendation.itinerary import (
    generate_itinerary,
    greedy_nearest_neighbor_route,
    travel_time_hours,
)
from recommendation.implicit_feedback import (
    ImplicitFeedbackProfile,
    build_implicit_feedback_profile,
    implicit_scores_blend,
    implicit_scores_cosine,
)
from recommendation.personalization import compute_preference_score
from recommendation.pipeline import (
    DEFAULT_WEIGHTS,
    recommend,
    recommend_with_legacy_list_return,
)
from recommendation.recommendation_pipeline import run_recommendation_pipeline
from recommendation.ranking_pipeline import (
    attach_preference_categories,
    normalize_ranking_weights,
    rank_candidates,
    renormalize_scoring_weights,
    step_compute_features,
    step_compute_score,
)
from recommendation.scoring import compute_score
__all__ = [
    "ATTR_CROWD_TIMESTAMP",
    "COL_CROWD_PRESSURE",
    "CROWD_COLUMN_CANDIDATES",
    "DEFAULT_WEIGHTS",
    "diurnal_crowd_multiplier",
    "infer_time_slot",
    "seasonal_crowd_multiplier",
    "time_aware_crowd_multiplier",
    "time_slot_crowd_multiplier",
    "visit_peak_strength",
    "weekend_crowd_multiplier",
    "attach_alternative_suggestions",
    "attach_crowd_scores",
    "apply_context_boost",
    "apply_context_score_multiplier",
    "attach_preference_categories",
    "ImplicitFeedbackProfile",
    "build_implicit_feedback_profile",
    "compute_features",
    "compute_preference_score",
    "compute_score",
    "implicit_scores_blend",
    "implicit_scores_cosine",
    "diversify",
    "enrich_explanations_alternative_clause",
    "fallback_mock_from_row",
    "filter_by_categories",
    "generate_itinerary",
    "get_context_boost",
    "get_crowd_score",
    "greedy_nearest_neighbor_route",
    "infer_time_bucket_from_datetime",
    "normalize_ranking_weights",
    "normalize_time_bucket",
    "rank_candidates",
    "recommend",
    "recommend_with_legacy_list_return",
    "renormalize_scoring_weights",
    "run_recommendation_pipeline",
    "resolve_crowd_signal_column",
    "rerank_with_mmr",
    "step_compute_features",
    "step_compute_score",
    "travel_time_hours",
    "set_crowd_score_provider",
]
