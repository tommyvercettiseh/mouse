from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any

from .comparison_flow import _plan_from_trials, latest_aim_session
from .models import normalize_trials
from .personal_model import contextual_simulate
from .storage import HEATMAPS, PROFILES, now_stamp, read_json, write_json


def create_heatmap_runs(run_count: int = 100) -> tuple[Path, dict[str, Any]]:
    """Simulate the latest completed Aim Lab target set repeatedly.

    Every run uses the exact same starts, targets and target radii from the latest
    real session. Only the generator seed changes between runs.
    """

    count = max(1, min(500, int(run_count)))
    profile = read_json(PROFILES / "master_profile.json", {})
    if not isinstance(profile, dict) or not profile:
        raise ValueError("Bouw eerst je persoonlijke profiel.")

    source_folder, source_trials = latest_aim_session()
    if not source_trials:
        raise ValueError("Nog geen voltooide Aim Lab-opname gevonden.")

    base_seed = random.randint(1, 2**31 - 1)
    plan = _plan_from_trials(source_trials, base_seed)
    expected_trials = len(source_trials)
    runs: list[dict[str, Any]] = []

    for run_index in range(count):
        seed = base_seed + run_index + 1
        trials = normalize_trials(contextual_simulate(plan, profile, seed))
        if len(trials) != expected_trials:
            raise ValueError(
                f"Run {run_index + 1} leverde {len(trials)} van "
                f"{expected_trials} targets."
            )
        runs.append(
            {
                "run_index": run_index,
                "seed": seed,
                "trials": trials,
            }
        )

    created_at = datetime.now().isoformat()
    payload = {
        "schema_version": 1,
        "source": "latest_aim_lab_session_repeated_with_personal_generator",
        "created_at": created_at,
        "run_count": count,
        "target_count": expected_trials,
        "movement_count": count * expected_trials,
        "source_aim_folder": str(source_folder) if source_folder else None,
        "profile_path": str(PROFILES / "master_profile.json"),
        "plan": plan,
        "runs": runs,
    }

    folder = HEATMAPS / now_stamp()
    write_json(folder / "heatmap_runs.json", payload)
    write_json(
        folder / "source.json",
        {
            "created_at": created_at,
            "source_aim_folder": str(source_folder) if source_folder else None,
            "run_count": count,
            "target_count": expected_trials,
            "movement_count": count * expected_trials,
        },
    )
    return folder, payload


def latest_heatmap_runs() -> tuple[Path | None, dict[str, Any]]:
    folders = sorted(
        (path for path in HEATMAPS.glob("*") if path.is_dir()),
        reverse=True,
    )
    for folder in folders:
        payload = read_json(folder / "heatmap_runs.json", {})
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("runs"), list)
            and payload.get("runs")
        ):
            return folder, payload
    return None, {}
