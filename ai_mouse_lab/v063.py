from __future__ import annotations

from typing import Any

import customtkinter as ctk


def apply_patch(original_app: Any) -> None:
    old_page_aim = original_app.App._page_aim
    old_start_aim = original_app.App.start_aim
    old_on_release = original_app.App.on_release

    def _metrics_text(self: Any) -> str:
        total = len(getattr(self, "trials", []))
        misses = sum(len(t.get("miss_clicks", [])) for t in getattr(self, "trials", []))
        overshoots = sum(1 for t in getattr(self, "trials", []) if float(t.get("derived", {}).get("overshoot_px", 0) or 0) > 0)
        corrections = sum(int(t.get("derived", {}).get("correction_count", 0) or 0) for t in getattr(self, "trials", []))
        last = getattr(self, "last_overshoot_px", None)
        last_text = "—" if last is None else f"{last:.1f} px"
        current = min(getattr(self, "index", 0) + 1, max(1, len(getattr(self, "plan", []))))
        count = max(1, len(getattr(self, "plan", [])))
        return (
            f"Target: {current}/{count}\n"
            f"Voltooid: {total}\n"
            f"Misklikken: {misses + len(getattr(self, 'miss_clicks', []))}\n"
            f"Overshoots: {overshoots}\n"
            f"Correcties: {corrections}\n"
            f"Laatste overshoot: {last_text}"
        )

    def _refresh_metrics(self: Any) -> None:
        if hasattr(self, "aim_metrics_label"):
            self.aim_metrics_label.configure(text=_metrics_text(self))

    def _page_aim(self: Any) -> None:
        old_page_aim(self)
        body = self.pages["Aim Lab"].winfo_children()[-1]
        children = body.winfo_children()
        if len(children) < 2:
            return
        side = children[1]
        ctk.CTkLabel(
            side,
            text="Live metingen",
            text_color=original_app.TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 4))
        self.aim_metrics_label = ctk.CTkLabel(
            side,
            text="Target: 0/0\nVoltooid: 0\nMisklikken: 0\nOvershoots: 0\nCorrecties: 0\nLaatste overshoot: —",
            text_color=original_app.MUTED,
            justify="left",
            font=("Consolas", 13),
        )
        self.aim_metrics_label.pack(anchor="w", padx=18, pady=(0, 12))

    def start_aim(self: Any) -> None:
        self.last_overshoot_px = None
        old_start_aim(self)
        _refresh_metrics(self)

    def on_release(self: Any, event: Any) -> None:
        before = len(getattr(self, "trials", []))
        old_on_release(self, event)
        after = len(getattr(self, "trials", []))
        if after > before:
            derived = self.trials[-1].get("derived", {})
            self.last_overshoot_px = float(derived.get("overshoot_px", 0) or 0)
        _refresh_metrics(self)

    original_app.App._page_aim = _page_aim
    original_app.App.start_aim = start_aim
    original_app.App.on_release = on_release
    original_app.App.refresh_aim_metrics = _refresh_metrics
