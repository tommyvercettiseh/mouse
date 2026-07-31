from __future__ import annotations

import math
import time
from typing import Any

from .metrics import derive_trial
from .ui_helpers import is_target_hit
from .v06 import _to_canvas, _to_virtual


UI_REFRESH_MS = 90.0
RENDER_INTERVAL_MS = 16.0


def _canvas_hit(canvas: Any, event_x: float, event_y: float, target: dict[str, Any]) -> bool:
    """Use the visible target geometry for click validation.

    This avoids stale virtual-coordinate mapping while the right panel is resizing.
    """
    tx, ty = _to_canvas(canvas, float(target["x"]), float(target["y"]))
    edge_x, _ = _to_canvas(canvas, float(target["x"]) + float(target["radius"]), float(target["y"]))
    radius = max(5.0, abs(edge_x - tx))
    return math.hypot(float(event_x) - tx, float(event_y) - ty) <= radius + 2.0


def apply_patch(original_app: Any) -> None:
    old_append_point = original_app.App.append_point
    old_show_target = original_app.App.show_target

    def show_target(self: Any) -> None:
        self._last_trace_render_ms = 0.0
        self._last_live_ui_ms = 0.0
        self._last_live_state = None
        old_show_target(self)

    def append_point(self: Any, x: float, y: float) -> None:
        """Record every point, but throttle expensive canvas/UI work."""
        if not getattr(self, "aim_active", False):
            return

        now_ms = time.perf_counter() * 1000.0
        point = {
            "t_ms": round((time.perf_counter() - self.target_spawn) * 1000, 3),
            "x": float(round(x)),
            "y": float(round(y)),
        }
        self.points.append(point)

        # Draw at ~60 FPS instead of rebuilding widgets for every sample.
        if now_ms - float(getattr(self, "_last_trace_render_ms", 0.0)) >= RENDER_INTERVAL_MS:
            from .v061 import _append_trace
            _append_trace(self.canvas, self.points, original_app.PURPLE)
            self._last_trace_render_ms = now_ms

        if not getattr(self, "plan", None) or self.index >= len(self.plan):
            return

        target = self.plan[self.index]
        tx, ty = float(target["x"]), float(target["y"])
        radius = float(target["radius"])
        current_distance = math.hypot(float(x) - tx, float(y) - ty)
        entered = current_distance <= radius or bool(getattr(self, "live_target_entered", False))
        self.live_target_entered = entered

        sx, sy = map(float, self.start_point)
        dx, dy = tx - sx, ty - sy
        distance = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / distance, dy / distance
        along = (float(x) - sx) * ux + (float(y) - sy) * uy
        beyond = along - (distance + radius)
        overshoot_now = entered and current_distance > radius and beyond > 0.0

        if overshoot_now:
            self.live_overshoot_px = max(float(getattr(self, "live_overshoot_px", 0.0)), beyond)
            state = f"OVERSHOOT {beyond:.1f} px"
            color = "#ef4444" if beyond >= 14.0 else "#f59e0b"
        elif entered:
            state = "Target gepasseerd / geraakt"
            color = original_app.PURPLE
        else:
            state = "Nog niet gepasseerd"
            color = original_app.PURPLE

        # Only mutate the existing target item when the state changes.
        if state != getattr(self, "_last_live_state", None):
            for item in self.canvas.find_withtag("target"):
                if self.canvas.type(item) == "oval":
                    self.canvas.itemconfigure(item, fill=color)
            self._last_live_state = state

        # Right panel text is deliberately throttled to prevent layout churn.
        if now_ms - float(getattr(self, "_last_live_ui_ms", 0.0)) >= UI_REFRESH_MS:
            if hasattr(self, "aim_metrics_label"):
                base = self.aim_metrics_label.cget("text").split("\nLive detectie:")[0]
                self.aim_metrics_label.configure(text=f"{base}\nLive detectie: {state}")
            self._last_live_ui_ms = now_ms

    def on_press(self: Any, event: Any) -> None:
        if not getattr(self, "aim_active", False):
            return
        self.click_down = time.perf_counter()
        x, y = _to_virtual(self.canvas, float(event.x), float(event.y))
        append_point(self, x, y)

    def on_release(self: Any, event: Any) -> None:
        if not getattr(self, "aim_active", False):
            return

        released = time.perf_counter()
        target = self.plan[self.index]
        x, y = _to_virtual(self.canvas, float(event.x), float(event.y))
        append_point(self, x, y)
        down_ms = round(((self.click_down or released) - self.target_spawn) * 1000, 3)
        up_ms = round((released - self.target_spawn) * 1000, 3)
        click = {
            "down_t_ms": down_ms,
            "up_t_ms": up_ms,
            "x": float(round(x)),
            "y": float(round(y)),
        }

        # Validate against the visible circle first, then keep the virtual check as fallback.
        hit = _canvas_hit(self.canvas, float(event.x), float(event.y), target) or is_target_hit(x, y, target)
        if not hit:
            self.miss_clicks.append(click)
            self.click_down = None
            if hasattr(self, "refresh_aim_metrics"):
                self.refresh_aim_metrics()
            self.aim_status.configure(
                text=f"Target {self.index + 1}/{len(self.plan)}\nMisklikken: {len(self.miss_clicks)}\nRaak hetzelfde target"
            )
            return

        target_data = {
            "index": target["index"],
            "x": target["x"],
            "y": target["y"],
            "radius": target["radius"],
        }
        start = {
            "x": float(round(self.start_point[0])),
            "y": float(round(self.start_point[1])),
        }
        derived = derive_trial(target_data, start, self.points, click)
        trial = {
            "schema_version": 5,
            "target": target_data,
            "start": start,
            "points": list(self.points),
            "click": click,
            "miss_clicks": list(self.miss_clicks),
            "derived": derived,
            "capture_mode": getattr(self, "active_capture_mode", "normal"),
        }
        self.trials.append(trial)
        self.last_overshoot_px = float(derived.get("overshoot_px", 0.0) or 0.0)
        self.index += 1
        if hasattr(self, "refresh_aim_metrics"):
            self.refresh_aim_metrics()
        show_target(self)

    original_app.App.show_target = show_target
    original_app.App.append_point = append_point
    original_app.App.on_press = on_press
    original_app.App.on_release = on_release
