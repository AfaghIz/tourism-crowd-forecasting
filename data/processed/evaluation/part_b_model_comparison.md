# Part B Model Comparison

This summary compares the manual fallback baseline against the Part B Random Forest and XGBoost models.

Important interpretation note:
- The manual baseline is not scored using copied observed wiki labels. Instead, direct wiki signal is hidden and the fallback shrinkage estimate is rebuilt from the training split only.

| model | family | rmse_test | mae_test | r2_test | train_rows | test_rows | source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Random Forest | Bagged decision trees | 1.192741 | 0.993307 | 0.314912 | 127 | 32 | metrics_json |
| XGBoost | Gradient-boosted trees | 1.342095 | 1.115385 | 0.132599 | 127 | 32 | metrics_json |
| Manual baseline | Rule-based fallback | 4.646803 | 3.907978 | -9.398298 | 127 | 32 | evaluation_script |
