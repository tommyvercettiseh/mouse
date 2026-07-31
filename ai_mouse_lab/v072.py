from __future__ import annotations

from typing import Any

import customtkinter as ctk


SAMPLE_INTERVAL_MS = 8
FULLSCREEN_READY_RETRIES = 20
FULLSCREEN_READY_DELAY_MS = 50


def apply_patch(original_app: Any) -> None:
    old_start_aim = original_app.App.start_aim
    old_finish_aim = original_app.App.finish_aim

    def _restore_hub(self: Any, message: str | None = None) -> None:
        self.aim_active = False
        self._aim_start_pending = False
        self._aim_sampler_token = int(getattr(self, "_aim_sampler_token", 0)) + 1
        self._aim_sampler_running = False

        after_id = getattr(self, "_aim_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self._aim_after_id = None

        start_after_id = getattr(self, "_aim_start_after_id", None)
        if start_after_id:
            try:
                self.after_cancel(start_after_id)
            except Exception:
                pass
        self._aim_start_after_id = None

        fullscreen = getattr(self, "aim_fullscreen", None)
        if fullscreen is not None:
            try:
                fullscreen.grab_release()
            except Exception:
                pass
            try:
                fullscreen.destroy()
            except Exception:
                pass
        self.aim_fullscreen = None

        hub_canvas = getattr(self, "aim_hub_canvas", None)
        if hub_canvas is not None:
            self.canvas = hub_canvas

        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

        if hasattr(self, "start_btn"):
            self.start_btn.configure(state="normal")
        if message and hasattr(self, "aim_status"):
            self.aim_status.configure(text=message, text_color=original_app.MUTED)

    def abort_fullscreen_aim(self: Any, _event: Any = None) -> None:
        if not getattr(self, "aim_active", False) and not getattr(self, "_aim_start_pending", False):
            _restore_hub(self)
            return
        _restore_hub(self, "Sessie afgebroken · geen profieldata opgeslagen")

    def _open_fullscreen(self: Any) -> None:
        existing = getattr(self, "aim_fullscreen", None)
        if existing is not None:
            try:
                existing.destroy()
            except Exception:
                pass

        self.aim_hub_canvas = self.canvas
        window = ctk.CTkToplevel(self)
        self.aim_fullscreen = window
        window.title("AI Mouse Lab · Fullscreen Aim Lab")
        window.configure(fg_color=original_app.BG)
        window.attributes("-fullscreen", True)
        window.protocol("WM_DELETE_WINDOW", lambda: abort_fullscreen_aim(self))
        window.bind("<Escape>", lambda event: abort_fullscreen_aim(self, event))

        canvas = ctk.CTkCanvas(window, bg=original_app.PANEL, highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True)
        canvas.bind("<ButtonPress-1>", self.on_press)
        canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas = canvas

        self._aim_ready_text = canvas.create_text(
            24,
            24,
            anchor="nw",
            text="Aim Lab voorbereiden…",
            fill=original_app.MUTED,
            font=("Segoe UI", 15, "bold"),
            tags="startup_status",
        )

        window.lift()
        window.focus_force()
        try:
            window.grab_set()
        except Exception:
            pass

    def sample_pointer(self: Any) -> None:
        """Run exactly one recorder loop per session."""
        if getattr(self, "_aim_sampler_running", False):
            return

        token = int(getattr(self, "_aim_sampler_token", 0)) + 1
        self._aim_sampler_token = token
        self._aim_sampler_running = True

        def tick() -> None:
            if (
                not getattr(self, "aim_active", False)
                or token != int(getattr(self, "_aim_sampler_token", -1))
            ):
                self._aim_sampler_running = False
                self._aim_after_id = None
                return

            canvas = getattr(self, "canvas", None)
            if canvas is None or not canvas.winfo_exists():
                _restore_hub(self, "Aim Lab-venster is gesloten")
                return

            x, y = self.pointer_canvas(canvas)
            self.append_point(x, y)
            self._aim_after_id = self.after(SAMPLE_INTERVAL_MS, tick)

        tick()

    def _begin_when_fullscreen_ready(self: Any, attempt: int = 0) -> None:
        window = getattr(self, "aim_fullscreen", None)
        canvas = getattr(self, "canvas", None)
        if window is None or canvas is None or not window.winfo_exists() or not canvas.winfo_exists():
            _restore_hub(self, "Fullscreen starten mislukt · probeer opnieuw")
            return

        window.update_idletasks()
        width = int(canvas.winfo_width())
        height = int(canvas.winfo_height())
        ready = width >= 1000 and height >= 600

        if not ready and attempt < FULLSCREEN_READY_RETRIES:
            self._aim_start_after_id = self.after(
                FULLSCREEN_READY_DELAY_MS,
                lambda: _begin_when_fullscreen_ready(self, attempt + 1),
            )
            return

        if not ready:
            _restore_hub(self, f"Fullscreen kreeg verkeerde afmetingen ({width}×{height})")
            return

        self._aim_start_after_id = None
        self._aim_start_pending = False
        canvas.delete("startup_status")

        try:
            old_start_aim(self)
        except Exception:
            _restore_hub(self, "Starten mislukt · probeer opnieuw")
            raise

    def start_aim(self: Any) -> None:
        if getattr(self, "aim_active", False) or getattr(self, "_aim_start_pending", False):
            return

        self._aim_start_pending = True
        if hasattr(self, "start_btn"):
            self.start_btn.configure(state="disabled")
        if hasattr(self, "aim_status"):
            self.aim_status.configure(text="Fullscreen voorbereiden…", text_color=original_app.MUTED)

        _open_fullscreen(self)
        self._aim_start_after_id = self.after(
            FULLSCREEN_READY_DELAY_MS,
            lambda: _begin_when_fullscreen_ready(self, 0),
        )

    def finish_aim(self: Any) -> None:
        old_finish_aim(self)
        _restore_hub(
            self,
            f"Klaar · {len(getattr(self, 'trials', []))} targets opgeslagen",
        )
        if hasattr(self, "refresh_aim_metrics"):
            self.refresh_aim_metrics()

    original_app.App.sample_pointer = sample_pointer
    original_app.App.start_aim = start_aim
    original_app.App.finish_aim = finish_aim
    original_app.App.abort_fullscreen_aim = abort_fullscreen_aim
