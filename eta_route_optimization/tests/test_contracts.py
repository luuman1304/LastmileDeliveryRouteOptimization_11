import pytest
from eta_route_optimization.contracts import RouteCost, validate_nonnegative_cost


def test_route_cost_components_are_additive() -> None:
    cost = RouteCost(transit_seconds=120.0, service_seconds=35.0)
    assert cost.total_seconds == 155.0


@pytest.mark.parametrize(
    "cost",
    [
        RouteCost(transit_seconds=-1.0, service_seconds=0.0),
        RouteCost(transit_seconds=0.0, service_seconds=-1.0),
    ],
)
def test_negative_route_cost_is_rejected(cost: RouteCost) -> None:
    with pytest.raises(ValueError):
        validate_nonnegative_cost(cost)
