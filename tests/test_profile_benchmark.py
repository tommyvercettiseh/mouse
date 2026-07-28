import unittest

from ai_mouse_lab.benchmark import generate_plan, simulate
from ai_mouse_lab.profile import build_profile


class ProfileBenchmarkTests(unittest.TestCase):
    def sample_trial(self):
        return {
            "target": {"radius": 18},
            "points": [{"t_ms": 0, "x": 0, "y": 0}, {"t_ms": 100, "x": 10, "y": 10}],
            "derived": {
                "reaction_ms": 20, "movement_time_ms": 100, "click_delay_ms": 15, "hold_ms": 70,
                "click_error_px": 2, "overshoot_px": 0, "correction_count": 0,
                "path_efficiency": 0.95, "peak_speed_px_s": 500, "distance_px": 100, "miss": False,
            },
        }

    def test_profile_builds(self):
        profile = build_profile([self.sample_trial()] * 10, [60, 70, 80])
        self.assertEqual(profile["trial_count"], 10)
        self.assertIn("movement_time_ms", profile["features"])

    def test_plan_reproducible(self):
        self.assertEqual(generate_plan(5, seed=123), generate_plan(5, seed=123))

    def test_simulation_count(self):
        profile = build_profile([self.sample_trial()] * 10, [])
        plan = generate_plan(7, seed=1)
        self.assertEqual(len(simulate(plan, profile)), 7)


if __name__ == "__main__":
    unittest.main()
