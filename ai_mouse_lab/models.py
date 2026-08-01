from __future__ import annotations

from typing import Any

from .metrics import derive_trial
from .schema import normalize_session, normalize_trial as _normalize_trial, normalize_trials as _normalize_trials


def normalize_trial(value: Any, index: int = 0) -> dict[str, Any] | None:
    trial = _normalize_trial(value, index)
    if trial is None:
        return None
    if not trial["derived"] and len(trial["points"]) >= 2:
        try:
            trial["derived"] = derive_trial(trial["target"], trial["start"], trial["points"], trial["click"])
        except (TypeError, ValueError, KeyError):
            trial["derived"] = {}
    return trial


def normalize_trials(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("trials", [])
    if not isinstance(value, list):
        return []

    # Fast path for current schema data. Replay calls this every frame, so avoid
    # rebuilding already-valid trials.
    if value and all(
        isinstance(trial, dict)
        and isinstance(trial.get("target"), dict)
        and isinstance(trial.get("start"), dict)
        and isinstance(trial.get("points"), list)
        and all(isinstance(point, dict) for point in trial.get("points", []))
        and isinstance(trial.get("click"), dict)
        and isinstance(trial.get("derived"), dict)
        for trial in value
    ):
        return value

    output: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        trial = normalize_trial(raw, index)
        if trial is not None:
            output.append(trial)
    return output


def normalize_replay_session(value: Any) -> dict[str, Any]:
    session = normalize_session(value)
    session["trials"] = normalize_trials(session["trials"])
    session["trial_count"] = len(session["trials"])
    return session


def trial_duration_ms(trial: dict[str, Any]) -> float:
    normalized = normalize_trial(trial)
    if normalized is None:
        return 0.0
    points = normalized["points"]
    point_end = float(points[-1]["t_ms"]) if points else 0.0
    click = normalized["click"]
    click_end = max(float(click.get("down_t_ms", 0.0)), float(click.get("up_t_ms", 0.0)))
    miss_end = max(
        (
            max(float(item.get("down_t_ms", 0.0)), float(item.get("up_t_ms", 0.0)))
            for item in normalized.get("miss_clicks", [])
            if isinstance(item, dict)
        ),
        default=0.0,
    )
    return max(point_end, click_end, miss_end)


def visible_points(trial: dict[str, Any], elapsed_ms: float) -> list[dict[str, float]]:
    normalized = normalize_trial(trial)
    if normalized is None or not normalized["points"]:
        return []
    visible = [point for point in normalized["points"] if float(point["t_ms"]) <= float(elapsed_ms)]
    return visible or [normalized["points"][0]]


__all__ = [
    "normalize_replay_session",
    "normalize_trial",
    "normalize_trials",
    "trial_duration_ms",
    "visible_points",
]
