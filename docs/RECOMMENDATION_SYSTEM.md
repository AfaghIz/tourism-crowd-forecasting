# Recommendation System Overview

This document describes the **pandas-based POI recommendation pipeline** implemented under `backend-python/recommendation/` and how clients (including the web frontend) call it via **`POST /api/recommendations`**.

---

## 1. Purpose

Given a **visitor origin** (latitude/longitude), optional **visit time**, and optional **user profile**, the system:

1. Loads POI data (primarily from CSV).
2. Filters by radius and optionally by category.
3. Attaches **time-aware** crowd / busyness signals.
4. Computes ranking **features** (distance, calm/crowd, rating, preference, novelty).
5. Applies **personalization** (explicit prefs + implicit feedback).
6. Combines features with **non-linear scoring** (weighted logs/powers).
7. Applies optional **time-of-day context** boosts per category.
8. **Re-ranks with MMR** for diversity.
9. Optionally caps diversity per category and builds **explanations** and an **itinerary**.

Design goals: **modular stages**, swappable components (e.g. ML crowd model), and a stable Python API (`recommend` / `run_recommendation_pipeline`).

---

## 2. Entry Points

### 2.1 Full pipeline (primary)

| Symbol | Module | Role |
|--------|--------|------|
| `recommend(...)` | `recommendation.pipeline` | User-facing wrapper with docstring. |
| `run_recommendation_pipeline(...)` | `recommendation.recommendation_pipeline` | Orchestrates named stages; returns `{ "recommendations": [...], "itinerary": ... }`. |

Main keyword arguments include `radius_km`, `top_k`, `include_itinerary`, `weights`, `alpha`, `lambda_mmr`, `context_beta`, `user_profile`, `preference_price_column`, `allowed_categories`, `csv_path`, etc. See module docstrings for the full list.

### 2.2 HTTP API

**`POST /api/recommendations`** calls `recommendation.pipeline.recommend` and returns JSON:

```json
{
  "recommendations": [ /* explanation-ready dicts per POI */ ],
  "itinerary": null | [ /* ordered stops when includeItinerary is true */ ]
}
```

Supported body fields include `origin` / `latlng`, optional ISO **`timestamp`**, **`userProfile`** / **`user_profile`**, **`radiusKm`**, **`topK`**, **`includeItinerary`**, **`allowedCategories`** / **`allowed_categories`**.

Environment variable **`RECOMMENDATION_POI_CSV`** can override the default CSV path (otherwise `data/otm_pois_model_ready.csv` or project-root CSV).

---

## 3. Pipeline Stages (Composable)

Implemented in `recommendation/recommendation_pipeline.py` as explicit functions so steps can be mocked or replaced.

### Stage A — Candidates

- **`load_poi_data`** → optional **`filter_by_categories`** (whitelist on `category_clean`) → **`get_candidates`** (Haversine radius around origin).
- Outputs a Geo/DataFrame with at least `distance_km`, coordinates, and POI identifiers.

### Stage B — Time-aware crowd column

- **`attach_crowd_scores`** fills **`crowd_pressure_index`** per row.
- Resolution uses **`get_crowd_score(poi_id, timestamp)`** in `crowd_scores.py`:
  - If a **`CrowdScoreProvider`** is registered (`set_crowd_score_provider`), its prediction is used as-is.
  - Otherwise: CSV/mock baseline × **`time_aware_crowd_multiplier(timestamp)`** from `crowd_time_heuristic.py` (diurnal curve, weekend uplift, seasonal placeholder, discrete time slots).
- **`df.attrs['crowd_timestamp']`** is set when a timestamp is supplied so **`compute_features`** stays consistent.

### Stage C — Ranking pool (`rank_candidates`)

From `ranking_pipeline.py`, this chains:

1. **`attach_preference_categories`** — legacy attrs for category allowlists used inside **`compute_features`**.
2. **`step_compute_features`** → **`compute_features`** (`feature_engineering.py`):
   - Builds **`distance_score`**, raw crowd → **`crowd_score`** (calm-oriented, with optional relative-neighborhood adjustment), **`rating_score`**, **`preference_score`**, **`novelty_score`**.
   - Uses **`get_crowd_score`** per row when `poi_id` is present.
   - Applies a **peak-visit penalty** when timestamp is set (busy POIs penalized more during peak visit windows via **`visit_peak_strength`**).
3. If **`user_profile`** is set → **`compute_preference_score`** (`personalization.py`) overwrites/refines **`preference_score`** (explicit prefs, implicit feedback, travel style, optional budget).
4. **`step_compute_score`** → **`compute_score`** (`scoring.py`): weighted combination with **`crowd_feature ** alpha`** (non-linear calm emphasis).
5. **`apply_context_boost`** — optional score multiplier by time bucket + category keywords.
6. **`rerank_with_mmr`** — **Maximal Marginal Relevance** on categories/geo similarity for diversity within the returned pool.

Parameters such as **`lambda_mmr`**, **`alpha`**, **`beta`** (context), **`novelty_jitter`**, etc., tune behavior.

### Stage D — Top-K

- Either **`ranked.head(top_k)`** or **`diversify`** when **`max_per_category`** is set (greedy cap per category).

### Stage E — Explanations

- **`generate_explanations`** (`explanation_engine.py`) builds natural-language text from scores + signals.
- Optional context: **`user_profile`**, **`timestamp`**, **`itinerary_poi_order`** (route stop index).
- Layers cover personalization phrasing, time-of-day crowding, diversity wording, and route position; **`enrich_explanations_alternative_clause`** adds copy when **`attach_alternative_suggestions`** finds a mellower same-category alternative.

### Stage F — Itinerary (optional)

- When **`include_itinerary=True`**, **`generate_itinerary`** (`itinerary.py`) orders stops (greedy NN, optional clustering, trip style from **`travel_style`** in profile).
- Stops include **`poi_id`** when available for explanation/route linkage.

---

## 4. Personalization

### 4.1 Explicit (`personalization.py`)

**`compute_preference_score`** reads **`user_profile`** keys such as:

- **`preferred_categories`** / **`avoided_categories`** — substring match on **`category_clean`** (no fixed taxonomy).
- **`budget_level`** / **`travel_style`** (`efficient` vs `explore`) — blends category signal with **`distance_score`**, **`novelty_score`**, and optional price columns.
- **`implicit_blend_weight`**, **`implicit_use_cosine`**, etc., tune implicit vs explicit mix.

### 4.2 Implicit feedback (`implicit_feedback.py`)

If **`poi_category_lookup`** plus **`visited_pois` / `liked_pois` / `skipped_pois`** are provided, category distributions drive extra **`preference_score`** mass (likes weighted higher than visits; skips penalize). Optional cosine variant compares a net preference vector to candidate categories.

---

## 5. Time-Aware Crowd Behavior

- **`crowd_time_heuristic.py`**: combines **diurnal**, **weekend**, **seasonal placeholder**, and **time-slot** multipliers on the non-ML path.
- **`visit_peak_strength(timestamp)`**: scalar used both semantically and inside **`compute_features`** for stronger penalties at crowded visit times.
- Registered ML providers bypass heuristic multiplication but still benefit from timestamp-aware **`preference_score`** / explanations when configured.

---

## 6. Frontend Integration

The Vite app (`frontend/`) calls **`fetchRecommendations`** (`src/api/api.ts`) → **`POST /api/recommendations`** with **`origin`**, **`timestamp`**, optional **`allowedCategories`**, etc.

- **“Use my location”** loads ranked rows into the global results list (requires the Flask API on port **8080**).
- **Alternatives / recommended nearby** lists use the same pipeline for any pin that shows the alternatives panel (location pins always receive ranked POIs; non-location pins when crowd is high).

Default API base URL: **`http://localhost:8080`** (override with **`VITE_API_BASE_URL`**).

---

## 7. Extension Points (Summary)

| Concern | Extension mechanism |
|--------|---------------------|
| Crowd ML | Implement **`CrowdScoreProvider`**; **`set_crowd_score_provider`**. |
| POI data | **`RECOMMENDATION_POI_CSV`**, or pass **`csv_path`** into **`run_recommendation_pipeline`**. |
| Weights / α / MMR | Arguments to **`rank_candidates`** / **`recommend`**. |
| Personalization | **`user_profile`** dict and optional **`preference_price_column`**. |
| Explanations | Swap or wrap **`generate_explanations`**; pass richer **`user_profile`** / **`timestamp`** / itinerary maps. |
| Routing | **`generate_itinerary`** parameters or replace with OR-Tools later (module doc hints). |

---

## 8. File Map (Core)

| Path | Role |
|------|------|
| `recommendation/recommendation_pipeline.py` | Stage orchestration, **`run_recommendation_pipeline`**. |
| `recommendation/pipeline.py` | **`recommend`**, **`recommend_with_legacy_list_return`**. |
| `recommendation/ranking_pipeline.py` | **`rank_candidates`**, **`step_compute_features`**, normalization helpers. |
| `recommendation/feature_engineering.py` | **`compute_features`**, score columns, peak penalty. |
| `recommendation/scoring.py` | **`compute_score`** (non-linear aggregate). |
| `recommendation/personalization.py` | **`compute_preference_score`**. |
| `recommendation/implicit_feedback.py` | Implicit profile + scores. |
| `recommendation/crowd_scores.py` | **`get_crowd_score`**, **`attach_crowd_scores`**. |
| `recommendation/crowd_time_heuristic.py` | Time multipliers, **`visit_peak_strength`**. |
| `recommendation/diversity.py` | **`rerank_with_mmr`**, **`diversify`**. |
| `recommendation/explanation_engine.py` | **`generate_explanations`**, alternative enrichment. |
| `recommendation/itinerary.py` | **`generate_itinerary`**, routing helpers. |
| `recommendation/alternatives.py` | Same-category lower-crowd alternatives. |
| `app.py` | Flask **`POST /api/recommendations`** → pandas **`recommend()`**. |

---

## 9. Quick Python Smoke Test

From `backend-python` with venv activated:

```python
from datetime import datetime
from recommendation import recommend

out = recommend(
    41.0086,
    28.9802,
    datetime.now(),
    {"preferred_categories": ["museum"], "travel_style": "explore"},
    radius_km=5,
    top_k=5,
    include_itinerary=False,
)
assert "recommendations" in out and "itinerary" in out
```

This exercises candidates → crowd → features → personalization → score → MMR → explanations end-to-end (subject to CSV availability).

---

*This document reflects the architecture as implemented in the repository; adjust weights and heuristics in code when production data or models change.*
