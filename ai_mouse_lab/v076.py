from __future__ import annotations

import time
from typing import Any

import customtkinter as ctk

from .v06 import VIRTUAL_HEIGHT, VIRTUAL_WIDTH, _canvas_box, _to_canvas


RENDER_INTERVAL_MS = 16.0
STATUS_INTERVAL_MS = 90.0


def _draw_benchmark_target(original_app: Any, self: Any) -> None:
    canvas = self.bench_canvas
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

    item = self.bench_plan["targets"][self.bench_index]
    tx, ty = _to_canvas(canvas, float(item["target"][0]), float(item["target"][1]))
    radius = max(5.0, float(item["radius"]) * scale)
    canvas.create_oval(
        tx - radius,
        ty - radius,
        tx + radius,
        ty + radius,
        fill=original_app.PURPLE,
        outline="#c4b5fd",
        width=3,
        tags="target",
    )
    canvas.create_text(
        tx,
        ty,
        text=str(self.bench_index + 1),
        fill="white",
        tags="target",
    )
    canvas._bench_rendered_points = 1


def _append_benchmark_trace(original_app: Any, self: Any) -> None:
    points = self.bench_points
    if len(points) < 2:
        return

    canvas = self.bench_canvas
    rendered = int(getattr(canvas, "_bench_rendered_points", 1))
    rendered = max(1, min(rendered, len(points)))

    for index in range(rendered, len(points)):
        previous = points[index - 1]
        current = points[index]
        px, py = _to_canvas(canvas, float(previous["x"]), float(previous["y"]))
        x, y = _to_canvas(canvas, float(current["x"]), float(current["y"]))
        canvas.create_line(
            px,
            py,
            x,
            y,
            fill=original_app.PURPLE,
            width=2.5,
            capstyle="round",
            tags="trace",
        )

    canvas._bench_rendered_points = len(points)
    x, y = _to_canvas(canvas, float(points[-1]["x"]), float(points[-1]["y"]))
    cursor = canvas.find_withtag("bench_cursor")
    if cursor:
        canvas.coords(cursor[0], x - 4, y - 4, x + 4, y + 4)
    else:
        canvas.create_oval(
            x - 4,
            y - 4,
            x + 4,
            y + 4,
            fill=original_app.PURPLE,
            outline="white",
            width=1,
            tags="bench_cursor",
        )


def apply_patch(original_app: Any) -> None:
    old_start_benchmark = original_app.App.start_benchmark
    old_show_benchmark_target = original_app.App.show_benchmark_target
    old_append_benchmark_point = original_app.App.append_benchmark_point
    old_finish_benchmark = original_app.App.finish_benchmark

    def _restore_benchmark_hub(self: Any, message: str | None = None) -> None:
        self._bench_preparing = False
        self._bench_overlay_active = False

        prepare_id = getattr(self, "_bench_prepare_after_id", None)
        if prepare_id:
            try:
                self.after_cancel(prepare_id)
            except Exception:
                pass
        self._bench_prepare_after_id = None

        overlay = getattr(self, "bench_overlay", None)
        if overlay is not None:
            try:
                overlay.destroy()
            except Exception:
                pass
        self.bench_overlay = None

        hub_canvas = getattr(self, "bench_hub_canvas", None)
        if hub_canvas is not None:
            self.bench_canvas = hub_canvas

        try:
            self.attributes("-fullscreen", False)
            previous_state = getattr(self, "_bench_previous_state", "normal")
            if previous_state in {"normal", "zoomed"}:
                self.state(previous_state)
            self.lift()
            self.focus_force()
        except Exception:
            pass

        if hasattr(self, "bench_start_btn"):
            self.bench_start_btn.configure(state="normal")
        if hasattr(self, "bench_count_slider"):
            self.bench_count_slider.configure(state="normal")
        if message and hasattr(self, "bench_status"):
            self.bench_status.configure(text=message, text_color=original_app.MUTED)

    def abort_fullscreen_benchmark(self: Any, _event: Any = None) -> None:
        self.bench_active = False
        self._bench_sampler_token = int(getattr(self, "_bench_sampler_token", 0)) + 1
        _restore_benchmark_hub(self, "Benchmark afgebroken · geen A/B-resultaat gemaakt")

    def start_benchmark(self: Any) -> None:
        if getattr(self, "bench_active", False) or getattr(self, "_bench_preparing", False):
            return

        # Let the existing start function perform profile validation and session setup,
        # but only after the fullscreen canvas has real Windows dimensions.
        self._bench_preparing = True
        self.bench_hub_canvas = self.bench_canvas
        try:
            self._bench_previous_state = self.state()
        except Exception:
            self._bench_previous_state = "normal"

        self.attributes("-fullscreen", True)
        self.update_idletasks()

        overlay = ctk.CTkFrame(self, fg_color=original_app.BG, corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()
        overlay.grid_rowconfigure(0, weight=1)
        overlay.grid_columnconfigure(0, weight=1)
        self.bench_overlay = overlay

        canvas = ctk.CTkCanvas(
            overlay,
            bg=original_app.PANEL,
            highlightthickness=0,
            cursor="crosshair",
        )
        canvas.grid(row=0, column=0, sticky="nsew")
        canvas.bind("<ButtonPress-1>", self.bench_press)
        canvas.bind("<ButtonRelease-1>", self.bench_release)
        canvas.bind("<Escape>", lambda event: abort_fullscreen_benchmark(self, event))
        self.bind("<Escape>", lambda event: abort_fullscreen_benchmark(self, event))
        self.bench_canvas = canvas
        self.bench_start_btn.configure(state="disabled")
        self.bench_status.configure(text="Benchmark voorbereiden…", text_color=original_app.MUTED)

        def begin_when_ready(attempt: int = 0) -> None:
            if not getattr(self, "_bench_preparing", False):
                return
            canvas.update_idletasks()
            width = int(canvas.winfo_width())
            height = int(canvas.winfo_height())
            if (width < 1000 or height < 600) and attempt < 30:
                self._bench_prepare_after_id = self.after(30, lambda: begin_when_ready(attempt + 1))
                return
            if width < 1000 or height < 600:
                _restore_benchmark_hub(self, "Fullscreen benchmark kon niet worden opgebouwd")
                return

            self._bench_preparing = False
            self._bench_overlay_active = True
            canvas.focus_set()
            try:
                old_start_benchmark(self)
            except Exception:
                _restore_benchmark_hub(self, "Benchmark starten mislukt")
                raise

        self._bench_prepare_after_id = self.after(60, begin_when_ready)

    def show_benchmark_target(self: Any) -> None:
        if self.bench_index >= len(self.bench_plan.get("targets", [])):
            self.finish_benchmark()
            return

        # Preserve the existing capture-state initialization, then replace its
        # expensive full redraw with one stable target scene.
        old_show_benchmark_target(self)
        if getattr(self, "bench_active", False):
            self._bench_last_render_ms = 0.0
            self._bench_last_status_ms = 0.0
            _draw_benchmark_target(original_app, self)

    def append_benchmark_point(self: Any, x: float, y: float) -> None:
        if not getattr(self, "bench_active", False):
            return

        # Record every sample using the existing pipeline's data format, but do not
        # redraw the complete canvas for each 8 ms sample.
        t_ms = round((time.perf_counter() - self.bench_target_spawn) * 1000, 3)
        self.bench_points.append({"t_ms": t_ms, "x": float(round(x)), "y": float(round(y))})

        now_ms = time.perf_counter() * 1000.0
        if now_ms - float(getattr(self, "_bench_last_render_ms", 0.0)) >= RENDER_INTERVAL_MS:
            _append_benchmark_trace(original_app, self)
            self._bench_last_render_ms = now_ms

        if now_ms - float(getattr(self, "_bench_last_status_ms", 0.0)) >= STATUS_INTERVAL_MS:
            self.bench_status.configure(
                text=(
                    f"Target {self.bench_index + 1}/{len(self.bench_plan['targets'])}"
                    f" · misklikken {len(getattr(self, 'bench_miss_clicks', []))}"
                ),
                text_color=original_app.MUTED,
            )
            self._bench_last_status_ms = now_ms

    def finish_benchmark(self: Any) -> None:
        # Generate/save A/B while all current benchmark state is still available.
        old_finish_benchmark(self)
        _restore_benchmark_hub(self, "Benchmark klaar · grote replay staat hieronder")
        try:
            self.show("Benchmark")
        except Exception:
            pass
        if hasattr(self, "replay_reset"):
            self.replay_reset()

    original_app.App.start_benchmark = start_benchmark
    original_app.App.show_benchmark_target = show_benchmark_target
    original_app.App.append_benchmark_point = append_benchmark_point
    original_app.App.finish_benchmark = finish_benchmark
    original_app.App.abort_fullscreen_benchmark = abort_fullscreen_benchmark
