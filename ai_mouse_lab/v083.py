from __future__ import annotations

from typing import Any


def _safe_derived(value: Any) -> dict[str, Any]:
    """Replay statistics require a mapping; legacy captures may contain a list."""
    return dict(value) if isinstance(value, dict) else {}


def apply_patch(original_app: Any) -> None:
    previous_normalize = original_app.App.normalize_replay_data

    def normalize_replay_data(self: Any) -> int:
        count = previous_normalize(self)
        for session_name in ("replay_a", "replay_b"):
            session = getattr(self, session_name, {})
            if not isinstance(session, dict):
                continue
            trials = session.get("trials", [])
            if not isinstance(trials, list):
                session["trials"] = []
                continue
            for trial in trials:
                if isinstance(trial, dict):
                    trial["derived"] = _safe_derived(trial.get("derived", {}))
        return min(
            len(getattr(self, "replay_a", {}).get("trials", [])),
            len(getattr(self, "replay_b", {}).get("trials", [])),
        )

    original_app.App.normalize_replay_data = normalize_replay_data
