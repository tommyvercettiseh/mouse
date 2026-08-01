from __future__ import annotations

import logging
from pathlib import Path
from tkinter import TclError
from types import TracebackType
from typing import Any

import customtkinter as ctk

from . import __version__
from .ui_aim import AimLabMixin
from .ui_replay import ReplayMixin
from .ui_theme import (
    BG,
    GREEN,
    MUTED,
    PANEL2,
    PURPLE,
    RED,
    TEXT,
    VIRTUAL_HEIGHT,
    VIRTUAL_WIDTH,
)

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "ai_mouse_lab.log"


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("ai_mouse_lab.app")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(
            LOG_FILE,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


LOGGER = _configure_logger()


class App(AimLabMixin, ReplayMixin, ctk.CTk):
    """Aim Lab recorder, personal profile builder and A/B replay UI."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"AI Mouse Lab v{__version__}")
        self.geometry("1440x880")
        self.minsize(1160, 720)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.init_aim_state()
        self.init_replay_state()
        self._build_shell()
        self.show("Aim Lab")
        LOGGER.info("Application started: version=%s", __version__)

    def report_callback_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        LOGGER.error(
            "Unhandled UI callback error",
            exc_info=(exc_type, exc_value, traceback),
        )
        status = getattr(self, "aim_status", None)
        if status is not None:
            try:
                status.configure(
                    text=(
                        f"Onverwachte fout: {exc_type.__name__}. "
                        "Zie logs/ai_mouse_lab.log"
                    ),
                    text_color=RED,
                )
            except TclError:
                LOGGER.debug("Status widget unavailable after callback failure")

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        nav = ctk.CTkFrame(
            self,
            width=170,
            fg_color="#0d131d",
            corner_radius=0,
        )
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        ctk.CTkLabel(
            nav,
            text="AI Mouse Lab",
            text_color=TEXT,
            font=("Segoe UI", 21, "bold"),
        ).pack(anchor="w", padx=16, pady=(24, 2))
        ctk.CTkLabel(nav, text=f"v{__version__}", text_color=MUTED).pack(
            anchor="w",
            padx=16,
            pady=(0, 18),
        )
        aim_button = ctk.CTkButton(
            nav,
            text="Aim Lab",
            anchor="w",
            height=42,
            fg_color=PURPLE,
            hover_color=PANEL2,
            command=lambda: self.show("Aim Lab"),
        )
        aim_button.pack(fill="x", padx=10, pady=3)
        self.nav_buttons["Aim Lab"] = aim_button
        ctk.CTkLabel(
            nav,
            text="● Data blijft lokaal",
            text_color=GREEN,
        ).pack(side="bottom", anchor="w", padx=16, pady=18)

        self.host = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.host.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.host.grid_rowconfigure(0, weight=1)
        self.host.grid_columnconfigure(0, weight=1)
        self._page_aim()
        self._page_results()

    def page(self, key: str, title: str, subtitle: str) -> ctk.CTkFrame:
        root = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        root.grid(row=0, column=0, sticky="nsew")
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(
            header,
            text=title,
            text_color=TEXT,
            font=("Segoe UI", 30, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=subtitle,
            text_color=MUTED,
        ).pack(anchor="w")
        body = ctk.CTkFrame(root, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        self.pages[key] = root
        return body

    def show(self, key: str) -> None:
        if key not in self.pages:
            key = "Aim Lab"
        self._pause_replay()
        for name, page in self.pages.items():
            page.grid_remove()
            button = self.nav_buttons.get(name)
            if button is not None:
                button.configure(
                    fg_color=PURPLE if name == key else "transparent"
                )
        self.pages[key].grid()
        if key == "Aim Lab":
            self.refresh_profile_status()
        elif key == "Results":
            self.refresh_results()

    @staticmethod
    def _canvas_box(canvas: ctk.CTkCanvas) -> tuple[float, float, float]:
        width = max(1.0, float(canvas.winfo_width()))
        height = max(1.0, float(canvas.winfo_height()))
        scale = min(width / VIRTUAL_WIDTH, height / VIRTUAL_HEIGHT)
        return (
            scale,
            (width - VIRTUAL_WIDTH * scale) / 2.0,
            (height - VIRTUAL_HEIGHT * scale) / 2.0,
        )

    def _to_canvas(
        self,
        canvas: ctk.CTkCanvas,
        x: float,
        y: float,
    ) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_box(canvas)
        return offset_x + x * scale, offset_y + y * scale

    def _to_virtual(
        self,
        canvas: ctk.CTkCanvas,
        x: float,
        y: float,
    ) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_box(canvas)
        return (
            (x - offset_x) / max(scale, 1e-9),
            (y - offset_y) / max(scale, 1e-9),
        )

    def _cancel_after(self, attribute: str) -> None:
        callback_id = getattr(self, attribute, None)
        if callback_id:
            try:
                self.after_cancel(callback_id)
            except TclError:
                LOGGER.debug("Callback already cancelled: %s", callback_id)
        setattr(self, attribute, None)

    @staticmethod
    def _show_error(action: str, error: BaseException, label: Any) -> None:
        LOGGER.exception("%s failed", action)
        try:
            label.configure(
                text=(
                    f"{action} mislukt: {error}\n"
                    "Zie logs/ai_mouse_lab.log"
                ),
                text_color=RED,
            )
        except TclError:
            LOGGER.debug("Error label unavailable for action: %s", action)

    def close_app(self) -> None:
        LOGGER.info("Application closing")
        self.aim_active = False
        self.aim_generation += 1
        self._cancel_aim_after()
        self._pause_replay()
        if self.aim_overlay is not None:
            self._close_aim_overlay()
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()
