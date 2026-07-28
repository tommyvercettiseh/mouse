from __future__ import annotations

import math
import random
from typing import Any


def generate_plan(count: int, width: int = 1000, height: int = 700, seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    actual_seed = seed if seed is not None else rng.randrange(1, 2**31)
    rng.seed(actual_seed)
    targets = []
    start = [width // 2, height // 2]
    for index in range(count):
        target = [rng.randint(80, width - 80), rng.randint(80, height - 80)]
        targets.append({"index": index, "start": start, "target": target, "radius": rng.choice([12, 18, 26])})
        start = target
    return {"schema_version": 1, "seed": actual_seed, "targets": targets}


def simulate(plan: dict[str, Any], profile: dict[str, Any], seed: int | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else int(plan["seed"]) + 1)
    features = profile.get("features", {})
    move = features.get("movement_time_ms", {})
    error = features.get("click_error_px", {})
    efficiency = features.get("path_efficiency", {})
    median_ms = max(80.0, float(move.get("median", 300)))
    stdev_ms = max(10.0, float(move.get("stdev", 45)))
    error_sd = max(0.5, float(error.get("stdev", 3)))
    efficiency_median = min(0.999, max(0.75, float(efficiency.get("median", 0.95))))
    output = []
    for item in plan["targets"]:
        sx, sy = item["start"]
        tx, ty = item["target"]
        duration = max(60.0, rng.gauss(median_ms, stdev_ms))
        distance = math.hypot(tx - sx, ty - sy)
        bend = rng.gauss(0, max(2.0, distance * (1.0 - efficiency_median)))
        steps = max(16, int(duration / 8))
        points = []
        for step in range(steps + 1):
            u = step / steps
            smooth = 10*u**3 - 15*u**4 + 6*u**5
            points.append({
                "t_ms": round(u * duration, 3),
                "x": round(sx + (tx - sx) * smooth, 3),
                "y": round(sy + (ty - sy) * smooth + math.sin(math.pi * u) * bend, 3),
            })
        output.append({
            "target": item,
            "points": points,
            "click": {"x": round(tx + rng.gauss(0, error_sd), 3), "y": round(ty + rng.gauss(0, error_sd), 3)},
        })
    return output
