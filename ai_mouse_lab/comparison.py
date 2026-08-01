from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any

from .generator import simulate
from .schema import SCHEMA_VERSION, VIRTUAL_HEIGHT, VIRTUAL_WIDTH, normalize_session
from .storage import AIM, COMPARISONS, PROFILES, now_stamp, read_json, write_json


class ComparisonError(RuntimeError):
    """Raised when an A/B comparison cannot be created or loaded."""


def latest_completed_aim_session() -> tuple[Path, dict[str, Any]]:
    folders = sorted((path for path in AIM.glob("*") if path.is_dir()), reverse=True)
    for folder in folders:
        raw = read_json(folder / "trials.json", [])
        session = normalize_session(raw)
        if session["trials"]:
            session["source_folder"] = str(folder)
            return folder, session
    raise ComparisonError("Nog geen voltooide Aim Lab-opname gevonden.")


def plan_from_session(session: dict[str, Any], seed: int) -> dict[str, Any]:
    normalized = normalize_session(session)
    targets: list[dict[str, Any]] = []
    for index, trial in enumerate(normalized["trials"]):
        start = trial["start"]
        target = trial["target"]
        targets.append(
            {
                "index": index,
                "start": [float(start["x"]), float(start["y"])],
                "target": [float(target["x"]), float(target["y"])],
                "radius": float(target["radius"]),
            }
        )
    if not targets:
        raise ComparisonError("De laatste Aim Lab-opname bevat geen geldige targets.")
    return {
        "schema_version": SCHEMA_VERSION,
        "seed": int(seed),
        "width": VIRTUAL_WIDTH,
        "height": VIRTUAL_HEIGHT,
        "targets": targets,
    }


def create_latest_comparison(seed: int | None = None) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    profile = read_json(PROFILES / "master_profile.json", {})
    if not isinstance(profile, dict) or not profile:
        raise ComparisonError("Bouw eerst je persoonlijke profiel.")

    source_folder, human_session = latest_completed_aim_session()
    actual_seed = int(seed if seed is not None else random.randint(1, 2**31 - 1))
    plan = plan_from_session(human_session, actual_seed)
    generated_trials = simulate(plan, profile, actual_seed + 1)

    comparison_id = f"comparison-{now_stamp()}"
    human = normalize_session(
        {
            "comparison_id": comparison_id,
            "label": "A",
            "source": "latest_aim_lab_recording",
            "created_at": datetime.now().isoformat(),
            "trials": human_session["trials"],
        }
    )
    generated = normalize_session(
        {
            "comparison_id": comparison_id,
            "label": "B",
            "source": "personal_generator",
            "created_at": datetime.now().isoformat(),
            "trials": generated_trials,
        }
    )

    count = min(len(human["trials"]), len(generated["trials"]))
    if count == 0:
        raise ComparisonError("A/B-generatie leverde geen geldige trials op.")
    human["trials"] = human["trials"][:count]
    generated["trials"] = generated["trials"][:count]
    human["trial_count"] = count
    generated["trial_count"] = count

    folder = COMPARISONS / comparison_id
    write_json(folder / "plan.json", plan)
    write_json(folder / "A.json", human)
    write_json(folder / "B.json", generated)
    write_json(
        folder / "source.json",
        {
            "schema_version": SCHEMA_VERSION,
            "source_aim_folder": str(source_folder),
            "trial_count": count,
            "A": "human_latest_recording",
            "B": "generated",
            "created_at": datetime.now().isoformat(),
        },
    )
    return folder, human, generated


def latest_comparison() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    folders = sorted((path for path in COMPARISONS.glob("*") if path.is_dir()), reverse=True)
    for folder in folders:
        if not (folder / "A.json").exists() or not (folder / "B.json").exists():
            continue
        a = normalize_session(read_json(folder / "A.json", {}))
        b = normalize_session(read_json(folder / "B.json", {}))
        if a["trials"] and b["trials"]:
            return folder, a, b
    raise ComparisonError("Nog geen A/B-vergelijking gevonden.")
