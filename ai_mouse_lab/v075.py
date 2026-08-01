from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import customtkinter as ctk

from .replay import source_size, trial_duration_ms, visible_points
from .storage import BENCHMARKS, RECORDINGS, now_stamp, read_json, write_json
from .v06 import VIRTUAL_HEIGHT, VIRTUAL_WIDTH, _canvas_box, _to_canvas

PURPLE_ALPHA = "#8b5cf6"
GREEN_ALPHA = "#3ccf78"


def apply_patch(original_app: Any) -> None:
    old_page_simple = original_app.App._page_simple

    # ------------------------------------------------------------------
    # Free Record
    # ------------------------------------------------------------------
    def _page_free_record(self: Any) -> None:
        body = self.page(
            "Free Record",
            "Free Record",
            "Neem vrije muisbewegingen op buiten targets om je natuurlijke timing en routevorm te bewaren.",
        )
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        arena = original_app.Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        self.free_canvas = ctk.CTkCanvas(arena, bg=original_app.PANEL, highlightthickness=0)
        self.free_canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)

        side = original_app.Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="Vrije opname", text_color=original_app.TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(
            side,
            text="Beweeg normaal over je scherm. Deze opname wordt apart opgeslagen en vervuilt je Aim Lab-profiel niet automatisch.",
            text_color=original_app.MUTED,
            justify="left",
            wraplength=245,
        ).pack(anchor="w", padx=18, pady=(0, 12))

        self.free_start_btn = ctk.CTkButton(side, text="▶ Start opname", fg_color=original_app.PURPLE, height=44, command=self.free_record_start)
        self.free_start_btn.pack(fill="x", padx=18, pady=6)
        self.free_pause_btn = ctk.CTkButton(side, text="⏸ Pauze", fg_color=original_app.PANEL2, height=42, command=self.free_record_pause, state="disabled")
        self.free_pause_btn.pack(fill="x", padx=18, pady=6)
        self.free_stop_btn = ctk.CTkButton(side, text="■ Stop en opslaan", fg_color=original_app.PANEL2, height=42, command=self.free_record_stop, state="disabled")
        self.free_stop_btn.pack(fill="x", padx=18, pady=6)
        self.free_status = ctk.CTkLabel(side, text="Klaar voor opname", text_color=original_app.MUTED, justify="left", font=("Consolas", 12))
        self.free_status.pack(anchor="w", padx=18, pady=16)

        self.free_recording = False
        self.free_paused = False
        self.free_points: list[dict[str, float]] = []
        self.free_started_at = 0.0
        self.free_pause_started = 0.0
        self.free_paused_total = 0.0
        self.free_after_id = None
        self.free_last_drawn = 0

    def _page_simple(self: Any, key: str, title: str, text: str) -> None:
        if key == "Free Record":
            _page_free_record(self)
            return
        old_page_simple(self, key, title, text)

    def free_record_start(self: Any) -> None:
        if getattr(self, "free_recording", False):
            return
        self.free_recording = True
        self.free_paused = False
        self.free_points = []
        self.free_started_at = time.perf_counter()
        self.free_paused_total = 0.0
        self.free_last_drawn = 0
        self.free_canvas.delete("all")
        self.free_start_btn.configure(state="disabled")
        self.free_pause_btn.configure(state="normal", text="⏸ Pauze")
        self.free_stop_btn.configure(state="normal")
        self.free_record_tick()

    def free_record_pause(self: Any) -> None:
        if not getattr(self, "free_recording", False):
            return
        if not self.free_paused:
            self.free_paused = True
            self.free_pause_started = time.perf_counter()
            self.free_pause_btn.configure(text="▶ Hervatten")
        else:
            self.free_paused_total += time.perf_counter() - self.free_pause_started
            self.free_paused = False
            self.free_pause_btn.configure(text="⏸ Pauze")

    def _draw_free_preview(self: Any) -> None:
        points = self.free_points
        if len(points) < 2:
            return
        width = max(100.0, float(self.free_canvas.winfo_width()))
        height = max(100.0, float(self.free_canvas.winfo_height()))
        screen_w = max(1.0, float(self.winfo_screenwidth()))
        screen_h = max(1.0, float(self.winfo_screenheight()))
        start = max(1, self.free_last_drawn)
        for i in range(start, len(points)):
            a, b = points[i - 1], points[i]
            self.free_canvas.create_line(
                a["x"] / screen_w * width,
                a["y"] / screen_h * height,
                b["x"] / screen_w * width,
                b["y"] / screen_h * height,
                fill=original_app.PURPLE,
                width=2,
            )
        self.free_last_drawn = len(points)

    def free_record_tick(self: Any) -> None:
        if not getattr(self, "free_recording", False):
            self.free_after_id = None
            return
        if not getattr(self, "free_paused", False):
            x, y = self.winfo_pointerxy()
            elapsed = (time.perf_counter() - self.free_started_at - self.free_paused_total) * 1000.0
            self.free_points.append({"t_ms": round(elapsed, 3), "x": float(x), "y": float(y)})
            if len(self.free_points) % 2 == 0:
                _draw_free_preview(self)
            if len(self.free_points) % 12 == 0:
                self.free_status.configure(text=f"Opnemen…\nPunten: {len(self.free_points)}\nDuur: {elapsed / 1000:.1f} s")
        self.free_after_id = self.after(8, self.free_record_tick)

    def free_record_stop(self: Any) -> None:
        if not getattr(self, "free_recording", False):
            return
        self.free_recording = False
        if self.free_after_id:
            try:
                self.after_cancel(self.free_after_id)
            except Exception:
                pass
        self.free_after_id = None
        if self.free_paused:
            self.free_paused_total += time.perf_counter() - self.free_pause_started
            self.free_paused = False
        duration = self.free_points[-1]["t_ms"] if self.free_points else 0.0
        payload = {
            "schema_version": 1,
            "coordinate_space": "global_screen",
            "screen": {"width": self.winfo_screenwidth(), "height": self.winfo_screenheight()},
            "duration_ms": round(duration, 3),
            "point_count": len(self.free_points),
            "points": self.free_points,
            "created_at": datetime.now().isoformat(),
        }
        path = RECORDINGS / f"free_{now_stamp()}.json"
        write_json(path, payload)
        self.free_start_btn.configure(state="normal")
        self.free_pause_btn.configure(state="disabled", text="⏸ Pauze")
        self.free_stop_btn.configure(state="disabled")
        self.free_status.configure(text=f"Opgeslagen\nPunten: {len(self.free_points)}\nDuur: {duration / 1000:.1f} s\n{path.name}")

    # ------------------------------------------------------------------
    # Full-size shared A/B replay
    # ------------------------------------------------------------------
    def _page_results(self: Any) -> None:
        body = self.page("Results", "Results", "A en B simultaan over elkaar in dezelfde 1920 × 1080 arena als Aim Lab.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        controls = original_app.Card(body)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 10))
        controls.grid_columnconfigure(6, weight=1)
        self.replay_prev_btn = ctk.CTkButton(controls, text="← Vorige", width=92, fg_color=original_app.PANEL2, command=lambda: self.replay_change_trial(-1))
        self.replay_prev_btn.grid(row=0, column=0, padx=(14, 6), pady=12)
        self.replay_play_btn = ctk.CTkButton(controls, text="▶ Afspelen", width=105, fg_color=original_app.PURPLE, command=self.replay_toggle)
        self.replay_play_btn.grid(row=0, column=1, padx=6, pady=12)
        self.replay_next_btn = ctk.CTkButton(controls, text="Volgende →", width=98, fg_color=original_app.PANEL2, command=lambda: self.replay_change_trial(1))
        self.replay_next_btn.grid(row=0, column=2, padx=6, pady=12)
        self.replay_speed = ctk.CTkOptionMenu(controls, values=["0.5x", "1x", "2x"], width=85, fg_color=original_app.PANEL2, button_color=original_app.PURPLE)
        self.replay_speed.set("1x")
        self.replay_speed.grid(row=0, column=3, padx=(18, 6), pady=12)
        self.replay_normalized = ctk.CTkCheckBox(controls, text="Gelijke duur", command=self.replay_reset, text_color=original_app.MUTED)
        self.replay_normalized.grid(row=0, column=4, padx=12, pady=12)
        self.replay_trial_label = ctk.CTkLabel(controls, text="Geen benchmark", text_color=original_app.TEXT, font=("Segoe UI", 14, "bold"))
        self.replay_trial_label.grid(row=0, column=6, sticky="e", padx=16)

        arena = original_app.Card(body)
        arena.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        self.replay_canvas = ctk.CTkCanvas(arena, bg=original_app.PANEL, highlightthickness=0)
        self.replay_canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)

        side = original_app.Card(body)
        side.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="A · PAARS", text_color=original_app.PURPLE, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        self.replay_stats_a = ctk.CTkLabel(side, text="", text_color=original_app.MUTED, justify="left", wraplength=260)
        self.replay_stats_a.pack(anchor="w", padx=18, pady=(0, 16))
        ctk.CTkLabel(side, text="B · GROEN", text_color=original_app.GREEN, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(4, 4))
        self.replay_stats_b = ctk.CTkLabel(side, text="", text_color=original_app.MUTED, justify="left", wraplength=260)
        self.replay_stats_b.pack(anchor="w", padx=18, pady=(0, 16))
        ctk.CTkLabel(side, text="Beide routes gebruiken exact dezelfde virtuele arena en targetpositie.", text_color=original_app.MUTED, justify="left", wraplength=250).pack(anchor="w", padx=18, pady=12)

        self.replay_a: dict[str, Any] = {}
        self.replay_b: dict[str, Any] = {}
        self.replay_folder = None
        self.replay_trial_index = 0
        self.replay_elapsed_ms = 0.0
        self.replay_started_at = 0.0
        self.replay_running = False
        self.replay_after_id = None

    def _stats_text(trial: dict[str, Any]) -> str:
        d = trial.get("derived", {})
        return (
            f"Reactie: {d.get('reaction_ms', 0):.0f} ms\n"
            f"Beweging: {d.get('movement_time_ms', 0):.0f} ms\n"
            f"Efficiëntie: {d.get('path_efficiency', 0):.3f}\n"
            f"Overshoot: {d.get('overshoot_px', 0):.1f} px\n"
            f"Correcties: {d.get('correction_count', 0)}\n"
            f"Misklikken: {len(trial.get('miss_clicks', []))}"
        )

    def _draw_overlay_route(self: Any, trial: dict[str, Any], points: list[dict[str, Any]], color: str, tag: str) -> None:
        coords: list[float] = []
        for p in points:
            x, y = _to_canvas(self.replay_canvas, float(p.get("x", 0)), float(p.get("y", 0)))
            coords.extend((x, y))
        if len(coords) >= 4:
            self.replay_canvas.create_line(*coords, fill=color, width=3, smooth=True, tags=tag)
        if points:
            x, y = _to_canvas(self.replay_canvas, float(points[-1].get("x", 0)), float(points[-1].get("y", 0)))
            self.replay_canvas.create_oval(x-5, y-5, x+5, y+5, fill=color, outline="white", width=1, tags=tag)

    def replay_draw(self: Any, elapsed_ms: float | None = None) -> None:
        canvas = getattr(self, "replay_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        trials_a, trials_b = self.replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            canvas.create_text(max(1, canvas.winfo_width()) / 2, max(1, canvas.winfo_height()) / 2, text="Nog geen A/B benchmark", fill=original_app.MUTED, font=("Segoe UI", 18, "bold"))
            return

        index = max(0, min(count - 1, self.replay_trial_index))
        a, b = trials_a[index], trials_b[index]
        duration_a = trial_duration_ms(a)
        duration_b = trial_duration_ms(b)
        elapsed = self.replay_elapsed_ms if elapsed_ms is None else elapsed_ms
        if self.replay_normalized.get():
            common = max(duration_a, duration_b, 1.0)
            elapsed_a = min(duration_a, elapsed / common * duration_a)
            elapsed_b = min(duration_b, elapsed / common * duration_b)
        else:
            elapsed_a = min(duration_a, elapsed)
            elapsed_b = min(duration_b, elapsed)

        scale, ox, oy = _canvas_box(canvas)
        canvas.create_rectangle(ox, oy, ox + VIRTUAL_WIDTH * scale, oy + VIRTUAL_HEIGHT * scale, outline="#2a3442", width=1)
        target = a.get("target", b.get("target", {}))
        tx, ty = _to_canvas(canvas, float(target.get("x", 0)), float(target.get("y", 0)))
        radius = max(5.0, float(target.get("radius", 18)) * scale)
        canvas.create_oval(tx-radius, ty-radius, tx+radius, ty+radius, fill="#1a2330", outline="white", width=2, tags="target")
        canvas.create_text(tx, ty, text=str(index + 1), fill="white", tags="target")

        points_a = visible_points(a.get("points", []), elapsed_a)
        points_b = visible_points(b.get("points", []), elapsed_b)
        _draw_overlay_route(self, a, points_a, original_app.PURPLE, "route_a")
        _draw_overlay_route(self, b, points_b, original_app.GREEN, "route_b")

        self.replay_trial_label.configure(text=f"Trial {index + 1} / {count} · {elapsed:.0f} ms")
        self.replay_stats_a.configure(text=_stats_text(a))
        self.replay_stats_b.configure(text=_stats_text(b))

    original_app.App._page_simple = _page_simple
    original_app.App.free_record_start = free_record_start
    original_app.App.free_record_pause = free_record_pause
    original_app.App.free_record_stop = free_record_stop
    original_app.App.free_record_tick = free_record_tick
    original_app.App._page_results = _page_results
    original_app.App.replay_draw = replay_draw
