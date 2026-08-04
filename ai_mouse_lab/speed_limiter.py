from __future__ import annotations

import math
from bisect import bisect_right
from typing import Any, Iterable

DEFAULT_SPEED_CAP_PX_S = 11_000.0
DEFAULT_SAMPLE_MS = 8.0
MIN_CORRECTION_STEPS = 2
ROUNDING_SAFETY = 1.001


def segment_speed_px_s(first: dict[str, Any], second: dict[str, Any]) -> float:
    dt_ms = float(second["t_ms"]) - float(first["t_ms"])
    if dt_ms <= 0.0:
        return math.inf
    distance = math.hypot(
        float(second["x"]) - float(first["x"]),
        float(second["y"]) - float(first["y"]),
    )
    return distance / dt_ms * 1000.0


def maximum_segment_speed_px_s(points: Iterable[dict[str, Any]]) -> float:
    source = list(points)
    return max(
        (
            segment_speed_px_s(first, second)
            for first, second in zip(source, source[1:])
        ),
        default=0.0,
    )


def _ceil_millisecond(value: float) -> float:
    return math.ceil((value - 1e-12) * 1000.0) / 1000.0


def _map_time(
    original_times: list[float],
    retimed_times: list[float],
    value: float,
) -> float:
    if value <= original_times[0]:
        return retimed_times[0] + value - original_times[0]
    if value >= original_times[-1]:
        return retimed_times[-1] + value - original_times[-1]

    index = max(0, bisect_right(original_times, value) - 1)
    original_span = original_times[index + 1] - original_times[index]
    if original_span <= 0.0:
        return retimed_times[index + 1]
    fraction = (value - original_times[index]) / original_span
    return retimed_times[index] + (
        retimed_times[index + 1] - retimed_times[index]
    ) * fraction


def _mapped_event(
    event: dict[str, Any],
    original_times: list[float],
    retimed_times: list[float],
) -> dict[str, Any]:
    mapped = dict(event)
    for key in ("down_t_ms", "up_t_ms"):
        if key in mapped:
            mapped[key] = round(
                _map_time(original_times, retimed_times, float(mapped[key])),
                3,
            )
    return mapped


def retime_route_without_jumps(
    points: list[dict[str, Any]],
    click: dict[str, Any],
    misses: list[dict[str, Any]] | None = None,
    *,
    cap_px_s: float = DEFAULT_SPEED_CAP_PX_S,
    sample_ms: float = DEFAULT_SAMPLE_MS,
) -> tuple[
    list[dict[str, float]],
    dict[str, Any],
    list[dict[str, Any]],
    bool,
]:
    """Retimes only impossible segments while preserving route geometry.

    Over-limit segments are split across multiple timestamped points. Their delay is
    carried into every later point and event, so no remaining distance can be caught
    up in the last step. Original control points and the exact endpoint stay intact.
    """
    if cap_px_s <= 0.0:
        raise ValueError("cap_px_s must be positive")
    if sample_ms <= 0.0:
        raise ValueError("sample_ms must be positive")

    copied_points = [dict(point) for point in points]
    copied_click = dict(click)
    copied_misses = [dict(miss) for miss in (misses or [])]
    if len(points) < 2:
        return copied_points, copied_click, copied_misses, False

    original = [
        {
            "t_ms": float(point["t_ms"]),
            "x": float(point["x"]),
            "y": float(point["y"]),
        }
        for point in points
    ]
    for first, second in zip(original, original[1:]):
        if second["t_ms"] <= first["t_ms"]:
            raise ValueError("Route timestamps must be strictly increasing")

    original_times = [point["t_ms"] for point in original]
    output: list[dict[str, float]] = [dict(original[0])]
    original_endpoint_indexes = [0]
    changed = False

    for first, second in zip(original, original[1:]):
        original_dt = second["t_ms"] - first["t_ms"]
        distance = math.hypot(
            second["x"] - first["x"],
            second["y"] - first["y"],
        )
        required_dt = distance / cap_px_s * 1000.0
        segment_start = float(output[-1]["t_ms"])

        if required_dt <= original_dt + 1e-12:
            output.append(
                {
                    "t_ms": round(segment_start + original_dt, 3),
                    "x": second["x"],
                    "y": second["y"],
                }
            )
            original_endpoint_indexes.append(len(output) - 1)
            continue

        changed = True
        steps = max(
            MIN_CORRECTION_STEPS,
            int(math.ceil(required_dt / sample_ms)),
        )
        duration = max(
            required_dt * ROUNDING_SAFETY,
            steps * sample_ms,
        )

        for step in range(1, steps + 1):
            fraction = step / steps
            output.append(
                {
                    "t_ms": _ceil_millisecond(
                        segment_start + duration * fraction
                    ),
                    "x": first["x"]
                    + (second["x"] - first["x"]) * fraction,
                    "y": first["y"]
                    + (second["y"] - first["y"]) * fraction,
                }
            )
        output[-1]["x"] = second["x"]
        output[-1]["y"] = second["y"]
        original_endpoint_indexes.append(len(output) - 1)

    if not changed:
        return copied_points, copied_click, copied_misses, False

    # Rounding to milliseconds must never put a segment microscopically above the cap.
    # Any safety delay is carried forward instead of being recovered by a later jump.
    safe_output = [dict(output[0])]
    carried_delay = 0.0
    for point in output[1:]:
        candidate = dict(point)
        candidate["t_ms"] = round(
            float(candidate["t_ms"]) + carried_delay,
            3,
        )
        previous = safe_output[-1]
        distance = math.hypot(
            candidate["x"] - previous["x"],
            candidate["y"] - previous["y"],
        )
        minimum_time = (
            float(previous["t_ms"])
            + distance / cap_px_s * 1000.0
        )
        if float(candidate["t_ms"]) < minimum_time - 1e-12:
            corrected = _ceil_millisecond(minimum_time)
            carried_delay += corrected - float(candidate["t_ms"])
            candidate["t_ms"] = corrected
        safe_output.append(candidate)

    retimed_original_times = [
        float(safe_output[index]["t_ms"])
        for index in original_endpoint_indexes
    ]
    mapped_click = _mapped_event(
        copied_click,
        original_times,
        retimed_original_times,
    )
    mapped_misses = [
        _mapped_event(miss, original_times, retimed_original_times)
        for miss in copied_misses
    ]

    original_down = float(click.get("down_t_ms", original_times[-1]))
    original_up = float(click.get("up_t_ms", original_down))
    hold_ms = max(0.0, original_up - original_down)
    route_end = float(safe_output[-1]["t_ms"])
    mapped_down = max(
        route_end,
        float(mapped_click.get("down_t_ms", route_end)),
    )
    mapped_click["down_t_ms"] = round(mapped_down, 3)
    mapped_click["up_t_ms"] = round(
        max(
            float(mapped_click.get("up_t_ms", mapped_down)),
            mapped_down + hold_ms,
        ),
        3,
    )

    return safe_output, mapped_click, mapped_misses, True
