from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .route_metrics import evaluate_order

MODELS = ["historical_median", "effective_speed", "knn", "lightgbm", "mlp", "selected_prediction"]
NOISE_SEEDS = [17, 29, 43, 71, 101]


def query_metrics(frame: pd.DataFrame, score_column: str) -> pd.DataFrame:
    rows = []
    for query_id, group in frame.groupby("query_id", sort=False):
        if len(group) < 2:
            continue
        actual = group.sort_values(["actual_rank", "sample_id"], kind="mergesort").index.tolist()
        predicted = group.sort_values([score_column, "sample_id"], kind="mergesort").index.tolist()
        rows.append(
            {
                "query_id": query_id,
                "city": group["city"].iloc[0],
                "tasks": len(group),
                **evaluate_order(predicted, actual),
            }
        )
    return pd.DataFrame(rows)


def summarize(model: str, frame: pd.DataFrame, seed: int | None = None, noise: float = 0.0) -> list[dict]:
    rows = []
    for scope, group, subset in [
        ("overall", "all", frame),
        *[("city", city, frame[frame["city"] == city]) for city in sorted(frame["city"].unique())],
    ]:
        rows.append(
            {
                "model": model,
                "seed": seed,
                "noise_sd_minutes": noise,
                "scope": scope,
                "group": group,
                "queries": len(subset),
                **{column: float(subset[column].mean()) for column in ["hr_at_3", "krc", "lsd", "edit_distance"]},
            }
        )
    return rows


def run(predictions: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(predictions).reset_index(drop=True)
    summaries = []
    query_tables = []
    for model in MODELS:
        result = query_metrics(frame, model)
        result["model"] = model
        result["seed"] = pd.NA
        result["noise_sd_minutes"] = 0.0
        query_tables.append(result)
        summaries.extend(summarize(model, result))

    for noise in [5.0, 10.0, 20.0]:
        for seed in NOISE_SEEDS:
            rng = np.random.default_rng(seed)
            column = f"noisy_{noise:g}_{seed}"
            frame[column] = frame["selected_prediction"] + rng.normal(0, noise, len(frame))
            result = query_metrics(frame, column)
            result["model"] = "selected_model_noisy"
            result["seed"] = seed
            result["noise_sd_minutes"] = noise
            query_tables.append(result)
            summaries.extend(summarize("selected_model_noisy", result, seed, noise))
            frame = frame.drop(columns=[column])

    query_frame = pd.concat(query_tables, ignore_index=True)
    summary_frame = pd.DataFrame(summaries)
    query_frame.to_parquet(output / "query_metrics.parquet", index=False)
    summary_frame.to_csv(output / "summary.csv", index=False)
    primary_frame = summary_frame[
        (summary_frame["scope"] == "overall")
        & (summary_frame["noise_sd_minutes"] == 0)
    ]
    primary = json.loads(primary_frame.to_json(orient="records"))
    noise_summary = (
        summary_frame[
            (summary_frame["scope"] == "overall")
            & (summary_frame["model"] == "selected_model_noisy")
        ]
        .groupby("noise_sd_minutes")[["hr_at_3", "krc", "lsd", "edit_distance"]]
        .agg(["mean", "std"])
    )
    payload = {
        "test_rows": len(frame),
        "eligible_queries_with_at_least_two_tasks": int(
            query_frame[query_frame["model"] == "selected_prediction"]["query_id"].nunique()
        ),
        "primary": primary,
        "noise_sensitivity": {
            str(index): {
                f"{column}_{stat}": float(value)
                for (column, stat), value in row.items()
            }
            for index, row in noise_summary.iterrows()
        },
    }
    (output / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.predictions, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
