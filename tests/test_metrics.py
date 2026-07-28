import unittest

from ai_mouse_lab.metrics import derive_trial, smooth_points, stats


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
        points = [{"t_ms": 0, "x": 0, "y": 0}, {"t_ms": 100, "x": 50, "y": 50}]
        click = {"down_t_ms": 100, "up_t_ms": 150, "x": 50, "y": 50}
        self.assertTrue(derive_trial(target, start, points, click)["miss"])


if __name__ == "__main__":
    unittest.main()
