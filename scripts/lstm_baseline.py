from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from tensorflow import keras
import tensorflow as tf


RANDOM_STATE = 42
TEST_SIZE = 0.2
LOOKBACK_WEEKS = 8
EPOCHS = 250
BATCH_SIZE = 16
LEARNING_RATE = 0.001
EARLY_STOPPING_PATIENCE = 20
VALIDATION_SPLIT = 0.15

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "model_dataset_with_holidays.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "lstm_baseline"
METRICS_PATH = OUTPUT_DIR / "metrics.csv"
PREDICTIONS_PATH = OUTPUT_DIR / "predictions.csv"
HISTORY_PATH = OUTPUT_DIR / "training_history.csv"
MODEL_SUMMARY_PATH = OUTPUT_DIR / "model_summary.txt"
CONFIG_PATH = OUTPUT_DIR / "config.json"

TARGET_COL = "crowd_index"
DROP_COLS = ["date", "crowd_index", "crowd_level"]


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
    try:
        tf.keras.utils.set_random_seed(seed)
    except AttributeError:
        pass


def load_and_prepare_data(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, parse_dates=["date"])
    data = data.sort_values("date").reset_index(drop=True)

    for col in data.columns:
        if data[col].dtype == bool:
            data[col] = data[col].astype(int)

    feature_cols = [c for c in data.columns if c not in DROP_COLS]
    for col in feature_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data[feature_cols] = data[feature_cols].fillna(data[feature_cols].median(numeric_only=True))
    return data


def build_features_target(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = data.drop(columns=DROP_COLS, errors="ignore").copy()
    y = pd.to_numeric(data[TARGET_COL], errors="coerce").copy()
    return X, y


def chronological_split_index(n_rows: int, test_size: float) -> int:
    return int(n_rows * (1 - test_size))


def build_sequences(
    X_scaled: np.ndarray,
    y: np.ndarray,
    dates: np.ndarray,
    lookback: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sequences: list[np.ndarray] = []
    targets: list[float] = []
    target_dates: list[np.datetime64] = []

    for end_idx in range(lookback - 1, len(X_scaled)):
        start_idx = end_idx - lookback + 1
        sequences.append(X_scaled[start_idx : end_idx + 1])
        targets.append(y[end_idx])
        target_dates.append(dates[end_idx])

    return np.asarray(sequences, dtype=np.float32), np.asarray(targets, dtype=np.float32), np.asarray(target_dates)


def build_model(input_shape: tuple[int, int]) -> keras.Model:
    model = keras.Sequential(
        [
            keras.layers.Input(shape=input_shape),
            keras.layers.LSTM(32, dropout=0.1, recurrent_dropout=0.0),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dense(1),
        ]
    )
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="mse",
        metrics=[keras.metrics.MeanAbsoluteError(name="mae")],
    )
    return model


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return rmse, mae, r2


def main() -> None:
    set_global_seed(RANDOM_STATE)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = load_and_prepare_data(INPUT_PATH)
    X_df, y_series = build_features_target(data)
    dates = data["date"].to_numpy()

    split_idx = chronological_split_index(len(data), TEST_SIZE)

    scaler = StandardScaler()
    scaler.fit(X_df.iloc[:split_idx])
    X_scaled = scaler.transform(X_df)

    X_seq, y_seq, seq_dates = build_sequences(
        X_scaled,
        y_series.to_numpy(dtype=np.float32),
        dates,
        LOOKBACK_WEEKS,
    )

    train_cutoff_date = dates[split_idx]
    train_mask = seq_dates < train_cutoff_date
    test_mask = ~train_mask

    X_train = X_seq[train_mask]
    y_train = y_seq[train_mask]
    dates_train = seq_dates[train_mask]

    X_test = X_seq[test_mask]
    y_test = y_seq[test_mask]
    dates_test = seq_dates[test_mask]

    if len(X_train) == 0 or len(X_test) == 0:
        raise ValueError("Sequence split produced empty train or test data; check lookback/test size.")

    model = build_model((X_train.shape[1], X_train.shape[2]))
    early_stopping = keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=EARLY_STOPPING_PATIENCE,
        restore_best_weights=True,
    )

    history = model.fit(
        X_train,
        y_train,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_split=VALIDATION_SPLIT,
        verbose=0,
        callbacks=[early_stopping],
        shuffle=False,
    )

    train_pred = model.predict(X_train, verbose=0).reshape(-1)
    test_pred = model.predict(X_test, verbose=0).reshape(-1)
    full_pred = model.predict(X_seq, verbose=0).reshape(-1)

    rmse_train, mae_train, r2_train = evaluate_predictions(y_train, train_pred)
    rmse_test, mae_test, r2_test = evaluate_predictions(y_test, test_pred)

    metrics_df = pd.DataFrame(
        [
            {
                "model": "LSTM",
                "rmse_train": rmse_train,
                "rmse_test": rmse_test,
                "mae_train": mae_train,
                "mae_test": mae_test,
                "r2_train": r2_train,
                "r2_test": r2_test,
                "split": "chronological_sequence",
                "test_size": TEST_SIZE,
                "lookback_weeks": LOOKBACK_WEEKS,
                "epochs_requested": EPOCHS,
                "epochs_trained": len(history.history["loss"]),
                "batch_size": BATCH_SIZE,
                "learning_rate": LEARNING_RATE,
                "validation_split": VALIDATION_SPLIT,
                "random_state": RANDOM_STATE,
            }
        ]
    )

    pred_df = pd.DataFrame(
        {
            "date": pd.to_datetime(seq_dates),
            "actual_crowd_index": y_seq,
            "predicted_crowd_index_lstm": full_pred,
            "split": np.where(test_mask, "test", "train"),
        }
    )

    history_df = pd.DataFrame(history.history)

    summary_lines: list[str] = []
    model.summary(print_fn=summary_lines.append)

    config = {
        "input_path": str(INPUT_PATH),
        "feature_columns": X_df.columns.tolist(),
        "target_column": TARGET_COL,
        "lookback_weeks": LOOKBACK_WEEKS,
        "test_size": TEST_SIZE,
        "epochs": EPOCHS,
        "epochs_trained": len(history.history["loss"]),
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "validation_split": VALIDATION_SPLIT,
        "random_state": RANDOM_STATE,
        "train_sequence_rows": int(len(X_train)),
        "test_sequence_rows": int(len(X_test)),
        "train_date_min": str(pd.to_datetime(dates_train).min()),
        "train_date_max": str(pd.to_datetime(dates_train).max()),
        "test_date_min": str(pd.to_datetime(dates_test).min()),
        "test_date_max": str(pd.to_datetime(dates_test).max()),
    }

    metrics_df.to_csv(METRICS_PATH, index=False)
    pred_df.to_csv(PREDICTIONS_PATH, index=False)
    history_df.to_csv(HISTORY_PATH, index=False)
    MODEL_SUMMARY_PATH.write_text("\n".join(summary_lines))
    CONFIG_PATH.write_text(json.dumps(config, indent=2))

    print(f"Loaded dataset: {INPUT_PATH}")
    print(f"Rows: {len(data)}, Features used: {X_df.shape[1]}")
    print(f"Sequence lookback: {LOOKBACK_WEEKS} weeks")
    print(f"Train sequences: {X_train.shape}, Test sequences: {X_test.shape}")

    print("\n=== Performance Metrics ===")
    print(metrics_df.to_string(index=False))

    print("\n=== Model Summary ===")
    print("\n".join(summary_lines))

    print(f"\nSaved metrics to: {METRICS_PATH}")
    print(f"Saved date-aligned predictions to: {PREDICTIONS_PATH}")
    print(f"Saved training history to: {HISTORY_PATH}")
    print(f"Saved model summary to: {MODEL_SUMMARY_PATH}")
    print(f"Saved config to: {CONFIG_PATH}")


if __name__ == "__main__":
    main()
