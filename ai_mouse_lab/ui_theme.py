from __future__ import annotations

from typing import Any

import customtkinter as ctk

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


class Card(ctk.CTkFrame):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(
            master,
            fg_color=PANEL,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
            **kwargs,
        )
