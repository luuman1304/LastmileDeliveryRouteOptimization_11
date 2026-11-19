from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceLevel(str, Enum):
    """Mức bằng chứng của một phát biểu trong nghiên cứu."""

    OBSERVED_DATA = "observed_data"
    PRIOR_RESEARCH = "prior_research"
    EXPERIMENTAL_HYPOTHESIS = "experimental_hypothesis"


@dataclass(frozen=True)
class ETAQueryKey:
    """Đơn vị nhóm tối thiểu của một truy vấn ETA trên LaDe-D."""

    city: str
    courier_id: int
    ds: int
    query_time: str


@dataclass(frozen=True)
class RouteCost:
    """Các thành phần chi phí phải được báo cáo riêng trước khi cộng."""

    transit_seconds: float
    service_seconds: float

    @property
    def total_seconds(self) -> float:
        return self.transit_seconds + self.service_seconds


def validate_nonnegative_cost(cost: RouteCost) -> None:
    if cost.transit_seconds < 0:
        raise ValueError("transit_seconds must be non-negative")
    if cost.service_seconds < 0:
        raise ValueError("service_seconds must be non-negative")
