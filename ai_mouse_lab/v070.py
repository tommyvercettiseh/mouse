from __future__ import annotations

from typing import Any

import customtkinter as ctk

from .personal_model import build_personal_profile, contextual_simulate
from .storage import PROFILES, write_json


def apply_patch(original_app: Any) -> None:
    old_page_aim = original_app.App._page_aim
    old_start_aim = original_app.App.start_aim
    old_on_release = original_app.App.on_release

    original_app.simulate = contextual_simulate
    original_app.build_profile = build_personal_profile

    def _page_aim(self: Any) -> None:
        old_page_aim(self)
        body = self.pages["Aim Lab"].winfo_children()[-1]
        children = body.winfo_children()
        if len(children) < 2:
            return
        side = children[1]
        ctk.CTkLabel(side, text="Opnamemodus", text_color=original_app.TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(12, 4))
        self.capture_mode = ctk.CTkOptionMenu(
            side,
            values=["Normale opname", "Detectietest"],
            fg_color=original_app.PANEL2,
            button_color=original_app.PURPLE,
        )
        self.capture_mode.set("Normale opname")
        self.capture_mode.pack(fill="x", padx=18, pady=(0, 12))

    def start_aim(self: Any) -> None:
        self.active_capture_mode = "test" if getattr(self, "capture_mode", None) and self.capture_mode.get() == "Detectietest" else "normal"
        old_start_aim(self)

    def on_release(self: Any, event: Any) -> None:
        before = len(getattr(self, "trials", []))
        old_on_release(self, event)
        if len(getattr(self, "trials", [])) > before:
            self.trials[-1]["capture_mode"] = getattr(self, "active_capture_mode", "normal")

    def make_profile(self: Any) -> None:
        profile = build_personal_profile(self.collect_trials(), [])
        write_json(PROFILES / "master_profile.json", profile)
        self.refresh_profile()
        self.refresh_dashboard()

    def refresh_profile(self: Any) -> None:
        profile = original_app.read_json(PROFILES / "master_profile.json", {})
        if not profile:
            self.profile_label.configure(text="Nog geen profiel")
            return
        contexts = profile.get("contexts", {})
        strong_contexts = sum(1 for value in contexts.values() if int(value.get("trial_count", 0)) >= 8)
        reasons = profile.get("rejected_reasons", {})
        rejected = ", ".join(f"{key}: {value}" for key, value in reasons.items()) or "geen"
        features = profile.get("features", {})
        self.profile_label.configure(text=(
            f"Kwaliteit: {profile.get('quality_percent', 0)}%\n"
            f"Geaccepteerde targets: {profile.get('trial_count', 0)} / {profile.get('raw_trial_count', 0)}\n"
            f"Afgekeurd: {profile.get('rejected_trial_count', 0)} ({rejected})\n"
            f"Sterke contexten: {strong_contexts} / {len(contexts)}\n"
            f"Ruwe punten: {profile.get('point_count', 0)}\n\n"
            f"Movement mediaan: {features.get('movement_time_ms', {}).get('median', 0)} ms\n"
            f"Remstart mediaan: {features.get('braking_start_ms', {}).get('median', 0)} ms\n"
            f"Piekversnelling mediaan: {features.get('peak_accel_px_s2', {}).get('median', 0)} px/s²\n"
            f"Jerk mediaan: {features.get('peak_jerk_px_s3', {}).get('median', 0)} px/s³\n"
            f"Overshootfrequentie: {float(profile.get('overshoot_rate', 0)) * 100:.1f}%"
        ))

    original_app.App._page_aim = _page_aim
    original_app.App.start_aim = start_aim
    original_app.App.on_release = on_release
    original_app.App.make_profile = make_profile
    original_app.App.refresh_profile = refresh_profile
