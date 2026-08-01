import unittest

from ai_mouse_lab.metrics import derive_trial, movement_points, smooth_points, stats


class MetricsTests(unittest.TestCase):
    def test_stats_percentiles(self):
        result = stats([1, 2, 3, 4, 5])
        self.assertEqual(result["median"], 3)
        self.assertEqual(result["min"], 1)
        self.assertEqual(result["max"], 5)

    def test_smoothing_keeps_count(self):
        points = [{"t_ms": i * 8, "x": i, "y": i} for i in range(10)]
        self.assertEqual(len(smooth_points(points)), len(points))

    def test_derive_hit_and_hold(self):
        target = {"x": 100, "y": 0, "radius": 10}
        start = {"x": 0, "y": 0}
        points = [
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 50, "x": 20, "y": 0},
            {"t_ms": 100, "x": 60, "y": 0},
            {"t_ms": 150, "x": 96, "y": 0},
        ]
        click = {"down_t_ms": 170, "up_t_ms": 240, "x": 96, "y": 0}
        result = derive_trial(target, start, points, click)
        self.assertFalse(result["miss"])
        self.assertEqual(result["hold_ms"], 70)
        self.assertGreater(result["path_efficiency"], 0.9)

    def test_derive_miss(self):
        target = {"x": 100, "y": 100, "radius": 10}
        start = {"x": 0, "y": 0}
        points = [
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 100, "x": 50, "y": 50},
        ]
        click = {"down_t_ms": 100, "up_t_ms": 150, "x": 50, "y": 50}
        self.assertTrue(derive_trial(target, start, points, click)["miss"])

    def test_braking_uses_sustained_slowdown(self):
        target = {"x": 100, "y": 0, "radius": 10}
        start = {"x": 0, "y": 0}
        points = [
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 40, "x": 8, "y": 0},
            {"t_ms": 80, "x": 28, "y": 0},
            {"t_ms": 120, "x": 55, "y": 0},
            {"t_ms": 160, "x": 76, "y": 0},
            {"t_ms": 200, "x": 88, "y": 0},
            {"t_ms": 240, "x": 94, "y": 0},
            {"t_ms": 280, "x": 98, "y": 0},
        ]
        click = {"down_t_ms": 300, "up_t_ms": 360, "x": 98, "y": 0}
        result = derive_trial(target, start, points, click)

        self.assertGreater(result["braking_start_ms"], 0)
        self.assertGreater(result["braking_duration_ms"], 0)
        self.assertGreater(result["peak_decel_px_s2"], 0)
        self.assertIn("speed_at_2r_px_s", result)
        self.assertIn("speed_at_1r_px_s", result)
        self.assertIn("speed_at_half_r_px_s", result)
        self.assertIn("final_100ms_speed_px_s", result)
        self.assertLess(result["slowdown_ratio"], 1.0)

    def test_post_click_drift_does_not_pollute_movement_metrics(self):
        target = {"x": 100, "y": 0, "radius": 20}
        start = {"x": 0, "y": 0}
        points = [
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 50, "x": 40, "y": 0},
            {"t_ms": 100, "x": 80, "y": 0},
            {"t_ms": 150, "x": 130, "y": 30},
        ]
        click = {"down_t_ms": 100, "up_t_ms": 150, "x": 130, "y": 30}
        result = derive_trial(target, start, points, click)

        self.assertAlmostEqual(result["click_error_px"], 20.0, places=3)
        self.assertAlmostEqual(result["click_distance_px"], 80.0, places=3)
        self.assertAlmostEqual(result["path_length_px"], 80.0, places=3)
        self.assertAlmostEqual(result["path_efficiency"], 1.0, places=3)
        self.assertEqual(result["overshoot_px"], 0.0)

    def test_movement_points_interpolates_mouse_down_position(self):
        points = [
            {"t_ms": 0, "x": 0, "y": 0},
            {"t_ms": 80, "x": 64, "y": 0},
            {"t_ms": 120, "x": 96, "y": 0},
        ]
        click = {"down_t_ms": 100, "up_t_ms": 140, "x": 110, "y": 5}
        route = movement_points(points, click, {"x": 0, "y": 0})

        self.assertEqual(route[-1]["t_ms"], 100)
        self.assertAlmostEqual(route[-1]["x"], 80.0, places=3)
        self.assertAlmostEqual(route[-1]["y"], 0.0, places=3)


if __name__ == "__main__":
    unittest.main()
