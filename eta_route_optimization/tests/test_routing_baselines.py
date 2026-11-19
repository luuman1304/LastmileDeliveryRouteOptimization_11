import pytest
from eta_route_optimization.routing_baselines import (
    closed_tour_cost,
    directed_two_opt,
    nearest_neighbor,
    validate_sequence,
)

COSTS = {
    "D": {"D": 0, "A": 2, "B": 5, "C": 4},
    "A": {"D": 2, "A": 0, "B": 2, "C": 6},
    "B": {"D": 5, "A": 2, "B": 0, "C": 2},
    "C": {"D": 2, "A": 6, "B": 2, "C": 0},
}


def test_nearest_neighbor_is_deterministic_and_valid() -> None:
    sequence = nearest_neighbor(COSTS, "D")
    assert sequence == ["D", "A", "B", "C"]
    validate_sequence(sequence, list(COSTS), "D")


def test_directed_two_opt_does_not_increase_test_cost() -> None:
    original = ["D", "B", "A", "C"]
    improved = directed_two_opt(original, COSTS, max_passes=5)
    validate_sequence(improved, list(COSTS), "D")
    assert closed_tour_cost(improved, COSTS) <= closed_tour_cost(original, COSTS)


@pytest.mark.parametrize(
    "sequence",
    [[], ["A", "D", "B", "C"], ["D", "A", "A", "C"], ["D", "A", "B"]],
)
def test_invalid_sequences_are_rejected(sequence: list[str]) -> None:
    with pytest.raises(ValueError):
        validate_sequence(sequence, list(COSTS), "D")
