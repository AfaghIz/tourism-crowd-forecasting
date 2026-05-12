from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from recommendation.crowd_scores import get_registered_provider
from recommendation.explanation_engine import crowd_level_label
from weekly_model import IstanbulWeeklyModelRepository, WeeklyRow


class ForecastService:
    def __init__(self, weekly_model: IstanbulWeeklyModelRepository) -> None:
        self._weekly = weekly_model

    def period_options(self) -> list[dict[str, str]]:
        if not self._weekly.is_loaded():
            return []

        rows = self._weekly.all_rows()
        latest = rows[-1]
        options: list[dict[str, str]] = [
            {
                "id": latest.week_start.isoformat(),
                "label": f"Latest modeled week ({latest.week_start.isoformat()})",
                "level": latest.crowd_level,
            }
        ]

        for level in ("Low", "Medium", "High"):
            row = _latest_row_for_level(rows, level)
            if row is None:
                continue
            option = {
                "id": row.week_start.isoformat(),
                "label": f"Recent {level.lower()} week ({row.week_start.isoformat()})",
                "level": row.crowd_level,
            }
            if option["id"] not in {item["id"] for item in options}:
                options.append(option)

        return options

    def forecast(self, req: dict[str, Any]) -> dict[str, Any]:
        if self._weekly.is_loaded():
            return self._city_wide_from_notebook(req)
        return self._demo_fallback(req)

    def _city_wide_from_notebook(self, req: dict[str, Any]) -> dict[str, Any]:
        rows = self._weekly.all_rows()
        selected_index = _resolve_row_index(rows, req.get("basisWeekStart"))
        selected = rows[selected_index]
        horizon = req.get("horizonWeeks")
        if horizon is None:
            horizon = 4
        horizon = max(1, min(52, int(horizon)))

        city_score_01 = min(1.0, max(0.0, selected.crowd_index))
        city_score = _to_pct_score(city_score_01)
        city_level = selected.crowd_level

        poi_id = str(req.get("entityId") or "").strip()
        poi_score_01 = _resolve_poi_score(poi_id, selected.week_start.isoformat())
        if poi_score_01 is not None:
            score = _to_pct_score(poi_score_01)
            level = crowd_level_label(poi_score_01).title()
            score_scope = "poi_modeled"
            score_label = "POI crowd estimate"
        else:
            score = city_score
            level = city_level
            score_scope = "city_wide"
            score_label = "City-wide crowd estimate"

        trend = _build_trend(rows, horizon, selected_index)
        basis = selected.week_start.isoformat()
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
            "level": level,
            "trend": trend,
            "forecastScope": "city_wide",
            "scoreScope": score_scope,
            "scoreLabel": score_label,
            "cityScore": city_score,
            "cityLevel": city_level,
            "basisWeekStart": basis,
            "basisLabel": f"Modeled week of {basis}",
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


def _build_trend(rows: list[WeeklyRow], horizon_weeks: int, end: int) -> str:
    if len(rows) < 2:
        return "Insufficient history for a trend line."
    start = max(0, end - horizon_weeks)
    total = 0.0
    n = 0
    for i in range(start, end):
        total += rows[i].crowd_index
        n += 1
    if n == 0:
        return "Baseline for the selected horizon."
    prior_mean = total / n
    current = rows[end].crowd_index
    delta = current - prior_mean
    if delta > 0.03:
        return f"Above the prior ~{n}-week average (city-wide index rising)."
    if delta < -0.03:
        return f"Below the prior ~{n}-week average (city-wide index softer)."
    return f"Near the prior ~{n}-week average for Istanbul."


def _resolve_row_index(rows: list[WeeklyRow], requested_basis: Any) -> int:
    if isinstance(requested_basis, str):
        wanted = requested_basis.strip()
        for idx, row in enumerate(rows):
            if row.week_start.isoformat() == wanted:
                return idx
    return len(rows) - 1


def _latest_row_for_level(rows: list[WeeklyRow], level: str) -> WeeklyRow | None:
    for row in reversed(rows):
        if row.crowd_level == level:
            return row
    return None


def _estimate_score(kind: str, lat: float, lng: float) -> int:
    kind_boost = {"hotel": 10, "poi": 7, "location": 4}.get(kind, 2)
    lat_factor = abs(lat * 3.1)
    lng_factor = abs(lng * 1.7)
    raw = 34 + kind_boost + ((lat_factor + lng_factor) % 44)
    rounded = int(round(raw))
    return max(1, min(99, rounded))


def _to_pct_score(value_01: float) -> int:
    score = int(round(min(1.0, max(0.0, value_01)) * 100.0))
    return max(1, min(99, score))


def _resolve_poi_score(poi_id: str, basis_week_start: str) -> float | None:
    if not poi_id:
        return None
    provider = get_registered_provider()
    if provider is None:
        return None
    try:
        timestamp = datetime.fromisoformat(basis_week_start)
        return float(provider.get_crowd_score(poi_id, timestamp))
    except Exception:
        return None
