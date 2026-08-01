from __future__ import annotations

from typing import Any


def _point(value: Any, fallback_t: float = 0.0) -> dict[str, float] | None:
    if isinstance(value, dict):
        try:
            return {
                "t_ms": float(value.get("t_ms", fallback_t) or fallback_t),
                "x": float(value.get("x", 0.0) or 0.0),
                "y": float(value.get("y", 0.0) or 0.0),
            }
        except (TypeError, ValueError):
            return None
    if isinstance(value, (list, tuple)):
        try:
            if len(value) >= 3:
                return {"t_ms": float(value[0]), "x": float(value[1]), "y": float(value[2])}
            if len(value) >= 2:
                return {"t_ms": float(fallback_t), "x": float(value[0]), "y": float(value[1])}
        except (TypeError, ValueError):
            return None
    return None


def _xy_object(value: Any, *, radius: float | None = None, index: int | None = None) -> dict[str, float | int]:
    output: dict[str, float | int] = {}
    if isinstance(value, dict):
        try:
            output["x"] = float(value.get("x", 0.0) or 0.0)
            output["y"] = float(value.get("y", 0.0) or 0.0)
        except (TypeError, ValueError):
            output.update(x=0.0, y=0.0)
        if "radius" in value:
            try:
                output["radius"] = float(value.get("radius", radius or 0.0) or 0.0)
            except (TypeError, ValueError):
                pass
        if "index" in value:
            try:
                output["index"] = int(value.get("index", index or 0) or 0)
            except (TypeError, ValueError):
                pass
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            output.update(x=float(value[0]), y=float(value[1]))
        except (TypeError, ValueError):
            output.update(x=0.0, y=0.0)
    else:
        output.update(x=0.0, y=0.0)
    if radius is not None and "radius" not in output:
        output["radius"] = float(radius)
    if index is not None and "index" not in output:
        output["index"] = int(index)
    return output


def _click(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        result: dict[str, float] = {}
        for key in ("down_t_ms", "up_t_ms", "x", "y"):
            try:
                result[key] = float(value.get(key, 0.0) or 0.0)
            except (TypeError, ValueError):
                result[key] = 0.0
        return result
    if isinstance(value, (list, tuple)):
        values = list(value) + [0.0, 0.0, 0.0, 0.0]
        try:
            return {
                "down_t_ms": float(values[0]),
                "up_t_ms": float(values[1]),
                "x": float(values[2]),
                "y": float(values[3]),
            }
        except (TypeError, ValueError):
            pass
    return {"down_t_ms": 0.0, "up_t_ms": 0.0, "x": 0.0, "y": 0.0}


def _trial(value: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    target_raw = value.get("target", {})
    radius = 26.0
    if isinstance(target_raw, dict):
        try:
            radius = float(target_raw.get("radius", 26.0) or 26.0)
        except (TypeError, ValueError):
            pass
    points: list[dict[str, float]] = []
    for point_index, raw in enumerate(value.get("points", []) if isinstance(value.get("points", []), list) else []):
        normalized = _point(raw, float(point_index * 8))
        if normalized is not None:
            points.append(normalized)
    points.sort(key=lambda item: item["t_ms"])
    return {
        **value,
        "target": _xy_object(target_raw, radius=radius, index=index),
        "start": _xy_object(value.get("start", {})),
        "points": points,
        "click": _click(value.get("click", {})),
        "miss_clicks": [
            _click(item) for item in value.get("miss_clicks", [])
        ] if isinstance(value.get("miss_clicks", []), list) else [],
    }


def _session(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        source_trials = value
        base: dict[str, Any] = {}
    elif isinstance(value, dict):
        source_trials = value.get("trials", [])
        base = dict(value)
    else:
        source_trials = []
        base = {}
    trials: list[dict[str, Any]] = []
    if isinstance(source_trials, list):
        for index, raw in enumerate(source_trials):
            normalized = _trial(raw, index)
            if normalized is not None:
                trials.append(normalized)
    base["trials"] = trials
    return base


def apply_patch(original_app: Any) -> None:
    previous_toggle = original_app.App.replay_toggle
    previous_refresh = original_app.App.refresh_results

    def normalize_replay_data(self: Any) -> int:
        self.replay_a = _session(getattr(self, "replay_a", {}))
        self.replay_b = _session(getattr(self, "replay_b", {}))
        return min(len(self.replay_a["trials"]), len(self.replay_b["trials"]))

    def replay_toggle(self: Any) -> None:
        count = normalize_replay_data(self)
        if count == 0:
            if hasattr(self, "replay_trial_label"):
                self.replay_trial_label.configure(text="Geen geldige A/B-trials gevonden")
            return
        previous_toggle(self)

    def refresh_results(self: Any) -> None:
        previous_refresh(self)
        count = normalize_replay_data(self)
        if count and hasattr(self, "replay_trial_label"):
            self.replay_trial_label.configure(text=f"Laatste Aim Lab-opname · {count} targets")
        if count and hasattr(self, "replay_draw"):
            self.replay_draw()

    original_app.App.normalize_replay_data = normalize_replay_data
    original_app.App.replay_toggle = replay_toggle
    original_app.App.refresh_results = refresh_results
