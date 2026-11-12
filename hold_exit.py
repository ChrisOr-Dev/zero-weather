"""Hold ESC for 3 seconds to quit, with a countdown bar (CardputerZero).

Keyboard reads evdev key events and remembers which keys are held. ExitHold
times an ESC hold; a release shorter than GRACE (the keyboard bounces when a
finger moves on a held key) still counts as held. bar() draws the countdown
band for the bottom of the screen.
"""
import os
import struct

from PIL import Image, ImageDraw

K_ESC = 1
HOLD = 3.0
GRACE = 0.4
BAR_H = 22
_EVENT = struct.calcsize('llHHi')


class Keyboard:
    def __init__(self, path='/dev/input/cardputer-zero-internal'):
        try:
            self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            self.fd = None
        self.down = set()

    def read(self):
        """Codes of keys pressed since the last call, in order."""
        if self.fd is None:
            return []
        try:
            buf = os.read(self.fd, _EVENT * 64)
        except BlockingIOError:
            return []
        pressed = []
        for i in range(0, len(buf) - _EVENT + 1, _EVENT):
            _, _, etype, code, value = struct.unpack_from('llHHi', buf, i)
            if etype != 1:
                continue
            if value == 0:
                self.down.discard(code)
            else:
                self.down.add(code)
                if value == 1:
                    pressed.append(code)
        return pressed


class ExitHold:
    def __init__(self):
        self.start = self.up = None

    def press(self, now):
        """ESC went down in a view where holding it quits."""
        if self.start is None:
            self.start = now
        self.up = None

    def cancel(self):
        self.start = self.up = None

    def progress(self, now, held):
        """0..1 while ESC is held (quit at 1), else None. held: ESC is down now."""
        if held:
            self.up = None
        elif self.up is None:
            self.up = now
        if self.start is None or (self.up is not None and now - self.up > GRACE):
            self.cancel()
            return None
        return (now - self.start) / HOLD


def bar(progress, width, font, bg=(24, 24, 28), fill=(200, 64, 56), fg=(240, 240, 240)):
    """The width x BAR_H countdown band."""
    img = Image.new('RGB', (width, BAR_H), bg)
    d = ImageDraw.Draw(img)
    if progress > 0:
        d.rectangle((0, 0, int(width * min(1, progress)), BAR_H), fill=fill)
    left = max(0.0, HOLD * (1 - progress))
    d.text((width / 2, BAR_H / 2), f'Keep holding ESC to exit  {left:.1f}s', font=font,
           fill=fg, anchor='mm')
    return img
