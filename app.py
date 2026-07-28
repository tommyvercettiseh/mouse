from __future__ import annotations

import math
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk

from ai_mouse_lab import __version__
from ai_mouse_lab.benchmark import generate_plan, simulate
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.profile import build_profile
from ai_mouse_lab.storage import AIM, BENCHMARKS, PROFILES, RECORDINGS, now_stamp, read_json, write_json

BG, PANEL, PANEL2, BORDER = "#0b1018", "#141b25", "#1a2330", "#2a3442"
TEXT, MUTED, PURPLE, GREEN, RED = "#f4f6fb", "#98a3b3", "#8b5cf6", "#3ccf78", "#d94b4b"


class Card(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
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
        self.plan: list[dict[str, Any]] = []
        self.trials: list[dict[str, Any]] = []
        self.index = 0
        self.target_spawn = 0.0
        self.start_point = (0.0, 0.0)
        self.points: list[dict[str, Any]] = []
        self.click_down: float | None = None
        self.session_folder: Path | None = None
        self._build_shell()
        self.show("Dashboard")

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        nav = ctk.CTkFrame(self, width=230, fg_color="#0d131d", corner_radius=0)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        ctk.CTkLabel(nav, text="AI Mouse Lab", text_color=TEXT, font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=20, pady=(24, 2))
        ctk.CTkLabel(nav, text=f"v{__version__} · lokale Windows hub", text_color=MUTED).pack(anchor="w", padx=20, pady=(0, 18))
        for name in ("Dashboard", "Free Record", "Aim Lab", "Build Profile", "Benchmark", "Results", "Profiles", "Settings"):
            b = ctk.CTkButton(nav, text=name, anchor="w", height=42, fg_color="transparent", hover_color=PANEL2, command=lambda n=name: self.show(n))
            b.pack(fill="x", padx=12, pady=3)
            self.buttons[name] = b
        ctk.CTkLabel(nav, text="● Data blijft lokaal", text_color=GREEN).pack(side="bottom", anchor="w", padx=20, pady=18)

        self.host = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.host.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.host.grid_rowconfigure(0, weight=1)
        self.host.grid_columnconfigure(0, weight=1)
        self._page_dashboard()
        self._page_simple("Free Record", "Free Record", "De recorderbasis blijft beschikbaar in v0.3.0. Aim Lab heeft nu prioriteit.")
        self._page_aim()
        self._page_profile()
        self._page_benchmark()
        self._page_simple("Results", "Results", "Upload later A.json en B.json voor een blinde analyse. Automatische classificatie blijft bewust buiten deze release.")
        self._page_simple("Profiles", "Profiles", "Eén transparant masterprofiel wordt lokaal opgeslagen in data/profiles.")
        self._page_simple("Settings", "Settings", "De app gebruikt één hoofdvenster en lokale bestanden. Geen cloud en geen externe muisbesturing.")

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
        for name, page in self.pages.items():
            page.grid_remove()
            self.buttons[name].configure(fg_color=PURPLE if name == key else "transparent")
        self.pages[key].grid()
        if key == "Dashboard":
            self.refresh_dashboard()
        if key == "Build Profile":
            self.refresh_profile()

    def _page_dashboard(self) -> None:
        body = self.page("Dashboard", "Dashboard", "Eén hub voor opnemen, trainen, profielbouw en benchmark.")
        body.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.dashboard_values = []
        for col, label in enumerate(("Profielkwaliteit", "Aim sessies", "Targets", "Benchmarks")):
            card = Card(body)
            card.grid(row=0, column=col, sticky="ew", padx=6, pady=6)
            ctk.CTkLabel(card, text=label, text_color=MUTED).pack(anchor="w", padx=18, pady=(16, 4))
            value = ctk.CTkLabel(card, text="0", text_color=PURPLE, font=("Segoe UI", 27, "bold"))
            value.pack(anchor="w", padx=18, pady=(0, 16))
            self.dashboard_values.append(value)
        info = Card(body)
        info.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=6, pady=12)
        body.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(info, text="Wat deze versie betrouwbaar doet", text_color=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(info, text="Volledige Aim Lab-route per target · misses bewaren · click down/up · smoothing · overshoot · correcties · testbare profielbouw · reproduceerbare benchmarkplannen", text_color=MUTED, wraplength=850, justify="left").pack(anchor="w", padx=20)

    def refresh_dashboard(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        sessions = [p for p in AIM.glob("*") if p.is_dir()]
        targets = sum(len(read_json(p / "trials.json", [])) for p in sessions)
        values = [f"{profile.get('quality_percent', 0)}%", str(len(sessions)), str(targets), str(len([p for p in BENCHMARKS.glob('*') if p.is_dir()]))]
        for label, value in zip(self.dashboard_values, values):
            label.configure(text=value)

    def _page_simple(self, key: str, title: str, text: str) -> None:
        body = self.page(key, title, text)
        card = Card(body)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(card, text=text, text_color=MUTED, wraplength=800, justify="left", font=("Segoe UI", 14)).pack(anchor="w", padx=22, pady=22)

    def _page_aim(self) -> None:
        body = self.page("Aim Lab", "Aim Lab", "Registreert de volledige beweging per target in canvas-coördinaten.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        self.canvas = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        side = Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="Sessie", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        self.count_menu = ctk.CTkOptionMenu(side, values=["20", "50", "100"], fg_color=PANEL2, button_color=PURPLE)
        self.count_menu.set("20")
        self.count_menu.pack(fill="x", padx=18, pady=8)
        self.start_btn = ctk.CTkButton(side, text="Start Aim Lab", fg_color=PURPLE, height=46, command=self.start_aim)
        self.start_btn.pack(fill="x", padx=18, pady=8)
        self.aim_status = ctk.CTkLabel(side, text="Klaar", text_color=MUTED, justify="left", wraplength=230)
        self.aim_status.pack(anchor="w", padx=18, pady=12)
        ctk.CTkLabel(side, text="Misses worden opgeslagen en gaan door naar het volgende target. Daardoor verdwijnen fouten niet uit je profiel.", text_color=MUTED, wraplength=230, justify="left").pack(anchor="w", padx=18, pady=12)

    def start_aim(self) -> None:
        self.canvas.update_idletasks()
        w, h = max(700, self.canvas.winfo_width()), max(500, self.canvas.winfo_height())
        self.plan = []
        for i in range(int(self.count_menu.get())):
            self.plan.append({"index": i, "x": random.randint(70, w - 70), "y": random.randint(70, h - 70), "radius": random.choice([12, 18, 26])})
        self.trials, self.index, self.aim_active = [], 0, True
        self.session_folder = AIM / now_stamp()
        self.session_folder.mkdir(parents=True, exist_ok=True)
        write_json(self.session_folder / "plan.json", self.plan)
        self.start_btn.configure(state="disabled")
        self.show_target()
        self.sample_pointer()

    def show_target(self) -> None:
        self.canvas.delete("all")
        if self.index >= len(self.plan):
            self.finish_aim()
            return
        target = self.plan[self.index]
        x, y, r = target["x"], target["y"], target["radius"]
        self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=PURPLE, outline="#c4b5fd", width=3)
        self.canvas.create_text(x, y, text=str(self.index + 1), fill="white")
        self.target_spawn = time.perf_counter()
        self.start_point = self.pointer_canvas()
        self.points = []
        self.click_down = None
        self.append_point(*self.start_point)
        self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: 1")

    def pointer_canvas(self) -> tuple[float, float]:
        sx, sy = self.winfo_pointerxy()
        return float(sx - self.canvas.winfo_rootx()), float(sy - self.canvas.winfo_rooty())

    def append_point(self, x: float, y: float) -> None:
        if not self.aim_active:
            return
        t_ms = round((time.perf_counter() - self.target_spawn) * 1000, 3)
        self.points.append({"t_ms": t_ms, "x": round(x, 3), "y": round(y, 3)})
        self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: {len(self.points)}")

    def sample_pointer(self) -> None:
        if not self.aim_active:
            return
        self.append_point(*self.pointer_canvas())
        self.after(8, self.sample_pointer)

    def on_motion(self, event) -> None:
        pass

    def on_press(self, event) -> None:
        if self.aim_active:
            self.click_down = time.perf_counter()
            self.append_point(float(event.x), float(event.y))

    def on_release(self, event) -> None:
        if not self.aim_active:
            return
        up = time.perf_counter()
        self.append_point(float(event.x), float(event.y))
        target = self.plan[self.index]
        down_ms = round(((self.click_down or up) - self.target_spawn) * 1000, 3)
        up_ms = round((up - self.target_spawn) * 1000, 3)
        target_data = {"index": target["index"], "x": target["x"], "y": target["y"], "radius": target["radius"]}
        start_data = {"x": self.start_point[0], "y": self.start_point[1]}
        click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(event.x), "y": float(event.y)}
        try:
            derived = derive_trial(target_data, start_data, self.points, click)
        except ValueError:
            return
        self.trials.append({"schema_version": 3, "target": target_data, "start": start_data, "points": list(self.points), "click": click, "derived": derived})
        self.index += 1
        self.show_target()

    def finish_aim(self) -> None:
        self.aim_active = False
        self.start_btn.configure(state="normal")
        folder = self.session_folder or (AIM / now_stamp())
        write_json(folder / "trials.json", self.trials)
        write_json(folder / "summary.json", {
            "schema_version": 3,
            "trial_count": len(self.trials),
            "point_count": sum(len(t["points"]) for t in self.trials),
            "miss_count": sum(1 for t in self.trials if t["derived"]["miss"]),
            "created_at": datetime.now().isoformat(),
        })
        self.canvas.delete("all")
        self.canvas.create_text(self.canvas.winfo_width()/2, self.canvas.winfo_height()/2, text="Sessie opgeslagen", fill=GREEN, font=("Segoe UI", 22, "bold"))
        self.aim_status.configure(text=f"Klaar\n{len(self.trials)} targets\n{sum(1 for t in self.trials if t['derived']['miss'])} misses")
        self.refresh_dashboard()

    def _page_profile(self) -> None:
        body = self.page("Build Profile", "Build Profile", "Bouwt een transparant profiel uit alle Aim Lab-routes.")
        card = Card(body)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        self.profile_label = ctk.CTkLabel(card, text="Nog geen profiel", text_color=MUTED, justify="left", font=("Consolas", 13))
        self.profile_label.pack(anchor="w", padx=22, pady=22)
        ctk.CTkButton(card, text="Profiel opnieuw bouwen", fg_color=PURPLE, command=self.make_profile).pack(anchor="w", padx=22, pady=8)

    def collect_trials(self) -> list[dict[str, Any]]:
        trials = []
        for folder in AIM.glob("*"):
            if folder.is_dir():
                trials.extend(read_json(folder / "trials.json", []))
        return trials

    def make_profile(self) -> None:
        profile = build_profile(self.collect_trials(), [])
        write_json(PROFILES / "master_profile.json", profile)
        self.refresh_profile()
        self.refresh_dashboard()

    def refresh_profile(self) -> None:
        p = read_json(PROFILES / "master_profile.json", {})
        if not p:
            self.profile_label.configure(text="Nog geen profiel")
            return
        self.profile_label.configure(text=f"Kwaliteit: {p['quality_percent']}%\nTargets: {p['trial_count']}\nRuwe punten: {p['point_count']}\nMisses: {p['miss_count']}\n\nMovement mediaan: {p['features']['movement_time_ms']['median']} ms\nOvershoot mediaan: {p['features']['overshoot_px']['median']} px\nCorrecties mediaan: {p['features']['correction_count']['median']}")

    def _page_benchmark(self) -> None:
        body = self.page("Benchmark", "Benchmark", "Reproduceerbaar plan en profielsimulatie met vaste seed.")
        card = Card(body)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        self.bench_status = ctk.CTkLabel(card, text="Bouw eerst een profiel.", text_color=MUTED, justify="left")
        self.bench_status.pack(anchor="w", padx=22, pady=22)
        ctk.CTkButton(card, text="Maak benchmarkplan", fg_color=PURPLE, command=self.make_benchmark).pack(anchor="w", padx=22, pady=8)

    def make_benchmark(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            self.bench_status.configure(text="Bouw eerst een profiel.", text_color=RED)
            return
        folder = BENCHMARKS / now_stamp()
        plan = generate_plan(20, seed=random.randint(1, 2**31-1))
        generated = simulate(plan, profile)
        write_json(folder / "benchmark_plan.json", plan)
        write_json(folder / "generated_pending.json", generated)
        self.bench_status.configure(text=f"Plan en simulatie opgeslagen\nSeed: {plan['seed']}\nMap: {folder.name}", text_color=GREEN)
        self.refresh_dashboard()


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()


if __name__ == "__main__":
    main()
