from __future__ import annotations

import math
from typing import Any


ORANGE = "#f59e0b"
RED = "#ef4444"


def _segment_distance_to_point(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _set_target_color(canvas: Any, color: str) -> None:
    for item in canvas.find_withtag("target"):
        if canvas.type(item) == "oval":
            canvas.itemconfigure(item, fill=color)


def apply_patch(original_app: Any) -> None:
    old_show_target = original_app.App.show_target
    old_append_point = original_app.App.append_point

    def show_target(self: Any) -> None:
        self.live_target_entered = False
        self.live_overshoot_active = False
        self.live_overshoot_px = 0.0
        old_show_target(self)

    def append_point(self: Any, x: float, y: float) -> None:
        previous = self.points[-1] if getattr(self, "points", None) else None
        old_append_point(self, x, y)
        if not getattr(self, "aim_active", False) or not getattr(self, "plan", None):
            return

        target = self.plan[self.index]
        tx, ty = float(target["x"]), float(target["y"])
        radius = float(target["radius"])
        sx, sy = map(float, self.start_point)
        dx, dy = tx - sx, ty - sy
        distance = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / distance, dy / distance

        current_distance = math.hypot(float(x) - tx, float(y) - ty)
        if current_distance <= radius:
            self.live_target_entered = True
        elif previous is not None:
            if _segment_distance_to_point(
                float(previous["x"]), float(previous["y"]), float(x), float(y), tx, ty
            ) <= radius:
                self.live_target_entered = True

        along = (float(x) - sx) * ux + (float(y) - sy) * uy
        beyond_edge = along - (distance + radius)
        overshoot_now = bool(self.live_target_entered and current_distance > radius and beyond_edge > 0.0)

        if overshoot_now:
            self.live_overshoot_active = True
            self.live_overshoot_px = max(float(getattr(self, "live_overshoot_px", 0.0)), beyond_edge)
            _set_target_color(self.canvas, RED if beyond_edge >= 14.0 else ORANGE)
        elif getattr(self, "live_overshoot_active", False):
            _set_target_color(self.canvas, original_app.PURPLE)
            self.live_overshoot_active = False

        if hasattr(self, "aim_metrics_label"):
            base = self.aim_metrics_label.cget("text").split("\nLive detectie:")[0]
            if overshoot_now:
                state = f"OVERSHOOT {beyond_edge:.1f} px"
            elif self.live_target_entered:
                state = "Target gepasseerd / geraakt"
            else:
                state = "Nog niet gepasseerd"
            self.aim_metrics_label.configure(text=f"{base}\nLive detectie: {state}")

    original_app.App.show_target = show_target
    original_app.App.append_point = append_point
