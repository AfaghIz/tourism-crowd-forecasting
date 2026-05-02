"""
Non-linear aggregation of POI feature columns into a single ``score``.

Feature columns are referenced by name via ``column_map`` so upstream pipelines can swap in
ML-derived ``crowd_score`` (or any column) without changing this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Mapping

import numpy as np
import pandas as pd

from recommendation.context_boost import apply_context_score_multiplier
from recommendation.data_loader import COL_CATEGORY

# Semantic keys expected in ``weights`` (optional aliases below).
KEY_DISTANCE: Final[str] = "distance"
KEY_CROWD: Final[str] = "crowd"
KEY_RATING: Final[str] = "rating"
KEY_PREFERENCE: Final[str] = "preference"
KEY_NOVELTY: Final[str] = "novelty"

_SEMANTIC_KEYS: Final[tuple[str, ...]] = (
    KEY_DISTANCE,
    KEY_CROWD,
    KEY_RATING,
    KEY_PREFERENCE,
    KEY_NOVELTY,
)

# Default column names produced by :func:`feature_engineering.compute_features` — override via ``column_map``.
_DEFAULT_COLUMN_MAP: Final[dict[str, str]] = {
    KEY_DISTANCE: "distance_score",
    KEY_CROWD: "crowd_score",
    KEY_RATING: "rating_score",
    KEY_PREFERENCE: "preference_score",
    KEY_NOVELTY: "novelty_score",
}

_WEIGHT_ALIASES: Final[dict[str, str]] = {
    "w_d": KEY_DISTANCE,
    "w_c": KEY_CROWD,
    "w_r": KEY_RATING,
    "w_p": KEY_PREFERENCE,
    "w_n": KEY_NOVELTY,
}


def compute_score(
    df: pd.DataFrame,
    weights: Mapping[str, float],
    alpha: float = 2.0,
    *,
    column_map: Mapping[str, str] | None = None,
    score_column: str = "score",
    context_beta: float = 0.0,
    context_time_of_day: str | datetime | None = None,
    category_column: str = COL_CATEGORY,
    context_boost_overrides: Mapping[str, Mapping[str, float]] | None = None,
    apply_context_multiplier: bool = True,
) -> pd.DataFrame:
    """
    Compute::

        score =
            w_d * log(1 + distance_feat)
          + w_c * (crowd_feat ** alpha)
          + w_r * log(1 + rating_feat)
          + w_p * preference_feat
          + w_n * novelty_feat

    Parameters
    ----------
    df
        Must contain the feature columns referenced by ``column_map`` (defaults align with
        :mod:`feature_engineering`).
    weights
        Maps **semantic** keys (``distance``, ``crowd``, ``rating``, ``preference``, ``novelty``)
        or aliases (``w_d``, …) to non-negative coefficients. Missing keys count as 0.
    alpha
        Exponent on the crowd feature (must be positive).
    column_map
        Maps each semantic key to the **actual column name** in ``df``. Merged over defaults;
        pass partial overrides only.
    score_column
        Name of the output score column.
    context_beta
        If ``> 0``, scales scores by ``1 + context_beta * get_context_boost(...)`` per row
        (requires ``category_column`` on ``df``).
    context_time_of_day
        Bucket name (e.g. ``\"evening\"``) or ignored when ``context_beta <= 0``.
    category_column
        POI category labels for context matching.
    context_boost_overrides
        Optional per-bucket keyword maps merged with defaults in :mod:`context_boost`.
    apply_context_multiplier
        If ``False``, skip the time-of-day multiplier so callers can apply context in a
        separate pipeline step (see :mod:`ranking_pipeline`).

    Returns
    -------
    pandas.DataFrame
        Copy of ``df`` with ``score_column`` added (overwritten if present).
    """
    if alpha <= 0 or not np.isfinite(alpha):
        raise ValueError("alpha must be a positive finite number.")

    out = df.copy()
    if out.empty:
        out[score_column] = pd.Series(dtype=np.float64)
        return out

    cmap = {**_DEFAULT_COLUMN_MAP, **dict(column_map or {})}
    w_eff = _canonicalize_weights(weights)

    n = len(out)
    total = np.zeros(n, dtype=np.float64)

    # Distance: log(1 + x) — np.log1p
    w = float(w_eff.get(KEY_DISTANCE, 0.0))
    if w != 0.0:
        col = cmap[KEY_DISTANCE]
        _require_column(out, col, KEY_DISTANCE)
        x = np.asarray(pd.to_numeric(out[col], errors="coerce").fillna(0.0), dtype=np.float64)
        total += w * np.log1p(np.clip(x, 0.0, np.inf))

    # Crowd: x ** alpha (crowd_score already "higher = calmer" from features)
    w = float(w_eff.get(KEY_CROWD, 0.0))
    if w != 0.0:
        col = cmap[KEY_CROWD]
        _require_column(out, col, KEY_CROWD)
        x = np.asarray(pd.to_numeric(out[col], errors="coerce").fillna(0.0), dtype=np.float64)
        total += w * np.power(np.clip(x, 0.0, np.inf), alpha)

    # Rating: log(1 + x)
    w = float(w_eff.get(KEY_RATING, 0.0))
    if w != 0.0:
        col = cmap[KEY_RATING]
        _require_column(out, col, KEY_RATING)
        x = np.asarray(pd.to_numeric(out[col], errors="coerce").fillna(0.0), dtype=np.float64)
        total += w * np.log1p(np.clip(x, 0.0, np.inf))

    # Preference & novelty: linear
    w = float(w_eff.get(KEY_PREFERENCE, 0.0))
    if w != 0.0:
        col = cmap[KEY_PREFERENCE]
        _require_column(out, col, KEY_PREFERENCE)
        x = np.asarray(pd.to_numeric(out[col], errors="coerce").fillna(0.0), dtype=np.float64)
        total += w * x

    w = float(w_eff.get(KEY_NOVELTY, 0.0))
    if w != 0.0:
        col = cmap[KEY_NOVELTY]
        _require_column(out, col, KEY_NOVELTY)
        x = np.asarray(pd.to_numeric(out[col], errors="coerce").fillna(0.0), dtype=np.float64)
        total += w * x

    out[score_column] = total
    if apply_context_multiplier:
        out = apply_context_score_multiplier(
            out,
            score_column=score_column,
            category_column=category_column,
            time_of_day=context_time_of_day,
            beta=context_beta,
            keyword_boosts=context_boost_overrides,
        )
    return out


def _require_column(df: pd.DataFrame, col: str, semantic: str) -> None:
    if col not in df.columns:
        raise ValueError(
            f"Column {col!r} not found in DataFrame (required for weight key {semantic!r})."
        )


def _canonicalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in weights.items():
        ks = str(k).strip()
        semantic = _WEIGHT_ALIASES.get(ks, ks)
        if semantic not in _SEMANTIC_KEYS:
            raise ValueError(
                f"Unknown weight key {k!r}. Use one of {_SEMANTIC_KEYS} or aliases {_WEIGHT_ALIASES}."
            )
        out[semantic] = float(v)
    return out
