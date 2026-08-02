from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import math
import os
import random
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_mouse_lab.continuous_generator import simulate
from ai_mouse_lab.storage import PROFILES, read_json

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "data" / "live_tests"
PROFILE_PATH = PROFILES / "master_profile.json"
VIRTUAL_WIDTH = 1920.0
VIRTUAL_HEIGHT = 1080.0
TRANSPARENT = "#010203"
TARGET_COUNT = 10
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

if os.name == "nt":
    user32 = ctypes.windll.user32
    winmm = ctypes.windll.winmm
else:
    user32 = None
    winmm = None


def _require_windows() -> None:
    if user32 is None or winmm is None:
        raise RuntimeError("Deze transparante desktoptest werkt alleen op Windows.")


def _set_cursor(x: float, y: float) -> None:
    _require_windows()
    user32.SetCursorPos(int(round(x)), int(round(y)))


def _left_down() -> None:
    _require_windows()
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)


def _left_up() -> None:
    _require_windows()
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _cursor_position() -> tuple[int, int]:
    _require_windows()
    point = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def _sleep_until(deadline: float, stop_event: threading.Event) -> bool:
    while not stop_event.is_set():
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return True
        time.sleep(max(0.0, remaining - 0.002) if remaining > 0.004 else 0)
    return False


class RandomMouseTest:
    def __init__(self) -> None:
        _require_windows()
        if not PROFILE_PATH.exists():
            raise FileNotFoundError(
                "Geen master_profile.json gevonden. Open AI Mouse Lab en klik eerst op Build Profile."
            )
        self.profile = read_json(PROFILE_PATH, {})
        if not isinstance(self.profile, dict) or not self.profile:
            raise ValueError("Het persoonlijke muisprofiel is leeg of ongeldig.")

        self.root = tk.Tk()
        self.root.title("AI Mouse Random Test")
        self.root.configure(bg=TRANSPARENT)

        # Windows/Tk does not allow -fullscreen while overrideredirect is active.
        # A borderless screen-sized window gives the same visual result without
        # triggering the TclError seen on startup.
        self.width = max(800, self.root.winfo_screenwidth())
        self.height = max(600, self.root.winfo_screenheight())
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.width}x{self.height}+0+0")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            self.root.attributes("-alpha", 0.22)

        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.root.bind_all("<Escape>", lambda _event: self.stop())
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.after(50, self._activate_overlay)

        self.stop_event = threading.Event()
        self.finished = False
        self.seed = random.SystemRandom().randrange(1, 2**31 - 1)
        self.rng = random.Random(self.seed)
        self.records: list[dict[str, Any]] = []
        self.worker: threading.Thread | None = None

    def _activate_overlay(self) -> None:
        try:
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def _draw_hud(self, current: int, status: str) -> None:
        self.canvas.delete("hud")
        self.canvas.create_rectangle(
            22, 20, 390, 150,
            fill="#0b0f16", outline="#2e3948", width=1, tags="hud",
        )
        self.canvas.create_text(
            42, 42, anchor="nw", text="AI Mouse – Randomized Test",
            fill="#f1f5f9", font=("Segoe UI", 17, "bold"), tags="hud",
        )
        self.canvas.create_text(
            42, 78, anchor="nw", text=f"Beweging {current}/{TARGET_COUNT}",
            fill="#d9e2ec", font=("Segoe UI", 12), tags="hud",
        )
        self.canvas.create_text(
            42, 105, anchor="nw", text=status,
            fill="#4ade80" if status == "Actief" else "#facc15",
            font=("Segoe UI", 12, "bold"), tags="hud",
        )
        self.canvas.create_text(
            42, 130, anchor="nw", text="Esc = direct stoppen",
            fill="#94a3b8", font=("Segoe UI", 10), tags="hud",
        )

    def _draw_target(self, index: int, x: int, y: int, radius: int) -> None:
        self.canvas.delete("target")
        color = "#4ade80" if index < TARGET_COUNT else "#facc15"
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            outline=color, width=3, tags="target",
        )
        self.canvas.create_oval(
            x - 3, y - 3, x + 3, y + 3,
            fill=color, outline="", tags="target",
        )
        self.canvas.create_text(
            x, y - radius - 14, text=str(index), fill=color,
            font=("Segoe UI", 11, "bold"), tags="target",
        )
        self._draw_hud(index, "Actief")
        self.canvas.update_idletasks()

    def _choose_target(self, current: tuple[int, int]) -> tuple[int, int, int]:
        margin_x = max(90, int(self.width * 0.06))
        margin_y = max(90, int(self.height * 0.08))
        minimum_distance = min(self.width, self.height) * 0.20
        for _ in range(100):
            x = self.rng.randint(margin_x, self.width - margin_x)
            y = self.rng.randint(margin_y, self.height - margin_y)
            if math.hypot(x - current[0], y - current[1]) >= minimum_distance:
                return x, y, self.rng.choice([16, 20, 24])
        return self.width // 2, self.height // 2, 20

    def _to_virtual(self, x: float, y: float) -> tuple[float, float]:
        return x * VIRTUAL_WIDTH / self.width, y * VIRTUAL_HEIGHT / self.height

    def _to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x * self.width / VIRTUAL_WIDTH, y * self.height / VIRTUAL_HEIGHT

    def _build_trial(
        self,
        index: int,
        start: tuple[int, int],
        target: tuple[int, int],
        radius: int,
    ) -> dict[str, Any]:
        sx, sy = self._to_virtual(*start)
        tx, ty = self._to_virtual(*target)
        scale = 0.5 * (VIRTUAL_WIDTH / self.width + VIRTUAL_HEIGHT / self.height)
        plan = {
            "schema_version": 3,
            "seed": self.seed + index,
            "width": int(VIRTUAL_WIDTH),
            "height": int(VIRTUAL_HEIGHT),
            "targets": [{
                "index": index - 1,
                "start": [sx, sy],
                "target": [tx, ty],
                "radius": max(8.0, radius * scale),
            }],
        }
        return simulate(plan, self.profile, seed=self.seed + index)[0]

    def _execute_trial(self, trial: dict[str, Any]) -> None:
        started = time.perf_counter()
        for point in trial["points"]:
            if not _sleep_until(started + float(point["t_ms"]) / 1000.0, self.stop_event):
                return
            x, y = self._to_screen(float(point["x"]), float(point["y"]))
            _set_cursor(x, y)

        click = trial["click"]
        if not _sleep_until(started + float(click["down_t_ms"]) / 1000.0, self.stop_event):
            return
        _left_down()
        if not _sleep_until(started + float(click["up_t_ms"]) / 1000.0, self.stop_event):
            _left_up()
            return
        _left_up()

    def _run(self) -> None:
        winmm.timeBeginPeriod(1)
        try:
            for index in range(1, TARGET_COUNT + 1):
                if self.stop_event.is_set():
                    break
                start = _cursor_position()
                target_x, target_y, radius = self._choose_target(start)
                ready = threading.Event()

                def draw(
                    move_index: int = index,
                    x: int = target_x,
                    y: int = target_y,
                    target_radius: int = radius,
                ) -> None:
                    self._draw_target(move_index, x, y, target_radius)
                    ready.set()

                self.root.after(0, draw)
                ready.wait(timeout=2.0)
                if self.stop_event.is_set():
                    break

                trial = self._build_trial(index, start, (target_x, target_y), radius)
                self._execute_trial(trial)
                if self.stop_event.is_set():
                    break
                self.records.append({
                    "index": index,
                    "screen_start": list(start),
                    "screen_target": [target_x, target_y],
                    "radius": radius,
                    "trial": trial,
                })
                if self.stop_event.wait(0.38):
                    break
        finally:
            winmm.timeEndPeriod(1)
            self._save_result()
            self.finished = True
            try:
                self.root.after(0, self._finish_ui)
            except tk.TclError:
                pass

    def _save_result(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        payload = {
            "created_at": datetime.now().isoformat(),
            "seed": self.seed,
            "screen": {"width": self.width, "height": self.height},
            "requested_moves": TARGET_COUNT,
            "completed_moves": len(self.records),
            "stopped": self.stop_event.is_set(),
            "moves": self.records,
        }
        (OUTPUT_DIR / f"random_mouse_test_{stamp}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _finish_ui(self) -> None:
        self.canvas.delete("target")
        self._draw_hud(
            len(self.records),
            "Klaar" if not self.stop_event.is_set() else "Gestopt",
        )
        self.root.after(1100, self.root.destroy)

    def stop(self) -> None:
        self.stop_event.set()
        if self.finished:
            self.root.destroy()

    def start(self) -> None:
        self._draw_hud(0, "Start over 2 seconden")
        self.root.after(2000, self._start_worker)
        self.root.mainloop()

    def _start_worker(self) -> None:
        if self.stop_event.is_set():
            self.root.destroy()
            return
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()


def main() -> None:
    try:
        RandomMouseTest().start()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        from tkinter import messagebox
        messagebox.showerror("AI Mouse Random Test", str(exc))
        root.destroy()
        raise


if __name__ == "__main__":
    main()
