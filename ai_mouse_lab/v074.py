from __future__ import annotations

import random
from typing import Any

import customtkinter as ctk

from .storage import AIM, now_stamp, write_json
from .v06 import _to_canvas


def _append_trace_continuous(canvas: ctk.CTkCanvas, points: list[dict[str, Any]], color: str) -> None:
    """Render every unpainted sample segment instead of only the newest pair.

    Sampling can run faster than painting. Drawing only the final pair created the
    dashed/jittery trace seen on Windows even though all samples were recorded.
    """
    if not points:
        return

    rendered = int(getattr(canvas, "_aim_rendered_points", 1))
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
            fill=color,
            width=2.5,
            capstyle="round",
            tags="trace",
        )
    canvas._aim_rendered_points = len(points)

    x, y = _to_canvas(canvas, float(points[-1]["x"]), float(points[-1]["y"]))
    cursor = canvas.find_withtag("cursor")
    if cursor:
        canvas.coords(cursor[0], x - 4, y - 4, x + 4, y + 4)
    else:
        canvas.create_oval(
            x - 4,
            y - 4,
            x + 4,
            y + 4,
            fill=color,
            outline="white",
            width=1,
            tags="cursor",
        )


def apply_patch(original_app: Any) -> None:
    # v0.7.1 imports this helper at render time, so replacing it here fixes the
    # trace without duplicating the complete capture pipeline.
    from . import v061

    v061._append_trace = _append_trace_continuous

    old_finish_aim = original_app.App.finish_aim

    def _restore_main_window(self: Any, message: str | None = None) -> None:
        self.aim_active = False
        self._aim_preparing = False
        self._aim_sampler_token = int(getattr(self, "_aim_sampler_token", 0)) + 1
        self._aim_sampler_running = False

        after_id = getattr(self, "_aim_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self._aim_after_id = None

        prepare_id = getattr(self, "_aim_prepare_after_id", None)
        if prepare_id:
            try:
                self.after_cancel(prepare_id)
            except Exception:
                pass
        self._aim_prepare_after_id = None

        overlay = getattr(self, "aim_overlay", None)
        if overlay is not None:
            try:
                overlay.destroy()
            except Exception:
                pass
        self.aim_overlay = None

        hub_canvas = getattr(self, "aim_hub_canvas", None)
        if hub_canvas is not None:
            self.canvas = hub_canvas

        try:
            self.attributes("-fullscreen", False)
            previous_state = getattr(self, "_aim_previous_state", "normal")
            if previous_state in {"normal", "zoomed"}:
                self.state(previous_state)
            self.lift()
            self.focus_force()
        except Exception:
            pass

        if hasattr(self, "start_btn"):
            self.start_btn.configure(state="normal")
        if message and hasattr(self, "aim_status"):
            self.aim_status.configure(text=message, text_color=original_app.MUTED)

    def abort_fullscreen_aim(self: Any, _event: Any = None) -> None:
        _restore_main_window(self, "Sessie afgebroken · geen profieldata opgeslagen")

    def start_aim(self: Any) -> None:
        if getattr(self, "aim_active", False) or getattr(self, "_aim_preparing", False):
            return

        self._aim_preparing = True
        self.aim_hub_canvas = self.canvas
        try:
            self._aim_previous_state = self.state()
        except Exception:
            self._aim_previous_state = "normal"

        # Use the existing application window. Windows therefore keeps Aim Lab on
        # the same one of the user's monitors where the hub is currently located.
        self.attributes("-fullscreen", True)
        self.update_idletasks()

        overlay = ctk.CTkFrame(self, fg_color=original_app.BG, corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()
        overlay.grid_rowconfigure(0, weight=1)
        overlay.grid_columnconfigure(0, weight=1)
        self.aim_overlay = overlay

        canvas = ctk.CTkCanvas(
            overlay,
            bg=original_app.PANEL,
            highlightthickness=0,
            cursor="crosshair",
        )
        canvas.grid(row=0, column=0, sticky="nsew")
        canvas.bind("<ButtonPress-1>", self.on_press)
        canvas.bind("<ButtonRelease-1>", self.on_release)
        canvas.bind("<Escape>", lambda event: abort_fullscreen_aim(self, event))
        self.bind("<Escape>", lambda event: abort_fullscreen_aim(self, event))
        self.canvas = canvas
        self.start_btn.configure(state="disabled")
        self.aim_status.configure(text="Aim Lab voorbereiden…", text_color=original_app.MUTED)

        def begin_when_ready(attempt: int = 0) -> None:
            if not getattr(self, "_aim_preparing", False):
                return
            canvas.update_idletasks()
            width = int(canvas.winfo_width())
            height = int(canvas.winfo_height())
            if (width < 1000 or height < 600) and attempt < 30:
                self._aim_prepare_after_id = self.after(30, lambda: begin_when_ready(attempt + 1))
                return
            if width < 1000 or height < 600:
                _restore_main_window(self, "Fullscreen kon niet correct worden opgebouwd")
                return

            count = 30
            if hasattr(self, "count_value"):
                count = int(round(float(self.count_value.get()) / 5.0) * 5)
            elif hasattr(self, "count_menu"):
                count = int(self.count_menu.get())

            self.plan = [
                {
                    "index": index,
                    "x": random.randint(80, 1840),
                    "y": random.randint(80, 1000),
                    "radius": random.choice([18, 26, 36]),
                }
                for index in range(count)
            ]
            self.trials = []
            self.index = 0
            self.aim_active = True
            self._aim_preparing = False
            self.session_folder = AIM / now_stamp()
            self.session_folder.mkdir(parents=True, exist_ok=True)
            write_json(
                self.session_folder / "plan.json",
                {"width": 1920, "height": 1080, "targets": self.plan},
            )
            canvas.focus_set()
            self.show_target()
            self.sample_pointer()

        self._aim_prepare_after_id = self.after(60, begin_when_ready)

    def finish_aim(self: Any) -> None:
        # The existing finish pipeline writes trials and summary while the overlay
        # canvas is still valid. Restore the normal hub immediately afterwards.
        old_finish_aim(self)
        _restore_main_window(
            self,
            f"Klaar · {len(getattr(self, 'trials', []))} targets opgeslagen",
        )
        if hasattr(self, "refresh_aim_metrics"):
            self.refresh_aim_metrics()

    original_app.App.start_aim = start_aim
    original_app.App.finish_aim = finish_aim
    original_app.App.abort_fullscreen_aim = abort_fullscreen_aim
