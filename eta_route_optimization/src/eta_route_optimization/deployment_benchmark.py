from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import early_stopping, log_evaluation

from .eta_experiment import (
    CATEGORICAL,
    NUMERIC,
    TARGET,
    add_features,
    lightgbm,
    set_training_categories,
)

DRIFT_FEATURES = ["query_minute_of_day", "waiting_minutes", "direct_distance_km", "pending_count"]


def psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    clean_reference = reference.replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    clean_current = current.replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    edges = np.unique(np.quantile(clean_reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    expected = np.histogram(clean_reference, bins=edges)[0] / len(clean_reference)
    actual = np.histogram(clean_current, bins=edges)[0] / len(clean_current)
    expected = np.clip(expected, 1e-6, None)
    actual = np.clip(actual, 1e-6, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def run(dataset: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    train = add_features(pd.read_parquet(dataset / "train.parquet")).reset_index(drop=True)
    validation = add_features(pd.read_parquet(dataset / "validation.parquet")).reset_index(drop=True)
    test = add_features(pd.read_parquet(dataset / "test.parquet")).reset_index(drop=True)
    set_training_categories(train, validation, test)
    features = NUMERIC + CATEGORICAL
    model = lightgbm(17)
    started = time.perf_counter()
    model.fit(
        train[features],
        train[TARGET],
        categorical_feature=CATEGORICAL,
        eval_X=validation[features],
        eval_y=validation[TARGET],
        callbacks=[early_stopping(150, verbose=False), log_evaluation(0)],
    )
    training_seconds = time.perf_counter() - started
    model_path = output / "lightgbm_seed17.txt"
    model.booster_.save_model(model_path)

    latency = {}
    rng = np.random.default_rng(17)
    for batch_size in [1, 32, 256, 4096]:
        indices = rng.choice(len(test), size=batch_size, replace=False)
        batch = test.iloc[indices][features]
        model.predict(batch)
        timings = []
        for _ in range(20):
            tick = time.perf_counter()
            prediction = model.predict(batch)
            timings.append(time.perf_counter() - tick)
        if not np.isfinite(prediction).all():
            raise RuntimeError("non-finite deployment benchmark prediction")
        latency[str(batch_size)] = {
            "median_batch_milliseconds": float(np.median(timings) * 1000),
            "p95_batch_milliseconds": float(np.quantile(timings, 0.95) * 1000),
            "median_per_row_milliseconds": float(np.median(timings) * 1000 / batch_size),
        }

    drift = {feature: psi(train[feature], test[feature]) for feature in DRIFT_FEATURES}
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_unit = "bytes" if platform.system() == "Darwin" else "kilobytes"
    payload = {
        "model": "lightgbm_seed17_runtime_proxy_for_ensemble",
        "training_seconds": training_seconds,
        "best_iteration": int(model.best_iteration_),
        "model_file_bytes": model_path.stat().st_size,
        "process_max_rss": int(rss),
        "process_max_rss_unit": rss_unit,
        "latency": latency,
        "drift_psi_train_vs_october_test": drift,
        "drift_thresholds": {"monitor": 0.1, "investigate_or_retrain": 0.25},
        "fallback_policy": {
            "schema_or_coordinate_failure": "reject_and_route_to_manual_planning",
            "unseen_city": "do_not_auto_dispatch; use historical_global_median_and_flag",
            "non_finite_prediction": "replace_with_training_global_median_and_log",
            "routing_solver_failure": "nearest_neighbor_plus_directed_2opt",
        },
        "limitations": [
            "Latency is local batch inference, not end-to-end service latency.",
            "RSS includes Python and loaded data, not only the model.",
            "A five-model ensemble is expected to cost approximately five single-model predictions if not parallelized.",
        ],
    }
    if any(not math.isfinite(value) for value in drift.values()):
        raise RuntimeError("non-finite PSI")
    (output / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
