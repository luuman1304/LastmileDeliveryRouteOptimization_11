import numpy as np
import pandas as pd
from eta_route_optimization.statistical_analysis import cluster_bootstrap_mean_ci


def test_cluster_bootstrap_preserves_constant_effect() -> None:
    frame = pd.DataFrame(
        {
            "city": ["A", "A", "A", "B"],
            "courier_id": [1, 1, 2, 3],
            "delta": [-2.0, -2.0, -2.0, -2.0],
        }
    )
    interval = cluster_bootstrap_mean_ci(
        frame, "delta", ["city", "courier_id"], seed=1, replicates=200
    )
    assert np.allclose(interval, [-2.0, -2.0])
