import unittest

from ai_mouse_lab.ui_helpers import is_target_hit, trace_coordinates


class UIHelpersTests(unittest.TestCase):
    def test_hit_inside_circle(self):
        self.assertTrue(is_target_hit(110, 110, {"x": 100, "y": 100, "radius": 20}))

    def test_miss_outside_circle(self):
        self.assertFalse(is_target_hit(121, 100, {"x": 100, "y": 100, "radius": 20}))

    def test_trace_coordinates(self):
        self.assertEqual(trace_coordinates([{"x": 1, "y": 2}, {"x": 3, "y": 4}]), [1.0, 2.0, 3.0, 4.0])


if __name__ == "__main__":
    unittest.main()
