from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW_COLUMNS = [
    "order_id",
    "region_id",
    "city",
    "courier_id",
    "lng",
    "lat",
    "aoi_id",
    "aoi_type",
    "accept_time",
    "delivery_time",
    "delivery_gps_lng",
    "delivery_gps_lat",
    "ds",
]


def _time(values: pd.Series) -> pd.Series:
    return pd.to_datetime("2022-" + values.astype(str), format="%Y-%m-%d %H:%M:%S", errors="coerce")


def _haversine_km(lng1, lat1, lng2, lat2) -> np.ndarray:
    lng1, lat1, lng2, lat2 = map(np.radians, [lng1, lat1, lng2, lat2])
    delta_lng, delta_lat = lng2 - lng1, lat2 - lat1
    value = np.sin(delta_lat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(delta_lng / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.minimum(1.0, np.sqrt(value)))


def _stable_hash(value: str) -> int:
    return int.from_bytes(hashlib.blake2b(value.encode(), digest_size=8).digest(), "big")


def _cap_complete_queries(frame: pd.DataFrame, cap: int) -> pd.DataFrame:
    if len(frame) <= cap:
        return frame
    sizes = frame.groupby("query_id", sort=False).size().rename("rows").reset_index()
    sizes["hash"] = sizes["query_id"].map(_stable_hash)
    sizes = sizes.sort_values(["hash", "query_id"], kind="mergesort")
    sizes["cumulative"] = sizes["rows"].cumsum()
    keep = set(sizes.loc[sizes["cumulative"] <= cap, "query_id"])
    if not keep:
        keep = {sizes.iloc[0]["query_id"]}
    return frame[frame["query_id"].isin(keep)].copy()


def build_city(path: Path, maximum_pending: int = 25) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_parquet(path, columns=RAW_COLUMNS)
    raw["accept_dt"] = _time(raw["accept_time"])
    raw["delivery_dt"] = _time(raw["delivery_time"])
    essential = ["order_id", "city", "courier_id", "ds", "accept_dt", "delivery_dt", "lng", "lat"]
    before = len(raw)
    raw = raw.dropna(subset=essential).copy()
    raw = raw[raw["delivery_dt"] >= raw["accept_dt"]].copy()
    raw = raw.sort_values(
        ["city", "courier_id", "ds", "delivery_dt", "order_id"], kind="mergesort"
    )
    # `ds` identifies the operational courier-day. Grouping by each target's
    # eventual delivery date would use future information to define the cohort.
    group = ["city", "courier_id", "ds"]
    first = raw.groupby(group, sort=False).head(1).copy()
    first = first[
        group
        + [
            "order_id",
            "delivery_dt",
            "delivery_gps_lng",
            "delivery_gps_lat",
            "lng",
            "lat",
            "aoi_id",
            "region_id",
        ]
    ].rename(
        columns={
            "order_id": "query_order_id",
            "delivery_dt": "query_dt",
            "delivery_gps_lng": "query_gps_lng",
            "delivery_gps_lat": "query_gps_lat",
            "lng": "query_stop_lng",
            "lat": "query_stop_lat",
            "aoi_id": "query_aoi_id",
            "region_id": "query_region_id",
        }
    )
    raw = raw.merge(first, on=group, how="inner", validate="many_to_one")
    raw["route_day"] = raw["query_dt"].dt.month * 100 + raw["query_dt"].dt.day
    raw["query_lng"] = raw["query_gps_lng"].fillna(raw["query_stop_lng"])
    raw["query_lat"] = raw["query_gps_lat"].fillna(raw["query_stop_lat"])
    raw["eta_minutes"] = (raw["delivery_dt"] - raw["query_dt"]).dt.total_seconds() / 60
    # Build the operational task set before applying any target-horizon rule.
    # Counts, ranks and the 25-task cap must be knowable at query time; using
    # eta_minutes <= 120 here would condition features on a future outcome.
    active = raw[
        (raw["accept_dt"] <= raw["query_dt"])
        & (raw["eta_minutes"] > 0)
    ].copy()
    active["query_id"] = (
        active["city"].astype(str)
        + "|"
        + active["courier_id"].astype(str)
        + "|"
        + active["ds"].astype(str)
        + "|"
        + active["query_order_id"].astype(str)
    )
    active["pending_count_before_cap"] = active.groupby("query_id")["order_id"].transform("size")
    active = active.sort_values(["query_id", "accept_dt", "order_id"], kind="mergesort")
    active["accept_rank"] = active.groupby("query_id").cumcount()
    active = active[active["accept_rank"] < maximum_pending].copy()
    active["pending_count"] = active.groupby("query_id")["order_id"].transform("size")
    # Keep every task that was observable at query time.  Earlier protocol
    # versions filtered rows using the future outcome ``eta_minutes <= 120``.
    # Although workload features were frozen before that filter, membership in
    # the evaluated cohort still depended on an outcome unavailable at serving
    # time.  The operational protocol therefore predicts all capped active
    # tasks and treats the 120-minute horizon only as an optional reporting
    # slice, never as a row-selection rule.
    pending = active.copy()
    pending = pending.sort_values(["query_id", "delivery_dt", "order_id"], kind="mergesort")
    pending["actual_rank"] = pending.groupby("query_id").cumcount()
    pending["sample_id"] = pending["query_id"] + "|" + pending["order_id"].astype(str)
    pending["query_hour"] = pending["query_dt"].dt.hour
    pending["query_minute_of_day"] = pending["query_dt"].dt.hour * 60 + pending["query_dt"].dt.minute
    pending["query_day_of_week"] = pending["query_dt"].dt.day_of_week
    pending["query_month"] = pending["query_dt"].dt.month
    pending["waiting_minutes"] = (
        pending["query_dt"] - pending["accept_dt"]
    ).dt.total_seconds().div(60).clip(lower=0)
    pending["direct_distance_km"] = _haversine_km(
        pending["query_lng"].to_numpy(),
        pending["query_lat"].to_numpy(),
        pending["lng"].to_numpy(),
        pending["lat"].to_numpy(),
    )
    pending["same_aoi"] = (pending["aoi_id"] == pending["query_aoi_id"]).astype("int8")
    pending["same_region"] = (pending["region_id"] == pending["query_region_id"]).astype("int8")
    pending["split"] = np.select(
        [pending["route_day"] < 901, pending["route_day"] < 1001],
        ["train", "validation"],
        default="test",
    )
    columns = [
        "sample_id",
        "query_id",
        "split",
        "query_dt",
        "accept_dt",
        "delivery_dt",
        "city",
        "courier_id",
        "ds",
        "route_day",
        "order_id",
        "region_id",
        "aoi_id",
        "aoi_type",
        "query_aoi_id",
        "query_region_id",
        "query_hour",
        "query_minute_of_day",
        "query_day_of_week",
        "query_month",
        "waiting_minutes",
        "direct_distance_km",
        "same_aoi",
        "same_region",
        "pending_count_before_cap",
        "pending_count",
        "accept_rank",
        "actual_rank",
        "lng",
        "lat",
        "query_lng",
        "query_lat",
        "eta_minutes",
    ]
    audit = {
        "path": str(path),
        "raw_rows": before,
        "usable_rows_after_time_checks": len(raw),
        "negative_or_missing_rows_removed": before - len(raw),
        "queries": int(pending["query_id"].nunique()),
        "active_rows_before_task_cap": int((raw["accept_dt"].le(raw["query_dt"]) & raw["eta_minutes"].gt(0)).sum()),
        "labeled_rows_after_operational_cap": len(pending),
        "rows_with_eta_over_120": int((pending["eta_minutes"] > 120).sum()),
        "outcome_based_horizon_filter_applied": False,
    }
    return pending[columns], audit


def prepare(pattern: str, output: Path, caps: dict[str, int]) -> dict:
    import glob

    files = [Path(path) for path in sorted(glob.glob(pattern))]
    if not files:
        raise FileNotFoundError(pattern)
    by_split: dict[str, list[pd.DataFrame]] = {name: [] for name in caps}
    audits = []
    for path in files:
        city_frame, audit = build_city(path)
        audits.append(audit)
        for split, cap in caps.items():
            selected = _cap_complete_queries(city_frame[city_frame["split"] == split], cap)
            by_split[split].append(selected)
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "source_pattern": pattern,
        "query_protocol": "first-delivery-all-observable-tasks-v2",
        "outcome_based_horizon_filter_applied": False,
        "cities": audits,
        "splits": {},
    }
    for split, frames in by_split.items():
        frame = pd.concat(frames, ignore_index=True)
        frame = frame.sort_values(["city", "query_id", "actual_rank"], kind="mergesort")
        path = output / f"{split}.parquet"
        frame.to_parquet(path, index=False)
        summary["splits"][split] = {
            "rows": len(frame),
            "queries": int(frame["query_id"].nunique()),
            "cities": frame.groupby("city").size().astype(int).to_dict(),
            "path": str(path),
        }
    (output / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lade-glob", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--train-cap", type=int, default=250_000)
    parser.add_argument("--validation-cap", type=int, default=50_000)
    parser.add_argument("--test-cap", type=int, default=50_000)
    args = parser.parse_args()
    summary = prepare(
        args.lade_glob,
        args.output,
        {"train": args.train_cap, "validation": args.validation_cap, "test": args.test_cap},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
