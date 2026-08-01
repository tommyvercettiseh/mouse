from __future__ import annotations

import math
import random
from typing import Any

from .click_model import sample_click_offset
from .metrics import derive_trial
from .schema import SCHEMA_VERSION


def _feature(profile: dict[str, Any], name: str, key: str, default: float) -> float:
    try:
        return float(profile.get("features", {}).get(name, {}).get(key, default))
    except (AttributeError, TypeError, ValueError):
        return default


def _candidate_templates(
    profile: dict[str, Any],
    distance: float,
    radius: float,
    angle: float,
) -> list[dict[str, Any]]:
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
            angle_cost = abs(
                (angle - template_angle + math.pi) % (2 * math.pi) - math.pi
            ) / math.pi
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


def _outside_click_offset(
    click_model: dict[str, Any],
    radius: float,
    rng: random.Random,
) -> tuple[float, float]:
    x, y = sample_click_offset(click_model, radius, rng, allow_outside=True)
    distance = math.hypot(x, y)
    if distance > radius:
        return x, y
    angle = math.atan2(y, x) if distance > 0 else rng.uniform(0.0, math.tau)
    outside_distance = radius + rng.uniform(1.5, 7.0)
    return math.cos(angle) * outside_distance, math.sin(angle) * outside_distance


def _append_correction(
    points: list[dict[str, float]],
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    start_t_ms: float,
    rng: random.Random,
) -> float:
    duration_ms = rng.uniform(65.0, 140.0)
    steps = max(6, int(duration_ms / 12.0))
    dx, dy = end_x - start_x, end_y - start_y
    distance = max(1.0, math.hypot(dx, dy))
    px, py = -dy / distance, dx / distance
    side = rng.gauss(0.0, min(4.0, distance * 0.08))
    t_ms = start_t_ms
    for index in range(1, steps + 1):
        u = index / steps
        ease = 3 * u**2 - 2 * u**3
        lateral = math.sin(math.pi * u) * side
        t_ms += duration_ms / steps
        points.append(
            {
                "t_ms": round(t_ms, 3),
                "x": round(start_x + dx * ease + px * lateral, 3),
                "y": round(start_y + dy * ease + py * lateral, 3),
            }
        )
    points[-1] = {
        "t_ms": round(t_ms, 3),
        "x": round(end_x, 3),
        "y": round(end_y, 3),
    }
    return t_ms


def generate_trial(
    item: dict[str, Any],
    profile: dict[str, Any],
    rng: random.Random,
    session_scale: float = 1.0,
) -> dict[str, Any]:
    sx, sy = map(float, item["start"])
    tx, ty = map(float, item["target"])
    radius = float(item["radius"])
    target_dx, target_dy = tx - sx, ty - sy
    target_distance = max(1.0, math.hypot(target_dx, target_dy))
    target_angle = math.atan2(target_dy, target_dx)

    candidates = _candidate_templates(profile, target_distance, radius, target_angle)
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

    distance_factor = 0.62 + 0.38 * min(1.5, target_distance / 600.0)
    radius_factor = 1.08 if radius <= 18 else 1.0 if radius <= 28 else 0.94
    movement_ms = max(
        100.0,
        rng.gauss(
            movement_median * distance_factor * radius_factor * session_scale,
            movement_stdev * 0.38,
        ),
    )
    reaction_ms = max(
        5.0,
        rng.gauss(reaction_median * session_scale, reaction_stdev * 0.55),
    )
    click_delay_ms = max(
        10.0,
        rng.gauss(click_delay_median * session_scale, click_delay_stdev * 0.55),
    )
    hold_ms = max(25.0, rng.gauss(hold_median, hold_stdev * 0.65))

    click_model = profile.get("click_model", {}) if isinstance(profile, dict) else {}
    click_offset_x, click_offset_y = sample_click_offset(click_model, radius, rng)
    click_x = tx + click_offset_x
    click_y = ty + click_offset_y

    miss_rate = float(profile.get("miss_count", 0) or 0) / max(
        float(profile.get("trial_count", 1) or 1),
        1.0,
    )
    will_miss = rng.random() < min(0.10, miss_rate)
    if will_miss:
        miss_offset_x, miss_offset_y = _outside_click_offset(click_model, radius, rng)
        route_end_x = tx + miss_offset_x
        route_end_y = ty + miss_offset_y
    else:
        route_end_x = click_x
        route_end_y = click_y

    route_dx, route_dy = route_end_x - sx, route_end_y - sy
    route_distance = max(1.0, math.hypot(route_dx, route_dy))
    ux, uy = route_dx / route_distance, route_dy / route_distance
    px, py = -uy, ux

    template_efficiency = float(template.get("path_efficiency", 0.9)) if template else 0.9
    side_scale = min(0.075, max(0.008, (1.0 - min(0.995, template_efficiency)) * 0.35))
    max_side = max(3.0, min(route_distance * 0.10, 58.0 if route_distance > 350 else 24.0))
    bend = max(-max_side, min(max_side, rng.gauss(0.0, route_distance * side_scale)))
    early_bias = rng.gauss(0.0, min(max_side * 0.35, 12.0))

    measured_overshoot_rate = float(profile.get("overshoot_rate", 0.0) or 0.0)
    overshoot_probability = min(0.35, max(0.01, measured_overshoot_rate))
    overshoot = rng.random() < overshoot_probability
    overshoot_px = (
        max(1.0, rng.gauss(overshoot_median, max(1.0, overshoot_median * 0.35)))
        if overshoot
        else 0.0
    )
    overshoot_px = min(overshoot_px, max(4.0, radius * 0.8))
    correction = rng.random() < min(0.50, max(0.04, correction_mean / 2.0)) or overshoot

    points: list[dict[str, float]] = [
        {"t_ms": 0.0, "x": round(sx, 3), "y": round(sy, 3)}
    ]
    t_ms = 0.0
    while t_ms < reaction_ms:
        t_ms += max(7.0, rng.gauss(12.0, 3.0))
        points.append(
            {
                "t_ms": round(min(t_ms, reaction_ms), 3),
                "x": round(sx, 3),
                "y": round(sy, 3),
            }
        )

    steps = max(28, min(120, int(movement_ms / 9.5)))
    for index in range(1, steps + 1):
        u = index / steps
        ease = 10 * u**3 - 15 * u**4 + 6 * u**5
        along = ease * (route_distance + overshoot_px)
        side = math.sin(math.pi * u) * bend
        side += math.sin(2 * math.pi * u) * early_bias * (1.0 - u)
        if correction and u > 0.72:
            side *= max(0.0, 1.0 - (u - 0.72) / 0.28)
        jitter_stdev = (0.35 if u < 0.75 else 0.55) * (1.0 - u)
        jitter = rng.gauss(0.0, jitter_stdev)
        x = sx + ux * along + px * (side + jitter)
        y = sy + uy * along + py * (side + jitter)
        t_ms += max(5.0, rng.gauss(movement_ms / steps, 2.0))
        points.append({"t_ms": round(t_ms, 3), "x": round(x, 3), "y": round(y, 3)})

    if overshoot:
        for fraction in (0.40, 0.68, 0.86, 1.0):
            t_ms += max(7.0, rng.gauss(13.0, 2.3))
            last = points[-1]
            points.append(
                {
                    "t_ms": round(t_ms, 3),
                    "x": round(last["x"] + (route_end_x - last["x"]) * fraction, 3),
                    "y": round(last["y"] + (route_end_y - last["y"]) * fraction, 3),
                }
            )
    else:
        points[-1] = {
            "t_ms": points[-1]["t_ms"],
            "x": round(route_end_x, 3),
            "y": round(route_end_y, 3),
        }

    miss_clicks: list[dict[str, float]] = []
    if will_miss:
        miss_down_ms = points[-1]["t_ms"] + max(10.0, click_delay_ms * 0.55)
        miss_up_ms = miss_down_ms + hold_ms * 0.85
        miss_clicks.append(
            {
                "down_t_ms": round(miss_down_ms, 3),
                "up_t_ms": round(miss_up_ms, 3),
                "x": round(route_end_x, 3),
                "y": round(route_end_y, 3),
            }
        )
        t_ms = _append_correction(
            points,
            route_end_x,
            route_end_y,
            click_x,
            click_y,
            miss_up_ms,
            rng,
        )
        click_down_ms = t_ms + max(10.0, click_delay_ms * 0.45)
    else:
        click_down_ms = max(points[-1]["t_ms"], reaction_ms) + click_delay_ms

    click = {
        "down_t_ms": round(click_down_ms, 3),
        "up_t_ms": round(click_down_ms + hold_ms, 3),
        "x": round(click_x, 3),
        "y": round(click_y, 3),
    }

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


def simulate(
    plan: dict[str, Any],
    profile: dict[str, Any],
    seed: int | None = None,
) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else int(plan.get("seed", 1)) + 1)
    session_scale = rng.uniform(0.94, 1.08)
    targets = plan.get("targets", [])
    if not isinstance(targets, list):
        raise ValueError("plan.targets must be a list")
    return [generate_trial(item, profile, rng, session_scale) for item in targets]
