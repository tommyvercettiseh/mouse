from __future__ import annotations

import json
import os
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from . import __version__
from .continuous_generator import simulate
from .schema import VIRTUAL_HEIGHT, VIRTUAL_WIDTH

API_VERSION = 1
PROVIDER_NAME = "ai_mouse_lab"
PROFILE_ENV = "AI_MOUSE_LAB_PROFILE"
DATA_ENV = "AI_MOUSE_LAB_DATA_DIR"
DEFAULT_PROFILE_NAME = "master_profile.json"


class ProfileNotFoundError(FileNotFoundError):
    """Raised when no personal Mouse Lab profile can be resolved."""


def _expanded_path(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(os.fspath(value))))


def profile_candidates() -> tuple[Path, ...]:
    """Return supported profile locations in lookup order."""
    candidates: list[Path] = []
    explicit = os.environ.get(PROFILE_ENV)
    if explicit:
        candidates.append(_expanded_path(explicit))

    data_dir = os.environ.get(DATA_ENV)
    if data_dir:
        candidates.append(_expanded_path(data_dir) / "profiles" / DEFAULT_PROFILE_NAME)

    for variable in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates.append(_expanded_path(base) / "AI Mouse Lab" / "profiles" / DEFAULT_PROFILE_NAME)

    # Backwards-compatible source checkout location used by the current desktop app.
    candidates.append(Path(__file__).resolve().parents[1] / "data" / "profiles" / DEFAULT_PROFILE_NAME)

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def resolve_profile_path(profile_path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve an explicit profile or the first available standard profile."""
    if profile_path is not None:
        candidate = _expanded_path(profile_path)
        if candidate.is_dir():
            candidate = candidate / DEFAULT_PROFILE_NAME
        if candidate.is_file():
            return candidate
        raise ProfileNotFoundError(f"AI Mouse profile not found: {candidate}")

    for candidate in profile_candidates():
        if candidate.is_file():
            return candidate
    searched = "\n".join(f"  {path}" for path in profile_candidates())
    raise ProfileNotFoundError(
        "No AI Mouse profile found. Set AI_MOUSE_LAB_PROFILE or pass profile_path.\n"
        f"Searched:\n{searched}"
    )


def load_profile(profile_path: str | os.PathLike[str] | None = None) -> tuple[dict[str, Any], Path]:
    path = resolve_profile_path(profile_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"AI Mouse profile is not valid JSON: {path}") from exc
    if not isinstance(value, dict) or not value:
        raise ValueError(f"AI Mouse profile must be a non-empty JSON object: {path}")
    return value, path


def _point(value: Sequence[float], name: str) -> tuple[float, float]:
    if isinstance(value, (str, bytes)) or len(value) < 2:
        raise ValueError(f"{name} must contain x and y")
    return float(value[0]), float(value[1])


def _target_circle(
    target: Mapping[str, Any] | Sequence[float],
    target_radius: float | None,
    padding_px: float,
    random_generator: random.Random,
) -> tuple[float, float, float, dict[str, float]]:
    padding = max(0.0, float(padding_px))
    bounds: dict[str, float]

    if isinstance(target, Mapping):
        if all(key in target for key in ("left", "top", "right", "bottom")):
            left = float(target["left"])
            top = float(target["top"])
            right = float(target["right"])
            bottom = float(target["bottom"])
            if right <= left or bottom <= top:
                raise ValueError("target bounds must have positive width and height")
            bounds = {"left": left, "top": top, "right": right, "bottom": bottom}
            safe_left = left + padding
            safe_top = top + padding
            safe_right = right - padding
            safe_bottom = bottom - padding
            safe_width = safe_right - safe_left
            safe_height = safe_bottom - safe_top
            if safe_width <= 0 or safe_height <= 0:
                raise ValueError("padding_px leaves no clickable target area")

            shortest_side = min(safe_width, safe_height)
            radius = shortest_side * random_generator.uniform(0.18, 0.28)
            radius = max(min(shortest_side / 2.0, radius), min(1.0, shortest_side / 2.0))
            x_space = max(0.0, safe_width - radius * 2.0)
            y_space = max(0.0, safe_height - radius * 2.0)
            x = safe_left + radius + x_space * random_generator.betavariate(2.2, 2.2)
            y = safe_top + radius + y_space * random_generator.betavariate(2.2, 2.2)
            return x, y, radius, bounds
        elif "x" in target and "y" in target:
            x = float(target["x"])
            y = float(target["y"])
            raw_radius = float(target.get("radius", target_radius or 0.0))
            bounds = {
                "left": x - raw_radius,
                "top": y - raw_radius,
                "right": x + raw_radius,
                "bottom": y + raw_radius,
            }
        else:
            raise ValueError("target must contain x/y or left/top/right/bottom")
    else:
        x, y = _point(target, "target")
        if len(target) >= 3:
            raw_radius = float(target[2])
        elif target_radius is not None:
            raw_radius = float(target_radius)
        else:
            raise ValueError("target_radius is required for an x/y target")
        bounds = {
            "left": x - raw_radius,
            "top": y - raw_radius,
            "right": x + raw_radius,
            "bottom": y + raw_radius,
        }

    radius = raw_radius - padding
    if radius <= 0:
        raise ValueError("padding_px leaves no clickable target area")
    return x, y, radius, bounds


def _event_timeline(
    trial: Mapping[str, Any],
    *,
    scale_x: float,
    scale_y: float,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "type": "move",
            "t_ms": float(point["t_ms"]),
            "x": float(point["x"]) / scale_x,
            "y": float(point["y"]) / scale_y,
        }
        for point in trial["points"]
    ]

    clicks = list(trial.get("miss_clicks", [])) + [trial["click"]]
    for click in clicks:
        common = {
            "x": float(click["x"]) / scale_x,
            "y": float(click["y"]) / scale_y,
            "button": "left",
        }
        events.append({"type": "button_down", "t_ms": float(click["down_t_ms"]), **common})
        events.append({"type": "button_up", "t_ms": float(click["up_t_ms"]), **common})

    priority = {"move": 0, "button_down": 1, "button_up": 2}
    events.sort(key=lambda event: (event["t_ms"], priority[event["type"]]))
    return events


def create_plan(
    start: Sequence[float],
    target: Mapping[str, Any] | Sequence[float],
    *,
    target_radius: float | None = None,
    padding_px: float = 0.0,
    profile_path: str | os.PathLike[str] | None = None,
    profile: Mapping[str, Any] | None = None,
    seed: int | None = None,
    coordinate_size: Sequence[float] = (VIRTUAL_WIDTH, VIRTUAL_HEIGHT),
) -> dict[str, Any]:
    """Create a complete, executable mouse timeline for one target.

    The returned event list preserves generated reaction time, every route sample,
    click delay, mouse-down duration and any generated miss/recovery clicks.
    """
    if profile is not None and profile_path is not None:
        raise ValueError("pass profile or profile_path, not both")
    if profile is None:
        loaded_profile, resolved_path = load_profile(profile_path)
        profile_source: str | None = str(resolved_path)
    else:
        loaded_profile = dict(profile)
        if not loaded_profile:
            raise ValueError("profile must be a non-empty mapping")
        profile_source = None

    width, height = _point(coordinate_size, "coordinate_size")
    if width <= 0 or height <= 0:
        raise ValueError("coordinate_size must have positive width and height")
    scale_x = VIRTUAL_WIDTH / width
    scale_y = VIRTUAL_HEIGHT / height

    actual_seed = int(seed) if seed is not None else int.from_bytes(os.urandom(8), "big")
    target_generator = random.Random(actual_seed ^ 0x7A26E91D)
    start_x, start_y = _point(start, "start")
    target_x, target_y, radius, bounds = _target_circle(
        target,
        target_radius,
        padding_px,
        target_generator,
    )
    model_start_x = start_x * scale_x
    model_start_y = start_y * scale_y
    model_target_x = target_x * scale_x
    model_target_y = target_y * scale_y
    model_radius = radius * min(scale_x, scale_y)
    generator_plan = {
        "schema_version": 3,
        "seed": actual_seed,
        "targets": [
            {
                "index": 0,
                "start": [model_start_x, model_start_y],
                "target": [model_target_x, model_target_y],
                "radius": model_radius,
            }
        ],
    }
    trial = simulate(generator_plan, loaded_profile, seed=actual_seed)[0]
    events = _event_timeline(trial, scale_x=scale_x, scale_y=scale_y)

    return {
        "api_version": API_VERSION,
        "provider": PROVIDER_NAME,
        "provider_version": __version__,
        "seed": actual_seed,
        "profile_path": profile_source,
        "target_bounds": bounds,
        "padding_px": max(0.0, float(padding_px)),
        "coordinate_size": {"width": width, "height": height},
        "model_coordinate_size": {"width": VIRTUAL_WIDTH, "height": VIRTUAL_HEIGHT},
        "events": events,
        "duration_ms": max(float(event["t_ms"]) for event in events),
        "trial": trial,
    }


def manifest() -> dict[str, Any]:
    return {
        "api_version": API_VERSION,
        "name": PROVIDER_NAME,
        "version": __version__,
        "capabilities": [
            "timed_move_points",
            "reaction_delay",
            "click_delay",
            "click_hold",
            "target_padding",
            "overshoot",
            "corrections",
            "miss_recovery",
        ],
    }


class MouseProvider:
    api_version = API_VERSION
    name = PROVIDER_NAME
    version = __version__

    def manifest(self) -> dict[str, Any]:
        return manifest()

    def create_plan(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return create_plan(*args, **kwargs)


def get_provider() -> MouseProvider:
    return MouseProvider()


__all__ = [
    "API_VERSION",
    "MouseProvider",
    "ProfileNotFoundError",
    "create_plan",
    "get_provider",
    "load_profile",
    "manifest",
    "profile_candidates",
    "resolve_profile_path",
]
