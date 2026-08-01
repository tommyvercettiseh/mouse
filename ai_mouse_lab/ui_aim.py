from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from tkinter import TclError
from typing import Any

import customtkinter as ctk

from .comparison_flow import collect_aim_trials, create_latest_comparison
from .metrics import derive_trial
from .models import normalize_trials
from .personal_model import build_personal_profile
from .schema import SCHEMA_VERSION
from .storage import AIM, PROFILES, now_stamp, read_json, write_json
from .ui_helpers import is_target_hit
from .ui_theme import (
    BG,
    BLUE,
    BORDER,
    GREEN,
    MUTED,
    PANEL,
    PANEL2,
    PURPLE,
    RED,
    SAMPLE_MS,
    TEXT,
    VIRTUAL_HEIGHT,
    VIRTUAL_WIDTH,
    Card,
)

LOGGER = logging.getLogger("ai_mouse_lab.app")


class AimLabMixin:
    def init_aim_state(self) -> None:
        self.aim_active = False
        self.aim_generation = 0
        self.aim_after_id: str | None = None
        self.aim_overlay: ctk.CTkFrame | None = None
        self.aim_canvas: ctk.CTkCanvas | None = None
        self.aim_plan: list[dict[str, Any]] = []
        self.aim_trials: list[dict[str, Any]] = []
        self.aim_index = 0
        self.aim_points: list[dict[str, float]] = []
        self.aim_miss_clicks: list[dict[str, float]] = []
        self.aim_start = {"x": 960.0, "y": 540.0}
        self.aim_spawn = 0.0
        self.aim_click_down: float | None = None
        self.aim_click_position: tuple[float, float] | None = None
        self.aim_session_folder: Path | None = None
        self.aim_last_drawn = 0

    def _page_aim(self) -> None:
        body = self.page(
            "Aim Lab",
            "Aim Lab",
            "Volledige targetroute, timing, overshoot, acceleratie, braking en slowdown in 1920 × 1080.",
        )
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        preview = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        preview.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        preview.create_text(
            500,
            300,
            text="Aim Lab opent fullscreen op hetzelfde scherm",
            fill=MUTED,
            font=("Segoe UI", 18, "bold"),
        )

        side = Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(
            side,
            text="Sessie",
            text_color=TEXT,
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 8))
        self.count_menu = ctk.CTkOptionMenu(
            side,
            values=["20", "50", "100"],
            fg_color=PANEL2,
            button_color=PURPLE,
        )
        self.count_menu.set("20")
        self.count_menu.pack(fill="x", padx=18, pady=8)
        self.capture_mode = ctk.CTkOptionMenu(
            side,
            values=["Normale opname", "Detectietest"],
            fg_color=PANEL2,
            button_color=PURPLE,
        )
        self.capture_mode.set("Normale opname")
        self.capture_mode.pack(fill="x", padx=18, pady=8)
        self.start_btn = ctk.CTkButton(
            side,
            text="Start Aim Lab",
            fg_color=PURPLE,
            height=46,
            command=self.start_aim,
        )
        self.start_btn.pack(fill="x", padx=18, pady=8)
        self.aim_status = ctk.CTkLabel(
            side,
            text="Klaar",
            text_color=MUTED,
            justify="left",
            wraplength=250,
        )
        self.aim_status.pack(anchor="w", padx=18, pady=10)

        ctk.CTkLabel(
            side,
            text="Persoonlijk profiel",
            text_color=TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", padx=18, pady=(10, 4))
        self.profile_btn = ctk.CTkButton(
            side,
            text="Build Profile",
            fg_color=GREEN,
            hover_color="#2fb669",
            text_color="#07140d",
            height=42,
            command=self.build_profile,
        )
        self.profile_btn.pack(fill="x", padx=18, pady=(0, 6))
        self.profile_status = ctk.CTkLabel(
            side,
            text="Nog geen profiel gebouwd",
            text_color=MUTED,
            justify="left",
            wraplength=250,
        )
        self.profile_status.pack(anchor="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(
            side,
            text="Laatste opname vergelijken",
            text_color=TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", padx=18, pady=(8, 4))
        self.compare_btn = ctk.CTkButton(
            side,
            text="Test nieuwste opname A/B",
            fg_color=PANEL2,
            hover_color=PURPLE,
            height=42,
            command=self.test_latest_ab,
        )
        self.compare_btn.pack(fill="x", padx=18, pady=(0, 6))
        self.compare_status = ctk.CTkLabel(
            side,
            text="Laatste Aim Lab-opname is de target-playlist.",
            text_color=MUTED,
            justify="left",
            wraplength=250,
        )
        self.compare_status.pack(anchor="w", padx=18, pady=(0, 12))

    def start_aim(self) -> None:
        if self.aim_active:
            return
        try:
            count = int(self.count_menu.get())
            plan = [
                {
                    "index": index,
                    "x": random.randint(100, 1820),
                    "y": random.randint(100, 980),
                    "radius": random.choice([12, 18, 26]),
                }
                for index in range(count)
            ]
            folder = AIM / now_stamp()
            write_json(
                folder / "plan.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "width": VIRTUAL_WIDTH,
                    "height": VIRTUAL_HEIGHT,
                    "targets": plan,
                },
            )
        except (OSError, TypeError, ValueError) as exc:
            self._show_error("Aim Lab starten", exc, self.aim_status)
            return

        self.aim_active = True
        self.aim_generation += 1
        self.aim_plan = plan
        self.aim_trials = []
        self.aim_index = 0
        self.aim_session_folder = folder
        self.start_btn.configure(state="disabled")
        try:
            self.aim_overlay = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
            self.aim_overlay.place(x=0, y=0, relwidth=1, relheight=1)
            self.aim_overlay.grid_rowconfigure(0, weight=1)
            self.aim_overlay.grid_columnconfigure(0, weight=1)
            self.aim_canvas = ctk.CTkCanvas(
                self.aim_overlay,
                bg=PANEL,
                highlightthickness=0,
            )
            self.aim_canvas.grid(row=0, column=0, sticky="nsew")
            self.aim_canvas.bind("<ButtonPress-1>", self._aim_press)
            self.aim_canvas.bind("<ButtonRelease-1>", self._aim_release)
            self.bind("<Escape>", lambda _event: self.abort_aim())
            self.attributes("-fullscreen", True)
            self.after(
                50,
                lambda: self._start_aim_when_ready(self.aim_generation, 0),
            )
        except TclError as exc:
            self.aim_active = False
            self._close_aim_overlay()
            self._show_error("Fullscreen openen", exc, self.aim_status)

    def _start_aim_when_ready(self, generation: int, attempt: int) -> None:
        if (
            not self.aim_active
            or generation != self.aim_generation
            or self.aim_canvas is None
        ):
            return
        try:
            self.aim_canvas.update_idletasks()
            width = self.aim_canvas.winfo_width()
            height = self.aim_canvas.winfo_height()
        except TclError as exc:
            self.abort_aim(f"Canvasfout: {exc}")
            return
        if width < 800 or height < 500:
            if attempt < 80:
                self.after(
                    40,
                    lambda: self._start_aim_when_ready(generation, attempt + 1),
                )
            else:
                self.abort_aim("Fullscreen canvas kon niet worden opgebouwd.")
            return
        self._show_aim_target()
        self._aim_sample(generation)

    def _pointer_virtual(self) -> tuple[float, float]:
        if self.aim_canvas is None:
            return 0.0, 0.0
        screen_x, screen_y = self.winfo_pointerxy()
        return self._to_virtual(
            self.aim_canvas,
            screen_x - self.aim_canvas.winfo_rootx(),
            screen_y - self.aim_canvas.winfo_rooty(),
        )

    def _show_aim_target(self) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        if self.aim_index >= len(self.aim_plan):
            self.finish_aim()
            return

        self.aim_miss_clicks = []
        self.aim_canvas.delete("all")
        scale, offset_x, offset_y = self._canvas_box(self.aim_canvas)
        self.aim_canvas.create_rectangle(
            offset_x,
            offset_y,
            offset_x + VIRTUAL_WIDTH * scale,
            offset_y + VIRTUAL_HEIGHT * scale,
            outline=BORDER,
        )
        target = self.aim_plan[self.aim_index]
        x, y = self._to_canvas(self.aim_canvas, target["x"], target["y"])
        radius = target["radius"] * scale
        self.aim_canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=PURPLE,
            outline="#c4b5fd",
            width=3,
        )
        self.aim_canvas.create_text(
            x,
            y,
            text=str(self.aim_index + 1),
            fill="white",
        )
        self.aim_canvas.create_text(
            18,
            18,
            anchor="nw",
            text=(
                f"Target {self.aim_index + 1}/{len(self.aim_plan)} · "
                "misklikken 0 · Esc stopt"
            ),
            fill=TEXT,
            font=("Segoe UI", 12, "bold"),
            tags="status",
        )
        pointer_x, pointer_y = self._pointer_virtual()
        self.aim_start = {"x": pointer_x, "y": pointer_y}
        self.aim_points = [
            {"t_ms": 0.0, "x": pointer_x, "y": pointer_y}
        ]
        self.aim_spawn = time.perf_counter()
        self.aim_click_down = None
        self.aim_click_position = None
        self.aim_last_drawn = 1

    def _aim_sample(self, generation: int) -> None:
        if not self.aim_active or generation != self.aim_generation:
            self.aim_after_id = None
            return
        x, y = self._pointer_virtual()
        t_ms = (time.perf_counter() - self.aim_spawn) * 1000.0
        self.aim_points.append(
            {
                "t_ms": round(t_ms, 3),
                "x": round(x, 3),
                "y": round(y, 3),
            }
        )
        self._draw_aim_trace()
        self.aim_after_id = self.after(
            SAMPLE_MS,
            lambda: self._aim_sample(generation),
        )

    def _draw_aim_trace(self) -> None:
        if self.aim_canvas is None or len(self.aim_points) < 2:
            return
        for index in range(max(1, self.aim_last_drawn), len(self.aim_points)):
            first = self.aim_points[index - 1]
            second = self.aim_points[index]
            first_x, first_y = self._to_canvas(
                self.aim_canvas,
                first["x"],
                first["y"],
            )
            second_x, second_y = self._to_canvas(
                self.aim_canvas,
                second["x"],
                second["y"],
            )
            self.aim_canvas.create_line(
                first_x,
                first_y,
                second_x,
                second_y,
                fill=BLUE,
                width=2,
            )
        self.aim_last_drawn = len(self.aim_points)

    def _aim_press(self, event: Any) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        self.aim_click_down = time.perf_counter()
        self.aim_click_position = self._to_virtual(
            self.aim_canvas,
            float(event.x),
            float(event.y),
        )

    def _aim_release(self, event: Any) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        released = time.perf_counter()
        release_x, release_y = self._to_virtual(
            self.aim_canvas,
            float(event.x),
            float(event.y),
        )
        self.aim_points.append(
            {
                "t_ms": round((released - self.aim_spawn) * 1000.0, 3),
                "x": round(release_x, 3),
                "y": round(release_y, 3),
            }
        )
        down_x, down_y = self.aim_click_position or (release_x, release_y)
        target = self.aim_plan[self.aim_index]
        click = {
            "down_t_ms": round(
                ((self.aim_click_down or released) - self.aim_spawn) * 1000.0,
                3,
            ),
            "up_t_ms": round((released - self.aim_spawn) * 1000.0, 3),
            "x": round(down_x, 3),
            "y": round(down_y, 3),
            "release_x": round(release_x, 3),
            "release_y": round(release_y, 3),
        }
        if not is_target_hit(down_x, down_y, target):
            self.aim_miss_clicks.append(click)
            self.aim_click_down = None
            self.aim_click_position = None
            self.aim_canvas.itemconfigure(
                "status",
                text=(
                    f"Target {self.aim_index + 1}/{len(self.aim_plan)} · "
                    f"misklikken {len(self.aim_miss_clicks)} · "
                    "raak hetzelfde target"
                ),
            )
            return

        target_data = {
            "index": self.aim_index,
            "x": target["x"],
            "y": target["y"],
            "radius": target["radius"],
        }
        try:
            derived = derive_trial(
                target_data,
                self.aim_start,
                self.aim_points,
                click,
            )
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.exception("Trial derivation failed")
            self.abort_aim(f"Meetfout: {type(exc).__name__}: {exc}")
            return
        self.aim_trials.append(
            {
                "schema_version": SCHEMA_VERSION,
                "coordinate_space": "virtual_1920x1080",
                "click_position_source": "mouse_down",
                "target": target_data,
                "start": dict(self.aim_start),
                "points": list(self.aim_points),
                "click": click,
                "miss_clicks": list(self.aim_miss_clicks),
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

    def _cancel_aim_after(self) -> None:
        self._cancel_after("aim_after_id")

    def finish_aim(self) -> None:
        if not self.aim_active:
            return
        self.aim_active = False
        self.aim_generation += 1
        self._cancel_aim_after()
        folder = self.aim_session_folder or (AIM / now_stamp())
        miss_count = sum(
            len(trial.get("miss_clicks", []))
            for trial in self.aim_trials
        )
        try:
            write_json(folder / "trials.json", self.aim_trials)
            write_json(
                folder / "summary.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "trial_count": len(self.aim_trials),
                    "point_count": sum(
                        len(trial["points"])
                        for trial in self.aim_trials
                    ),
                    "miss_count": miss_count,
                    "created_at": datetime.now().isoformat(),
                },
            )
        except OSError as exc:
            self._show_error("Sessie opslaan", exc, self.aim_status)
        else:
            self.aim_status.configure(
                text=(
                    f"Klaar\n{len(self.aim_trials)} targets\n"
                    f"{miss_count} misklikken"
                ),
                text_color=GREEN,
            )
            LOGGER.info(
                "Aim session saved: folder=%s trials=%s misses=%s",
                folder,
                len(self.aim_trials),
                miss_count,
            )
        finally:
            self._close_aim_overlay()

    def abort_aim(self, message: str = "Sessie afgebroken") -> None:
        if not self.aim_active:
            return
        self.aim_active = False
        self.aim_generation += 1
        self._cancel_aim_after()
        self._close_aim_overlay()
        self.aim_status.configure(text=message, text_color=RED)
        LOGGER.info("Aim session aborted: %s", message)

    def _close_aim_overlay(self) -> None:
        try:
            self.attributes("-fullscreen", False)
        except TclError:
            LOGGER.debug("Fullscreen was already closed")
        self.unbind("<Escape>")
        if self.aim_overlay is not None:
            try:
                self.aim_overlay.destroy()
            except TclError:
                LOGGER.debug("Aim overlay was already destroyed")
        self.aim_overlay = None
        self.aim_canvas = None
        if hasattr(self, "start_btn"):
            self.start_btn.configure(state="normal")
        try:
            self.lift()
            self.focus_force()
        except TclError:
            LOGGER.debug("Window no longer available for focus")

    def build_profile(self) -> None:
        self.profile_btn.configure(state="disabled", text="Profiel bouwen…")
        try:
            trials = collect_aim_trials()
            if not trials:
                raise ValueError("Nog geen Aim Lab-opnames gevonden.")
            profile = build_personal_profile(trials, [])
            if int(profile.get("trial_count", 0) or 0) == 0:
                raise ValueError(
                    "Geen geldige normale trials gevonden. "
                    "Controleer de afkeur-redenen."
                )
            write_json(PROFILES / "master_profile.json", profile)
            self.refresh_profile_status()
            self.aim_status.configure(
                text="Persoonlijk profiel bijgewerkt",
                text_color=GREEN,
            )
            LOGGER.info(
                "Profile built: accepted=%s rejected=%s quality=%s",
                profile.get("trial_count", 0),
                profile.get("rejected_trial_count", 0),
                profile.get("quality_percent", 0),
            )
        except (KeyError, OSError, TypeError, ValueError) as exc:
            self._show_error("Profielbouw", exc, self.aim_status)
        finally:
            self.profile_btn.configure(state="normal", text="Build Profile")

    def refresh_profile_status(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not isinstance(profile, dict) or not profile:
            self.profile_status.configure(
                text="Nog geen profiel gebouwd",
                text_color=MUTED,
            )
            return
        contexts = profile.get("contexts", {})
        strong_contexts = (
            sum(
                1
                for context in contexts.values()
                if isinstance(context, dict)
                and int(context.get("trial_count", 0)) >= 8
            )
            if isinstance(contexts, dict)
            else 0
        )
        click_model = profile.get("click_model", {})
        click_samples = (
            int(click_model.get("sample_count", 0) or 0)
            if isinstance(click_model, dict)
            else 0
        )
        self.profile_status.configure(
            text=(
                f"Kwaliteit: {profile.get('quality_percent', 0)}%\n"
                f"Targets: {profile.get('trial_count', 0)}\n"
                f"Klikmetingen: {click_samples}\n"
                f"Afgekeurd: {profile.get('rejected_trial_count', 0)}\n"
                f"Sterke contexten: {strong_contexts}"
            ),
            text_color=GREEN,
        )

    def test_latest_ab(self) -> None:
        self.compare_btn.configure(
            state="disabled",
            text="Vergelijking maken…",
        )
        try:
            folder, session_a, session_b = create_latest_comparison()
            trials_a = normalize_trials(session_a)
            trials_b = normalize_trials(session_b)
            if not trials_a or len(trials_a) != len(trials_b):
                raise ValueError(
                    "A/B-data is leeg of heeft ongelijke targetaantallen."
                )
            self.replay_a = {**session_a, "trials": trials_a}
            self.replay_b = {**session_b, "trials": trials_b}
            self.replay_index = 0
            self.replay_elapsed = 0.0
            self.replay_finished = False
            self.compare_status.configure(
                text=f"Klaar · {len(trials_a)} targets\n{folder.name}",
                text_color=GREEN,
            )
            LOGGER.info(
                "Comparison created: folder=%s trials=%s",
                folder,
                len(trials_a),
            )
            self.show("Results")
        except (KeyError, OSError, TypeError, ValueError) as exc:
            self._show_error("A/B-vergelijking", exc, self.compare_status)
        finally:
            self.compare_btn.configure(
                state="normal",
                text="Test nieuwste opname A/B",
            )
