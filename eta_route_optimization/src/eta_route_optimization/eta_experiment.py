from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor, early_stopping, log_evaluation
from sklearn.compose import ColumnTransformer
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEEDS = [17, 29, 43, 71, 101]
NUMERIC = [
    "query_hour_sin",
    "query_hour_cos",
    "query_day_sin",
    "query_day_cos",
    "query_month",
    "query_minute_of_day",
    "waiting_minutes",
    "direct_distance_km",
    "same_aoi",
    "same_region",
    "pending_count",
    "pending_count_before_cap",
    "accept_rank",
    "query_lng",
    "query_lat",
    "lng",
    "lat",
]
CATEGORICAL = ["city", "aoi_type"]
TARGET = "eta_minutes"


def json_records(frame: pd.DataFrame) -> list[dict]:
    """Return strict-JSON records, representing missing values as null."""
    return json.loads(frame.to_json(orient="records"))


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    hour_angle = 2 * math.pi * frame["query_minute_of_day"] / 1440
    day_angle = 2 * math.pi * frame["query_day_of_week"] / 7
    frame["query_hour_sin"] = np.sin(hour_angle)
    frame["query_hour_cos"] = np.cos(hour_angle)
    frame["query_day_sin"] = np.sin(day_angle)
    frame["query_day_cos"] = np.cos(day_angle)
    return frame


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    predicted = np.clip(np.asarray(predicted, dtype=float), 0, None)
    actual = np.asarray(actual, dtype=float)
    error = predicted - actual
    return {
        "mae_minutes": float(np.mean(np.abs(error))),
        "rmse_minutes": float(np.sqrt(np.mean(error**2))),
        "median_absolute_error": float(np.median(np.abs(error))),
        "acc_at_20": float(np.mean(np.abs(error) <= 20)),
        "n": len(actual),
    }


def append_metric_rows(
    rows: list[dict], model: str, seed: int | None, split: str, frame: pd.DataFrame, prediction
) -> None:
    predicted = np.asarray(prediction)
    scopes = [("overall", "all", np.ones(len(frame), dtype=bool))]
    scopes.extend(("city", city, frame["city"].eq(city).to_numpy()) for city in sorted(frame["city"].unique()))
    if "courier_seen" in frame:
        scopes.extend(
            ("courier_status", str(value), frame["courier_seen"].eq(value).to_numpy())
            for value in [False, True]
            if frame["courier_seen"].eq(value).any()
        )
    for scope, group, mask in scopes:
        result = metrics(frame.loc[mask, TARGET].to_numpy(), predicted[mask])
        rows.append(
            {"model": model, "seed": seed, "split": split, "scope": scope, "group": group, **result}
        )


def query_mae(frame: pd.DataFrame, prediction: np.ndarray) -> float:
    work = frame[["query_id", TARGET]].copy()
    work["absolute_error"] = np.abs(np.clip(np.asarray(prediction), 0, None) - work[TARGET])
    return float(work.groupby("query_id", observed=True)["absolute_error"].mean().mean())


def set_training_categories(train: pd.DataFrame, *others: pd.DataFrame) -> list[str]:
    """Fit the city vocabulary on training data and map unseen values explicitly."""

    categories = sorted(str(value) for value in train["city"].dropna().unique())
    vocabulary = categories + ["__UNKNOWN__"]
    for frame in (train, *others):
        values = frame["city"].astype("string")
        frame["city"] = pd.Categorical(
            values.where(values.isin(categories), "__UNKNOWN__"), categories=vocabulary
        )
    return vocabulary


def _hash_sample(frame: pd.DataFrame, size: int) -> pd.DataFrame:
    if len(frame) <= size:
        return frame
    hashes = frame["sample_id"].map(
        lambda value: int.from_bytes(hashlib.blake2b(value.encode(), digest_size=8).digest(), "big")
    )
    return frame.loc[hashes.nsmallest(size).index].copy()


class HistoricalMedian:
    def fit(self, frame: pd.DataFrame) -> HistoricalMedian:
        work = frame.copy()
        work["hour_bucket"] = work["query_hour"] // 2
        self.levels = [
            (["city", "aoi_type", "hour_bucket"], work.groupby(["city", "aoi_type", "hour_bucket"])[TARGET].median()),
            (["city", "aoi_type"], work.groupby(["city", "aoi_type"])[TARGET].median()),
            (["city"], work.groupby("city")[TARGET].median()),
        ]
        self.global_median = float(work[TARGET].median())
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        work = frame.copy()
        work["hour_bucket"] = work["query_hour"] // 2
        result = pd.Series(np.nan, index=work.index, dtype=float)
        for keys, mapping in self.levels:
            if len(keys) == 1:
                values = work[keys[0]].map(mapping)
            else:
                index = pd.MultiIndex.from_frame(work[keys])
                values = pd.Series(mapping.reindex(index).to_numpy(), index=work.index)
            result = result.fillna(values)
        return result.fillna(self.global_median).to_numpy()


class EffectiveSpeed:
    """Distance-rate proxy; not physical road speed."""

    def fit(self, frame: pd.DataFrame) -> EffectiveSpeed:
        work = frame[frame["direct_distance_km"] > 0.02].copy()
        work["effective_km_per_min"] = work["direct_distance_km"] / work[TARGET].clip(lower=1)
        work["hour_bucket"] = work["query_hour"] // 2
        self.by_city_hour = work.groupby(["city", "hour_bucket"])["effective_km_per_min"].median()
        self.by_city = work.groupby("city")["effective_km_per_min"].median()
        self.global_rate = float(work["effective_km_per_min"].median())
        self.zero_distance_eta = float(frame.loc[frame["direct_distance_km"] <= 0.02, TARGET].median())
        if not math.isfinite(self.zero_distance_eta):
            self.zero_distance_eta = float(frame[TARGET].median())
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        hour_bucket = frame["query_hour"] // 2
        index = pd.MultiIndex.from_arrays([frame["city"], hour_bucket])
        rate = pd.Series(self.by_city_hour.reindex(index).to_numpy(), index=frame.index)
        rate = rate.fillna(frame["city"].map(self.by_city)).fillna(self.global_rate).clip(lower=1e-4)
        prediction = frame["direct_distance_km"] / rate
        prediction = prediction.where(frame["direct_distance_km"] > 0.02, self.zero_distance_eta)
        return prediction.to_numpy()


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("numeric", StandardScaler(), NUMERIC),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ],
        remainder="drop",
    )


def lightgbm(seed: int) -> LGBMRegressor:
    return LGBMRegressor(
        objective="regression_l1",
        n_estimators=10_000,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=50,
        subsample=0.9,
        subsample_freq=1,
        colsample_bytree=0.9,
        reg_lambda=0.1,
        random_state=seed,
        n_jobs=-1,
        verbosity=-1,
    )


def run(dataset: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    train = add_features(pd.read_parquet(dataset / "train.parquet"))
    validation = add_features(pd.read_parquet(dataset / "validation.parquet"))
    test = add_features(pd.read_parquet(dataset / "test.parquet"))
    set_training_categories(train, validation, test)
    train_couriers = set(zip(train["city"].astype(str), train["courier_id"]))
    for frame in (validation, test):
        frame["courier_seen"] = [
            pair in train_couriers for pair in zip(frame["city"].astype(str), frame["courier_id"])
        ]

    feature_columns = NUMERIC + CATEGORICAL
    frames = {"validation": validation, "test": test}
    prediction_tables = {
        split: frame[
            ["sample_id", "query_id", "city", "courier_id", TARGET, "actual_rank"]
        ].copy()
        for split, frame in frames.items()
    }
    rows: list[dict] = []
    timings: dict[str, float] = {}

    started = time.perf_counter()
    historical = HistoricalMedian().fit(train)
    for split, frame in frames.items():
        prediction_tables[split]["historical_median"] = historical.predict(frame)
        append_metric_rows(
            rows, "historical_median", None, split, frame, prediction_tables[split]["historical_median"]
        )
    timings["historical_median_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    speed = EffectiveSpeed().fit(train)
    for split, frame in frames.items():
        prediction_tables[split]["effective_speed"] = speed.predict(frame)
        append_metric_rows(
            rows, "effective_speed", None, split, frame, prediction_tables[split]["effective_speed"]
        )
    timings["effective_speed_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    knn_train = _hash_sample(train, 50_000)
    knn = make_pipeline(
        preprocessor(), KNeighborsRegressor(n_neighbors=25, weights="distance", n_jobs=-1)
    )
    knn.fit(knn_train[feature_columns], knn_train[TARGET])
    for split, frame in frames.items():
        prediction_tables[split]["knn"] = knn.predict(frame[feature_columns])
        append_metric_rows(rows, "knn", None, split, frame, prediction_tables[split]["knn"])
    timings["knn_seconds"] = time.perf_counter() - started

    lgb_predictions = {split: [] for split in frames}
    lgb_best_iterations: dict[str, int] = {}
    for seed in SEEDS:
        started = time.perf_counter()
        model = lightgbm(seed)
        model.fit(
            train[feature_columns],
            train[TARGET],
            categorical_feature=CATEGORICAL,
            eval_X=validation[feature_columns],
            eval_y=validation[TARGET],
            callbacks=[early_stopping(150, verbose=False), log_evaluation(0)],
        )
        lgb_best_iterations[str(seed)] = int(model.best_iteration_)
        for split, frame in frames.items():
            predicted = model.predict(frame[feature_columns])
            lgb_predictions[split].append(predicted)
            append_metric_rows(rows, "lightgbm", seed, split, frame, predicted)
        timings[f"lightgbm_seed_{seed}_seconds"] = time.perf_counter() - started
    for split, frame in frames.items():
        prediction_tables[split]["lightgbm"] = np.mean(lgb_predictions[split], axis=0)
        append_metric_rows(
            rows, "lightgbm_ensemble", None, split, frame, prediction_tables[split]["lightgbm"]
        )

    mlp_train = _hash_sample(train, 100_000)
    mlp_predictions = {split: [] for split in frames}
    mlp_iterations: dict[str, int] = {}
    for seed in SEEDS:
        started = time.perf_counter()
        model = make_pipeline(
            preprocessor(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                batch_size=512,
                learning_rate_init=0.001,
                max_iter=250,
                early_stopping=True,
                validation_fraction=0.1,
                n_iter_no_change=10,
                random_state=seed,
            ),
        )
        model.fit(mlp_train[feature_columns], mlp_train[TARGET])
        mlp_iterations[str(seed)] = int(model[-1].n_iter_)
        for split, frame in frames.items():
            predicted = model.predict(frame[feature_columns])
            mlp_predictions[split].append(predicted)
            append_metric_rows(rows, "mlp", seed, split, frame, predicted)
        timings[f"mlp_seed_{seed}_seconds"] = time.perf_counter() - started
    for split, frame in frames.items():
        prediction_tables[split]["mlp"] = np.mean(mlp_predictions[split], axis=0)
        append_metric_rows(rows, "mlp_ensemble", None, split, frame, prediction_tables[split]["mlp"])

    candidate_columns = {
        "historical_median": "historical_median",
        "effective_speed": "effective_speed",
        "knn": "knn",
        "lightgbm_ensemble": "lightgbm",
        "mlp_ensemble": "mlp",
    }
    validation_query_mae = {
        model_name: query_mae(validation, prediction_tables["validation"][column].to_numpy())
        for model_name, column in candidate_columns.items()
    }
    selected_model = min(validation_query_mae, key=validation_query_mae.get)
    selected_column = candidate_columns[selected_model]
    for split in frames:
        prediction_tables[split]["selected_prediction"] = prediction_tables[split][selected_column]
        prediction_tables[split]["selected_model"] = selected_model

    # Leave-one-city-out must not include the held city in the fitted vocabulary.
    raw_train = add_features(pd.read_parquet(dataset / "train.parquet"))
    raw_validation = add_features(pd.read_parquet(dataset / "validation.parquet"))
    raw_test = add_features(pd.read_parquet(dataset / "test.parquet"))
    cross_city = []
    for held_city in sorted(raw_test["city"].astype(str).unique()):
        fit = raw_train[raw_train["city"].astype(str) != held_city].copy()
        valid = raw_validation[raw_validation["city"].astype(str) != held_city].copy()
        target = raw_test[raw_test["city"].astype(str) == held_city].copy()
        if len(target) < 100 or len(valid) < 100:
            continue
        set_training_categories(fit, valid, target)
        model = lightgbm(SEEDS[0])
        model.fit(
            fit[feature_columns],
            fit[TARGET],
            categorical_feature=CATEGORICAL,
            eval_X=valid[feature_columns],
            eval_y=valid[TARGET],
            callbacks=[early_stopping(150, verbose=False), log_evaluation(0)],
        )
        result = metrics(target[TARGET].to_numpy(), model.predict(target[feature_columns]))
        cross_city.append({"held_city": held_city, **result})

    result_frame = pd.DataFrame(rows)
    result_frame.to_csv(output / "metrics.csv", index=False)
    prediction_tables["validation"].to_parquet(output / "validation_predictions.parquet", index=False)
    prediction_tables["test"].to_parquet(output / "test_predictions.parquet", index=False)
    pd.DataFrame(cross_city).to_csv(output / "leave_one_city_out.csv", index=False)
    model_selection = {
        "selection_split": "validation",
        "test_metrics_used_for_selection": False,
        "selection_metric": "mean_query_mae_minutes",
        "candidate_validation_query_mae": validation_query_mae,
        "selected_model": selected_model,
        "selected_prediction_column": selected_column,
        "lightgbm_best_iterations": lgb_best_iterations,
        "mlp_iterations": mlp_iterations,
    }
    (output / "model_selection.json").write_text(
        json.dumps(model_selection, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    model_names = list(candidate_columns)
    summary = {
        "protocol": "eta-v2-all-observable-tasks-validation-selection",
        "train_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
        "test_queries": int(test["query_id"].nunique()),
        "test_unseen_courier_rows": int((~test["courier_seen"]).sum()),
        "seeds": SEEDS,
        "model_selection": model_selection,
        "timings": timings,
        "validation_overall_metrics": result_frame[
            (result_frame["split"] == "validation")
            & (result_frame["scope"] == "overall")
            & result_frame["model"].isin(model_names)
        ].pipe(json_records),
        "overall_metrics": result_frame[
            (result_frame["split"] == "test")
            & (result_frame["scope"] == "overall")
            & result_frame["model"].isin(model_names)
        ].pipe(json_records),
        "leave_one_city_out": cross_city,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
