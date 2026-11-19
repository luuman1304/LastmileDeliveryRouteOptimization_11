from __future__ import annotations

from collections.abc import Sequence


def hit_rate(predicted: Sequence[int], actual: Sequence[int], k: int = 3) -> float:
    count = min(k, len(actual))
    if count == 0:
        return float("nan")
    return len(set(predicted[:count]) & set(actual[:count])) / count


def kendall_rank_correlation(predicted: Sequence[int], actual: Sequence[int]) -> float:
    if len(actual) <= 1:
        return 1.0
    position = {value: index for index, value in enumerate(predicted)}
    concordant = 0
    discordant = 0
    for left in range(len(actual)):
        for right in range(left + 1, len(actual)):
            if position[actual[left]] < position[actual[right]]:
                concordant += 1
            else:
                discordant += 1
    return (concordant - discordant) / (concordant + discordant)


def location_square_deviation(predicted: Sequence[int], actual: Sequence[int]) -> float:
    if not actual:
        return float("nan")
    position = {value: index for index, value in enumerate(predicted)}
    return sum((index - position[value]) ** 2 for index, value in enumerate(actual)) / len(actual)


def edit_distance(predicted: Sequence[int], actual: Sequence[int]) -> int:
    previous = list(range(len(predicted) + 1))
    for row, left in enumerate(actual, start=1):
        current = [row]
        for column, right in enumerate(predicted, start=1):
            current.append(
                min(current[-1] + 1, previous[column] + 1, previous[column - 1] + int(left != right))
            )
        previous = current
    return previous[-1]


def evaluate_order(predicted: Sequence[int], actual: Sequence[int]) -> dict[str, float]:
    if set(predicted) != set(actual) or len(predicted) != len(actual):
        raise ValueError("predicted and actual routes must contain the same unique tasks")
    return {
        "hr_at_3": hit_rate(predicted, actual, 3),
        "krc": kendall_rank_correlation(predicted, actual),
        "lsd": location_square_deviation(predicted, actual),
        "edit_distance": float(edit_distance(predicted, actual)),
    }
