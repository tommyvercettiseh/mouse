import unittest

from ai_mouse_lab.generator import simulate
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.profile_model import build_personal_profile


def upward_wiggle_trial():
    target = {"index": 0, "x": 300.0, "y": 100.0, "radius": 20.0}
    start = {"x": 0.0, "y": 100.0}
    points = [
        {"t_ms": 0.0, "x": 0.0, "y": 100.0},
        {"t_ms": 30.0, "x": 0.0, "y": 100.0},
        {"t_ms": 70.0, "x": 55.0, "y": 126.0},
        {"t_ms": 125.0, "x": 145.0, "y": 148.0},
        {"t_ms": 185.0, "x": 235.0, "y": 130.0},
        {"t_ms": 240.0, "x": 300.0, "y": 100.0},
        # Deliberate release drift that must not become movement or a wiggle.
        {"t_ms": 290.0, "x": 350.0, "y": -50.0},
    ]
    click = {
        "down_t_ms": 240.0,
        "up_t_ms": 290.0,
        "x": 350.0,
        "y": -50.0,
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


class RouteTemplateTests(unittest.TestCase):
    def test_template_contains_real_normalized_wiggle_shape(self):
        profile = build_personal_profile([upward_wiggle_trial()] * 20, [])
        template = profile["route_templates"][0]
        shape = template["points"]

        self.assertEqual(template["shape_version"], 1)
        self.assertEqual(shape[0], {"t": 0.0, "along": 0.0, "side": 0.0})
        self.assertEqual(shape[-1], {"t": 1.0, "along": 1.0, "side": 0.0})
        self.assertGreater(max(point["side"] for point in shape), 0.12)
        self.assertGreater(min(point["side"] for point in shape), -0.05)

    def test_generator_reuses_personal_wiggle_direction(self):
        profile = build_personal_profile([upward_wiggle_trial()] * 30, [])
        plan = {
            "seed": 21,
            "targets": [
                {
                    "index": index,
                    "start": [0.0, 100.0],
                    "target": [300.0, 100.0],
                    "radius": 20.0,
                }
                for index in range(12)
            ],
        }
        generated = simulate(plan, profile, seed=23)
        peak_offsets = [
            max(point["y"] - 100.0 for point in trial["points"])
            for trial in generated
        ]
        downward_offsets = [
            min(point["y"] - 100.0 for point in trial["points"])
            for trial in generated
        ]

        self.assertGreater(min(peak_offsets), 25.0)
        self.assertGreater(min(downward_offsets), -8.0)

    def test_release_drift_is_not_stored_in_route_template(self):
        profile = build_personal_profile([upward_wiggle_trial()] * 10, [])
        template = profile["route_templates"][0]

        self.assertLessEqual(max(point["along"] for point in template["points"]), 1.01)
        self.assertGreater(min(point["side"] for point in template["points"]), -0.05)


if __name__ == "__main__":
    unittest.main()
