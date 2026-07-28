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
    """Use the human's actual start position while preserving targets and order."""
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


def simulate(plan: dict[str, Any], profile: dict[str, Any], seed: int | None = None) -> list[dict[str, Any]]:
    """Generate trial-shaped data with the same schema as human Aim Lab trials."""
    rng = random.Random(seed if seed is not None else int(plan["seed"]) + 1)
    median_ms = max(80.0, _feature(profile, "movement_time_ms", "median", 300))
    stdev_ms = max(10.0, _feature(profile, "movement_time_ms", "stdev", 45))
    reaction_med = max(0.0, _feature(profile, "reaction_ms", "median", 55))
    reaction_sd = max(3.0, _feature(profile, "reaction_ms", "stdev", 18))
    delay_med = max(0.0, _feature(profile, "click_delay_ms", "median", 45))
    delay_sd = max(2.0, _feature(profile, "click_delay_ms", "stdev", 15))
    hold_med = max(10.0, _feature(profile, "hold_ms", "median", 75))
    hold_sd = max(3.0, _feature(profile, "hold_ms", "stdev", 18))
    error_sd = max(0.5, _feature(profile, "click_error_px", "stdev", 3))
    efficiency = min(0.999, max(0.70, _feature(profile, "path_efficiency", "median", 0.95)))
    overshoot_med = max(0.0, _feature(profile, "overshoot_px", "median", 0))
    correction_med = max(0.0, _feature(profile, "correction_count", "mean", 0))

    output: list[dict[str, Any]] = []
    for item in plan["targets"]:
        sx, sy = map(float, item["start"])
        tx, ty = map(float, item["target"])
        radius = float(item["radius"])
        movement_ms = max(60.0, rng.gauss(median_ms, stdev_ms))
        reaction_ms = max(0.0, rng.gauss(reaction_med, reaction_sd))
        click_delay_ms = max(0.0, rng.gauss(delay_med, delay_sd))
        hold_ms = max(8.0, rng.gauss(hold_med, hold_sd))
        distance = math.hypot(tx - sx, ty - sy)
        bend = rng.gauss(0, max(2.0, distance * (1.0 - efficiency)))
        steps = max(18, int(movement_ms / 8))
        points: list[dict[str, float]] = [{"t_ms": 0.0, "x": sx, "y": sy}]

        for step in range(1, steps + 1):
            u = step / steps
            smooth = 10 * u**3 - 15 * u**4 + 6 * u**5
            x = sx + (tx - sx) * smooth
            y = sy + (ty - sy) * smooth + math.sin(math.pi * u) * bend
            points.append({
                "t_ms": round(reaction_ms + u * movement_ms, 3),
                "x": round(x, 3),
                "y": round(y, 3),
            })

        correction_count = max(0, int(round(rng.gauss(correction_med, 0.65))))
        if overshoot_med > 0 and correction_count > 0 and distance > 0:
            ux, uy = (tx - sx) / distance, (ty - sy) / distance
            over = max(1.0, rng.gauss(overshoot_med, max(1.0, overshoot_med * 0.35)))
            points[-1] = {
                "t_ms": round(reaction_ms + movement_ms, 3),
                "x": round(tx + ux * over, 3),
                "y": round(ty + uy * over, 3),
            }
            for correction in range(correction_count):
                frac = (correction + 1) / correction_count
                points.append({
                    "t_ms": round(reaction_ms + movement_ms + 16 + correction * 18, 3),
                    "x": round(points[-1]["x"] + (tx - points[-1]["x"]) * frac, 3),
                    "y": round(points[-1]["y"] + (ty - points[-1]["y"]) * frac, 3),
                })

        click_x = tx + rng.gauss(0, error_sd)
        click_y = ty + rng.gauss(0, error_sd)
        click_down_ms = max(points[-1]["t_ms"], reaction_ms + movement_ms) + click_delay_ms
        click = {
            "down_t_ms": round(click_down_ms, 3),
            "up_t_ms": round(click_down_ms + hold_ms, 3),
            "x": round(click_x, 3),
            "y": round(click_y, 3),
        }
        target = {"index": int(item["index"]), "x": tx, "y": ty, "radius": radius}
        start = {"x": sx, "y": sy}
        try:
            derived = derive_trial(target, start, points, click)
        except ValueError:
            derived = {}
        output.append({
            "schema_version": 4,
            "target": target,
            "start": start,
            "points": points,
            "click": click,
            "derived": derived,
        })
    return output


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


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

    def session(label: str, trials: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schema_version": 4,
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
            "schema_version": 1,
            "benchmark_id": benchmark_id,
            "seed": int(plan["seed"]),
            "trial_count": len(human_trials),
            "plan_hash": _canonical_hash(plan),
            "instructions": "Upload alleen A.json en B.json voor de blinde beoordeling. Deel private_answer.json pas na de keuze.",
        },
    }
