from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from .amazon_experiment import (
    _hash,
    evaluate_route,
    objects,
    ortools_tsp_soft_time_windows,
    select_routes,
)


def sequence_hash(sequence: list[str]) -> str:
    return hashlib.sha256("|".join(sequence).encode()).hexdigest()


def run(source: Path, output: Path, per_station: int, repeats: int, routes_per_station: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    selected, routes = select_routes(source / "route_data.json", per_station)
    by_station: dict[str, list[str]] = {}
    for route_id in selected:
        by_station.setdefault(routes[route_id]["station_code"], []).append(route_id)
    calibration = {
        min(route_ids, key=lambda route_id: (_hash(route_id), route_id))
        for route_ids in by_station.values()
    }
    stability_routes = {
        route_id
        for station, route_ids in by_station.items()
        for route_id in sorted(
            [value for value in route_ids if value not in calibration],
            key=lambda value: (_hash(value), value),
        )[:routes_per_station]
    }
    sequences = {
        route_id: payload["actual"]
        for route_id, payload in objects(source / "actual_sequences.json")
        if route_id in stability_routes
    }
    packages = {
        route_id: payload
        for route_id, payload in objects(source / "package_data.json")
        if route_id in stability_routes
    }
    rows = []
    completed = 0
    for route_id, costs in objects(source / "travel_times.json"):
        if route_id not in stability_routes:
            continue
        route = routes[route_id]
        observed = sorted(sequences[route_id], key=sequences[route_id].get)
        depot = observed[0]
        observed_result = evaluate_route(observed, route, packages[route_id], costs)
        observed_cost = observed_result["closed_duration_seconds"] + observed_result["lateness_seconds"]
        for repeat in range(repeats):
            started = time.perf_counter()
            proposed = ortools_tsp_soft_time_windows(costs, depot, route, packages[route_id], 1, 1)
            runtime = time.perf_counter() - started
            if proposed is None:
                rows.append(
                    {
                        "route_id": route_id,
                        "station": route["station_code"],
                        "repeat": repeat,
                        "solver_solved": False,
                        "runtime_seconds": runtime,
                    }
                )
                continue
            result = evaluate_route(proposed, route, packages[route_id], costs)
            operational_cost = result["closed_duration_seconds"] + result["lateness_seconds"]
            rows.append(
                {
                    "route_id": route_id,
                    "station": route["station_code"],
                    "repeat": repeat,
                    "solver_solved": True,
                    "runtime_seconds": runtime,
                    "sequence_hash": sequence_hash(proposed),
                    "operational_cost": operational_cost,
                    "operational_delta_vs_observed": operational_cost - observed_cost,
                    "closed_transit_seconds": result["closed_transit_seconds"],
                    "lateness_seconds": result["lateness_seconds"],
                }
            )
        completed += 1
        if completed % 10 == 0:
            print(f"completed {completed}/{len(stability_routes)} stability routes", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "runs.csv", index=False)
    solved = frame[frame["solver_solved"] == True]
    per_route = solved.groupby(["route_id", "station"]).agg(
        unique_sequences=("sequence_hash", "nunique"),
        operational_cost_min=("operational_cost", "min"),
        operational_cost_max=("operational_cost", "max"),
        delta_mean=("operational_delta_vs_observed", "mean"),
    ).reset_index()
    per_route["operational_cost_range"] = (
        per_route["operational_cost_max"] - per_route["operational_cost_min"]
    )
    per_route.to_csv(output / "per_route.csv", index=False)
    repeat_means = solved.groupby("repeat")["operational_delta_vs_observed"].mean()
    payload = {
        "protocol": {
            "penalty": 1,
            "solver_seconds": 1,
            "repeats": repeats,
            "routes_per_station": routes_per_station,
            "stations": len(by_station),
            "routes": len(stability_routes),
            "selection": "SHA256 after excluding the calibration route",
        },
        "solver_solved_rate": float(frame["solver_solved"].mean()),
        "routes_with_identical_sequence_all_repeats": int((per_route["unique_sequences"] == 1).sum()),
        "routes_with_identical_cost_all_repeats": int((per_route["operational_cost_range"] == 0).sum()),
        "maximum_within_route_operational_cost_range": float(per_route["operational_cost_range"].max()),
        "mean_within_route_operational_cost_range": float(per_route["operational_cost_range"].mean()),
        "mean_delta_by_repeat": {str(k): float(v) for k, v in repeat_means.items()},
        "mean_delta_repeat_range": float(repeat_means.max() - repeat_means.min()),
    }
    (output / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--per-station", type=int, default=12)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--routes-per-station", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.output, args.per_station, args.repeats, args.routes_per_station), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
