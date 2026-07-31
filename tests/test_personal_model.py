import unittest

from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.personal_model import build_personal_profile, context_key


def trial(points, target=None, start=None, mode="normal"):
    target = target or {"x": 100, "y": 0, "radius": 10}
    start = start or {"x": 0, "y": 0}
    click = {"down_t_ms": points[-1]["t_ms"] + 20, "up_t_ms": points[-1]["t_ms"] + 90, "x": target["x"], "y": target["y"]}
    return {
        "target": target,
        "start": start,
        "points": points,
        "click": click,
        "miss_clicks": [],
        "capture_mode": mode,
        "derived": derive_trial(target, start, points, click),
    }


class PersonalModelTests(unittest.TestCase):
    def test_directional_overshoot_is_detected(self):
        points = [
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 50, "x": 60, "y": 0},
            {"t_ms": 100, "x": 116, "y": 0},
            {"t_ms": 150, "x": 100, "y": 0},
        ]
        result = trial(points)["derived"]
        self.assertGreater(result["overshoot_px"], 0)
        self.assertGreaterEqual(result["correction_count"], 1)

    def test_fast_segment_crossing_counts_as_entry(self):
        points = [
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 40, "x": 80, "y": 0},
            {"t_ms": 80, "x": 120, "y": 0},
            {"t_ms": 120, "x": 100, "y": 0},
        ]
        result = trial(points)["derived"]
        self.assertGreaterEqual(result["entry_count"], 1)

    def test_detection_tests_do_not_train_profile(self):
        normal = trial([
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 60, "x": 50, "y": 0},
            {"t_ms": 120, "x": 100, "y": 0},
        ])
        test = trial([
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 60, "x": 50, "y": 0},
            {"t_ms": 120, "x": 100, "y": 0},
        ], mode="test")
        profile = build_personal_profile([normal, test], [])
        self.assertEqual(profile["trial_count"], 1)
        self.assertEqual(profile["rejected_reasons"]["test_mode"], 1)

    def test_contexts_separate_distance_target_and_direction(self):
        self.assertNotEqual(context_key(100, 10, 0), context_key(800, 10, 0))
        self.assertNotEqual(context_key(100, 10, 0), context_key(100, 36, 0))
        self.assertNotEqual(context_key(100, 10, 0), context_key(100, 10, 3.14))


if __name__ == "__main__":
    unittest.main()
