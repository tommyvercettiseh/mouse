from __future__ import annotations

import math
import random
from typing import Any

from .metrics import click_position, stats


def target_size_band(radius: float) -> str:
    if radius <= 18:
        return "small"
    if radius <= 28:
        return "medium"
    return "large"


def _sample_from_trial(trial: dict[str, Any]) -> dict[str, float] | None:
    target = trial.get("target")
    click = trial.get("click")
    points = trial.get("points", [])
    if not isinstance(target, dict) or not isinstance(click, dict):
        return None
    if not isinstance(points, list):
        points = []
    try:
        radius = max(1.0, float(target["radius"]))
        if trial.get("click_position_source") == "mouse_down":
            click_x = float(click["x"])
            click_y = float(click["y"])
        else:
            click_x, click_y = click_position(points, click)
        dx = click_x - float(target["x"])
        dy = click_y - float(target["y"])
    except (KeyError, TypeError, ValueError):
        return None
    distance = math.hypot(dx, dy)
    return {
        "radius": radius,
        "x_ratio": dx / radius,
        "y_ratio": dy / radius,
        "radial_ratio": distance / radius,
        "edge_padding_ratio": 1.0 - distance / radius,
        "angle_rad": math.atan2(dy, dx),
    }


def build_click_model(
    trials: list[dict[str, Any]],
    max_samples: int = 1200,
) -> dict[str, Any]:
    samples: list[dict[str, float]] = []
    for trial in trials:
        if trial.get("capture_mode", "normal") != "normal":
            continue
        sample = _sample_from_trial(trial)
        if sample is not None:
            samples.append(sample)
    samples = samples[-max_samples:]

    bands: dict[str, list[dict[str, float]]] = {
        "small": [],
        "medium": [],
        "large": [],
    }
    for sample in samples:
        bands[target_size_band(sample["radius"])].append(sample)

    def summarize(group: list[dict[str, float]]) -> dict[str, Any]:
        return {
            "sample_count": len(group),
            "x_ratio": stats([item["x_ratio"] for item in group]),
            "y_ratio": stats([item["y_ratio"] for item in group]),
            "radial_ratio": stats([item["radial_ratio"] for item in group]),
            "edge_padding_ratio": stats(
                [item["edge_padding_ratio"] for item in group]
            ),
            "near_edge_rate": round(
                sum(item["radial_ratio"] >= 0.72 for item in group)
                / max(1, len(group)),
                4,
            ),
            "outside_rate": round(
                sum(item["radial_ratio"] > 1.0 for item in group)
                / max(1, len(group)),
                4,
            ),
            "samples": [
                {
                    "x_ratio": round(item["x_ratio"], 6),
                    "y_ratio": round(item["y_ratio"], 6),
                    "radial_ratio": round(item["radial_ratio"], 6),
                }
                for item in group[-300:]
            ],
        }

    return {
        "sample_count": len(samples),
        "overall": summarize(samples),
        "by_target_size": {
            name: summarize(group)
            for name, group in bands.items()
        },
    }


def sample_click_offset(
    click_model: dict[str, Any],
    radius: float,
    rng: random.Random,
    *,
    allow_outside: bool = False,
) -> tuple[float, float]:
    band = target_size_band(radius)
    by_size = (
        click_model.get("by_target_size", {})
        if isinstance(click_model, dict)
        else {}
    )
    selected = by_size.get(band, {}) if isinstance(by_size, dict) else {}
    overall = click_model.get("overall", {}) if isinstance(click_model, dict) else {}
    source = (
        selected
        if int(selected.get("sample_count", 0) or 0) >= 8
        else overall
    )
    samples = source.get("samples", []) if isinstance(source, dict) else []

    if isinstance(samples, list) and samples:
        base = rng.choice(samples)
        x_ratio = float(base.get("x_ratio", 0.0)) + rng.gauss(0.0, 0.025)
        y_ratio = float(base.get("y_ratio", 0.0)) + rng.gauss(0.0, 0.025)
    else:
        x_stats = source.get("x_ratio", {}) if isinstance(source, dict) else {}
        y_stats = source.get("y_ratio", {}) if isinstance(source, dict) else {}
        x_ratio = rng.gauss(
            float(x_stats.get("mean", 0.0) or 0.0),
            max(0.08, float(x_stats.get("stdev", 0.22) or 0.22)),
        )
        y_ratio = rng.gauss(
            float(y_stats.get("mean", 0.0) or 0.0),
            max(0.08, float(y_stats.get("stdev", 0.22) or 0.22)),
        )

    radial = math.hypot(x_ratio, y_ratio)
    limit = 1.08 if allow_outside else 0.96
    if radial > limit:
        scale = limit / radial
        x_ratio *= scale
        y_ratio *= scale
    return x_ratio * radius, y_ratio * radius
