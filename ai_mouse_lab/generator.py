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


def _context_key(distance: float, radius: float, angle: float) -> str:
    distance_band = "short" if distance < 260 else "medium" if distance < 650 else "long"
    target_band = "small" if radius <= 18 else "medium" if radius <= 28 else "large"
    degrees = (math.degrees(angle) + 360.0) % 360.0
    directions = (
        "right",
        "down_right",
        "down",
        "down_left",
        "left",
        "up_left",
        "up",
        "up_right",
    )
    index = int(((degrees + 22.5) % 360.0) // 45.0)
    return f"{distance_band}:{target_band}:{directions[index]}"


def _context(profile: dict[str, Any], distance: float, radius: float, angle: float) -> dict[str, Any]:
    contexts = profile.get("contexts", {}) if isinstance(profile, dict) else {}
    if not isinstance(contexts, dict):
        return {}
    value = contexts.get(_context_key(distance, radius, angle), {})
    return value if isinstance(value, dict) else {}


def _context_feature(
    profile: dict[str, Any],
    context: dict[str, Any],
    name: str,
    key: str,
    default: float,
) -> float:
    global_value = _feature(profile, name, key, default)
    try:
        count = max(0.0, float(context.get("trial_count", 0) or 0))
        local_value = float(context.get("features", {}).get(name, {}).get(key, global_value))
    except (AttributeError, TypeError, ValueError):
        return global_value
    weight = min(0.72, count / 18.0 * 0.72)
    return global_value * (1.0 - weight) + local_value * weight


def _context_rate(
    profile: dict[str, Any],
    context: dict[str, Any],
    global_name: str,
    context_name: str,
    default: float,
) -> float:
    try:
        global_value = float(profile.get(global_name, default) or 0.0)
    except (AttributeError, TypeError, ValueError):
        global_value = default
    try:
        count = max(0.0, float(context.get("trial_count", 0) or 0))
        local_value = float(context.get(context_name, global_value) or 0.0)
    except (AttributeError, TypeError, ValueError):
        return global_value
    weight = min(0.72, count / 18.0 * 0.72)
    return global_value * (1.0 - weight) + local_value * weight


def _template_shape(template: dict[str, Any] | None) -> list[dict[str, float]]:
    if not isinstance(template, dict):
        return []
    if int(template.get("shape_version", 0) or 0) != 1:
        return []
    raw_points = template.get("points", [])
    if not isinstance(raw_points, list):
        return []

    parsed: list[dict[str, float]] = []
    for point in raw_points:
        if not isinstance(point, dict):
            continue
        try:
            parsed.append(
                {
                    "t": max(0.0, min(1.0, float(point["t"]))),
                    "along": float(point["along"]),
                    "side": float(point["side"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    parsed.sort(key=lambda point: point["t"])
    if len(parsed) < 2:
        return []

    shape: list[dict[str, float]] = [{"t": 0.0, "along": 0.0, "side": 0.0}]
    for point in parsed:
        previous = shape[-1]
        if point["t"] <= previous["t"] + 1e-6:
            continue
        movement = math.hypot(
            point["along"] - previous["along"],
            point["side"] - previous["side"],
        )
        if movement < 0.0009 and point["t"] - previous["t"] < 0.075:
            continue
        shape.append(point)

    if len(shape) < 2:
        return []
    if shape[-1]["t"] < 1.0:
        shape.append({"t": 1.0, "along": 1.0, "side": 0.0})
    else:
        shape[-1] = {"t": 1.0, "along": 1.0, "side": 0.0}
    return shape


def _template_quality(template: dict[str, Any]) -> float:
    shape = _template_shape(template)
    if len(shape) < 3:
        return 0.0
    try:
        efficiency = float(template.get("path_efficiency", 0.0) or 0.0)
        duration = float(template.get("duration_ms", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not 0.58 <= efficiency <= 1.03 or not 55.0 <= duration <= 4200.0:
        return 0.0

    max_side = max(abs(point["side"]) for point in shape)
    min_along = min(point["along"] for point in shape)
    max_along = max(point["along"] for point in shape)
    if max_side > 0.38 or min_along < -0.30 or max_along > 1.55:
        return 0.0

    quality = 1.0
    quality -= max(0.0, 0.78 - efficiency) * 1.6
    quality -= max(0.0, max_side - 0.22) * 1.8
    stored = template.get("quality_score")
    if stored is not None:
        try:
            quality *= max(0.25, min(1.0, float(stored)))
        except (TypeError, ValueError):
            pass
    return max(0.05, min(1.0, quality))


def _candidate_templates(
    profile: dict[str, Any],
    distance: float,
    radius: float,
    angle: float,
) -> list[tuple[float, float, dict[str, Any]]]:
    candidates: list[tuple[float, float, dict[str, Any]]] = []
    templates = profile.get("route_templates", [])
    if not isinstance(templates, list):
        return []
    wanted_context = _context_key(distance, radius, angle)
    for template in templates:
        if not isinstance(template, dict):
            continue
        quality = _template_quality(template)
        if quality <= 0.0:
            continue
        try:
            template_distance = max(1.0, float(template["distance_px"]))
            template_angle = float(template.get("angle", angle))
            angle_cost = abs(
                (angle - template_angle + math.pi) % (2 * math.pi) - math.pi
            ) / math.pi
            cost = abs(math.log(max(distance, 1.0) / template_distance)) * 2.6
            cost += abs(float(template.get("radius", radius)) - radius) / 22.0
            cost += angle_cost * 0.65
            if template.get("context") == wanted_context:
                cost *= 0.72
            candidates.append((cost, quality, template))
        except (KeyError, TypeError, ValueError):
            continue
    candidates.sort(key=lambda item: item[0])
    return candidates[:16]


def _choose_template(
    candidates: list[tuple[float, float, dict[str, Any]]],
    rng: random.Random,
) -> dict[str, Any] | None:
    if not candidates:
        return None
    pool = candidates[: min(10, len(candidates))]
    weights = [
        max(1e-4, math.exp(-cost * 1.35) * quality**2.2)
        for cost, quality, _ in pool
    ]
    return rng.choices([item[2] for item in pool], weights=weights, k=1)[0]


def _interpolate_shape(
    shape: list[dict[str, float]],
    u: float,
) -> tuple[float, float]:
    if not shape:
        return u, 0.0
    clamped = max(0.0, min(1.0, u))
    if clamped <= shape[0]["t"]:
        return shape[0]["along"], shape[0]["side"]
    for first, second in zip(shape, shape[1:]):
        if clamped > second["t"]:
            continue
        duration = second["t"] - first["t"]
        if duration <= 0:
            return second["along"], second["side"]
        fraction = (clamped - first["t"]) / duration
        return (
            first["along"] + (second["along"] - first["along"]) * fraction,
            first["side"] + (second["side"] - first["side"]) * fraction,
        )
    return shape[-1]["along"], shape[-1]["side"]


def _time_fractions(steps: int, rng: random.Random) -> list[float]:
    increments = [
        max(0.42, min(1.85, rng.gauss(1.0, 0.24)))
        for _ in range(steps)
    ]
    total = sum(increments)
    cumulative = 0.0
    result: list[float] = []
    for increment in increments:
        cumulative += increment
        result.append(cumulative / total)
    result[-1] = 1.0
    return result


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
    fractions = _time_fractions(steps, rng)
    dx, dy = end_x - start_x, end_y - start_y
    distance = max(1.0, math.hypot(dx, dy))
    px, py = -dy / distance, dx / distance
    side = rng.gauss(0.0, min(4.0, distance * 0.08))
    for fraction in fractions:
        ease = 3 * fraction**2 - 2 * fraction**3
        lateral = math.sin(math.pi * fraction) * side
        t_ms = start_t_ms + duration_ms * fraction
        points.append(
            {
                "t_ms": round(t_ms, 3),
                "x": round(start_x + dx * ease + px * lateral, 3),
                "y": round(start_y + dy * ease + py * lateral, 3),
            }
        )
    points[-1] = {
        "t_ms": round(start_t_ms + duration_ms, 3),
        "x": round(end_x, 3),
        "y": round(end_y, 3),
    }
    return start_t_ms + duration_ms


def _append_profiled_route(
    points: list[dict[str, float]],
    *,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    start_t_ms: float,
    duration_ms: float,
    template: dict[str, Any] | None,
    rng: random.Random,
    overshoot_px: float,
    correction: bool,
) -> tuple[float, bool]:
    dx, dy = end_x - start_x, end_y - start_y
    distance = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / distance, dy / distance
    px, py = -uy, ux
    steps = max(24, min(150, int(duration_ms / 9.0)))
    fractions = _time_fractions(steps, rng)
    shape = _template_shape(template)

    if shape:
        side_variation = rng.uniform(0.91, 1.09)
        along_variation = rng.uniform(0.98, 1.02)
        for fraction in fractions:
            along_ratio, side_ratio = _interpolate_shape(shape, fraction)
            along = along_ratio * distance * along_variation
            side = side_ratio * distance * side_variation
            motion_strength = min(1.0, abs(along_ratio - 1.0) + abs(side_ratio) * 2.0)
            jitter = rng.gauss(
                0.0,
                0.16 * math.sin(math.pi * fraction) * max(0.18, motion_strength),
            )
            t_ms = start_t_ms + duration_ms * fraction
            points.append(
                {
                    "t_ms": round(t_ms, 3),
                    "x": round(start_x + ux * along + px * (side + jitter), 3),
                    "y": round(start_y + uy * along + py * (side + jitter), 3),
                }
            )
        points[-1] = {
            "t_ms": round(start_t_ms + duration_ms, 3),
            "x": round(end_x, 3),
            "y": round(end_y, 3),
        }
        return start_t_ms + duration_ms, True

    side_scale = 0.026 if distance < 260 else 0.020 if distance < 650 else 0.016
    max_side = max(3.0, min(distance * 0.09, 54.0 if distance > 350 else 22.0))
    bend = max(-max_side, min(max_side, rng.gauss(0.0, distance * side_scale)))
    early_bias = rng.gauss(0.0, min(max_side * 0.30, 10.0))

    for fraction in fractions:
        ease = 10 * fraction**3 - 15 * fraction**4 + 6 * fraction**5
        along = ease * (distance + overshoot_px)
        side = math.sin(math.pi * fraction) * bend
        side += math.sin(2 * math.pi * fraction) * early_bias * (1.0 - fraction)
        if correction and fraction > 0.72:
            side *= max(0.0, 1.0 - (fraction - 0.72) / 0.28)
        jitter = rng.gauss(0.0, (0.28 if fraction < 0.78 else 0.18) * (1.0 - fraction))
        t_ms = start_t_ms + duration_ms * fraction
        points.append(
            {
                "t_ms": round(t_ms, 3),
                "x": round(start_x + ux * along + px * (side + jitter), 3),
                "y": round(start_y + uy * along + py * (side + jitter), 3),
            }
        )

    if overshoot_px > 0:
        t_ms = start_t_ms + duration_ms
        fractions_back = (0.34, 0.62, 0.82, 1.0)
        for fraction in fractions_back:
            t_ms += max(7.0, rng.gauss(13.0, 2.3))
            last = points[-1]
            points.append(
                {
                    "t_ms": round(t_ms, 3),
                    "x": round(last["x"] + (end_x - last["x"]) * fraction, 3),
                    "y": round(last["y"] + (end_y - last["y"]) * fraction, 3),
                }
            )
        points[-1] = {
            "t_ms": round(t_ms, 3),
            "x": round(end_x, 3),
            "y": round(end_y, 3),
        }
        return t_ms, False

    points[-1] = {
        "t_ms": round(start_t_ms + duration_ms, 3),
        "x": round(end_x, 3),
        "y": round(end_y, 3),
    }
    return start_t_ms + duration_ms, False


def _clean_generated_points(
    points: list[dict[str, float]],
    reaction_ms: float,
) -> list[dict[str, float]]:
    if len(points) < 3:
        return points
    waiting = [point for point in points if float(point["t_ms"]) <= reaction_ms + 1e-6]
    active = [point for point in points if float(point["t_ms"]) > reaction_ms + 1e-6]
    if not active:
        return points

    cleaned: list[dict[str, float]] = []
    for point in active:
        if not cleaned:
            cleaned.append(point)
            continue
        previous = cleaned[-1]
        distance = math.hypot(point["x"] - previous["x"], point["y"] - previous["y"])
        elapsed = point["t_ms"] - previous["t_ms"]
        if distance < 0.35 and elapsed < 28.0:
            continue
        cleaned.append(point)
    if cleaned[-1] != active[-1]:
        cleaned.append(active[-1])
    return waiting + cleaned


def _positive_overshoot_sample(
    profile: dict[str, Any],
    context: dict[str, Any],
    radius: float,
    distance: float,
    rng: random.Random,
) -> float:
    median = _context_feature(
        profile,
        context,
        "overshoot_positive_px",
        "median",
        max(3.0, radius * 0.55),
    )
    p90 = _context_feature(
        profile,
        context,
        "overshoot_positive_px",
        "p90",
        max(median * 1.8, radius),
    )
    median = max(1.0, median)
    p90 = max(median, p90)
    sigma = max(0.18, math.log(max(p90 / median, 1.01)) / 1.2816)
    value = rng.lognormvariate(math.log(median), sigma)
    cap = min(max(radius * 12.0, 45.0), max(65.0, distance * 0.42))
    return min(value, cap)


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
    context = _context(profile, target_distance, radius, target_angle)

    candidates = _candidate_templates(profile, target_distance, radius, target_angle)
    template = _choose_template(candidates, rng)
    shape = _template_shape(template)

    movement_total_median = max(
        120.0,
        _context_feature(profile, context, "movement_time_ms", "median", 650.0),
    )
    movement_total_stdev = max(
        35.0,
        _context_feature(profile, context, "movement_time_ms", "stdev", 140.0),
    )
    reaction_median = max(
        8.0,
        _context_feature(profile, context, "reaction_ms", "median", 75.0),
    )
    reaction_stdev = max(
        8.0,
        _context_feature(profile, context, "reaction_ms", "stdev", 28.0),
    )
    click_delay_median = max(
        10.0,
        _context_feature(profile, context, "click_delay_ms", "median", 80.0),
    )
    click_delay_stdev = max(
        8.0,
        _context_feature(profile, context, "click_delay_ms", "stdev", 30.0),
    )
    click_delay_p90 = max(
        click_delay_median,
        _context_feature(profile, context, "click_delay_ms", "p90", click_delay_median * 1.8),
    )
    hold_median = max(
        35.0,
        _context_feature(profile, context, "hold_ms", "median", 95.0),
    )
    hold_stdev = max(
        6.0,
        _context_feature(profile, context, "hold_ms", "stdev", 18.0),
    )
    correction_mean = max(
        0.0,
        _context_feature(profile, context, "correction_count", "mean", 0.0),
    )

    reaction_ms = max(
        5.0,
        rng.gauss(reaction_median * session_scale, reaction_stdev * 0.70),
    )
    click_delay_ms = max(
        8.0,
        rng.gauss(click_delay_median * session_scale, click_delay_stdev * 0.62),
    )
    click_delay_ms = min(click_delay_ms, max(120.0, click_delay_p90 * 1.35))
    hold_ms = max(25.0, rng.gauss(hold_median, hold_stdev * 0.72))

    if shape and isinstance(template, dict):
        base_motion_ms = max(70.0, float(template.get("duration_ms", 220.0)))
        template_distance = max(1.0, float(template.get("distance_px", target_distance)))
        distance_scale = max(0.72, min(1.45, target_distance / template_distance))
        motion_ms = max(
            65.0,
            rng.gauss(
                base_motion_ms * (0.72 + 0.28 * distance_scale) * session_scale,
                max(8.0, base_motion_ms * 0.065),
            ),
        )
    else:
        base_motion_ms = max(
            80.0,
            movement_total_median - reaction_median - click_delay_median,
        )
        distance_factor = 0.62 + 0.38 * min(1.5, target_distance / 600.0)
        radius_factor = 1.08 if radius <= 18 else 1.0 if radius <= 28 else 0.94
        motion_ms = max(
            65.0,
            rng.gauss(
                base_motion_ms * distance_factor * radius_factor * session_scale,
                movement_total_stdev * 0.34,
            ),
        )

    click_model = profile.get("click_model", {}) if isinstance(profile, dict) else {}
    click_offset_x, click_offset_y = sample_click_offset(click_model, radius, rng)
    click_x = tx + click_offset_x
    click_y = ty + click_offset_y

    miss_rate = _context_rate(
        profile,
        context,
        "miss_rate",
        "miss_rate",
        float(profile.get("miss_count", 0) or 0)
        / max(float(profile.get("trial_count", 1) or 1), 1.0),
    )
    will_miss = rng.random() < min(0.18, max(0.0, miss_rate))
    if will_miss:
        miss_offset_x, miss_offset_y = _outside_click_offset(click_model, radius, rng)
        route_end_x = tx + miss_offset_x
        route_end_y = ty + miss_offset_y
    else:
        route_end_x = click_x
        route_end_y = click_y

    overshoot_probability = min(
        0.55,
        max(
            0.005,
            _context_rate(profile, context, "overshoot_rate", "overshoot_rate", 0.08),
        ),
    )
    overshoot = not shape and rng.random() < overshoot_probability
    overshoot_px = (
        _positive_overshoot_sample(profile, context, radius, target_distance, rng)
        if overshoot
        else 0.0
    )
    correction_rate = _context_rate(
        profile,
        context,
        "correction_rate",
        "correction_rate",
        min(0.50, correction_mean / 2.0),
    )
    correction = not shape and (rng.random() < min(0.60, max(0.02, correction_rate)) or overshoot)

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

    t_ms, used_template = _append_profiled_route(
        points,
        start_x=sx,
        start_y=sy,
        end_x=route_end_x,
        end_y=route_end_y,
        start_t_ms=reaction_ms,
        duration_ms=motion_ms,
        template=template,
        rng=rng,
        overshoot_px=overshoot_px,
        correction=correction,
    )
    points = _clean_generated_points(points, reaction_ms)

    miss_clicks: list[dict[str, float]] = []
    if will_miss:
        miss_down_ms = t_ms + max(8.0, click_delay_ms * 0.45)
        miss_up_ms = miss_down_ms + hold_ms * rng.uniform(0.72, 0.92)
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
        click_down_ms = t_ms + max(8.0, click_delay_ms * 0.35)
    elif used_template:
        click_down_ms = t_ms
    else:
        click_down_ms = t_ms + click_delay_ms

    click = {
        "down_t_ms": round(click_down_ms, 3),
        "up_t_ms": round(click_down_ms + hold_ms, 3),
        "x": round(click_x, 3),
        "y": round(click_y, 3),
    }
    target = {
        "index": int(item["index"]),
        "x": tx,
        "y": ty,
        "radius": radius,
    }
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
