from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import early_stopping, log_evaluation

from .eta_experiment import (
    CATEGORICAL,
    NUMERIC,
    SEEDS,
    TARGET,
    add_features,
    lightgbm,
    metrics,
    set_training_categories,
)


def describe_split(frame: pd.DataFrame) -> dict:
    bins = pd.cut(
        frame[TARGET],
        [0, 20, 40, 60, 80, 100, 120, 480, 1440, np.inf],
        labels=["<=20", "20-40", "40-60", "60-80", "80-100", "100-120", "2-8h", "8-24h", ">24h"],
        include_lowest=True,
    )
    return {
        "rows": len(frame),
        "queries": int(frame["query_id"].nunique()),
        "city_rows": {str(k): int(v) for k, v in frame["city"].value_counts().sort_index().items()},
        "eta_bins": {str(k): int(v) for k, v in bins.value_counts(sort=False).items()},
        "eta_mean": float(frame[TARGET].mean()),
        "eta_median": float(frame[TARGET].median()),
    }


def scoped_metrics(frame: pd.DataFrame, prediction: np.ndarray) -> dict:
    city = {
        str(name): metrics(group[TARGET].to_numpy(), prediction[group.index.to_numpy()])
        for name, group in frame.reset_index(drop=True).groupby("city", observed=True)
    }
    return {
        "overall": metrics(frame[TARGET].to_numpy(), prediction),
        "by_city": city,
        "macro_city_mae": float(np.mean([value["mae_minutes"] for value in city.values()])),
    }


def run(dataset: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    frames = {
        split: add_features(pd.read_parquet(dataset / f"{split}.parquet")).reset_index(drop=True)
        for split in ["train", "validation", "test"]
    }
    set_training_categories(frames["train"], frames["validation"], frames["test"])
    features = NUMERIC + CATEGORICAL
    predictions = {split: [] for split in frames}
    best_iterations = {}
    for seed in SEEDS:
        model = lightgbm(seed)
        model.fit(
            frames["train"][features],
            frames["train"][TARGET],
            categorical_feature=CATEGORICAL,
            eval_X=frames["validation"][features],
            eval_y=frames["validation"][TARGET],
            callbacks=[early_stopping(150, verbose=False), log_evaluation(0)],
        )
        best_iterations[str(seed)] = int(model.best_iteration_)
        for split, frame in frames.items():
            predictions[split].append(model.predict(frame[features]))
    ensemble = {split: np.mean(values, axis=0) for split, values in predictions.items()}
    evaluation = {split: scoped_metrics(frames[split], ensemble[split]) for split in frames}
    train_mae = evaluation["train"]["overall"]["mae_minutes"]
    validation_mae = evaluation["validation"]["overall"]["mae_minutes"]
    test_mae = evaluation["test"]["overall"]["mae_minutes"]
    payload = {
        "model": "lightgbm_ensemble_5_seeds",
        "best_iterations": best_iterations,
        "data_distribution": {split: describe_split(frame) for split, frame in frames.items()},
        "evaluation": evaluation,
        "mae_gaps": {
            "validation_minus_train": validation_mae - train_mae,
            "test_minus_validation": test_mae - validation_mae,
            "test_minus_train": test_mae - train_mae,
        },
        "interpretation_rule": (
            "A train gap alone is not proof of overfitting. Inspect validation stopping, seed stability, "
            "city slices and temporal test degradation together."
        ),
    }
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
