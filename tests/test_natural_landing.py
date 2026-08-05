from __future__ import annotations

import math
import random
import unittest

from ai_mouse_lab.natural_landing import (
    FINAL_LANDING_SPEED_PX_S,
    MAX_LANDING_SPEED_PX_S,
    MIN_LANDING_DURATION_MS,
    refine_natural_landing,
)


class NaturalLandingTests(unittest.TestCase):
    def test_landing_slows_without_changing_route_or_endpoint(self):
        points = [
            {"t_ms": 0.0, "x": 0.0, "y": 0.0},
            {"t_ms": 100.0, "x": 850.0, "y": 390.0},
            {"t_ms": 110.0, "x": 930.0, "y": 405.0},
            {"t_ms": 120.0, "x": 970.0, "y": 410.0},
            {"t_ms": 130.0, "x": 980.0, "y": 410.0},
        ]
        trial = {
            "points": [dict(point) for point in points],
            "click": {
                "down_t_ms": 155.0,
                "up_t_ms": 235.0,
                "x": 980.0,
                "y": 410.0,
            },
        }

        refine_natural_landing(trial, random.Random(4))

        self.assertEqual(
            [(point["x"], point["y"]) for point in points],
            [(point["x"], point["y"]) for point in trial["points"]],
        )
        self.assertEqual((980.0, 410.0), (
            trial["points"][-1]["x"],
            trial["points"][-1]["y"],
        ))
        self.assertGreaterEqual(
            trial["landing"]["duration_ms"],
            MIN_LANDING_DURATION_MS,
        )
        self.assertAlmostEqual(
            80.0,
            trial["click"]["up_t_ms"] - trial["click"]["down_t_ms"],
        )

        start_index = trial["landing"]["start_index"]
        for first, second in zip(
            trial["points"][start_index:],
            trial["points"][start_index + 1 :],
        ):
            distance = math.hypot(second["x"] - first["x"], second["y"] - first["y"])
            elapsed = second["t_ms"] - first["t_ms"]
            self.assertLessEqual(
                distance / elapsed * 1000.0,
                MAX_LANDING_SPEED_PX_S + 1.0,
            )
        final_first, final_second = trial["points"][-2:]
        final_distance = math.hypot(
            final_second["x"] - final_first["x"],
            final_second["y"] - final_first["y"],
        )
        final_elapsed = final_second["t_ms"] - final_first["t_ms"]
        self.assertLessEqual(
            final_distance / final_elapsed * 1000.0,
            FINAL_LANDING_SPEED_PX_S + 1.0,
        )


if __name__ == "__main__":
    unittest.main()
