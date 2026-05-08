# Part A Model Comparison

This summary compares model performance on the `crowd_index` target used in Part A.

- Target minimum: `0.145655`
- Target maximum: `0.926518`
- Target mean: `0.425607`
- Target standard deviation: `0.141544`
- Target range: `0.780862`

Important interpretation note:
- `crowd_index` is a constructed target based directly on trend demand, temperature, and precipitation, so very small linear-model errors partly reflect target reconstructability rather than purely out-of-sample forecasting difficulty.

| model | family | rmse_test | mae_test | r2_test | rmse_test_pct_of_range | mae_test_pct_of_range | source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OLS | Linear regression | 0.000000 | 0.000000 | 1.000000 | 0.00% | 0.00% | metrics_csv |
| Lasso | Regularized linear regression | 0.000250 | 0.000202 | 0.999996 | 0.03% | 0.03% | metrics_csv |
| Ridge | Regularized linear regression | 0.001789 | 0.001486 | 0.999811 | 0.23% | 0.19% | metrics_csv |
| LightGBM | Gradient-boosted trees | 0.015203 | 0.010714 | 0.986339 | 1.95% | 1.37% | metrics_csv |
| Random Forest | Bagged decision trees | 0.017606 | 0.012488 | 0.981679 | 2.25% | 1.60% | metrics_csv |
| XGBoost | Gradient-boosted trees | 0.017767 | 0.013037 | 0.981342 | 2.28% | 1.67% | metrics_csv |
| LSTM | Sequence neural network | 0.043456 | 0.032338 | 0.888382 | 5.57% | 4.14% | metrics_csv |
