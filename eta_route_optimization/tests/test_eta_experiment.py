import numpy as np
import pandas as pd
from eta_route_optimization.eta_experiment import metrics, set_training_categories


def test_eta_metrics_are_zero_for_exact_prediction() -> None:
    result = metrics(np.array([10.0, 30.0]), np.array([10.0, 30.0]))
    assert result["mae_minutes"] == 0
    assert result["rmse_minutes"] == 0
    assert result["acc_at_20"] == 1


def test_eta_metrics_do_not_cap_predictions_at_120_minutes() -> None:
    result = metrics(np.array([180.0]), np.array([180.0]))
    assert result["mae_minutes"] == 0


def test_city_vocabulary_is_fit_from_training_only() -> None:
    train = pd.DataFrame({"city": ["A", "B"]})
    validation = pd.DataFrame({"city": ["B", "C"]})
    test = pd.DataFrame({"city": ["D"]})
    vocabulary = set_training_categories(train, validation, test)
    assert vocabulary == ["A", "B", "__UNKNOWN__"]
    assert validation["city"].astype(str).tolist() == ["B", "__UNKNOWN__"]
    assert test["city"].astype(str).tolist() == ["__UNKNOWN__"]
