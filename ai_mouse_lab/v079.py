from __future__ import annotations

from typing import Any

import customtkinter as ctk

from .storage import PROFILES, read_json


VISIBLE_PAGES = ("Free Record", "Aim Lab")


def apply_patch(original_app: Any) -> None:
    old_build_shell = original_app.App._build_shell
    old_page_aim = original_app.App._page_aim

    def _page_aim(self: Any) -> None:
        old_page_aim(self)
        page = self.pages.get("Aim Lab")
        if page is None:
            return
        body_children = page.winfo_children()
        if not body_children:
            return
        body = body_children[-1]
        cards = body.winfo_children()
        if len(cards) < 2:
            return
        side = cards[1]

        ctk.CTkLabel(
            side,
            text="Persoonlijk profiel",
            text_color=original_app.TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", padx=18, pady=(10, 4))

        self.aim_build_profile_btn = ctk.CTkButton(
            side,
            text="Build Profile",
            fg_color=original_app.GREEN,
            hover_color="#2fb669",
            text_color="#07140d",
            height=42,
            command=self.build_profile_from_aim,
        )
        self.aim_build_profile_btn.pack(fill="x", padx=18, pady=(0, 6))

        self.aim_profile_status = ctk.CTkLabel(
            side,
            text="Nog geen profiel gebouwd",
            text_color=original_app.MUTED,
            justify="left",
            wraplength=250,
        )
        self.aim_profile_status.pack(anchor="w", padx=18, pady=(0, 10))
        self.refresh_aim_profile_status()

    def refresh_aim_profile_status(self: Any) -> None:
        label = getattr(self, "aim_profile_status", None)
        if label is None:
            return
        profile = read_json(PROFILES / "master_profile.json", {})
        if not profile:
            label.configure(text="Nog geen profiel gebouwd", text_color=original_app.MUTED)
            return
        label.configure(
            text=(
                f"Kwaliteit: {profile.get('quality_percent', 0)}%\n"
                f"Targets: {profile.get('trial_count', 0)}\n"
                f"Sterke contexten: "
                f"{sum(1 for value in profile.get('contexts', {}).values() if value.get('trial_count', 0) >= 8)}"
            ),
            text_color=original_app.GREEN,
        )

    def build_profile_from_aim(self: Any) -> None:
        button = getattr(self, "aim_build_profile_btn", None)
        if button is not None:
            button.configure(state="disabled", text="Profiel bouwen…")
        try:
            self.make_profile()
            self.refresh_aim_profile_status()
            if hasattr(self, "aim_status"):
                self.aim_status.configure(text="Persoonlijk profiel bijgewerkt", text_color=original_app.GREEN)
        finally:
            if button is not None:
                button.configure(state="normal", text="Build Profile")

    def show(self: Any, key: str) -> None:
        # Dashboard was the old startup page. Aim Lab is now the product home.
        if key not in self.pages or key in {"Dashboard", "Benchmark", "Profiles", "Settings", "Build Profile"}:
            key = "Aim Lab"

        for name, page in self.pages.items():
            page.grid_remove()
            button = self.buttons.get(name)
            if button is not None:
                try:
                    button.configure(fg_color=original_app.PURPLE if name == key else "transparent")
                except Exception:
                    pass

        self.pages[key].grid()
        if key == "Aim Lab":
            self.refresh_aim_profile_status()
        elif key == "Results":
            self.refresh_results()

    def _build_shell(self: Any) -> None:
        old_build_shell(self)

        # Keep internal pages available for existing logic, but remove every
        # non-core destination from the visible navigation.
        for name, button in list(self.buttons.items()):
            if name not in VISIBLE_PAGES:
                try:
                    button.pack_forget()
                except Exception:
                    pass

        # Aim Lab is the default product home.
        self.show("Aim Lab")

    original_app.App._page_aim = _page_aim
    original_app.App._build_shell = _build_shell
    original_app.App.show = show
    original_app.App.refresh_aim_profile_status = refresh_aim_profile_status
    original_app.App.build_profile_from_aim = build_profile_from_aim
