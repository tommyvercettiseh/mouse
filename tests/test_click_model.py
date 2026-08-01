import math
import random
import unittest

from ai_mouse_lab.click_model import build_click_model, sample_click_offset
from ai_mouse_lab.generator import simulate
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.profile_model import build_personal_profile


def make_trial(click_x: float, click_y: float, radius: float = 20.0):
    target = {"index": 0, "x": 100.0, "y": 100.0, "radius": radius}
    start = {"x": 0.0, "y": 100.0}
    points = [
        {"t_ms": 0.0, "x": 0.0, "y": 100.0},
        {"t_ms": 70.0, "x": 45.0, "y": 100.0},
        {"t_ms": 140.0, "x": 88.0, "y": 100.0},
        {"t_ms": 190.0, "x": click_x, "y": click_y},
    ]
    click = {
        "down_t_ms": 210.0,
        "up_t_ms": 280.0,
        "x": click_x,
        "y": click_y,
    }
    return {
        "capture_mode": "normal",
        "target": target,
        "start": start,
        "points": points,
        "click": click,
        "miss_clicks": [],
        "derived": derive_trial(target, start, points, click),
    }


class ClickModelTests(unittest.TestCase):
    def test_profile_preserves_directional_click_bias(self):
        trials = [make_trial(112.0, 104.0) for _ in range(20)]
        model = build_click_model(trials)
        self.assertEqual(20, model["sample_count"])
        self.assertGreater(model["overall"]["x_ratio"]["mean"], 0.5)
        self.assertGreater(model["overall"]["y_ratio"]["mean"], 0.1)

    def test_exact_mouse_down_event_beats_sample_interpolation(self):
        trial = make_trial(118.0, 100.0)
        trial["points"] = [
            {"t_ms": 0.0, "x": 0.0, "y": 100.0},
            {"t_ms": 210.0, "x": 100.0, "y": 100.0},
            {"t_ms": 280.0, "x": 130.0, "y": 120.0},
        ]
        trial["click_position_source"] = "mouse_down"
        model = build_click_model([trial])

        self.assertAlmostEqual(model["overall"]["x_ratio"]["mean"], 0.9, places=3)
        self.assertAlmostEqual(model["overall"]["y_ratio"]["mean"], 0.0, places=3)

    def test_sampling_is_not_forced_to_center(self):
        trials = [make_trial(112.0, 104.0) for _ in range(20)]
        model = build_click_model(trials)
        rng = random.Random(42)
        samples = [sample_click_offset(model, 20.0, rng) for _ in range(30)]
        average_distance = sum(math.hypot(x, y) for x, y in samples) / len(samples)
        self.assertGreater(average_distance, 8.0)
        self.assertGreater(sum(x for x, _ in samples) / len(samples), 8.0)

    def test_generator_uses_click_model_and_finishes_at_click(self):
        profile = build_personal_profile(
            [make_trial(112.0, 104.0) for _ in range(30)],
            [],
        )
        plan = {
            "seed": 1,
            "targets": [
                {
                    "index": index,
                    "start": [0.0, 100.0],
                    "target": [100.0, 100.0],
                    "radius": 20.0,
                }
                for index in range(20)
            ],
        }
        generated = simulate(plan, profile, seed=7)
        offsets = [
            trial["click"]["x"] - trial["target"]["x"]
            for trial in generated
        ]
        self.assertGreater(sum(offsets) / len(offsets), 8.0)
        self.assertTrue(
            all(
                math.hypot(
                    trial["click"]["x"] - 100.0,
                    trial["click"]["y"] - 100.0,
                )
                <= 19.3
                for trial in generated
            )
        )
        for trial in generated:
            self.assertAlmostEqual(
                trial["points"][-1]["x"],
                trial["click"]["x"],
                places=3,
            )
            self.assertAlmostEqual(
                trial["points"][-1]["y"],
                trial["click"]["y"],
                places=3,
            )

    def test_generated_miss_has_visible_recovery_route(self):
        profile = build_personal_profile(
            [make_trial(112.0, 104.0) for _ in range(40)],
            [],
        )
        profile["miss_count"] = 100
        profile["trial_count"] = 100
        plan = {
            "seed": 3,
            "targets": [
                {
                    "index": index,
                    "start": [0.0, 100.0],
                    "target": [100.0, 100.0],
                    "radius": 20.0,
                }
                for index in range(100)
            ],
        }
        generated = simulate(plan, profile, seed=11)
        missed = [trial for trial in generated if trial["miss_clicks"]]
        self.assertTrue(missed)
        for trial in missed:
            miss = trial["miss_clicks"][0]
            self.assertGreater(
                math.hypot(miss["x"] - 100.0, miss["y"] - 100.0),
                20.0,
            )
            self.assertAlmostEqual(
                trial["points"][-1]["x"],
                trial["click"]["x"],
                places=3,
            )
            self.assertAlmostEqual(
                trial["points"][-1]["y"],
                trial["click"]["y"],
                places=3,
            )
            self.assertGreater(
                trial["click"]["down_t_ms"],
                miss["up_t_ms"],
            )


if __name__ == "__main__":
    unittest.main()
