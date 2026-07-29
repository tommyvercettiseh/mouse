from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import customtkinter as ctk

import app as original_app
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.replay import scale_point, source_size, trial_duration_ms, visible_points
from ai_mouse_lab.storage import BENCHMARKS, read_json
from ai_mouse_lab.ui_helpers import TRACE_COLOR, TRACE_WIDTH, is_target_hit, trace_coordinates

A_COLOR = original_app.PURPLE
B_COLOR = original_app.GREEN


def _draw_scene(self, canvas: ctk.CTkCanvas, target: dict[str, Any], points: list[dict[str, Any]], index: int, misses: int = 0) -> None:
    canvas.delete("all")
    coordinates = trace_coordinates(points)
    if len(coordinates) >= 4:
        canvas.create_line(*coordinates, fill=TRACE_COLOR, width=TRACE_WIDTH, smooth=True, tags="trace")
    x, y, radius = float(target["x"]), float(target["y"]), float(target["radius"])
    canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=original_app.PURPLE, outline="#c4b5fd", width=3, tags="target")
    canvas.create_text(x, y, text=str(index + 1), fill="white", tags="target")
    if misses:
        canvas.create_text(12, 12, anchor="nw", text=f"Misklikken: {misses}", fill=original_app.RED, font=("Segoe UI", 11, "bold"))


def _ensure_state(self) -> None:
    if not hasattr(self, "miss_clicks"):
        self.miss_clicks = []
    if not hasattr(self, "bench_miss_clicks"):
        self.bench_miss_clicks = []


def show_target(self) -> None:
    _ensure_state(self)
    if self.index >= len(self.plan):
        self.finish_aim()
        return
    self.target_spawn = time.perf_counter()
    self.start_point = self.pointer_canvas(self.canvas)
    self.points = []
    self.miss_clicks = []
    self.click_down = None
    self.append_point(*self.start_point)


def append_point(self, x: float, y: float) -> None:
    _ensure_state(self)
    if not self.aim_active:
        return
    t_ms = round((time.perf_counter() - self.target_spawn) * 1000, 3)
    self.points.append({"t_ms": t_ms, "x": round(x, 3), "y": round(y, 3)})
    target = self.plan[self.index]
    _draw_scene(self, self.canvas, target, self.points, self.index, len(self.miss_clicks))
    self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: {len(self.points)}\nMisklikken: {len(self.miss_clicks)}")


def on_release(self, event) -> None:
    _ensure_state(self)
    if not self.aim_active:
        return
    released = time.perf_counter()
    self.append_point(float(event.x), float(event.y))
    target = self.plan[self.index]
    down_ms = round(((self.click_down or released) - self.target_spawn) * 1000, 3)
    up_ms = round((released - self.target_spawn) * 1000, 3)
    click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(event.x), "y": float(event.y)}

    if not is_target_hit(event.x, event.y, target):
        self.miss_clicks.append(click)
        self.click_down = None
        _draw_scene(self, self.canvas, target, self.points, self.index, len(self.miss_clicks))
        self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: {len(self.points)}\nMisklikken: {len(self.miss_clicks)}\nRaak hetzelfde target")
        return

    target_data = {"index": target["index"], "x": target["x"], "y": target["y"], "radius": target["radius"]}
    start_data = {"x": self.start_point[0], "y": self.start_point[1]}
    derived = derive_trial(target_data, start_data, self.points, click)
    self.trials.append({
        "schema_version": 5,
        "target": target_data,
        "start": start_data,
        "points": list(self.points),
        "click": click,
        "miss_clicks": list(self.miss_clicks),
        "derived": derived,
    })
    self.index += 1
    self.show_target()


def show_benchmark_target(self) -> None:
    _ensure_state(self)
    if self.bench_index >= len(self.bench_plan.get("targets", [])):
        self.finish_benchmark()
        return
    self.bench_target_spawn = time.perf_counter()
    self.bench_start_point = self.pointer_canvas(self.bench_canvas)
    self.bench_points = []
    self.bench_miss_clicks = []
    self.bench_click_down = None
    self.append_benchmark_point(*self.bench_start_point)


def _benchmark_target(self) -> dict[str, Any]:
    item = self.bench_plan["targets"][self.bench_index]
    x, y = item["target"]
    return {"index": item["index"], "x": x, "y": y, "radius": item["radius"]}


def append_benchmark_point(self, x: float, y: float) -> None:
    _ensure_state(self)
    if not self.bench_active:
        return
    t_ms = round((time.perf_counter() - self.bench_target_spawn) * 1000, 3)
    self.bench_points.append({"t_ms": t_ms, "x": round(x, 3), "y": round(y, 3)})
    target = _benchmark_target(self)
    _draw_scene(self, self.bench_canvas, target, self.bench_points, self.bench_index, len(self.bench_miss_clicks))
    self.bench_status.configure(text=f"Jij speelt\nTarget {self.bench_index + 1}/{len(self.bench_plan['targets'])}\nPoints: {len(self.bench_points)}\nMisklikken: {len(self.bench_miss_clicks)}")


def bench_release(self, event) -> None:
    _ensure_state(self)
    if not self.bench_active:
        return
    released = time.perf_counter()
    self.append_benchmark_point(float(event.x), float(event.y))
    target = _benchmark_target(self)
    down_ms = round(((self.bench_click_down or released) - self.bench_target_spawn) * 1000, 3)
    up_ms = round((released - self.bench_target_spawn) * 1000, 3)
    click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(event.x), "y": float(event.y)}

    if not is_target_hit(event.x, event.y, target):
        self.bench_miss_clicks.append(click)
        self.bench_click_down = None
        _draw_scene(self, self.bench_canvas, target, self.bench_points, self.bench_index, len(self.bench_miss_clicks))
        self.bench_status.configure(text=f"Jij speelt\nTarget {self.bench_index + 1}/{len(self.bench_plan['targets'])}\nMisklikken: {len(self.bench_miss_clicks)}\nRaak hetzelfde target")
        return

    start_data = {"x": self.bench_start_point[0], "y": self.bench_start_point[1]}
    derived = derive_trial(target, start_data, self.bench_points, click)
    self.bench_trials.append({
        "schema_version": 5,
        "target": target,
        "start": start_data,
        "points": list(self.bench_points),
        "click": click,
        "miss_clicks": list(self.bench_miss_clicks),
        "derived": derived,
    })
    self.bench_index += 1
    self.show_benchmark_target()


def _page_results(self) -> None:
    body = self.page("Results", "Results", "Bekijk A en B blind, side-by-side en exact gelijktijdig.")
    body.grid_columnconfigure((0, 1), weight=1)
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

    left = original_app.Card(body)
    left.grid(row=1, column=0, sticky="nsew", padx=(6, 5), pady=6)
    left.grid_rowconfigure(1, weight=1)
    left.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(left, text="A · PAARS", text_color=A_COLOR, font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
    self.replay_canvas_a = ctk.CTkCanvas(left, bg=original_app.PANEL, highlightthickness=0)
    self.replay_canvas_a.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
    self.replay_stats_a = ctk.CTkLabel(left, text="", text_color=original_app.MUTED, justify="left")
    self.replay_stats_a.grid(row=2, column=0, sticky="w", padx=16, pady=(2, 12))

    right = original_app.Card(body)
    right.grid(row=1, column=1, sticky="nsew", padx=(5, 6), pady=6)
    right.grid_rowconfigure(1, weight=1)
    right.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(right, text="B · GROEN", text_color=B_COLOR, font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
    self.replay_canvas_b = ctk.CTkCanvas(right, bg=original_app.PANEL, highlightthickness=0)
    self.replay_canvas_b.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
    self.replay_stats_b = ctk.CTkLabel(right, text="", text_color=original_app.MUTED, justify="left")
    self.replay_stats_b.grid(row=2, column=0, sticky="w", padx=16, pady=(2, 12))

    self.replay_a: dict[str, Any] = {}
    self.replay_b: dict[str, Any] = {}
    self.replay_folder: Path | None = None
    self.replay_trial_index = 0
    self.replay_elapsed_ms = 0.0
    self.replay_started_at = 0.0
    self.replay_running = False
    self.replay_after_id = None


def refresh_results(self) -> None:
    folders = sorted((path for path in BENCHMARKS.glob("*") if path.is_dir()), reverse=True)
    folder = next((path for path in folders if (path / "A.json").exists() and (path / "B.json").exists()), None)
    if folder is None:
        self.replay_a, self.replay_b = {}, {}
        self.replay_trial_label.configure(text="Nog geen A/B-bestanden")
        self.replay_draw()
        return
    if self.replay_folder != folder:
        self.replay_folder = folder
        self.replay_a = read_json(folder / "A.json", {})
        self.replay_b = read_json(folder / "B.json", {})
        self.replay_trial_index = 0
        self.replay_reset()
    else:
        self.replay_draw()


def replay_speed_value(self) -> float:
    return {"0.5x": 0.5, "1x": 1.0, "2x": 2.0}.get(self.replay_speed.get(), 1.0)


def replay_trials(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return self.replay_a.get("trials", []), self.replay_b.get("trials", [])


def replay_toggle(self) -> None:
    trials_a, trials_b = self.replay_trials()
    if not trials_a or not trials_b:
        return
    if self.replay_running:
        self.replay_elapsed_ms += (time.perf_counter() - self.replay_started_at) * 1000 * self.replay_speed_value()
        self.replay_running = False
        self.replay_play_btn.configure(text="▶ Afspelen")
    else:
        if self.replay_elapsed_ms >= self.replay_current_duration():
            self.replay_elapsed_ms = 0.0
        self.replay_started_at = time.perf_counter()
        self.replay_running = True
        self.replay_play_btn.configure(text="⏸ Pauze")
        self.replay_tick()


def replay_reset(self) -> None:
    self.replay_running = False
    self.replay_elapsed_ms = 0.0
    self.replay_started_at = 0.0
    if hasattr(self, "replay_play_btn"):
        self.replay_play_btn.configure(text="▶ Afspelen")
    self.replay_draw()


def replay_change_trial(self, delta: int) -> None:
    trials_a, trials_b = self.replay_trials()
    count = min(len(trials_a), len(trials_b))
    if count == 0:
        return
    self.replay_trial_index = max(0, min(count - 1, self.replay_trial_index + delta))
    self.replay_reset()


def replay_current_duration(self) -> float:
    trials_a, trials_b = self.replay_trials()
    if not trials_a or not trials_b:
        return 0.0
    a = trial_duration_ms(trials_a[self.replay_trial_index])
    b = trial_duration_ms(trials_b[self.replay_trial_index])
    if self.replay_normalized.get():
        return max(a, b)
    return max(a, b)


def replay_tick(self) -> None:
    if not self.replay_running:
        return
    elapsed = self.replay_elapsed_ms + (time.perf_counter() - self.replay_started_at) * 1000 * self.replay_speed_value()
    duration = self.replay_current_duration()
    if elapsed >= duration:
        self.replay_elapsed_ms = duration
        self.replay_running = False
        self.replay_play_btn.configure(text="↻ Opnieuw")
    self.replay_draw(elapsed)
    if self.replay_running:
        self.replay_after_id = self.after(16, self.replay_tick)


def _stats_text(trial: dict[str, Any]) -> str:
    derived = trial.get("derived", {})
    misses = len(trial.get("miss_clicks", []))
    return (
        f"Reactie: {derived.get('reaction_ms', 0):.0f} ms   ·   Beweging: {derived.get('movement_time_ms', 0):.0f} ms\n"
        f"Efficiëntie: {derived.get('path_efficiency', 0):.3f}   ·   Overshoot: {derived.get('overshoot_px', 0):.1f}px   ·   Correcties: {derived.get('correction_count', 0)}   ·   Misklikken: {misses}"
    )


def replay_draw(self, elapsed_ms: float | None = None) -> None:
    trials_a, trials_b = self.replay_trials()
    count = min(len(trials_a), len(trials_b))
    for canvas in (getattr(self, "replay_canvas_a", None), getattr(self, "replay_canvas_b", None)):
        if canvas:
            canvas.delete("all")
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

    self.replay_canvas_a.update_idletasks()
    self.replay_canvas_b.update_idletasks()
    size_a = source_size(self.replay_a)
    size_b = source_size(self.replay_b)
    source_w, source_h = max(size_a[0], size_b[0]), max(size_a[1], size_b[1])
    self.replay_draw_trial(self.replay_canvas_a, trial_a, points_a, A_COLOR, source_w, source_h)
    self.replay_draw_trial(self.replay_canvas_b, trial_b, points_b, B_COLOR, source_w, source_h)

    self.replay_trial_label.configure(text=f"Trial {self.replay_trial_index + 1} / {count}   ·   {elapsed:.0f} ms")
    self.replay_stats_a.configure(text=_stats_text(trial_a))
    self.replay_stats_b.configure(text=_stats_text(trial_b))


def replay_draw_trial(self, canvas: ctk.CTkCanvas, trial: dict[str, Any], points: list[dict[str, Any]], color: str, source_w: float, source_h: float) -> None:
    width = max(100.0, float(canvas.winfo_width()))
    height = max(100.0, float(canvas.winfo_height()))
    target = trial.get("target", {})
    tx, ty = scale_point(float(target.get("x", 0)), float(target.get("y", 0)), source_w, source_h, width, height)
    edge_x, _ = scale_point(float(target.get("x", 0)) + float(target.get("radius", 0)), float(target.get("y", 0)), source_w, source_h, width, height)
    radius = max(4.0, abs(edge_x - tx))
    canvas.create_oval(tx-radius, ty-radius, tx+radius, ty+radius, outline="#d7dce5", width=2)

    coords: list[float] = []
    for point in points:
        x, y = scale_point(float(point.get("x", 0)), float(point.get("y", 0)), source_w, source_h, width, height)
        coords.extend((x, y))
    if len(coords) >= 4:
        canvas.create_line(*coords, fill=color, width=3, smooth=True)
    if len(coords) >= 2:
        x, y = coords[-2], coords[-1]
        canvas.create_oval(x-5, y-5, x+5, y+5, fill=color, outline="white", width=1)


original_app.App.show_target = show_target
original_app.App.append_point = append_point
original_app.App.on_release = on_release
original_app.App.show_benchmark_target = show_benchmark_target
original_app.App.append_benchmark_point = append_benchmark_point
original_app.App.bench_release = bench_release
original_app.App._page_results = _page_results
original_app.App.refresh_results = refresh_results
original_app.App.replay_speed_value = replay_speed_value
original_app.App.replay_trials = replay_trials
original_app.App.replay_toggle = replay_toggle
original_app.App.replay_reset = replay_reset
original_app.App.replay_change_trial = replay_change_trial
original_app.App.replay_current_duration = replay_current_duration
original_app.App.replay_tick = replay_tick
original_app.App.replay_draw = replay_draw
original_app.App.replay_draw_trial = replay_draw_trial


def main() -> None:
    ctk.set_appearance_mode("dark")
    original_app.App().mainloop()


if __name__ == "__main__":
    main()
