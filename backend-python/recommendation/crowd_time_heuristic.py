"""
Time-aware modulation for crowd / busyness when no ML model is registered.

Combines:

- smooth **diurnal** curve (intraday peak ~ lunch),
- **weekend** uplift,
- optional **seasonal** placeholder (calendar month),
- discrete **time-slot** factors (morning / afternoon / evening / night).

Ranking applies an extra **visit peak strength** (same timestamp for all candidates) to
penalize intrinsically busy POIs more strongly during predicted peak visit windows — see
:func:`visit_peak_strength`.

Replaceable; registered ML providers bypass this module (see :mod:`crowd_scores`).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Final

# --- Diurnal Gaussian (unchanged public surface for callers) ---
_PEAK_HOUR: float = 13.0
_SIGMA_HOURS: float = 3.75
_MULT_MIN: float = 0.74
_MULT_MAX: float = 1.22

# --- Weekend ---
_WEEKEND_MULT: Final[float] = 1.11

# --- Seasonal placeholder (±~3% around 1.0; peak mid-year) ---
_SEASONAL_AMPLITUDE: Final[float] = 0.032

# --- Time slots (local wall clock): multipliers vs neutral 1.0 ---
_SLOT_MULTIPLIERS: Final[dict[str, float]] = {
    "morning": 0.91,
    "afternoon": 1.12,
    "evening": 1.05,
    "night": 0.80,
}

# --- visit_peak_strength blend (output [0, 1]) ---
_PEAK_WEIGHT_DIURNAL: Final[float] = 0.28
_PEAK_WEIGHT_WEEKEND: Final[float] = 0.24
_PEAK_WEIGHT_SLOT: Final[float] = 0.38
_PEAK_WEIGHT_SEASONAL: Final[float] = 0.10

_SLOT_PEAK_SCORES: Final[dict[str, float]] = {
    "morning": 0.34,
    "afternoon": 1.0,
    "evening": 0.58,
    "night": 0.22,
}


def diurnal_crowd_multiplier(timestamp: datetime | None) -> float:
    """
    Return a factor in ``[MULT_MIN, MULT_MAX]`` from local clock time (Gaussian bump ~13:00).

    If ``timestamp`` is ``None``, returns ``1.0``.
    """
    if timestamp is None:
        return 1.0
    h = (
        float(timestamp.hour)
        + float(timestamp.minute) / 60.0
        + float(timestamp.second) / 3600.0
    )
    z = (h - _PEAK_HOUR) / _SIGMA_HOURS
    bump = math.exp(-0.5 * z * z)
    return _MULT_MIN + (_MULT_MAX - _MULT_MIN) * bump


def infer_time_slot(timestamp: datetime | None) -> str | None:
    """
    Bucket local time into ``morning`` | ``afternoon`` | ``evening`` | ``night``.

    Boundaries (hour): [5,11) morning, [11,17) afternoon, [17,22) evening, else night.
    """
    if timestamp is None:
        return None
    h = float(timestamp.hour) + float(timestamp.minute) / 60.0
    if 5.0 <= h < 11.0:
        return "morning"
    if 11.0 <= h < 17.0:
        return "afternoon"
    if 17.0 <= h < 22.0:
        return "evening"
    return "night"


def weekend_crowd_multiplier(timestamp: datetime | None) -> float:
    """Saturday/Sunday → busier (weekends more crowded)."""
    if timestamp is None:
        return 1.0
    return _WEEKEND_MULT if timestamp.weekday() >= 5 else 1.0


def seasonal_crowd_multiplier(timestamp: datetime | None) -> float:
    """
    Placeholder seasonal curve: modest uplift mid-year, dip in opposite season.

    Uses calendar month only (no hemisphere flag — refine when real seasonality exists).
    """
    if timestamp is None:
        return 1.0
    # Peak near July (month 7); cosine max when month == 7
    return 1.0 + _SEASONAL_AMPLITUDE * math.cos(
        2.0 * math.pi * (float(timestamp.month) - 7.0) / 12.0
    )


def time_slot_crowd_multiplier(timestamp: datetime | None) -> float:
    """Discrete slot weights (morning / afternoon / evening / night)."""
    if timestamp is None:
        return 1.0
    slot = infer_time_slot(timestamp)
    if slot is None:
        return 1.0
    return float(_SLOT_MULTIPLIERS.get(slot, 1.0))


def time_aware_crowd_multiplier(timestamp: datetime | None) -> float:
    """
    Combined fallback multiplier applied to baseline busyness before clipping to ``[0, 1]``.

    Product of diurnal, weekend, seasonal placeholder, and time-slot factors.
    """
    if timestamp is None:
        return 1.0
    return (
        diurnal_crowd_multiplier(timestamp)
        * weekend_crowd_multiplier(timestamp)
        * seasonal_crowd_multiplier(timestamp)
        * time_slot_crowd_multiplier(timestamp)
    )


def visit_peak_strength(timestamp: datetime | None) -> float:
    """
    Scalar in ``[0, 1]`` — how "peak" the visit instant is for ranking penalties.

    High on weekend afternoons in mid-day seasonal peaks; used to scale down ``crowd_score``
    (calm) more for POIs that are already busy when the user visits at a crowded time.
    """
    if timestamp is None:
        return 0.0
    d = diurnal_crowd_multiplier(timestamp)
    d_norm = (d - _MULT_MIN) / (_MULT_MAX - _MULT_MIN + 1e-12)
    d_norm = max(0.0, min(1.0, d_norm))

    wk = 1.0 if timestamp.weekday() >= 5 else 0.22

    slot = infer_time_slot(timestamp) or "afternoon"
    slot_peak = float(_SLOT_PEAK_SCORES.get(slot, 0.5))

    sea = seasonal_crowd_multiplier(timestamp)
    sea_norm = (sea - (1.0 - _SEASONAL_AMPLITUDE)) / (2.0 * _SEASONAL_AMPLITUDE + 1e-12)
    sea_norm = max(0.0, min(1.0, sea_norm))

    v = (
        _PEAK_WEIGHT_DIURNAL * d_norm
        + _PEAK_WEIGHT_WEEKEND * wk
        + _PEAK_WEIGHT_SLOT * slot_peak
        + _PEAK_WEIGHT_SEASONAL * sea_norm
    )
    return max(0.0, min(1.0, v))
