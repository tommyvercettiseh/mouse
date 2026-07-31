from __future__ import annotations

from typing import Any, Callable


def _feedback_text(trial: dict[str, Any], prefix: str = "") -> str:
    derived = trial.get("derived", {})
    overshoot = float(derived.get("overshoot_px", 0) or 0)
    corrections = int(derived.get("correction_count", 0) or 0)
    entries = int(derived.get("entry_count", 0) or 0)
    exits = int(derived.get("exit_count", 0) or 0)
    label = "Geen overshoot" if overshoot <= 0.0 else f"Overshoot: {overshoot:.1f} px"
    return f"{prefix}{label} · correcties {corrections} · entries/exits {entries}/{exits}"


def _wrap_release(method: Callable[..., None], trials_name: str, status_name: str, prefix: str = "") -> Callable[..., None]:
    def wrapped(self: Any, event: Any) -> None:
        trials_before = len(getattr(self, trials_name, []))
        method(self, event)
        trials = getattr(self, trials_name, [])
        if len(trials) <= trials_before:
            return

        status = getattr(self, status_name, None)
        if status is None:
            return

        text = _feedback_text(trials[-1], prefix)
        status.configure(text=text)

        def restore() -> None:
            active = bool(getattr(self, "aim_active" if trials_name == "trials" else "bench_active", False))
            if not active:
                return
            if trials_name == "trials":
                status.configure(
                    text=f"Target {self.index + 1}/{len(self.plan)}\nPoints: {len(self.points)}\nMisklikken: {len(self.miss_clicks)}"
                )
            else:
                count = len(self.bench_plan.get("targets", []))
                status.configure(
                    text=f"Target {self.bench_index + 1}/{count} · misklikken {len(self.bench_miss_clicks)}"
                )

        self.after(1400, restore)

    return wrapped


def apply_patch(original_app: Any) -> None:
    original_app.App.on_release = _wrap_release(
        original_app.App.on_release,
        "trials",
        "aim_status",
    )
    original_app.App.bench_release = _wrap_release(
        original_app.App.bench_release,
        "bench_trials",
        "bench_status",
        "Benchmark · ",
    )
