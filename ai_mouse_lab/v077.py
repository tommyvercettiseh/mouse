from __future__ import annotations

import random
from datetime import datetime
from typing import Any

import customtkinter as ctk

from .storage import AIM, BENCHMARKS, PROFILES, now_stamp, read_json, write_json


def _latest_completed_trials() -> tuple[Any, list[dict[str, Any]]] | tuple[None, list[Any]]:
    folders = sorted((path for path in AIM.glob("*") if path.is_dir()), reverse=True)
    for folder in folders:
        trials = read_json(folder / "trials.json", [])
        if isinstance(trials, list) and trials:
            return folder, trials
    return None, []


def _plan_from_trials(trials: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    targets = []
    for index, trial in enumerate(trials):
        start = trial.get("start", {})
        target = trial.get("target", {})
        targets.append({
            "index": index,
            "start": [float(start.get("x", 960)), float(start.get("y", 540))],
            "target": [int(target.get("x", 960)), int(target.get("y", 540))],
            "radius": int(target.get("radius", 26)),
        })
    return {
        "schema_version": 2,
        "seed": seed,
        "width": 1920,
        "height": 1080,
        "targets": targets,
    }


def apply_patch(original_app: Any) -> None:
    old_page_aim = original_app.App._page_aim

    def _page_aim(self: Any) -> None:
        old_page_aim(self)
        page = self.pages.get("Aim Lab")
        if page is None:
            return
        body_children = page.winfo_children()
        if not body_children:
            return
        body = body_children[-1]
        cards = body.winfo_children()
        if len(cards) < 2:
            return
        side = cards[1]

        ctk.CTkLabel(
            side,
            text="Laatste opname vergelijken",
            text_color=original_app.TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", padx=18, pady=(12, 4))
        self.latest_ab_btn = ctk.CTkButton(
            side,
            text="Test nieuwste opname A/B",
            fg_color=original_app.PANEL2,
            hover_color=original_app.PURPLE,
            height=42,
            command=self.test_latest_recording_ab,
        )
        self.latest_ab_btn.pack(fill="x", padx=18, pady=(0, 6))
        self.latest_ab_status = ctk.CTkLabel(
            side,
            text="Gebruikt je laatste voltooide Aim Lab-sessie.",
            text_color=original_app.MUTED,
            justify="left",
            wraplength=250,
        )
        self.latest_ab_status.pack(anchor="w", padx=18, pady=(0, 12))

    def test_latest_recording_ab(self: Any) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            message = "Bouw eerst je persoonlijke profiel."
            if hasattr(self, "latest_ab_status"):
                self.latest_ab_status.configure(text=message, text_color=original_app.RED)
            if hasattr(self, "bench_status"):
                self.bench_status.configure(text=message, text_color=original_app.RED)
            return

        source_folder, human_trials = _latest_completed_trials()
        if not human_trials:
            message = "Nog geen voltooide Aim Lab-opname gevonden."
            if hasattr(self, "latest_ab_status"):
                self.latest_ab_status.configure(text=message, text_color=original_app.RED)
            if hasattr(self, "bench_status"):
                self.bench_status.configure(text=message, text_color=original_app.RED)
            return

        seed = random.randint(1, 2**31 - 1)
        plan = _plan_from_trials(human_trials, seed)
        generated_trials = original_app.simulate(plan, profile, seed + 1)

        folder = BENCHMARKS / now_stamp()
        folder.mkdir(parents=True, exist_ok=True)
        benchmark_id = f"latest-{folder.name}"
        a = {
            "schema_version": 5,
            "benchmark_id": benchmark_id,
            "label": "A",
            "source": "latest_aim_lab_recording",
            "trials": human_trials,
            "created_at": datetime.now().isoformat(),
        }
        b = {
            "schema_version": 5,
            "benchmark_id": benchmark_id,
            "label": "B",
            "source": "personal_generator",
            "trials": generated_trials,
            "created_at": datetime.now().isoformat(),
        }
        write_json(folder / "benchmark_plan.json", plan)
        write_json(folder / "A.json", a)
        write_json(folder / "B.json", b)
        write_json(folder / "source.json", {
            "source_aim_folder": str(source_folder) if source_folder else None,
            "trial_count": len(human_trials),
            "A": "human_latest_recording",
            "B": "generated",
        })

        self.replay_folder = folder
        self.replay_a = a
        self.replay_b = b
        self.replay_trial_index = 0
        self.replay_elapsed_ms = 0.0
        self.replay_running = False

        if hasattr(self, "latest_ab_status"):
            self.latest_ab_status.configure(
                text=f"Klaar · {len(human_trials)} targets · replay geopend",
                text_color=original_app.GREEN,
            )
        self.show("Results")
        self.refresh_results()

    def start_benchmark(self: Any) -> None:
        # The separate fullscreen benchmark proved fragile on Windows. Reuse the
        # latest completed Aim Lab session instead, so A and B share identical targets.
        self.test_latest_recording_ab()

    original_app.App._page_aim = _page_aim
    original_app.App.test_latest_recording_ab = test_latest_recording_ab
    original_app.App.start_benchmark = start_benchmark
