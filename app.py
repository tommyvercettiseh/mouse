from __future__ import annotations

import json
import math
import os
import random
import statistics
import threading
import time
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk
from pynput import mouse
from screeninfo import get_monitors

APP_NAME = "AI Mouse Lab"
VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RECORDINGS = DATA / "recordings"
AIM = DATA / "aim_lab"
PROFILES = DATA / "profiles"
BENCHMARKS = DATA / "benchmarks"
for folder in (RECORDINGS, AIM, PROFILES, BENCHMARKS):
    folder.mkdir(parents=True, exist_ok=True)

BG = "#0b1018"
SURFACE = "#141b25"
SURFACE_2 = "#1a2330"
BORDER = "#2a3442"
TEXT = "#f4f6fb"
MUTED = "#98a3b3"
PURPLE = "#8b5cf6"
PURPLE_2 = "#6d44d8"
RED = "#d94b4b"
GREEN = "#3ccf78"


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def write_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


class Recorder:
    def __init__(self, event_callback) -> None:
        self.callback = event_callback
        self.listener: mouse.Listener | None = None
        self.running = False
        self.started = 0.0
        self.events: list[dict[str, Any]] = []
        self.counts: Counter[str] = Counter()
        self._down: dict[str, tuple[float, int, int]] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        if self.running:
            return
        self.events = []
        self.counts.clear()
        self._down.clear()
        self.started = time.perf_counter()
        self.running = True
        self.listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self.listener.start()

    def _emit(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.events.append(event)
        self.counts[event["type"]] += 1
        self.callback(event)

    def _t(self) -> float:
        return round(time.perf_counter() - self.started, 6)

    def _on_move(self, x: int, y: int) -> None:
        if not self.running:
            return
        self._emit({"type": "move", "t": self._t(), "x": int(x), "y": int(y)})

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not self.running:
            return
        name = str(button).split(".")[-1]
        hold_ms = None
        if pressed:
            self._down[name] = (time.perf_counter(), int(x), int(y))
        else:
            start = self._down.pop(name, None)
            if start:
                hold_ms = round((time.perf_counter() - start[0]) * 1000, 3)
        self._emit({
            "type": "click",
            "t": self._t(),
            "x": int(x),
            "y": int(y),
            "button": name,
            "pressed": bool(pressed),
            "hold_ms": hold_ms,
        })

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self.running:
            return
        self._emit({
            "type": "scroll",
            "t": self._t(),
            "x": int(x),
            "y": int(y),
            "dx": int(dx),
            "dy": int(dy),
        })

    def stop(self) -> Path | None:
        if not self.running:
            return None
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        folder = RECORDINGS / now_stamp()
        folder.mkdir(parents=True, exist_ok=True)
        duration = round(time.perf_counter() - self.started, 3)
        write_json(folder / "events.json", self.events)
        write_json(folder / "summary.json", {
            "schema_version": 1,
            "duration_s": duration,
            "event_count": len(self.events),
            "event_types": dict(self.counts),
            "created_at": datetime.now().isoformat(),
        })
        return folder


class MonitorCanvas(ctk.CTkCanvas):
    def __init__(self, master) -> None:
        super().__init__(master, bg=SURFACE, highlightthickness=0)
        self.monitors = get_monitors()
        self.trace: deque[tuple[float, float, float]] = deque(maxlen=180)
        self.cursor: tuple[float, float] | None = None
        self.bind("<Configure>", lambda _e: self.redraw())

    def add_point(self, x: float, y: float) -> None:
        self.cursor = (x, y)
        self.trace.append((time.perf_counter(), x, y))
        self.redraw()

    def bounds(self) -> tuple[int, int, int, int]:
        left = min(m.x for m in self.monitors)
        top = min(m.y for m in self.monitors)
        right = max(m.x + m.width for m in self.monitors)
        bottom = max(m.y + m.height for m in self.monitors)
        return left, top, right, bottom

    def map_point(self, x: float, y: float) -> tuple[float, float]:
        left, top, right, bottom = self.bounds()
        w = max(1, self.winfo_width() - 60)
        h = max(1, self.winfo_height() - 60)
        scale = min(w / max(1, right - left), h / max(1, bottom - top))
        ox = (self.winfo_width() - (right - left) * scale) / 2
        oy = (self.winfo_height() - (bottom - top) * scale) / 2
        return ox + (x - left) * scale, oy + (y - top) * scale

    def redraw(self) -> None:
        self.delete("all")
        for index, monitor in enumerate(self.monitors, start=1):
            x1, y1 = self.map_point(monitor.x, monitor.y)
            x2, y2 = self.map_point(monitor.x + monitor.width, monitor.y + monitor.height)
            self.create_rectangle(x1, y1, x2, y2, outline=BORDER, width=2, fill=SURFACE_2)
            self.create_text((x1+x2)/2, y2-18, text=str(index), fill=MUTED, font=("Segoe UI", 10))
        points = list(self.trace)
        if len(points) > 1:
            now = time.perf_counter()
            coords: list[float] = []
            for stamp, x, y in points:
                if now - stamp <= 1.6:
                    px, py = self.map_point(x, y)
                    coords.extend([px, py])
            if len(coords) >= 4:
                self.create_line(*coords, fill=PURPLE, width=2, smooth=True)
        if self.cursor:
            x, y = self.map_point(*self.cursor)
            self.create_oval(x-7, y-7, x+7, y+7, fill=PURPLE, outline="")
            self.create_oval(x-15, y-15, x+15, y+15, outline=PURPLE_2, width=2)


class Card(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER, **kwargs)


class Hub(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("1440x860")
        self.minsize(1180, 720)
        self.configure(fg_color=BG)
        self.recorder = Recorder(self.on_record_event)
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.nav: dict[str, ctk.CTkButton] = {}
        self.record_started = 0.0
        self.event_queue: deque[dict[str, Any]] = deque()
        self.aim_active = False
        self.aim_plan: list[dict[str, Any]] = []
        self.aim_index = 0
        self.aim_trial_start = 0.0
        self.aim_start_point: tuple[int, int] | None = None
        self.aim_trials: list[dict[str, Any]] = []
        self._build_shell()
        self.show_page("Dashboard")
        self.after(16, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=245, fg_color="#0d131d", corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text="⌁  AI Mouse Lab", text_color=TEXT, font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=22, pady=(24, 2))
        ctk.CTkLabel(sidebar, text=f"v{VERSION} · één lokale hub", text_color=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=22, pady=(0, 24))
        for name in ("Dashboard", "Free Record", "Aim Lab", "Build Profile", "Benchmark", "Results", "Profiles", "Settings"):
            button = ctk.CTkButton(
                sidebar, text=name, height=44, anchor="w", corner_radius=11,
                fg_color="transparent", hover_color=SURFACE_2,
                command=lambda value=name: self.show_page(value),
            )
            button.pack(fill="x", padx=14, pady=4)
            self.nav[name] = button
        ctk.CTkLabel(sidebar, text="● Apparaat verbonden", text_color=GREEN, font=("Segoe UI", 10)).pack(side="bottom", anchor="w", padx=22, pady=(0, 8))
        ctk.CTkLabel(sidebar, text="Alle data blijft lokaal", text_color=MUTED, font=("Segoe UI", 9)).pack(side="bottom", anchor="w", padx=22, pady=(0, 6))
        self.host = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.host.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.host.grid_rowconfigure(0, weight=1)
        self.host.grid_columnconfigure(0, weight=1)
        self._make_dashboard()
        self._make_free_record()
        self._make_aim_lab()
        self._make_profile()
        self._make_benchmark()
        self._make_results()
        self._make_simple_page("Profiles", "Profielen", "Beheer lokale gedragsprofielen. In v0.1.0 wordt één standaardprofiel gebruikt.")
        self._make_simple_page("Settings", "Instellingen", "Schermindeling en recorderinformatie worden automatisch uit Windows gelezen.")

    def page(self, name: str, title: str, subtitle: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        root = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        root.grid(row=0, column=0, sticky="nsew")
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(4, 16))
        ctk.CTkLabel(header, text=title, text_color=TEXT, font=("Segoe UI", 30, "bold")).pack(anchor="w")
        ctk.CTkLabel(header, text=subtitle, text_color=MUTED, font=("Segoe UI", 12)).pack(anchor="w", pady=(2, 0))
        body = ctk.CTkFrame(root, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        self.pages[name] = root
        return root, body

    def show_page(self, name: str) -> None:
        for key, page in self.pages.items():
            page.grid_remove()
            self.nav[key].configure(fg_color=PURPLE_2 if key == name else "transparent")
        self.pages[name].grid()

    def _make_dashboard(self) -> None:
        _, body = self.page("Dashboard", "Dashboard", "Overzicht van je muisgedrag en benchmarkstatus.")
        body.grid_columnconfigure((0,1,2,3), weight=1)
        profile = read_json(PROFILES / "master_profile.json", {})
        cards = [
            ("Profielkwaliteit", f"{profile.get('quality_percent', 0)}%"),
            ("Opnames", str(len(list(RECORDINGS.glob('*'))))),
            ("Aim Lab targets", str(sum(len(read_json(p / 'trials.json', [])) for p in AIM.glob('*') if p.is_dir()))),
            ("Benchmarks", str(len(list(BENCHMARKS.glob('*'))))),
        ]
        for col, (label, value) in enumerate(cards):
            card = Card(body)
            card.grid(row=0, column=col, sticky="ew", padx=6, pady=6)
            ctk.CTkLabel(card, text=label, text_color=MUTED, font=("Segoe UI", 11)).pack(anchor="w", padx=18, pady=(16,4))
            ctk.CTkLabel(card, text=value, text_color=PURPLE, font=("Segoe UI", 28, "bold")).pack(anchor="w", padx=18, pady=(0,16))
        info = Card(body)
        info.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=6, pady=(12,6))
        body.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(info, text="Eén hub, drie stappen", text_color=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(22,8))
        ctk.CTkLabel(info, text="1. Verzamel natuurlijke data in Free Record\n2. Meet doelgericht gedrag in Aim Lab\n3. Bouw je profiel en test mens versus profiel in Benchmark", text_color=MUTED, justify="left", font=("Segoe UI", 14)).pack(anchor="w", padx=22, pady=(0,22))

    def _make_free_record(self) -> None:
        _, body = self.page("Free Record", "Free Record", "Neem je muisgedrag op tijdens normaal gebruik.")
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)
        stats = Card(body)
        stats.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        self.record_status = ctk.CTkLabel(stats, text="● Klaar", text_color=GREEN, font=("Segoe UI", 12, "bold"))
        self.record_status.pack(side="left", padx=18, pady=18)
        self.record_timer = ctk.CTkLabel(stats, text="00:00:00", text_color=TEXT, font=("Segoe UI", 26, "bold"))
        self.record_timer.pack(side="left", padx=24)
        self.record_counts = ctk.CTkLabel(stats, text="0 events · 0 kliks · 0 scrolls", text_color=MUTED, font=("Segoe UI", 12))
        self.record_counts.pack(side="left", padx=18)
        self.record_xy = ctk.CTkLabel(stats, text="X 0 · Y 0", text_color=MUTED, font=("Segoe UI", 12))
        self.record_xy.pack(side="right", padx=18)
        left = Card(body)
        left.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Live weergave van je schermen", text_color=TEXT, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(18,8))
        self.monitor_canvas = MonitorCanvas(left)
        self.monitor_canvas.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)
        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(8,14))
        actions.grid_columnconfigure((0,1), weight=1)
        self.start_record_btn = ctk.CTkButton(actions, text="Start opname", fg_color=PURPLE, height=48, command=self.start_recording)
        self.start_record_btn.grid(row=0, column=0, sticky="ew", padx=(0,6))
        self.stop_record_btn = ctk.CTkButton(actions, text="Stop opname", fg_color=RED, height=48, command=self.stop_recording, state="disabled")
        self.stop_record_btn.grid(row=0, column=1, sticky="ew", padx=(6,0))
        recent = Card(body)
        recent.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(recent, text="Recente sessies", text_color=TEXT, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(18,8))
        self.recent_recordings = ctk.CTkLabel(recent, text=self._recent_text(RECORDINGS), text_color=MUTED, justify="left", font=("Consolas", 11))
        self.recent_recordings.pack(anchor="w", padx=18, pady=8)
        ctk.CTkButton(recent, text="Open opnamemap", fg_color=SURFACE_2, command=lambda: os.startfile(RECORDINGS)).pack(side="bottom", fill="x", padx=16, pady=16)

    def _recent_text(self, root: Path) -> str:
        folders = sorted((p for p in root.glob('*') if p.is_dir()), reverse=True)[:6]
        return "Nog geen sessies" if not folders else "\n\n".join(p.name for p in folders)

    def start_recording(self) -> None:
        self.recorder.start()
        self.record_started = time.perf_counter()
        self.record_status.configure(text="● Opname actief", text_color=RED)
        self.start_record_btn.configure(state="disabled")
        self.stop_record_btn.configure(state="normal")
        self._tick_recording()

    def stop_recording(self) -> None:
        folder = self.recorder.stop()
        self.record_status.configure(text=f"● Opgeslagen: {folder.name if folder else ''}", text_color=GREEN)
        self.start_record_btn.configure(state="normal")
        self.stop_record_btn.configure(state="disabled")
        self.recent_recordings.configure(text=self._recent_text(RECORDINGS))

    def on_record_event(self, event: dict[str, Any]) -> None:
        self.event_queue.append(event)

    def _tick_recording(self) -> None:
        if not self.recorder.running:
            return
        elapsed = int(time.perf_counter() - self.record_started)
        h, rest = divmod(elapsed, 3600)
        m, s = divmod(rest, 60)
        self.record_timer.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        counts = self.recorder.counts
        self.record_counts.configure(text=f"{sum(counts.values()):,} events · {counts['click']:,} kliks · {counts['scroll']:,} scrolls".replace(',', '.'))
        self.after(250, self._tick_recording)

    def _make_aim_lab(self) -> None:
        _, body = self.page("Aim Lab", "Aim Lab", "Meet gericht gedrag op gecontroleerde targets.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        arena_card = Card(body)
        arena_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena_card.grid_rowconfigure(0, weight=1)
        arena_card.grid_columnconfigure(0, weight=1)
        self.aim_canvas = ctk.CTkCanvas(arena_card, bg=SURFACE, highlightthickness=0)
        self.aim_canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.aim_canvas.bind("<Button-1>", self._aim_click)
        panel = Card(body)
        panel.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(panel, text="Sessie instellingen", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18,12))
        self.aim_count = ctk.CTkOptionMenu(panel, values=["20", "50", "100"], fg_color=SURFACE_2, button_color=PURPLE_2)
        self.aim_count.set("20")
        self.aim_count.pack(fill="x", padx=18, pady=8)
        ctk.CTkLabel(panel, text="Gemengde afstanden en targetgroottes", text_color=MUTED, wraplength=230, justify="left").pack(anchor="w", padx=18, pady=8)
        self.aim_button = ctk.CTkButton(panel, text="Start sessie", fg_color=PURPLE, height=48, command=self.start_aim)
        self.aim_button.pack(fill="x", padx=18, pady=12)
        self.aim_stats = ctk.CTkLabel(panel, text="Nog geen actieve sessie", text_color=MUTED, justify="left")
        self.aim_stats.pack(anchor="w", padx=18, pady=12)

    def start_aim(self) -> None:
        count = int(self.aim_count.get())
        w = max(600, self.aim_canvas.winfo_width())
        h = max(400, self.aim_canvas.winfo_height())
        self.aim_plan = []
        for index in range(count):
            radius = random.choice([12, 18, 26])
            self.aim_plan.append({"index": index, "x": random.randint(70, w-70), "y": random.randint(70, h-70), "radius": radius})
        self.aim_index = 0
        self.aim_trials = []
        self.aim_active = True
        self.aim_button.configure(state="disabled")
        self._show_target()

    def _show_target(self) -> None:
        self.aim_canvas.delete("all")
        if self.aim_index >= len(self.aim_plan):
            self._finish_aim()
            return
        target = self.aim_plan[self.aim_index]
        x, y, r = target["x"], target["y"], target["radius"]
        self.aim_canvas.create_oval(x-r, y-r, x+r, y+r, fill=PURPLE, outline="#bba5ff", width=3, tags="target")
        self.aim_canvas.create_text(x, y, text=str(self.aim_index + 1), fill="white", font=("Segoe UI", 10, "bold"))
        self.aim_trial_start = time.perf_counter()
        self.aim_start_point = self.winfo_pointerxy()
        self.aim_stats.configure(text=f"Target {self.aim_index + 1} van {len(self.aim_plan)}")

    def _aim_click(self, event) -> None:
        if not self.aim_active:
            return
        target = self.aim_plan[self.aim_index]
        dx = event.x - target["x"]
        dy = event.y - target["y"]
        hit = math.hypot(dx, dy) <= target["radius"]
        if not hit:
            return
        elapsed_ms = round((time.perf_counter() - self.aim_trial_start) * 1000, 3)
        sx, sy = self.aim_start_point or (event.x, event.y)
        distance = round(math.hypot(target["x"] - sx, target["y"] - sy), 3)
        self.aim_trials.append({
            **target,
            "start_x": sx,
            "start_y": sy,
            "click_x": event.x,
            "click_y": event.y,
            "movement_time_ms": elapsed_ms,
            "distance_px": distance,
            "click_error_px": round(math.hypot(dx, dy), 3),
        })
        self.aim_index += 1
        self._show_target()

    def _finish_aim(self) -> None:
        self.aim_active = False
        self.aim_button.configure(state="normal")
        folder = AIM / now_stamp()
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / "plan.json", self.aim_plan)
        write_json(folder / "trials.json", self.aim_trials)
        avg = statistics.fmean(t["movement_time_ms"] for t in self.aim_trials) if self.aim_trials else 0
        self.aim_stats.configure(text=f"Klaar · {len(self.aim_trials)} targets\nGem. bewegingstijd: {avg:.0f} ms")
        self.aim_canvas.delete("all")
        self.aim_canvas.create_text(self.aim_canvas.winfo_width()/2, self.aim_canvas.winfo_height()/2, text="Sessie opgeslagen", fill=GREEN, font=("Segoe UI", 22, "bold"))

    def _make_profile(self) -> None:
        _, body = self.page("Build Profile", "Build Profile", "Bouw één transparant profiel uit al je lokale sessies.")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        left = Card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.profile_quality = ctk.CTkLabel(left, text="0%", text_color=PURPLE, font=("Segoe UI", 54, "bold"))
        self.profile_quality.pack(pady=(70,8))
        ctk.CTkLabel(left, text="Profielkwaliteit", text_color=MUTED, font=("Segoe UI", 13)).pack()
        ctk.CTkButton(left, text="Profiel opnieuw bouwen", fg_color=PURPLE, height=48, command=self.build_profile).pack(side="bottom", fill="x", padx=18, pady=18)
        right = Card(body)
        right.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(right, text="Profielkenmerken", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18,12))
        self.profile_text = ctk.CTkLabel(right, text="Nog geen profiel gebouwd", text_color=MUTED, justify="left", font=("Consolas", 12))
        self.profile_text.pack(anchor="w", padx=18, pady=8)
        self._load_profile_view()

    def build_profile(self) -> None:
        trials: list[dict[str, Any]] = []
        for folder in AIM.glob('*'):
            if folder.is_dir():
                trials.extend(read_json(folder / "trials.json", []))
        holds: list[float] = []
        for folder in RECORDINGS.glob('*'):
            if folder.is_dir():
                for event in read_json(folder / "events.json", []):
                    if event.get("type") == "click" and event.get("hold_ms") is not None:
                        holds.append(float(event["hold_ms"]))
        movement = [float(t["movement_time_ms"]) for t in trials]
        errors = [float(t["click_error_px"]) for t in trials]
        distances = [float(t["distance_px"]) for t in trials]
        quality = min(100, int((len(trials) / 300) * 70 + (len(holds) / 300) * 30))
        profile = {
            "schema_version": 1,
            "quality_percent": quality,
            "trial_count": len(trials),
            "click_count": len(holds),
            "movement_time_ms": self._stats(movement),
            "click_error_px": self._stats(errors),
            "distance_px": self._stats(distances),
            "click_hold_ms": self._stats(holds),
            "created_at": datetime.now().isoformat(),
        }
        write_json(PROFILES / "master_profile.json", profile)
        self._load_profile_view()

    def _stats(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {"mean": 0, "median": 0, "stdev": 0, "min": 0, "max": 0}
        return {
            "mean": round(statistics.fmean(values), 3),
            "median": round(statistics.median(values), 3),
            "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0,
            "min": round(min(values), 3),
            "max": round(max(values), 3),
        }

    def _load_profile_view(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        q = int(profile.get("quality_percent", 0))
        self.profile_quality.configure(text=f"{q}%")
        if not profile:
            self.profile_text.configure(text="Nog geen profiel gebouwd")
            return
        self.profile_text.configure(text=(
            f"Aim Lab targets       {profile.get('trial_count', 0)}\n"
            f"Klikken               {profile.get('click_count', 0)}\n\n"
            f"Bewegingstijd mediaan {profile['movement_time_ms']['median']} ms\n"
            f"Klikfout mediaan      {profile['click_error_px']['median']} px\n"
            f"Klikduur mediaan      {profile['click_hold_ms']['median']} ms\n"
        ))

    def _make_benchmark(self) -> None:
        _, body = self.page("Benchmark", "Benchmark", "Vergelijk jouw sessie met een visuele profielsimulatie op exact hetzelfde plan.")
        body.grid_columnconfigure((0,1,2), weight=1)
        settings = Card(body)
        settings.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(settings, text="Benchmark instellingen", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18,12))
        self.bench_count = ctk.CTkOptionMenu(settings, values=["20", "50", "100"], fg_color=SURFACE_2, button_color=PURPLE_2)
        self.bench_count.set("20")
        self.bench_count.pack(fill="x", padx=18, pady=8)
        ctk.CTkButton(settings, text="Benchmark voorbereiden", fg_color=PURPLE, height=48, command=self.prepare_benchmark).pack(fill="x", padx=18, pady=12)
        status = Card(body)
        status.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(status, text="Status", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18,12))
        self.bench_status = ctk.CTkLabel(status, text="Nog geen benchmark voorbereid", text_color=MUTED, justify="left", wraplength=260)
        self.bench_status.pack(anchor="w", padx=18, pady=8)
        files = Card(body)
        files.grid(row=0, column=2, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(files, text="Blinde bestanden", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18,12))
        self.bench_files = ctk.CTkLabel(files, text="A.json\nB.json\nprivate_answer.json", text_color=MUTED, justify="left")
        self.bench_files.pack(anchor="w", padx=18, pady=8)
        ctk.CTkButton(files, text="Open benchmarkmap", fg_color=SURFACE_2, command=lambda: os.startfile(BENCHMARKS)).pack(side="bottom", fill="x", padx=16, pady=16)

    def prepare_benchmark(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            self.bench_status.configure(text="Bouw eerst een profiel.", text_color=RED)
            return
        count = int(self.bench_count.get())
        folder = BENCHMARKS / now_stamp()
        folder.mkdir(parents=True, exist_ok=True)
        plan = []
        for index in range(count):
            plan.append({
                "index": index,
                "start": [random.randint(120, 900), random.randint(120, 600)],
                "target": [random.randint(120, 900), random.randint(120, 600)],
                "radius": random.choice([12, 18, 26]),
            })
        generated = []
        median_ms = max(80.0, float(profile["movement_time_ms"].get("median", 300)))
        stdev_ms = max(15.0, float(profile["movement_time_ms"].get("stdev", 50)))
        error_sd = max(1.0, float(profile["click_error_px"].get("stdev", 3)))
        for item in plan:
            sx, sy = item["start"]
            tx, ty = item["target"]
            duration = max(60.0, random.gauss(median_ms, stdev_ms))
            points = []
            steps = max(12, int(duration / 8))
            bend = random.gauss(0, max(4, math.hypot(tx-sx, ty-sy) * 0.035))
            for step in range(steps + 1):
                u = step / steps
                smooth = 10*u**3 - 15*u**4 + 6*u**5
                x = sx + (tx-sx)*smooth
                y = sy + (ty-sy)*smooth + math.sin(math.pi*u)*bend
                points.append({"t_ms": round(u*duration, 3), "x": round(x, 3), "y": round(y, 3)})
            generated.append({
                **item,
                "movement_time_ms": round(duration, 3),
                "click_x": round(tx + random.gauss(0, error_sd), 3),
                "click_y": round(ty + random.gauss(0, error_sd), 3),
                "points": points,
            })
        write_json(folder / "benchmark_plan.json", plan)
        write_json(folder / "generated_pending.json", generated)
        write_json(folder / "README.json", {
            "next_step": "Run dezelfde targetreeks als mens in een volgende versie van de benchmarkrunner. Daarna worden human en generated blind als A/B toegewezen.",
            "note": "v0.1.0 genereert het plan en de visuele profielsimulatie, maar bestuurt geen externe muis.",
        })
        self.bench_status.configure(text=f"Plan met {count} targets aangemaakt.\nProfielsimulatie opgeslagen.\nMap: {folder.name}", text_color=GREEN)

    def _make_results(self) -> None:
        _, body = self.page("Results", "Results", "Analyseer later waarom A of B waarschijnlijk menselijker was.")
        card = Card(body)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(card, text="Benchmarkanalyse", text_color=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=22, pady=(22,8))
        ctk.CTkLabel(card, text="Upload A.json en B.json later samen in ChatGPT. De app bewaart het antwoord apart zodat de beoordeling blind blijft.\n\nIn v0.1.0 toont deze pagina alleen de lokale workflow; automatische classificatie volgt pas nadat echte benchmarksets beschikbaar zijn.", text_color=MUTED, justify="left", wraplength=760, font=("Segoe UI", 13)).pack(anchor="w", padx=22, pady=8)

    def _make_simple_page(self, key: str, title: str, text: str) -> None:
        _, body = self.page(key, title, text)
        card = Card(body)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(card, text=text, text_color=MUTED, wraplength=720, font=("Segoe UI", 14)).pack(anchor="w", padx=22, pady=22)

    def _poll(self) -> None:
        while self.event_queue:
            event = self.event_queue.popleft()
            if event.get("type") in {"move", "click", "scroll"}:
                x = float(event.get("x", 0))
                y = float(event.get("y", 0))
                self.monitor_canvas.add_point(x, y)
                self.record_xy.configure(text=f"X {int(x)} · Y {int(y)}")
        self.after(16, self._poll)

    def _close(self) -> None:
        self.recorder.stop()
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    Hub().mainloop()


if __name__ == "__main__":
    main()
