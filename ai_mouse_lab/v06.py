from __future__ import annotations

import math
import random
import time
from pathlib import Path
from typing import Any

import customtkinter as ctk

from .benchmark import create_blind_export, generate_plan, plan_from_human_trials
from .metrics import derive_trial
from .replay import scale_point, source_size, trial_duration_ms, visible_points
from .storage import BENCHMARKS, PROFILES, read_json, write_json, now_stamp
from .ui_helpers import is_target_hit

VIRTUAL_WIDTH = 1920.0
VIRTUAL_HEIGHT = 1080.0


def _canvas_box(canvas: ctk.CTkCanvas) -> tuple[float, float, float]:
    canvas.update_idletasks()
    width = max(320.0, float(canvas.winfo_width()))
    height = max(240.0, float(canvas.winfo_height()))
    scale = min(width / VIRTUAL_WIDTH, height / VIRTUAL_HEIGHT)
    return scale, (width - VIRTUAL_WIDTH * scale) / 2.0, (height - VIRTUAL_HEIGHT * scale) / 2.0


def _to_canvas(canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
    scale, ox, oy = _canvas_box(canvas)
    return ox + x * scale, oy + y * scale


def _to_virtual(canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
    scale, ox, oy = _canvas_box(canvas)
    return (x - ox) / max(scale, 1e-9), (y - oy) / max(scale, 1e-9)


def _draw_virtual_scene(app: Any, canvas: ctk.CTkCanvas, target: dict[str, Any], points: list[dict[str, Any]], color: str, misses: int = 0) -> None:
    canvas.delete("all")
    scale, ox, oy = _canvas_box(canvas)
    canvas.create_rectangle(ox, oy, ox + VIRTUAL_WIDTH * scale, oy + VIRTUAL_HEIGHT * scale, outline="#2a3442", width=1)
    coords: list[float] = []
    for point in points:
        px, py = _to_canvas(canvas, float(point["x"]), float(point["y"]))
        coords.extend((px, py))
    if len(coords) >= 4:
        canvas.create_line(*coords, fill=color, width=2.5, smooth=True)
    tx, ty = _to_canvas(canvas, float(target["x"]), float(target["y"]))
    radius = max(5.0, float(target["radius"]) * scale)
    canvas.create_oval(tx-radius, ty-radius, tx+radius, ty+radius, fill=color, outline="#e5e7eb", width=2)
    canvas.create_text(tx, ty, text=str(int(target["index"]) + 1), fill="white")
    if misses:
        canvas.create_text(12, 12, anchor="nw", text=f"Misklikken: {misses}", fill=app.RED, font=("Segoe UI", 11, "bold"))


def _feature(profile: dict[str, Any], name: str, key: str, default: float) -> float:
    try:
        return float(profile.get("features", {}).get(name, {}).get(key, default))
    except (TypeError, ValueError):
        return default


def _candidate_templates(profile: dict[str, Any], distance: float, radius: float, angle: float) -> list[dict[str, Any]]:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for template in profile.get("route_templates", []):
        try:
            td = max(1.0, float(template["distance_px"]))
            ta = float(template.get("angle", angle))
            angle_cost = abs((angle - ta + math.pi) % (2 * math.pi) - math.pi) / math.pi
            cost = abs(math.log(max(distance, 1.0) / td)) * 2.6
            cost += abs(float(template.get("radius", radius)) - radius) / 22.0
            cost += angle_cost * 0.55
            efficiency = float(template.get("path_efficiency", 0.9))
            if efficiency < 0.55 or efficiency > 1.02:
                cost += 4.0
            candidates.append((cost, template))
        except (KeyError, TypeError, ValueError):
            continue
    candidates.sort(key=lambda item: item[0])
    return [item[1] for item in candidates[:12]]


def _personal_route(item: dict[str, Any], profile: dict[str, Any], rng: random.Random, session_scale: float) -> dict[str, Any]:
    sx, sy = map(float, item["start"])
    tx, ty = map(float, item["target"])
    radius = float(item["radius"])
    dx, dy = tx - sx, ty - sy
    distance = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / distance, dy / distance
    px, py = -uy, ux
    angle = math.atan2(dy, dx)

    templates = _candidate_templates(profile, distance, radius, angle)
    template = rng.choice(templates[: min(5, len(templates))]) if templates else None

    movement_med = max(120.0, _feature(profile, "movement_time_ms", "median", 650.0))
    movement_sd = max(35.0, _feature(profile, "movement_time_ms", "stdev", 140.0))
    reaction_med = max(15.0, _feature(profile, "reaction_ms", "median", 80.0))
    reaction_sd = max(10.0, _feature(profile, "reaction_ms", "stdev", 30.0))
    delay_med = max(20.0, _feature(profile, "click_delay_ms", "median", 90.0))
    delay_sd = max(12.0, _feature(profile, "click_delay_ms", "stdev", 40.0))
    hold_med = max(40.0, _feature(profile, "hold_ms", "median", 100.0))
    hold_sd = max(8.0, _feature(profile, "hold_ms", "stdev", 18.0))

    distance_factor = 0.62 + 0.38 * min(1.5, distance / 600.0)
    radius_factor = 1.08 if radius <= 12 else 1.0 if radius <= 18 else 0.94
    duration = max(100.0, rng.gauss(movement_med * distance_factor * radius_factor * session_scale, movement_sd * 0.38))
    reaction = max(8.0, rng.gauss(reaction_med * session_scale, reaction_sd * 0.55))

    if template and template.get("points"):
        source = template["points"]
        efficiency = float(template.get("path_efficiency", 0.9))
        side_scale = min(0.075, max(0.008, (1.0 - min(0.995, efficiency)) * 0.35))
    else:
        source = []
        side_scale = rng.uniform(0.012, 0.045)

    max_side = max(3.0, min(distance * 0.10, 58.0 if distance > 350 else 24.0))
    points: list[dict[str, float]] = []
    t = 0.0
    while t < reaction:
        t += max(7.0, rng.gauss(12.0, 3.0))
        points.append({"t_ms": round(min(t, reaction), 3), "x": float(round(sx)), "y": float(round(sy))})

    steps = max(28, min(115, int(duration / 10.5)))
    bend = max(-max_side, min(max_side, rng.gauss(0.0, distance * side_scale)))
    early_bias = rng.gauss(0.0, min(max_side * 0.35, 12.0))
    correction = rng.random() < (0.10 if radius <= 18 else 0.05)
    overshoot = rng.random() < (0.08 if radius <= 12 else 0.045)
    overshoot_px = rng.uniform(2.0, min(16.0, radius * 0.7)) if overshoot else 0.0

    for index in range(1, steps + 1):
        u = index / steps
        ease = 3 * u * u - 2 * u * u * u
        along = ease * (distance + overshoot_px)
        side = math.sin(math.pi * u) * bend
        side += math.sin(2 * math.pi * u) * early_bias * (1.0 - u)
        if correction and u > 0.72:
            side *= max(0.0, 1.0 - (u - 0.72) / 0.28)
        jitter = rng.gauss(0.0, 0.45 if u < 0.75 else 0.7)
        x = sx + ux * along + px * (side + jitter)
        y = sy + uy * along + py * (side + jitter)
        dt = max(6.0, rng.gauss(duration / steps, 2.6))
        t += dt
        points.append({"t_ms": round(t, 3), "x": float(round(x)), "y": float(round(y))})

    if overshoot:
        for fraction in (0.45, 0.72, 0.9, 1.0):
            t += max(8.0, rng.gauss(13.0, 2.5))
            last_x, last_y = points[-1]["x"], points[-1]["y"]
            points.append({
                "t_ms": round(t, 3),
                "x": float(round(last_x + (tx - last_x) * fraction)),
                "y": float(round(last_y + (ty - last_y) * fraction)),
            })

    click_error_sd = max(1.2, radius * (0.19 if radius <= 18 else 0.24))
    ex = rng.gauss(0.0, click_error_sd)
    ey = rng.gauss(0.0, click_error_sd)
    error_len = math.hypot(ex, ey)
    if error_len > radius * 0.82:
        scale = radius * 0.82 / error_len
        ex, ey = ex * scale, ey * scale
    click_x, click_y = float(round(tx + ex)), float(round(ty + ey))

    difficulty = min(2.0, distance / max(radius * 22.0, 1.0))
    delay = max(15.0, rng.gauss(delay_med * (0.78 + 0.22 * difficulty) * session_scale, delay_sd * 0.55))
    click_down = max(points[-1]["t_ms"], reaction) + delay
    hold = max(45.0, rng.gauss(hold_med, hold_sd * 0.65))

    miss_clicks: list[dict[str, float]] = []
    measured_miss = float(profile.get("miss_count", 0)) / max(float(profile.get("trial_count", 1)), 1.0)
    miss_probability = min(0.08, measured_miss * (1.25 if radius <= 12 else 0.7))
    if rng.random() < miss_probability:
        miss_angle = rng.uniform(0, math.tau)
        miss_distance = radius + rng.uniform(2.0, 8.0)
        miss_t = max(points[-1]["t_ms"], reaction) + max(20.0, delay * 0.55)
        miss_clicks.append({
            "down_t_ms": round(miss_t, 3),
            "up_t_ms": round(miss_t + hold * 0.85, 3),
            "x": float(round(tx + math.cos(miss_angle) * miss_distance)),
            "y": float(round(ty + math.sin(miss_angle) * miss_distance)),
        })
        click_down = miss_clicks[-1]["up_t_ms"] + rng.uniform(45.0, 105.0)

    click = {"down_t_ms": round(click_down, 3), "up_t_ms": round(click_down + hold, 3), "x": click_x, "y": click_y}
    target = {"index": int(item["index"]), "x": int(tx), "y": int(ty), "radius": int(radius)}
    start = {"x": float(round(sx)), "y": float(round(sy))}
    derived = derive_trial(target, start, points, click)
    return {"schema_version": 5, "target": target, "start": start, "points": points, "click": click, "miss_clicks": miss_clicks, "derived": derived}


def personal_simulate(plan: dict[str, Any], profile: dict[str, Any], seed: int | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else int(plan["seed"]) + 1)
    session_scale = rng.uniform(0.94, 1.08)
    return [_personal_route(item, profile, rng, session_scale) for item in plan["targets"]]


def apply_patch(original_app: Any) -> None:
    original_app.simulate = personal_simulate

    def pointer_canvas(self: Any, canvas: ctk.CTkCanvas) -> tuple[float, float]:
        screen_x, screen_y = self.winfo_pointerxy()
        return _to_virtual(canvas, float(screen_x - canvas.winfo_rootx()), float(screen_y - canvas.winfo_rooty()))

    def _page_aim(self: Any) -> None:
        body = self.page("Aim Lab", "Aim Lab", "Vaste virtuele arena van 1920 × 1080, automatisch passend in het venster.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        arena = original_app.Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        self.canvas = ctk.CTkCanvas(arena, bg=original_app.PANEL, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        side = original_app.Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="Sessie", text_color=original_app.TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        self.count_value = ctk.IntVar(value=30)
        self.count_label = ctk.CTkLabel(side, text="30 targets", text_color=original_app.TEXT, font=("Segoe UI", 15, "bold"))
        self.count_label.pack(anchor="w", padx=18, pady=(8, 2))
        self.count_slider = ctk.CTkSlider(side, from_=10, to=100, number_of_steps=18, variable=self.count_value, command=lambda value: self.count_label.configure(text=f"{int(round(value / 5) * 5)} targets"))
        self.count_slider.pack(fill="x", padx=18, pady=8)
        self.start_btn = ctk.CTkButton(side, text="Start Aim Lab", fg_color=original_app.PURPLE, height=46, command=self.start_aim)
        self.start_btn.pack(fill="x", padx=18, pady=8)
        self.aim_status = ctk.CTkLabel(side, text="Klaar", text_color=original_app.MUTED, justify="left", wraplength=230)
        self.aim_status.pack(anchor="w", padx=18, pady=12)

    def start_aim(self: Any) -> None:
        count = int(round(float(self.count_value.get()) / 5.0) * 5)
        self.plan = [{"index": index, "x": random.randint(80, 1840), "y": random.randint(80, 1000), "radius": random.choice([18, 26, 36])} for index in range(count)]
        self.trials, self.index, self.aim_active = [], 0, True
        self.session_folder = original_app.AIM / now_stamp()
        self.session_folder.mkdir(parents=True, exist_ok=True)
        write_json(self.session_folder / "plan.json", {"width": 1920, "height": 1080, "targets": self.plan})
        self.start_btn.configure(state="disabled")
        self.show_target()
        self.sample_pointer()

    def show_target(self: Any) -> None:
        if self.index >= len(self.plan):
            self.finish_aim()
            return
        self.target_spawn = time.perf_counter()
        self.start_point = self.pointer_canvas(self.canvas)
        self.points, self.miss_clicks = [], []
        self.click_down = None
        self.append_point(*self.start_point)

    def append_point(self: Any, x: float, y: float) -> None:
        if not self.aim_active:
            return
        t_ms = round((time.perf_counter() - self.target_spawn) * 1000, 3)
        self.points.append({"t_ms": t_ms, "x": float(round(x)), "y": float(round(y))})
        _draw_virtual_scene(original_app, self.canvas, self.plan[self.index], self.points, original_app.PURPLE, len(getattr(self, "miss_clicks", [])))
        self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: {len(self.points)}\nMisklikken: {len(getattr(self, 'miss_clicks', []))}")

    def _page_benchmark(self: Any) -> None:
        body = self.page("Benchmark", "Benchmark", "Instellen, spelen en A/B synchroon terugkijken in één hoofdflow.")
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(2, weight=1)
        controls = original_app.Card(body)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 8))
        controls.grid_columnconfigure(8, weight=1)
        self.bench_count_value = ctk.IntVar(value=30)
        self.bench_count_label = ctk.CTkLabel(controls, text="30 targets", text_color=original_app.TEXT, font=("Segoe UI", 14, "bold"))
        self.bench_count_label.grid(row=0, column=0, padx=(16, 8), pady=12)
        self.bench_count_slider = ctk.CTkSlider(controls, from_=10, to=100, number_of_steps=18, width=210, variable=self.bench_count_value, command=lambda value: self.bench_count_label.configure(text=f"{int(round(value / 5) * 5)} targets"))
        self.bench_count_slider.grid(row=0, column=1, padx=8, pady=12)
        self.bench_start_btn = ctk.CTkButton(controls, text="Start benchmark", fg_color=original_app.PURPLE, width=130, command=self.start_benchmark)
        self.bench_start_btn.grid(row=0, column=2, padx=8, pady=12)
        self.bench_open_btn = ctk.CTkButton(controls, text="Open map", fg_color=original_app.PANEL2, width=90, command=self.open_benchmark_folder, state="disabled")
        self.bench_open_btn.grid(row=0, column=3, padx=8, pady=12)
        self.bench_status = ctk.CTkLabel(controls, text="Klaar", text_color=original_app.MUTED)
        self.bench_status.grid(row=0, column=8, sticky="e", padx=16)

        self.bench_play_frame = original_app.Card(body)
        self.bench_play_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        self.bench_play_frame.grid_rowconfigure(0, weight=1)
        self.bench_play_frame.grid_columnconfigure(0, weight=1)
        self.bench_canvas = ctk.CTkCanvas(self.bench_play_frame, bg=original_app.PANEL, highlightthickness=0, height=480)
        self.bench_canvas.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.bench_canvas.bind("<ButtonPress-1>", self.bench_press)
        self.bench_canvas.bind("<ButtonRelease-1>", self.bench_release)

        replay_controls = original_app.Card(body)
        replay_controls.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 6))
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

        replay = ctk.CTkFrame(body, fg_color="transparent")
        replay.grid(row=3, column=0, columnspan=2, sticky="nsew")
        replay.grid_columnconfigure((0, 1), weight=1)
        replay.grid_rowconfigure(0, weight=1)
        left = original_app.Card(replay); left.grid(row=0, column=0, sticky="nsew", padx=(6, 4), pady=6); left.grid_rowconfigure(1, weight=1); left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="A · PAARS", text_color=original_app.PURPLE, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        self.replay_canvas_a = ctk.CTkCanvas(left, bg=original_app.PANEL, highlightthickness=0, height=300); self.replay_canvas_a.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.replay_stats_a = ctk.CTkLabel(left, text="", text_color=original_app.MUTED, justify="left"); self.replay_stats_a.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        right = original_app.Card(replay); right.grid(row=0, column=1, sticky="nsew", padx=(4, 6), pady=6); right.grid_rowconfigure(1, weight=1); right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="B · GROEN", text_color=original_app.GREEN, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        self.replay_canvas_b = ctk.CTkCanvas(right, bg=original_app.PANEL, highlightthickness=0, height=300); self.replay_canvas_b.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.replay_stats_b = ctk.CTkLabel(right, text="", text_color=original_app.MUTED, justify="left"); self.replay_stats_b.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        self.replay_a, self.replay_b, self.replay_folder = {}, {}, None
        self.replay_trial_index = 0; self.replay_elapsed_ms = 0.0; self.replay_started_at = 0.0; self.replay_running = False; self.replay_after_id = None

    def start_benchmark(self: Any) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            self.bench_status.configure(text="Bouw eerst een profiel", text_color=original_app.RED)
            return
        count = int(round(float(self.bench_count_value.get()) / 5.0) * 5)
        self.bench_plan = generate_plan(count, width=int(VIRTUAL_WIDTH), height=int(VIRTUAL_HEIGHT), seed=random.randint(1, 2**31 - 1))
        self.bench_trials, self.bench_index, self.bench_active = [], 0, True
        self.bench_folder = BENCHMARKS / now_stamp(); self.bench_folder.mkdir(parents=True, exist_ok=True)
        write_json(self.bench_folder / "benchmark_plan_original.json", self.bench_plan)
        self.bench_start_btn.configure(state="disabled"); self.bench_count_slider.configure(state="disabled"); self.bench_open_btn.configure(state="disabled")
        self.show_benchmark_target(); self.sample_benchmark_pointer()

    def show_benchmark_target(self: Any) -> None:
        if self.bench_index >= len(self.bench_plan.get("targets", [])):
            self.finish_benchmark(); return
        self.bench_target_spawn = time.perf_counter(); self.bench_start_point = self.pointer_canvas(self.bench_canvas)
        self.bench_points, self.bench_miss_clicks = [], []; self.bench_click_down = None
        self.append_benchmark_point(*self.bench_start_point)

    def append_benchmark_point(self: Any, x: float, y: float) -> None:
        if not self.bench_active: return
        t_ms = round((time.perf_counter() - self.bench_target_spawn) * 1000, 3)
        self.bench_points.append({"t_ms": t_ms, "x": float(round(x)), "y": float(round(y))})
        item = self.bench_plan["targets"][self.bench_index]
        target = {"index": item["index"], "x": item["target"][0], "y": item["target"][1], "radius": item["radius"]}
        _draw_virtual_scene(original_app, self.bench_canvas, target, self.bench_points, original_app.PURPLE, len(self.bench_miss_clicks))
        self.bench_status.configure(text=f"Target {self.bench_index + 1}/{len(self.bench_plan['targets'])} · misklikken {len(self.bench_miss_clicks)}", text_color=original_app.MUTED)

    def bench_press(self: Any, event: Any) -> None:
        if self.bench_active:
            self.bench_click_down = time.perf_counter(); x, y = _to_virtual(self.bench_canvas, float(event.x), float(event.y)); self.append_benchmark_point(x, y)

    def bench_release(self: Any, event: Any) -> None:
        if not self.bench_active: return
        released = time.perf_counter(); x, y = _to_virtual(self.bench_canvas, float(event.x), float(event.y)); self.append_benchmark_point(x, y)
        item = self.bench_plan["targets"][self.bench_index]
        target = {"index": item["index"], "x": item["target"][0], "y": item["target"][1], "radius": item["radius"]}
        down_ms = round(((self.bench_click_down or released) - self.bench_target_spawn) * 1000, 3); up_ms = round((released - self.bench_target_spawn) * 1000, 3)
        click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(round(x)), "y": float(round(y))}
        if not is_target_hit(x, y, target):
            self.bench_miss_clicks.append(click); self.bench_click_down = None; self.append_benchmark_point(x, y); return
        start = {"x": float(round(self.bench_start_point[0])), "y": float(round(self.bench_start_point[1]))}
        derived = derive_trial(target, start, self.bench_points, click)
        self.bench_trials.append({"schema_version": 5, "target": target, "start": start, "points": list(self.bench_points), "click": click, "miss_clicks": list(self.bench_miss_clicks), "derived": derived})
        self.bench_index += 1; self.show_benchmark_target()

    old_finish = original_app.App.finish_benchmark
    def finish_benchmark(self: Any) -> None:
        old_finish(self)
        self.bench_count_slider.configure(state="normal")
        self.replay_folder = self.bench_folder
        if self.bench_folder:
            self.replay_a = read_json(self.bench_folder / "A.json", {})
            self.replay_b = read_json(self.bench_folder / "B.json", {})
            self.replay_trial_index = 0
            self.replay_reset()
        self.bench_status.configure(text="Benchmark klaar · replay staat hieronder", text_color=original_app.GREEN)

    original_app.App.pointer_canvas = pointer_canvas
    original_app.App._page_aim = _page_aim
    original_app.App.start_aim = start_aim
    original_app.App.show_target = show_target
    original_app.App.append_point = append_point
    original_app.App._page_benchmark = _page_benchmark
    original_app.App.start_benchmark = start_benchmark
    original_app.App.show_benchmark_target = show_benchmark_target
    original_app.App.append_benchmark_point = append_benchmark_point
    original_app.App.bench_press = bench_press
    original_app.App.bench_release = bench_release
    original_app.App.finish_benchmark = finish_benchmark
