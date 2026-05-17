# Recommendation System Evaluation

This evaluation treats the recommendation layer as an anchor-based decision system rather than a supervised predictor.
The goal is to measure whether the system returns nearby, lower-crowd, semantically compatible alternatives across modeled periods.

## Overall Summary

- Total anchor-period cases: `18`
- Cases with at least one recommendation: `18`
- Overall coverage rate: `100.00%`
- High-anchor coverage rate: `100.00%`
- Raw low/medium-anchor suppression rate: `0.00%`
- Average recommendation count: `3.83`
- Average top crowd relief: `0.3212`
- Median top crowd relief: `0.2975`
- Average top similarity: `0.7958`
- Average top practicality: `0.8649`
- Average top distance to anchor: `0.507` km

Important interpretation note:
- These results evaluate recommendation behavior under modeled crowd conditions. They do not represent click-through accuracy or ground-truth user acceptance, because the project does not have labeled recommendation targets.
- The app UI only surfaces anchor alternatives for high-crowd POIs, so the raw low/medium suppression rate here describes backend recommendation behavior rather than the final frontend gating rule.

## By Modeled Period

| basis_week_start | basis_label | basis_level | cases | recommendations | average_anchor_crowd | average_city_demand | average_top_crowd_relief | coverage_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-03-08 | Recent low week (2026-03-08) | Low | 6 | 6 | 0.4378 | 0.3077 | 0.3326 | 100.00% |
| 2026-04-19 | Recent medium week (2026-04-19) | Medium | 6 | 6 | 0.5409 | 0.4252 | 0.3211 | 100.00% |
| 2026-05-03 | Latest modeled week (2026-05-03) | High | 6 | 6 | 0.7018 | 0.6085 | 0.3099 | 100.00% |

## By Anchor

| anchor_name | anchor_category | periods_evaluated | recommendations | average_anchor_crowd | average_top_crowd_relief | average_top_similarity | average_top_distance_to_anchor_km | coverage_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Chora Mosque / Kariye Museum | museum | 3 | 3 | 0.4890 | 0.2521 | 0.9167 | 0.6490 | 100.00% |
| Galata Tower | attraction | 3 | 3 | 0.5794 | 0.3444 | 0.8750 | 0.7370 | 100.00% |
| Hagia Sophia | museum | 3 | 3 | 0.6736 | 0.1985 | 0.9833 | 0.1640 | 100.00% |
| Rumeli Fortress | museum | 3 | 3 | 0.5147 | 0.2249 | 0.2500 | 0.4130 | 100.00% |
| Süleymaniye Mosque | religious | 3 | 3 | 0.5746 | 0.4701 | 0.8750 | 0.6780 | 100.00% |
| The Blue Mosque | religious | 3 | 3 | 0.5298 | 0.4372 | 0.8750 | 0.4000 | 100.00% |

## Case Table

| anchor_name | basis_week_start | anchor_crowd_level | anchor_crowd_signal | anchor_city_demand_score | recommendation_count | top_alternative_name | top_crowd_relief | top_similarity | top_practicality | top_distance_to_anchor_km |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hagia Sophia | 2026-05-03 | High | 0.8398 | 0.6085 | 5 | Hagia Irene | 0.1928 | 0.9833 | 0.9563 | 0.1640 |
| Hagia Sophia | 2026-03-08 | Medium | 0.5301 | 0.3077 | 5 | Hagia Irene | 0.2043 | 0.9833 | 0.9563 | 0.1640 |
| Hagia Sophia | 2026-04-19 | Medium | 0.6510 | 0.4252 | 5 | Hagia Irene | 0.1985 | 0.9833 | 0.9563 | 0.1640 |
| Chora Mosque / Kariye Museum | 2026-05-03 | Medium | 0.6153 | 0.6085 | 1 | Fethiye Mosque / Museum | 0.2420 | 0.9167 | 0.8268 | 0.6490 |
| Chora Mosque / Kariye Museum | 2026-03-08 | Medium | 0.3799 | 0.3077 | 1 | Fethiye Mosque / Museum | 0.2622 | 0.9167 | 0.8268 | 0.6490 |
| Chora Mosque / Kariye Museum | 2026-04-19 | Medium | 0.4718 | 0.4252 | 1 | Fethiye Mosque / Museum | 0.2520 | 0.9167 | 0.8268 | 0.6490 |
| Galata Tower | 2026-05-03 | High | 0.7252 | 0.6085 | 5 | Nusretiye Clock Tower | 0.3328 | 0.8750 | 0.8036 | 0.7370 |
| Galata Tower | 2026-03-08 | Medium | 0.4534 | 0.3077 | 5 | Nusretiye Clock Tower | 0.3561 | 0.8750 | 0.8036 | 0.7370 |
| Galata Tower | 2026-04-19 | Medium | 0.5596 | 0.4252 | 5 | Nusretiye Clock Tower | 0.3443 | 0.8750 | 0.8036 | 0.7370 |
| The Blue Mosque | 2026-05-03 | Medium | 0.6648 | 0.6085 | 5 | Sokullu Mehmed Pasa Mosque | 0.4211 | 0.8750 | 0.8934 | 0.4000 |
| The Blue Mosque | 2026-03-08 | Medium | 0.4130 | 0.3077 | 5 | Sokullu Mehmed Pasa Mosque | 0.4534 | 0.8750 | 0.8934 | 0.4000 |
| The Blue Mosque | 2026-04-19 | Medium | 0.5114 | 0.4252 | 5 | Sokullu Mehmed Pasa Mosque | 0.4370 | 0.8750 | 0.8934 | 0.4000 |
| Süleymaniye Mosque | 2026-05-03 | High | 0.7194 | 0.6085 | 5 | Bayezid II Mosque | 0.4542 | 0.8750 | 0.8191 | 0.6780 |
| Süleymaniye Mosque | 2026-03-08 | Medium | 0.4495 | 0.3077 | 5 | Bayezid II Mosque | 0.4862 | 0.8750 | 0.8191 | 0.6780 |
| Süleymaniye Mosque | 2026-04-19 | Medium | 0.5549 | 0.4252 | 5 | Bayezid II Mosque | 0.4700 | 0.8750 | 0.8191 | 0.6780 |
| Rumeli Fortress | 2026-05-03 | Medium | 0.6465 | 0.6085 | 2 | Schiffbrücke über den Bosporus | 0.2164 | 0.2500 | 0.8899 | 0.4130 |
| Rumeli Fortress | 2026-03-08 | Medium | 0.4008 | 0.3077 | 2 | Schiffbrücke über den Bosporus | 0.2335 | 0.2500 | 0.8899 | 0.4130 |
| Rumeli Fortress | 2026-04-19 | Medium | 0.4968 | 0.4252 | 2 | Schiffbrücke über den Bosporus | 0.2248 | 0.2500 | 0.8899 | 0.4130 |
