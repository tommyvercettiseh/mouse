from __future__ import annotations

import math
import random
from typing import Any

from .metrics import derive_trial
from .schema import SCHEMA_VERSION


def _feature(profile: dict[str, Any], name: str, key: str, default: float) -> float:
    try:
        return float(profile.get("features", {}).get(name, {}).get(key, default))
    except (TypeError, ValueError, AttributeError):
        return default


def _candidate_templates(profile: dict[str, Any], distance: float, radius: float, angle: float) -> list[dict[str, Any]]:
    candidates: list[tuple[float, dict[str, Any]]] = []
    templates = profile.get("route_templates", [])
    if not isinstance(templates, list):
        return []
    for template in templates:
        if not isinstance(template, dict):
            continue
        try:
            template_distance = max(1.0, float(template["distance_px"]))
            template_angle = float(template.get("angle", angle))
            angle_cost = abs((angle - template_angle + math.pi) % (2 * math.pi) - math.pi) / math.pi
            cost = abs(math.log(max(distance, 1.0) / template_distance)) * 2.6
            cost += abs(float(template.get("radius", radius)) - radius) / 22.0
            cost += angle_cost * 0.55
            efficiency = float(template.get("path_efficiency", 0.9))
            if not 0.55 <= efficiency <= 1.02:
                cost += 4.0
            candidates.append((cost, template))
        except (KeyError, TypeError, ValueError):
            continue
    candidates.sort(key=lambda item: item[0])
    return [template for _, template in candidates[:12]]


def generate_trial(
    item: dict[str, Any],
    profile: dict[str, Any],
    rng: random.Random,
    session_scale: float = 1.0,
) -> dict[str, Any]:
    sx, sy = map(float, item["start"])
    tx, ty = map(float, item["target"])
    radius = float(item["radius"])
    dx, dy = tx - sx, ty - sy
    distance = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / distance, dy / distance
    px, py = -uy, ux
    angle = math.atan2(dy, dx)

    candidates = _candidate_templates(profile, distance, radius, angle)
    template = rng.choice(candidates[: min(5, len(candidates))]) if candidates else None

    movement_median = max(120.0, _feature(profile, "movement_time_ms", "median", 650.0))
    movement_stdev = max(35.0, _feature(profile, "movement_time_ms", "stdev", 140.0))
    reaction_median = max(8.0, _feature(profile, "reaction_ms", "median", 75.0))
    reaction_stdev = max(8.0, _feature(profile, "reaction_ms", "stdev", 28.0))
    click_delay_median = max(15.0, _feature(profile, "click_delay_ms", "median", 80.0))
    click_delay_stdev = max(8.0, _feature(profile, "click_delay_ms", "stdev", 30.0))
    hold_median = max(35.0, _feature(profile, "hold_ms", "median", 95.0))
    hold_stdev = max(6.0, _feature(profile, "hold_ms", "stdev", 18.0))
    overshoot_median = max(0.0, _feature(profile, "overshoot_px", "median", 0.0))
    correction_mean = max(0.0, _feature(profile, "correction_count", "mean", 0.0))

    distance_factor = 0.62 + 0.38 * min(1.5, distance / 600.0)
    radius_factor = 1.08 if radius <= 18 else 1.0 if radius <= 28 else 0.94
    movement_ms = max(
        100.0,
        rng.gauss(movement_median * distance_factor * radius_factor * session_scale, movement_stdev * 0.38),
    )
    reaction_ms = max(5.0, rng.gauss(reaction_median * session_scale, reaction_stdev * 0.55))

    template_efficiency = float(template.get("path_efficiency", 0.9)) if template else 0.9
    side_scale = min(0.075, max(0.008, (1.0 - min(0.995, template_efficiency)) * 0.35))
    max_side = max(3.0, min(distance * 0.10, 58.0 if distance > 350 else 24.0))
    bend = max(-max_side, min(max_side, rng.gauss(0.0, distance * side_scale)))
    early_bias = rng.gauss(0.0, min(max_side * 0.35, 12.0))

    measured_overshoot_rate = float(profile.get("overshoot_rate", 0.0) or 0.0)
    overshoot_probability = min(0.35, max(0.01, measured_overshoot_rate))
    overshoot = rng.random() < overshoot_probability
    overshoot_px = max(1.0, rng.gauss(overshoot_median, max(1.0, overshoot_median * 0.35))) if overshoot else 0.0
    overshoot_px = min(overshoot_px, max(4.0, radius * 0.8))
    correction = rng.random() < min(0.50, max(0.04, correction_mean / 2.0)) or overshoot

    points: list[dict[str, float]] = []
    t_ms = 0.0
    while t_ms < reaction_ms:
        t_ms += max(7.0, rng.gauss(12.0, 3.0))
        points.append({"t_ms": round(min(t_ms, reaction_ms), 3), "x": round(sx, 3), "y": round(sy, 3)})

    steps = max(28, min(120, int(movement_ms / 9.5)))
    for index in range(1, steps + 1):
        u = index / steps
        ease = 10 * u**3 - 15 * u**4 + 6 * u**5
        along = ease * (distance + overshoot_px)
        side = math.sin(math.pi * u) * bend
        side += math.sin(2 * math.pi * u) * early_bias * (1.0 - u)
        if correction and u > 0.72:
            side *= max(0.0, 1.0 - (u - 0.72) / 0.28)
        jitter = rng.gauss(0.0, 0.35 if u < 0.75 else 0.55)
        x = sx + ux * along + px * (side + jitter)
        y = sy + uy * along + py * (side + jitter)
        t_ms += max(5.0, rng.gauss(movement_ms / steps, 2.0))
        points.append({"t_ms": round(t_ms, 3), "x": round(x, 3), "y": round(y, 3)})

    if overshoot:
        for fraction in (0.40, 0.68, 0.86, 1.0):
            t_ms += max(7.0, rng.gauss(13.0, 2.3))
            last = points[-1]
            points.append({
                "t_ms": round(t_ms, 3),
                "x": round(last["x"] + (tx - last["x"]) * fraction, 3),
                "y": round(last["y"] + (ty - last["y"]) * fraction, 3),
            })

    click_error_stdev = max(1.0, _feature(profile, "click_error_px", "stdev", radius * 0.18))
    error_x = rng.gauss(0.0, click_error_stdev)
    error_y = rng.gauss(0.0, click_error_stdev)
    error_length = math.hypot(error_x, error_y)
    if error_length > radius * 0.82:
        scale = radius * 0.82 / error_length
        error_x *= scale
        error_y *= scale

    click_delay_ms = max(10.0, rng.gauss(click_delay_median * session_scale, click_delay_stdev * 0.55))
    hold_ms = max(25.0, rng.gauss(hold_median, hold_stdev * 0.65))
    click_down_ms = max(points[-1]["t_ms"], reaction_ms) + click_delay_ms
    click = {
        "down_t_ms": round(click_down_ms, 3),
        "up_t_ms": round(click_down_ms + hold_ms, 3),
        "x": round(tx + error_x, 3),
        "y": round(ty + error_y, 3),
    }

    miss_clicks: list[dict[str, float]] = []
    miss_rate = float(profile.get("miss_count", 0) or 0) / max(float(profile.get("trial_count", 1) or 1), 1.0)
    if rng.random() < min(0.10, miss_rate):
        miss_angle = rng.uniform(0.0, math.tau)
        miss_distance = radius + rng.uniform(2.0, 8.0)
        miss_t = max(points[-1]["t_ms"], reaction_ms) + max(20.0, click_delay_ms * 0.55)
        miss_clicks.append({
            "down_t_ms": round(miss_t, 3),
            "up_t_ms": round(miss_t + hold_ms * 0.85, 3),
            "x": round(tx + math.cos(miss_angle) * miss_distance, 3),
            "y": round(ty + math.sin(miss_angle) * miss_distance, 3),
        })
        click["down_t_ms"] = round(miss_clicks[-1]["up_t_ms"] + rng.uniform(45.0, 105.0), 3)
        click["up_t_ms"] = round(click["down_t_ms"] + hold_ms, 3)

    target = {"index": int(item["index"]), "x": tx, "y": ty, "radius": radius}
    start = {"x": sx, "y": sy}
    derived = derive_trial(target, start, points, click)
    return {
        "schema_version": SCHEMA_VERSION,
        "capture_mode": "generated",
        "coordinate_space": "virtual_1920x1080",
        "target": target,
        "start": start,
        "points": points,
        "click": click,
        "miss_clicks": miss_clicks,
        "derived": derived,
    }


def simulate(plan: dict[str, Any], profile: dict[str, Any], seed: int | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else int(plan.get("seed", 1)) + 1)
    session_scale = rng.uniform(0.94, 1.08)
    targets = plan.get("targets", [])
    if not isinstance(targets, list):
        raise ValueError("plan.targets must be a list")
    return [generate_trial(item, profile, rng, session_scale) for item in targets]
