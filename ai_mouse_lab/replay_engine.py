from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Any

from .schema import normalize_session

FRAME_MS = 16


def trial_duration_ms(trial: dict[str, Any]) -> float:
    points = trial.get("points", [])
    point_end = float(points[-1]["t_ms"]) if isinstance(points, list) and points else 0.0
    click = trial.get("click", {})
    click_end = float(click.get("up_t_ms", click.get("down_t_ms", 0.0))) if isinstance(click, dict) else 0.0
    misses = trial.get("miss_clicks", [])
    miss_end = max(
        (float(item.get("up_t_ms", item.get("down_t_ms", 0.0))) for item in misses if isinstance(item, dict)),
        default=0.0,
    ) if isinstance(misses, list) else 0.0
    return max(16.0, point_end, click_end, miss_end)


def visible_points(trial: dict[str, Any], elapsed_ms: float, normalized_duration_ms: float | None = None) -> list[dict[str, float]]:
    points = trial.get("points", [])
    if not isinstance(points, list) or not points:
        return []
    source_duration = trial_duration_ms(trial)
    source_elapsed = float(elapsed_ms)
    if normalized_duration_ms is not None:
        source_elapsed = source_elapsed * source_duration / max(1.0, float(normalized_duration_ms))
    times = [float(point["t_ms"]) for point in points]
    end = bisect_right(times, source_elapsed)
    return points[: max(1, end)]


@dataclass
class ReplayTimeline:
    session_a: dict[str, Any]
    session_b: dict[str, Any]
    trial_index: int = 0
    elapsed_ms: float = 0.0
    equal_duration: bool = False

    def __post_init__(self) -> None:
        self.session_a = normalize_session(self.session_a)
        self.session_b = normalize_session(self.session_b)
        if self.count == 0:
            raise ValueError("Replay requires at least one valid A/B trial")

    @property
    def count(self) -> int:
        return min(len(self.session_a["trials"]), len(self.session_b["trials"]))

    @property
    def current_a(self) -> dict[str, Any]:
        return self.session_a["trials"][self.trial_index]

    @property
    def current_b(self) -> dict[str, Any]:
        return self.session_b["trials"][self.trial_index]

    @property
    def duration_ms(self) -> float:
        return max(trial_duration_ms(self.current_a), trial_duration_ms(self.current_b))

    def points(self) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
        normalized = self.duration_ms if self.equal_duration else None
        return (
            visible_points(self.current_a, self.elapsed_ms, normalized),
            visible_points(self.current_b, self.elapsed_ms, normalized),
        )

    def reset(self) -> None:
        self.trial_index = 0
        self.elapsed_ms = 0.0

    def change_trial(self, delta: int) -> None:
        self.trial_index = max(0, min(self.count - 1, self.trial_index + int(delta)))
        self.elapsed_ms = 0.0

    def advance(self, delta_ms: float) -> bool:
        """Advance time. Returns True when the complete session is finished."""
        self.elapsed_ms += max(0.0, float(delta_ms))
        while self.elapsed_ms >= self.duration_ms:
            overflow = self.elapsed_ms - self.duration_ms
            if self.trial_index >= self.count - 1:
                self.elapsed_ms = self.duration_ms
                return True
            self.trial_index += 1
            self.elapsed_ms = overflow
        return False
