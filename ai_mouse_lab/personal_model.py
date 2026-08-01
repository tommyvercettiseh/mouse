from __future__ import annotations

from typing import Any

from .generator import simulate
from .profile_model import FEATURES, build_personal_profile, context_key, quality_reason


def contextual_simulate(
    plan: dict[str, Any],
    profile: dict[str, Any],
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Compatibility name for the integrated context-aware generator."""
    return simulate(plan, profile, seed)


__all__ = [
    "FEATURES",
    "build_personal_profile",
    "context_key",
    "contextual_simulate",
    "quality_reason",
]
