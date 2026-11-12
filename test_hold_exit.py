import os
import struct
import unittest

from PIL import ImageFont

import hold_exit


class KeyboardTests(unittest.TestCase):
    def test_pressed_and_held(self):
        r, w = os.pipe()
        os.set_blocking(r, False)
        self.addCleanup(os.close, r)
        kbd = hold_exit.Keyboard('/nonexistent')
        kbd.fd = r
        for code, value in ((1, 1), (1, 2), (19, 1), (19, 0)):
            os.write(w, struct.pack('llHHi', 0, 0, 1, code, value))
        self.assertEqual(kbd.read(), [1, 19])  # repeats (value 2) are not presses
        self.assertEqual(kbd.down, {1})
        os.write(w, struct.pack('llHHi', 0, 0, 1, 1, 0))
        os.close(w)
        self.assertEqual(kbd.read(), [])
        self.assertEqual(kbd.down, set())


class ExitHoldTests(unittest.TestCase):
    def test_hold_three_seconds(self):
        h = hold_exit.ExitHold()
        self.assertIsNone(h.progress(0, False))
        h.press(10)
        self.assertEqual(h.progress(10, True), 0)
        self.assertAlmostEqual(h.progress(11.5, True), 0.5)
        self.assertGreaterEqual(h.progress(13, True), 1)

    def test_short_bounce_keeps_counting(self):
        h = hold_exit.ExitHold()
        h.press(0)
        self.assertAlmostEqual(h.progress(1, False), 1 / 3)
        self.assertAlmostEqual(h.progress(1.3, False), 1.3 / 3)
        h.press(1.35)  # key bounced back down: still timed from the first press
        self.assertGreaterEqual(h.progress(3, True), 1)

    def test_letting_go_cancels(self):
        h = hold_exit.ExitHold()
        h.press(0)
        h.progress(1, False)
        self.assertIsNotNone(h.progress(1 + hold_exit.GRACE - 0.05, False))
        self.assertIsNone(h.progress(1 + hold_exit.GRACE + 0.05, False))
        self.assertIsNone(h.progress(2, True))  # needs a new press
        h.press(5)
        h.cancel()
        self.assertIsNone(h.progress(5.1, True))

    def test_bar_sizes(self):
        font = ImageFont.load_default()
        for p in (0, 0.001, 0.5, 1.2):
            self.assertEqual(hold_exit.bar(p, 320, font).size, (320, hold_exit.BAR_H))


if __name__ == '__main__':
    unittest.main()
