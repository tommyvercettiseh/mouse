from __future__ import annotations

import time
from typing import Any

import customtkinter as ctk

import app as original_app
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.ui_helpers import TRACE_COLOR, TRACE_WIDTH, is_target_hit, trace_coordinates


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


original_app.App.show_target = show_target
original_app.App.append_point = append_point
original_app.App.on_release = on_release
original_app.App.show_benchmark_target = show_benchmark_target
original_app.App.append_benchmark_point = append_benchmark_point
original_app.App.bench_release = bench_release


def main() -> None:
    ctk.set_appearance_mode("dark")
    original_app.App().mainloop()


if __name__ == "__main__":
    main()
