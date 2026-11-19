from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from .amazon_experiment import (
    _hash,
    bootstrap_ci,
    evaluate_route,
    objects,
    ortools_tsp_soft_time_windows,
    select_routes,
)
from .routing_baselines import directed_two_opt, nearest_neighbor

PENALTIES = [1, 10, 100]


def operational_cost(result: dict) -> float:
    return float(result["closed_duration_seconds"] + result["lateness_seconds"])


def sequence_hash(sequence: list[str]) -> str:
    return hashlib.sha256("|".join(sequence).encode()).hexdigest()


def run(
    source: Path,
    output: Path,
    per_station: int,
    solver_seconds: int,
    repeats: int = 3,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    selected, routes = select_routes(source / "route_data.json", per_station)
    sequences = {
        route_id: payload["actual"]
        for route_id, payload in objects(source / "actual_sequences.json")
        if route_id in selected
    }
    packages = {
        route_id: payload
        for route_id, payload in objects(source / "package_data.json")
        if route_id in selected
    }
    if set(sequences) != selected or set(packages) != selected:
        raise RuntimeError("selected Amazon sidecars are incomplete")
    by_station: dict[str, list[str]] = {}
    for route_id in selected:
        by_station.setdefault(routes[route_id]["station_code"], []).append(route_id)
    calibration = {
        min(route_ids, key=lambda route_id: (_hash(route_id), route_id))
        for route_ids in by_station.values()
    }

    calibration_rows = []
    for route_id, costs in objects(source / "travel_times.json"):
        if route_id not in calibration:
            continue
        route = routes[route_id]
        depot = min(sequences[route_id], key=sequences[route_id].get)
        for penalty in PENALTIES:
            for repeat in range(repeats):
                started = time.perf_counter()
                sequence = ortools_tsp_soft_time_windows(
                    costs, depot, route, packages[route_id], solver_seconds, penalty
                )
                runtime = time.perf_counter() - started
                if sequence is None:
                    calibration_rows.append(
                        {
                            "route_id": route_id,
                            "penalty": penalty,
                            "repeat": repeat,
                            "solver_solved": False,
                            "runtime_seconds": runtime,
                        }
                    )
                    continue
                result = evaluate_route(sequence, route, packages[route_id], costs)
                calibration_rows.append(
                    {
                        "route_id": route_id,
                        "penalty": penalty,
                        "repeat": repeat,
                        "solver_solved": True,
                        "runtime_seconds": runtime,
                        "sequence_hash": sequence_hash(sequence),
                        "operational_cost": operational_cost(result),
                        **result,
                    }
                )
    calibration_frame = pd.DataFrame(calibration_rows)
    calibration_frame.to_csv(output / "calibration_results.csv", index=False)
    candidate_summary = []
    for penalty, group in calibration_frame.groupby("penalty"):
        solved = group[group["solver_solved"] == True]
        route_medians = solved.groupby("route_id")["operational_cost"].median()
        candidate_summary.append(
            {
                "penalty": int(penalty),
                "solved_rate": float(group["solver_solved"].mean()),
                "mean_route_median_operational_cost": float(route_medians.mean()),
                "median_route_median_operational_cost": float(route_medians.median()),
                "mean_lateness_seconds": float(solved["lateness_seconds"].mean()),
                "mean_closed_transit_seconds": float(solved["closed_transit_seconds"].mean()),
                "attempts": len(group),
            }
        )
    selected_penalty = min(
        candidate_summary,
        key=lambda row: (
            -row["solved_rate"],
            row["mean_route_median_operational_cost"],
            row["penalty"],
        ),
    )["penalty"]

    run_rows = []
    run_sequences: dict[tuple[str, int], list[str]] = {}
    completed = 0
    for route_id, costs in objects(source / "travel_times.json"):
        if route_id not in selected:
            continue
        route = routes[route_id]
        observed = sorted(sequences[route_id], key=sequences[route_id].get)
        depot = observed[0]
        observed_result = evaluate_route(observed, route, packages[route_id], costs)
        for repeat in range(repeats):
            started = time.perf_counter()
            proposed = ortools_tsp_soft_time_windows(
                costs, depot, route, packages[route_id], solver_seconds, selected_penalty
            )
            solver_runtime = time.perf_counter() - started
            fallback_used = proposed is None
            if fallback_used:
                proposed = directed_two_opt(nearest_neighbor(costs, depot), costs, 5)
            proposed_result = evaluate_route(proposed, route, packages[route_id], costs)
            run_sequences[(route_id, repeat)] = proposed
            run_rows.append(
                {
                    "route_id": route_id,
                    "station": route["station_code"],
                    "is_calibration": route_id in calibration,
                    "repeat": repeat,
                    "solver_solved": not fallback_used,
                    "fallback_used": fallback_used,
                    "runtime_seconds": solver_runtime,
                    "sequence_hash": sequence_hash(proposed),
                    "operational_cost": operational_cost(proposed_result),
                    "operational_delta_vs_observed": operational_cost(proposed_result)
                    - operational_cost(observed_result),
                    "closed_transit_delta_vs_observed": proposed_result["closed_transit_seconds"]
                    - observed_result["closed_transit_seconds"],
                    "lateness_delta_vs_observed": proposed_result["lateness_seconds"]
                    - observed_result["lateness_seconds"],
                    **proposed_result,
                }
            )
        completed += 1
        if completed % 25 == 0:
            print(f"completed {completed}/{len(selected)} routes x {repeats} repeats", flush=True)

    runs = pd.DataFrame(run_rows).sort_values(["route_id", "repeat"])
    runs.to_csv(output / "route_runs.csv", index=False)
    aggregate_rows = []
    representative_sequences = {}
    numeric_medians = [
        "operational_cost",
        "operational_delta_vs_observed",
        "closed_transit_delta_vs_observed",
        "lateness_delta_vs_observed",
        "open_transit_seconds",
        "return_transit_seconds",
        "closed_transit_seconds",
        "service_seconds",
        "waiting_seconds",
        "open_duration_seconds",
        "closed_duration_seconds",
        "lateness_seconds",
        "late_packages",
        "windowed_packages",
        "volume_cm3",
        "volume_capacity_ratio",
    ]
    for route_id, group in runs.groupby("route_id", sort=True):
        median_cost = float(group["operational_cost"].median())
        representative_index = (group["operational_cost"] - median_cost).abs().idxmin()
        representative = group.loc[representative_index]
        row = {
            "route_id": route_id,
            "station": representative["station"],
            "is_calibration": bool(representative["is_calibration"]),
            "repeats": len(group),
            "solver_solved_rate": float(group["solver_solved"].mean()),
            "fallback_rate": float(group["fallback_used"].mean()),
            "runtime_seconds": float(group["runtime_seconds"].median()),
            "unique_sequences": int(group["sequence_hash"].nunique()),
            "operational_cost_range": float(
                group["operational_cost"].max() - group["operational_cost"].min()
            ),
            "volume_feasible": bool(representative["volume_feasible"]),
            "sequence_valid": bool(representative["sequence_valid"]),
        }
        row.update({column: float(group[column].median()) for column in numeric_medians})
        aggregate_rows.append(row)
        repeat = int(representative["repeat"])
        representative_sequences[route_id] = run_sequences[(route_id, repeat)]
    frame = pd.DataFrame(aggregate_rows).sort_values("route_id")
    frame.to_csv(output / "route_results.csv", index=False)
    with (output / "sequences.jsonl").open("w") as solution_file:
        for route_id in sorted(representative_sequences):
            solution_file.write(
                json.dumps(
                    {"route_id": route_id, "sequence": representative_sequences[route_id]},
                    ensure_ascii=False,
                )
                + "\n"
            )
    evaluation = frame[~frame["is_calibration"]]
    delta = evaluation["operational_delta_vs_observed"].to_numpy()
    station_delta = evaluation.groupby("station")["operational_delta_vs_observed"].mean()
    station_values = station_delta.to_numpy()
    rng = np.random.default_rng(20261117)
    cluster_means = np.empty(20_000)
    for index in range(len(cluster_means)):
        cluster_means[index] = station_values[
            rng.integers(0, len(station_values), len(station_values))
        ].mean()
    station_better = int((station_values < 0).sum())
    leave_one_station_out = {
        str(station): float(station_delta.drop(station).mean())
        for station in station_delta.index
    }
    cost_weight_sensitivity = {}
    for lateness_weight in [0.5, 1.0, 2.0]:
        weighted_delta = (
            evaluation["operational_delta_vs_observed"]
            + (lateness_weight - 1.0) * evaluation["lateness_delta_vs_observed"]
        )
        weighted_station = weighted_delta.groupby(evaluation["station"]).mean()
        cost_weight_sensitivity[str(lateness_weight)] = {
            "mean_route_delta": float(weighted_delta.mean()),
            "equal_station_mean_delta": float(weighted_station.mean()),
            "stations_better_than_observed": int((weighted_station < 0).sum()),
            "stations_worse_than_observed": int((weighted_station > 0).sum()),
        }
    payload = {
        "protocol": {
            "routes": len(frame),
            "calibration_routes": len(calibration),
            "evaluation_routes": len(evaluation),
            "penalty_candidates": PENALTIES,
            "selection_metric": "calibration_mean_route_median_closed_duration_plus_package_lateness",
            "solver_seconds": solver_seconds,
            "repeats_per_route": repeats,
            "fallback": "nearest_neighbor_plus_directed_2opt",
        },
        "calibration": candidate_summary,
        "selected_penalty": selected_penalty,
        "all_routes": {
            "solver_solved_rate": float(runs["solver_solved"].mean()),
            "fallback_rate": float(runs["fallback_used"].mean()),
        },
        "held_out_evaluation": {
            "routes": len(evaluation),
            "mean_operational_delta_vs_observed": float(delta.mean()),
            "route_level_bootstrap_ci95_sensitivity_only": bootstrap_ci(delta),
            "routes_better_than_observed": int(np.sum(delta < 0)),
            "routes_worse_than_observed": int(np.sum(delta > 0)),
            "mean_closed_transit_seconds": float(evaluation["closed_transit_seconds"].mean()),
            "mean_lateness_seconds": float(evaluation["lateness_seconds"].mean()),
            "mean_late_packages": float(evaluation["late_packages"].mean()),
            "mean_runtime_seconds": float(evaluation["runtime_seconds"].mean()),
        },
        "solver_stability": {
            "routes": len(frame),
            "routes_with_identical_sequence_all_repeats": int(
                (frame["unique_sequences"] == 1).sum()
            ),
            "routes_with_identical_cost_all_repeats": int(
                (frame["operational_cost_range"] == 0).sum()
            ),
            "mean_within_route_operational_cost_range": float(
                frame["operational_cost_range"].mean()
            ),
            "maximum_within_route_operational_cost_range": float(
                frame["operational_cost_range"].max()
            ),
        },
        "operational_cost_lateness_weight_sensitivity": cost_weight_sensitivity,
        "primary_station_cluster_inference": {
            "stations": len(station_values),
            "routes_per_station": evaluation.groupby("station").size().astype(int).to_dict(),
            "equal_station_mean_operational_delta": float(station_values.mean()),
            "station_cluster_bootstrap_ci95": [
                float(value) for value in np.quantile(cluster_means, [0.025, 0.975])
            ],
            "stations_better_than_observed": station_better,
            "stations_worse_than_observed": int((station_values > 0).sum()),
            "exact_sign_test_two_sided_p": float(
                binomtest(station_better, len(station_values), 0.5, alternative="two-sided").pvalue
            ),
            "leave_one_station_out_mean_delta": leave_one_station_out,
        },
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
    parser.add_argument("--solver-seconds", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.source, args.output, args.per_station, args.solver_seconds, args.repeats),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
