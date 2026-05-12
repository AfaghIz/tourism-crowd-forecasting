from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from catalog import list_hotels, list_pois, search_everything, search_hotels, search_pois
from forecast_service import ForecastService
from recommendation.pipeline import recommend as pipeline_recommend
from weekly_model import IstanbulWeeklyModelRepository

DEFAULT_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:4173,"
    "http://127.0.0.1:4173,"
    "https://afaghiz.github.io"
)

ALLOWED_KINDS = frozenset({"hotel", "poi", "location", "map"})


def _cors_origins() -> list[str]:
    raw = os.environ.get("APP_CORS_ALLOWED_ORIGINS", DEFAULT_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def _validate_forecast_body(body: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(body, dict):
        return None, ["Request body must be a JSON object"]

    kind = body.get("kind")
    if kind not in ALLOWED_KINDS:
        errors.append("kind must be one of: hotel, poi, location, map")

    label = body.get("label")
    if label is None or not str(label).strip():
        errors.append("label is required")

    latlng = body.get("latlng")
    if not isinstance(latlng, dict):
        errors.append("latlng is required")
    else:
        try:
            lat = float(latlng["lat"])
            lng = float(latlng["lng"])
        except (KeyError, TypeError, ValueError):
            errors.append("latlng must include numeric lat and lng")
        else:
            body = {**body, "latlng": {"lat": lat, "lng": lng}}

    hw = body.get("horizonWeeks")
    if hw is not None:
        try:
            hi = int(hw)
            if hi < 1 or hi > 52:
                errors.append("horizonWeeks must be between 1 and 52")
            else:
                body = {**body, "horizonWeeks": hi}
        except (TypeError, ValueError):
            errors.append("horizonWeeks must be an integer")

    basis_week_start = body.get("basisWeekStart")
    if basis_week_start is not None:
        if not isinstance(basis_week_start, str) or not basis_week_start.strip():
            errors.append("basisWeekStart must be a non-empty ISO date string when provided")
        else:
            body = {**body, "basisWeekStart": basis_week_start.strip()}

    entity_id = body.get("entityId")
    if entity_id is not None:
        if not isinstance(entity_id, str) or not entity_id.strip():
            errors.append("entityId must be a non-empty string when provided")
        else:
            body = {**body, "entityId": entity_id.strip()}

    if errors:
        return None, errors

    assert isinstance(body, dict)
    out = dict(body)
    out["label"] = str(out["label"]).strip()
    return out, []


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(
        app,
        resources={r"/api/*": {"origins": _cors_origins()}},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers="*",
    )

    weekly_repo = IstanbulWeeklyModelRepository()
    forecast_svc = ForecastService(weekly_repo)

    @app.get("/api/health")
    def health() -> Response:
        return Response("ok", mimetype="text/plain")

    @app.get("/api/hotels")
    def hotels() -> Any:
        return jsonify(list_hotels())

    @app.get("/api/hotels/search")
    def hotels_search() -> Any:
        q = request.args.get("q", "")
        limit = request.args.get("limit", 7, type=int) or 7
        return jsonify(search_hotels(q, limit))

    @app.get("/api/pois/search")
    def pois_search() -> Any:
        q = request.args.get("q", "")
        limit = request.args.get("limit", 7, type=int) or 7
        return jsonify(search_pois(q, limit))

    @app.get("/api/pois")
    def pois() -> Any:
        limit = request.args.get("limit", 60, type=int) or 60
        return jsonify(list_pois(limit))

    @app.get("/api/search")
    def search() -> Any:
        q = request.args.get("q", "")
        limit = request.args.get("limit", 10, type=int) or 10
        return jsonify(search_everything(q, limit))

    @app.post("/api/forecast")
    def forecast() -> Any:
        body = request.get_json(silent=True)
        req, errs = _validate_forecast_body(body)
        if req is None:
            return jsonify({"errors": errs}), 400
        return jsonify(forecast_svc.forecast(req))

    @app.get("/api/forecast-periods")
    def forecast_periods() -> Any:
        return jsonify(forecast_svc.period_options())

    @app.post("/api/recommendations")
    def recommendations() -> Any:
        """
        Pandas recommendation pipeline → ``{ "recommendations": [...], "itinerary": ... }``.

        Body (JSON)::

            origin: { lat, lng }  (or latlng)
            timestamp: optional ISO-8601 string
            userProfile / user_profile: optional mapping
            radiusKm / radius_km: default 5
            topK / top_k: default 10
            includeItinerary / include_itinerary: default false
            allowedCategories / allowed_categories: optional string array
            anchorPoiId / anchor_poi_id: optional POI id for crowd-aware alternative mode
            anchorRadiusKm / anchor_radius_km: optional radius around anchor, default 3
        """
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"errors": ["Request body must be a JSON object"]}), 400
        origin = body.get("origin") or body.get("latlng")
        if not isinstance(origin, dict):
            return jsonify({"errors": ["origin (or latlng) with lat and lng is required"]}), 400
        try:
            olat = float(origin["lat"])
            olng = float(origin["lng"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"errors": ["origin.lat and origin.lng must be numeric"]}), 400

        ts: datetime | None = None
        raw_ts = body.get("timestamp")
        if raw_ts is not None:
            if isinstance(raw_ts, str):
                s = raw_ts.strip().replace("Z", "+00:00")
                try:
                    ts = datetime.fromisoformat(s)
                except ValueError:
                    return jsonify({"errors": ["timestamp must be ISO-8601 (e.g. 2026-05-02T14:30:00)"]}), 400
            else:
                return jsonify({"errors": ["timestamp must be a string"]}), 400

        user_profile = body.get("userProfile")
        if user_profile is None:
            user_profile = body.get("user_profile")

        radius = float(body.get("radiusKm", body.get("radius_km", 5.0)))
        top_k = int(body.get("topK", body.get("top_k", 10)))
        inc_it = bool(body.get("includeItinerary", body.get("include_itinerary", False)))
        anchor_poi_id = body.get("anchorPoiId", body.get("anchor_poi_id"))
        entity_id = body.get("entityId", body.get("entity_id"))
        anchor_radius_km = float(body.get("anchorRadiusKm", body.get("anchor_radius_km", 3.0)))

        if not isinstance(user_profile, dict) and user_profile is not None:
            return jsonify({"errors": ["userProfile must be an object when provided"]}), 400
        if anchor_poi_id is not None and not str(anchor_poi_id).strip():
            return jsonify({"errors": ["anchorPoiId must be a non-empty string when provided"]}), 400
        if anchor_poi_id is None and entity_id is not None:
            if not isinstance(entity_id, str) or not entity_id.strip():
                return jsonify({"errors": ["entityId must be a non-empty string when provided"]}), 400
            anchor_poi_id = entity_id.strip()

        allowed = body.get("allowedCategories") or body.get("allowed_categories")
        if allowed is not None and not isinstance(allowed, list):
            return jsonify({"errors": ["allowedCategories must be an array of strings when provided"]}), 400
        allowed_list = [str(x).strip() for x in allowed if str(x).strip()] if allowed else None

        try:
            result = pipeline_recommend(
                olat,
                olng,
                ts,
                user_profile,
                radius_km=radius,
                top_k=top_k,
                include_itinerary=inc_it,
                allowed_categories=allowed_list,
                anchor_poi_id=str(anchor_poi_id).strip() if anchor_poi_id is not None else None,
                anchor_radius_km=anchor_radius_km,
            )
            return jsonify(result)
        except ValueError as e:
            return jsonify({"errors": [str(e)]}), 400

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
