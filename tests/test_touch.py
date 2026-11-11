import tempfile
import unittest
from pathlib import Path

from tv.state import StateStore
from tv.touch import (
    HoldDetector,
    MultiTouchTracker,
    ThreeFingerHoldDetector,
    TouchMapper,
    toggle_treehouse_channel,
)
from tv.menu import channel_at


class TouchTests(unittest.TestCase):
    def test_one_finger_hold_triggers_after_two_seconds(self):
        detector = HoldDetector(hold_seconds=2.0)

        self.assertFalse(detector.update(1, 4.0))
        self.assertFalse(detector.update(1, 5.9))
        self.assertTrue(detector.update(1, 6.0))
        self.assertFalse(detector.update(1, 7.0))

    def test_three_finger_hold_triggers_once_until_release(self):
        detector = ThreeFingerHoldDetector(hold_seconds=2.0)

        self.assertFalse(detector.update(3, 10.0))
        self.assertFalse(detector.update(3, 11.9))
        self.assertTrue(detector.update(3, 12.0))
        self.assertFalse(detector.update(3, 13.0))
        self.assertFalse(detector.update(0, 13.1))
        self.assertFalse(detector.update(3, 20.0))
        self.assertTrue(detector.update(3, 22.0))

    def test_two_fingers_never_start_the_gesture(self):
        detector = ThreeFingerHoldDetector(hold_seconds=2.0)

        self.assertFalse(detector.update(2, 1.0))
        self.assertFalse(detector.update(2, 5.0))
        self.assertFalse(detector.update(3, 6.0))
        self.assertFalse(detector.update(3, 7.9))

    def test_channel_action_toggles_both_directions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = StateStore(Path(temporary_directory) / "state.json")

            first = toggle_treehouse_channel(store)
            second = toggle_treehouse_channel(store)

            self.assertEqual(first, "treehouse-after-dark")
            self.assertEqual(second, "springfield-tv")

    def test_portrait_touch_coordinates_rotate_to_landscape(self):
        mapper = TouchMapper(0, 479, 0, 639, width=640, height=480, rotation=90)

        self.assertEqual(mapper.map(479, 0), (0, 0))
        self.assertEqual(mapper.map(0, 639), (639, 479))

    def test_channel_cards_have_large_hit_areas(self):
        self.assertEqual(channel_at((150, 200)), "springfield-tv")
        self.assertEqual(channel_at((480, 200)), "treehouse-after-dark")
        self.assertIsNone(channel_at((320, 450)))

    def test_touch_tracker_retains_release_position(self):
        tracker = MultiTouchTracker()
        tracker.select_slot(0)
        tracker.set_tracking_id(12)
        tracker.set_x(100)
        tracker.set_y(200)

        tracker.set_tracking_id(-1)

        self.assertEqual(tracker.active_count, 0)
        self.assertEqual(tracker.take_released_position(), (100, 200))
        self.assertIsNone(tracker.take_released_position())


if __name__ == "__main__":
    unittest.main()

