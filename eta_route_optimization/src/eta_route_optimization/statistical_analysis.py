from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest


def bootstrap_mean_ci(values: np.ndarray, seed: int = 20261116, replicates: int = 5000) -> list[float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.empty(replicates)
    batch = 100
    for start in range(0, replicates, batch):
        count = min(batch, replicates - start)
        indices = rng.integers(0, len(values), size=(count, len(values)))
        means[start : start + count] = values[indices].mean(axis=1)
    return [float(value) for value in np.quantile(means, [0.025, 0.975])]


def cluster_bootstrap_mean_ci(
    frame: pd.DataFrame,
    value_column: str,
    cluster_columns: list[str],
    seed: int = 20261117,
    replicates: int = 20_000,
) -> list[float]:
    """Bootstrap complete courier clusters while retaining query weighting."""

    clusters = frame.groupby(cluster_columns, observed=True)[value_column].agg(["sum", "count"])
    sums = clusters["sum"].to_numpy(dtype=float)
    counts = clusters["count"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    result = np.empty(replicates)
    for start in range(0, replicates, 100):
        size = min(100, replicates - start)
        indices = rng.integers(0, len(clusters), size=(size, len(clusters)))
        result[start : start + size] = sums[indices].sum(axis=1) / counts[indices].sum(axis=1)
    return [float(value) for value in np.quantile(result, [0.025, 0.975])]


def run(predictions: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(predictions)
    frame["abs_error_historical"] = (frame["historical_median"] - frame["eta_minutes"]).abs()
    if "selected_prediction" not in frame:
        raise RuntimeError("predictions must contain the validation-selected model")
    frame["abs_error_selected"] = (frame["selected_prediction"] - frame["eta_minutes"]).abs()
    query = (
        frame.groupby(["query_id", "city", "courier_id"], as_index=False)[
            ["abs_error_historical", "abs_error_selected"]
        ]
        .mean()
    )
    query["delta_mae_selected_minus_historical"] = (
        query["abs_error_selected"] - query["abs_error_historical"]
    )
    delta_column = "delta_mae_selected_minus_historical"
    delta = query[delta_column].to_numpy()
    courier = query.groupby(["city", "courier_id"], observed=True)[delta_column].mean()
    nonzero_courier = courier[courier != 0].to_numpy()
    sign = binomtest(
        int(np.sum(nonzero_courier < 0)),
        len(nonzero_courier),
        0.5,
        alternative="two-sided",
    )
    leave_city = []
    for city in sorted(query["city"].unique()):
        kept = query[query["city"] != city][delta_column].to_numpy()
        leave_city.append({"left_out_city": city, "mean_delta": float(kept.mean()), "queries": len(kept)})
    payload = {
        "unit": "query_id",
        "primary_uncertainty_unit": "city_courier_id_cluster",
        "queries": len(query),
        "courier_clusters": len(courier),
        "mean_delta_mae_selected_minus_historical": float(delta.mean()),
        "relative_mae_change": float(delta.mean() / query["abs_error_historical"].mean()),
        "courier_cluster_bootstrap_ci95": cluster_bootstrap_mean_ci(
            query, delta_column, ["city", "courier_id"]
        ),
        "query_bootstrap_ci95_sensitivity": bootstrap_mean_ci(delta),
        "queries_selected_better": int(np.sum(delta < 0)),
        "queries_historical_better": int(np.sum(delta > 0)),
        "couriers_selected_better": int(np.sum(nonzero_courier < 0)),
        "couriers_historical_better": int(np.sum(nonzero_courier > 0)),
        "courier_exact_sign_test_two_sided_p": float(sign.pvalue),
        "leave_one_city_out": leave_city,
    }
    query.to_parquet(output / "paired_query_errors.parquet", index=False)
    (output / "eta_paired_inference.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.predictions, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
