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


def evaluate(frame: pd.DataFrame, prediction: np.ndarray) -> dict:
    by_city = {}
    for city, indices in frame.groupby("city", observed=True).groups.items():
        by_city[str(city)] = metrics(frame.loc[indices, TARGET].to_numpy(), prediction[indices])
    return {
        "micro": metrics(frame[TARGET].to_numpy(), prediction),
        "macro_city_mae": float(np.mean([result["mae_minutes"] for result in by_city.values()])),
        "by_city": by_city,
    }


def fit_ensemble(train, validation, test, weighted: bool) -> tuple[dict, dict[str, np.ndarray]]:
    features = NUMERIC + CATEGORICAL
    counts = train["city"].value_counts()
    sample_weight = train["city"].map(1.0 / counts).astype(float)
    sample_weight *= len(sample_weight) / sample_weight.sum()
    predictions = {"validation": [], "test": []}
    iterations = {}
    for seed in SEEDS:
        model = lightgbm(seed)
        model.fit(
            train[features],
            train[TARGET],
            sample_weight=sample_weight if weighted else None,
            categorical_feature=CATEGORICAL,
            eval_X=validation[features],
            eval_y=validation[TARGET],
            callbacks=[early_stopping(150, verbose=False), log_evaluation(0)],
        )
        iterations[str(seed)] = int(model.best_iteration_)
        predictions["validation"].append(model.predict(validation[features]))
        predictions["test"].append(model.predict(test[features]))
    ensemble = {split: np.mean(values, axis=0) for split, values in predictions.items()}
    return {
        "weighting": "inverse_city_frequency_normalized" if weighted else "none",
        "best_iterations": iterations,
        "validation": evaluate(validation, ensemble["validation"]),
        "test": evaluate(test, ensemble["test"]),
    }, ensemble


def load_base_prediction(frame: pd.DataFrame, path: Path) -> np.ndarray:
    base = pd.read_parquet(path, columns=["sample_id", "selected_prediction"])
    aligned = frame[["sample_id"]].merge(base, on="sample_id", how="left", validate="one_to_one")
    if aligned["selected_prediction"].isna().any():
        raise RuntimeError(f"incomplete base predictions: {path}")
    return aligned["selected_prediction"].to_numpy()


def run(
    dataset: Path,
    output: Path,
    base_validation_predictions: Path,
    base_test_predictions: Path,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    train = add_features(pd.read_parquet(dataset / "train.parquet")).reset_index(drop=True)
    validation = add_features(pd.read_parquet(dataset / "validation.parquet")).reset_index(drop=True)
    test = add_features(pd.read_parquet(dataset / "test.parquet")).reset_index(drop=True)
    set_training_categories(train, validation, test)

    unweighted_predictions = {
        "validation": load_base_prediction(validation, base_validation_predictions),
        "test": load_base_prediction(test, base_test_predictions),
    }
    selection = json.loads((base_test_predictions.parent / "model_selection.json").read_text())
    unweighted = {
        "weighting": "none",
        "best_iterations": selection["lightgbm_best_iterations"],
        "validation": evaluate(validation, unweighted_predictions["validation"]),
        "test": evaluate(test, unweighted_predictions["test"]),
        "reused_frozen_baseline_predictions": True,
    }
    weighted, weighted_predictions = fit_ensemble(train, validation, test, True)
    candidates = {"unweighted": unweighted, "city_balanced": weighted}
    selected = min(candidates, key=lambda name: candidates[name]["validation"]["macro_city_mae"])
    selected_predictions = {
        "unweighted": unweighted_predictions,
        "city_balanced": weighted_predictions,
    }[selected]
    prediction_frame = test[["sample_id", "query_id", "city", TARGET]].copy()
    prediction_frame["prediction"] = selected_predictions["test"]
    prediction_frame.to_parquet(output / "selected_test_predictions.parquet", index=False)
    payload = {
        "selection_metric": "validation_macro_city_mae",
        "selection_performed_without_test_metric": True,
        "selected": selected,
        "candidates": candidates,
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
    parser.add_argument("--base-validation-predictions", required=True, type=Path)
    parser.add_argument("--base-test-predictions", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.dataset,
                args.output,
                args.base_validation_predictions,
                args.base_test_predictions,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
