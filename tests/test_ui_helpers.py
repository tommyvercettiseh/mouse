import unittest

from ai_mouse_lab.ui_helpers import (
    click_is_visible,
    is_target_hit,
    trace_coordinates,
    visible_miss_clicks,
)


class UIHelpersTests(unittest.TestCase):
    def test_hit_inside_circle(self):
        self.assertTrue(is_target_hit(110, 110, {"x": 100, "y": 100, "radius": 20}))

    def test_miss_outside_circle(self):
        self.assertFalse(is_target_hit(121, 100, {"x": 100, "y": 100, "radius": 20}))

    def test_trace_coordinates(self):
        self.assertEqual(
            trace_coordinates([{"x": 1, "y": 2}, {"x": 3, "y": 4}]),
            [1.0, 2.0, 3.0, 4.0],
        )

    def test_click_visibility_uses_press_time(self):
        click = {"down_t_ms": 120, "up_t_ms": 180, "x": 10, "y": 20}
        self.assertFalse(click_is_visible(click, 119.9))
        self.assertTrue(click_is_visible(click, 120.0))

    def test_visible_misses_filters_future_clicks(self):
        trial = {
            "miss_clicks": [
                {"down_t_ms": 50, "x": 1, "y": 1},
                {"down_t_ms": 150, "x": 2, "y": 2},
            ]
        }
        self.assertEqual(1, len(visible_miss_clicks(trial, 100)))
        self.assertEqual(2, len(visible_miss_clicks(trial, 200)))


if __name__ == "__main__":
    unittest.main()
