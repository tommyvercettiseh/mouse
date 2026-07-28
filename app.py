from __future__ import annotations

import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk

from ai_mouse_lab import __version__
from ai_mouse_lab.benchmark import create_blind_export, generate_plan, plan_from_human_trials, simulate
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

        self.bench_active = False
        self.bench_plan: dict[str, Any] = {}
        self.bench_trials: list[dict[str, Any]] = []
        self.bench_index = 0
        self.bench_target_spawn = 0.0
        self.bench_start_point = (0.0, 0.0)
        self.bench_points: list[dict[str, Any]] = []
        self.bench_click_down: float | None = None
        self.bench_folder: Path | None = None

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
            button = ctk.CTkButton(nav, text=name, anchor="w", height=42, fg_color="transparent", hover_color=PANEL2, command=lambda value=name: self.show(value))
            button.pack(fill="x", padx=12, pady=3)
            self.buttons[name] = button
        ctk.CTkLabel(nav, text="● Data blijft lokaal", text_color=GREEN).pack(side="bottom", anchor="w", padx=20, pady=18)

        self.host = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.host.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.host.grid_rowconfigure(0, weight=1)
        self.host.grid_columnconfigure(0, weight=1)
        self._page_dashboard()
        self._page_simple("Free Record", "Free Record", "De recorderbasis blijft beschikbaar. Benchmark is nu de primaire productflow.")
        self._page_aim()
        self._page_profile()
        self._page_benchmark()
        self._page_results()
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
        if key == "Results":
            self.refresh_results()

    def _page_dashboard(self) -> None:
        body = self.page("Dashboard", "Dashboard", "Eén hub voor trainen, profielbouw en blinde benchmark.")
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
        ctk.CTkLabel(info, text="Benchmark is nu de kern", text_color=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(info, text="Bouw profiel → start benchmark → klik dezelfde targetreeks → genereer AI-sessie → exporteer A.json en B.json → onthul private_answer.json pas na beoordeling.", text_color=MUTED, wraplength=850, justify="left").pack(anchor="w", padx=20)

    def refresh_dashboard(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        sessions = [path for path in AIM.glob("*") if path.is_dir()]
        targets = sum(len(read_json(path / "trials.json", [])) for path in sessions)
        values = [f"{profile.get('quality_percent', 0)}%", str(len(sessions)), str(targets), str(len([path for path in BENCHMARKS.glob('*') if path.is_dir()]))]
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
        ctk.CTkLabel(side, text="Misses worden opgeslagen en gaan door naar het volgende target.", text_color=MUTED, wraplength=230, justify="left").pack(anchor="w", padx=18, pady=12)

    def start_aim(self) -> None:
        self.canvas.update_idletasks()
        width, height = max(700, self.canvas.winfo_width()), max(500, self.canvas.winfo_height())
        self.plan = [{"index": index, "x": random.randint(70, width - 70), "y": random.randint(70, height - 70), "radius": random.choice([12, 18, 26])} for index in range(int(self.count_menu.get()))]
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
        x, y, radius = target["x"], target["y"], target["radius"]
        self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=PURPLE, outline="#c4b5fd", width=3)
        self.canvas.create_text(x, y, text=str(self.index + 1), fill="white")
        self.target_spawn = time.perf_counter()
        self.start_point = self.pointer_canvas(self.canvas)
        self.points = []
        self.click_down = None
        self.append_point(*self.start_point)
        self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: 1")

    def pointer_canvas(self, canvas: ctk.CTkCanvas) -> tuple[float, float]:
        screen_x, screen_y = self.winfo_pointerxy()
        return float(screen_x - canvas.winfo_rootx()), float(screen_y - canvas.winfo_rooty())

    def append_point(self, x: float, y: float) -> None:
        if not self.aim_active:
            return
        t_ms = round((time.perf_counter() - self.target_spawn) * 1000, 3)
        self.points.append({"t_ms": t_ms, "x": round(x, 3), "y": round(y, 3)})
        self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: {len(self.points)}")

    def sample_pointer(self) -> None:
        if not self.aim_active:
            return
        self.append_point(*self.pointer_canvas(self.canvas))
        self.after(8, self.sample_pointer)

    def on_press(self, event) -> None:
        if self.aim_active:
            self.click_down = time.perf_counter()
            self.append_point(float(event.x), float(event.y))

    def on_release(self, event) -> None:
        if not self.aim_active:
            return
        released = time.perf_counter()
        self.append_point(float(event.x), float(event.y))
        target = self.plan[self.index]
        down_ms = round(((self.click_down or released) - self.target_spawn) * 1000, 3)
        up_ms = round((released - self.target_spawn) * 1000, 3)
        target_data = {"index": target["index"], "x": target["x"], "y": target["y"], "radius": target["radius"]}
        start_data = {"x": self.start_point[0], "y": self.start_point[1]}
        click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(event.x), "y": float(event.y)}
        try:
            derived = derive_trial(target_data, start_data, self.points, click)
        except ValueError:
            return
        self.trials.append({"schema_version": 4, "target": target_data, "start": start_data, "points": list(self.points), "click": click, "derived": derived})
        self.index += 1
        self.show_target()

    def finish_aim(self) -> None:
        self.aim_active = False
        self.start_btn.configure(state="normal")
        folder = self.session_folder or (AIM / now_stamp())
        write_json(folder / "trials.json", self.trials)
        write_json(folder / "summary.json", {"schema_version": 4, "trial_count": len(self.trials), "point_count": sum(len(trial["points"]) for trial in self.trials), "miss_count": sum(1 for trial in self.trials if trial["derived"]["miss"]), "created_at": datetime.now().isoformat()})
        self.canvas.delete("all")
        self.canvas.create_text(self.canvas.winfo_width()/2, self.canvas.winfo_height()/2, text="Sessie opgeslagen", fill=GREEN, font=("Segoe UI", 22, "bold"))
        self.aim_status.configure(text=f"Klaar\n{len(self.trials)} targets\n{sum(1 for trial in self.trials if trial['derived']['miss'])} misses")
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
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            self.profile_label.configure(text="Nog geen profiel")
            return
        self.profile_label.configure(text=f"Kwaliteit: {profile['quality_percent']}%\nTargets: {profile['trial_count']}\nRuwe punten: {profile['point_count']}\nMisses: {profile['miss_count']}\n\nMovement mediaan: {profile['features']['movement_time_ms']['median']} ms\nOvershoot mediaan: {profile['features']['overshoot_px']['median']} px\nCorrecties mediaan: {profile['features']['correction_count']['median']}")

    def _page_benchmark(self) -> None:
        body = self.page("Benchmark", "Benchmark", "Speel zelf en exporteer daarna een echte blinde A/B-test.")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(0, weight=1)
        arena.grid_columnconfigure(0, weight=1)
        self.bench_canvas = ctk.CTkCanvas(arena, bg=PANEL, highlightthickness=0)
        self.bench_canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.bench_canvas.bind("<ButtonPress-1>", self.bench_press)
        self.bench_canvas.bind("<ButtonRelease-1>", self.bench_release)

        side = Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(side, text="Blinde benchmark", text_color=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        self.bench_count_menu = ctk.CTkOptionMenu(side, values=["20", "50", "100"], fg_color=PANEL2, button_color=PURPLE)
        self.bench_count_menu.set("20")
        self.bench_count_menu.pack(fill="x", padx=18, pady=8)
        self.bench_start_btn = ctk.CTkButton(side, text="Start benchmark", fg_color=PURPLE, height=46, command=self.start_benchmark)
        self.bench_start_btn.pack(fill="x", padx=18, pady=8)
        self.bench_status = ctk.CTkLabel(side, text="Bouw eerst een profiel. Daarna speel jij exact de targetreeks.", text_color=MUTED, justify="left", wraplength=235)
        self.bench_status.pack(anchor="w", padx=18, pady=12)
        self.bench_open_btn = ctk.CTkButton(side, text="Open laatste benchmarkmap", fg_color=PANEL2, command=self.open_benchmark_folder, state="disabled")
        self.bench_open_btn.pack(side="bottom", fill="x", padx=18, pady=18)

    def start_benchmark(self) -> None:
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            self.bench_status.configure(text="Bouw eerst een profiel.", text_color=RED)
            return
        self.bench_canvas.update_idletasks()
        width = max(700, self.bench_canvas.winfo_width())
        height = max(500, self.bench_canvas.winfo_height())
        self.bench_plan = generate_plan(int(self.bench_count_menu.get()), width=width, height=height, seed=random.randint(1, 2**31 - 1))
        self.bench_trials, self.bench_index, self.bench_active = [], 0, True
        self.bench_folder = BENCHMARKS / now_stamp()
        self.bench_folder.mkdir(parents=True, exist_ok=True)
        write_json(self.bench_folder / "benchmark_plan_original.json", self.bench_plan)
        self.bench_start_btn.configure(state="disabled")
        self.bench_open_btn.configure(state="disabled")
        self.show_benchmark_target()
        self.sample_benchmark_pointer()

    def show_benchmark_target(self) -> None:
        self.bench_canvas.delete("all")
        if self.bench_index >= len(self.bench_plan.get("targets", [])):
            self.finish_benchmark()
            return
        item = self.bench_plan["targets"][self.bench_index]
        x, y = item["target"]
        radius = item["radius"]
        self.bench_canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=PURPLE, outline="#c4b5fd", width=3)
        self.bench_canvas.create_text(x, y, text=str(self.bench_index + 1), fill="white")
        self.bench_target_spawn = time.perf_counter()
        self.bench_start_point = self.pointer_canvas(self.bench_canvas)
        self.bench_points = []
        self.bench_click_down = None
        self.append_benchmark_point(*self.bench_start_point)
        self.bench_status.configure(text=f"Jij speelt\nTarget {self.bench_index + 1}/{len(self.bench_plan['targets'])}\nPoints: 1", text_color=MUTED)

    def append_benchmark_point(self, x: float, y: float) -> None:
        if not self.bench_active:
            return
        t_ms = round((time.perf_counter() - self.bench_target_spawn) * 1000, 3)
        self.bench_points.append({"t_ms": t_ms, "x": round(x, 3), "y": round(y, 3)})
        self.bench_status.configure(text=f"Jij speelt\nTarget {self.bench_index + 1}/{len(self.bench_plan['targets'])}\nPoints: {len(self.bench_points)}")

    def sample_benchmark_pointer(self) -> None:
        if not self.bench_active:
            return
        self.append_benchmark_point(*self.pointer_canvas(self.bench_canvas))
        self.after(8, self.sample_benchmark_pointer)

    def bench_press(self, event) -> None:
        if self.bench_active:
            self.bench_click_down = time.perf_counter()
            self.append_benchmark_point(float(event.x), float(event.y))

    def bench_release(self, event) -> None:
        if not self.bench_active:
            return
        released = time.perf_counter()
        self.append_benchmark_point(float(event.x), float(event.y))
        item = self.bench_plan["targets"][self.bench_index]
        down_ms = round(((self.bench_click_down or released) - self.bench_target_spawn) * 1000, 3)
        up_ms = round((released - self.bench_target_spawn) * 1000, 3)
        target_x, target_y = item["target"]
        target_data = {"index": item["index"], "x": target_x, "y": target_y, "radius": item["radius"]}
        start_data = {"x": self.bench_start_point[0], "y": self.bench_start_point[1]}
        click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(event.x), "y": float(event.y)}
        try:
            derived = derive_trial(target_data, start_data, self.bench_points, click)
        except ValueError:
            return
        self.bench_trials.append({"schema_version": 4, "target": target_data, "start": start_data, "points": list(self.bench_points), "click": click, "derived": derived})
        self.bench_index += 1
        self.show_benchmark_target()

    def finish_benchmark(self) -> None:
        self.bench_active = False
        self.bench_start_btn.configure(state="normal")
        folder = self.bench_folder or (BENCHMARKS / now_stamp())
        folder.mkdir(parents=True, exist_ok=True)
        profile = read_json(PROFILES / "master_profile.json", {})
        effective_plan = plan_from_human_trials(self.bench_plan, self.bench_trials)
        generated = simulate(effective_plan, profile, seed=int(effective_plan["seed"]) + 1)
        bundle = create_blind_export(effective_plan, self.bench_trials, generated, seed=int(effective_plan["seed"]) + 2)
        write_json(folder / "benchmark_plan.json", effective_plan)
        write_json(folder / "human_private.json", {"schema_version": 4, "trials": self.bench_trials})
        write_json(folder / "generated_private.json", {"schema_version": 4, "trials": generated})
        write_json(folder / "A.json", bundle["A"])
        write_json(folder / "B.json", bundle["B"])
        write_json(folder / "private_answer.json", bundle["private_answer"])
        write_json(folder / "summary.json", bundle["summary"])
        self.bench_canvas.delete("all")
        self.bench_canvas.create_text(self.bench_canvas.winfo_width()/2, self.bench_canvas.winfo_height()/2, text="A.json en B.json zijn klaar", fill=GREEN, font=("Segoe UI", 22, "bold"))
        self.bench_status.configure(text=f"Benchmark klaar\n{len(self.bench_trials)} targets\nUpload alleen A.json en B.json\nOnthul private_answer.json later", text_color=GREEN)
        self.bench_open_btn.configure(state="normal")
        self.refresh_dashboard()

    def open_benchmark_folder(self) -> None:
        if not self.bench_folder:
            return
        try:
            os.startfile(self.bench_folder)
        except Exception:
            pass

    def _page_results(self) -> None:
        body = self.page("Results", "Results", "Laatste benchmarkbestanden en juiste reveal-volgorde.")
        card = Card(body)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        self.results_label = ctk.CTkLabel(card, text="Nog geen benchmark.", text_color=MUTED, justify="left", wraplength=850, font=("Segoe UI", 14))
        self.results_label.pack(anchor="w", padx=22, pady=22)

    def refresh_results(self) -> None:
        folders = sorted((path for path in BENCHMARKS.glob("*") if path.is_dir()), reverse=True)
        if not folders:
            self.results_label.configure(text="Nog geen benchmark.")
            return
        folder = folders[0]
        summary = read_json(folder / "summary.json", {})
        ready = all((folder / name).exists() for name in ("A.json", "B.json", "private_answer.json"))
        self.results_label.configure(text=(
            f"Laatste benchmark: {folder.name}\n"
            f"Targets: {summary.get('trial_count', 0)}\n"
            f"A/B klaar: {'Ja' if ready else 'Nee'}\n\n"
            "1. Upload A.json en B.json in ChatGPT.\n"
            "2. Vraag welke waarschijnlijk echt is en waarom.\n"
            "3. Vertel daarna pas de waarheid of open private_answer.json.\n"
            "4. Gebruik de opvallende verschillen als input voor de volgende generatorversie."
        ))


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()


if __name__ == "__main__":
    main()
