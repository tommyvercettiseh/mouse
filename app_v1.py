from __future__ import annotations

import math
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk

from ai_mouse_lab import __version__
from ai_mouse_lab.comparison_flow import collect_aim_trials, create_latest_comparison, latest_comparison
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.models import normalize_trials, trial_duration_ms, visible_points
from ai_mouse_lab.personal_model import build_personal_profile
from ai_mouse_lab.storage import AIM, PROFILES, RECORDINGS, now_stamp, read_json, write_json

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
VIRTUAL_WIDTH = 1920.0
VIRTUAL_HEIGHT = 1080.0
SAMPLE_MS = 8
FRAME_MS = 16
SCHEMA_VERSION = 7


class Card(ctk.CTkFrame):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER, **kwargs)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"AI Mouse Lab v{__version__}")
        self.geometry("1440x880")
        self.minsize(1160, 720)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self.pages: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}

        self.free_recording = False
        self.free_paused = False
        self.free_points: list[dict[str, float]] = []
        self.free_started = 0.0
        self.free_pause_started = 0.0
        self.free_paused_total = 0.0
        self.free_after_id: str | None = None
        self.free_last_drawn = 0

        self.aim_active = False
        self.aim_generation = 0
        self.aim_after_id: str | None = None
        self.aim_overlay: ctk.CTkFrame | None = None
        self.aim_canvas: ctk.CTkCanvas | None = None
        self.aim_plan: list[dict[str, Any]] = []
        self.aim_trials: list[dict[str, Any]] = []
        self.aim_index = 0
        self.aim_points: list[dict[str, float]] = []
        self.aim_miss_clicks: list[dict[str, float]] = []
        self.aim_start = {"x": 960.0, "y": 540.0}
        self.aim_spawn = 0.0
        self.aim_click_down: float | None = None
        self.aim_session_folder: Path | None = None
        self.aim_last_drawn = 0

        self.replay_a: dict[str, Any] = {}
        self.replay_b: dict[str, Any] = {}
        self.replay_index = 0
        self.replay_elapsed = 0.0
        self.replay_started = 0.0
        self.replay_running = False
        self.replay_finished = False
        self.replay_after_id: str | None = None

        self._build_shell()
        self.show("Aim Lab")

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        nav = ctk.CTkFrame(self, width=170, fg_color="#0d131d", corner_radius=0)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        ctk.CTkLabel(nav, text="AI Mouse Lab", text_color=TEXT, font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=16, pady=(24, 2))
        ctk.CTkLabel(nav, text=f"v{__version__}", text_color=MUTED).pack(anchor="w", padx=16, pady=(0, 18))
        for name in ("Free Record", "Aim Lab"):
            button = ctk.CTkButton(nav, text=name, anchor="w", height=42, fg_color="transparent", hover_color=PANEL2, command=lambda key=name: self.show(key))
            button.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[name] = button
        ctk.CTkLabel(nav, text="● Data blijft lokaal", text_color=GREEN).pack(side="bottom", anchor="w", padx=16, pady=18)

        self.host = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.host.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.host.grid_rowconfigure(0, weight=1)
        self.host.grid_columnconfigure(0, weight=1)
        self._page_free_record()
        self._page_aim()
        self._page_results()

    def page(self, key: str, title: str, subtitle: str) -> ctk.CTkFrame:
        root = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        root.grid(row=0, column=0, sticky="nsew")
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(header, text=title, text_color=TEXT, font=("Segoe UI", 30, "bold")).pack(anchor="w")
        ctk.CTkLabel(header, text=subtitle, text_color=MUTED).pack(anchor="w")
        body = ctk.CTkFrame(root, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        self.pages[key] = root
        return body

    def show(self, key: str) -> None:
        if key not in self.pages:
            key = "Aim Lab"
        self._stop_replay()
        for name, page in self.pages.items():
            page.grid_remove()
            button = self.nav_buttons.get(name)
            if button is not None:
                button.configure(fg_color=PURPLE if name == key else "transparent")
        self.pages[key].grid()
        if key == "Aim Lab":
            self.refresh_profile_status()
        elif key == "Results":
            self.refresh_results()

    def _page_free_record(self) -> None:
        body = self.page("Free Record", "Free Record", "Vrije muisroute opnemen zonder deze automatisch als Aim Lab-training te gebruiken.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        self.free_canvas = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        self.free_canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        side = Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="Vrije opname", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(side, text="Registreert globale cursorpunten en timing. Aim Lab blijft de bron voor targetmetriek.", text_color=MUTED, justify="left", wraplength=245).pack(anchor="w", padx=18, pady=(0, 12))
        self.free_start_btn = ctk.CTkButton(side, text="▶ Start opname", fg_color=PURPLE, height=44, command=self.free_start)
        self.free_start_btn.pack(fill="x", padx=18, pady=6)
        self.free_pause_btn = ctk.CTkButton(side, text="⏸ Pauze", fg_color=PANEL2, height=42, command=self.free_pause, state="disabled")
        self.free_pause_btn.pack(fill="x", padx=18, pady=6)
        self.free_stop_btn = ctk.CTkButton(side, text="■ Stop en opslaan", fg_color=PANEL2, height=42, command=self.free_stop, state="disabled")
        self.free_stop_btn.pack(fill="x", padx=18, pady=6)
        self.free_status = ctk.CTkLabel(side, text="Klaar voor opname", text_color=MUTED, justify="left", font=("Consolas", 12))
        self.free_status.pack(anchor="w", padx=18, pady=16)

    def free_start(self) -> None:
        if self.free_recording:
            return
        self.free_recording = True
        self.free_paused = False
        self.free_points = []
        self.free_started = time.perf_counter()
        self.free_paused_total = 0.0
        self.free_last_drawn = 0
        self.free_canvas.delete("all")
        self.free_start_btn.configure(state="disabled")
        self.free_pause_btn.configure(state="normal", text="⏸ Pauze")
        self.free_stop_btn.configure(state="normal")
        self._free_tick()

    def free_pause(self) -> None:
        if not self.free_recording:
            return
        if self.free_paused:
            self.free_paused_total += time.perf_counter() - self.free_pause_started
            self.free_paused = False
            self.free_pause_btn.configure(text="⏸ Pauze")
        else:
            self.free_paused = True
            self.free_pause_started = time.perf_counter()
            self.free_pause_btn.configure(text="▶ Hervatten")

    def _free_tick(self) -> None:
        if not self.free_recording:
            self.free_after_id = None
            return
        if not self.free_paused:
            x, y = self.winfo_pointerxy()
            elapsed = (time.perf_counter() - self.free_started - self.free_paused_total) * 1000.0
            self.free_points.append({"t_ms": round(elapsed, 3), "x": float(x), "y": float(y)})
            self._draw_free()
            if len(self.free_points) % 12 == 0:
                self.free_status.configure(text=f"Opnemen…\nPunten: {len(self.free_points)}\nDuur: {elapsed / 1000:.1f} s")
        self.free_after_id = self.after(SAMPLE_MS, self._free_tick)

    def _draw_free(self) -> None:
        if len(self.free_points) < 2:
            return
        width = max(100.0, float(self.free_canvas.winfo_width()))
        height = max(100.0, float(self.free_canvas.winfo_height()))
        screen_width = max(1.0, float(self.winfo_screenwidth()))
        screen_height = max(1.0, float(self.winfo_screenheight()))
        for index in range(max(1, self.free_last_drawn), len(self.free_points)):
            first, second = self.free_points[index - 1], self.free_points[index]
            self.free_canvas.create_line(
                first["x"] / screen_width * width,
                first["y"] / screen_height * height,
                second["x"] / screen_width * width,
                second["y"] / screen_height * height,
                fill=PURPLE,
                width=2,
            )
        self.free_last_drawn = len(self.free_points)

    def free_stop(self) -> None:
        if not self.free_recording:
            return
        self.free_recording = False
        self._cancel_free_after()
        duration = self.free_points[-1]["t_ms"] if self.free_points else 0.0
        path = RECORDINGS / f"free_{now_stamp()}.json"
        write_json(path, {"schema_version": SCHEMA_VERSION, "coordinate_space": "global_screen", "screen": {"width": self.winfo_screenwidth(), "height": self.winfo_screenheight()}, "duration_ms": duration, "points": self.free_points, "created_at": datetime.now().isoformat()})
        self.free_start_btn.configure(state="normal")
        self.free_pause_btn.configure(state="disabled", text="⏸ Pauze")
        self.free_stop_btn.configure(state="disabled")
        self.free_status.configure(text=f"Opgeslagen\nPunten: {len(self.free_points)}\nDuur: {duration / 1000:.1f} s\n{path.name}")

    def _cancel_free_after(self) -> None:
        if self.free_after_id:
            try:
                self.after_cancel(self.free_after_id)
            except Exception:
                pass
        self.free_after_id = None

    def _page_aim(self) -> None:
        body = self.page("Aim Lab", "Aim Lab", "Volledige targetroute, timing, overshoot, acceleratie, braking en slowdown in 1920 × 1080.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        preview = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        preview.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        preview.create_text(500, 300, text="Aim Lab opent fullscreen op hetzelfde scherm", fill=MUTED, font=("Segoe UI", 18, "bold"))
        side = Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="Sessie", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        self.count_menu = ctk.CTkOptionMenu(side, values=["20", "50", "100"], fg_color=PANEL2, button_color=PURPLE)
        self.count_menu.set("20")
        self.count_menu.pack(fill="x", padx=18, pady=8)
        self.capture_mode = ctk.CTkOptionMenu(side, values=["Normale opname", "Detectietest"], fg_color=PANEL2, button_color=PURPLE)
        self.capture_mode.set("Normale opname")
        self.capture_mode.pack(fill="x", padx=18, pady=8)
        self.start_btn = ctk.CTkButton(side, text="Start Aim Lab", fg_color=PURPLE, height=46, command=self.start_aim)
        self.start_btn.pack(fill="x", padx=18, pady=8)
        self.aim_status = ctk.CTkLabel(side, text="Klaar", text_color=MUTED, justify="left", wraplength=250)
        self.aim_status.pack(anchor="w", padx=18, pady=10)
        ctk.CTkLabel(side, text="Persoonlijk profiel", text_color=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(10, 4))
        self.profile_btn = ctk.CTkButton(side, text="Build Profile", fg_color=GREEN, hover_color="#2fb669", text_color="#07140d", height=42, command=self.build_profile)
        self.profile_btn.pack(fill="x", padx=18, pady=(0, 6))
        self.profile_status = ctk.CTkLabel(side, text="Nog geen profiel gebouwd", text_color=MUTED, justify="left", wraplength=250)
        self.profile_status.pack(anchor="w", padx=18, pady=(0, 12))
        ctk.CTkLabel(side, text="Laatste opname vergelijken", text_color=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(8, 4))
        self.compare_btn = ctk.CTkButton(side, text="Test nieuwste opname A/B", fg_color=PANEL2, hover_color=PURPLE, height=42, command=self.test_latest_ab)
        self.compare_btn.pack(fill="x", padx=18, pady=(0, 6))
        self.compare_status = ctk.CTkLabel(side, text="Laatste Aim Lab-opname is de target-playlist.", text_color=MUTED, justify="left", wraplength=250)
        self.compare_status.pack(anchor="w", padx=18, pady=(0, 12))

    def start_aim(self) -> None:
        if self.aim_active:
            return
        self.aim_active = True
        self.aim_generation += 1
        self.aim_trials = []
        self.aim_index = 0
        self.aim_session_folder = AIM / now_stamp()
        self.aim_session_folder.mkdir(parents=True, exist_ok=True)
        self.start_btn.configure(state="disabled")
        self.aim_overlay = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.aim_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.aim_overlay.grid_rowconfigure(0, weight=1)
        self.aim_overlay.grid_columnconfigure(0, weight=1)
        self.aim_canvas = ctk.CTkCanvas(self.aim_overlay, bg=PANEL, highlightthickness=0)
        self.aim_canvas.grid(row=0, column=0, sticky="nsew")
        self.aim_canvas.bind("<ButtonPress-1>", self._aim_press)
        self.aim_canvas.bind("<ButtonRelease-1>", self._aim_release)
        self.bind("<Escape>", lambda _event: self.abort_aim())
        self.attributes("-fullscreen", True)
        count = int(self.count_menu.get())
        self.aim_plan = [
            {
                "index": index,
                "x": random.randint(100, 1820),
                "y": random.randint(100, 980),
                "radius": random.choice([12, 18, 26]),
            }
            for index in range(count)
        ]
        write_json(self.aim_session_folder / "plan.json", {"schema_version": SCHEMA_VERSION, "width": VIRTUAL_WIDTH, "height": VIRTUAL_HEIGHT, "targets": self.aim_plan})
        self.after(50, lambda: self._start_aim_when_ready(self.aim_generation, 0))

    def _start_aim_when_ready(self, generation: int, attempt: int) -> None:
        if not self.aim_active or generation != self.aim_generation or self.aim_canvas is None:
            return
        self.aim_canvas.update_idletasks()
        if self.aim_canvas.winfo_width() < 800 or self.aim_canvas.winfo_height() < 500:
            if attempt < 80:
                self.after(40, lambda: self._start_aim_when_ready(generation, attempt + 1))
            else:
                self.abort_aim("Fullscreen canvas kon niet worden opgebouwd.")
            return
        self._show_aim_target()
        self._aim_sample(generation)

    def _canvas_box(self, canvas: ctk.CTkCanvas) -> tuple[float, float, float]:
        width = max(1.0, float(canvas.winfo_width()))
        height = max(1.0, float(canvas.winfo_height()))
        scale = min(width / VIRTUAL_WIDTH, height / VIRTUAL_HEIGHT)
        return scale, (width - VIRTUAL_WIDTH * scale) / 2.0, (height - VIRTUAL_HEIGHT * scale) / 2.0

    def _to_canvas(self, canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_box(canvas)
        return offset_x + x * scale, offset_y + y * scale

    def _to_virtual(self, canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_box(canvas)
        return (x - offset_x) / max(scale, 1e-9), (y - offset_y) / max(scale, 1e-9)

    def _pointer_virtual(self) -> tuple[float, float]:
        if self.aim_canvas is None:
            return 0.0, 0.0
        screen_x, screen_y = self.winfo_pointerxy()
        return self._to_virtual(self.aim_canvas, screen_x - self.aim_canvas.winfo_rootx(), screen_y - self.aim_canvas.winfo_rooty())

    def _show_aim_target(self) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        if self.aim_index >= len(self.aim_plan):
            self.finish_aim()
            return
        self.aim_canvas.delete("all")
        scale, offset_x, offset_y = self._canvas_box(self.aim_canvas)
        self.aim_canvas.create_rectangle(offset_x, offset_y, offset_x + VIRTUAL_WIDTH * scale, offset_y + VIRTUAL_HEIGHT * scale, outline=BORDER)
        target = self.aim_plan[self.aim_index]
        x, y = self._to_canvas(self.aim_canvas, target["x"], target["y"])
        radius = target["radius"] * scale
        self.aim_canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=PURPLE, outline="#c4b5fd", width=3)
        self.aim_canvas.create_text(x, y, text=str(self.aim_index + 1), fill="white")
        self.aim_canvas.create_text(18, 18, anchor="nw", text=f"Target {self.aim_index + 1}/{len(self.aim_plan)} · misklikken {len(self.aim_miss_clicks)} · Esc stopt", fill=TEXT, font=("Segoe UI", 12, "bold"), tags="status")
        pointer_x, pointer_y = self._pointer_virtual()
        self.aim_start = {"x": pointer_x, "y": pointer_y}
        self.aim_points = [{"t_ms": 0.0, "x": pointer_x, "y": pointer_y}]
        self.aim_miss_clicks = []
        self.aim_spawn = time.perf_counter()
        self.aim_click_down = None
        self.aim_last_drawn = 1

    def _aim_sample(self, generation: int) -> None:
        if not self.aim_active or generation != self.aim_generation:
            self.aim_after_id = None
            return
        x, y = self._pointer_virtual()
        t_ms = (time.perf_counter() - self.aim_spawn) * 1000.0
        self.aim_points.append({"t_ms": round(t_ms, 3), "x": round(x, 3), "y": round(y, 3)})
        self._draw_aim_trace()
        self.aim_after_id = self.after(SAMPLE_MS, lambda: self._aim_sample(generation))

    def _draw_aim_trace(self) -> None:
        if self.aim_canvas is None or len(self.aim_points) < 2:
            return
        for index in range(max(1, self.aim_last_drawn), len(self.aim_points)):
            first, second = self.aim_points[index - 1], self.aim_points[index]
            first_x, first_y = self._to_canvas(self.aim_canvas, first["x"], first["y"])
            second_x, second_y = self._to_canvas(self.aim_canvas, second["x"], second["y"])
            self.aim_canvas.create_line(first_x, first_y, second_x, second_y, fill=BLUE, width=2)
        self.aim_last_drawn = len(self.aim_points)

    def _aim_press(self, _event: Any) -> None:
        if self.aim_active:
            self.aim_click_down = time.perf_counter()

    def _aim_release(self, event: Any) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        released = time.perf_counter()
        x, y = self._to_virtual(self.aim_canvas, float(event.x), float(event.y))
        self.aim_points.append({"t_ms": round((released - self.aim_spawn) * 1000.0, 3), "x": x, "y": y})
        target = self.aim_plan[self.aim_index]
        click = {
            "down_t_ms": round(((self.aim_click_down or released) - self.aim_spawn) * 1000.0, 3),
            "up_t_ms": round((released - self.aim_spawn) * 1000.0, 3),
            "x": x,
            "y": y,
        }
        hit = math.hypot(x - target["x"], y - target["y"]) <= target["radius"]
        if not hit:
            self.aim_miss_clicks.append(click)
            self.aim_click_down = None
            self.aim_canvas.itemconfigure("status", text=f"Target {self.aim_index + 1}/{len(self.aim_plan)} · misklikken {len(self.aim_miss_clicks)} · raak hetzelfde target")
            return

        target_data = {"index": self.aim_index, "x": target["x"], "y": target["y"], "radius": target["radius"]}
        try:
            derived = derive_trial(target_data, self.aim_start, self.aim_points, click)
        except (TypeError, ValueError, KeyError) as exc:
            self.abort_aim(f"Meetfout: {type(exc).__name__}: {exc}")
            return
        self.aim_trials.append(
            {
                "schema_version": SCHEMA_VERSION,
                "target": target_data,
                "start": self.aim_start,
                "points": list(self.aim_points),
                "click": click,
                "miss_clicks": list(self.aim_miss_clicks),
                "derived": derived,
                "capture_mode": "test" if self.capture_mode.get() == "Detectietest" else "normal",
            }
        )
        self.aim_index += 1
        self._show_aim_target()

    def _cancel_aim_after(self) -> None:
        if self.aim_after_id:
            try:
                self.after_cancel(self.aim_after_id)
            except Exception:
                pass
        self.aim_after_id = None

    def finish_aim(self) -> None:
        if not self.aim_active:
            return
        self.aim_active = False
        self.aim_generation += 1
        self._cancel_aim_after()
        folder = self.aim_session_folder or (AIM / now_stamp())
        write_json(folder / "trials.json", self.aim_trials)
        write_json(folder / "summary.json", {"schema_version": SCHEMA_VERSION, "trial_count": len(self.aim_trials), "point_count": sum(len(trial["points"]) for trial in self.aim_trials), "miss_count": sum(len(trial.get("miss_clicks", [])) for trial in self.aim_trials), "created_at": datetime.now().isoformat()})
        self._close_aim_overlay()
        self.aim_status.configure(text=f"Klaar\n{len(self.aim_trials)} targets\n{sum(len(trial.get('miss_clicks', [])) for trial in self.aim_trials)} misklikken", text_color=GREEN)

    def abort_aim(self, message: str = "Sessie afgebroken") -> None:
        if not self.aim_active:
            return
        self.aim_active = False
        self.aim_generation += 1
        self._cancel_aim_after()
        self._close_aim_overlay()
        self.aim_status.configure(text=message, text_color=RED)

    def _close_aim_overlay(self) -> None:
        try:
            self.attributes("-fullscreen", False)
        except Exception:
            pass
        self.unbind("<Escape>")
        if self.aim_overlay is not None:
            self.aim_overlay.destroy()
        self.aim_overlay = None
        self.aim_canvas = None
        self.start_btn.configure(state="normal")
        self.lift()
        self.focus_force()

    def build_profile(self) -> None:
        self.profile_btn.configure(state="disabled", text="Profiel bouwen…")
        try:
            trials = collect_aim_trials()
            if not trials:
                raise ValueError("Nog geen Aim Lab-opnames gevonden.")
            profile = build_personal_profile(trials, [])
            write_json(PROFILES / "master_profile.json", profile)
            self.refresh_profile_status()
            self.aim_status.configure(text="Persoonlijk profiel bijgewerkt", text_color=GREEN)
        except (TypeError, ValueError, KeyError) as exc:
            self.aim_status.configure(text=f"Profielbouw mislukt: {exc}", text_color=RED)
        finally:
            self.profile_btn.configure(state="normal", text="Build Profile")

    def refresh_profile_status(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not isinstance(profile, dict) or not profile:
            self.profile_status.configure(text="Nog geen profiel gebouwd", text_color=MUTED)
            return
        contexts = profile.get("contexts", {})
        strong_contexts = sum(1 for context in contexts.values() if isinstance(context, dict) and int(context.get("trial_count", 0)) >= 8) if isinstance(contexts, dict) else 0
        self.profile_status.configure(text=f"Kwaliteit: {profile.get('quality_percent', 0)}%\nTargets: {profile.get('trial_count', 0)}\nAfgekeurd: {profile.get('rejected_trial_count', 0)}\nSterke contexten: {strong_contexts}", text_color=GREEN)

    def test_latest_ab(self) -> None:
        self.compare_btn.configure(state="disabled", text="Vergelijking maken…")
        try:
            folder, session_a, session_b = create_latest_comparison()
            self.replay_a = {**session_a, "trials": normalize_trials(session_a)}
            self.replay_b = {**session_b, "trials": normalize_trials(session_b)}
            self.replay_index = 0
            self.replay_elapsed = 0.0
            self.replay_finished = False
            self.compare_status.configure(text=f"Klaar · {self._replay_count()} targets\n{folder.name}", text_color=GREEN)
            self.show("Results")
        except (TypeError, ValueError, KeyError) as exc:
            self.compare_status.configure(text=f"A/B mislukt: {exc}", text_color=RED)
        finally:
            self.compare_btn.configure(state="normal", text="Test nieuwste opname A/B")

    def _page_results(self) -> None:
        body = self.page("Results", "Results", "A en B automatisch achter elkaar in dezelfde 1920 × 1080 arena.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        controls = Card(body)
        controls.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(controls, text="← Aim Lab", fg_color=PANEL2, command=lambda: self.show("Aim Lab")).pack(side="left", padx=(12, 6), pady=10)
        ctk.CTkButton(controls, text="← Vorige", fg_color=PANEL2, command=lambda: self.replay_change(-1)).pack(side="left", padx=6, pady=10)
        self.replay_play_btn = ctk.CTkButton(controls, text="▶ Alles afspelen", fg_color=PURPLE, command=self.replay_toggle)
        self.replay_play_btn.pack(side="left", padx=6, pady=10)
        ctk.CTkButton(controls, text="Volgende →", fg_color=PANEL2, command=lambda: self.replay_change(1)).pack(side="left", padx=6, pady=10)
        self.replay_speed_menu = ctk.CTkOptionMenu(controls, values=["0.5x", "1x", "1.5x", "2x"], width=82)
        self.replay_speed_menu.set("1x")
        self.replay_speed_menu.pack(side="left", padx=6, pady=10)
        self.replay_equal = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(controls, text="Gelijke duur", variable=self.replay_equal, command=lambda: self.replay_draw(self.replay_elapsed)).pack(side="left", padx=8, pady=10)
        self.replay_label = ctk.CTkLabel(controls, text="Nog geen replay", text_color=MUTED, font=("Segoe UI", 12, "bold"))
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
        self.replay_canvas.bind("<Configure>", lambda _event: self.replay_draw(self.replay_elapsed))
        stats = Card(content)
        stats.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(stats, text="A · PAARS", text_color=PURPLE, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(18, 6))
        self.stats_a = ctk.CTkLabel(stats, text="", text_color=MUTED, justify="left", wraplength=260)
        self.stats_a.pack(anchor="w", padx=16, pady=(0, 14))
        ctk.CTkLabel(stats, text="B · GROEN", text_color=GREEN, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(8, 6))
        self.stats_b = ctk.CTkLabel(stats, text="", text_color=MUTED, justify="left", wraplength=260)
        self.stats_b.pack(anchor="w", padx=16, pady=(0, 14))

    def refresh_results(self) -> None:
        if self._replay_count() == 0:
            _folder, session_a, session_b = latest_comparison()
            self.replay_a = {**session_a, "trials": normalize_trials(session_a)} if isinstance(session_a, dict) else {}
            self.replay_b = {**session_b, "trials": normalize_trials(session_b)} if isinstance(session_b, dict) else {}
        self.replay_index = max(0, min(max(0, self._replay_count() - 1), self.replay_index))
        self.replay_draw(self.replay_elapsed)

    def _replay_trials(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return normalize_trials(self.replay_a), normalize_trials(self.replay_b)

    def _replay_count(self) -> int:
        trials_a, trials_b = self._replay_trials()
        return min(len(trials_a), len(trials_b))

    def _replay_duration(self) -> float:
        trials_a, trials_b = self._replay_trials()
        if not trials_a or not trials_b:
            return 0.0
        index = max(0, min(self._replay_count() - 1, self.replay_index))
        return max(16.0, trial_duration_ms(trials_a[index]), trial_duration_ms(trials_b[index]))

    def _replay_speed_value(self) -> float:
        try:
            return max(0.1, float(self.replay_speed_menu.get().rstrip("x")))
        except ValueError:
            return 1.0

    def replay_toggle(self) -> None:
        if self._replay_count() == 0:
            self.replay_label.configure(text="Geen geldige A/B-data", text_color=RED)
            return
        if self.replay_running:
            self.replay_elapsed += (time.perf_counter() - self.replay_started) * 1000.0 * self._replay_speed_value()
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
        elapsed = self.replay_elapsed + (time.perf_counter() - self.replay_started) * 1000.0 * self._replay_speed_value()
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
        self.replay_label.configure(text=f"Klaar · {self._replay_count()}/{self._replay_count()} targets", text_color=TEXT)

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

    def _stop_replay(self) -> None:
        self.replay_running = False
        if self.replay_after_id:
            try:
                self.after_cancel(self.replay_after_id)
            except Exception:
                pass
        self.replay_after_id = None

    def replay_draw(self, elapsed: float) -> None:
        canvas = getattr(self, "replay_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        trials_a, trials_b = self._replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            canvas.create_text(max(1, canvas.winfo_width()) / 2, max(1, canvas.winfo_height()) / 2, text="Nog geen A/B-vergelijking", fill=MUTED, font=("Segoe UI", 18, "bold"))
            self.stats_a.configure(text="")
            self.stats_b.configure(text="")
            return
        index = max(0, min(count - 1, self.replay_index))
        trial_a, trial_b = trials_a[index], trials_b[index]
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
        canvas.create_rectangle(offset_x, offset_y, offset_x + VIRTUAL_WIDTH * scale, offset_y + VIRTUAL_HEIGHT * scale, outline=BORDER)
        target = trial_a["target"]
        target_x, target_y = self._to_canvas(canvas, float(target["x"]), float(target["y"]))
        radius = float(target["radius"]) * scale
        canvas.create_oval(target_x - radius, target_y - radius, target_x + radius, target_y + radius, outline="white", width=2)
        canvas.create_text(target_x, target_y, text=str(index + 1), fill="white")
        self._draw_route(canvas, visible_points(trial_a, elapsed_a), PURPLE)
        self._draw_route(canvas, visible_points(trial_b, elapsed_b), GREEN)
        self.stats_a.configure(text=self._stats_text(trial_a))
        self.stats_b.configure(text=self._stats_text(trial_b))
        self.replay_label.configure(text=f"Target {index + 1}/{count}", text_color=TEXT)

    def _draw_route(self, canvas: ctk.CTkCanvas, points: list[dict[str, float]], color: str) -> None:
        if not points:
            return
        coordinates: list[float] = []
        for point in points:
            x, y = self._to_canvas(canvas, point["x"], point["y"])
            coordinates.extend((x, y))
        if len(coordinates) >= 4:
            canvas.create_line(*coordinates, fill=color, width=3, smooth=True)
        x, y = coordinates[-2], coordinates[-1]
        canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="white", width=1)

    @staticmethod
    def _stats_text(trial: dict[str, Any]) -> str:
        derived = trial.get("derived", {})
        if not isinstance(derived, dict):
            derived = {}
        return (
            f"Reactie: {float(derived.get('reaction_ms', 0) or 0):.0f} ms\n"
            f"Beweging: {float(derived.get('movement_time_ms', 0) or 0):.0f} ms\n"
            f"Efficiëntie: {float(derived.get('path_efficiency', 0) or 0):.3f}\n"
            f"Overshoot: {float(derived.get('overshoot_px', 0) or 0):.1f} px\n"
            f"Piek accel.: {float(derived.get('peak_accel_px_s2', 0) or 0):.0f}\n"
            f"Piek remming: {float(derived.get('peak_decel_px_s2', 0) or 0):.0f}\n"
            f"Remstart: {float(derived.get('braking_start_ms', 0) or 0):.0f} ms\n"
            f"Remafstand: {float(derived.get('braking_distance_px', 0) or 0):.1f} px\n"
            f"Slowdown: {float(derived.get('slowdown_ratio', 0) or 0):.3f}\n"
            f"Correcties: {int(float(derived.get('correction_count', 0) or 0))}\n"
            f"Misklikken: {len(trial.get('miss_clicks', []))}"
        )

    def close_app(self) -> None:
        self.free_recording = False
        self._cancel_free_after()
        self.aim_active = False
        self.aim_generation += 1
        self._cancel_aim_after()
        self._stop_replay()
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()


if __name__ == "__main__":
    main()
