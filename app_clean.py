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

BG, PANEL, PANEL2, BORDER = "#0b1018", "#141b25", "#1a2330", "#2a3442"
TEXT, MUTED, PURPLE, GREEN, RED = "#f4f6fb", "#98a3b3", "#8b5cf6", "#3ccf78", "#d94b4b"
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = 1920.0, 1080.0
FRAME_MS, SAMPLE_MS = 16, 8


class Card(ctk.CTkFrame):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER, **kwargs)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"AI Mouse Lab v{__version__}")
        self.geometry("1380x840")
        self.minsize(1120, 700)
        self.configure(fg_color=BG)
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.buttons: dict[str, ctk.CTkButton] = {}

        self.aim_active = False
        self.aim_plan: list[dict[str, Any]] = []
        self.aim_trials: list[dict[str, Any]] = []
        self.aim_index = 0
        self.aim_points: list[dict[str, float]] = []
        self.aim_start = {"x": 960.0, "y": 540.0}
        self.aim_spawn = 0.0
        self.aim_click_down: float | None = None
        self.aim_after_id: str | None = None
        self.aim_session_folder: Path | None = None
        self.aim_overlay: ctk.CTkFrame | None = None
        self.aim_canvas: ctk.CTkCanvas | None = None
        self.aim_last_drawn = 0

        self.free_recording = False
        self.free_paused = False
        self.free_points: list[dict[str, float]] = []
        self.free_started = 0.0
        self.free_paused_total = 0.0
        self.free_pause_started = 0.0
        self.free_after_id: str | None = None
        self.free_last_drawn = 0

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
        ctk.CTkLabel(nav, text=f"v{__version__} · lokale Windows hub", text_color=MUTED, font=("Segoe UI", 11)).pack(anchor="w", padx=16, pady=(0, 18))
        for name in ("Free Record", "Aim Lab"):
            button = ctk.CTkButton(nav, text=name, anchor="w", height=42, fg_color="transparent", hover_color=PANEL2, command=lambda key=name: self.show(key))
            button.pack(fill="x", padx=10, pady=3)
            self.buttons[name] = button
        ctk.CTkLabel(nav, text="● Data blijft lokaal", text_color=GREEN, font=("Segoe UI", 11)).pack(side="bottom", anchor="w", padx=16, pady=18)

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
        head = ctk.CTkFrame(root, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(head, text=title, text_color=TEXT, font=("Segoe UI", 30, "bold")).pack(anchor="w")
        ctk.CTkLabel(head, text=subtitle, text_color=MUTED).pack(anchor="w")
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
            button = self.buttons.get(name)
            if button is not None:
                button.configure(fg_color=PURPLE if name == key else "transparent")
        self.pages[key].grid()
        if key == "Aim Lab":
            self.refresh_profile_status()
        elif key == "Results":
            self.refresh_results()

    def _page_free_record(self) -> None:
        body = self.page("Free Record", "Free Record", "Neem vrije muisbewegingen op buiten targets om je natuurlijke timing en routevorm te bewaren.")
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
        ctk.CTkLabel(side, text="Beweeg normaal over je scherm. Deze opname wordt apart opgeslagen en vervuilt je Aim Lab-profiel niet automatisch.", text_color=MUTED, justify="left", wraplength=245).pack(anchor="w", padx=18, pady=(0, 12))
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
        screen_w = max(1.0, float(self.winfo_screenwidth()))
        screen_h = max(1.0, float(self.winfo_screenheight()))
        for index in range(max(1, self.free_last_drawn), len(self.free_points)):
            a, b = self.free_points[index - 1], self.free_points[index]
            self.free_canvas.create_line(a["x"] / screen_w * width, a["y"] / screen_h * height, b["x"] / screen_w * width, b["y"] / screen_h * height, fill=PURPLE, width=2)
        self.free_last_drawn = len(self.free_points)

    def free_stop(self) -> None:
        if not self.free_recording:
            return
        self.free_recording = False
        if self.free_after_id:
            self.after_cancel(self.free_after_id)
            self.free_after_id = None
        duration = self.free_points[-1]["t_ms"] if self.free_points else 0.0
        path = RECORDINGS / f"free_{now_stamp()}.json"
        write_json(path, {"schema_version": 1, "coordinate_space": "global_screen", "screen": {"width": self.winfo_screenwidth(), "height": self.winfo_screenheight()}, "duration_ms": duration, "points": self.free_points, "created_at": datetime.now().isoformat()})
        self.free_start_btn.configure(state="normal")
        self.free_pause_btn.configure(state="disabled", text="⏸ Pauze")
        self.free_stop_btn.configure(state="disabled")
        self.free_status.configure(text=f"Opgeslagen\nPunten: {len(self.free_points)}\nDuur: {duration / 1000:.1f} s\n{path.name}")

    def _page_aim(self) -> None:
        body = self.page("Aim Lab", "Aim Lab", "Registreert de volledige beweging per target in een vaste virtuele arena van 1920 × 1080.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        preview = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        preview.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        preview.create_text(500, 300, text="Aim Lab opent fullscreen op dit scherm", fill=MUTED, font=("Segoe UI", 18, "bold"))
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
        self.compare_status = ctk.CTkLabel(side, text="Gebruikt je laatste voltooide Aim Lab-sessie.", text_color=MUTED, justify="left", wraplength=250)
        self.compare_status.pack(anchor="w", padx=18, pady=(0, 12))

    def start_aim(self) -> None:
        if self.aim_active:
            return
        self.aim_active = True
        self.aim_trials = []
        self.aim_index = 0
        self.aim_session_folder = AIM / now_stamp()
        self.aim_session_folder.mkdir(parents=True, exist_ok=True)
        self.start_btn.configure(state="disabled")
        self.aim_overlay = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.aim_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.aim_canvas = ctk.CTkCanvas(self.aim_overlay, bg=PANEL, highlightthickness=0)
        self.aim_canvas.pack(fill="both", expand=True)
        self.aim_canvas.bind("<ButtonPress-1>", self._aim_press)
        self.aim_canvas.bind("<ButtonRelease-1>", self._aim_release)
        self.bind("<Escape>", lambda _event: self.abort_aim())
        self.attributes("-fullscreen", True)
        self.update_idletasks()
        count = int(self.count_menu.get())
        self.aim_plan = []
        for index in range(count):
            radius = random.choice([12, 18, 26])
            self.aim_plan.append({"index": index, "x": random.randint(80 + radius, int(VIRTUAL_WIDTH - 80 - radius)), "y": random.randint(80 + radius, int(VIRTUAL_HEIGHT - 80 - radius)), "radius": radius})
        write_json(self.aim_session_folder / "plan.json", self.aim_plan)
        self._show_aim_target()
        self._aim_sample()

    def _canvas_box(self, canvas: ctk.CTkCanvas) -> tuple[float, float, float]:
        width = max(1.0, float(canvas.winfo_width()))
        height = max(1.0, float(canvas.winfo_height()))
        scale = min(width / VIRTUAL_WIDTH, height / VIRTUAL_HEIGHT)
        return scale, (width - VIRTUAL_WIDTH * scale) / 2.0, (height - VIRTUAL_HEIGHT * scale) / 2.0

    def _to_canvas(self, canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
        scale, ox, oy = self._canvas_box(canvas)
        return ox + x * scale, oy + y * scale

    def _to_virtual(self, canvas: ctk.CTkCanvas, x: float, y: float) -> tuple[float, float]:
        scale, ox, oy = self._canvas_box(canvas)
        return (x - ox) / max(scale, 1e-9), (y - oy) / max(scale, 1e-9)

    def _pointer_virtual(self) -> tuple[float, float]:
        if self.aim_canvas is None:
            return 0.0, 0.0
        sx, sy = self.winfo_pointerxy()
        return self._to_virtual(self.aim_canvas, sx - self.aim_canvas.winfo_rootx(), sy - self.aim_canvas.winfo_rooty())

    def _show_aim_target(self) -> None:
        if not self.aim_active or self.aim_canvas is None:
            return
        if self.aim_index >= len(self.aim_plan):
            self.finish_aim()
            return
        self.aim_canvas.delete("all")
        scale, ox, oy = self._canvas_box(self.aim_canvas)
        self.aim_canvas.create_rectangle(ox, oy, ox + VIRTUAL_WIDTH * scale, oy + VIRTUAL_HEIGHT * scale, outline=BORDER)
        target = self.aim_plan[self.aim_index]
        x, y = self._to_canvas(self.aim_canvas, target["x"], target["y"])
        radius = target["radius"] * scale
        self.aim_canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=PURPLE, outline="#c4b5fd", width=3)
        self.aim_canvas.create_text(x, y, text=str(self.aim_index + 1), fill="white")
        px, py = self._pointer_virtual()
        self.aim_start = {"x": px, "y": py}
        self.aim_points = [{"t_ms": 0.0, "x": px, "y": py}]
        self.aim_spawn = time.perf_counter()
        self.aim_click_down = None
        self.aim_last_drawn = 1

    def _aim_sample(self) -> None:
        if not self.aim_active:
            self.aim_after_id = None
            return
        x, y = self._pointer_virtual()
        t_ms = (time.perf_counter() - self.aim_spawn) * 1000.0
        self.aim_points.append({"t_ms": round(t_ms, 3), "x": round(x, 3), "y": round(y, 3)})
        self._draw_aim_trace()
        self.aim_after_id = self.after(SAMPLE_MS, self._aim_sample)

    def _draw_aim_trace(self) -> None:
        if self.aim_canvas is None or len(self.aim_points) < 2:
            return
        for index in range(max(1, self.aim_last_drawn), len(self.aim_points)):
            a, b = self.aim_points[index - 1], self.aim_points[index]
            ax, ay = self._to_canvas(self.aim_canvas, a["x"], a["y"])
            bx, by = self._to_canvas(self.aim_canvas, b["x"], b["y"])
            self.aim_canvas.create_line(ax, ay, bx, by, fill=PURPLE, width=2)
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
        click = {"down_t_ms": round(((self.aim_click_down or released) - self.aim_spawn) * 1000.0, 3), "up_t_ms": round((released - self.aim_spawn) * 1000.0, 3), "x": x, "y": y}
        target_data = {"index": self.aim_index, "x": target["x"], "y": target["y"], "radius": target["radius"]}
        try:
            derived = derive_trial(target_data, self.aim_start, self.aim_points, click)
        except (TypeError, ValueError, KeyError):
            return
        miss = math.hypot(x - target["x"], y - target["y"]) > target["radius"]
        self.aim_trials.append({"schema_version": 7, "target": target_data, "start": self.aim_start, "points": list(self.aim_points), "click": click, "miss_clicks": [click] if miss else [], "derived": derived, "capture_mode": "test" if self.capture_mode.get() == "Detectietest" else "normal"})
        self.aim_index += 1
        self._show_aim_target()

    def finish_aim(self) -> None:
        if not self.aim_active:
            return
        self.aim_active = False
        if self.aim_after_id:
            self.after_cancel(self.aim_after_id)
            self.aim_after_id = None
        folder = self.aim_session_folder or (AIM / now_stamp())
        write_json(folder / "trials.json", self.aim_trials)
        write_json(folder / "summary.json", {"schema_version": 7, "trial_count": len(self.aim_trials), "point_count": sum(len(trial["points"]) for trial in self.aim_trials), "miss_count": sum(len(trial.get("miss_clicks", [])) for trial in self.aim_trials), "created_at": datetime.now().isoformat()})
        self._close_aim_overlay()
        self.aim_status.configure(text=f"Klaar\n{len(self.aim_trials)} targets\n{sum(len(t.get('miss_clicks', [])) for t in self.aim_trials)} misses", text_color=GREEN)

    def abort_aim(self) -> None:
        if not self.aim_active:
            return
        self.aim_active = False
        if self.aim_after_id:
            self.after_cancel(self.aim_after_id)
            self.aim_after_id = None
        self._close_aim_overlay()
        self.aim_status.configure(text="Sessie afgebroken", text_color=RED)

    def _close_aim_overlay(self) -> None:
        self.attributes("-fullscreen", False)
        self.unbind("<Escape>")
        if self.aim_overlay is not None:
            self.aim_overlay.destroy()
            self.aim_overlay = None
        self.aim_canvas = None
        self.start_btn.configure(state="normal")
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
        except ValueError as exc:
            self.aim_status.configure(text=str(exc), text_color=RED)
        finally:
            self.profile_btn.configure(state="normal", text="Build Profile")

    def refresh_profile_status(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not isinstance(profile, dict) or not profile:
            self.profile_status.configure(text="Nog geen profiel gebouwd", text_color=MUTED)
            return
        strong = sum(1 for context in profile.get("contexts", {}).values() if int(context.get("trial_count", 0)) >= 8)
        self.profile_status.configure(text=f"Kwaliteit: {profile.get('quality_percent', 0)}%\nTargets: {profile.get('trial_count', 0)}\nSterke contexten: {strong}", text_color=GREEN)

    def test_latest_ab(self) -> None:
        self.compare_btn.configure(state="disabled", text="Vergelijking maken…")
        try:
            _folder, self.replay_a, self.replay_b = create_latest_comparison()
            self.replay_index = 0
            self.replay_elapsed = 0.0
            self.replay_finished = False
            count = min(len(self.replay_a["trials"]), len(self.replay_b["trials"]))
            self.compare_status.configure(text=f"Klaar · {count} targets · replay geopend", text_color=GREEN)
            self.show("Results")
        except ValueError as exc:
            self.compare_status.configure(text=str(exc), text_color=RED)
        finally:
            self.compare_btn.configure(state="normal", text="Test nieuwste opname A/B")

    def _page_results(self) -> None:
        body = self.page("Results", "Results", "A en B simultaan over elkaar in dezelfde 1920 × 1080 arena als Aim Lab.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)
        controls = Card(body)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 10))
        controls.grid_columnconfigure(6, weight=1)
        ctk.CTkButton(controls, text="← Vorige", width=92, fg_color=PANEL2, command=lambda: self.replay_change(-1)).grid(row=0, column=0, padx=(14, 6), pady=12)
        self.replay_play_btn = ctk.CTkButton(controls, text="▶ Alles afspelen", width=105, fg_color=PURPLE, command=self.replay_toggle)
        self.replay_play_btn.grid(row=0, column=1, padx=6, pady=12)
        ctk.CTkButton(controls, text="Volgende →", width=98, fg_color=PANEL2, command=lambda: self.replay_change(1)).grid(row=0, column=2, padx=6, pady=12)
        self.replay_speed = ctk.CTkOptionMenu(controls, values=["0.5x", "1x", "2x"], width=85, fg_color=PANEL2, button_color=PURPLE)
        self.replay_speed.set("1x")
        self.replay_speed.grid(row=0, column=3, padx=(18, 6), pady=12)
        self.replay_equal = ctk.CTkCheckBox(controls, text="Gelijke duur", text_color=MUTED, command=self.replay_reset)
        self.replay_equal.grid(row=0, column=4, padx=12, pady=12)
        self.replay_label = ctk.CTkLabel(controls, text="Nog geen A/B-vergelijking", text_color=TEXT, font=("Segoe UI", 14, "bold"))
        self.replay_label.grid(row=0, column=6, sticky="e", padx=16)
        arena = Card(body)
        arena.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        self.replay_canvas = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        self.replay_canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        side = Card(body)
        side.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="A · PAARS", text_color=PURPLE, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        self.stats_a = ctk.CTkLabel(side, text="", text_color=MUTED, justify="left", wraplength=260)
        self.stats_a.pack(anchor="w", padx=18, pady=(0, 16))
        ctk.CTkLabel(side, text="B · GROEN", text_color=GREEN, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(4, 4))
        self.stats_b = ctk.CTkLabel(side, text="", text_color=MUTED, justify="left", wraplength=260)
        self.stats_b.pack(anchor="w", padx=18, pady=(0, 16))
        ctk.CTkLabel(side, text="Beide routes gebruiken exact dezelfde virtuele arena en targetpositie.", text_color=MUTED, justify="left", wraplength=250).pack(anchor="w", padx=18, pady=12)

    def refresh_results(self) -> None:
        if not normalize_trials(self.replay_a) or not normalize_trials(self.replay_b):
            _folder, self.replay_a, self.replay_b = latest_comparison()
        self.replay_a = {**self.replay_a, "trials": normalize_trials(self.replay_a)} if isinstance(self.replay_a, dict) else {}
        self.replay_b = {**self.replay_b, "trials": normalize_trials(self.replay_b)} if isinstance(self.replay_b, dict) else {}
        count = self._replay_count()
        self.replay_label.configure(text="Nog geen A/B-vergelijking" if count == 0 else f"Laatste Aim Lab-opname · {count} targets")
        if count:
            self.replay_index = min(self.replay_index, count - 1)
        self.replay_draw(self.replay_elapsed)

    def _replay_count(self) -> int:
        a = self.replay_a.get("trials", []) if isinstance(self.replay_a, dict) else []
        b = self.replay_b.get("trials", []) if isinstance(self.replay_b, dict) else []
        return min(len(a), len(b))

    def _replay_trials(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return self.replay_a.get("trials", []), self.replay_b.get("trials", [])

    def _replay_speed_value(self) -> float:
        return float(self.replay_speed.get().replace("x", ""))

    def _replay_duration(self) -> float:
        trials_a, trials_b = self._replay_trials()
        if not trials_a or not trials_b:
            return 0.0
        return max(16.0, trial_duration_ms(trials_a[self.replay_index]), trial_duration_ms(trials_b[self.replay_index]))

    def replay_toggle(self) -> None:
        if self._replay_count() == 0:
            self.replay_label.configure(text="Geen geldige A/B-data geladen", text_color=RED)
            return
        if self.replay_running:
            self.replay_elapsed += (time.perf_counter() - self.replay_started) * 1000.0 * self._replay_speed_value()
            self.replay_running = False
            self._cancel_replay_after()
            self.replay_play_btn.configure(text="▶ Verder afspelen")
            return
        if self.replay_finished:
            self.replay_index = 0
            self.replay_elapsed = 0.0
            self.replay_finished = False
        self.replay_started = time.perf_counter()
        self.replay_running = True
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
            self.replay.draw(0.0)
            self.replay_after_id = self.after(FRAME_MS, self._replay_tick)
            return
        self.replay_elapsed = duration
        self.replay_running = False
        self.replay_finished = True
        self.replay_after_id = None
        self.replay_play_btn.configure(text="↻ Opnieuw afspelen")
        self.replay_label.configure(text=f"Klaar · {self._replay_count()}/{self._replay_count()} targets afgespeeld", text_color=TEXT)

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

    def replay_reset(self) -> None:
        self._stop_replay()
        self.replay_finished = False
        self.replay_elapsed = 0.0
        self.replay_play_btn.configure(text="▶ Alles afspelen")
        self.replay_draw(0.0)

    def _stop_replay(self) -> None:
        self.replay_running = False
        self._cancel_replay_after()

    def _cancel_replay_after(self) -> None:
        if self.replay_after_id:
            try:
                self.after_cancel(self.replay_after_id)
            except Exception:
                pass
            self.replay_after_id = None

    def replay_draw(self, elapsed: float) -> None:
        canvas = self.replay_canvas
        canvas.delete("all")
        trials_a, trials_b = self._replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            canvas.create_text(max(1, canvas.winfo_width()) / 2, max(1, canvas.winfo_height()) / 2, text="Nog geen A/B-vergelijking", fill=MUTED, font=("Segoe UI", 18, "bold"))
            self.stats_a.configure(text="")
            self.stats_b.configure(text="")
            return
        index = max(0, min(count - 1, self.replay_index))
        a, b = trials_a[index], trials_b[index]
        duration_a, duration_b = trial_duration_ms(a), trial_duration_ms(b)
        if self.replay_equal.get():
            common = max(duration_a, duration_b, 1.0)
            elapsed_a = min(duration_a, elapsed / common * duration_a)
            elapsed_b = min(duration_b, elapsed / common * duration_b)
        else:
            elapsed_a, elapsed_b = min(duration_a, elapsed), min(duration_b, elapsed)
        scale, ox, oy = self._canvas_box(canvas)
        canvas.create_rectangle(ox, oy, ox + VIRTUAL_WIDTH * scale, oy + VIRTUAL_HEIGHT * scale, outline=BORDER)
        target = a.get("target", {})
        tx, ty = self._to_canvas(canvas, float(target.get("x", 0)), float(target.get("y", 0)))
        radius = float(target.get("radius", 26)) * scale
        canvas.create_oval(tx - radius, ty - radius, tx + radius, ty + radius, outline="white", width=2)
        canvas.create_text(tx, ty, text=str(index + 1), fill="white")
        self._draw_route(canvas, visible_points(a, elapsed_a), PURPLE)
        self._draw_route(canvas, visible_points(b, elapsed_b), GREEN)
        self.stats_a.configure(text=self._stats_text(a))
        self.stats_b.configure(text=self._stats_text(b))
        self.replay_label.configure(text=f"Target {index + 1}/{count}", text_color=TEXT)

    def _draw_route(self, canvas: ctk.CTkCanvas, points: list[dict[str, float]], color: str) -> None:
        if not points:
            return
        coords: list[float] = []
        for point in points:
            x, y = self._to_canvas(canvas, point["x"], point["y"])
            coords.extend((x, y))
        if len(coords) >= 4:
            canvas.create_line(*coords, fill=color, width=3, smooth=True)
        x, y = coords[-2], coords[-1]
        canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="white", width=1)

    @staticmethod
    def _stats_text(trial: dict[str, Any]) -> str:
        derived = trial.get("derived", {})
        if not isinstance(derived, dict):
            derived = {}
        return (f"Reactie: {float(derived.get('reaction_ms', 0) or 0):.0f} ms\n" f"Beweging: {float(derived.get('movement_time_ms', 0) or 0):.0f} ms\n" f"Efficiëntie: {float(derived.get('path_efficiency', 0) or 0):.3f}\n" f"Overshoot: {float(derived.get('overshoot_px', 0) or 0):.1f} px\n" f"Correcties: {int(float(derived.get('correction_count', 0) or 0))}\n" f"Misklikken: {len(trial.get('miss_clicks', []))}")


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()


if __name__ == "__main__":
    main()
