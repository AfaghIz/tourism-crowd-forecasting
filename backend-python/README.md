# Python backend (Flask)

HTTP API for the Vite frontend.

## Setup

```bash
cd backend-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Default port **8080** (`VITE_API_BASE_URL` in the frontend).

```bash
cd backend-python
.venv\Scripts\activate
python app.py
```

Or:

```bash
set PORT=8080
flask --app app:app run --host 0.0.0.0 --port 8080
```

## Configuration

- **PORT** — listen port (default `8080`).
- **APP_CORS_ALLOWED_ORIGINS** — comma-separated allowed origins for `/api/*` (defaults match local Vite preview ports).
- **FLASK_DEBUG** — set to `1` for debug mode when running `python app.py`.
- **RECOMMENDATION_POI_CSV** — optional override path to the OTM POI CSV used by the pandas recommendation pipeline.

## Endpoints

- `GET /api/health` — plain text `ok`
- `GET /api/hotels`
- `GET /api/hotels/search?q=...&limit=7`
- `GET /api/pois/search?q=...&limit=7`
- `GET /api/search?q=...&limit=10`
- `POST /api/forecast`
- **`POST /api/recommendations`** — full pandas pipeline (`recommendation.pipeline.recommend`): returns `{ "recommendations": [...], "itinerary": null | [...] }`

Example recommendation body (pipeline):

```json
{
  "origin": { "lat": 41.0086, "lng": 28.9802 },
  "timestamp": "2026-05-02T14:30:00",
  "radiusKm": 5,
  "topK": 10,
  "includeItinerary": false,
  "allowedCategories": ["museum"],
  "userProfile": {
    "preferred_categories": ["museum"],
    "travel_style": "explore"
  }
}
```

Optional fields use camelCase or snake_case aliases (`user_profile`, `radius_km`, `top_k`, `include_itinerary`, `allowed_categories`).

Weekly city-wide forecast index data is loaded from `data/istanbul_weekly_model.csv` when present.

Example forecast body:

```json
{
  "kind": "hotel",
  "label": "Ottoman Tiles Suites",
  "latlng": { "lat": 41.0049, "lng": 28.9769 },
  "horizonWeeks": 4
}
```
