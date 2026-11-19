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
    TARGET,
    add_features,
    lightgbm,
    metrics,
    set_training_categories,
)

FOLDS = [
    {"name": "july", "fit_before": 624, "inner_start": 624, "eval_start": 701, "eval_end": 731},
    {"name": "august", "fit_before": 725, "inner_start": 725, "eval_start": 801, "eval_end": 831},
    {"name": "september", "fit_before": 825, "inner_start": 825, "eval_start": 901, "eval_end": 930},
]


def macro_city_mae(frame: pd.DataFrame, prediction: np.ndarray) -> tuple[float, dict]:
    results = {}
    for city, indices in frame.groupby("city", observed=True).groups.items():
        results[str(city)] = metrics(frame.loc[indices, TARGET].to_numpy(), prediction[indices])
    return float(np.mean([value["mae_minutes"] for value in results.values()])), results


def run(
    dataset: Path,
    output: Path,
    only_fold: str | None = None,
    only_candidate: str | None = None,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    data = pd.concat(
        [pd.read_parquet(dataset / f"{split}.parquet") for split in ["train", "validation"]],
        ignore_index=True,
    )
    data = add_features(data).reset_index(drop=True)
    features = NUMERIC + CATEGORICAL
    rows = []
    selected_folds = [fold for fold in FOLDS if only_fold is None or fold["name"] == only_fold]
    if not selected_folds:
        raise ValueError(f"unknown fold: {only_fold}")
    for fold in selected_folds:
        fit = data[data["route_day"] < fold["fit_before"]].reset_index(drop=True)
        inner = data[
            (data["route_day"] >= fold["inner_start"])
            & (data["route_day"] < fold["eval_start"])
        ].reset_index(drop=True)
        evaluation = data[
            (data["route_day"] >= fold["eval_start"])
            & (data["route_day"] <= fold["eval_end"])
        ].reset_index(drop=True)
        if min(len(fit), len(inner), len(evaluation)) == 0:
            raise RuntimeError(f"empty rolling-origin partition: {fold['name']}")
        set_training_categories(fit, inner, evaluation)
        counts = fit["city"].value_counts()
        weights = fit["city"].map(1.0 / counts).astype(float)
        weights *= len(weights) / weights.sum()
        candidates = [("unweighted", None), ("city_balanced", weights)]
        for candidate, sample_weight in candidates:
            if only_candidate is not None and candidate != only_candidate:
                continue
            model = lightgbm(17)
            model.set_params(n_estimators=15_000)
            model.fit(
                fit[features],
                fit[TARGET],
                sample_weight=sample_weight,
                categorical_feature=CATEGORICAL,
                eval_X=inner[features],
                eval_y=inner[TARGET],
                callbacks=[early_stopping(150, verbose=False), log_evaluation(0)],
            )
            prediction = model.predict(evaluation[features])
            macro, by_city = macro_city_mae(evaluation, prediction)
            rows.append(
                {
                    "fold": fold["name"],
                    "candidate": candidate,
                    "fit_rows": len(fit),
                    "inner_validation_rows": len(inner),
                    "evaluation_rows": len(evaluation),
                    "best_iteration": int(model.best_iteration_),
                    "micro": metrics(evaluation[TARGET].to_numpy(), prediction),
                    "macro_city_mae": macro,
                    "by_city": by_city,
                }
            )
    if (only_fold is not None or only_candidate is not None) and (output / "summary.json").exists():
        previous = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        rows = [
            row
            for row in previous["folds"]
            if not (
                (only_fold is None or row["fold"] == only_fold)
                and (only_candidate is None or row["candidate"] == only_candidate)
            )
        ] + rows
    frame = pd.DataFrame(
        {
            "fold": [row["fold"] for row in rows],
            "candidate": [row["candidate"] for row in rows],
            "macro_city_mae": [row["macro_city_mae"] for row in rows],
            "micro_mae": [row["micro"]["mae_minutes"] for row in rows],
        }
    )
    aggregate = (
        frame.groupby("candidate")[["macro_city_mae", "micro_mae"]]
        .agg(["mean", "std"])
    )
    payload = {
        "test_october_used": False,
        "seed": 17,
        "folds": rows,
        "aggregate": {
            str(candidate): {
                f"{metric}_{stat}": float(value)
                for (metric, stat), value in values.items()
            }
            for candidate, values in aggregate.iterrows()
        },
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
    parser.add_argument("--only-fold", choices=[fold["name"] for fold in FOLDS])
    parser.add_argument("--only-candidate", choices=["unweighted", "city_balanced"])
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.dataset, args.output, args.only_fold, args.only_candidate),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
