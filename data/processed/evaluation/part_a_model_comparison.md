# Part A Model Comparison

This summary compares model performance on the `crowd_index` target used in Part A.

- Target minimum: `0.145655`
- Target maximum: `0.796757`
- Target mean: `0.398808`
- Target standard deviation: `0.121133`
- Target range: `0.651102`

Important interpretation note:
- `crowd_index` is a constructed target based directly on trend demand, temperature, and precipitation, so very small linear-model errors partly reflect target reconstructability rather than purely out-of-sample forecasting difficulty.

| model | family | rmse_test | mae_test | r2_test | rmse_test_pct_of_range | mae_test_pct_of_range | source_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OLS | Linear regression | 0.000000 | 0.000000 | 1.000000 | 0.00% | 0.00% | metrics_csv |
| Lasso | Regularized linear regression | 0.000209 | 0.000164 | 0.999997 | 0.03% | 0.03% | metrics_csv |
| Ridge | Regularized linear regression | 0.001600 | 0.001249 | 0.999804 | 0.25% | 0.19% | metrics_csv |
| XGBoost | Gradient-boosted trees | 0.036230 | 0.020677 | 0.899764 | 5.56% | 3.18% | metrics_csv |
| Random Forest | Bagged decision trees | 0.059935 | 0.027415 | 0.725683 | 9.21% | 4.21% | metrics_csv |
| LSTM | Sequence neural network | 0.066824 | 0.044257 | 0.659002 | 10.26% | 6.80% | metrics_csv |
| LightGBM | Gradient-boosted trees | 0.068420 | 0.031220 | 0.642519 | 10.51% | 4.79% | metrics_csv |
