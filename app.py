from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ai_mouse_lab import __version__
from app_v1 import App as LegacyApp
from app_v1 import BG, GREEN, MUTED, PANEL2, PURPLE, TEXT


class App(LegacyApp):
    """Active Aim Lab application without the unreliable Free Record flow."""

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        nav = ctk.CTkFrame(self, width=170, fg_color="#0d131d", corner_radius=0)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        ctk.CTkLabel(
            nav,
            text="AI Mouse Lab",
            text_color=TEXT,
            font=("Segoe UI", 21, "bold"),
        ).pack(anchor="w", padx=16, pady=(24, 2))
        ctk.CTkLabel(nav, text=f"v{__version__}", text_color=MUTED).pack(
            anchor="w", padx=16, pady=(0, 18)
        )

        button = ctk.CTkButton(
            nav,
            text="Aim Lab",
            anchor="w",
            height=42,
            fg_color=PURPLE,
            hover_color=PANEL2,
            command=lambda: self.show("Aim Lab"),
        )
        button.pack(fill="x", padx=10, pady=3)
        self.nav_buttons["Aim Lab"] = button

        ctk.CTkLabel(nav, text="● Data blijft lokaal", text_color=GREEN).pack(
            side="bottom", anchor="w", padx=16, pady=18
        )

        self.host = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.host.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.host.grid_rowconfigure(0, weight=1)
        self.host.grid_columnconfigure(0, weight=1)
        self._page_aim()
        self._page_results()

    def close_app(self) -> None:
        self.aim_active = False
        self.aim_generation += 1
        self._cancel_aim_after()
        self._stop_replay()
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("dark")
    App().mainloop()


__all__ = ["App", "main"]


if __name__ == "__main__":
    main()
