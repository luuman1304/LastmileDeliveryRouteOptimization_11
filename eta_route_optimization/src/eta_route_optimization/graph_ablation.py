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
from .statistical_analysis import bootstrap_mean_ci

GRAPH_FEATURES = [
    "edge_history_log_count",
    "destination_history_log_count",
    "edge_history_median_eta",
    "edge_seen",
]


def fit_statistics(train: pd.DataFrame) -> dict:
    edge = (
        train.groupby(["city", "query_aoi_id", "aoi_id"], observed=True)[TARGET]
        .agg(edge_history_median_eta="median", edge_history_count="size")
        .reset_index()
    )
    destination = (
        train.groupby(["city", "aoi_id"], observed=True)[TARGET]
        .agg(destination_history_median_eta="median", destination_history_count="size")
        .reset_index()
    )
    city = train.groupby("city", observed=True)[TARGET].median().to_dict()
    return {"edge": edge, "destination": destination, "city": city, "global": float(train[TARGET].median())}


def apply_statistics(frame: pd.DataFrame, statistics: dict) -> pd.DataFrame:
    result = frame.merge(
        statistics["edge"], on=["city", "query_aoi_id", "aoi_id"], how="left", validate="many_to_one"
    ).merge(
        statistics["destination"], on=["city", "aoi_id"], how="left", validate="many_to_one"
    )
    result["edge_seen"] = result["edge_history_count"].notna().astype("int8")
    result["edge_history_log_count"] = np.log1p(result["edge_history_count"].fillna(0))
    result["destination_history_log_count"] = np.log1p(result["destination_history_count"].fillna(0))
    fallback = result["city"].map(statistics["city"]).fillna(statistics["global"])
    result["edge_history_median_eta"] = (
        result["edge_history_median_eta"]
        .fillna(result["destination_history_median_eta"])
        .fillna(fallback)
    )
    return result


def paired_comparison(frame: pd.DataFrame, graph_prediction: np.ndarray, base_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, list[float]]:
    base = pd.read_parquet(base_path)[["sample_id", "selected_prediction"]]
    compare = frame[["sample_id", "query_id", "city", TARGET]].copy()
    compare["graph_lightgbm"] = graph_prediction
    compare = compare.merge(base, on="sample_id", how="left", validate="one_to_one")
    if compare["selected_prediction"].isna().any():
        raise RuntimeError("base predictions are incomplete")
    compare["base_abs_error"] = (compare["selected_prediction"] - compare[TARGET]).abs()
    compare["graph_abs_error"] = (compare["graph_lightgbm"] - compare[TARGET]).abs()
    query = compare.groupby(["query_id", "city"], as_index=False)[
        ["base_abs_error", "graph_abs_error"]
    ].mean()
    query["delta_graph_minus_base"] = query["graph_abs_error"] - query["base_abs_error"]
    delta = query["delta_graph_minus_base"].to_numpy()
    return compare, query, delta, bootstrap_mean_ci(delta)


def run(
    dataset: Path,
    base_validation_predictions: Path,
    base_test_predictions: Path,
    output: Path,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    train = add_features(pd.read_parquet(dataset / "train.parquet"))
    validation = add_features(pd.read_parquet(dataset / "validation.parquet"))
    test = add_features(pd.read_parquet(dataset / "test.parquet"))
    set_training_categories(train, validation, test)
    statistics = fit_statistics(train)
    train = apply_statistics(train, statistics)
    validation = apply_statistics(validation, statistics)
    test = apply_statistics(test, statistics)
    features = NUMERIC + CATEGORICAL + GRAPH_FEATURES
    predictions = {"validation": [], "test": []}
    seed_metrics = {"validation": [], "test": []}
    for seed in SEEDS:
        model = lightgbm(seed)
        model.fit(
            train[features],
            train[TARGET],
            categorical_feature=CATEGORICAL,
            eval_X=validation[features],
            eval_y=validation[TARGET],
            callbacks=[early_stopping(150, verbose=False), log_evaluation(0)],
        )
        for split, frame in {"validation": validation, "test": test}.items():
            predicted = model.predict(frame[features])
            predictions[split].append(predicted)
            seed_metrics[split].append({"seed": seed, **metrics(frame[TARGET].to_numpy(), predicted)})
    graph_predictions = {split: np.mean(values, axis=0) for split, values in predictions.items()}
    validation_compare, validation_query, validation_delta, validation_ci = paired_comparison(
        validation, graph_predictions["validation"], base_validation_predictions
    )
    test_compare, test_query, test_delta, test_ci = paired_comparison(
        test, graph_predictions["test"], base_test_predictions
    )
    if validation_ci[1] < 0:
        decision = "relational_features_improve_eta_but_full_gnn_still_requires_cost_benefit_gate"
    else:
        decision = "no_stable_eta_gain_from_relational_features_do_not_implement_gnn"
    validation_compare.to_parquet(output / "validation_predictions.parquet", index=False)
    validation_query.to_parquet(output / "validation_paired_query_errors.parquet", index=False)
    test_compare.to_parquet(output / "test_predictions.parquet", index=False)
    test_query.to_parquet(output / "test_paired_query_errors.parquet", index=False)
    payload = {
        "features": GRAPH_FEATURES,
        "training_only_statistics": True,
        "decision_split": "validation",
        "test_metrics_used_for_decision": False,
        "edge_seen_rate_validation": float(validation["edge_seen"].mean()),
        "edge_seen_rate_test": float(test["edge_seen"].mean()),
        "validation_seed_metrics": seed_metrics["validation"],
        "test_seed_metrics": seed_metrics["test"],
        "validation_ensemble_metrics": metrics(
            validation[TARGET].to_numpy(), graph_predictions["validation"]
        ),
        "test_ensemble_metrics": metrics(test[TARGET].to_numpy(), graph_predictions["test"]),
        "validation_paired_query_mean_delta": float(validation_delta.mean()),
        "validation_bootstrap_ci95": validation_ci,
        "test_confirmation_paired_query_mean_delta": float(test_delta.mean()),
        "test_confirmation_bootstrap_ci95": test_ci,
        "decision": decision,
        "note": "This is a graph-feature ablation, not a GNN result.",
    }
    (output / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--base-validation-predictions", required=True, type=Path)
    parser.add_argument("--base-test-predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.dataset,
                args.base_validation_predictions,
                args.base_test_predictions,
                args.output,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
