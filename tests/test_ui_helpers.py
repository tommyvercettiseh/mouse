import unittest

from ai_mouse_lab.ui_helpers import is_target_hit, trace_coordinates


class UIHelpersTests(unittest.TestCase):
    def test_hit_inside_circle(self):
        target = {"x": 100, "y": 100, "radius": 20}
        self.assertTrue(is_target_hit(110, 110, target))

    def test_miss_outside_circle(self):
        target = {"x": 100, "y": 100, "radius": 20}
        self.assertFalse(is_target_hit(121, 100, target))

    def test_trace_coordinates(self):
        points = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
        self.assertEqual(trace_coordinates(points), [1.0, 2.0, 3.0, 4.0])


if __name__ == "__main__":
    unittest.main()
