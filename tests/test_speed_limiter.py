from __future__ import annotations

import math
import unittest

from ai_mouse_lab.metrics import derive_trial
from ai_mouse_lab.speed_limiter import (
    maximum_segment_speed_px_s,
    retime_route_without_jumps,
)

CAP = 11_000.0


class SpeedLimiterTests(unittest.TestCase):
    def _assert_valid(self, before, after, click):
        self.assertLessEqual(maximum_segment_speed_px_s(after), CAP + 1e-6)
        self.assertTrue(
            math.isclose(after[-1]["x"], before[-1]["x"], abs_tol=0.001)
        )
        self.assertTrue(
            math.isclose(after[-1]["y"], before[-1]["y"], abs_tol=0.001)
        )
        self.assertGreaterEqual(click["down_t_ms"], after[-1]["t_ms"])
        for first, second in zip(after, after[1:]):
            self.assertGreater(second["t_ms"], first["t_ms"])

    def test_short_valid_movement_is_unchanged(self):
        points = [
            {"t_ms": 0.0, "x": 100.0, "y": 100.0},
            {"t_ms": 20.0, "x": 120.0, "y": 103.0},
            {"t_ms": 45.0, "x": 145.0, "y": 108.0},
        ]
        click_in = {
            "down_t_ms": 60.0,
            "up_t_ms": 140.0,
            "x": 145.0,
            "y": 108.0,
        }
        result, click, misses, changed = retime_route_without_jumps(
            points,
            click_in,
            cap_px_s=CAP,
        )
        self.assertFalse(changed)
        self.assertEqual(result, points)
        self.assertEqual(click, click_in)
        self.assertEqual(misses, [])
        self._assert_valid(points, result, click)

    def test_long_fast_movement_is_distributed_over_substeps(self):
        points = [
            {"t_ms": 0.0, "x": 0.0, "y": 0.0},
            {"t_ms": 20.0, "x": 600.0, "y": 80.0},
            {"t_ms": 45.0, "x": 1200.0, "y": 0.0},
        ]
        result, click, _, changed = retime_route_without_jumps(
            points,
            {
                "down_t_ms": 50.0,
                "up_t_ms": 120.0,
                "x": 1200.0,
                "y": 0.0,
            },
            cap_px_s=CAP,
        )
        self.assertTrue(changed)
        self.assertGreater(len(result), len(points) + 4)
        self.assertGreater(sum(point["x"] < 600.0 for point in result), 3)
        self.assertGreater(sum(point["x"] > 600.0 for point in result), 3)
        self._assert_valid(points, result, click)

    def test_very_fast_final_segment_has_no_last_step_catch_up(self):
        points = [
            {"t_ms": 0.0, "x": 10.0, "y": 10.0},
            {"t_ms": 100.0, "x": 400.0, "y": 40.0},
            {"t_ms": 101.0, "x": 900.0, "y": 100.0},
        ]
        result, click, _, changed = retime_route_without_jumps(
            points,
            {
                "down_t_ms": 102.0,
                "up_t_ms": 180.0,
                "x": 900.0,
                "y": 100.0,
            },
            cap_px_s=CAP,
        )
        self.assertTrue(changed)
        section_start = next(
            index
            for index, point in enumerate(result)
            if math.isclose(point["x"], 400.0, abs_tol=0.001)
        )
        final_section = result[section_start:]
        self.assertGreater(len(final_section), 3)
        distances = [
            math.hypot(
                second["x"] - first["x"],
                second["y"] - first["y"],
            )
            for first, second in zip(final_section, final_section[1:])
        ]
        self.assertLessEqual(distances[-1], max(distances[:-1]) + 1e-6)
        self._assert_valid(points, result, click)

    def test_click_and_miss_timing_move_with_the_route(self):
        points = [
            {"t_ms": 0.0, "x": 0.0, "y": 0.0},
            {"t_ms": 10.0, "x": 300.0, "y": 0.0},
            {"t_ms": 30.0, "x": 500.0, "y": 0.0},
        ]
        click_in = {
            "down_t_ms": 35.0,
            "up_t_ms": 95.0,
            "x": 500.0,
            "y": 0.0,
        }
        misses_in = [
            {
                "down_t_ms": 8.0,
                "up_t_ms": 12.0,
                "x": 220.0,
                "y": 0.0,
            }
        ]
        result, click, misses, changed = retime_route_without_jumps(
            points,
            click_in,
            misses_in,
            cap_px_s=CAP,
        )
        self.assertTrue(changed)
        self.assertGreater(click["down_t_ms"], click_in["down_t_ms"])
        self.assertGreater(
            misses[0]["down_t_ms"],
            misses_in[0]["down_t_ms"],
        )
        self.assertGreater(misses[0]["up_t_ms"], misses[0]["down_t_ms"])
        self._assert_valid(points, result, click)

    def test_final_spike_retiming_does_not_raise_measured_acceleration(self):
        target = {"x": 370.0, "y": 16.0, "radius": 18.0}
        start = {"x": 0.0, "y": 0.0}
        points = [
            {"t_ms": 0.0, "x": 0.0, "y": 0.0},
            {"t_ms": 30.0, "x": 20.0, "y": 0.0},
            {"t_ms": 60.0, "x": 70.0, "y": 3.0},
            {"t_ms": 90.0, "x": 150.0, "y": 6.0},
            {"t_ms": 120.0, "x": 250.0, "y": 10.0},
            {"t_ms": 150.0, "x": 350.0, "y": 15.0},
            {"t_ms": 151.0, "x": 370.0, "y": 16.0},
        ]
        click_in = {
            "down_t_ms": 152.0,
            "up_t_ms": 230.0,
            "x": 370.0,
            "y": 16.0,
        }
        before = derive_trial(target, start, points, click_in)
        result, click, _, changed = retime_route_without_jumps(
            points,
            click_in,
            cap_px_s=CAP,
        )
        after = derive_trial(target, start, result, click)

        self.assertTrue(changed)
        self.assertLessEqual(
            after["peak_accel_px_s2"],
            before["peak_accel_px_s2"],
        )
        self.assertLess(after["peak_speed_px_s"], before["peak_speed_px_s"])
        self._assert_valid(points, result, click)


if __name__ == "__main__":
    unittest.main()
