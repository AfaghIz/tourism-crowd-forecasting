"""
Human-readable explanations for ranked POI recommendations.

Core copy uses ranking features (distance, calm / crowd, rating, novelty). Optional context layers
— personalization (profile), visit time, list diversity, and route stop order — add short, varied
sentences without sounding like fixed templates (variants hashed per POI for stability).
"""

from __future__ import annotations

import zlib
from datetime import datetime
from typing import Any, Final, Mapping

import numpy as np
import pandas as pd

from recommendation.crowd_time_heuristic import visit_peak_strength
from recommendation.data_loader import COL_CATEGORY, COL_RATE
from recommendation.crowd_signal import resolve_crowd_signal_column
from recommendation.feature_engineering import (
    COL_CROWD_SCORE,
    COL_DISTANCE_SCORE,
    COL_NOVELTY_SCORE,
    COL_RATING_SCORE,
)
from recommendation.ranker import COL_DISTANCE_KM, COL_SCORE

COL_DISPLAY_NAME: Final[str] = "display_name_en"
COL_NAME: Final[str] = "name"
COL_POI_ID: Final[str] = "poi_id"

# Feature scores are on [0, 1]; "high" uses batch-relative lift with a floor.
_HIGH_FEATURE_FLOOR: Final[float] = 0.58
_HIGH_FEATURE_QUANTILE: Final[float] = 0.62

# Crowd signal thresholds on [0, 1] (busyness ↑); aligned with typical calm/tier splits.
_HIGH_CROWD: Final[float] = 2.0 / 3.0
_MED_CROWD: Final[float] = 1.0 / 3.0

_REASON_PHRASES: Final[dict[str, str]] = {
    "distance": "very close to you",
    "crowd": "less crowded than nearby places",
    "rating": "highly rated",
    "novelty": "a hidden gem",
}

_CATEGORY_VOICE: Final[dict[str, str]] = {
    "museum": "museum / cultural stop",
    "historic": "historic site",
    "religious": "religious landmark",
    "attraction": "attraction",
    "historic_architecture": "architecture highlight",
    "architecture": "architecture spot",
    "urban_environment": "urban landmark",
    "natural": "outdoor / nature point",
    "unknown": "sightseeing stop",
}

_MAX_CONTEXT_SNIPPETS: Final[int] = 3


def _matches_avoided_category(cat_blob: str, user_profile: Mapping[str, Any]) -> bool:
    for a in user_profile.get("avoided_categories") or []:
        lab = str(a).strip().lower()
        if lab and lab in cat_blob:
            return True
    return False


def _snippet_personalization(
    category_blob: str,
    user_profile: Mapping[str, Any],
    stable_key: str,
) -> str | None:
    if _matches_avoided_category(category_blob, user_profile):
        return None
    prefs = user_profile.get("preferred_categories") or []
    for raw in prefs:
        lab = str(raw).strip().lower()
        if lab and lab in category_blob:
            label = str(raw).strip()
            v = zlib.adler32((stable_key + "|pref").encode("utf-8")) % 4
            phrases = (
                f"It lines up with your interest in {label}.",
                f"This matches what you enjoy — especially {label}-style stops.",
                f"We weighted it because it fits your taste for {label}.",
                f"You said you like {label}; this one lines up with that.",
            )
            return phrases[v]
    return None


def _snippet_time_aware(
    timestamp: datetime,
    calm_score: float | None,
    median_calm: float | None,
    crowd_signal: float,
    median_crowd: float,
    stable_key: str,
) -> str | None:
    peak = float(visit_peak_strength(timestamp))
    v = zlib.adler32((stable_key + "|time").encode("utf-8")) % 4
    if peak >= 0.42 and calm_score is not None and median_calm is not None:
        if calm_score >= median_calm - 0.03:
            phrases = (
                "For this time of day—when streets usually swell—it still looks manageable.",
                "Even now, when crowds tend to spike, this stop should feel lighter than many peers.",
                "Right now is often hectic; this pick still reads calmer than headline attractions.",
                "At this hour you'd expect jam-packed corners—here the vibe stays comparatively relaxed.",
            )
            return phrases[v]
    if peak < 0.36:
        phrases = (
            "Quieter hours work in your favor—paths usually thin out around now.",
            "This slice of the day tends to feel less rushed than midday crunch.",
            "Timing helps: foot traffic often eases off during this window.",
            "You picked a mellower part of the clock; crowds usually soften.",
        )
        return phrases[v]
    if crowd_signal <= median_crowd - 0.05:
        phrases = (
            "Looks comparatively gentle on crowding for this time slot.",
            "Relative to what we'd expect right now, crowd pressure seems lighter here.",
            "Nice option when you want breathing room at this hour.",
            "Should feel a notch calmer than typical spots at this time of day.",
        )
        return phrases[v]
    return None


def _snippet_diversity_balance(
    category_blob: str,
    crowd_signal: float,
    median_crowd: float,
    row_feats: dict[str, float | None],
    batch_features: dict[str, pd.Series],
    cat_counts: dict[str, int],
    list_len: int,
    stable_key: str,
) -> str | None:
    if list_len < 3:
        return None
    v = zlib.adler32((stable_key + "|div").encode("utf-8")) % 4
    if crowd_signal < median_crowd - 0.06:
        phrases = (
            "It's a softer alternative to the most packed picks on this list.",
            "Compared with heavier-footfall spots nearby, this one eases the pressure.",
            "Think of it as breathing room next to blockbuster attractions.",
            "Nice counterweight if you want relief from the busiest pins above.",
        )
        return phrases[v]
    nov = row_feats.get("novelty")
    bnov = batch_features.get("novelty")
    if (
        nov is not None
        and bnov is not None
        and np.isfinite(float(nov))
        and _is_feature_high(float(nov), bnov)
    ):
        phrases = (
            "Adds variety beyond the usual blockbuster circuit.",
            "Brings a fresher angle than stacking the same marquee sights.",
            "Helps diversify the day instead of repeating one theme.",
            "You get something a little less stamped-by-the-tour-bus.",
        )
        return phrases[v]
    cnt = cat_counts.get(category_blob, 0)
    if cnt == 1 and len(cat_counts) >= 2 and list_len >= 4:
        phrases = (
            "Adds category variety so the day isn't one-note.",
            "Breaks up the list with a different kind of stop.",
            "Keeps the mix from feeling repetitive.",
            "Introduces a new thread alongside the other picks.",
        )
        return phrases[v]
    return None


def _snippet_route_stop(
    poi_id: str,
    itinerary_poi_order: Mapping[str, int] | None,
    stable_key: str,
) -> str | None:
    if not itinerary_poi_order or not poi_id:
        return None
    n = itinerary_poi_order.get(poi_id)
    if n is None:
        return None
    v = zlib.adler32((stable_key + "|route").encode("utf-8")) % 4
    phrases = (
        f"Slotted as stop {n} on your route.",
        f"Next logical pin on the walking plan—stop {n}.",
        f"You're hitting this as stop {n} in the ordered itinerary.",
        f"Number {n} along the path we drew for you.",
    )
    return phrases[v]


def _collect_context_snippets(
    *,
    category_blob: str,
    crowd_signal: float,
    median_crowd_signal: float,
    calm_score: float | None,
    median_calm_score: float | None,
    row_feats: dict[str, float | None],
    batch_features: dict[str, pd.Series],
    timestamp: datetime | None,
    user_profile: Mapping[str, Any] | None,
    poi_id: str,
    itinerary_poi_order: Mapping[str, int] | None,
    stable_key: str,
    cat_counts: dict[str, int],
    list_len: int,
) -> list[str]:
    layers: list[tuple[int, str]] = []
    if user_profile:
        p = _snippet_personalization(category_blob, user_profile, stable_key)
        if p:
            layers.append((0, p))
    if timestamp is not None:
        t = _snippet_time_aware(
            timestamp,
            calm_score,
            median_calm_score,
            crowd_signal,
            median_crowd_signal,
            stable_key,
        )
        if t:
            layers.append((1, t))
    d = _snippet_diversity_balance(
        category_blob,
        crowd_signal,
        median_crowd_signal,
        row_feats,
        batch_features,
        cat_counts,
        list_len,
        stable_key,
    )
    if d:
        layers.append((2, d))
    r = _snippet_route_stop(poi_id, itinerary_poi_order, stable_key)
    if r:
        layers.append((3, r))
    layers.sort(key=lambda x: x[0])
    out: list[str] = []
    for _, text in layers[:_MAX_CONTEXT_SNIPPETS]:
        out.append(text)
    return out


def _append_context_snippets(base: str, snippets: list[str], stable_key: str) -> str:
    if not snippets:
        return base
    extra = " ".join(snippets)
    return _tidy_whitespace(f"{base} {extra}")


def enrich_explanations_alternative_clause(items: list[dict[str, Any]]) -> None:
    """Append a short line when :mod:`alternatives` attached a mellower backup."""
    for it in items:
        alt = it.get("alternative_suggestion")
        if not isinstance(alt, dict):
            continue
        pid = str(it.get("poi_id", "") or "")
        v = zlib.adler32((pid + "|alt").encode("utf-8")) % 3
        phrases = (
            "If it feels too tight, we lined up a mellower same-category backup nearby.",
            "Prefer breathing room? There's a gentler swap in the same vein flagged below.",
            "Crowded when you arrive—peek at the alternate we tucked in for you.",
        )
        base = it.get("explanation") or ""
        it["explanation"] = _tidy_whitespace(f"{base} {phrases[v]}")
        it["explanation_text"] = it["explanation"]


def generate_explanations(
    df: pd.DataFrame,
    *,
    user_profile: Mapping[str, Any] | None = None,
    timestamp: datetime | None = None,
    itinerary_poi_order: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    """
    Build one structured explanation dict per row of a ranked candidate frame.

    Expects columns added upstream — at minimum ``distance_km``, a crowd signal column
    (see :func:`~recommendation.crowd_signal.resolve_crowd_signal_column`), and ``score``
    from ranking output. Uses ``category_clean``, ``name`` / ``display_name_en``, and ``rate``
    when present.

    If ``distance_score``, ``crowd_score``, ``rating_score``, and/or ``novelty_score`` exist
    (from :mod:`feature_engineering`), the ``explanation`` field combines the strongest signals
    into one sentence (e.g. proximity, relative calm, ratings, novelty).

    Optional context (no API change for callers who omit keywords):

    - ``user_profile`` — lines like interest in preferred categories.
    - ``timestamp`` — time-of-day crowding context.
    - ``itinerary_poi_order`` — ``poi_id`` → stop index when a route was built.

    Parameters
    ----------
    df
        Typically the output of ``rank_candidates`` (possibly sliced to top-N).

    Returns
    -------
    list[dict[str, Any]]
        Each dict includes ``name``, ``score``, ``distance_km``, ``explanation``,
        ``explanation_text`` (same string, legacy key), ``category``, and ``crowd_level_label``
        (``\"low\"``, ``\"medium\"``, or ``\"high\"`` on raw busyness).
    """
    if df.empty:
        return []

    required = (COL_DISTANCE_KM, COL_SCORE)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"generate_explanations requires columns {missing} on the DataFrame.")

    crowd_col = resolve_crowd_signal_column(df)
    crowd_series = pd.to_numeric(df[crowd_col], errors="coerce").fillna(0.5)
    median_crowd = float(crowd_series.median())
    median_calm: float | None = None
    if COL_CROWD_SCORE in df.columns:
        median_calm = float(
            pd.to_numeric(df[COL_CROWD_SCORE], errors="coerce").median()
        )
    cat_counts: dict[str, int] = {}
    if COL_CATEGORY in df.columns:
        cat_counts = (
            df[COL_CATEGORY]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.lower()
            .value_counts()
            .to_dict()
        )
    score_series = pd.to_numeric(df[COL_SCORE], errors="coerce")
    q_score_hi = float(score_series.quantile(0.75)) if len(score_series) > 1 else float(score_series.iloc[0])

    feature_cols = {
        "distance": COL_DISTANCE_SCORE,
        "crowd": COL_CROWD_SCORE,
        "rating": COL_RATING_SCORE,
        "novelty": COL_NOVELTY_SCORE,
    }
    batch_features: dict[str, pd.Series] = {}
    for key, col in feature_cols.items():
        if col in df.columns:
            batch_features[key] = pd.to_numeric(df[col], errors="coerce")

    use_feature_voice = len(batch_features) > 0

    records = df.to_dict("records")
    out: list[dict[str, Any]] = []

    for rec in records:
        name = _pick_name(rec)
        km = float(rec[COL_DISTANCE_KM])
        score = float(rec[COL_SCORE])
        cat_raw = str(rec.get(COL_CATEGORY, "unknown") or "unknown").strip().lower()
        crowd_val = float(pd.to_numeric(rec.get(crowd_col), errors="coerce") or 0.5)

        label = crowd_level_label(crowd_val)
        stable_key = str(rec.get(COL_POI_ID, name))

        if use_feature_voice:
            row_feats = {
                k: _optional_float(rec.get(col))
                for k, col in feature_cols.items()
                if col in df.columns
            }
            expl = _compose_feature_explanation(
                name=name,
                row_feats=row_feats,
                batch_features=batch_features,
                stable_key=stable_key,
                distance_km=km,
                category_key=cat_raw,
                crowd_signal=crowd_val,
                median_crowd=median_crowd,
                score=score,
                score_quantile_high=q_score_hi,
                rate=_optional_float(rec.get(COL_RATE)),
            )
        else:
            row_feats = {}
            expl = _compose_explanation(
                name=name,
                distance_km=km,
                score=score,
                crowd_signal=crowd_val,
                median_crowd=median_crowd,
                category_key=cat_raw,
                rate=_optional_float(rec.get(COL_RATE)),
                score_quantile_high=q_score_hi,
                stable_key=stable_key,
            )

        calm_now = _optional_float(rec.get(COL_CROWD_SCORE)) if COL_CROWD_SCORE in df.columns else None
        snippets = _collect_context_snippets(
            category_blob=cat_raw,
            crowd_signal=crowd_val,
            median_crowd_signal=median_crowd,
            calm_score=calm_now,
            median_calm_score=median_calm,
            row_feats=row_feats if use_feature_voice else {},
            batch_features=batch_features,
            timestamp=timestamp,
            user_profile=user_profile,
            poi_id=str(rec.get(COL_POI_ID, "") or "").strip(),
            itinerary_poi_order=itinerary_poi_order,
            stable_key=stable_key,
            cat_counts=cat_counts,
            list_len=len(df),
        )
        if snippets:
            expl = _append_context_snippets(expl, snippets, stable_key)

        item = {
            "name": name,
            "score": score,
            "distance_km": round(km, 4),
            "explanation": expl,
            "explanation_text": expl,
            "category": cat_raw,
            "crowd_level_label": label,
        }
        out.append(item)

    return out


def crowd_level_label(crowd_signal: float) -> str:
    """Map a 0–1 busyness signal to ``low`` / ``medium`` / ``high``."""
    x = float(crowd_signal)
    if x >= _HIGH_CROWD:
        return "high"
    if x >= _MED_CROWD:
        return "medium"
    return "low"


def _is_feature_high(val: float, batch: pd.Series) -> bool:
    """True if ``val`` clears a batch-relative bar (and a floor) on 0–1 feature scores."""
    s = pd.to_numeric(batch, errors="coerce").dropna()
    if s.empty or len(s) < 2:
        return val >= _HIGH_FEATURE_FLOOR + 0.12
    lo = max(_HIGH_FEATURE_FLOOR, float(s.quantile(_HIGH_FEATURE_QUANTILE)))
    return float(val) >= lo


def _active_reasons(
    row_feats: dict[str, float | None],
    batch_features: dict[str, pd.Series],
) -> list[tuple[str, str]]:
    """Ordered (key, phrase) pairs for batch-high ranking features."""
    order = ("distance", "crowd", "rating", "novelty")
    out: list[tuple[str, str]] = []
    for key in order:
        batch = batch_features.get(key)
        if batch is None:
            continue
        v = row_feats.get(key)
        if v is None or not np.isfinite(v):
            continue
        if not _is_feature_high(float(v), batch):
            continue
        out.append((key, _REASON_PHRASES[key]))
    return out


def _oxford_join_phrases(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _compose_feature_explanation(
    *,
    name: str,
    row_feats: dict[str, float | None],
    batch_features: dict[str, pd.Series],
    stable_key: str,
    distance_km: float,
    category_key: str,
    crowd_signal: float,
    median_crowd: float,
    score: float,
    score_quantile_high: float,
    rate: float | None,
) -> str:
    """One sentence from high distance/crowd/rating/novelty features; fallback if none qualify."""
    reasons = _active_reasons(row_feats, batch_features)
    variant = zlib.adler32(stable_key.encode("utf-8")) % 3 if stable_key else 0

    if reasons:
        phrases = [p for _, p in reasons]
        joined = _oxford_join_phrases(phrases)
        if variant == 0:
            return _tidy_whitespace(f"{name} is a strong pick because it is {joined}.")
        if variant == 1:
            return _tidy_whitespace(f"We short-listed {name} for being {joined}.")
        return _tidy_whitespace(f"{name} ranks well here: it is {joined}.")

    dist_phrase = _format_distance_phrase(distance_km)
    cat_desc = _category_descriptor(category_key)
    delta = crowd_signal - median_crowd
    if abs(delta) < 0.04:
        rel = "typical crowd level compared with the other options here"
    elif delta < 0:
        rel = "lighter crowd pressure than the batch median"
    else:
        rel = "heavier crowd pressure than the batch median"

    score_note = ""
    if score >= score_quantile_high and score_quantile_high > 0:
        score_note = " It lines up with the top composite scores in this list."
    elif rate is not None and rate >= 5.5:
        score_note = f" Listing reviews sit around {rate:.1f}/7."

    return _tidy_whitespace(
        f"{name} is a {cat_desc} {dist_phrase}, with {rel}.{score_note}"
    )


def _pick_name(rec: dict[str, Any]) -> str:
    for key in (COL_DISPLAY_NAME, COL_NAME):
        v = rec.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    pid = rec.get(COL_POI_ID)
    if pid is not None and str(pid).strip():
        return str(pid).strip()
    return "This place"


def _optional_float(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _format_distance_phrase(km: float) -> str:
    if km < 1.0:
        m = max(1, int(round(km * 1000)))
        return f"{m} meters from your pin"
    return f"{km:.1f} km from your pin"


def _category_descriptor(category_key: str) -> str:
    return _CATEGORY_VOICE.get(category_key, _CATEGORY_VOICE["unknown"])


def _compose_explanation(
    *,
    name: str,
    distance_km: float,
    score: float,
    crowd_signal: float,
    median_crowd: float,
    category_key: str,
    rate: float | None,
    score_quantile_high: float,
    stable_key: str,
) -> str:
    """Assemble 1–2 sentences from measured values; variant chosen deterministically."""
    dist_phrase = _format_distance_phrase(distance_km)
    cat_desc = _category_descriptor(category_key)

    delta = crowd_signal - median_crowd
    variant = zlib.adler32(stable_key.encode("utf-8")) % 3 if stable_key else 0

    # Relative crowd vs peers in this recommendation list (same dataframe).
    if abs(delta) < 0.04:
        crowd_vs_list = "close to the median crowd signal for this batch"
    elif delta < 0:
        crowd_vs_list = "below the median crowd signal for this batch"
    else:
        crowd_vs_list = "above the median crowd signal for this batch"

    # Absolute tier wording
    if crowd_signal >= _HIGH_CROWD:
        tier_msg = "expects busy conditions"
    elif crowd_signal >= _MED_CROWD:
        tier_msg = "usually moderate foot traffic"
    else:
        tier_msg = "often quieter relative to major landmarks"

    # Rating hook
    rating_clause = ""
    if rate is not None:
        if rate >= 6.5:
            rating_clause = f"It carries a strong listing rating ({rate:.0f}/7)."
        elif rate >= 5.0:
            rating_clause = f"It shows solid ratings ({rate:.1f}/7)."
        elif rate >= 3.5:
            rating_clause = f"Ratings sit around {rate:.1f}/7 — fine for a quick stop."
        else:
            rating_clause = "Ratings are thinner on this listing — worth checking recent reviews."

    # Score prominence within batch
    if score >= score_quantile_high and score_quantile_high > 0:
        rank_hint = "It sits near the top of this batch by the composite score."
    elif score >= score_quantile_high * 0.92:
        rank_hint = "It stays competitive with the best matches here."
    else:
        rank_hint = ""

    # Sentence 1: distance + category + crowd comparison (examples asked for this blend)
    openers = (
        f"{name} is {dist_phrase}, framed as a {cat_desc}. Crowd signal is {crowd_vs_list}.",
        f"It ranks strongly on proximity ({dist_phrase}) as a {cat_desc}; relative to this batch the crowd signal is {crowd_vs_list}.",
        f"A {cat_desc} sitting {dist_phrase}, with crowd pressure {crowd_vs_list} compared with the other picks here.",
    )
    s1 = openers[variant]

    # Sentence 2: tier + optional rating + optional rank
    parts2 = [
        f"Our crowd signal ({crowd_signal:.2f}) suggests it {tier_msg}.",
    ]
    if rating_clause:
        parts2.append(rating_clause)
    if rank_hint:
        parts2.append(rank_hint)

    s2 = " ".join(p for p in parts2 if p).strip()

    text = f"{s1} {s2}".strip()
    return _tidy_whitespace(text)


def _tidy_whitespace(text: str) -> str:
    return " ".join(text.split())
