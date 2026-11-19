import pandas as pd
from eta_route_optimization.deployment_benchmark import psi


def test_psi_is_zero_for_identical_distribution() -> None:
    values = pd.Series(range(100))
    assert abs(psi(values, values)) < 1e-12


def test_psi_detects_distribution_shift() -> None:
    reference = pd.Series(range(100))
    shifted = pd.Series(range(100, 200))
    assert psi(reference, shifted) > 0.25
