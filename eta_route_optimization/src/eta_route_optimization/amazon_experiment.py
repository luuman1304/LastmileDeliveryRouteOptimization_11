from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .routing_baselines import (
    directed_two_opt,
    nearest_neighbor,
    validate_sequence,
)


def objects(path: Path):
    """Stream members of a top-level JSON object, one route at a time."""

    decoder = json.JSONDecoder()
    with path.open() as handle:
        buffer = ""
        eof = False

        def fill():
            nonlocal buffer, eof
            chunk = handle.read(1024 * 1024)
            buffer += chunk
            eof = not chunk

        def token():
            nonlocal buffer
            while True:
                buffer = buffer.lstrip()
                if buffer or eof:
                    return buffer[:1]
                fill()

        def consume(expected):
            nonlocal buffer
            if token() != expected:
                raise ValueError(f"{path}: expected {expected}")
            buffer = buffer[1:]

        def value():
            nonlocal buffer
            token()
            while True:
                try:
                    result, end = decoder.raw_decode(buffer)
                    buffer = buffer[end:]
                    return result
                except json.JSONDecodeError:
                    if eof:
                        raise
                    fill()

        consume("{")
        if token() != "}":
            while True:
                key = value()
                consume(":")
                yield key, value()
                if token() == "}":
                    break
                consume(",")
        consume("}")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def select_routes(route_path: Path, per_station: int) -> tuple[set[str], dict[str, dict]]:
    station_ids: dict[str, list[str]] = defaultdict(list)
    for route_id, route in objects(route_path):
        station_ids[route["station_code"]].append(route_id)
    selected = {
        route_id
        for station, route_ids in station_ids.items()
        for route_id in sorted(route_ids, key=lambda value: (_hash(value), value))[:per_station]
    }
    routes = {route_id: route for route_id, route in objects(route_path) if route_id in selected}
    if set(routes) != selected:
        raise RuntimeError("selected Amazon routes are incomplete")
    return selected, routes


def load_city_map(path: Path) -> dict[str, str]:
    with path.open(newline="") as handle:
        rows = csv.DictReader(handle)
        return {row["station_code"]: row["metropolitan_group"].replace("_", " ") for row in rows}


def ortools_tsp(costs: dict[str, dict[str, float]], depot: str, seconds: int) -> list[str]:
    stops = list(costs)
    index = {stop: position for position, stop in enumerate(stops)}
    manager = pywrapcp.RoutingIndexManager(len(stops), 1, index[depot])
    routing = pywrapcp.RoutingModel(manager)

    def transit(from_index: int, to_index: int) -> int:
        left = stops[manager.IndexToNode(from_index)]
        right = stops[manager.IndexToNode(to_index)]
        return round(float(costs[left][right]) * 1000)

    callback = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(callback)
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.seconds = seconds
    search.log_search = False
    solution = routing.SolveWithParameters(search)
    if solution is None:
        raise RuntimeError("OR-Tools did not return a feasible TSP tour")
    result = []
    current = routing.Start(0)
    while not routing.IsEnd(current):
        result.append(stops[manager.IndexToNode(current)])
        current = solution.Value(routing.NextVar(current))
    return result


def ortools_tsp_time_windows(costs, depot, route, packages, seconds: int) -> list[str] | None:
    """Closed TSP with hard package-window intersections at each stop."""

    stops = list(costs)
    index = {stop: position for position, stop in enumerate(stops)}
    manager = pywrapcp.RoutingIndexManager(len(stops), 1, index[depot])
    routing = pywrapcp.RoutingModel(manager)
    service = {
        stop: sum(float(item["planned_service_time_seconds"]) for item in packages[stop].values())
        for stop in stops
    }

    def transit(from_index: int, to_index: int) -> int:
        left = stops[manager.IndexToNode(from_index)]
        right = stops[manager.IndexToNode(to_index)]
        return round(float(costs[left][right]) + service[left])

    callback = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(callback)
    horizon = 48 * 60 * 60
    routing.AddDimension(callback, horizon, horizon, True, "Time")
    dimension = routing.GetDimensionOrDie("Time")
    start = datetime.fromisoformat(route["date_YYYY_MM_DD"] + " " + route["departure_time_utc"])
    for stop in stops:
        if stop == depot:
            continue
        bounds = [
            (
                _offset(item["time_window"].get("start_time_utc"), start),
                _offset(item["time_window"].get("end_time_utc"), start),
            )
            for item in packages[stop].values()
        ]
        lower_values = [value for value, _ in bounds if value is not None]
        upper_values = [value for _, value in bounds if value is not None]
        lower = max([0.0, *lower_values])
        upper = min([float(horizon), *upper_values])
        if lower > upper:
            return None
        dimension.CumulVar(manager.NodeToIndex(index[stop])).SetRange(
            math.ceil(lower), math.floor(upper)
        )
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.seconds = seconds
    solution = routing.SolveWithParameters(search)
    if solution is None:
        return None
    result = []
    current = routing.Start(0)
    while not routing.IsEnd(current):
        result.append(stops[manager.IndexToNode(current)])
        current = solution.Value(routing.NextVar(current))
    return result


def ortools_tsp_soft_time_windows(
    costs, depot, route, packages, seconds: int, lateness_penalty: int
) -> list[str] | None:
    """Closed TSP with hard releases and penalized upper time-window bounds.

    Package windows at one stop can conflict. The evaluator still scores every
    package separately; the solver uses the latest release and earliest deadline
    as a reproducible stop-level approximation.
    """

    stops = list(costs)
    index = {stop: position for position, stop in enumerate(stops)}
    manager = pywrapcp.RoutingIndexManager(len(stops), 1, index[depot])
    routing = pywrapcp.RoutingModel(manager)
    service = {
        stop: sum(float(item["planned_service_time_seconds"]) for item in packages[stop].values())
        for stop in stops
    }

    def transit(from_index: int, to_index: int) -> int:
        left = stops[manager.IndexToNode(from_index)]
        right = stops[manager.IndexToNode(to_index)]
        return round(float(costs[left][right]) + service[left])

    callback = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(callback)
    horizon = 48 * 60 * 60
    routing.AddDimension(callback, horizon, horizon, True, "Time")
    dimension = routing.GetDimensionOrDie("Time")
    start = datetime.fromisoformat(route["date_YYYY_MM_DD"] + " " + route["departure_time_utc"])
    for stop in stops:
        if stop == depot:
            continue
        bounds = [
            (
                _offset(item["time_window"].get("start_time_utc"), start),
                _offset(item["time_window"].get("end_time_utc"), start),
            )
            for item in packages[stop].values()
        ]
        lower_values = [value for value, _ in bounds if value is not None]
        upper_values = [value for _, value in bounds if value is not None]
        node = manager.NodeToIndex(index[stop])
        lower = min(float(horizon), max([0.0, *lower_values]))
        dimension.CumulVar(node).SetRange(math.ceil(lower), horizon)
        if upper_values:
            upper = max(0, min(horizon, math.floor(min(upper_values))))
            dimension.SetCumulVarSoftUpperBound(node, upper, int(lateness_penalty))
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.seconds = seconds
    solution = routing.SolveWithParameters(search)
    if solution is None:
        return None
    result = []
    current = routing.Start(0)
    while not routing.IsEnd(current):
        result.append(stops[manager.IndexToNode(current)])
        current = solution.Value(routing.NextVar(current))
    return result


def _offset(value, start: datetime) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return (datetime.fromisoformat(value) - start).total_seconds()


def evaluate_route(sequence, route, packages, costs) -> dict:
    stops = route["stops"]
    depots = [stop for stop, value in stops.items() if value["type"] == "Station"]
    if len(depots) != 1:
        raise ValueError("expected exactly one depot")
    depot = depots[0]
    validate_sequence(sequence, list(stops), depot)
    start = datetime.fromisoformat(route["date_YYYY_MM_DD"] + " " + route["departure_time_utc"])
    elapsed = service = waiting = lateness = open_transit = 0.0
    windowed = late = 0
    previous = depot
    volume = 0.0
    for stop in sequence[1:]:
        transit = float(costs[previous][stop])
        open_transit += transit
        elapsed += transit
        items = list(packages[stop].values())
        bounds = [
            (
                _offset(item["time_window"].get("start_time_utc"), start),
                _offset(item["time_window"].get("end_time_utc"), start),
            )
            for item in items
        ]
        release = max([elapsed] + [left for left, _ in bounds if left is not None])
        waiting += release - elapsed
        elapsed = release
        for left, right in bounds:
            windowed += int(left is not None and right is not None)
            if right is not None:
                delay = max(0.0, elapsed - right)
                lateness += delay
                late += int(delay > 0)
        duration = sum(float(item["planned_service_time_seconds"]) for item in items)
        for item in items:
            dimensions = item["dimensions"]
            volume += float(dimensions["depth_cm"]) * float(dimensions["height_cm"]) * float(dimensions["width_cm"])
        service += duration
        elapsed += duration
        previous = stop
    return_transit = float(costs[previous][depot])
    closed_transit = open_transit + return_transit
    return {
        "open_transit_seconds": open_transit,
        "return_transit_seconds": return_transit,
        "closed_transit_seconds": closed_transit,
        "service_seconds": service,
        "waiting_seconds": waiting,
        "open_duration_seconds": elapsed,
        "closed_duration_seconds": elapsed + return_transit,
        "lateness_seconds": lateness,
        "late_packages": late,
        "windowed_packages": windowed,
        "volume_cm3": volume,
        "volume_capacity_ratio": volume / float(route["executor_capacity_cm3"]),
        "volume_feasible": volume <= float(route["executor_capacity_cm3"]) + 1e-9,
        "sequence_valid": True,
    }


def bootstrap_ci(values, seed=20261116, replicates=5000):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    result = np.empty(replicates)
    for start in range(0, replicates, 100):
        count = min(100, replicates - start)
        indices = rng.integers(0, len(values), size=(count, len(values)))
        result[start : start + count] = values[indices].mean(axis=1)
    return [float(value) for value in np.quantile(result, [0.025, 0.975])]


def run(source: Path, city_map_path: Path, output: Path, per_station: int, solver_seconds: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    selected, routes = select_routes(source / "route_data.json", per_station)
    city_map = load_city_map(city_map_path)
    sequences = {route_id: payload["actual"] for route_id, payload in objects(source / "actual_sequences.json") if route_id in selected}
    packages = {route_id: payload for route_id, payload in objects(source / "package_data.json") if route_id in selected}
    if set(sequences) != selected or set(packages) != selected:
        raise RuntimeError("selected Amazon sidecars are incomplete")
    rows = []
    solution_path = output / "sequences.jsonl"
    with solution_path.open("w") as solution_file:
        for route_id, costs in objects(source / "travel_times.json"):
            if route_id not in selected:
                continue
            route = routes[route_id]
            observed_map = sequences[route_id]
            observed = sorted(observed_map, key=observed_map.get)
            depot = observed[0]
            methods = {}
            methods["observed"] = observed
            methods["nearest_neighbor"] = nearest_neighbor(costs, depot)
            methods["nearest_neighbor_2opt"] = directed_two_opt(methods["nearest_neighbor"], costs, 5)
            started = time.perf_counter()
            methods["ortools"] = ortools_tsp(costs, depot, solver_seconds)
            ortools_runtime = time.perf_counter() - started
            started = time.perf_counter()
            methods["ortools_time_windows"] = ortools_tsp_time_windows(
                costs, depot, route, packages[route_id], solver_seconds
            )
            ortools_tw_runtime = time.perf_counter() - started
            reference = evaluate_route(observed, route, packages[route_id], costs)
            for method, sequence in methods.items():
                runtime = {
                    "ortools": ortools_runtime,
                    "ortools_time_windows": ortools_tw_runtime,
                }.get(method, 0.0)
                if sequence is None:
                    rows.append(
                        {
                            "route_id": route_id,
                            "station": route["station_code"],
                            "city": city_map.get(route["station_code"], "unknown"),
                            "route_quality": route["route_score"],
                            "stops": len(route["stops"]),
                            "method": method,
                            "runtime_seconds": runtime,
                            "solver_feasible": False,
                            "sequence_valid": False,
                        }
                    )
                    solution_file.write(json.dumps({"route_id": route_id, "method": method, "sequence": None}) + "\n")
                    continue
                started = time.perf_counter()
                result = evaluate_route(sequence, route, packages[route_id], costs)
                if method not in {"ortools", "ortools_time_windows"}:
                    runtime = time.perf_counter() - started
                rows.append(
                    {
                        "route_id": route_id,
                        "station": route["station_code"],
                        "city": city_map.get(route["station_code"], "unknown"),
                        "route_quality": route["route_score"],
                        "stops": len(sequence),
                        "method": method,
                        "runtime_seconds": runtime,
                        "solver_feasible": True,
                        "closed_delta_vs_observed_seconds": result["closed_transit_seconds"] - reference["closed_transit_seconds"],
                        "open_delta_vs_observed_seconds": result["open_transit_seconds"] - reference["open_transit_seconds"],
                        **result,
                    }
                )
                solution_file.write(json.dumps({"route_id": route_id, "method": method, "sequence": sequence}) + "\n")
            if len({row["route_id"] for row in rows}) % 25 == 0:
                print(f"completed {len({row['route_id'] for row in rows})}/{len(selected)} routes", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "route_results.csv", index=False)
    summary_rows = []
    for method, group in frame.groupby("method"):
        feasible = group[group["solver_feasible"] == True]
        summary_rows.append(
            {
                "method": method,
                "routes": len(group),
                "solved_routes": len(feasible),
                **{
                    "mean_" + column: float(feasible[column].mean())
                    for column in [
                        "closed_transit_seconds",
                        "open_transit_seconds",
                        "service_seconds",
                        "lateness_seconds",
                        "late_packages",
                        "runtime_seconds",
                        "closed_delta_vs_observed_seconds",
                    ]
                },
                "feasibility_rate": float(group["solver_feasible"].mean()),
                "volume_feasibility_rate": float(feasible["volume_feasible"].mean()),
            }
        )
    inference = {}
    for method in ["nearest_neighbor", "nearest_neighbor_2opt", "ortools", "ortools_time_windows"]:
        delta = frame[
            (frame["method"] == method) & (frame["solver_feasible"] == True)
        ].sort_values("route_id")["closed_delta_vs_observed_seconds"].to_numpy()
        inference[method] = {
            "mean_delta_vs_observed_seconds": float(delta.mean()),
            "bootstrap_ci95": bootstrap_ci(delta),
            "solved_routes": len(delta),
            "routes_better_than_observed": int(np.sum(delta < 0)),
            "routes_worse_than_observed": int(np.sum(delta > 0)),
        }
    payload = {
        "protocol": {
            "source_split": "training only",
            "selection": f"up to {per_station} SHA256-selected routes per station",
            "routes": len(selected),
            "stations": len({route["station_code"] for route in routes.values()}),
            "closed_tour_primary": True,
            "open_path_sensitivity": True,
            "ortools_time_limit_seconds": solver_seconds,
        },
        "summary": summary_rows,
        "paired_inference": inference,
    }
    (output / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--city-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--per-station", type=int, default=12)
    parser.add_argument("--solver-seconds", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.city_map, args.output, args.per_station, args.solver_seconds), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
