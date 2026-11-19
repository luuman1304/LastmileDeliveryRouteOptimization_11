from eta_route_optimization.route_metrics import evaluate_order


def test_route_metrics_are_perfect_for_identical_order() -> None:
    result = evaluate_order([1, 2, 3], [1, 2, 3])
    assert result == {"hr_at_3": 1.0, "krc": 1.0, "lsd": 0.0, "edit_distance": 0.0}


def test_reversed_order_has_negative_kendall() -> None:
    result = evaluate_order([3, 2, 1], [1, 2, 3])
    assert result["krc"] == -1.0
