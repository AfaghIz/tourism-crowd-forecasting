"""
User-specific tuning of ``preference_score`` for ranked POI candidates.

Category labels come from the caller's lists (substring match on ``category_clean`` — no
fixed taxonomy). Price-aware budgeting activates only when a numeric or ordinal price column
is present on the frame or passed explicitly.
"""

from __future__ import annotations

from typing import Any, Final, Mapping

import numpy as np
import pandas as pd

from recommendation.data_loader import COL_CATEGORY
from recommendation.implicit_feedback import (
    build_implicit_feedback_profile,
    implicit_scores_blend,
    implicit_scores_cosine,
)
from recommendation.feature_engineering import (
    COL_DISTANCE_SCORE,
    COL_NOVELTY_SCORE,
    COL_PREFERENCE_SCORE,
)

# Try these column names for price / spend signals (first match wins).
_PRICE_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "price_numeric",
    "price",
    "avg_price",
    "estimated_price",
    "price_level",
)

_TRAVEL_EFFICIENT: Final[str] = "efficient"
_TRAVEL_EXPLORE: Final[str] = "explore"

# How much implicit feedback shifts the category component when interaction data is present.
_DEFAULT_IMPLICIT_BLEND: Final[float] = 0.42


def _norm_tokens(items: object) -> set[str]:
    if not items:
        return set()
    out: set[str] = set()
    for x in items:
        s = str(x).strip().lower()
        if s:
            out.add(s)
    return out


def _category_component(
    df: pd.DataFrame,
    *,
    preferred: set[str],
    avoided: set[str],
    category_column: str,
) -> np.ndarray:
    """Per-row score from substring rules on ``category_clean`` (avoided → penalize, preferred → boost)."""
    n = len(df)
    if category_column not in df.columns:
        return np.full(n, 0.5, dtype=np.float64)
    blob = df[category_column].astype("string").fillna("").str.strip().str.lower()
    mask_avoid = np.zeros(n, dtype=bool)
    for lab in avoided:
        mask_avoid |= blob.str.contains(lab, regex=False, na=False).to_numpy(dtype=bool)
    mask_pref = np.zeros(n, dtype=bool)
    for lab in preferred:
        mask_pref |= blob.str.contains(lab, regex=False, na=False).to_numpy(dtype=bool)
    # Avoided wins over preferred when both match.
    return np.where(mask_avoid, 0.15, np.where(mask_pref, 0.92, 0.5)).astype(np.float64)


def _min_max_unit(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    mn, mx = np.nanmin(a), np.nanmax(a)
    span = mx - mn
    if not np.isfinite(span) or span <= 1e-12:
        return np.full_like(a, 0.5)
    return np.clip((a - mn) / span, 0.0, 1.0)


def _resolve_price_series(df: pd.DataFrame, explicit_column: str | None) -> tuple[np.ndarray | None, bool]:
    """Returns (normalized expensive-ness in [0,1] or None, is_ordinal_text)."""
    col = explicit_column
    if col is None:
        for name in _PRICE_COLUMN_CANDIDATES:
            if name in df.columns:
                col = name
                break
    if col is None or col not in df.columns:
        return None, False

    raw = df[col]
    numeric = pd.to_numeric(raw, errors="coerce")
    valid_n = int(numeric.notna().sum())
    if valid_n >= max(1, len(df) // 2):
        vals = numeric.to_numpy(dtype=np.float64)
        med = float(np.nanmedian(vals))
        if not np.isfinite(med):
            med = 0.5
        vals = np.nan_to_num(vals, nan=med)
        return _min_max_unit(vals), False

    # Ordinal text e.g. low/medium/high
    mapping = {"low": 0.2, "budget": 0.2, "medium": 0.5, "mid": 0.5, "high": 0.85, "luxury": 0.95}
    scores = []
    for v in raw.astype("string").fillna(""):
        key = str(v).strip().lower()
        scores.append(mapping.get(key, 0.5))
    return np.asarray(scores, dtype=np.float64), True


def _budget_component(price_norm: np.ndarray, budget_level: str) -> np.ndarray:
    """Higher score = better match to user's budget band."""
    b = str(budget_level or "medium").strip().lower()
    x = np.clip(price_norm.astype(np.float64), 0.0, 1.0)
    if b in ("low", "budget"):
        return np.clip(1.0 - x, 0.0, 1.0)
    if b in ("high", "luxury"):
        return np.clip(x, 0.0, 1.0)
    # medium
    return np.clip(1.0 - np.abs(x - 0.5) * 2.0, 0.0, 1.0)


def _style_weights(travel_style: str) -> tuple[float, float, float, float]:
    """
    Returns weights (category, distance_score, novelty_score, budget) summing to 1.
    """
    s = str(travel_style or _TRAVEL_EFFICIENT).strip().lower()
    if s == _TRAVEL_EXPLORE:
        return (0.28, 0.14, 0.38, 0.20)
    return (0.28, 0.38, 0.14, 0.20)


def compute_preference_score(
    df: pd.DataFrame,
    user_profile: Mapping[str, Any],
    *,
    category_column: str = COL_CATEGORY,
    price_column: str | None = None,
) -> pd.DataFrame:
    """
    Compute ``preference_score`` in ``[0, 1]`` from a flexible user profile.

    Parameters
    ----------
    df
        Candidate POIs, typically after :func:`~recommendation.feature_engineering.compute_features`
        so ``distance_score`` and ``novelty_score`` exist.
    user_profile
        Supported keys (all optional):

        - ``preferred_categories``: iterable of substrings to reward on ``category_clean``.
        - ``avoided_categories``: iterable of substrings to penalize (stronger than neutral).
        - ``budget_level``: ``\"low\"`` | ``\"medium\"`` | ``\"high\"`` (free-form synonyms accepted).
        - ``travel_style``: ``\"efficient\"`` (weight proximity) or ``\"explore\"`` (weight novelty).
        - **Implicit feedback** (lightweight; requires ``poi_category_lookup``):

          - ``visited_pois``, ``liked_pois``, ``skipped_pois`` — iterables of ``poi_id`` strings.
          - ``poi_category_lookup``: mapping ``poi_id`` → category label (typically ``category_clean``).
          - ``implicit_blend_weight`` — blend explicit vs implicit category scores (default ``0.42``).
          - ``implicit_use_cosine`` — if true, use cosine-style similarity instead of affinity blend.
          - ``implicit_like_weight`` — likes vs visits (default ``2.0``).
          - ``implicit_skip_lambda`` — skip penalty strength (default ``0.62``).

    price_column
        If set, use this column for budget fit; otherwise the first available among common
        price column names is used.

    Returns
    -------
    pandas.DataFrame
        Copy of ``df`` with ``preference_score`` added or overwritten.
    """
    out = df.copy()
    if df.empty:
        out[COL_PREFERENCE_SCORE] = pd.Series(dtype=np.float64)
        return out

    preferred = _norm_tokens(user_profile.get("preferred_categories"))
    avoided = _norm_tokens(user_profile.get("avoided_categories"))
    budget_level = str(user_profile.get("budget_level") or "medium")
    travel_style = str(user_profile.get("travel_style") or _TRAVEL_EFFICIENT)

    cat_explicit = _category_component(out, preferred=preferred, avoided=avoided, category_column=category_column)
    cat_part = cat_explicit

    lookup = user_profile.get("poi_category_lookup")
    if isinstance(lookup, Mapping):
        v = list(user_profile.get("visited_pois") or [])
        lk = list(user_profile.get("liked_pois") or [])
        sk = list(user_profile.get("skipped_pois") or [])
        if v or lk or sk:
            like_w = float(user_profile.get("implicit_like_weight", 2.0))
            profile = build_implicit_feedback_profile(
                v,
                lk,
                sk,
                lookup,
                like_weight=like_w,
            )
            if profile is not None:
                skip_lam = float(user_profile.get("implicit_skip_lambda", 0.62))
                if user_profile.get("implicit_use_cosine", False):
                    implicit_part = implicit_scores_cosine(
                        out,
                        profile,
                        category_column=category_column,
                        skip_lambda=skip_lam,
                    )
                else:
                    implicit_part = implicit_scores_blend(
                        out,
                        profile,
                        category_column=category_column,
                        skip_lambda=skip_lam,
                    )
                w_impl = float(user_profile.get("implicit_blend_weight", _DEFAULT_IMPLICIT_BLEND))
                w_impl = max(0.0, min(1.0, w_impl))
                cat_part = (1.0 - w_impl) * cat_explicit + w_impl * implicit_part

    dist_series = (
        pd.to_numeric(out[COL_DISTANCE_SCORE], errors="coerce").fillna(0.5).to_numpy(dtype=np.float64)
        if COL_DISTANCE_SCORE in out.columns
        else np.full(len(out), 0.5, dtype=np.float64)
    )
    nov_series = (
        pd.to_numeric(out[COL_NOVELTY_SCORE], errors="coerce").fillna(0.5).to_numpy(dtype=np.float64)
        if COL_NOVELTY_SCORE in out.columns
        else np.full(len(out), 0.5, dtype=np.float64)
    )

    price_norm, _ = _resolve_price_series(out, price_column)
    if price_norm is None or len(price_norm) != len(out):
        budget_part = np.full(len(out), 0.5, dtype=np.float64)
        w_cat, w_dist, w_nov, w_bud = _style_weights(travel_style)
        s = w_cat + w_dist + w_nov
        w_cat, w_dist, w_nov = w_cat / s, w_dist / s, w_nov / s
        blend = w_cat * cat_part + w_dist * dist_series + w_nov * nov_series
    else:
        budget_part = _budget_component(price_norm, budget_level)
        w_cat, w_dist, w_nov, w_bud = _style_weights(travel_style)
        blend = w_cat * cat_part + w_dist * dist_series + w_nov * nov_series + w_bud * budget_part

    out[COL_PREFERENCE_SCORE] = np.clip(blend, 0.0, 1.0)
    return out
