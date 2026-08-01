from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import normalize_trials
from .personal_model import contextual_simulate
from .storage import AIM, COMPARISONS, PROFILES, now_stamp, read_json, write_json


def collect_aim_trials() -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for folder in sorted((path for path in AIM.glob("*") if path.is_dir())):
        trials.extend(normalize_trials(read_json(folder / "trials.json", [])))
    return trials


def latest_aim_session() -> tuple[Path | None, list[dict[str, Any]]]:
    folders = sorted((path for path in AIM.glob("*") if path.is_dir()), reverse=True)
    for folder in folders:
        trials = normalize_trials(read_json(folder / "trials.json", []))
        if trials:
            return folder, trials
    return None, []


def _plan_from_trials(trials: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    targets = []
    for index, trial in enumerate(trials):
        target = trial["target"]
        start = trial["start"]
        targets.append({
            "index": index,
            "start": [float(start["x"]), float(start["y"])],
            "target": [float(target["x"]), float(target["y"])],
            "radius": int(target.get("radius", 26)),
        })
    return {"schema_version": 3, "seed": seed, "width": 1920, "height": 1080, "targets": targets}


def create_latest_comparison() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    profile = read_json(PROFILES / "master_profile.json", {})
    if not isinstance(profile, dict) or not profile:
        raise ValueError("Bouw eerst je persoonlijke profiel.")

    source_folder, human_trials = latest_aim_session()
    if not human_trials:
        raise ValueError("Nog geen voltooide Aim Lab-opname gevonden.")

    seed = random.randint(1, 2**31 - 1)
    plan = _plan_from_trials(human_trials, seed)
    generated_trials = normalize_trials(contextual_simulate(plan, profile, seed + 1))
    if len(generated_trials) != len(human_trials):
        raise ValueError("Generator leverde niet voor ieder target een geldige trial.")

    created_at = datetime.now().isoformat()
    comparison_id = f"comparison-{now_stamp()}"
    a = {
        "schema_version": 1,
        "comparison_id": comparison_id,
        "label": "A",
        "source": "latest_aim_lab_recording",
        "trials": human_trials,
        "created_at": created_at,
    }
    b = {
        "schema_version": 1,
        "comparison_id": comparison_id,
        "label": "B",
        "source": "personal_generator",
        "trials": generated_trials,
        "created_at": created_at,
    }

    folder = COMPARISONS / now_stamp()
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "plan.json", plan)
    write_json(folder / "A.json", a)
    write_json(folder / "B.json", b)
    write_json(folder / "source.json", {
        "source_aim_folder": str(source_folder) if source_folder else None,
        "trial_count": len(human_trials),
    })
    return folder, a, b


def latest_comparison() -> tuple[Path | None, dict[str, Any], dict[str, Any]]:
    folders = sorted((path for path in COMPARISONS.glob("*") if path.is_dir()), reverse=True)
    for folder in folders:
        a = read_json(folder / "A.json", {})
        b = read_json(folder / "B.json", {})
        trials_a = normalize_trials(a)
        trials_b = normalize_trials(b)
        if trials_a and trials_b:
            a = {**(a if isinstance(a, dict) else {}), "trials": trials_a}
            b = {**(b if isinstance(b, dict) else {}), "trials": trials_b}
            return folder, a, b
    return None, {}, {}
