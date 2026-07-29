from __future__ import annotations

import time
from typing import Any

import customtkinter as ctk

from .metrics import derive_trial
from .replay import scale_point, source_size, trial_duration_ms, visible_points
from .storage import PROFILES, read_json
from .ui_helpers import is_target_hit
from .v06 import VIRTUAL_HEIGHT, VIRTUAL_WIDTH, _canvas_box, _to_canvas, _to_virtual


def _draw_static_arena(app: Any, canvas: ctk.CTkCanvas, target: dict[str, Any], color: str) -> None:
    canvas.delete("all")
    scale, ox, oy = _canvas_box(canvas)
    canvas.create_rectangle(
        ox,
        oy,
        ox + VIRTUAL_WIDTH * scale,
        oy + VIRTUAL_HEIGHT * scale,
        outline="#2a3442",
        width=1,
        tags="arena",
    )
    tx, ty = _to_canvas(canvas, float(target["x"]), float(target["y"]))
    radius = max(5.0, float(target["radius"]) * scale)
    canvas.create_oval(
        tx - radius,
        ty - radius,
        tx + radius,
        ty + radius,
        fill=color,
        outline="#e5e7eb",
        width=2,
        tags="target",
    )
    canvas.create_text(tx, ty, text=str(int(target["index"]) + 1), fill="white", tags="target")


def _append_trace(canvas: ctk.CTkCanvas, points: list[dict[str, Any]], color: str) -> None:
    if not points:
        return
    x, y = _to_canvas(canvas, float(points[-1]["x"]), float(points[-1]["y"]))
    if len(points) >= 2:
        px, py = _to_canvas(canvas, float(points[-2]["x"]), float(points[-2]["y"]))
        canvas.create_line(px, py, x, y, fill=color, width=2.5, capstyle="round", tags="trace")
    cursor = canvas.find_withtag("cursor")
    if cursor:
        canvas.coords(cursor[0], x - 4, y - 4, x + 4, y + 4)
    else:
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="white", width=1, tags="cursor")


def _stats_text(trial: dict[str, Any]) -> str:
    derived = trial.get("derived", {})
    return (
        f"A paars · B groen   |   "
        f"overshoot {derived.get('overshoot_px', 0):.1f}px   ·   "
        f"correcties {derived.get('correction_count', 0)}   ·   "
        f"misklikken {len(trial.get('miss_clicks', []))}"
    )


def apply_patch(original_app: Any) -> None:
    def show_target(self: Any) -> None:
        if self.index >= len(self.plan):
            self.finish_aim()
            return
        self.target_spawn = time.perf_counter()
        self.start_point = self.pointer_canvas(self.canvas)
        self.points, self.miss_clicks = [], []
        self.click_down = None
        _draw_static_arena(original_app, self.canvas, self.plan[self.index], original_app.PURPLE)
        self.append_point(*self.start_point)

    def append_point(self: Any, x: float, y: float) -> None:
        if not self.aim_active:
            return
        point = {
            "t_ms": round((time.perf_counter() - self.target_spawn) * 1000, 3),
            "x": float(round(x)),
            "y": float(round(y)),
        }
        self.points.append(point)
        _append_trace(self.canvas, self.points, original_app.PURPLE)
        self.aim_status.configure(
            text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: {len(self.points)}\nMisklikken: {len(self.miss_clicks)}"
        )

    def on_press(self: Any, event: Any) -> None:
        if self.aim_active:
            self.click_down = time.perf_counter()
            x, y = _to_virtual(self.canvas, float(event.x), float(event.y))
            self.append_point(x, y)

    def on_release(self: Any, event: Any) -> None:
        if not self.aim_active:
            return
        released = time.perf_counter()
        x, y = _to_virtual(self.canvas, float(event.x), float(event.y))
        self.append_point(x, y)
        target = self.plan[self.index]
        down_ms = round(((self.click_down or released) - self.target_spawn) * 1000, 3)
        up_ms = round((released - self.target_spawn) * 1000, 3)
        click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(round(x)), "y": float(round(y))}

        if not is_target_hit(x, y, target):
            self.miss_clicks.append(click)
            self.click_down = None
            self.aim_status.configure(
                text=f"Target {self.index + 1}/{len(self.plan)}\nMisklikken: {len(self.miss_clicks)}\nRaak hetzelfde target"
            )
            return

        target_data = {"index": target["index"], "x": target["x"], "y": target["y"], "radius": target["radius"]}
        start = {"x": float(round(self.start_point[0])), "y": float(round(self.start_point[1]))}
        derived = derive_trial(target_data, start, self.points, click)
        self.trials.append({
            "schema_version": 5,
            "target": target_data,
            "start": start,
            "points": list(self.points),
            "click": click,
            "miss_clicks": list(self.miss_clicks),
            "derived": derived,
        })
        self.index += 1
        self.show_target()

    def _page_benchmark(self: Any) -> None:
        body = self.page("Benchmark", "Benchmark", "Speel de benchmark en bekijk mens en generator daarna tegelijk op één arena.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_rowconfigure(3, weight=1)

        controls = original_app.Card(body)
        controls.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 8))
        controls.grid_columnconfigure(8, weight=1)
        self.bench_count_value = ctk.IntVar(value=30)
        self.bench_count_label = ctk.CTkLabel(controls, text="30 targets", text_color=original_app.TEXT, font=("Segoe UI", 14, "bold"))
        self.bench_count_label.grid(row=0, column=0, padx=(16, 8), pady=12)
        self.bench_count_slider = ctk.CTkSlider(
            controls,
            from_=10,
            to=100,
            number_of_steps=18,
            width=210,
            variable=self.bench_count_value,
            command=lambda value: self.bench_count_label.configure(text=f"{int(round(value / 5) * 5)} targets"),
        )
        self.bench_count_slider.grid(row=0, column=1, padx=8, pady=12)
        self.bench_start_btn = ctk.CTkButton(controls, text="Start benchmark", fg_color=original_app.PURPLE, width=130, command=self.start_benchmark)
        self.bench_start_btn.grid(row=0, column=2, padx=8, pady=12)
        self.bench_open_btn = ctk.CTkButton(controls, text="Open map", fg_color=original_app.PANEL2, width=90, command=self.open_benchmark_folder, state="disabled")
        self.bench_open_btn.grid(row=0, column=3, padx=8, pady=12)
        self.bench_status = ctk.CTkLabel(controls, text="Klaar", text_color=original_app.MUTED)
        self.bench_status.grid(row=0, column=8, sticky="e", padx=16)

        play = original_app.Card(body)
        play.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        play.grid_rowconfigure(0, weight=1)
        play.grid_columnconfigure(0, weight=1)
        self.bench_canvas = ctk.CTkCanvas(play, bg=original_app.PANEL, highlightthickness=0, height=410)
        self.bench_canvas.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.bench_canvas.bind("<ButtonPress-1>", self.bench_press)
        self.bench_canvas.bind("<ButtonRelease-1>", self.bench_release)

        replay_controls = original_app.Card(body)
        replay_controls.grid(row=2, column=0, sticky="ew", padx=6, pady=(8, 6))
        self.replay_prev_btn = ctk.CTkButton(replay_controls, text="← Vorige", width=88, fg_color=original_app.PANEL2, command=lambda: self.replay_change_trial(-1))
        self.replay_prev_btn.pack(side="left", padx=(12, 5), pady=10)
        self.replay_play_btn = ctk.CTkButton(replay_controls, text="▶ Afspelen", width=105, fg_color=original_app.PURPLE, command=self.replay_toggle)
        self.replay_play_btn.pack(side="left", padx=5, pady=10)
        self.replay_next_btn = ctk.CTkButton(replay_controls, text="Volgende →", width=96, fg_color=original_app.PANEL2, command=lambda: self.replay_change_trial(1))
        self.replay_next_btn.pack(side="left", padx=5, pady=10)
        self.replay_speed = ctk.CTkOptionMenu(replay_controls, values=["0.5x", "1x", "2x"], width=78, fg_color=original_app.PANEL2, button_color=original_app.PURPLE)
        self.replay_speed.set("1x")
        self.replay_speed.pack(side="left", padx=12, pady=10)
        self.replay_normalized = ctk.CTkCheckBox(replay_controls, text="Gelijke duur", command=self.replay_reset, text_color=original_app.MUTED)
        self.replay_normalized.pack(side="left", padx=8, pady=10)
        self.replay_trial_label = ctk.CTkLabel(replay_controls, text="Nog geen replay", text_color=original_app.TEXT, font=("Segoe UI", 14, "bold"))
        self.replay_trial_label.pack(side="right", padx=16, pady=10)

        overlay = original_app.Card(body)
        overlay.grid(row=3, column=0, sticky="nsew", padx=6, pady=6)
        overlay.grid_rowconfigure(1, weight=1)
        overlay.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(overlay, text="PAARS = A   ·   GROEN = B   ·   simultane overlay", text_color=original_app.TEXT, font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        self.replay_canvas = ctk.CTkCanvas(overlay, bg=original_app.PANEL, highlightthickness=0, height=330)
        self.replay_canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.replay_stats_a = ctk.CTkLabel(overlay, text="", text_color=original_app.PURPLE, justify="left")
        self.replay_stats_a.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 2))
        self.replay_stats_b = ctk.CTkLabel(overlay, text="", text_color=original_app.GREEN, justify="left")
        self.replay_stats_b.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 10))

        self.replay_a, self.replay_b, self.replay_folder = {}, {}, None
        self.replay_trial_index = 0
        self.replay_elapsed_ms = 0.0
        self.replay_started_at = 0.0
        self.replay_running = False
        self.replay_after_id = None

    def show_benchmark_target(self: Any) -> None:
        if self.bench_index >= len(self.bench_plan.get("targets", [])):
            self.finish_benchmark()
            return
        item = self.bench_plan["targets"][self.bench_index]
        target = {"index": item["index"], "x": item["target"][0], "y": item["target"][1], "radius": item["radius"]}
        self.bench_target_spawn = time.perf_counter()
        self.bench_start_point = self.pointer_canvas(self.bench_canvas)
        self.bench_points, self.bench_miss_clicks = [], []
        self.bench_click_down = None
        _draw_static_arena(original_app, self.bench_canvas, target, original_app.PURPLE)
        self.append_benchmark_point(*self.bench_start_point)

    def append_benchmark_point(self: Any, x: float, y: float) -> None:
        if not self.bench_active:
            return
        point = {
            "t_ms": round((time.perf_counter() - self.bench_target_spawn) * 1000, 3),
            "x": float(round(x)),
            "y": float(round(y)),
        }
        self.bench_points.append(point)
        _append_trace(self.bench_canvas, self.bench_points, original_app.PURPLE)
        self.bench_status.configure(
            text=f"Target {self.bench_index + 1}/{len(self.bench_plan['targets'])} · misklikken {len(self.bench_miss_clicks)}",
            text_color=original_app.MUTED,
        )

    def bench_press(self: Any, event: Any) -> None:
        if self.bench_active:
            self.bench_click_down = time.perf_counter()
            x, y = _to_virtual(self.bench_canvas, float(event.x), float(event.y))
            self.append_benchmark_point(x, y)

    def bench_release(self: Any, event: Any) -> None:
        if not self.bench_active:
            return
        released = time.perf_counter()
        x, y = _to_virtual(self.bench_canvas, float(event.x), float(event.y))
        self.append_benchmark_point(x, y)
        item = self.bench_plan["targets"][self.bench_index]
        target = {"index": item["index"], "x": item["target"][0], "y": item["target"][1], "radius": item["radius"]}
        down_ms = round(((self.bench_click_down or released) - self.bench_target_spawn) * 1000, 3)
        up_ms = round((released - self.bench_target_spawn) * 1000, 3)
        click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(round(x)), "y": float(round(y))}
        if not is_target_hit(x, y, target):
            self.bench_miss_clicks.append(click)
            self.bench_click_down = None
            return
        start = {"x": float(round(self.bench_start_point[0])), "y": float(round(self.bench_start_point[1]))}
        derived = derive_trial(target, start, self.bench_points, click)
        self.bench_trials.append({
            "schema_version": 5,
            "target": target,
            "start": start,
            "points": list(self.bench_points),
            "click": click,
            "miss_clicks": list(self.bench_miss_clicks),
            "derived": derived,
        })
        self.bench_index += 1
        self.show_benchmark_target()

    def replay_draw(self: Any, elapsed_ms: float | None = None) -> None:
        trials_a, trials_b = self.replay_trials()
        count = min(len(trials_a), len(trials_b))
        self.replay_canvas.delete("all")
        if count == 0:
            return

        self.replay_trial_index = min(self.replay_trial_index, count - 1)
        trial_a = trials_a[self.replay_trial_index]
        trial_b = trials_b[self.replay_trial_index]
        elapsed = self.replay_elapsed_ms if elapsed_ms is None else elapsed_ms
        duration_a = trial_duration_ms(trial_a)
        duration_b = trial_duration_ms(trial_b)
        normalized = max(duration_a, duration_b) if self.replay_normalized.get() else None
        points_a = visible_points(trial_a, elapsed, normalized)
        points_b = visible_points(trial_b, elapsed, normalized)

        self.replay_canvas.update_idletasks()
        width = max(100.0, float(self.replay_canvas.winfo_width()))
        height = max(100.0, float(self.replay_canvas.winfo_height()))
        size_a = source_size(self.replay_a)
        size_b = source_size(self.replay_b)
        source_w, source_h = max(size_a[0], size_b[0]), max(size_a[1], size_b[1])
        target = trial_a.get("target", {})
        tx, ty = scale_point(float(target.get("x", 0)), float(target.get("y", 0)), source_w, source_h, width, height)
        edge_x, _ = scale_point(float(target.get("x", 0)) + float(target.get("radius", 0)), float(target.get("y", 0)), source_w, source_h, width, height)
        radius = max(4.0, abs(edge_x - tx))
        self.replay_canvas.create_oval(tx - radius, ty - radius, tx + radius, ty + radius, outline="#e5e7eb", width=2)

        def draw_path(points: list[dict[str, Any]], color: str) -> None:
            coords: list[float] = []
            for point in points:
                x, y = scale_point(float(point.get("x", 0)), float(point.get("y", 0)), source_w, source_h, width, height)
                coords.extend((x, y))
            if len(coords) >= 4:
                self.replay_canvas.create_line(*coords, fill=color, width=3, smooth=True)
            if len(coords) >= 2:
                x, y = coords[-2], coords[-1]
                self.replay_canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="white", width=1)

        draw_path(points_a, original_app.PURPLE)
        draw_path(points_b, original_app.GREEN)
        self.replay_trial_label.configure(text=f"Trial {self.replay_trial_index + 1} / {count} · {elapsed:.0f} ms")
        self.replay_stats_a.configure(text="A · " + _stats_text(trial_a))
        self.replay_stats_b.configure(text="B · " + _stats_text(trial_b))

    def refresh_profile(self: Any) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            self.profile_label.configure(text="Nog geen profiel")
            return
        rate = float(profile.get("overshoot_rate", 0.0)) * 100.0
        positive = profile.get("overshoot_positive", {})
        self.profile_label.configure(text=(
            f"Kwaliteit: {profile.get('quality_percent', 0)}%\n"
            f"Targets: {profile.get('trial_count', 0)}\n"
            f"Ruwe punten: {profile.get('point_count', 0)}\n"
            f"Misses: {profile.get('miss_count', 0)}\n\n"
            f"Movement mediaan: {profile.get('features', {}).get('movement_time_ms', {}).get('median', 0)} ms\n"
            f"Overshootfrequentie: {rate:.1f}%\n"
            f"Overshoot mediaan wanneer aanwezig: {positive.get('median', 0)} px\n"
            f"Correcties mediaan: {profile.get('features', {}).get('correction_count', {}).get('median', 0)}"
        ))

    original_app.App.show_target = show_target
    original_app.App.append_point = append_point
    original_app.App.on_press = on_press
    original_app.App.on_release = on_release
    original_app.App._page_benchmark = _page_benchmark
    original_app.App.show_benchmark_target = show_benchmark_target
    original_app.App.append_benchmark_point = append_benchmark_point
    original_app.App.bench_press = bench_press
    original_app.App.bench_release = bench_release
    original_app.App.replay_draw = replay_draw
    original_app.App.refresh_profile = refresh_profile
