# Tourism Crowd Forecasting: Project Details and Goals

## 1. Executive Summary

This project builds an end-to-end tourism crowd forecasting and recommendation prototype for Istanbul. Its central purpose is to help visitors make better decisions about when and where to go by combining city-level demand forecasting, point-of-interest attractiveness modeling, crowd-aware ranking, and a map-based user experience.

The core idea is simple: popular cities do not feel crowded uniformly. A busy week in Istanbul affects Sultanahmet, Galata, the Bosphorus, museums, religious sites, viewpoints, and quieter neighborhood attractions differently. A useful travel assistant therefore needs more than a generic weather forecast or a list of famous landmarks. It needs to estimate broad tourism pressure over time, distribute that pressure across places, and recommend practical alternatives when a selected attraction is likely to be crowded.

The repository currently contains four major layers:

1. A data science workflow in `notebooks/` and `scripts/` that prepares weather, Google Trends, holiday, POI, Wikipedia, OpenTripMap, and derived modeling artifacts.
2. A two-part modeling system that estimates temporal city demand and POI-level attractiveness.
3. A Flask backend in `backend-python/` that exposes search, forecast, and recommendation APIs.
4. A Vite TypeScript frontend in `frontend/` that presents an interactive map, place search, crowd details, and nearby alternatives.

The project should be understood as a research-backed prototype rather than a production crowd-counting system. It does not yet use live sensor data, ticket scans, mobile mobility feeds, or real-time congestion measurements. Instead, it constructs a defensible crowd-pressure signal from available proxy data and makes that signal useful through ranking, explanation, and UI design.

## 2. Project Motivation

Tourism crowding is both a visitor-experience problem and a destination-management problem. Visitors want to avoid wasting limited travel time in long queues or overpacked spaces. Local planners and tourism businesses want demand to be distributed more evenly across neighborhoods and attractions. A recommendation system that gently redirects visitors from overloaded places toward nearby, semantically similar, and lower-crowd alternatives can support both goals.

Istanbul is a strong case study because it has dense clusters of iconic attractions, large seasonal tourism swings, many historic and cultural POIs, and a transportation geography where small distance changes can meaningfully alter visitor experience. A visitor near Hagia Sophia may not need a generic list of "top attractions"; they may need to know whether Hagia Sophia is currently expected to be difficult and, if so, whether Hagia Irene, a nearby museum, mosque, viewpoint, or quieter historic site would be a better choice.

The project therefore aims to answer practical questions such as:

- Which weeks are expected to have high tourism pressure in Istanbul?
- How can city-wide demand be translated into likely crowd pressure at specific POIs?
- Which nearby alternatives offer meaningful crowd relief while staying relevant to the user's intent?
- How can these recommendations be presented clearly enough for a traveler to trust and act on?
- How can a prototype remain modular so better data sources and models can replace the current proxies later?

## 3. Main Goals

### 3.1 Forecast Tourism Crowd Pressure

The first goal is to model weekly crowd pressure for Istanbul. The project constructs a `crowd_index` target from tourism demand proxies, weather, temporal features, and holiday indicators. This target is then modeled using several approaches, including linear regression, regularized linear models, Random Forest, XGBoost, LightGBM, and LSTM.

The forecasting layer is called "Part A" in the evaluation artifacts. It focuses on time: given a week, what is the expected city-level tourism pressure? This produces an Istanbul-wide demand score that can be used by the backend and frontend.

### 3.2 Model POI-Level Attractiveness

The second goal is to estimate how much of the city-wide tourism pressure should be associated with each POI. This layer is called "Part B". It uses POI metadata, categories, location, OpenTripMap information, Wikipedia enrichment, and manually reviewed signals to produce a POI attractiveness or weight score.

The Part B model does not claim to measure live foot traffic. Instead, it estimates relative attraction strength. A famous landmark should absorb more city demand than a minor fountain; a major mosque, museum, palace, fortress, or tower should usually receive a different score than a small or poorly documented site.

### 3.3 Combine Time and Place

The project combines the Part A temporal demand score with Part B POI weights to create POI-time crowd matrices. These matrices estimate crowd pressure for each POI across modeled weeks. The combined workflow outputs files such as `otm_crowdindex_xgb__rf_weekly.csv`, where the first model label represents the temporal model and the second represents the POI attractiveness model.

This design is important because it separates two different questions:

- "How busy is Istanbul likely to be this week?"
- "Which places are most likely to absorb that demand?"

Keeping those questions separate makes the workflow easier to evaluate, debug, and replace later.

### 3.4 Recommend Better Alternatives

The fourth goal is to turn crowd estimates into user-facing decisions. The recommendation system can rank candidate POIs near a user location, incorporate distance and quality, apply personalization, and rerank results for diversity. It can also run in anchor-based alternative mode: when a user selects a specific landmark, the backend can return nearby alternatives that are more practical or calmer.

This is the core visitor-value feature. The app should not merely say, "This place is crowded." It should help the user answer, "What should I do instead?"

### 3.5 Explain Recommendations

The system includes an explanation layer so recommendations are not black boxes. Explanations can mention distance, crowd level, category relevance, personalization, and itinerary context. This matters because travel recommendations require trust: a visitor is more likely to switch plans if the app gives a clear reason.

### 3.6 Provide a Working Interactive Prototype

The project includes a frontend called Istanbul Crowd Compass. It allows the user to search for landmarks, use their current location, click on the map, inspect crowd estimates, and open places in Google Maps. The frontend is not just a demo wrapper around notebooks; it is the beginning of a usable product experience.

## 4. Repository Structure

The repository is organized around research artifacts, backend services, and frontend experience.

`notebooks/` contains the exploratory and production-style notebook workflow. These notebooks cover raw data collection, weather preprocessing, Google Trends preprocessing, crowd-index construction, holiday features, model training, POI enrichment, OpenTripMap processing, Wikipedia review, NLP feature creation, and final end-to-end workflow assembly.

`scripts/` contains repeatable Python scripts that rebuild model artifacts, refresh weather and trends, evaluate models, generate result tables, and rebuild the workflow matrix. These scripts are important because they move the project from manual notebook execution toward reproducible pipelines.

`data/raw/` contains original or lightly processed source files such as Istanbul POIs, daily weather, and Google Trends exports.

`data/processed/` contains cleaned datasets, model-ready tables, predictions, evaluation outputs, POI weights, combined crowd matrices, feature importance files, and recommendation examples.

`backend-python/` contains the Flask API and the Python recommendation engine. The backend reads CSV artifacts, exposes search endpoints, serves city-wide forecasts, and runs the recommendation pipeline.

`frontend/` contains the Vite TypeScript web app. It communicates with the Flask API, renders a Leaflet map, manages user selection state, and presents forecast and recommendation results.

`docs/` contains explanatory documentation. The existing recommendation-system document focuses on pipeline internals; this document provides a broader project-level explanation.

## 5. Data Sources and Feature Engineering

The project uses multiple proxy data sources because true crowd counts are not available in the repository.

Weather data is collected and aggregated into weekly Istanbul weather features. Daily values are converted into weekly signals such as average temperature and total precipitation. Weather matters because outdoor tourism demand is affected by comfort, rainfall, and seasonality.

Google Trends data is used as a demand proxy. Tourism-related search interest can help approximate periods when visitors are more likely to plan or perform tourism activity. These trend scores are merged into the temporal dataset and normalized.

Holiday data is added as a binary or calendar feature. Public holidays and major religious holidays can shift visitor behavior, domestic travel, and attraction crowding. The workflow includes holiday processing through `model_dataset_with_holidays.csv`.

POI data is collected and enriched from sources such as OpenStreetMap, OpenTripMap, and Wikipedia. The project works to create canonical POI records, remove duplicates, enrich names and descriptions, identify categories, and generate model-ready rows.

Wikipedia enrichment is especially useful because page metadata can act as a popularity proxy. Well-known sites tend to have stronger Wikipedia signals, although this is imperfect and can be biased toward better-documented places. The project therefore includes review files and manual cleanup steps to improve reliability.

NLP POI text features are generated for richer POI modeling. Textual descriptions and category information can help distinguish museums, mosques, palaces, towers, viewpoints, and other attraction types.

## 6. Part A: Temporal Crowd-Index Modeling

Part A predicts the city-wide `crowd_index`. This index is constructed from normalized demand and environmental signals. Earlier project documentation describes a formula that combines trend demand, average temperature, and inverse precipitation. Later model datasets include holiday and temporal features such as month, week of year, and season flags.

The models are evaluated using a chronological split, which is appropriate for time-dependent forecasting because it avoids training on future observations and testing on past observations. Evaluation artifacts compare model families using RMSE, MAE, and R2.

Current Part A results show very strong performance for linear and regularized linear models. This is expected because the target is constructed directly from the same family of input features. The documentation correctly notes that near-perfect linear results partly reflect target reconstructability rather than proof of real-world forecasting power. XGBoost and Random Forest also perform reasonably, while LSTM and LightGBM are present as comparative baselines.

The project currently uses the temporal model outputs to create weekly city-wide scores. The backend can load `backend-python/data/istanbul_weekly_model.csv` and return forecast details for a selected week. The frontend exposes period options such as latest modeled week, recent low week, recent medium week, and recent high week.

## 7. Part B: POI Attractiveness Modeling

Part B estimates POI attractiveness. The key purpose is to distribute city-level tourism pressure across attractions. A POI with high attractiveness should receive a larger share of the city demand signal than a lower-profile POI.

Part B uses manually reviewed and enriched POI data. The repository contains files for OpenTripMap base data, Wikipedia review, model-ready POIs, candidate duplicate handling, exclusion lists, weight group statistics, and final POI weights.

Evaluation compares a manual baseline with Random Forest and XGBoost. Current results show Random Forest performing best among the Part B options, followed by XGBoost, with the manual baseline much weaker on the test set. The evaluation note is important: the manual baseline is tested without leaking direct Wikipedia labels into the fallback estimate.

The Part B output is not a live crowd count. It is an attraction-weight model. This distinction should remain clear in any presentation or report. The model is useful because it provides a structured way to say, "When Istanbul is busy, these POIs are more likely to be crowded than those POIs."

## 8. Combined POI-Time Crowd Workflow

The combined workflow multiplies or blends temporal demand with POI attractiveness to estimate crowd pressure at the POI-week level. The script `scripts/rebuild_workflow_matrix.py` loads the model dataset, rebuilds Random Forest and XGBoost temporal predictions, prepares manual/RF/XGB Part B tables, and creates combination outputs.

The workflow creates combinations such as:

- Random Forest temporal model with manual POI weights.
- Random Forest temporal model with Random Forest POI weights.
- Random Forest temporal model with XGBoost POI weights.
- XGBoost temporal model with manual POI weights.
- XGBoost temporal model with Random Forest POI weights.
- XGBoost temporal model with XGBoost POI weights.

The backend default currently prefers the `xgb__rf` workflow CSV through the crowd-score provider. This choice balances a strong temporal model with the strongest evaluated Part B model in the repository.

The crowd-score provider normalizes crowd pressure using three ideas: global absolute normalization, within-date relative ranking, and city-demand intensity. This prevents the system from flattening all weeks into the same shape and helps low, medium, and high modeled periods produce visibly different app behavior.

## 9. Backend Architecture

The backend is implemented with Flask in `backend-python/app.py`. It exposes APIs for health checks, hotels, POI search, combined search, forecast periods, forecasts, and recommendations.

The forecast endpoint validates the selected entity, location, forecast horizon, and optional modeled week. If the weekly model CSV is available, it returns a city-wide modeled forecast. If the file is missing, it falls back to a deterministic demo score so the UI remains usable.

The recommendation endpoint accepts an origin, optional timestamp, user profile, radius, result count, itinerary flag, allowed categories, and optional anchor POI. If no anchor is provided, it runs the general recommendation pipeline. If an anchor POI is provided, it switches into anchor-based alternative mode.

The backend design is intentionally CSV-first. That keeps the project easy to run and easy to inspect. Data science outputs become backend inputs without requiring a database or model server. In a production version, these CSVs could be replaced by scheduled jobs, feature stores, databases, or deployed model services.

## 10. Recommendation Pipeline

The recommendation pipeline lives under `backend-python/recommendation/`. It is modular and stage-oriented.

Candidate generation loads POI data, cleans it, filters by category when requested, and selects rows within a radius of the origin. Spatial distance is computed so nearer POIs can be favored.

Crowd scoring attaches `crowd_pressure_index` to candidate rows. The preferred path uses a registered provider backed by the workflow CSV. If that provider is unavailable, the system can fall back to deterministic mock crowd scores, optionally adjusted by time-aware heuristics.

Feature engineering creates ranking features such as distance score, calm score, rating score, preference score, and novelty score. Higher raw crowd means lower calm, so the ranker can prefer less crowded options.

Scoring combines features with configurable weights. The default weighting emphasizes distance and calm while preserving quality. The pipeline can also apply non-linear crowd penalties so highly crowded places are pushed down more aggressively.

Personalization can incorporate preferred categories, avoided categories, travel style, budget, and implicit feedback. This gives the project a path from generic crowd recommendations toward user-specific travel planning.

Diversity reranking uses Maximal Marginal Relevance so the result list does not become a repetitive set of nearly identical places. Optional per-category caps can further prevent overconcentration.

Explanations convert model and ranking signals into readable recommendation text. This is essential because the app needs to justify why an alternative is better, not only return a score.

Itinerary generation can order selected stops when requested. This is currently optional, but it points toward a future route-planning feature.

## 11. Anchor-Based Alternatives

The anchor-based alternative mode is one of the most important product behaviors. In this mode, a user selects a specific POI, such as Hagia Sophia or Galata Tower. The backend finds candidate alternatives near the user's origin and near the selected anchor, attaches crowd scores, and ranks alternatives by crowd relief, similarity, and practicality.

This mode matches how people often make travel decisions. A visitor does not usually begin with an abstract desire for a ranked list. They begin with an intended stop: "I want to go here." If that place is crowded, the app should say, "Here are nearby alternatives that still fit your plan."

The evaluation file for the recommendation system treats this as an anchor-based decision system. It reports full coverage across evaluated anchor-period cases, average top crowd relief around 0.32, high average similarity, high practicality, and an average top alternative distance of roughly half a kilometer. These metrics do not prove user satisfaction, but they show that the recommendation logic is behaving coherently under modeled crowd conditions.

## 12. Frontend Experience

The frontend is a Vite TypeScript application. It uses Leaflet for the map and plain DOM APIs for UI state and rendering. The interface is called Istanbul Crowd Compass.

The app lets users choose a starting point using browser geolocation, tap the map, or search for a landmark. The selected place is reflected in a marker, a selection chip, and a detail sheet. The app can show expected crowd level, a numerical score, city activity, visit notes, warnings for crowded places, and nearby alternatives.

The frontend communicates with the Flask backend through `frontend/src/api/api.ts`. The default API base is `http://localhost:8080`, with `VITE_API_BASE_URL` available as an override.

The app currently focuses on landmark search and POI alternatives rather than hotel search as the main workflow. It is designed around quick decision support: pick a place, inspect the crowd read, and either keep the plan or switch to a nearby option.

## 13. Evaluation and Current Results

The project includes evaluation artifacts for Part A, Part B, and the recommendation system.

Part A evaluation compares multiple temporal forecasting models. Linear models perform almost perfectly because the target is constructed from modeled input features. XGBoost, Random Forest, LSTM, and LightGBM provide broader comparisons and give a more realistic sense of non-linear model behavior.

Part B evaluation shows Random Forest as the strongest POI attractiveness model among the current options, with XGBoost second and the manual baseline substantially weaker.

Recommendation evaluation focuses on coverage, crowd relief, similarity, practicality, and distance to anchor. The current evaluation shows that the system returns alternatives for all tested anchor-period cases and generally finds nearby lower-crowd options that remain semantically related.

These evaluations are valuable, but they should be interpreted carefully. The project does not yet have ground-truth crowd observations, real user acceptance labels, or controlled A/B testing. The current metrics mostly validate internal consistency and comparative model behavior.

## 14. Important Limitations

The main limitation is that the crowd target is proxy-based. Google Trends, weather, holidays, Wikipedia popularity, and POI metadata are useful signals, but they are not the same as measured footfall.

The temporal target is constructed, so models can partially reconstruct it from its own ingredients. This is acceptable for a prototype, but future work should validate against independent observations.

The POI attractiveness model depends on metadata quality. Some POIs may be underdocumented, duplicated, mislabeled, or overrepresented because of Wikipedia or OpenTripMap coverage patterns.

The recommendation system has no real user feedback loop yet. It can estimate crowd relief and semantic similarity, but it cannot yet learn from clicks, saves, skips, route changes, or user satisfaction.

The frontend depends on the local Flask backend. It is a working prototype, but production deployment would require hosting, API reliability, CORS configuration, monitoring, and a more robust data-refresh process.

The system currently works at weekly modeled granularity for core forecasts. Time-of-day heuristics exist, but truly live hourly or minute-level crowd forecasting would require additional data.

## 15. Future Roadmap

The most important future improvement is independent validation. The project would become much stronger with ground-truth or semi-ground-truth crowd data, such as attraction visit counts, ticketing data, mobility aggregates, queue observations, Google Popular Times-style data, or manually collected samples.

The data pipeline should be made more reproducible. Notebooks are useful for exploration, but the project already has scripts that can be extended into a clear command-line pipeline for refreshing raw data, rebuilding processed datasets, retraining models, evaluating results, and exporting backend-ready artifacts.

The backend could move from CSV loading to a lightweight database once the data becomes larger or more frequently refreshed. However, the current CSV-first design is appropriate for a prototype and should not be replaced until there is a real operational need.

The frontend can be expanded with richer itinerary planning, filters for visitor type, accessibility preferences, indoor/outdoor preferences, opening hours, route duration, transit mode, and multi-stop planning.

The recommendation system can learn from implicit feedback. If users choose alternatives, dismiss suggestions, open directions, or return to the same category, those behaviors could adjust preference scores.

The model layer can support more granular timestamps. A future version could combine weekly seasonality with day-of-week, hour-of-day, event calendars, weather forecasts, ferry/transport disruptions, and live signals.

The explanation layer can be improved with uncertainty. Instead of presenting a single score as definitive, the app could communicate confidence, data freshness, and whether the estimate is model-based, heuristic, or fallback.

## 16. Definition of Success

The project succeeds if it demonstrates that tourism crowd forecasting can be converted into useful traveler decisions. A strong version of the project should:

- Produce a credible city-wide demand signal for Istanbul.
- Estimate relative crowd pressure across POIs.
- Recommend alternatives that are nearby, lower-crowd, and semantically relevant.
- Explain recommendations in a way that users can understand.
- Let users interact with the system through a polished map-based interface.
- Preserve a modular architecture where better data and models can replace the prototype components.

The current repository already establishes this foundation. It includes the data preparation work, multiple model comparisons, an integrated POI-time crowd matrix, a backend recommendation pipeline, and a usable frontend. The next phase should focus on validation, automation, deployment readiness, and stronger real-world data.

## 17. One-Sentence Project Vision

Tourism Crowd Forecasting aims to become a practical decision-support tool that helps Istanbul visitors avoid overcrowded attractions and discover nearby alternatives, while giving destination managers a framework for understanding and distributing tourism pressure across time and place.
