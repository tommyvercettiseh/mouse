from __future__ import annotations

import time
from typing import Any

FRAME_MS = 16


def _trial_duration(trial: dict[str, Any]) -> float:
    values: list[float] = []
    for point in trial.get("points", []):
        try:
            values.append(float(point.get("t_ms", 0) or 0))
        except (TypeError, ValueError):
            pass
    click = trial.get("click", {})
    for key in ("down_t_ms", "up_t_ms"):
        try:
            values.append(float(click.get(key, 0) or 0))
        except (TypeError, ValueError):
            pass
    return max(values, default=0.0)


def apply_patch(original_app: Any) -> None:
    old_build_shell = original_app.App._build_shell

    def _cancel(self: Any) -> None:
        after_id = getattr(self, "replay_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self.replay_after_id = None

    def _duration(self: Any) -> float:
        trials_a, trials_b = self.replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            return 0.0
        index = max(0, min(count - 1, int(getattr(self, "replay_trial_index", 0))))
        return max(16.0, _trial_duration(trials_a[index]), _trial_duration(trials_b[index]))

    def replay_toggle(self: Any) -> None:
        try:
            trials_a, trials_b = self.replay_trials()
            count = min(len(trials_a), len(trials_b))
            if count == 0:
                if hasattr(self, "replay_trial_label"):
                    self.replay_trial_label.configure(text="Geen A/B-data geladen")
                return

            if getattr(self, "replay_running", False):
                self.replay_elapsed_ms += (time.perf_counter() - self.replay_started_at) * 1000.0 * self.replay_speed_value()
                self.replay_running = False
                _cancel(self)
                self.replay_play_btn.configure(text="▶ Verder afspelen")
                self.replay_draw(self.replay_elapsed_ms)
                return

            if getattr(self, "replay_session_finished", False):
                self.replay_trial_index = 0
                self.replay_elapsed_ms = 0.0
                self.replay_session_finished = False

            duration = _duration(self)
            if self.replay_elapsed_ms >= duration:
                self.replay_elapsed_ms = 0.0
                if self.replay_trial_index < count - 1:
                    self.replay_trial_index += 1
                else:
                    self.replay_trial_index = 0

            self.replay_started_at = time.perf_counter()
            self.replay_running = True
            self.replay_play_btn.configure(text="⏸ Pauze")
            replay_tick(self)
        except Exception as exc:
            self.replay_running = False
            _cancel(self)
            if hasattr(self, "replay_trial_label"):
                self.replay_trial_label.configure(text=f"Replayfout: {type(exc).__name__}: {exc}")

    def replay_tick(self: Any) -> None:
        if not getattr(self, "replay_running", False):
            self.replay_after_id = None
            return
        try:
            trials_a, trials_b = self.replay_trials()
            count = min(len(trials_a), len(trials_b))
            if count == 0:
                self.replay_running = False
                self.replay_after_id = None
                return

            speed = max(0.1, float(self.replay_speed_value()))
            elapsed = self.replay_elapsed_ms + (time.perf_counter() - self.replay_started_at) * 1000.0 * speed
            duration = _duration(self)

            if elapsed < duration:
                self.replay_draw(elapsed)
                self.replay_after_id = self.after(FRAME_MS, lambda: replay_tick(self))
                return

            self.replay_draw(duration)
            if self.replay_trial_index < count - 1:
                self.replay_trial_index += 1
                self.replay_elapsed_ms = 0.0
                self.replay_started_at = time.perf_counter()
                self.replay_draw(0.0)
                self.replay_after_id = self.after(FRAME_MS, lambda: replay_tick(self))
                return

            self.replay_elapsed_ms = duration
            self.replay_running = False
            self.replay_session_finished = True
            self.replay_after_id = None
            self.replay_play_btn.configure(text="↻ Opnieuw afspelen")
            self.replay_trial_label.configure(text=f"Klaar · {count}/{count} targets afgespeeld")
        except Exception as exc:
            self.replay_running = False
            _cancel(self)
            if hasattr(self, "replay_trial_label"):
                self.replay_trial_label.configure(text=f"Replayfout: {type(exc).__name__}: {exc}")

    def _build_shell(self: Any) -> None:
        old_build_shell(self)
        button = getattr(self, "replay_play_btn", None)
        if button is not None:
            button.configure(command=self.replay_toggle, text="▶ Alles afspelen")

    original_app.App._build_shell = _build_shell
    original_app.App.replay_toggle = replay_toggle
    original_app.App.replay_tick = replay_tick
    original_app.App.replay_current_duration = _duration
