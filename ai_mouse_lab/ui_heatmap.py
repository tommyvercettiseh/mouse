from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import customtkinter as ctk

from .heatmap_flow import create_heatmap_runs, latest_heatmap_runs
from .models import normalize_trials
from .ui_theme import (
    BORDER,
    GREEN,
    MUTED,
    PANEL,
    PANEL2,
    PURPLE,
    RED,
    TEXT,
    VIRTUAL_HEIGHT,
    VIRTUAL_WIDTH,
    Card,
)


class HeatmapMixin:
    def init_heatmap_state(self) -> None:
        self.heatmap_folder: Path | None = None
        self.heatmap_payload: dict[str, Any] = {}
        self.heatmap_target_index = 0

    def _page_heatmap(self) -> None:
        body = self.page(
            "Heatmap",
            "Heatmap",
            "Simuleer je laatste echte Aim Lab-sessie meerdere keren op exact dezelfde targets.",
        )
        body.grid_columnconfigure(0, weight=4)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        arena = Card(body)
        arena.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        arena.grid_rowconfigure(1, weight=1)
        arena.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(arena, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkButton(
            controls,
            text="← Vorige target",
            fg_color=PANEL2,
            command=lambda: self.change_heatmap_target(-1),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            controls,
            text="Volgende target →",
            fg_color=PANEL2,
            command=lambda: self.change_heatmap_target(1),
        ).pack(side="left", padx=6)
        self.heatmap_target_label = ctk.CTkLabel(
            controls,
            text="Nog geen dataset",
            text_color=TEXT,
            font=("Segoe UI", 13, "bold"),
        )
        self.heatmap_target_label.pack(side="right")

        self.heatmap_canvas = ctk.CTkCanvas(
            arena,
            bg=PANEL,
            highlightthickness=0,
        )
        self.heatmap_canvas.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=14,
            pady=(4, 14),
        )
        self.heatmap_canvas.bind("<Configure>", lambda _event: self.draw_heatmap())

        side = Card(body)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(
            side,
            text="Laatste sessie herhalen",
            text_color=TEXT,
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 6))
        ctk.CTkLabel(
            side,
            text=(
                "Iedere run gebruikt exact dezelfde startpunten, targets en "
                "targetgroottes uit je nieuwste voltooide sessie."
            ),
            text_color=MUTED,
            justify="left",
            wraplength=245,
        ).pack(anchor="w", padx=18, pady=(0, 12))

        self.heatmap_run_value = ctk.IntVar(value=100)
        self.heatmap_run_label = ctk.CTkLabel(
            side,
            text="100 runs",
            text_color=TEXT,
            font=("Segoe UI", 15, "bold"),
        )
        self.heatmap_run_label.pack(anchor="w", padx=18, pady=(6, 2))
        self.heatmap_slider = ctk.CTkSlider(
            side,
            from_=10,
            to=500,
            number_of_steps=49,
            variable=self.heatmap_run_value,
            command=self._heatmap_slider_changed,
        )
        self.heatmap_slider.pack(fill="x", padx=18, pady=8)
        self.heatmap_movement_label = ctk.CTkLabel(
            side,
            text="Aantal bewegingen volgt na laden van de nieuwste sessie.",
            text_color=MUTED,
            justify="left",
            wraplength=245,
        )
        self.heatmap_movement_label.pack(anchor="w", padx=18, pady=(0, 10))

        self.heatmap_generate_btn = ctk.CTkButton(
            side,
            text="Genereer runs + heatmap",
            fg_color=PURPLE,
            height=46,
            command=self.generate_heatmap,
        )
        self.heatmap_generate_btn.pack(fill="x", padx=18, pady=6)
        self.heatmap_open_btn = ctk.CTkButton(
            side,
            text="Open opslagmap",
            fg_color=PANEL2,
            height=42,
            state="disabled",
            command=self.open_heatmap_folder,
        )
        self.heatmap_open_btn.pack(fill="x", padx=18, pady=6)
        self.heatmap_status = ctk.CTkLabel(
            side,
            text="Nog geen heatmap gegenereerd.",
            text_color=MUTED,
            justify="left",
            wraplength=245,
        )
        self.heatmap_status.pack(anchor="w", padx=18, pady=12)

    def _heatmap_slider_changed(self, value: float) -> None:
        runs = int(round(value / 10.0) * 10)
        self.heatmap_run_value.set(runs)
        self.heatmap_run_label.configure(text=f"{runs} runs")
        target_count = int(self.heatmap_payload.get("target_count", 0) or 0)
        if target_count:
            self.heatmap_movement_label.configure(
                text=f"{runs * target_count} gesimuleerde bewegingen"
            )

    def generate_heatmap(self) -> None:
        runs = int(self.heatmap_run_value.get())
        self.heatmap_generate_btn.configure(
            state="disabled",
            text=f"{runs} runs genereren…",
        )
        self.heatmap_status.configure(
            text="Bezig. De app kan enkele seconden minder responsief zijn.",
            text_color=MUTED,
        )
        self.update_idletasks()
        try:
            folder, payload = create_heatmap_runs(runs)
            self.heatmap_folder = folder
            self.heatmap_payload = payload
            self.heatmap_target_index = 0
            target_count = int(payload.get("target_count", 0) or 0)
            movement_count = int(payload.get("movement_count", 0) or 0)
            self.heatmap_movement_label.configure(
                text=f"{movement_count} gesimuleerde bewegingen"
            )
            self.heatmap_status.configure(
                text=(
                    f"Klaar · {runs} runs × {target_count} targets\n"
                    f"{folder.name}\nheatmap_runs.json"
                ),
                text_color=GREEN,
            )
            self.heatmap_open_btn.configure(state="normal")
            self.draw_heatmap()
        except (KeyError, OSError, TypeError, ValueError) as exc:
            self._show_error("Heatmap genereren", exc, self.heatmap_status)
        finally:
            self.heatmap_generate_btn.configure(
                state="normal",
                text="Genereer runs + heatmap",
            )

    def refresh_heatmap(self) -> None:
        if not self.heatmap_payload:
            folder, payload = latest_heatmap_runs()
            self.heatmap_folder = folder
            self.heatmap_payload = payload
            if folder is not None:
                self.heatmap_open_btn.configure(state="normal")
        target_count = int(self.heatmap_payload.get("target_count", 0) or 0)
        self.heatmap_target_index = max(
            0,
            min(max(0, target_count - 1), self.heatmap_target_index),
        )
        self.draw_heatmap()

    def change_heatmap_target(self, delta: int) -> None:
        target_count = int(self.heatmap_payload.get("target_count", 0) or 0)
        if target_count <= 0:
            return
        self.heatmap_target_index = max(
            0,
            min(target_count - 1, self.heatmap_target_index + delta),
        )
        self.draw_heatmap()

    def draw_heatmap(self) -> None:
        canvas = getattr(self, "heatmap_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        runs = self.heatmap_payload.get("runs", [])
        if not isinstance(runs, list) or not runs:
            canvas.create_text(
                max(1, canvas.winfo_width()) / 2,
                max(1, canvas.winfo_height()) / 2,
                text="Genereer eerst meerdere runs",
                fill=MUTED,
                font=("Segoe UI", 18, "bold"),
            )
            self.heatmap_target_label.configure(text="Nog geen dataset")
            return

        index = self.heatmap_target_index
        selected: list[dict[str, Any]] = []
        for run in runs:
            if not isinstance(run, dict):
                continue
            trials = normalize_trials(run.get("trials", []))
            if index < len(trials):
                selected.append(trials[index])
        if not selected:
            return

        scale, offset_x, offset_y = self._canvas_box(canvas)
        canvas.create_rectangle(
            offset_x,
            offset_y,
            offset_x + VIRTUAL_WIDTH * scale,
            offset_y + VIRTUAL_HEIGHT * scale,
            outline=BORDER,
        )
        target = selected[0]["target"]
        tx, ty = self._to_canvas(canvas, float(target["x"]), float(target["y"]))
        radius = max(3.0, float(target["radius"]) * scale)
        canvas.create_oval(
            tx - radius,
            ty - radius,
            tx + radius,
            ty + radius,
            outline="white",
            width=2,
        )

        for trial in selected:
            points = trial.get("points", [])
            if not isinstance(points, list) or len(points) < 2:
                continue
            coordinates: list[float] = []
            stride = max(1, len(points) // 180)
            for point in points[::stride]:
                try:
                    x, y = self._to_canvas(
                        canvas,
                        float(point["x"]),
                        float(point["y"]),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                coordinates.extend((x, y))
            if len(coordinates) >= 4:
                canvas.create_line(
                    *coordinates,
                    fill="#385b72",
                    width=1,
                    smooth=True,
                )
            click = trial.get("click", {})
            if isinstance(click, dict):
                try:
                    cx, cy = self._to_canvas(
                        canvas,
                        float(click["x"]),
                        float(click["y"]),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                canvas.create_oval(
                    cx - 1.5,
                    cy - 1.5,
                    cx + 1.5,
                    cy + 1.5,
                    fill=GREEN,
                    outline="",
                )

        self.heatmap_target_label.configure(
            text=f"Target {index + 1}/{self.heatmap_payload.get('target_count', 0)} · {len(selected)} runs"
        )

    def open_heatmap_folder(self) -> None:
        folder = self.heatmap_folder
        if folder is None or not folder.exists():
            self.heatmap_status.configure(
                text="De opslagmap bestaat niet meer.",
                text_color=RED,
            )
            return
        try:
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            else:
                raise OSError("Open opslagmap is alleen beschikbaar op Windows.")
        except OSError as exc:
            self._show_error("Map openen", exc, self.heatmap_status)
