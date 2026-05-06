"""
Lightweight implicit feedback from POI interactions (no ML models).

Aggregates visit / like / skip events into category-level distributions, then scores candidate
rows via fuzzy category match. Optional cosine mode compares a normalized net preference vector
to a soft one-hot derived from each row's ``category_clean``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from recommendation.data_loader import COL_CATEGORY

COL_POI_ID: str = "poi_id"

# Substring alignment bonus (same taxonomy, slightly different wording).
_SIM_SUBSTRING: float = 0.72


@dataclass(frozen=True)
class ImplicitFeedbackProfile:
    """Normalized category masses derived from interaction lists."""

    positive_distribution: dict[str, float]
    skip_distribution: dict[str, float]
    visit_counts: dict[str, int]
    like_counts: dict[str, int]
    skip_counts: dict[str, int]


def _norm_id(pid: object) -> str:
    return str(pid or "").strip()


def _norm_cat_label(value: object) -> str:
    return str(value or "").strip().lower()


def _category_similarity(candidate_blob: str, key: str) -> float:
    if not candidate_blob or not key:
        return 0.0
    if candidate_blob == key:
        return 1.0
    if key in candidate_blob or candidate_blob in key:
        return _SIM_SUBSTRING
    return 0.0


def build_implicit_feedback_profile(
    visited_pois: Iterable[str] | None,
    liked_pois: Iterable[str] | None,
    skipped_pois: Iterable[str] | None,
    poi_category_lookup: Mapping[str, str],
    *,
    like_weight: float = 2.0,
) -> ImplicitFeedbackProfile | None:
    """
    Map interaction POI ids to categories and build normalized positive / skip distributions.

    Positive mass per category ``c`` is ``visits(c) + like_weight * likes(c)``.
    Skip mass uses raw skip counts per category.
    Missing ids in ``poi_category_lookup`` are ignored.
    """
    lookup = {_norm_id(k): _norm_cat_label(v) for k, v in poi_category_lookup.items() if _norm_id(k)}

    visit_c = Counter()
    like_c = Counter()
    skip_c = Counter()

    for pid in visited_pois or []:
        cat = lookup.get(_norm_id(pid))
        if cat:
            visit_c[cat] += 1
    for pid in liked_pois or []:
        cat = lookup.get(_norm_id(pid))
        if cat:
            like_c[cat] += 1
    for pid in skipped_pois or []:
        cat = lookup.get(_norm_id(pid))
        if cat:
            skip_c[cat] += 1

    if not visit_c and not like_c and not skip_c:
        return None

    raw_pos: dict[str, float] = {}
    for c, n in visit_c.items():
        raw_pos[c] = raw_pos.get(c, 0.0) + float(n)
    for c, n in like_c.items():
        raw_pos[c] = raw_pos.get(c, 0.0) + float(n) * float(like_weight)

    total_pos = sum(raw_pos.values())
    pos_dist = {c: raw_pos[c] / total_pos for c in raw_pos} if total_pos > 0 else {}

    total_skip = sum(skip_c.values())
    skip_dist = {c: skip_c[c] / total_skip for c in skip_c} if total_skip > 0 else {}

    return ImplicitFeedbackProfile(
        positive_distribution=pos_dist,
        skip_distribution=skip_dist,
        visit_counts=dict(visit_c),
        like_counts=dict(like_c),
        skip_counts=dict(skip_c),
    )


def _affinity_and_aversion(
    blob: str,
    pos_dist: dict[str, float],
    skip_dist: dict[str, float],
) -> tuple[float, float]:
    aff = 0.0
    for k, p in pos_dist.items():
        aff += float(p) * _category_similarity(blob, k)
    aver = 0.0
    for k, p in skip_dist.items():
        aver += float(p) * _category_similarity(blob, k)
    return aff, aver


def implicit_scores_blend(
    df: pd.DataFrame,
    profile: ImplicitFeedbackProfile,
    *,
    category_column: str = COL_CATEGORY,
    skip_lambda: float = 0.62,
) -> np.ndarray:
    """
    Per-row scores in ``[0, 1]`` from affinity minus skip penalty, min–max scaled over ``df``.
    """
    n = len(df)
    if category_column not in df.columns:
        return np.full(n, 0.5, dtype=np.float64)
    blobs = df[category_column].astype("string").fillna("").str.strip().str.lower()
    raw = np.empty(n, dtype=np.float64)
    pos_dist = profile.positive_distribution
    skip_dist = profile.skip_distribution
    for i, blob in enumerate(blobs):
        aff, aver = _affinity_and_aversion(str(blob), pos_dist, skip_dist)
        raw[i] = aff - float(skip_lambda) * aver
    return _min_max_unit(raw)


def implicit_scores_cosine(
    df: pd.DataFrame,
    profile: ImplicitFeedbackProfile,
    *,
    category_column: str = COL_CATEGORY,
    skip_lambda: float = 0.62,
) -> np.ndarray:
    """
    Cosine similarity between a normalized **net preference vector** (positive − penalty skips)
    and a per-row soft category vector (similarities to profile keys). Mapped to ``[0, 1]``.
    """
    n = len(df)
    if category_column not in df.columns:
        return np.full(n, 0.5, dtype=np.float64)

    keys = sorted(set(profile.positive_distribution) | set(profile.skip_distribution))
    if not keys:
        return np.full(n, 0.5, dtype=np.float64)

    net = np.array(
        [
            profile.positive_distribution.get(k, 0.0)
            - float(skip_lambda) * profile.skip_distribution.get(k, 0.0)
            for k in keys
        ],
        dtype=np.float64,
    )
    nu = np.linalg.norm(net)
    if nu < 1e-12:
        return np.full(n, 0.5, dtype=np.float64)
    net_u = net / nu

    blobs = df[category_column].astype("string").fillna("").str.strip().str.lower()
    out = np.empty(n, dtype=np.float64)
    for i, blob in enumerate(blobs):
        b = str(blob)
        r = np.array([_category_similarity(b, k) for k in keys], dtype=np.float64)
        nr = np.linalg.norm(r)
        if nr < 1e-12:
            out[i] = 0.5
            continue
        r_u = r / nr
        cos = float(np.dot(net_u, r_u))
        out[i] = (cos + 1.0) / 2.0
    return np.clip(out, 0.0, 1.0)


def _min_max_unit(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    if a.size == 0:
        return a
    mn, mx = float(np.nanmin(a)), float(np.nanmax(a))
    span = mx - mn
    if not np.isfinite(span) or span <= 1e-12:
        return np.full_like(a, 0.5)
    return np.clip((a - mn) / span, 0.0, 1.0)
