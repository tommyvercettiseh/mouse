from __future__ import annotations

import queue
import random
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk
from pynput import mouse

from . import __version__
from .comparison import ComparisonError, create_latest_comparison, latest_comparison
from .metrics import derive_trial
from .personal_model import build_personal_profile
from .replay_engine import FRAME_MS, ReplayTimeline
from .schema import SCHEMA_VERSION, VIRTUAL_HEIGHT, VIRTUAL_WIDTH, normalize_session
from .storage import AIM, PROFILES, RECORDINGS, now_stamp, read_json, write_json
from .ui_helpers import is_target_hit

BG = "#0b1018"
PANEL = "#141b25"
PANEL2 = "#1a2330"
BORDER = "#2a3442"
TEXT = "#f4f6fb"
MUTED = "#98a3b3"
PURPLE = "#8b5cf6"
GREEN = "#3ccf78"
RED = "#ef6262"
BLUE = "#7aa2ff"


class Card(ctk.CTkFrame):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER, **kwargs)


class FreeRecorder:
    def __init__(self, event_queue: queue.Queue[dict[str, Any]]) -> None:
        self.event_queue = event_queue
        self.listener: mouse.Listener | None = None
        self.running = False
        self.paused = False
        self.started_at = 0.0
        self.pause_started_at = 0.0
        self.paused_duration = 0.0
        self.events: list[dict[str, Any]] = []
        self.counts: Counter[str] = Counter()
        self._down: dict[str, tuple[float, int, int]] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.paused = False
        self.started_at = time.perf_counter()
        self.paused_duration = 0.0
        self.events = []
        self.counts.clear()
        self._down.clear()
        self.listener = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
        self.listener.start()

    def pause(self) -> None:
        if self.running and not self.paused:
            self.paused = True
            self.pause_started_at = time.perf_counter()

    def resume(self) -> None:
        if self.running and self.paused:
            self.paused_duration += time.perf_counter() - self.pause_started_at
            self.paused = False

    def elapsed_s(self) -> float:
        if not self.running:
            return 0.0
        now = self.pause_started_at if self.paused else time.perf_counter()
        return max(0.0, now - self.started_at - self.paused_duration)

    def _time_s(self) -> float:
        return round(self.elapsed_s(), 6)

    def _emit(self, event: dict[str, Any]) -> None:
        if not self.running or self.paused:
            return
        with self._lock:
            self.events.append(event)
            self.counts[event["type"]] += 1
        self.event_queue.put(event)

    def _on_move(self, x: int, y: int) -> None:
        self._emit({"type": "move", "t": self._time_s(), "x": int(x), "y": int(y)})

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not self.running or self.paused:
            return
        name = str(button).split(".")[-1]
        hold_ms = None
        if pressed:
            self._down[name] = (time.perf_counter(), int(x), int(y))
        else:
            down = self._down.pop(name, None)
            if down:
                hold_ms = round((time.perf_counter() - down[0]) * 1000.0, 3)
        self._emit(
            {
                "type": "click",
                "t": self._time_s(),
                "x": int(x),
                "y": int(y),
                "button": name,
                "pressed": bool(pressed),
                "hold_ms": hold_ms,
            }
        )

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self._emit({"type": "scroll", "t": self._time_s(), "x": int(x), "y": int(y), "dx": int(dx), "dy": int(dy)})

    def stop(self) -> Path | None:
        if not self.running:
            return None
        if self.paused:
            self.resume()
        self.running = False
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        folder = RECORDINGS / now_stamp()
        write_json(folder / "events.json", self.events)
        write_json(
            folder / "summary.json",
            {
                "schema_version": SCHEMA_VERSION,
                "duration_s": round(self.elapsed_s(), 3),
                "event_count": len(self.events),
                "event_types": dict(self.counts),
                "created_at": datetime.now().isoformat(),
            },
        )
        return folder


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"AI Mouse Lab v{__version__}")
        self.geometry("1480x900")
        self.minsize(1180, 720)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self.pages: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}

        self.event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.recorder = FreeRecorder(self.event_queue)

        self.aim_active = False
        self.aim_after_id: str | None = None
        self.aim_generation = 0
        self.aim_overlay: ctk.CTkFrame | None = None
        self.aim_canvas: ctk.CTkCanvas | None = None
        self.aim_plan: list[dict[str, Any]] = []
        self.aim_trials: list[dict[str, Any]] = []
        self.aim_index = 0
        self.target_spawn = 0.0
        self.start_point = (0.0, 0.0)
        self.points: list[dict[str, float]] = []
        self.miss_clicks: list[dict[str, float]] = []
        self.click_down: float | None = None
        self.session_folder: Path | None = None

        self.timeline: ReplayTimeline | None = None
        self.replay_running = False
        self.replay_started_at = 0.0
        self.replay_speed = 1.0
        self.replay_after_id: str | None = None

        self._build_shell()
        self.show("Aim Lab")
        self.after(50, self._poll_free_record)

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        nav = ctk.CTkFrame(self, width=170, fg_color="#0d131d", corner_radius=0)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        ctk.CTkLabel(nav, text="AI Mouse Lab", text_color=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=17, pady=(22, 2))
        ctk.CTkLabel(nav, text=f"v{__version__}", text_color=MUTED).pack(anchor="w", padx=17, pady=(0, 22))
        for key in ("Free Record", "Aim Lab"):
            button = ctk.CTkButton(nav, text=key, anchor="w", height=42, fg_color="transparent", hover_color=PANEL2, command=lambda page=key: self.show(page))
            button.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[key] = button
        ctk.CTkLabel(nav, text="● Data blijft lokaal", text_color=GREEN).pack(side="bottom", anchor="w", padx=17, pady=18)

        self.host = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.host.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.host.grid_columnconfigure(0, weight=1)
        self.host.grid_rowconfigure(0, weight=1)

        self._page_free_record()
        self._page_aim()
        self._page_results()

    def _page(self, key: str, title: str, subtitle: str) -> ctk.CTkFrame:
        root = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        root.grid(row=0, column=0, sticky="nsew")
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(header, text=title, text_color=TEXT, font=("Segoe UI", 28, "bold")).pack(anchor="w")
        ctk.CTkLabel(header, text=subtitle, text_color=MUTED).pack(anchor="w")
        body = ctk.CTkFrame(root, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        self.pages[key] = root
        return body

    def show(self, key: str) -> None:
        if key not in self.pages:
            key = "Aim Lab"
        for name, page in self.pages.items():
            page.grid_remove()
            button = self.nav_buttons.get(name)
            if button is not None:
                button.configure(fg_color=PURPLE if name == key else "transparent")
        self.pages[key].grid()
        if key == "Aim Lab":
            self.refresh_profile_status()
        elif key == "Results":
            self.draw_replay()

    def _page_free_record(self) -> None:
        body = self._page("Free Record", "Free Record", "Globale muisopname met start, pauze, hervatten en lokale opslag.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        controls = Card(body)
        controls.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        self.record_status = ctk.CTkLabel(controls, text="Klaar", text_color=MUTED, font=("Segoe UI", 14, "bold"))
        self.record_status.pack(side="left", padx=18, pady=16)
        self.record_timer = ctk.CTkLabel(controls, text="00:00:00", text_color=TEXT, font=("Segoe UI", 23, "bold"))
        self.record_timer.pack(side="left", padx=22)
        self.record_counts = ctk.CTkLabel(controls, text="0 events", text_color=MUTED)
        self.record_counts.pack(side="left", padx=18)
        self.record_start_btn = ctk.CTkButton(controls, text="Start", fg_color=PURPLE, command=self.start_recording)
        self.record_start_btn.pack(side="right", padx=(6, 18), pady=12)
        self.record_pause_btn = ctk.CTkButton(controls, text="Pauze", fg_color=PANEL2, command=self.toggle_record_pause, state="disabled")
        self.record_pause_btn.pack(side="right", padx=6, pady=12)
        self.record_stop_btn = ctk.CTkButton(controls, text="Stop en opslaan", fg_color=RED, command=self.stop_recording, state="disabled")
        self.record_stop_btn.pack(side="right", padx=6, pady=12)

        card = Card(body)
        card.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.record_info = ctk.CTkLabel(card, text="Nog geen actieve opname.", text_color=MUTED, justify="left", font=("Consolas", 13))
        self.record_info.pack(anchor="nw", padx=20, pady=20)

    def start_recording(self) -> None:
        self.recorder.start()
        self.record_start_btn.configure(state="disabled")
        self.record_pause_btn.configure(state="normal", text="Pauze")
        self.record_stop_btn.configure(state="normal")
        self.record_status.configure(text="Opname actief", text_color=RED)

    def toggle_record_pause(self) -> None:
        if not self.recorder.running:
            return
        if self.recorder.paused:
            self.recorder.resume()
            self.record_pause_btn.configure(text="Pauze")
            self.record_status.configure(text="Opname actief", text_color=RED)
        else:
            self.recorder.pause()
            self.record_pause_btn.configure(text="Hervatten")
            self.record_status.configure(text="Gepauzeerd", text_color=MUTED)

    def stop_recording(self) -> None:
        folder = self.recorder.stop()
        self.record_start_btn.configure(state="normal")
        self.record_pause_btn.configure(state="disabled", text="Pauze")
        self.record_stop_btn.configure(state="disabled")
        self.record_status.configure(text=f"Opgeslagen: {folder.name if folder else '-'}", text_color=GREEN)

    def _poll_free_record(self) -> None:
        last_event: dict[str, Any] | None = None
        while True:
            try:
                last_event = self.event_queue.get_nowait()
            except queue.Empty:
                break
        if self.recorder.running:
            elapsed = int(self.recorder.elapsed_s())
            hours, rest = divmod(elapsed, 3600)
            minutes, seconds = divmod(rest, 60)
            self.record_timer.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            self.record_counts.configure(text=f"{len(self.recorder.events)} events")
        if last_event is not None:
            self.record_info.configure(text=f"Laatste event\n{last_event}\n\nMoves: {self.recorder.counts['move']}\nClicks: {self.recorder.counts['click']}\nScrolls: {self.recorder.counts['scroll']}")
        self.after(100, self._poll_free_record)

    def _page_aim(self) -> None:
        body = self._page("Aim Lab", "Aim Lab", "Eén vaste 1920 × 1080 arena voor opname, profielbouw en A/B-test.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_columnconfigure(0, weight=1)
        arena.grid_rowconfigure(0, weight=1)
        self.aim_preview = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        self.aim_preview.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.aim_preview.create_text(420, 260, text="Start Aim Lab om fullscreen op dit scherm te testen", fill=MUTED, font=("Segoe UI", 17))

        side = Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="Opname", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        self.count_value = ctk.IntVar(value=50)
        self.count_label = ctk.CTkLabel(side, text="50 targets", text_color=TEXT, font=("Segoe UI", 14, "bold"))
        self.count_label.pack(anchor="w", padx=18, pady=(6, 2))
        slider = ctk.CTkSlider(side, from_=10, to=100, number_of_steps=18, variable=self.count_value, command=self._update_count_label)
        slider.pack(fill="x", padx=18, pady=8)
        self.start_aim_btn = ctk.CTkButton(side, text="Start Aim Lab", fg_color=PURPLE, height=44, command=self.start_aim)
        self.start_aim_btn.pack(fill="x", padx=18, pady=8)
        self.aim_status = ctk.CTkLabel(side, text="Klaar", text_color=MUTED, justify="left", wraplength=250)
        self.aim_status.pack(anchor="w", padx=18, pady=(4, 14))

        ctk.CTkLabel(side, text="Persoonlijk profiel", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(12, 8))
        self.build_profile_btn = ctk.CTkButton(side, text="Build Profile", fg_color=GREEN, hover_color="#2fb669", text_color="#07140d", height=42, command=self.build_profile)
        self.build_profile_btn.pack(fill="x", padx=18, pady=6)
        self.profile_status = ctk.CTkLabel(side, text="Nog geen profiel", text_color=MUTED, justify="left", wraplength=250)
        self.profile_status.pack(anchor="w", padx=18, pady=(4, 14))

        ctk.CTkLabel(side, text="Vergelijken", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(12, 8))
        self.compare_btn = ctk.CTkButton(side, text="Test nieuwste opname A/B", fg_color=PANEL2, hover_color=PURPLE, height=42, command=self.test_latest_ab)
        self.compare_btn.pack(fill="x", padx=18, pady=6)
        self.compare_status = ctk.CTkLabel(side, text="Laatste Aim Lab-opname wordt de target-playlist.", text_color=MUTED, justify="left", wraplength=250)
        self.compare_status.pack(anchor="w", padx=18, pady=(4, 14))

    def _update_count_label(self, value: float) -> None:
        count = int(round(float(value) / 5.0) * 5)
        self.count_value.set(count)
        self.count_label.configure(text=f"{count} targets")

    def _canvas_box(self, canvas: ctk.CTkCanvas) -> tuple[float, float, float]:
        canvas.update_idletasks()
        width = max(320.0, float(canvas.winfo_width()))
        height = max(240.0, float(canvas.winfo_height()))
        scale = min(width / VIRTUAL_WIDTH, height / VIRTUAL_HEIGHT)
        return scale, (width - VIRTUAL_WIDTH * scale) / 2.0, (height - VIRTUAL_HEIGHT * scale) / 2.0

    def _to_canvas(self, canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_box(canvas)
        return offset_x + x * scale, offset_y + y * scale

    def _to_virtual(self, canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_box(canvas)
        return (x - offset_x) / max(scale, 1e-9), (y - offset_y) / max(scale, 1e-9)

    def pointer_virtual(self, canvas: ctk.CTkCanvas) -> tuple[float, float]:
        screen_x, screen_y = self.winfo_pointerxy()
        return self._to_virtual(canvas, float(screen_x - canvas.winfo_rootx()), float(screen_y - canvas.winfo_rooty()))

    def start_aim(self) -> None:
        if self.aim_active:
            return
        count = int(self.count_value.get())
        self.aim_plan = [
            {
                "index": index,
                "x": random.randint(90, 1830),
                "y": random.randint(90, 990),
                "radius": random.choice([18, 26, 36]),
            }
            for index in range(count)
        ]
        self.aim_trials = []
        self.aim_index = 0
        self.aim_active = True
        self.aim_generation += 1
        self.session_folder = AIM / now_stamp()
        write_json(self.session_folder / "plan.json", {"schema_version": SCHEMA_VERSION, "width": VIRTUAL_WIDTH, "height": VIRTUAL_HEIGHT, "targets": self.aim_plan})
        self.start_aim_btn.configure(state="disabled")
        self._open_aim_overlay()

    def _open_aim_overlay(self) -> None:
        self.aim_overlay = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.aim_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.aim_overlay.grid_columnconfigure(0, weight=1)
        self.aim_overlay.grid_rowconfigure(0, weight=1)
        self.aim_canvas = ctk.CTkCanvas(self.aim_overlay, bg=BG, highlightthickness=0)
        self.aim_canvas.grid(row=0, column=0, sticky="nsew")
        self.aim_canvas.bind("<ButtonPress-1>", self.on_aim_press)
        self.aim_canvas.bind("<ButtonRelease-1>", self.on_aim_release)
        self.bind("<Escape>", lambda _event: self.abort_aim())
        self.attributes("-fullscreen", True)
        self.after(60, self._begin_aim_when_ready)

    def _begin_aim_when_ready(self, attempts: int = 0) -> None:
        canvas = self.aim_canvas
        if not self.aim_active or canvas is None:
            return
        canvas.update_idletasks()
        if canvas.winfo_width() < 800 or canvas.winfo_height() < 500:
            if attempts < 80:
                self.after(40, lambda: self._begin_aim_when_ready(attempts + 1))
            else:
                self.abort_aim("Fullscreen canvas kon niet worden opgebouwd.")
            return
        self.show_target()
        self.sample_pointer(self.aim_generation)

    def draw_aim_scene(self) -> None:
        canvas = self.aim_canvas
        if canvas is None or not self.aim_active or self.aim_index >= len(self.aim_plan):
            return
        target = self.aim_plan[self.aim_index]
        canvas.delete("all")
        scale, offset_x, offset_y = self._canvas_box(canvas)
        canvas.create_rectangle(offset_x, offset_y, offset_x + VIRTUAL_WIDTH * scale, offset_y + VIRTUAL_HEIGHT * scale, outline=BORDER, width=1)
        coordinates: list[float] = []
        for point in self.points:
            x, y = self._to_canvas(canvas, point["x"], point["y"])
            coordinates.extend((x, y))
        if len(coordinates) >= 4:
            canvas.create_line(*coordinates, fill=BLUE, width=2.3, smooth=True)
        x, y = self._to_canvas(canvas, float(target["x"]), float(target["y"]))
        radius = max(6.0, float(target["radius"]) * scale)
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=PURPLE, outline="#e5e7eb", width=2)
        canvas.create_text(x, y, text=str(self.aim_index + 1), fill="white", font=("Segoe UI", 10, "bold"))
        canvas.create_text(18, 18, anchor="nw", text=f"Target {self.aim_index + 1}/{len(self.aim_plan)} · misklikken {len(self.miss_clicks)} · Esc stopt", fill=TEXT, font=("Segoe UI", 12, "bold"))

    def show_target(self) -> None:
        if not self.aim_active:
            return
        if self.aim_index >= len(self.aim_plan):
            self.finish_aim()
            return
        canvas = self.aim_canvas
        if canvas is None:
            return
        self.target_spawn = time.perf_counter()
        self.start_point = self.pointer_virtual(canvas)
        self.points = []
        self.miss_clicks = []
        self.click_down = None
        self.append_point(*self.start_point)
        self.draw_aim_scene()

    def append_point(self, x: float, y: float) -> None:
        if not self.aim_active:
            return
        self.points.append(
            {
                "t_ms": round((time.perf_counter() - self.target_spawn) * 1000.0, 3),
                "x": round(float(x), 3),
                "y": round(float(y), 3),
            }
        )

    def sample_pointer(self, generation: int) -> None:
        if not self.aim_active or generation != self.aim_generation or self.aim_canvas is None:
            self.aim_after_id = None
            return
        self.append_point(*self.pointer_virtual(self.aim_canvas))
        self.draw_aim_scene()
        self.aim_after_id = self.after(8, lambda: self.sample_pointer(generation))

    def on_aim_press(self, event: Any) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        self.click_down = time.perf_counter()
        self.append_point(*self._to_virtual(self.aim_canvas, float(event.x), float(event.y)))

    def on_aim_release(self, event: Any) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        released = time.perf_counter()
        x, y = self._to_virtual(self.aim_canvas, float(event.x), float(event.y))
        self.append_point(x, y)
        target = self.aim_plan[self.aim_index]
        click = {
            "down_t_ms": round(((self.click_down or released) - self.target_spawn) * 1000.0, 3),
            "up_t_ms": round((released - self.target_spawn) * 1000.0, 3),
            "x": round(x, 3),
            "y": round(y, 3),
        }
        if not is_target_hit(x, y, target):
            self.miss_clicks.append(click)
            self.click_down = None
            self.draw_aim_scene()
            return

        target_data = {
            "index": int(target["index"]),
            "x": float(target["x"]),
            "y": float(target["y"]),
            "radius": float(target["radius"]),
        }
        start_data = {"x": float(self.start_point[0]), "y": float(self.start_point[1])}
        derived = derive_trial(target_data, start_data, self.points, click)
        self.aim_trials.append(
            {
                "schema_version": SCHEMA_VERSION,
                "capture_mode": "normal",
                "coordinate_space": "virtual_1920x1080",
                "target": target_data,
                "start": start_data,
                "points": list(self.points),
                "click": click,
                "miss_clicks": list(self.miss_clicks),
                "derived": derived,
            }
        )
        self.aim_index += 1
        self.show_target()

    def _cancel_aim_sampler(self) -> None:
        if self.aim_after_id:
            try:
                self.after_cancel(self.aim_after_id)
            except Exception:
                pass
        self.aim_after_id = None

    def _close_aim_overlay(self) -> None:
        self._cancel_aim_sampler()
        self.unbind("<Escape>")
        try:
            self.attributes("-fullscreen", False)
        except Exception:
            pass
        if self.aim_overlay is not None:
            self.aim_overlay.destroy()
        self.aim_overlay = None
        self.aim_canvas = None
        self.start_aim_btn.configure(state="normal")
        self.lift()
        self.focus_force()

    def abort_aim(self, message: str = "Aim Lab gestopt; onvolledige sessie niet opgeslagen.") -> None:
        self.aim_active = False
        self.aim_generation += 1
        self._close_aim_overlay()
        self.aim_status.configure(text=message, text_color=RED)

    def finish_aim(self) -> None:
        self.aim_active = False
        self.aim_generation += 1
        folder = self.session_folder or (AIM / now_stamp())
        write_json(folder / "trials.json", self.aim_trials)
        write_json(
            folder / "summary.json",
            {
                "schema_version": SCHEMA_VERSION,
                "coordinate_space": "virtual_1920x1080",
                "trial_count": len(self.aim_trials),
                "point_count": sum(len(trial["points"]) for trial in self.aim_trials),
                "miss_click_count": sum(len(trial["miss_clicks"]) for trial in self.aim_trials),
                "created_at": datetime.now().isoformat(),
            },
        )
        self._close_aim_overlay()
        self.aim_status.configure(text=f"Opgeslagen · {len(self.aim_trials)} targets\n{folder.name}", text_color=GREEN)

    def collect_trials(self) -> list[dict[str, Any]]:
        trials: list[dict[str, Any]] = []
        for folder in sorted((path for path in AIM.glob("*") if path.is_dir())):
            session = normalize_session(read_json(folder / "trials.json", []))
            trials.extend(session["trials"])
        return trials

    def free_hold_times(self) -> list[float]:
        holds: list[float] = []
        for folder in RECORDINGS.glob("*"):
            events = read_json(folder / "events.json", [])
            if not isinstance(events, list):
                continue
            for event in events:
                if isinstance(event, dict) and event.get("type") == "click" and event.get("hold_ms") is not None:
                    try:
                        holds.append(float(event["hold_ms"]))
                    except (TypeError, ValueError):
                        pass
        return holds

    def build_profile(self) -> None:
        self.build_profile_btn.configure(state="disabled", text="Profiel bouwen…")
        try:
            profile = build_personal_profile(self.collect_trials(), self.free_hold_times())
            write_json(PROFILES / "master_profile.json", profile)
            self.refresh_profile_status()
            self.aim_status.configure(text="Persoonlijk profiel bijgewerkt", text_color=GREEN)
        except Exception as exc:
            self.aim_status.configure(text=f"Profielbouw mislukt: {type(exc).__name__}: {exc}", text_color=RED)
        finally:
            self.build_profile_btn.configure(state="normal", text="Build Profile")

    def refresh_profile_status(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not isinstance(profile, dict) or not profile:
            self.profile_status.configure(text="Nog geen profiel", text_color=MUTED)
            return
        contexts = profile.get("contexts", {})
        strong_contexts = sum(1 for value in contexts.values() if isinstance(value, dict) and int(value.get("trial_count", 0)) >= 8) if isinstance(contexts, dict) else 0
        self.profile_status.configure(
            text=f"Kwaliteit: {profile.get('quality_percent', 0)}%\nTargets: {profile.get('trial_count', 0)}\nSterke contexten: {strong_contexts}\nAfgekeurd: {profile.get('rejected_trial_count', 0)}",
            text_color=GREEN,
        )

    def test_latest_ab(self) -> None:
        self.compare_btn.configure(state="disabled", text="A/B maken…")
        try:
            folder, a, b = create_latest_comparison()
            self.timeline = ReplayTimeline(a, b)
            self.replay_running = False
            self.compare_status.configure(text=f"Klaar · {self.timeline.count} targets\n{folder.name}", text_color=GREEN)
            self.show("Results")
            self.draw_replay()
        except ComparisonError as exc:
            self.compare_status.configure(text=str(exc), text_color=RED)
        except Exception as exc:
            self.compare_status.configure(text=f"A/B-fout: {type(exc).__name__}: {exc}", text_color=RED)
        finally:
            self.compare_btn.configure(state="normal", text="Test nieuwste opname A/B")

    def _page_results(self) -> None:
        body = self._page("Results", "Results", "A en B simultaan in exact dezelfde 1920 × 1080 arena.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        controls = Card(body)
        controls.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(controls, text="← Aim Lab", fg_color=PANEL2, command=lambda: self.show("Aim Lab")).pack(side="left", padx=(12, 6), pady=10)
        ctk.CTkButton(controls, text="← Vorige", fg_color=PANEL2, command=lambda: self.change_replay_trial(-1)).pack(side="left", padx=6, pady=10)
        self.replay_play_btn = ctk.CTkButton(controls, text="▶ Alles afspelen", fg_color=PURPLE, command=self.toggle_replay)
        self.replay_play_btn.pack(side="left", padx=6, pady=10)
        ctk.CTkButton(controls, text="Volgende →", fg_color=PANEL2, command=lambda: self.change_replay_trial(1)).pack(side="left", padx=6, pady=10)
        self.speed_menu = ctk.CTkOptionMenu(controls, values=["0.5x", "1x", "1.5x", "2x"], width=80, command=self.set_replay_speed)
        self.speed_menu.set("1x")
        self.speed_menu.pack(side="left", padx=6, pady=10)
        self.equal_duration = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(controls, text="Gelijke duur", variable=self.equal_duration, command=self.update_equal_duration).pack(side="left", padx=8, pady=10)
        self.replay_status = ctk.CTkLabel(controls, text="Nog geen replay geladen", text_color=MUTED, font=("Segoe UI", 12, "bold"))
        self.replay_status.pack(side="right", padx=16)

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
        self.replay_canvas.bind("<Configure>", lambda _event: self.draw_replay())
        info = Card(content)
        info.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(info, text="A · PAARS", text_color=PURPLE, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(18, 6))
        ctk.CTkLabel(info, text="B · GROEN", text_color=GREEN, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(18, 6))
        self.replay_metrics = ctk.CTkLabel(info, text="", text_color=MUTED, justify="left", wraplength=250)
        self.replay_metrics.pack(anchor="w", padx=16, pady=18)

    def ensure_timeline(self) -> bool:
        if self.timeline is not None:
            return True
        try:
            _folder, a, b = latest_comparison()
            self.timeline = ReplayTimeline(a, b)
            return True
        except (ComparisonError, ValueError):
            self.replay_status.configure(text="Nog geen A/B-vergelijking", text_color=RED)
            return False

    def set_replay_speed(self, value: str) -> None:
        try:
            self.replay_speed = max(0.1, float(value.rstrip("x")))
        except ValueError:
            self.replay_speed = 1.0

    def update_equal_duration(self) -> None:
        if self.timeline is not None:
            self.timeline.equal_duration = bool(self.equal_duration.get())
            self.draw_replay()

    def _cancel_replay(self) -> None:
        if self.replay_after_id:
            try:
                self.after_cancel(self.replay_after_id)
            except Exception:
                pass
        self.replay_after_id = None

    def toggle_replay(self) -> None:
        if not self.ensure_timeline() or self.timeline is None:
            return
        if self.replay_running:
            elapsed = (time.perf_counter() - self.replay_started_at) * 1000.0 * self.replay_speed
            self.timeline.advance(elapsed)
            self.replay_running = False
            self._cancel_replay()
            self.replay_play_btn.configure(text="▶ Verder afspelen")
            self.draw_replay()
            return
        if self.timeline.trial_index == self.timeline.count - 1 and self.timeline.elapsed_ms >= self.timeline.duration_ms:
            self.timeline.reset()
        self.replay_running = True
        self.replay_started_at = time.perf_counter()
        self.replay_play_btn.configure(text="⏸ Pauze")
        self._replay_tick()

    def _replay_tick(self) -> None:
        if not self.replay_running or self.timeline is None:
            self.replay_after_id = None
            return
        now = time.perf_counter()
        delta_ms = (now - self.replay_started_at) * 1000.0 * self.replay_speed
        self.replay_started_at = now
        finished = self.timeline.advance(delta_ms)
        self.draw_replay()
        if finished:
            self.replay_running = False
            self.replay_after_id = None
            self.replay_play_btn.configure(text="↻ Opnieuw afspelen")
            self.replay_status.configure(text=f"Klaar · {self.timeline.count}/{self.timeline.count} targets")
            return
        self.replay_after_id = self.after(FRAME_MS, self._replay_tick)

    def change_replay_trial(self, delta: int) -> None:
        if not self.ensure_timeline() or self.timeline is None:
            return
        self.replay_running = False
        self._cancel_replay()
        self.timeline.change_trial(delta)
        self.replay_play_btn.configure(text="▶ Vanaf hier afspelen")
        self.draw_replay()

    def draw_replay(self) -> None:
        canvas = getattr(self, "replay_canvas", None)
        if canvas is None:
            return
        if not self.ensure_timeline() or self.timeline is None:
            canvas.delete("all")
            return
        timeline = self.timeline
        timeline.equal_duration = bool(self.equal_duration.get())
        points_a, points_b = timeline.points()
        trial_a = timeline.current_a
        trial_b = timeline.current_b
        canvas.delete("all")
        scale, offset_x, offset_y = self._canvas_box(canvas)
        canvas.create_rectangle(offset_x, offset_y, offset_x + VIRTUAL_WIDTH * scale, offset_y + VIRTUAL_HEIGHT * scale, outline=BORDER, width=1)

        def draw_points(points: list[dict[str, float]], color: str) -> None:
            coordinates: list[float] = []
            for point in points:
                x, y = self._to_canvas(canvas, point["x"], point["y"])
                coordinates.extend((x, y))
            if len(coordinates) >= 4:
                canvas.create_line(*coordinates, fill=color, width=2.5, smooth=True)
            if points:
                x, y = self._to_canvas(canvas, points[-1]["x"], points[-1]["y"])
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="")

        draw_points(points_a, PURPLE)
        draw_points(points_b, GREEN)
        target = trial_a["target"]
        target_x, target_y = self._to_canvas(canvas, float(target["x"]), float(target["y"]))
        radius = max(6.0, float(target["radius"]) * scale)
        canvas.create_oval(target_x - radius, target_y - radius, target_x + radius, target_y + radius, outline="#e5e7eb", width=2)
        canvas.create_text(target_x, target_y, text=str(timeline.trial_index + 1), fill="white")
        self.replay_status.configure(text=f"Target {timeline.trial_index + 1}/{timeline.count}")

        derived_a = trial_a.get("derived", {}) if isinstance(trial_a.get("derived"), dict) else {}
        derived_b = trial_b.get("derived", {}) if isinstance(trial_b.get("derived"), dict) else {}
        self.replay_metrics.configure(
            text=(
                f"Movement A: {derived_a.get('movement_time_ms', 0):.0f} ms\n"
                f"Movement B: {derived_b.get('movement_time_ms', 0):.0f} ms\n\n"
                f"Overshoot A: {derived_a.get('overshoot_px', 0):.1f} px\n"
                f"Overshoot B: {derived_b.get('overshoot_px', 0):.1f} px\n\n"
                f"Slowdown A: {derived_a.get('slowdown_ratio', 0):.2f}\n"
                f"Slowdown B: {derived_b.get('slowdown_ratio', 0):.2f}\n\n"
                f"Correcties A: {int(derived_a.get('correction_count', 0) or 0)}\n"
                f"Correcties B: {int(derived_b.get('correction_count', 0) or 0)}"
            )
        )

    def close_app(self) -> None:
        self._cancel_aim_sampler()
        self._cancel_replay()
        if self.recorder.running:
            self.recorder.stop()
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()
