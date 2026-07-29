from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime
from typing import Any

from .metrics import derive_trial


def generate_plan(count: int, width: int = 1000, height: int = 700, seed: int | None = None) -> dict[str, Any]:
    if count < 1:
        raise ValueError("count must be at least 1")
    if width < 240 or height < 240:
        raise ValueError("benchmark area is too small")
    rng = random.Random(seed)
    actual_seed = seed if seed is not None else rng.randrange(1, 2**31)
    rng.seed(actual_seed)
    targets = []
    start = [width // 2, height // 2]
    for index in range(count):
        target = [rng.randint(80, width - 80), rng.randint(80, height - 80)]
        targets.append({"index": index, "start": list(start), "target": target, "radius": rng.choice([12, 18, 26])})
        start = target
    return {"schema_version": 2, "seed": actual_seed, "width": width, "height": height, "targets": targets}


def plan_from_human_trials(original_plan: dict[str, Any], human_trials: list[dict[str, Any]]) -> dict[str, Any]:
    if len(human_trials) != len(original_plan.get("targets", [])):
        raise ValueError("human trial count must match benchmark plan")
    targets = []
    for item, trial in zip(original_plan["targets"], human_trials):
        targets.append({
            "index": int(item["index"]),
            "start": [round(float(trial["start"]["x"]), 3), round(float(trial["start"]["y"]), 3)],
            "target": [int(item["target"][0]), int(item["target"][1])],
            "radius": int(item["radius"]),
        })
    return {
        "schema_version": 2,
        "seed": int(original_plan["seed"]),
        "width": int(original_plan.get("width", 1000)),
        "height": int(original_plan.get("height", 700)),
        "targets": targets,
    }


def _feature(profile: dict[str, Any], name: str, key: str, default: float) -> float:
    try:
        return float(profile.get("features", {}).get(name, {}).get(key, default))
    except (TypeError, ValueError):
        return default


def _angle_delta(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def _choose_template(profile: dict[str, Any], distance: float, radius: float, angle: float, rng: random.Random) -> dict[str, Any] | None:
    templates = profile.get("route_templates", [])
    if not isinstance(templates, list) or not templates:
        return None
    ranked = []
    for template in templates:
        try:
            template_distance = max(float(template["distance_px"]), 1.0)
            distance_cost = abs(math.log(max(distance, 1.0) / template_distance))
            radius_cost = abs(float(template.get("radius", radius)) - radius) / 20.0
            angle_cost = _angle_delta(angle, float(template.get("angle", angle))) / math.pi
            ranked.append((distance_cost * 2.2 + radius_cost + angle_cost * 0.35, template))
        except (KeyError, TypeError, ValueError):
            continue
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0])
    pool = [template for _, template in ranked[: min(8, len(ranked))]]
    return rng.choice(pool)


def _human_time(value: float, rng: random.Random, floor: float = 0.0) -> float:
    return max(floor, value * rng.uniform(0.86, 1.16) + rng.gauss(0, max(2.0, value * 0.04)))


def _template_points(
    template: dict[str, Any], sx: float, sy: float, tx: float, ty: float, distance: float, rng: random.Random
) -> tuple[list[dict[str, float]], float, float, float]:
    dx, dy = tx - sx, ty - sy
    ux, uy = dx / max(distance, 1.0), dy / max(distance, 1.0)
    px, py = -uy, ux
    duration = _human_time(float(template.get("duration_ms", 500)), rng, 60.0)
    reaction = _human_time(float(template.get("reaction_ms", 60)), rng, 0.0)
    click_delay = _human_time(float(template.get("click_delay_ms", 50)), rng, 0.0)

    points: list[dict[str, float]] = []
    last_t = 0.0
    source_points = template.get("points", [])
    for index, point in enumerate(source_points):
        along = float(point.get("along", 0))
        side = float(point.get("side", 0)) * rng.uniform(0.82, 1.18)
        raw_t = float(point.get("t", 0)) * duration
        if index > 0:
            raw_t += rng.gauss(0, 2.3)
        t_ms = max(last_t + (0.2 if index else 0.0), raw_t)
        x = sx + ux * along * distance + px * side * distance
        y = sy + uy * along * distance + py * side * distance
        points.append({"t_ms": round(t_ms, 3), "x": float(round(x)), "y": float(round(y))})
        last_t = t_ms

    if not points:
        points = [{"t_ms": 0.0, "x": float(round(sx)), "y": float(round(sy))}]
    return points, reaction, click_delay, duration


def _fallback_points(sx: float, sy: float, tx: float, ty: float, distance: float, movement_ms: float, reaction_ms: float, rng: random.Random) -> list[dict[str, float]]:
    dx, dy = tx - sx, ty - sy
    ux, uy = dx / max(distance, 1.0), dy / max(distance, 1.0)
    px, py = -uy, ux
    side_bend = rng.gauss(0, max(2.0, distance * rng.uniform(0.015, 0.09)))
    overshoot = rng.random() < 0.22
    over = rng.uniform(3.0, min(40.0, max(5.0, distance * 0.08))) if overshoot else 0.0
    intervals = []
    elapsed = 0.0
    while elapsed < movement_ms:
        dt = max(5.0, rng.gauss(11.5, 3.8))
        intervals.append(dt)
        elapsed += dt
    points = [{"t_ms": 0.0, "x": float(round(sx)), "y": float(round(sy))}]
    stationary_samples = max(0, int(reaction_ms / max(8.0, rng.gauss(12.0, 2.5))))
    t = 0.0
    for _ in range(stationary_samples):
        t += max(6.0, rng.gauss(12.0, 3.0))
        points.append({"t_ms": round(t, 3), "x": float(round(sx)), "y": float(round(sy))})
    total = max(sum(intervals), 1.0)
    elapsed = 0.0
    for dt in intervals:
        elapsed += dt
        u = min(1.0, elapsed / total)
        shaped = 3 * u**2 - 2 * u**3
        wobble = math.sin(math.pi * u) * side_bend
        along = shaped * (distance + over)
        x = sx + ux * along + px * wobble
        y = sy + uy * along + py * wobble
        points.append({"t_ms": round(t + elapsed, 3), "x": float(round(x)), "y": float(round(y))})
    if overshoot:
        for step in range(rng.randint(2, 5)):
            t_ms = points[-1]["t_ms"] + max(7.0, rng.gauss(13.0, 3.0))
            fraction = (step + 1) / rng.randint(step + 2, step + 5)
            x = points[-1]["x"] + (tx - points[-1]["x"]) * fraction
            y = points[-1]["y"] + (ty - points[-1]["y"]) * fraction
            points.append({"t_ms": round(t_ms, 3), "x": float(round(x)), "y": float(round(y))})
    return points


def _click_from_template(template: dict[str, Any] | None, tx: float, ty: float, ux: float, uy: float, radius: float, rng: random.Random) -> tuple[float, float]:
    px, py = -uy, ux
    if template:
        along = float(template.get("click_along_px", 0)) * rng.uniform(0.75, 1.25)
        side = float(template.get("click_side_px", 0)) * rng.uniform(0.75, 1.25)
    else:
        along = rng.gauss(0, max(1.0, radius * 0.28))
        side = rng.gauss(0, max(1.0, radius * 0.28))
    length = math.hypot(along, side)
    if length > radius * 0.92:
        scale = radius * 0.92 / max(length, 1.0)
        along, side = along * scale, side * scale
    return float(round(tx + ux * along + px * side)), float(round(ty + uy * along + py * side))


def simulate(plan: dict[str, Any], profile: dict[str, Any], seed: int | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else int(plan["seed"]) + 1)
    median_ms = max(80.0, _feature(profile, "movement_time_ms", "median", 420))
    stdev_ms = max(20.0, _feature(profile, "movement_time_ms", "stdev", 95))
    reaction_med = max(0.0, _feature(profile, "reaction_ms", "median", 65))
    reaction_sd = max(8.0, _feature(profile, "reaction_ms", "stdev", 28))
    delay_med = max(0.0, _feature(profile, "click_delay_ms", "median", 70))
    delay_sd = max(8.0, _feature(profile, "click_delay_ms", "stdev", 35))
    hold_med = max(10.0, _feature(profile, "hold_ms", "median", 90))
    hold_sd = max(5.0, _feature(profile, "hold_ms", "stdev", 20))

    output: list[dict[str, Any]] = []
    for item in plan["targets"]:
        sx, sy = map(float, item["start"])
        tx, ty = map(float, item["target"])
        radius = float(item["radius"])
        dx, dy = tx - sx, ty - sy
        distance = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)
        ux, uy = dx / max(distance, 1.0), dy / max(distance, 1.0)
        template = _choose_template(profile, distance, radius, angle, rng)

        if template:
            points, reaction_ms, click_delay_ms, _ = _template_points(template, sx, sy, tx, ty, distance, rng)
        else:
            movement_ms = max(70.0, rng.gauss(median_ms, stdev_ms))
            reaction_ms = max(0.0, rng.gauss(reaction_med, reaction_sd))
            click_delay_ms = max(0.0, rng.gauss(delay_med, delay_sd))
            points = _fallback_points(sx, sy, tx, ty, distance, movement_ms, reaction_ms, rng)

        click_x, click_y = _click_from_template(template, tx, ty, ux, uy, radius, rng)
        click_down_ms = max(points[-1]["t_ms"], reaction_ms) + click_delay_ms
        hold_ms = max(8.0, rng.gauss(hold_med, hold_sd))
        miss_clicks: list[dict[str, float]] = []
        miss_probability = min(0.18, max(0.0, float(profile.get("miss_count", 0)) / max(float(profile.get("trial_count", 1)), 1.0)))
        if rng.random() < miss_probability:
            miss_angle = rng.uniform(0, 2 * math.pi)
            miss_distance = radius + rng.uniform(2.0, 18.0)
            miss_t = max(points[-1]["t_ms"], reaction_ms) + max(8.0, click_delay_ms * rng.uniform(0.25, 0.8))
            miss_clicks.append({
                "down_t_ms": round(miss_t, 3),
                "up_t_ms": round(miss_t + max(30.0, hold_ms * rng.uniform(0.65, 1.15)), 3),
                "x": float(round(tx + math.cos(miss_angle) * miss_distance)),
                "y": float(round(ty + math.sin(miss_angle) * miss_distance)),
            })
            click_down_ms = miss_clicks[-1]["up_t_ms"] + max(25.0, rng.gauss(85.0, 28.0))

        click = {
            "down_t_ms": round(click_down_ms, 3),
            "up_t_ms": round(click_down_ms + hold_ms, 3),
            "x": click_x,
            "y": click_y,
        }
        target = {"index": int(item["index"]), "x": int(tx), "y": int(ty), "radius": int(radius)}
        start = {"x": float(round(sx)), "y": float(round(sy))}
        try:
            derived = derive_trial(target, start, points, click)
        except ValueError:
            derived = {}
        output.append({
            "schema_version": 5,
            "target": target,
            "start": start,
            "points": points,
            "click": click,
            "miss_clicks": miss_clicks,
            "derived": derived,
        })
    return output


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _normalize_trial(trial: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 5,
        "target": trial.get("target", {}),
        "start": trial.get("start", {}),
        "points": trial.get("points", []),
        "click": trial.get("click", {}),
        "miss_clicks": trial.get("miss_clicks", []),
        "derived": trial.get("derived", {}),
    }


def create_blind_export(
    plan: dict[str, Any],
    human_trials: list[dict[str, Any]],
    generated_trials: list[dict[str, Any]],
    seed: int | None = None,
) -> dict[str, Any]:
    if len(human_trials) != len(generated_trials):
        raise ValueError("human and generated trial counts must match")
    if len(human_trials) != len(plan.get("targets", [])):
        raise ValueError("trial count must match plan")
    rng = random.Random(seed if seed is not None else int(plan["seed"]) + 2)
    benchmark_id = f"bench-{_canonical_hash({'plan': plan, 'n': len(human_trials)})}"
    human_is_a = bool(rng.getrandbits(1))
    human_trials = [_normalize_trial(trial) for trial in human_trials]
    generated_trials = [_normalize_trial(trial) for trial in generated_trials]

    def session(label: str, trials: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schema_version": 5,
            "benchmark_id": benchmark_id,
            "label": label,
            "plan_hash": _canonical_hash(plan),
            "trial_count": len(trials),
            "trials": trials,
        }

    a_source = "human" if human_is_a else "generated"
    b_source = "generated" if human_is_a else "human"
    a_trials = human_trials if human_is_a else generated_trials
    b_trials = generated_trials if human_is_a else human_trials
    return {
        "A": session("A", a_trials),
        "B": session("B", b_trials),
        "private_answer": {
            "schema_version": 1,
            "benchmark_id": benchmark_id,
            "A": a_source,
            "B": b_source,
            "human": "A" if human_is_a else "B",
            "generated": "B" if human_is_a else "A",
            "created_at": datetime.now().isoformat(),
        },
        "summary": {
            "schema_version": 2,
            "benchmark_id": benchmark_id,
            "seed": int(plan["seed"]),
            "trial_count": len(human_trials),
            "plan_hash": _canonical_hash(plan),
            "instructions": "Upload alleen A.json en B.json voor de blinde beoordeling. Deel private_answer.json pas na de keuze.",
        },
    }
