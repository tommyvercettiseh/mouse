from __future__ import annotations

import time
from typing import Any

from .metrics import derive_trial
from .ui_helpers import is_target_hit
from .v06 import _draw_virtual_scene, _to_virtual


def apply_hotfix(original_app: Any) -> None:
    def on_press(self: Any, event: Any) -> None:
        if not self.aim_active:
            return
        self.click_down = time.perf_counter()
        x, y = _to_virtual(self.canvas, float(event.x), float(event.y))
        self.append_point(x, y)

    def on_release(self: Any, event: Any) -> None:
        if not self.aim_active:
            return
        released = time.perf_counter()
        x, y = _to_virtual(self.canvas, float(event.x), float(event.y))
        self.append_point(x, y)
        target = self.plan[self.index]
        down_ms = round(((self.click_down or released) - self.target_spawn) * 1000, 3)
        up_ms = round((released - self.target_spawn) * 1000, 3)
        click = {"down_t_ms": down_ms, "up_t_ms": up_ms, "x": float(round(x)), "y": float(round(y))}

        if not is_target_hit(x, y, target):
            self.miss_clicks.append(click)
            self.click_down = None
            _draw_virtual_scene(original_app, self.canvas, target, self.points, original_app.PURPLE, len(self.miss_clicks))
            self.aim_status.configure(text=f"Target {self.index + 1}/{len(self.plan)}\nMisklikken: {len(self.miss_clicks)}\nRaak hetzelfde target")
            return

        target_data = {"index": target["index"], "x": target["x"], "y": target["y"], "radius": target["radius"]}
        start_data = {"x": float(round(self.start_point[0])), "y": float(round(self.start_point[1]))}
        derived = derive_trial(target_data, start_data, self.points, click)
        self.trials.append({
            "schema_version": 5,
            "target": target_data,
            "start": start_data,
            "points": list(self.points),
            "click": click,
            "miss_clicks": list(self.miss_clicks),
            "derived": derived,
        })
        self.index += 1
        self.show_target()

    original_app.App.on_press = on_press
    original_app.App.on_release = on_release
