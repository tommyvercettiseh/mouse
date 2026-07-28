import unittest

from ai_mouse_lab.benchmark import create_blind_export, generate_plan, plan_from_human_trials, simulate


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.plan = generate_plan(3, width=800, height=600, seed=42)
        self.profile = {
            "features": {
                "movement_time_ms": {"median": 250, "stdev": 25},
                "reaction_ms": {"median": 55, "stdev": 8},
                "click_delay_ms": {"median": 35, "stdev": 5},
                "hold_ms": {"median": 70, "stdev": 7},
                "click_error_px": {"stdev": 2},
                "path_efficiency": {"median": 0.94},
                "overshoot_px": {"median": 4},
                "correction_count": {"mean": 1},
            }
        }

    def test_plan_is_reproducible(self):
        self.assertEqual(self.plan, generate_plan(3, width=800, height=600, seed=42))

    def test_simulation_matches_trial_schema(self):
        trials = simulate(self.plan, self.profile, seed=99)
        self.assertEqual(3, len(trials))
        self.assertIn("points", trials[0])
        self.assertIn("derived", trials[0])
        self.assertIn("down_t_ms", trials[0]["click"])

    def test_plan_uses_real_human_starts(self):
        human = simulate(self.plan, self.profile, seed=100)
        human[0]["start"] = {"x": 123.0, "y": 234.0}
        effective = plan_from_human_trials(self.plan, human)
        self.assertEqual([123.0, 234.0], effective["targets"][0]["start"])

    def test_blind_export_same_schema_and_hidden_answer(self):
        human = simulate(self.plan, self.profile, seed=100)
        generated = simulate(self.plan, self.profile, seed=101)
        bundle = create_blind_export(self.plan, human, generated, seed=7)
        self.assertEqual(set(bundle["A"].keys()), set(bundle["B"].keys()))
        self.assertNotIn("source", bundle["A"])
        self.assertIn(bundle["private_answer"]["human"], {"A", "B"})
        self.assertEqual(3, bundle["A"]["trial_count"])

    def test_export_rejects_mismatched_counts(self):
        with self.assertRaises(ValueError):
            create_blind_export(self.plan, [], [], seed=7)


if __name__ == "__main__":
    unittest.main()
