from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .eta_experiment import metrics


def run(dataset: Path, predictions: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    train = pd.read_parquet(dataset / "train.parquet", columns=["city", "aoi_id"])
    test_features = pd.read_parquet(
        dataset / "test.parquet",
        columns=["sample_id", "query_id", "city", "aoi_id", "pending_count", "direct_distance_km", "query_hour"],
    )
    frame = test_features.merge(pd.read_parquet(predictions), on=["sample_id", "query_id", "city"], validate="one_to_one")
    seen_aoi = set(zip(train["city"], train["aoi_id"]))
    frame["aoi_seen"] = [pair in seen_aoi for pair in zip(frame["city"], frame["aoi_id"])]
    frame["pending_band"] = pd.cut(frame["pending_count"], [0, 5, 10, 25], labels=["1-5", "6-10", "11-25"])
    frame["distance_band"] = pd.cut(
        frame["direct_distance_km"], [-np.inf, 0.5, 1.0, 3.0, np.inf], labels=["<=0.5", "0.5-1", "1-3", ">3"]
    )
    frame["hour_band"] = pd.cut(frame["query_hour"], [-1, 9, 12, 15, 18, 24], labels=["0-9", "10-12", "13-15", "16-18", "19-23"])
    frame["eta_band"] = pd.cut(
        frame["eta_minutes"],
        [0, 120, 480, 1440, np.inf],
        labels=["<=2h", "2-8h", "8-24h", ">24h"],
        include_lowest=True,
    )
    model_columns = ["historical_median", "lightgbm", "mlp"]
    if "selected_prediction" in frame.columns:
        model_columns.append("selected_prediction")
    rows = []
    dimensions = ["city", "aoi_seen", "pending_band", "distance_band", "hour_band", "eta_band"]
    for dimension in dimensions:
        for group, subset in frame.groupby(dimension, observed=True):
            for model in model_columns:
                rows.append({"dimension": dimension, "group": str(group), "model": model, **metrics(subset["eta_minutes"], subset[model])})
    result = pd.DataFrame(rows)
    result.to_csv(output / "eta_slices.csv", index=False)
    payload = {
        "rows": len(frame),
        "aoi_unseen_rows": int((~frame["aoi_seen"]).sum()),
        "aoi_unseen_ratio": float((~frame["aoi_seen"]).mean()),
        "dimensions": dimensions,
        "models": model_columns,
    }
    (output / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.predictions, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
