from __future__ import annotations

import unittest

from ai_mouse_lab.metrics import derive_trial


class ApproachCorrectionTests(unittest.TestCase):
    def test_pre_target_steering_is_not_overshoot(self) -> None:
        target = {"x": 100.0, "y": 0.0, "radius": 10.0}
        start = {"x": 0.0, "y": 0.0}
        points = [
            {"t_ms": 0.0, "x": 0.0, "y": 0.0},
            {"t_ms": 10.0, "x": 15.0, "y": 0.0},
            {"t_ms": 20.0, "x": 30.0, "y": 8.0},
            {"t_ms": 30.0, "x": 45.0, "y": 15.0},
            {"t_ms": 40.0, "x": 60.0, "y": 8.0},
            {"t_ms": 50.0, "x": 75.0, "y": 3.0},
            {"t_ms": 60.0, "x": 90.0, "y": 0.0},
            {"t_ms": 70.0, "x": 100.0, "y": 0.0},
            {"t_ms": 90.0, "x": 100.0, "y": 0.0},
        ]
        click = {
            "down_t_ms": 70.0,
            "up_t_ms": 90.0,
            "x": 100.0,
            "y": 0.0,
        }

        derived = derive_trial(target, start, points, click)

        self.assertGreaterEqual(derived["approach_correction_count"], 1)
        self.assertGreater(derived["approach_deviation_px"], 3.0)
        self.assertEqual(derived["overshoot_px"], 0.0)
        self.assertEqual(derived["hold_ms"], 20.0)

    def test_straight_approach_has_no_correction(self) -> None:
        target = {"x": 100.0, "y": 0.0, "radius": 10.0}
        start = {"x": 0.0, "y": 0.0}
        points = [
            {"t_ms": float(index * 10), "x": float(index * 20), "y": 0.0}
            for index in range(6)
        ]
        click = {
            "down_t_ms": 50.0,
            "up_t_ms": 65.0,
            "x": 100.0,
            "y": 0.0,
        }

        derived = derive_trial(target, start, points, click)

        self.assertEqual(derived["approach_correction_count"], 0.0)
        self.assertEqual(derived["overshoot_px"], 0.0)
        self.assertEqual(derived["hold_ms"], 15.0)


if __name__ == "__main__":
    unittest.main()
