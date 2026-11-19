"""Deterministic routing baselines for directed travel-time matrices.

Adapted from ``src/lastmile_data/baselines.py`` on 2026-11-16.  The functions
are copied into this independent project to avoid coupling the new protocol to
the station cold-start source tree.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise

CostMatrix = Mapping[str, Mapping[str, float]]


def validate_sequence(sequence: Sequence[str], stops: Sequence[str], depot: str) -> None:
    stop_set = set(stops)
    if not sequence or sequence[0] != depot:
        raise ValueError("sequence must start at the depot")
    if len(sequence) != len(stop_set):
        raise ValueError("sequence length must equal the number of unique stops")
    if len(set(sequence)) != len(sequence):
        raise ValueError("sequence must not contain duplicate stops")
    if set(sequence) != stop_set:
        raise ValueError("sequence must visit every stop exactly once")


def closed_tour_cost(sequence: Sequence[str], costs: CostMatrix) -> float:
    if not sequence:
        raise ValueError("sequence must not be empty")
    return sum(
        float(costs[left][right])
        for left, right in zip(sequence, [*sequence[1:], sequence[0]])
    )


def nearest_neighbor(costs: CostMatrix, depot: str) -> list[str]:
    if depot not in costs:
        raise KeyError(f"depot {depot!r} is absent from the cost matrix")
    remaining = set(costs) - {depot}
    sequence = [depot]
    while remaining:
        current = sequence[-1]
        chosen = min(remaining, key=lambda stop: (float(costs[current][stop]), stop))
        sequence.append(chosen)
        remaining.remove(chosen)
    return sequence


def directed_two_opt(
    sequence: Sequence[str], costs: CostMatrix, max_passes: int = 5
) -> list[str]:
    """Best-improvement directed 2-opt with a fixed pass limit.

    The pass limit is part of the method.  Returning a route does not imply
    global optimality or unrestricted local optimality.
    """

    if max_passes < 0:
        raise ValueError("max_passes must be non-negative")
    result = list(sequence)
    for _ in range(max_passes):
        size = len(result)
        reverse_arc_delta_prefix = [0.0]
        for left, right in pairwise(result):
            reverse_arc_delta_prefix.append(
                reverse_arc_delta_prefix[-1]
                + float(costs[right][left])
                - float(costs[left][right])
            )

        best_delta = -1e-9
        best_pair: tuple[int, int] | None = None
        for start in range(1, size - 1):
            before, first = result[start - 1], result[start]
            for end in range(start + 1, size):
                last, after = result[end], result[(end + 1) % size]
                delta = (
                    float(costs[before][last])
                    + float(costs[first][after])
                    - float(costs[before][first])
                    - float(costs[last][after])
                    + reverse_arc_delta_prefix[end]
                    - reverse_arc_delta_prefix[start]
                )
                if delta < best_delta:
                    best_delta = delta
                    best_pair = (start, end)
        if best_pair is None:
            break
        start, end = best_pair
        result[start : end + 1] = reversed(result[start : end + 1])
    return result
