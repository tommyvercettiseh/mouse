from __future__ import annotations

import random
import unittest

from ai_mouse_lab.braking import _analyze_approach_corrections
from ai_mouse_lab.generator import _candidate_templates, generate_trial


def _stats(value: float, stdev: float = 0.0, p90: float | None = None) -> dict[str, float]:
    high = value if p90 is None else p90
    return {
        "mean": value,
        "median": value,
        "stdev": stdev,
        "p10": value,
        "p90": high,
        "min": value,
        "max": high,
    }


def _profile(template: dict | None = None) -> dict:
    features = {
        "movement_time_ms": _stats(700.0, 80.0, 820.0),
        "reaction_ms": _stats(150.0, 20.0, 180.0),
        "click_delay_ms": _stats(300.0, 20.0, 340.0),
        "hold_ms": _stats(100.0, 8.0, 112.0),
        "correction_count": _stats(0.0),
        "overshoot_positive_px": _stats(18.0, 6.0, 35.0),
    }
    return {
        "trial_count": 100,
        "miss_count": 0,
        "miss_rate": 0.0,
        "overshoot_rate": 0.0,
        "correction_rate": 0.0,
        "features": features,
        "contexts": {},
        "route_templates": [template] if template else [],
        "click_model": {},
    }


class ModelQualityTests(unittest.TestCase):
    def test_template_click_delay_is_not_added_twice(self) -> None:
        template = {
            "shape_version": 1,
            "distance_px": 100.0,
            "radius": 20.0,
            "angle": 0.0,
            "duration_ms": 500.0,
            "path_efficiency": 1.0,
            "quality_score": 1.0,
            "points": [
                {"t": 0.0, "along": 0.0, "side": 0.0},
                {"t": 0.5, "along": 0.5, "side": 0.01},
                {"t": 0.8, "along": 0.82, "side": 0.0},
                {"t": 1.0, "along": 1.0, "side": 0.0},
            ],
        }
        trial = generate_trial(
            {"index": 0, "start": [0.0, 0.0], "target": [100.0, 0.0], "radius": 20.0},
            _profile(template),
            random.Random(4),
        )
        self.assertLess(trial["derived"]["click_delay_ms"], 250.0)

    def test_bad_template_is_rejected(self) -> None:
        template = {
            "shape_version": 1,
            "distance_px": 100.0,
            "radius": 20.0,
            "angle": 0.0,
            "duration_ms": 500.0,
            "path_efficiency": 0.35,
            "points": [
                {"t": 0.0, "along": 0.0, "side": 0.0},
                {"t": 0.5, "along": 0.4, "side": 0.8},
                {"t": 1.0, "along": 1.0, "side": 0.0},
            ],
        }
        self.assertEqual(_candidate_templates(_profile(template), 100.0, 20.0, 0.0), [])

    def test_micro_jitter_does_not_count_as_approach_correction(self) -> None:
        velocities = [
            {
                "t_ms": float(index * 10),
                "x": float(index * 8),
                "y": 0.18 if index % 2 else -0.18,
                "speed_px_s": 800.0,
            }
            for index in range(1, 12)
        ]
        result = _analyze_approach_corrections(
            velocities,
            target_x=100.0,
            target_y=0.0,
            radius=5.0,
        )
        self.assertEqual(result["approach_correction_count"], 0.0)
        self.assertLess(result["approach_angle_change_deg"], 170.0)

    def test_real_lateral_correction_is_kept(self) -> None:
        coordinates = [
            (8.0, 0.0),
            (16.0, 2.0),
            (24.0, 5.0),
            (32.0, 9.0),
            (40.0, 13.0),
            (48.0, 10.0),
            (56.0, 6.0),
            (64.0, 3.0),
            (72.0, 1.0),
            (80.0, 0.0),
            (88.0, 0.0),
        ]
        velocities = [
            {
                "t_ms": float(index * 10),
                "x": x,
                "y": y,
                "speed_px_s": 850.0,
            }
            for index, (x, y) in enumerate(coordinates, start=1)
        ]
        result = _analyze_approach_corrections(
            velocities,
            target_x=100.0,
            target_y=0.0,
            radius=5.0,
        )
        self.assertGreaterEqual(result["approach_correction_count"], 1.0)
        self.assertGreater(result["approach_deviation_px"], 5.0)


if __name__ == "__main__":
    unittest.main()
