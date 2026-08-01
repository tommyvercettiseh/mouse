import unittest

from ai_mouse_lab.generator import simulate
from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.models import normalize_trials, trial_duration_ms, visible_points
from ai_mouse_lab.profile_model import FEATURES, build_personal_profile
from ai_mouse_lab.schema import normalize_session, validate_trial


class CoreV1Tests(unittest.TestCase):
    def sample_trial(self):
        target = {"index": 0, "x": 300.0, "y": 100.0, "radius": 20.0}
        start = {"x": 0.0, "y": 100.0}
        points = [
            {"t_ms": 0.0, "x": 0.0, "y": 100.0},
            {"t_ms": 40.0, "x": 20.0, "y": 100.0},
            {"t_ms": 90.0, "x": 120.0, "y": 102.0},
            {"t_ms": 140.0, "x": 230.0, "y": 101.0},
            {"t_ms": 190.0, "x": 292.0, "y": 100.0},
        ]
        click = {"down_t_ms": 210.0, "up_t_ms": 280.0, "x": 298.0, "y": 101.0}
        derived = derive_trial(target, start, points, click)
        return {
            "schema_version": 7,
            "capture_mode": "normal",
            "target": target,
            "start": start,
            "points": points,
            "click": click,
            "miss_clicks": [],
            "derived": derived,
        }

    def test_metrics_include_complete_movement_model(self):
        derived = self.sample_trial()["derived"]
        required = {
            "peak_speed_px_s",
            "peak_accel_px_s2",
            "peak_decel_px_s2",
            "peak_jerk_px_s3",
            "braking_start_ms",
            "braking_distance_px",
            "braking_duration_ms",
            "target_approach_speed_px_s",
            "speed_at_entry_px_s",
            "slowdown_ratio",
            "radial_overshoot_px",
            "directional_overshoot_px",
        }
        self.assertTrue(required.issubset(derived))

    def test_legacy_list_points_are_normalized(self):
        legacy = {
            "target": [300, 100, 20],
            "start": [0, 100],
            "points": [[0, 0, 100], [100, 150, 100], [210, 298, 101]],
            "click": [210, 280, 298, 101],
            "derived": [],
        }
        session = normalize_session([legacy])
        trial = session["trials"][0]
        self.assertIsInstance(trial["points"][0], dict)
        self.assertIsInstance(trial["derived"], dict)
        self.assertEqual([], validate_trial(trial))

    def test_models_recompute_missing_derived(self):
        trial = self.sample_trial()
        trial["derived"] = []
        normalized = normalize_trials([trial])[0]
        self.assertIsInstance(normalized["derived"], dict)
        self.assertIn("movement_time_ms", normalized["derived"])

    def test_replay_helpers_are_safe(self):
        trial = self.sample_trial()
        self.assertGreater(trial_duration_ms(trial), 0)
        visible = visible_points(trial, 100.0)
        self.assertGreaterEqual(len(visible), 1)
        self.assertLessEqual(len(visible), len(trial["points"]))

    def test_profile_registers_all_features(self):
        profile = build_personal_profile([self.sample_trial()] * 10, [70.0, 80.0])
        for name in FEATURES:
            self.assertIn(name, profile["features"])
        self.assertEqual(10, profile["trial_count"])

    def test_generator_returns_valid_trials(self):
        profile = build_personal_profile([self.sample_trial()] * 20, [])
        plan = {
            "schema_version": 7,
            "seed": 42,
            "width": 1920,
            "height": 1080,
            "targets": [
                {"index": 0, "start": [100, 100], "target": [800, 500], "radius": 18},
                {"index": 1, "start": [800, 500], "target": [1200, 700], "radius": 26},
            ],
        }
        generated = simulate(plan, profile, seed=99)
        self.assertEqual(2, len(generated))
        for trial in generated:
            self.assertEqual([], validate_trial(trial))
            self.assertIn("slowdown_ratio", trial["derived"])


if __name__ == "__main__":
    unittest.main()
