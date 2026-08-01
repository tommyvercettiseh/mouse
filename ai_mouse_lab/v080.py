from __future__ import annotations

from typing import Any

from .storage import COMPARISONS, read_json


def apply_patch(original_app: Any) -> None:
    old_refresh_results = original_app.App.refresh_results

    def refresh_results(self: Any) -> None:
        """Keep a freshly generated latest-recording A/B comparison loaded.

        The previous flow generated A and B correctly, then immediately called the
        legacy refresh routine, which could clear the in-memory comparison and show
        'Geen benchmark'. A loaded pair is now authoritative. Disk scanning is only
        used when no pair is loaded yet.
        """
        replay_a = getattr(self, "replay_a", {})
        replay_b = getattr(self, "replay_b", {})
        trials_a = replay_a.get("trials", []) if isinstance(replay_a, dict) else []
        trials_b = replay_b.get("trials", []) if isinstance(replay_b, dict) else []

        if trials_a and trials_b:
            if hasattr(self, "replay_trial_index"):
                count = min(len(trials_a), len(trials_b))
                self.replay_trial_index = max(0, min(count - 1, int(getattr(self, "replay_trial_index", 0))))
            if hasattr(self, "replay_trial_label"):
                self.replay_trial_label.configure(text=f"Laatste Aim Lab-opname · {min(len(trials_a), len(trials_b))} targets")
            if hasattr(self, "replay_draw"):
                self.replay_draw()
            return

        folders = sorted((path for path in COMPARISONS.glob("*") if path.is_dir()), reverse=True)
        folder = next((path for path in folders if (path / "A.json").exists() and (path / "B.json").exists()), None)
        if folder is None:
            if hasattr(self, "replay_trial_label"):
                self.replay_trial_label.configure(text="Nog geen A/B-vergelijking")
            if hasattr(self, "replay_draw"):
                self.replay_draw()
            return

        self.replay_folder = folder
        self.replay_a = read_json(folder / "A.json", {})
        self.replay_b = read_json(folder / "B.json", {})
        self.replay_trial_index = 0
        self.replay_elapsed_ms = 0.0
        self.replay_running = False
        if hasattr(self, "replay_reset"):
            self.replay_reset()
        else:
            old_refresh_results(self)

    original_app.App.refresh_results = refresh_results
