import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_mouse_lab import heatmap_flow


class HeatmapFlowTests(unittest.TestCase):
    def test_repeats_exact_latest_target_plan_with_unique_seeds(self):
        source_trials = [
            {
                "target": {"index": 0, "x": 100, "y": 120, "radius": 18},
                "start": {"x": 20, "y": 30},
                "points": [
                    {"t_ms": 0, "x": 20, "y": 30},
                    {"t_ms": 100, "x": 100, "y": 120},
                ],
                "click": {
                    "down_t_ms": 100,
                    "up_t_ms": 180,
                    "x": 100,
                    "y": 120,
                },
                "click_position_source": "mouse_down",
                "miss_clicks": [],
                "derived": {"movement_time_ms": 100},
            },
            {
                "target": {"index": 1, "x": 500, "y": 420, "radius": 26},
                "start": {"x": 100, "y": 120},
                "points": [
                    {"t_ms": 0, "x": 100, "y": 120},
                    {"t_ms": 100, "x": 500, "y": 420},
                ],
                "click": {
                    "down_t_ms": 100,
                    "up_t_ms": 180,
                    "x": 500,
                    "y": 420,
                },
                "click_position_source": "mouse_down",
                "miss_clicks": [],
                "derived": {"movement_time_ms": 100},
            },
        ]
        profile = {"trial_count": 20, "features": {}}
        observed_plans = []
        observed_seeds = []

        def fake_simulate(plan, _profile, seed):
            observed_plans.append(plan)
            observed_seeds.append(seed)
            return source_trials

        with tempfile.TemporaryDirectory() as temporary:
            heatmaps = Path(temporary)
            with (
                patch.object(heatmap_flow, "HEATMAPS", heatmaps),
                patch.object(heatmap_flow, "read_json", return_value=profile),
                patch.object(
                    heatmap_flow,
                    "latest_aim_session",
                    return_value=(Path("latest-session"), source_trials),
                ),
                patch.object(
                    heatmap_flow,
                    "contextual_simulate",
                    side_effect=fake_simulate,
                ),
                patch.object(heatmap_flow.random, "randint", return_value=1000),
            ):
                folder, payload = heatmap_flow.create_heatmap_runs(3)

            self.assertEqual(payload["run_count"], 3)
            self.assertEqual(payload["target_count"], 2)
            self.assertEqual(payload["movement_count"], 6)
            self.assertEqual(len(payload["runs"]), 3)
            self.assertEqual(observed_seeds, [1001, 1002, 1003])
            self.assertTrue(all(plan == observed_plans[0] for plan in observed_plans))
            self.assertEqual(observed_plans[0]["targets"][0]["start"], [20.0, 30.0])
            self.assertEqual(observed_plans[0]["targets"][1]["target"], [500.0, 420.0])
            self.assertTrue((folder / "heatmap_runs.json").exists())
            self.assertTrue((folder / "source.json").exists())

    def test_run_count_is_capped_at_500(self):
        self.assertEqual(max(1, min(500, 900)), 500)


if __name__ == "__main__":
    unittest.main()
