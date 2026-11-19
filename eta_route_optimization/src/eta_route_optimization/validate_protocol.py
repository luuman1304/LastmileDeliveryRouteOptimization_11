from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def validate_eta_dataset(dataset: Path) -> dict:
    frames = {split: pd.read_parquet(dataset / f"{split}.parquet") for split in ["train", "validation", "test"]}
    sample_sets = {split: set(frame["sample_id"]) for split, frame in frames.items()}
    query_sets = {split: set(frame["query_id"]) for split, frame in frames.items()}
    for left, right in [("train", "validation"), ("train", "test"), ("validation", "test")]:
        if sample_sets[left] & sample_sets[right]:
            raise RuntimeError(f"sample leakage between {left} and {right}")
        if query_sets[left] & query_sets[right]:
            raise RuntimeError(f"query leakage between {left} and {right}")
    checks = {}
    for split, frame in frames.items():
        if frame["sample_id"].duplicated().any():
            raise RuntimeError(f"duplicate sample_id in {split}")
        if not (frame["accept_dt"] <= frame["query_dt"]).all():
            raise RuntimeError(f"future accept event used in {split}")
        if not (frame["delivery_dt"] > frame["query_dt"]).all():
            raise RuntimeError(f"non-future target in {split}")
        if not (frame["eta_minutes"] > 0).all():
            raise RuntimeError(f"non-positive ETA in {split}")
        if frame.groupby("query_id").size().max() > 25:
            raise RuntimeError(f"too many pending tasks in {split}")
        if not (frame["pending_count_before_cap"] >= frame["pending_count"]).all():
            raise RuntimeError(f"pre-cap active count smaller than capped count in {split}")
        if not (frame["pending_count"] >= frame.groupby("query_id")["order_id"].transform("size")).all():
            raise RuntimeError(f"observable active count smaller than labeled rows in {split}")
        if not (frame["accept_rank"] < frame["pending_count"]).all():
            raise RuntimeError(f"accept rank inconsistent with operational cap in {split}")
        expected = {
            "train": frame["route_day"] < 901,
            "validation": (frame["route_day"] >= 901) & (frame["route_day"] < 1001),
            "test": frame["route_day"] >= 1001,
        }[split]
        if not expected.all():
            raise RuntimeError(f"time split violation in {split}")
        query_mmdd = frame["query_dt"].dt.month * 100 + frame["query_dt"].dt.day
        if not (query_mmdd == frame["route_day"]).all():
            raise RuntimeError(f"route_day differs from query date in {split}")
        checks[split] = {
            "rows": len(frame),
            "queries": int(frame["query_id"].nunique()),
            "maximum_tasks_per_query": int(frame.groupby("query_id").size().max()),
            "minimum_eta": float(frame["eta_minutes"].min()),
            "maximum_eta": float(frame["eta_minutes"].max()),
            "rows_with_eta_over_120": int((frame["eta_minutes"] > 120).sum()),
        }
    return {
        "status": "pass",
        "checks": checks,
        "query_sets_disjoint": True,
        "sample_sets_disjoint": True,
        "outcome_based_horizon_filter_applied": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = validate_eta_dataset(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
