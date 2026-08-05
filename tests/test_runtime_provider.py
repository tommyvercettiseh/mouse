from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_mouse_lab.runtime import (
    API_VERSION,
    ProfileNotFoundError,
    create_plan,
    get_provider,
    resolve_profile_path,
)


def personal_profile() -> dict:
    return {
        "trial_count": 100,
        "miss_count": 0,
        "miss_rate": 0.0,
        "overshoot_rate": 0.08,
        "correction_rate": 0.12,
        "features": {
            "movement_time_ms": {"median": 500.0, "stdev": 80.0},
            "reaction_ms": {"median": 90.0, "stdev": 25.0},
            "click_delay_ms": {"median": 120.0, "stdev": 30.0, "p90": 220.0},
            "hold_ms": {"median": 95.0, "stdev": 12.0},
            "correction_count": {"mean": 0.2},
            "overshoot_positive_px": {"median": 8.0, "p90": 20.0},
        },
        "contexts": {},
        "route_templates": [],
        "click_model": {},
    }


class RuntimeProviderTests(unittest.TestCase):
    def test_complete_timeline_preserves_moves_and_click_timing(self):
        result = create_plan(
            (100.0, 200.0),
            {"left": 900.0, "top": 400.0, "right": 1000.0, "bottom": 480.0},
            padding_px=10.0,
            profile=personal_profile(),
            seed=42,
        )

        events = result["events"]
        self.assertEqual(API_VERSION, result["api_version"])
        self.assertEqual("ai_mouse_lab", result["provider"])
        self.assertEqual(sorted(event["t_ms"] for event in events), [event["t_ms"] for event in events])
        self.assertGreater(sum(event["type"] == "move" for event in events), 10)
        self.assertEqual(1, sum(event["type"] == "button_down" for event in events))
        self.assertEqual(1, sum(event["type"] == "button_up" for event in events))
        self.assertEqual(result["trial"]["click"]["down_t_ms"], next(
            event["t_ms"] for event in events if event["type"] == "button_down"
        ))
        self.assertEqual(result["trial"]["click"]["up_t_ms"], result["duration_ms"])
        self.assertGreater(result["trial"]["target"]["radius"], 0.0)
        self.assertLess(result["trial"]["target"]["radius"], 30.0)
        click = result["trial"]["click"]
        self.assertGreaterEqual(click["x"], 910.0)
        self.assertLessEqual(click["x"], 990.0)
        self.assertGreaterEqual(click["y"], 410.0)
        self.assertLessEqual(click["y"], 470.0)

    def test_same_seed_produces_the_same_full_plan(self):
        first = create_plan((10, 10), (700, 500, 25), profile=personal_profile(), seed=77)
        second = create_plan((10, 10), (700, 500, 25), profile=personal_profile(), seed=77)
        self.assertEqual(first, second)

    def test_rectangle_targets_vary_without_becoming_centre_locked(self):
        centres = []
        clicks = []
        bounds = {"left": 700.0, "top": 400.0, "right": 1000.0, "bottom": 520.0}
        for seed in range(12):
            result = create_plan(
                (100, 200),
                bounds,
                padding_px=20,
                profile=personal_profile(),
                seed=seed,
            )
            target = result["trial"]["target"]
            click = result["trial"]["click"]
            centres.append((round(target["x"], 1), round(target["y"], 1)))
            clicks.append((round(click["x"], 1), round(click["y"], 1)))
            self.assertGreaterEqual(click["x"], 720.0)
            self.assertLessEqual(click["x"], 980.0)
            self.assertGreaterEqual(click["y"], 420.0)
            self.assertLessEqual(click["y"], 500.0)

        self.assertGreater(len(set(centres)), 9)
        self.assertGreater(len(set(clicks)), 9)
        self.assertTrue(any(abs(x - 850.0) > 25.0 for x, _ in clicks))

    def test_screen_coordinates_are_scaled_through_personal_model_space(self):
        result = create_plan(
            (200, 150),
            (1600, 900, 40),
            coordinate_size=(2560, 1440),
            profile=personal_profile(),
            seed=12,
        )
        first_move = next(event for event in result["events"] if event["type"] == "move")
        self.assertAlmostEqual(200.0, first_move["x"])
        self.assertAlmostEqual(150.0, first_move["y"])
        self.assertEqual(30.0, result["trial"]["target"]["radius"])

    def test_profile_can_be_loaded_from_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "hesse.json"
            path.write_text(json.dumps(personal_profile()), encoding="utf-8")
            with patch.dict(os.environ, {"AI_MOUSE_LAB_PROFILE": str(path)}, clear=True):
                self.assertEqual(path, resolve_profile_path())
                result = create_plan((0, 0), (200, 200, 20), seed=2)
            self.assertEqual(str(path), result["profile_path"])

    def test_missing_explicit_profile_fails_clearly(self):
        with self.assertRaises(ProfileNotFoundError):
            resolve_profile_path("missing-profile.json")

    def test_provider_exposes_stable_manifest(self):
        provider = get_provider()
        self.assertEqual(API_VERSION, provider.api_version)
        self.assertIn("click_hold", provider.manifest()["capabilities"])


if __name__ == "__main__":
    unittest.main()
