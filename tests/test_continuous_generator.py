from __future__ import annotations

import math
import unittest

from ai_mouse_lab.continuous_generator import simulate


class ContinuousGeneratorTests(unittest.TestCase):
    def _profile(self):
        return {
            "trial_count": 100,
            "miss_count": 0,
            "miss_rate": 0.0,
            "overshoot_rate": 0.0,
            "correction_rate": 0.0,
            "features": {
                "movement_time_ms": {"median": 500.0, "stdev": 80.0},
                "reaction_ms": {"median": 90.0, "stdev": 25.0},
                "click_delay_ms": {"median": 120.0, "stdev": 30.0, "p90": 220.0},
                "hold_ms": {"median": 95.0, "stdev": 12.0},
                "correction_count": {"mean": 0.0},
                "overshoot_positive_px": {"median": 8.0, "p90": 20.0},
            },
            "contexts": {},
            "route_templates": [],
            "click_model": {},
        }

    def _plan(self, count=20):
        return {
            "seed": 11,
            "targets": [
                {
                    "index": index,
                    "start": [100.0, 500.0],
                    "target": [1500.0, 500.0],
                    "radius": 20.0,
                }
                for index in range(count)
            ],
        }

    def test_routes_fill_continuous_lateral_band(self):
        trials = simulate(self._plan(30), self._profile(), seed=42)
        midpoints = []
        for trial in trials:
            point = min(trial["points"], key=lambda p: abs(p["x"] - 800.0))
            midpoints.append(float(point["y"]))
        rounded = {round(value, 1) for value in midpoints}
        self.assertGreater(len(rounded), 12)
        self.assertGreater(max(midpoints) - min(midpoints), 8.0)

    def test_click_delay_and_peak_speed_are_bounded(self):
        trials = simulate(self._plan(40), self._profile(), seed=99)
        for trial in trials:
            self.assertGreaterEqual(trial["derived"]["click_delay_ms"], 20.0)
            self.assertLessEqual(trial["derived"]["click_delay_ms"], 380.0)
            self.assertLessEqual(trial["derived"]["peak_speed_px_s"], 11650.0)

    def test_route_still_ends_at_click(self):
        trial = simulate(self._plan(1), self._profile(), seed=7)[0]
        end = trial["points"][-1]
        self.assertTrue(math.isclose(end["x"], trial["click"]["x"], abs_tol=0.001))
        self.assertTrue(math.isclose(end["y"], trial["click"]["y"], abs_tol=0.001))

    def test_no_segment_jumps_when_time_is_tight(self):
        trial = simulate(self._plan(1), self._profile(), seed=123)[0]
        points = trial["points"]
        for first, second in zip(points, points[1:]):
            dt = float(second["t_ms"]) - float(first["t_ms"])
            distance = math.hypot(
                float(second["x"]) - float(first["x"]),
                float(second["y"]) - float(first["y"]),
            )
            self.assertGreater(dt, 0.0)
            self.assertLessEqual(distance / dt * 1000.0, 11650.0)


if __name__ == "__main__":
    unittest.main()
