"""
Composable ranking pipeline: features → aggregate score → time-of-day context → MMR diversity.

Each step is a thin wrapper so tests can call them independently without running the full chain.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Final, Mapping

from recommendation.crowd_scores import ATTR_CROWD_TIMESTAMP

import numpy as np
import pandas as pd

from recommendation.context_boost import apply_context_boost
from recommendation.data_loader import COL_CATEGORY
from recommendation.diversity import rerank_with_mmr
from recommendation.feature_engineering import compute_features
from recommendation.personalization import compute_preference_score
from recommendation.scoring import (
    KEY_CROWD,
    KEY_DISTANCE,
    KEY_NOVELTY,
    KEY_PREFERENCE,
    KEY_RATING,
    compute_score,
)

SCORE_COLUMN: Final[str] = "score"


def normalize_ranking_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """
    Map legacy ranker keys (``calm``, ``quality``, ``exploration``, ``category``, ``w1``…)
    to :mod:`scoring` semantic keys, then renormalize positive weights to sum to 1.

    Explicit ``crowd``, ``rating``, ``preference``, ``novelty`` override legacy counterparts.
    """
    raw = dict(weights)
    if "w1" in raw and "distance" not in raw:
        raw["distance"] = raw["w1"]
    if "w2" in raw and "crowd" not in raw:
        raw["crowd"] = raw["w2"]
    if "w3" in raw and "rating" not in raw:
        raw["rating"] = raw["w3"]

    merged = {
        KEY_DISTANCE: float(raw.get(KEY_DISTANCE, raw.get("distance", 0.0))),
        KEY_CROWD: float(
            raw.get(KEY_CROWD, raw.get("crowd", raw.get("calm", raw.get("w2", 0.0))))
        ),
        KEY_RATING: float(
            raw.get(KEY_RATING, raw.get("rating", raw.get("quality", raw.get("w3", 0.0))))
        ),
        KEY_PREFERENCE: float(
            raw.get(KEY_PREFERENCE, raw.get("preference", raw.get("category", 0.0)))
        ),
        KEY_NOVELTY: float(raw.get(KEY_NOVELTY, raw.get("novelty", raw.get("exploration", 0.0)))),
    }
    return renormalize_scoring_weights(merged)


def renormalize_scoring_weights(merged: Mapping[str, float]) -> dict[str, float]:
    keys = (KEY_DISTANCE, KEY_CROWD, KEY_RATING, KEY_PREFERENCE, KEY_NOVELTY)
    out = {k: max(0.0, float(merged.get(k, 0.0))) for k in keys}
    s = sum(out.values())
    if s <= 0:
        raise ValueError(
            "At least one positive weight is required (distance, crowd, rating, preference, novelty)."
        )
    return {k: out[k] / s for k in keys}


def attach_preference_categories(
    df: pd.DataFrame,
    *,
    category_preference: Mapping[str, float] | None = None,
    preference_categories: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Copy ``df`` and set ``attrs['preference_categories']`` for :func:`compute_features`."""
    out = df.copy()
    if preference_categories is not None:
        out.attrs = {**out.attrs, "preference_categories": list(preference_categories)}
    elif category_preference is not None and len(category_preference) > 0:
        pref = {str(k).strip().lower(): float(v) for k, v in category_preference.items()}
        allowed = [k for k, v in pref.items() if v > 0.0]
        out.attrs = {**out.attrs, "preference_categories": allowed}
    return out


def step_compute_features(
    df: pd.DataFrame,
    *,
    crowd_signal_column: str | None = None,
    timestamp: datetime | None = None,
    novelty_jitter: float | None = None,
    novelty_dampen: float | None = None,
    user_profile: Mapping[str, Any] | None = None,
    category_column: str = COL_CATEGORY,
    preference_price_column: str | None = None,
) -> pd.DataFrame:
    """Pipeline step 1 — normalized feature columns (see :func:`compute_features`)."""
    feats = compute_features(
        df,
        crowd_signal_column=crowd_signal_column,
        timestamp=timestamp,
        novelty_jitter=novelty_jitter,
        novelty_dampen=novelty_dampen,
    )
    if user_profile is not None:
        feats = compute_preference_score(
            feats,
            user_profile,
            category_column=category_column,
            price_column=preference_price_column,
        )
    return feats


def step_compute_score(
    df: pd.DataFrame,
    weights: Mapping[str, float],
    alpha: float,
    *,
    score_column: str = SCORE_COLUMN,
) -> pd.DataFrame:
    """Pipeline step 2 — non-linear weighted sum into ``score_column`` (no context multiplier)."""
    w = normalize_ranking_weights(weights)
    return compute_score(
        df,
        w,
        alpha,
        context_beta=0.0,
        apply_context_multiplier=False,
        score_column=score_column,
    )


def rank_candidates(
    df: pd.DataFrame,
    weights: Mapping[str, float],
    alpha: float,
    lambda_: float,
    beta: float,
    top_k: int,
    *,
    time_of_day: str | datetime | None = None,
    context_boost_overrides: Mapping[str, Mapping[str, float]] | None = None,
    crowd_signal_column: str | None = None,
    score_column: str = SCORE_COLUMN,
    category_column: str = COL_CATEGORY,
    category_preference: Mapping[str, float] | None = None,
    preference_categories: Iterable[str] | None = None,
    novelty_jitter: float | None = None,
    novelty_dampen: float | None = None,
    use_geo_similarity: bool | None = None,
    timestamp: datetime | None = None,
    user_profile: Mapping[str, Any] | None = None,
    preference_price_column: str | None = None,
) -> pd.DataFrame:
    """
    Full pipeline: :func:`step_compute_features` → :func:`step_compute_score` →
    :func:`~recommendation.context_boost.apply_context_boost` → :func:`~recommendation.diversity.rerank_with_mmr`.

    Parameters
    ----------
    weights
        Legacy keys (``distance``, ``calm``, ``quality``, …) or semantic keys
        (``distance``, ``crowd``, ``rating``, …); see :func:`normalize_ranking_weights`.
    alpha
        Crowd exponent in :func:`compute_score` (must be positive).
    lambda_
        MMR trade-off (higher → more weight on raw score vs diversity).
    beta
        Context strength for ``score *= (1 + beta * context_boost)``.
    top_k
        Rows returned after MMR (capped by ``len(df)``).
    user_profile
        When set, replaces ``preference_score`` after base features via
        :func:`~recommendation.personalization.compute_preference_score`.
    preference_price_column
        Optional POI column for budget reweighting when present (see personalization module).
    timestamp
        Passed to :func:`~recommendation.feature_engineering.compute_features` for time-aware
        crowd scoring via :func:`~recommendation.crowd_scores.get_crowd_score`.
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    if df.empty:
        out = df.copy()
        out[score_column] = pd.Series(dtype=np.float64)
        return out

    prepared = attach_preference_categories(
        df,
        category_preference=category_preference,
        preference_categories=preference_categories,
    )
    ts = timestamp if timestamp is not None else prepared.attrs.get(ATTR_CROWD_TIMESTAMP)
    feats = step_compute_features(
        prepared,
        crowd_signal_column=crowd_signal_column,
        timestamp=ts,
        novelty_jitter=novelty_jitter,
        novelty_dampen=novelty_dampen,
        user_profile=user_profile,
        category_column=category_column,
        preference_price_column=preference_price_column,
    )
    scored = step_compute_score(feats, weights, alpha, score_column=score_column)
    boosted = apply_context_boost(
        scored,
        score_column=score_column,
        category_column=category_column,
        time_of_day=time_of_day,
        beta=beta,
        keyword_boosts=context_boost_overrides,
    )
    k = min(int(top_k), len(boosted))
    return rerank_with_mmr(
        boosted,
        lambda_=lambda_,
        top_k=k,
        score_column=score_column,
        category_column=category_column,
        use_geo_similarity=use_geo_similarity,
    )
