from __future__ import annotations

import math
import time
from typing import Any

import customtkinter as ctk

from app_clean import App as CleanApp
from ai_mouse_lab.approach import enrich_derived
from ai_mouse_lab.comparison_flow import collect_aim_trials
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.personal_model import build_personal_profile
from ai_mouse_lab.storage import PROFILES, write_json

GREEN = "#3ccf78"
RED = "#d94b4b"


class App(CleanApp):
    """v0.9.1 app: same UI, richer movement measurements."""

    def _aim_release(self, event: Any) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return

        released = time.perf_counter()
        x, y = self._to_virtual(self.aim_canvas, float(event.x), float(event.y))
        self.aim_points.append(
            {
                "t_ms": round((released - self.aim_spawn) * 1000.0, 3),
                "x": x,
                "y": y,
            }
        )

        target = self.aim_plan[self.aim_index]
        click = {
            "down_t_ms": round(
                ((self.aim_click_down or released) - self.aim_spawn) * 1000.0,
                3,
            ),
            "up_t_ms": round((released - self.aim_spawn) * 1000.0, 3),
            "x": x,
            "y": y,
        }
        target_data = {
            "index": self.aim_index,
            "x": target["x"],
            "y": target["y"],
            "radius": target["radius"],
        }

        try:
            base = derive_trial(target_data, self.aim_start, self.aim_points, click)
            derived = enrich_derived(
                base,
                target_data,
                self.aim_start,
                self.aim_points,
                click,
            )
        except (TypeError, ValueError, KeyError):
            return

        miss = math.hypot(x - target["x"], y - target["y"]) > target["radius"]
        self.aim_trials.append(
            {
                "schema_version": 8,
                "target": target_data,
                "start": self.aim_start,
                "points": list(self.aim_points),
                "click": click,
                "miss_clicks": [click] if miss else [],
                "derived": derived,
                "capture_mode": (
                    "test"
                    if self.capture_mode.get() == "Detectietest"
                    else "normal"
                ),
            }
        )
        self.aim_index += 1
        self._show_aim_target()

    def build_profile(self) -> None:
        self.profile_btn.configure(state="disabled", text="Profiel bouwen…")
        try:
            trials = collect_aim_trials()
            if not trials:
                raise ValueError("Nog geen Aim Lab-opnames gevonden.")

            for trial in trials:
                if not isinstance(trial, dict):
                    continue
                derived = trial.get("derived", {})
                if not isinstance(derived, dict):
                    continue
                if "approach_correction_count" not in derived:
                    trial["derived"] = enrich_derived(
                        derived,
                        trial.get("target", {}),
                        trial.get("start", {}),
                        trial.get("points", []),
                        trial.get("click", {}),
                    )

            profile = build_personal_profile(trials, [])
            accepted = [
                trial.get("derived", {})
                for trial in trials
                if isinstance(trial, dict)
                and isinstance(trial.get("derived"), dict)
                and trial.get("capture_mode", "normal") == "normal"
            ]
            profile.setdefault("features", {})
            for name in (
                "approach_correction_count",
                "approach_deviation_px",
                "approach_correction_ms",
                "approach_recovery_ms",
                "approach_angle_change_deg",
            ):
                values = [float(item.get(name, 0.0) or 0.0) for item in accepted]
                if values:
                    ordered = sorted(values)
                    middle = len(ordered) // 2
                    median = (
                        ordered[middle]
                        if len(ordered) % 2
                        else (ordered[middle - 1] + ordered[middle]) / 2
                    )
                    profile["features"][name] = {
                        "mean": round(sum(values) / len(values), 3),
                        "median": round(median, 3),
                        "min": round(min(values), 3),
                        "max": round(max(values), 3),
                    }

            write_json(PROFILES / "master_profile.json", profile)
            self.refresh_profile_status()
            self.aim_status.configure(
                text="Persoonlijk profiel bijgewerkt",
                text_color=GREEN,
            )
        except ValueError as exc:
            self.aim_status.configure(text=str(exc), text_color=RED)
        finally:
            self.profile_btn.configure(state="normal", text="Build Profile")


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()


if __name__ == "__main__":
    main()
