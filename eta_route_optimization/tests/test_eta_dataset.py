import numpy as np
import pandas as pd
from eta_route_optimization.eta_dataset import _haversine_km, _time, build_city


def test_haversine_zero_for_same_point() -> None:
    result = _haversine_km(
        np.array([106.0]), np.array([10.0]), np.array([106.0]), np.array([10.0])
    )
    assert result[0] == 0.0


def test_haversine_is_symmetric() -> None:
    forward = _haversine_km(
        np.array([106.0]), np.array([10.0]), np.array([106.1]), np.array([10.2])
    )[0]
    backward = _haversine_km(
        np.array([106.1]), np.array([10.2]), np.array([106.0]), np.array([10.0])
    )[0]
    assert abs(forward - backward) < 1e-12


def test_mmdd_time_parser_preserves_day_boundary() -> None:
    parsed = _time(pd.Series(["08-31 23:59:59", "09-01 00:00:00"]))
    assert parsed.iloc[0] == pd.Timestamp("2022-08-31 23:59:59")
    assert parsed.iloc[1] == pd.Timestamp("2022-09-01 00:00:00")
    assert (parsed.iloc[1] - parsed.iloc[0]).total_seconds() == 1


def test_mmdd_time_parser_rejects_invalid_date() -> None:
    assert pd.isna(_time(pd.Series(["02-30 10:00:00"])).iloc[0])


def test_operational_day_group_does_not_use_target_delivery_date(tmp_path) -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["query", "pending"],
            "region_id": [1, 1],
            "city": ["Test", "Test"],
            "courier_id": [7, 7],
            "lng": [106.0, 106.1],
            "lat": [10.0, 10.1],
            "aoi_id": [1, 2],
            "aoi_type": ["A", "B"],
            "accept_time": ["08-31 23:00:00", "08-31 23:30:00"],
            "delivery_time": ["08-31 23:55:00", "09-01 00:10:00"],
            "delivery_gps_lng": [106.0, 106.1],
            "delivery_gps_lat": [10.0, 10.1],
            "ds": [831, 831],
        }
    )
    path = tmp_path / "city.parquet"
    frame.to_parquet(path, index=False)
    result, _ = build_city(path)
    assert result["order_id"].tolist() == ["pending"]
    assert result["route_day"].tolist() == [831]
    assert result["eta_minutes"].tolist() == [15.0]


def test_all_observable_tasks_are_kept_without_future_horizon_filter(tmp_path) -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["query", "long", "short"],
            "region_id": [1, 1, 1],
            "city": ["Test", "Test", "Test"],
            "courier_id": [7, 7, 7],
            "lng": [106.0, 106.2, 106.1],
            "lat": [10.0, 10.2, 10.1],
            "aoi_id": [1, 3, 2],
            "aoi_type": ["A", "C", "B"],
            "accept_time": ["08-31 08:00:00", "08-31 08:30:00", "08-31 08:45:00"],
            "delivery_time": ["08-31 09:00:00", "08-31 12:00:00", "08-31 09:15:00"],
            "delivery_gps_lng": [106.0, 106.2, 106.1],
            "delivery_gps_lat": [10.0, 10.2, 10.1],
            "ds": [831, 831, 831],
        }
    )
    path = tmp_path / "city.parquet"
    frame.to_parquet(path, index=False)
    result, _ = build_city(path)
    assert result["order_id"].tolist() == ["short", "long"]
    assert result["pending_count_before_cap"].tolist() == [2, 2]
    assert result["pending_count"].tolist() == [2, 2]
    assert result["accept_rank"].tolist() == [1, 0]
    assert result["eta_minutes"].tolist() == [15.0, 180.0]
