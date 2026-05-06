from __future__ import annotations

import math
from typing import Any

from weekly_model import IstanbulWeeklyModelRepository, WeeklyRow


class ForecastService:
    def __init__(self, weekly_model: IstanbulWeeklyModelRepository) -> None:
        self._weekly = weekly_model

    def forecast(self, req: dict[str, Any]) -> dict[str, Any]:
        if self._weekly.is_loaded():
            return self._city_wide_from_notebook(req)
        return self._demo_fallback(req)

    def _city_wide_from_notebook(self, req: dict[str, Any]) -> dict[str, Any]:
        rows = self._weekly.all_rows()
        latest = rows[-1]
        horizon = req.get("horizonWeeks")
        if horizon is None:
            horizon = 4
        horizon = max(1, min(52, int(horizon)))

        score = int(round(min(1.0, max(0.0, latest.crowd_index)) * 100.0))
        score = max(1, min(99, score))

        trend = _build_trend(rows, horizon)
        basis = latest.week_start.isoformat()
        interpretation = (
            "City-wide weekly pressure for Istanbul (trained pipeline: trends + weather + time). "
            "Same index for every place on the map — not measured crowds at this venue."
        )
        latlng = req["latlng"]
        return {
            "label": req["label"],
            "kind": req["kind"],
            "latlng": {"lat": latlng["lat"], "lng": latlng["lng"]},
            "score": score,
            "level": latest.crowd_level,
            "trend": trend,
            "forecastScope": "city_wide",
            "basisWeekStart": basis,
            "interpretation": interpretation,
        }

    def _demo_fallback(self, req: dict[str, Any]) -> dict[str, Any]:
        kind = req["kind"]
        latlng = req["latlng"]
        score = _estimate_score(kind, latlng["lat"], latlng["lng"])
        level = "High" if score >= 72 else "Medium" if score >= 45 else "Low"
        trend = (
            "Demo scoring only — bundle weekly CSV for real city-wide index."
        )
        return {
            "label": req["label"],
            "kind": kind,
            "latlng": {"lat": latlng["lat"], "lng": latlng["lng"]},
            "score": score,
            "level": level,
            "trend": trend,
            "forecastScope": "demo",
            "basisWeekStart": "",
            "interpretation": (
                "Demo mode: weekly model file not loaded. Pin placement still affects this placeholder score."
            ),
        }


def _build_trend(rows: list[WeeklyRow], horizon_weeks: int) -> str:
    if len(rows) < 2:
        return "Insufficient history for a trend line."
    end = len(rows) - 1
    start = max(0, end - horizon_weeks)
    total = 0.0
    n = 0
    for i in range(start, end):
        total += rows[i].crowd_index
        n += 1
    if n == 0:
        return "Baseline for the selected horizon."
    prior_mean = total / n
    latest = rows[end].crowd_index
    delta = latest - prior_mean
    if delta > 0.03:
        return f"Above the prior ~{n}-week average (city-wide index rising)."
    if delta < -0.03:
        return f"Below the prior ~{n}-week average (city-wide index softer)."
    return f"Near the prior ~{n}-week average for Istanbul."


def _estimate_score(kind: str, lat: float, lng: float) -> int:
    kind_boost = {"hotel": 10, "poi": 7, "location": 4}.get(kind, 2)
    lat_factor = abs(lat * 3.1)
    lng_factor = abs(lng * 1.7)
    raw = 34 + kind_boost + ((lat_factor + lng_factor) % 44)
    rounded = int(round(raw))
    return max(1, min(99, rounded))
