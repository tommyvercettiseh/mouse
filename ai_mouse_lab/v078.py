from __future__ import annotations

import time
from typing import Any


FRAME_MS = 16


def apply_patch(original_app: Any) -> None:
    def _cancel_replay_after(self: Any) -> None:
        after_id = getattr(self, "replay_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self.replay_after_id = None

    def replay_toggle(self: Any) -> None:
        trials_a, trials_b = self.replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            return

        if getattr(self, "replay_running", False):
            self.replay_elapsed_ms += (
                time.perf_counter() - self.replay_started_at
            ) * 1000.0 * self.replay_speed_value()
            self.replay_running = False
            _cancel_replay_after(self)
            self.replay_play_btn.configure(text="▶ Verder afspelen")
            self.replay_draw()
            return

        # When the full session already finished, restart from trial one.
        if getattr(self, "replay_session_finished", False):
            self.replay_trial_index = 0
            self.replay_elapsed_ms = 0.0
            self.replay_session_finished = False

        duration = self.replay_current_duration()
        if self.replay_elapsed_ms >= duration:
            if self.replay_trial_index < count - 1:
                self.replay_trial_index += 1
            else:
                self.replay_trial_index = 0
            self.replay_elapsed_ms = 0.0

        self.replay_started_at = time.perf_counter()
        self.replay_running = True
        self.replay_play_btn.configure(text="⏸ Pauze")
        replay_tick(self)

    def replay_reset(self: Any) -> None:
        _cancel_replay_after(self)
        self.replay_running = False
        self.replay_elapsed_ms = 0.0
        self.replay_started_at = 0.0
        self.replay_session_finished = False
        if hasattr(self, "replay_play_btn"):
            self.replay_play_btn.configure(text="▶ Alles afspelen")
        self.replay_draw()

    def replay_change_trial(self: Any, delta: int) -> None:
        trials_a, trials_b = self.replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            return
        _cancel_replay_after(self)
        self.replay_running = False
        self.replay_session_finished = False
        self.replay_trial_index = max(
            0,
            min(count - 1, self.replay_trial_index + delta),
        )
        self.replay_elapsed_ms = 0.0
        self.replay_started_at = 0.0
        self.replay_play_btn.configure(text="▶ Vanaf hier afspelen")
        self.replay_draw()

    def replay_tick(self: Any) -> None:
        if not getattr(self, "replay_running", False):
            self.replay_after_id = None
            return

        trials_a, trials_b = self.replay_trials()
        count = min(len(trials_a), len(trials_b))
        if count == 0:
            self.replay_running = False
            self.replay_after_id = None
            return

        speed = self.replay_speed_value()
        elapsed = self.replay_elapsed_ms + (
            time.perf_counter() - self.replay_started_at
        ) * 1000.0 * speed
        duration = max(1.0, self.replay_current_duration())

        if elapsed < duration:
            self.replay_draw(elapsed)
            self.replay_after_id = self.after(FRAME_MS, lambda: replay_tick(self))
            return

        # Draw the completed trial once before automatically advancing.
        self.replay_draw(duration)

        if self.replay_trial_index < count - 1:
            self.replay_trial_index += 1
            self.replay_elapsed_ms = 0.0
            self.replay_started_at = time.perf_counter()
            self.replay_draw(0.0)
            self.replay_after_id = self.after(FRAME_MS, lambda: replay_tick(self))
            return

        # End of the complete A/B session.
        self.replay_elapsed_ms = duration
        self.replay_running = False
        self.replay_session_finished = True
        self.replay_after_id = None
        self.replay_play_btn.configure(text="↻ Opnieuw afspelen")
        if hasattr(self, "replay_trial_label"):
            self.replay_trial_label.configure(
                text=f"Klaar · {count}/{count} trials afgespeeld"
            )

    original_app.App.replay_toggle = replay_toggle
    original_app.App.replay_reset = replay_reset
    original_app.App.replay_change_trial = replay_change_trial
    original_app.App.replay_tick = replay_tick
