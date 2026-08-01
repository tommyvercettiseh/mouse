from __future__ import annotations

import unittest

from ai_mouse_lab.models import normalize_trials, trial_duration_ms, visible_points


class ModelTests(unittest.TestCase):
    def test_legacy_lists_are_normalized(self) -> None:
        trials = normalize_trials([
            {
                "target": [500, 300, 18],
                "start": [100, 100],
                "points": [[0, 100, 100], [50, 250, 200], [100, 500, 300]],
                "click": [100, 140, 500, 300],
                "derived": [],
            }
        ])
        self.assertEqual(len(trials), 1)
        trial = trials[0]
        self.assertIsInstance(trial["target"], dict)
        self.assertIsInstance(trial["points"][0], dict)
        self.assertIsInstance(trial["click"], dict)
        self.assertIsInstance(trial["derived"], dict)

    def test_duration_includes_click_release(self) -> None:
        trial = {
            "target": {"x": 10, "y": 10, "radius": 5},
            "start": {"x": 0, "y": 0},
            "points": [{"t_ms": 0, "x": 0, "y": 0}, {"t_ms": 100, "x": 10, "y": 10}],
            "click": {"down_t_ms": 110, "up_t_ms": 160, "x": 10, "y": 10},
        }
        self.assertEqual(trial_duration_ms(trial), 160)

    def test_visible_points_always_returns_first_point(self) -> None:
        trial = {
            "target": {"x": 10, "y": 10, "radius": 5},
            "start": {"x": 0, "y": 0},
            "points": [{"t_ms": 20, "x": 0, "y": 0}, {"t_ms": 40, "x": 10, "y": 10}],
            "click": {"down_t_ms": 40, "up_t_ms": 60, "x": 10, "y": 10},
        }
        self.assertEqual(len(visible_points(trial, 0)), 1)


if __name__ == "__main__":
    unittest.main()
