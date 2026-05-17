# Recommendation Weight Sensitivity

This analysis checks whether small policy changes to the anchor-based alternative ranking weights substantially alter recommendation behavior.

Interpreting the results:
- A high top-1 match rate means the chosen policy is not highly fragile relative to nearby alternatives.
- A high top-3 overlap means the broader short list remains stable even when the exact policy changes.
- Few baseline top-1 rank changes mean the implemented winner is not easily displaced under nearby policies.
- Similar average crowd relief, similarity, and practicality values suggest that the overall recommendation behavior remains coherent across policy variants.

## Policy Summary

| policy_id | policy_label | coverage_rate | average_recommendation_count | average_top_crowd_relief | average_top_similarity | average_top_practicality | average_top_distance_to_anchor_km | top1_match_rate_vs_implemented | changed_top1_cases_vs_implemented | average_top3_overlap_vs_implemented | baseline_top1_rank_changed_cases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| implemented_dynamic | Implemented dynamic policy | 100.00% | 3.8333 | 0.3212 | 0.7958 | 0.8649 | 0.5068 | 100.00% | 0 | 100.00% | 0 |
| crowd_heavy_fixed | Crowd-heavy fixed policy | 100.00% | 3.8333 | 0.3212 | 0.7958 | 0.8649 | 0.5068 | 100.00% | 0 | 96.30% | 0 |
| balanced_fixed | Balanced fixed policy | 100.00% | 3.8333 | 0.3212 | 0.7958 | 0.8649 | 0.5068 | 100.00% | 0 | 96.30% | 0 |
| similarity_practicality_fixed | Similarity-practicality fixed policy | 100.00% | 3.8333 | 0.3212 | 0.7958 | 0.8649 | 0.5068 | 100.00% | 0 | 85.19% | 0 |

## Top-1 Comparison

| policy_label | anchor_name | basis_week_start | policy_top_alternative | policy_top3_ids | implemented_top_alternative | implemented_top3_ids | top3_overlap_rate | implemented_top1_rank_under_policy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Crowd-heavy fixed policy | Hagia Sophia | 2026-05-03 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Balanced fixed policy | Hagia Sophia | 2026-05-03 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Similarity-practicality fixed policy | Hagia Sophia | 2026-05-03 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Crowd-heavy fixed policy | Hagia Sophia | 2026-03-08 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Balanced fixed policy | Hagia Sophia | 2026-03-08 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Similarity-practicality fixed policy | Hagia Sophia | 2026-03-08 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Crowd-heavy fixed policy | Hagia Sophia | 2026-04-19 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Balanced fixed policy | Hagia Sophia | 2026-04-19 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Similarity-practicality fixed policy | Hagia Sophia | 2026-04-19 | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | Hagia Irene | ["otm_R4742554", "otm_W303179753", "otm_W103953125"] | 100.00% | None |
| Crowd-heavy fixed policy | Chora Mosque / Kariye Museum | 2026-05-03 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Balanced fixed policy | Chora Mosque / Kariye Museum | 2026-05-03 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Similarity-practicality fixed policy | Chora Mosque / Kariye Museum | 2026-05-03 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Crowd-heavy fixed policy | Chora Mosque / Kariye Museum | 2026-03-08 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Balanced fixed policy | Chora Mosque / Kariye Museum | 2026-03-08 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Similarity-practicality fixed policy | Chora Mosque / Kariye Museum | 2026-03-08 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Crowd-heavy fixed policy | Chora Mosque / Kariye Museum | 2026-04-19 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Balanced fixed policy | Chora Mosque / Kariye Museum | 2026-04-19 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Similarity-practicality fixed policy | Chora Mosque / Kariye Museum | 2026-04-19 | Fethiye Mosque / Museum | ["otm_W136456159"] | Fethiye Mosque / Museum | ["otm_W136456159"] | 100.00% | None |
| Crowd-heavy fixed policy | Galata Tower | 2026-05-03 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | 100.00% | None |
| Balanced fixed policy | Galata Tower | 2026-05-03 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | 100.00% | None |
| Similarity-practicality fixed policy | Galata Tower | 2026-05-03 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W280961352"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | 66.67% | None |
| Crowd-heavy fixed policy | Galata Tower | 2026-03-08 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W280961352"] | 66.67% | None |
| Balanced fixed policy | Galata Tower | 2026-03-08 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W280961352"] | 66.67% | None |
| Similarity-practicality fixed policy | Galata Tower | 2026-03-08 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W280961352"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W280961352"] | 100.00% | None |
| Crowd-heavy fixed policy | Galata Tower | 2026-04-19 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | 100.00% | None |
| Balanced fixed policy | Galata Tower | 2026-04-19 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | 100.00% | None |
| Similarity-practicality fixed policy | Galata Tower | 2026-04-19 | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W280961352"] | Nusretiye Clock Tower | ["otm_N6373080188", "otm_W639302102", "otm_W263949143"] | 66.67% | None |
| Crowd-heavy fixed policy | The Blue Mosque | 2026-05-03 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | 100.00% | None |
| Balanced fixed policy | The Blue Mosque | 2026-05-03 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | 100.00% | None |
| Similarity-practicality fixed policy | The Blue Mosque | 2026-05-03 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_W132277802", "otm_W104061375"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | 66.67% | None |
| Crowd-heavy fixed policy | The Blue Mosque | 2026-03-08 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_W132277802", "otm_R12342892"] | 100.00% | None |
| Balanced fixed policy | The Blue Mosque | 2026-03-08 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_W132277802", "otm_R12342892"] | 100.00% | None |
| Similarity-practicality fixed policy | The Blue Mosque | 2026-03-08 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_W132277802", "otm_W104061375"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_W132277802", "otm_R12342892"] | 66.67% | None |
| Crowd-heavy fixed policy | The Blue Mosque | 2026-04-19 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | 100.00% | None |
| Balanced fixed policy | The Blue Mosque | 2026-04-19 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | 100.00% | None |
| Similarity-practicality fixed policy | The Blue Mosque | 2026-04-19 | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_W132277802", "otm_W104061375"] | Sokullu Mehmed Pasa Mosque | ["otm_R4567928", "otm_R12342892", "otm_W132277802"] | 66.67% | None |
| Crowd-heavy fixed policy | Süleymaniye Mosque | 2026-05-03 | Bayezid II Mosque | ["otm_R12342892", "otm_R4567928", "otm_W109980654"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | 100.00% | None |
| Balanced fixed policy | Süleymaniye Mosque | 2026-05-03 | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | 100.00% | None |
| Similarity-practicality fixed policy | Süleymaniye Mosque | 2026-05-03 | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_W175518494"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | 66.67% | None |
| Crowd-heavy fixed policy | Süleymaniye Mosque | 2026-03-08 | Bayezid II Mosque | ["otm_R12342892", "otm_R4567928", "otm_W109980654"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_W175518494"] | 66.67% | None |
| Balanced fixed policy | Süleymaniye Mosque | 2026-03-08 | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_W175518494"] | 66.67% | None |
| Similarity-practicality fixed policy | Süleymaniye Mosque | 2026-03-08 | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_N4509066189"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_W175518494"] | 66.67% | None |
| Crowd-heavy fixed policy | Süleymaniye Mosque | 2026-04-19 | Bayezid II Mosque | ["otm_R12342892", "otm_R4567928", "otm_W109980654"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | 100.00% | None |
| Balanced fixed policy | Süleymaniye Mosque | 2026-04-19 | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | 100.00% | None |
| Similarity-practicality fixed policy | Süleymaniye Mosque | 2026-04-19 | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_N4509066189"] | Bayezid II Mosque | ["otm_R12342892", "otm_W109980654", "otm_R4567928"] | 66.67% | None |
| Crowd-heavy fixed policy | Rumeli Fortress | 2026-05-03 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Balanced fixed policy | Rumeli Fortress | 2026-05-03 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Similarity-practicality fixed policy | Rumeli Fortress | 2026-05-03 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Crowd-heavy fixed policy | Rumeli Fortress | 2026-03-08 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Balanced fixed policy | Rumeli Fortress | 2026-03-08 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Similarity-practicality fixed policy | Rumeli Fortress | 2026-03-08 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Crowd-heavy fixed policy | Rumeli Fortress | 2026-04-19 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Balanced fixed policy | Rumeli Fortress | 2026-04-19 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
| Similarity-practicality fixed policy | Rumeli Fortress | 2026-04-19 | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | Schiffbrücke über den Bosporus | ["otm_Q1389334", "otm_W403376607"] | 100.00% | None |
