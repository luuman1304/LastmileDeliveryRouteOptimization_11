from eta_route_optimization.amazon_experiment import (
    ortools_tsp,
    ortools_tsp_soft_time_windows,
)
from eta_route_optimization.routing_baselines import validate_sequence
from eta_route_optimization.soft_window_experiment import operational_cost


def test_ortools_returns_valid_sequence() -> None:
    costs = {
        "D": {"D": 0, "A": 1, "B": 4},
        "A": {"D": 1, "A": 0, "B": 1},
        "B": {"D": 1, "A": 1, "B": 0},
    }
    sequence = ortools_tsp(costs, "D", 1)
    validate_sequence(sequence, list(costs), "D")


def test_soft_time_windows_return_route_when_deadlines_conflict() -> None:
    costs = {
        "D": {"D": 0, "A": 10, "B": 10},
        "A": {"D": 10, "A": 0, "B": 10},
        "B": {"D": 10, "A": 10, "B": 0},
    }
    route = {"date_YYYY_MM_DD": "2022-01-01", "departure_time_utc": "08:00:00"}
    packages = {
        "D": {},
        "A": {
            "p1": {
                "planned_service_time_seconds": 5,
                "time_window": {
                    "start_time_utc": "2022-01-01 08:01:00",
                    "end_time_utc": "2022-01-01 08:00:30",
                },
            }
        },
        "B": {
            "p2": {
                "planned_service_time_seconds": 5,
                "time_window": {"start_time_utc": None, "end_time_utc": None},
            }
        },
    }
    sequence = ortools_tsp_soft_time_windows(costs, "D", route, packages, 1, 10)
    assert sequence is not None
    validate_sequence(sequence, list(costs), "D")


def test_operational_cost_adds_closed_duration_and_package_lateness() -> None:
    assert operational_cost({"closed_duration_seconds": 100.0, "lateness_seconds": 25.0}) == 125.0
