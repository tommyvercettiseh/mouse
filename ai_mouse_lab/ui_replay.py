from __future__ import annotations

import time
from typing import Any

import customtkinter as ctk

from .comparison_flow import latest_comparison
from .models import normalize_trials, trial_duration_ms, visible_points
from .ui_helpers import click_is_visible, visible_miss_clicks
from .ui_theme import (
    BORDER,
    FRAME_MS,
    GREEN,
    MUTED,
    PANEL,
    PANEL2,
    PURPLE,
    RED,
    TEXT,
    VIRTUAL_HEIGHT,
    VIRTUAL_WIDTH,
    Card,
)


class ReplayMixin:
    def init_replay_state(self) -> None:
        self.replay_a: dict[str, Any] = {}
        self.replay_b: dict[str, Any] = {}
        self.replay_index = 0
        self.replay_elapsed = 0.0
        self.replay_started = 0.0
        self.replay_running = False
        self.replay_finished = False
        self.replay_after_id: str | None = None
        self.replay_speed = 1.0

    def _page_results(self) -> None:
        body = self.page(
            "Results",
            "Results",
            "A en B automatisch achter elkaar in dezelfde 1920 × 1080 arena.",
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        controls = Card(body)
        controls.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(
            controls,
            text="← Aim Lab",
            fg_color=PANEL2,
            command=lambda: self.show("Aim Lab"),
        ).pack(side="left", padx=(12, 6), pady=10)
        ctk.CTkButton(
            controls,
            text="← Vorige",
            fg_color=PANEL2,
            command=lambda: self.replay_change(-1),
        ).pack(side="left", padx=6, pady=10)
        self.replay_play_btn = ctk.CTkButton(
            controls,
            text="▶ Alles afspelen",
            fg_color=PURPLE,
            command=self.replay_toggle,
        )
        self.replay_play_btn.pack(side="left", padx=6, pady=10)
        ctk.CTkButton(
            controls,
            text="Volgende →",
            fg_color=PANEL2,
            command=lambda: self.replay_change(1),
        ).pack(side="left", padx=6, pady=10)
        self.replay_speed_menu = ctk.CTkOptionMenu(
            controls,
            values=["0.5x", "1x", "1.5x", "2x"],
            width=82,
            command=self._set_replay_speed,
        )
        self.replay_speed_menu.set("1x")
        self.replay_speed_menu.pack(side="left", padx=6, pady=10)
        self.replay_equal = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            controls,
            text="Gelijke duur",
            variable=self.replay_equal,
            command=lambda: self.replay_draw(self._current_replay_elapsed()),
        ).pack(side="left", padx=8, pady=10)
        self.replay_label = ctk.CTkLabel(
            controls,
            text="Nog geen replay",
            text_color=MUTED,
            font=("Segoe UI", 12, "bold"),
        )
        self.replay_label.pack(side="right", padx=16)

        content = ctk.CTkFrame(body, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=4)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)
        arena = Card(content)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_columnconfigure(0, weight=1)
        arena.grid_rowconfigure(0, weight=1)
        self.replay_canvas = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        self.replay_canvas.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.replay_canvas.bind(
            "<Configure>",
            lambda _event: self.replay_draw(self._current_replay_elapsed()),
        )

        stats = Card(content)
        stats.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(
            stats,
            text="A · PAARS",
            text_color=PURPLE,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=16, pady=(18, 6))
        self.stats_a = ctk.CTkLabel(
            stats,
            text="",
            text_color=MUTED,
            justify="left",
            wraplength=260,
        )
        self.stats_a.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(
            stats,
            text="B · GROEN",
            text_color=GREEN,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=16, pady=(8, 6))
        self.stats_b = ctk.CTkLabel(
            stats,
            text="",
            text_color=MUTED,
            justify="left",
            wraplength=260,
        )
        self.stats_b.pack(anchor="w", padx=16, pady=(0, 14))

    def refresh_results(self) -> None:
        if self._replay_count() == 0:
            _folder, session_a, session_b = latest_comparison()
            trials_a = normalize_trials(session_a)
            trials_b = normalize_trials(session_b)
            self.replay_a = (
                {**session_a, "trials": trials_a}
                if isinstance(session_a, dict) and trials_a
                else {}
            )
            self.replay_b = (
                {**session_b, "trials": trials_b}
                if isinstance(session_b, dict) and trials_b
                else {}
            )
        count = self._replay_count()
        self.replay_index = max(0, min(max(0, count - 1), self.replay_index))
        self.replay_draw(self._current_replay_elapsed())

    @staticmethod
    def _session_trials(session: dict[str, Any]) -> list[dict[str, Any]]:
        trials = session.get("trials", []) if isinstance(session, dict) else []
        return trials if isinstance(trials, list) else []

    def _replay_trials(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return self._session_trials(self.replay_a), self._session_trials(self.replay_b)

    def _replay_count(self) -> int:
        trials_a, trials_b = self._replay_trials()
        return min(len(trials_a), len(trials_b))

    def _replay_duration(self) -> float:
        trials_a, trials_b = self._replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            return 0.0
        index = max(0, min(count - 1, self.replay_index))
        return max(
            16.0,
            trial_duration_ms(trials_a[index]),
            trial_duration_ms(trials_b[index]),
        )

    def _current_replay_elapsed(self) -> float:
        if not self.replay_running:
            return self.replay_elapsed
        return self.replay_elapsed + (
            (time.perf_counter() - self.replay_started) * 1000.0 * self.replay_speed
        )

    def _set_replay_speed(self, value: str) -> None:
        current = self._current_replay_elapsed()
        try:
            speed = max(0.1, float(value.rstrip("x")))
        except ValueError:
            speed = 1.0
        self.replay_elapsed = current
        self.replay_started = time.perf_counter()
        self.replay_speed = speed

    def replay_toggle(self) -> None:
        if self._replay_count() == 0:
            self.replay_label.configure(text="Geen geldige A/B-data", text_color=RED)
            return
        if self.replay_running:
            self.replay_elapsed = self._current_replay_elapsed()
            self._stop_replay()
            self.replay_play_btn.configure(text="▶ Verder afspelen")
            self.replay_draw(self.replay_elapsed)
            return
        if self.replay_finished:
            self.replay_index = 0
            self.replay_elapsed = 0.0
            self.replay_finished = False
        if self.replay_elapsed >= self._replay_duration():
            self.replay_elapsed = 0.0
        self.replay_running = True
        self.replay_started = time.perf_counter()
        self.replay_play_btn.configure(text="⏸ Pauze")
        self._replay_tick()

    def _replay_tick(self) -> None:
        if not self.replay_running:
            self.replay_after_id = None
            return
        elapsed = self._current_replay_elapsed()
        duration = self._replay_duration()
        if elapsed < duration:
            self.replay_draw(elapsed)
            self.replay_after_id = self.after(FRAME_MS, self._replay_tick)
            return
        self.replay_draw(duration)
        if self.replay_index < self._replay_count() - 1:
            self.replay_index += 1
            self.replay_elapsed = 0.0
            self.replay_started = time.perf_counter()
            self.replay_draw(0.0)
            self.replay_after_id = self.after(FRAME_MS, self._replay_tick)
            return
        self.replay_elapsed = duration
        self.replay_running = False
        self.replay_finished = True
        self.replay_after_id = None
        self.replay_play_btn.configure(text="↻ Opnieuw afspelen")
        count = self._replay_count()
        self.replay_label.configure(
            text=f"Klaar · {count}/{count} targets",
            text_color=TEXT,
        )

    def replay_change(self, delta: int) -> None:
        count = self._replay_count()
        if count == 0:
            return
        self._stop_replay()
        self.replay_finished = False
        self.replay_index = max(0, min(count - 1, self.replay_index + delta))
        self.replay_elapsed = 0.0
        self.replay_play_btn.configure(text="▶ Vanaf hier afspelen")
        self.replay_draw(0.0)

    def _pause_replay(self) -> None:
        if self.replay_running:
            self.replay_elapsed = self._current_replay_elapsed()
        self._stop_replay()

    def _stop_replay(self) -> None:
        self.replay_running = False
        self._cancel_after("replay_after_id")

    def replay_draw(self, elapsed: float) -> None:
        canvas = getattr(self, "replay_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        trials_a, trials_b = self._replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            canvas.create_text(
                max(1, canvas.winfo_width()) / 2,
                max(1, canvas.winfo_height()) / 2,
                text="Nog geen A/B-vergelijking",
                fill=MUTED,
                font=("Segoe UI", 18, "bold"),
            )
            self.stats_a.configure(text="")
            self.stats_b.configure(text="")
            self.replay_label.configure(text="Nog geen replay", text_color=MUTED)
            return

        index = max(0, min(count - 1, self.replay_index))
        trial_a = trials_a[index]
        trial_b = trials_b[index]
        duration_a = trial_duration_ms(trial_a)
        duration_b = trial_duration_ms(trial_b)
        if self.replay_equal.get():
            common = max(duration_a, duration_b, 1.0)
            elapsed_a = min(duration_a, elapsed / common * duration_a)
            elapsed_b = min(duration_b, elapsed / common * duration_b)
        else:
            elapsed_a = min(duration_a, elapsed)
            elapsed_b = min(duration_b, elapsed)

        scale, offset_x, offset_y = self._canvas_box(canvas)
        canvas.create_rectangle(
            offset_x,
            offset_y,
            offset_x + VIRTUAL_WIDTH * scale,
            offset_y + VIRTUAL_HEIGHT * scale,
            outline=BORDER,
        )
        target = trial_a["target"]
        target_x, target_y = self._to_canvas(
            canvas,
            float(target["x"]),
            float(target["y"]),
        )
        radius = float(target["radius"]) * scale
        canvas.create_oval(
            target_x - radius,
            target_y - radius,
            target_x + radius,
            target_y + radius,
            outline="white",
            width=2,
        )
        canvas.create_text(target_x, target_y, text=str(index + 1), fill="white")
        self._draw_trial(canvas, trial_a, elapsed_a, PURPLE)
        self._draw_trial(canvas, trial_b, elapsed_b, GREEN)
        self.stats_a.configure(text=self._stats_text(trial_a))
        self.stats_b.configure(text=self._stats_text(trial_b))
        self.replay_label.configure(text=f"Target {index + 1}/{count}", text_color=TEXT)

    def _draw_trial(
        self,
        canvas: ctk.CTkCanvas,
        trial: dict[str, Any],
        elapsed_ms: float,
        color: str,
    ) -> None:
        self._draw_route(canvas, visible_points(trial, elapsed_ms), color)
        for miss in visible_miss_clicks(trial, elapsed_ms):
            self._draw_click_marker(canvas, miss, RED, miss=True)
        click = trial.get("click", {})
        if isinstance(click, dict) and click_is_visible(click, elapsed_ms):
            self._draw_click_marker(canvas, click, color, miss=False)

    def _draw_route(
        self,
        canvas: ctk.CTkCanvas,
        points: list[dict[str, float]],
        color: str,
    ) -> None:
        if not points:
            return
        coordinates: list[float] = []
        for point in points:
            x, y = self._to_canvas(canvas, point["x"], point["y"])
            coordinates.extend((x, y))
        if len(coordinates) >= 4:
            canvas.create_line(*coordinates, fill=color, width=3, smooth=True)
        x, y = coordinates[-2], coordinates[-1]
        canvas.create_oval(
            x - 5,
            y - 5,
            x + 5,
            y + 5,
            fill=color,
            outline="white",
            width=1,
        )

    def _draw_click_marker(
        self,
        canvas: ctk.CTkCanvas,
        click: dict[str, Any],
        color: str,
        *,
        miss: bool,
    ) -> None:
        try:
            x, y = self._to_canvas(canvas, float(click["x"]), float(click["y"]))
        except (KeyError, TypeError, ValueError):
            return
        radius = 8 if miss else 10
        canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=color,
            width=3,
        )
        if miss:
            canvas.create_line(x - 5, y - 5, x + 5, y + 5, fill=color, width=2)
            canvas.create_line(x - 5, y + 5, x + 5, y - 5, fill=color, width=2)

    @staticmethod
    def _stats_text(trial: dict[str, Any]) -> str:
        derived = trial.get("derived", {})
        if not isinstance(derived, dict):
            derived = {}
        click_error = float(derived.get("click_error_px", 0) or 0)
        target = trial.get("target", {})
        radius = float(target.get("radius", 0) or 0) if isinstance(target, dict) else 0.0
        edge_padding = radius - click_error
        return (
            f"Reactie: {float(derived.get('reaction_ms', 0) or 0):.0f} ms\n"
            f"Beweging: {float(derived.get('movement_time_ms', 0) or 0):.0f} ms\n"
            f"Efficiëntie: {float(derived.get('path_efficiency', 0) or 0):.3f}\n"
            f"Klikfout: {click_error:.1f} px\n"
            f"Randpadding: {edge_padding:.1f} px\n"
            f"Overshoot: {float(derived.get('overshoot_px', 0) or 0):.1f} px\n"
            f"Piek accel.: {float(derived.get('peak_accel_px_s2', 0) or 0):.0f}\n"
            f"Piek remming: {float(derived.get('peak_decel_px_s2', 0) or 0):.0f}\n"
            f"Remstart: {float(derived.get('braking_start_ms', 0) or 0):.0f} ms\n"
            f"Remafstand: {float(derived.get('braking_distance_px', 0) or 0):.1f} px\n"
            f"Slowdown: {float(derived.get('slowdown_ratio', 0) or 0):.3f}\n"
            f"Correcties: {int(float(derived.get('correction_count', 0) or 0))}\n"
            f"Misklikken: {len(trial.get('miss_clicks', []))}"
        )
