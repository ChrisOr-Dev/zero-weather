"""Small UI glyphs drawn with PIL primitives, so they never depend on font coverage.

Every ic_* function draws into the s x s box whose top-left corner is (x, y).
"""
import math


def ic_pin(d, x, y, s, c, bg):
    r, cx = s * 0.36, x + s / 2
    d.polygon([(cx - r * 0.85, y + r * 1.3), (cx + r * 0.85, y + r * 1.3), (cx, y + s)], fill=c)
    d.ellipse((cx - r, y, cx + r, y + 2 * r), fill=c)
    k = r * 0.42
    d.ellipse((cx - k, y + r - k, cx + k, y + r + k), fill=bg)


def ic_gps(d, x, y, s, c):
    cx, cy, r, w = x + s / 2, y + s / 2, s * 0.3, max(1, round(s / 10))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=w)
    k = s * 0.1
    d.ellipse((cx - k, cy - k, cx + k, cy + k), fill=c)
    for seg in ((cx, y, cx, cy - r), (cx, cy + r, cx, y + s), (x, cy, cx - r, cy), (cx + r, cy, x + s, cy)):
        d.line(seg, fill=c, width=w)


def ic_thermo(d, x, y, s, c):
    cx, w, r = x + s / 2, s * 0.14, s * 0.25
    d.rounded_rectangle((cx - w, y, cx + w, y + s * 0.7), radius=int(w), fill=c)
    d.ellipse((cx - r, y + s - 2 * r, cx + r, y + s), fill=c)


def ic_drop(d, x, y, s, c):
    cx, r = x + s / 2, s * 0.32
    cy = y + s - r
    d.polygon([(cx, y), (cx - r * 0.95, cy - r * 0.3), (cx + r * 0.95, cy - r * 0.3)], fill=c)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)


def ic_wind(d, x, y, s, c):
    w = max(1, round(s / 9))
    d.line((x, y + s * 0.32, x + s * 0.62, y + s * 0.32), fill=c, width=w)
    d.arc((x + s * 0.49, y + s * 0.06, x + s * 0.75, y + s * 0.32), 200, 450, fill=c, width=w)
    d.line((x, y + s * 0.56, x + s, y + s * 0.56), fill=c, width=w)
    d.line((x, y + s * 0.78, x + s * 0.5, y + s * 0.78), fill=c, width=w)
    d.arc((x + s * 0.39, y + s * 0.78, x + s * 0.61, y + s), 270, 520, fill=c, width=w)


def ic_tri(d, x, y, s, c, up=True):
    if up:
        pts = [(x + s / 2, y + s * 0.15), (x + s * 0.1, y + s * 0.85), (x + s * 0.9, y + s * 0.85)]
    else:
        pts = [(x + s * 0.1, y + s * 0.15), (x + s * 0.9, y + s * 0.15), (x + s / 2, y + s * 0.85)]
    d.polygon(pts, fill=c)


def ic_gear(d, x, y, s, c, bg):
    cx, cy = x + s / 2, y + s / 2
    for i in range(8):
        a = i * math.pi / 4
        d.line((cx, cy, cx + math.cos(a) * s * 0.5, cy + math.sin(a) * s * 0.5),
               fill=c, width=max(2, round(s / 5)))
    r, k = s * 0.34, s * 0.13
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
    d.ellipse((cx - k, cy - k, cx + k, cy + k), fill=bg)


def _arrowhead(d, px, py, dx, dy, t, c):
    nx, ny = -dy, dx
    d.polygon([(px + dx * t, py + dy * t), (px + nx * t * 0.8, py + ny * t * 0.8),
               (px - nx * t * 0.8, py - ny * t * 0.8)], fill=c)


def ic_refresh(d, x, y, s, c):
    cx, cy, r = x + s / 2, y + s / 2, s * 0.36
    d.arc((cx - r, cy - r, cx + r, cy + r), 60, 330, fill=c, width=max(1, round(s / 8)))
    a = math.radians(330)
    _arrowhead(d, cx + math.cos(a) * r, cy + math.sin(a) * r, -math.sin(a), math.cos(a), s * 0.28, c)


def ic_power(d, x, y, s, c):
    cx, cy, r, w = x + s / 2, y + s * 0.55, s * 0.4, max(1, round(s / 8))
    d.arc((cx - r, cy - r, cx + r, cy + r), 300, 600, fill=c, width=w)
    d.line((cx, y, cx, cy), fill=c, width=w)


def ic_clock(d, x, y, s, c):
    cx, cy, r, w = x + s / 2, y + s / 2, s / 2 - 0.5, max(1, round(s / 10))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=w)
    d.line((cx, cy, cx, cy - r * 0.6), fill=c, width=w)
    d.line((cx, cy, cx + r * 0.5, cy), fill=c, width=w)


def ic_updown(d, x, y, s, c):
    ic_tri(d, x, y - s * 0.1, s * 0.55, c, True)
    ic_tri(d, x, y + s * 0.5, s * 0.55, c, False)


def ic_check(d, x, y, s, c):
    d.line((x, y + s * 0.55, x + s * 0.38, y + s * 0.9, x + s, y + s * 0.15),
           fill=c, width=max(2, round(s / 6)), joint='curve')


def ic_back(d, x, y, s, c):
    d.line((x + s * 0.3, y + s / 2, x + s, y + s / 2), fill=c, width=max(1, round(s / 7)))
    _arrowhead(d, x + s * 0.35, y + s / 2, -1, 0, s * 0.35, c)


def ic_chevron(d, x, y, s, c):
    d.line((x + s * 0.3, y, x + s * 0.75, y + s / 2, x + s * 0.3, y + s), fill=c, width=2)


def keycap(d, x, y, label, font, c):
    """A key outline with its label; returns the width drawn."""
    w = d.textlength(label, font=font) + 8
    d.rounded_rectangle((x, y, x + w, y + 13), radius=3, outline=c)
    d.text((x + w / 2, y + 7), label, font=font, fill=c, anchor='mm')
    return w


def key_hints(d, items, font, c, right, y):
    """Right-aligned key hints: items is [(key labels, icon function)]."""
    widths = [sum(d.textlength(k, font=font) + 10 for k in keys) + 12 for keys, _ in items]
    x = right - sum(widths) - 8 * (len(items) - 1)
    for (keys, icon), w in zip(items, widths):
        cx = x
        for k in keys:
            cx += keycap(d, cx, y, k, font, c) + 2
        icon(d, cx + 1, y + 1, 11, c)
        x += w + 8
