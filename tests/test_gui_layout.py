import unittest

from riftbound.gui import OriginsGUI


class GuiLayoutTests(unittest.TestCase):
    def test_fan_step_keeps_single_card_full_width(self):
        self.assertEqual(OriginsGUI._fan_step(500, 84, 1), 84.0)

    def test_fan_step_overlaps_when_row_is_dense(self):
        step = OriginsGUI._fan_step(500, 84, 10)
        self.assertGreaterEqual(step, 18)
        self.assertLess(step, 84)
        # The last card's right edge stays within the configured row width.
        self.assertLessEqual(9 * step + 84, 500.01)

    def test_fan_step_never_returns_zero_for_a_narrow_region(self):
        # A narrow panel still needs an exposed strip for each card; a zero
        # step would stack widgets exactly and make all but the top card dead.
        self.assertGreaterEqual(OriginsGUI._fan_step(100, 84, 20), 18)


if __name__ == "__main__":
    unittest.main()
