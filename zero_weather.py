#!/usr/bin/python3
"""Weather for the M5Stack CardputerZero (320x170 LCD), data from Open-Meteo.

Location: the Cap LoRa-1262 GNSS (/dev/ttyS0, NMEA) when enabled and it has
a fix, otherwise the fixed location in ~/.config/zero-weather.json (set from
the in-app settings screen; Toronto if absent).

Usage:
  zero_weather.py                  run on the LCD (S settings, R refresh, hold ESC 3s to exit)
  zero_weather.py --fetch          fetch once and print the result
  zero_weather.py --preview out.png               render one frame to PNG
  zero_weather.py --make-icon out.png             write the 100x100 launcher icon
"""
import json
import math
import os
import sys
import threading
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

import icons
import net
from gps import parse_nmea, read_gps  # noqa: F401  (parse_nmea re-exported for tests)

W, H = 320, 170
HOME = os.path.expanduser('~')
DATA = os.path.join(HOME, '.local/share/zero-weather/weather.json')
CONFIG = os.path.join(HOME, '.config/zero-weather.json')
DEFAULT_PLACE = {'name': 'Toronto', 'lat': 43.65, 'lon': -79.38}
URL = ('https://api.open-meteo.com/v1/forecast'
       '?latitude={lat:.4f}&longitude={lon:.4f}'
       '&current=temperature_2m,apparent_temperature,relative_humidity_2m,'
       'weather_code,wind_speed_10m,is_day'
       '&daily=weather_code,temperature_2m_max,temperature_2m_min,'
       'precipitation_probability_max'
       '&timezone=auto&forecast_days=3&timeformat=unixtime')
POLL = 15 * 60
STALE_AFTER = 60 * 60
FB = '/dev/fb0'
KBD = '/dev/input/cardputer-zero-internal'
KEY_ESC, KEY_R, KEY_S = 1, 19, 31

FONT_DIRS = ['/usr/share/APPLaunch/share/font', os.path.dirname(os.path.abspath(__file__))]

BG = (14, 18, 26)
FG = (236, 238, 242)
DIM = (138, 148, 165)
LINE = (40, 48, 62)
ACCENT = (110, 180, 255)
SUN = (255, 196, 64)
CLOUD = (200, 208, 222)
DARK_CLOUD = (130, 140, 158)
RAIN = (90, 160, 255)
SNOW = (235, 245, 255)
BOLT = (255, 220, 80)
WARN = (232, 178, 70)
HOT = (226, 86, 74)
GPS_TAG = (120, 200, 130)


def font(name, size):
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


F_TITLE = font('JetBrainsMono-Bold.ttf', 13)
F_TEMP = font('Montserrat-Bold.ttf', 40)
F_TEXT = font('JetBrainsMono-Regular.ttf', 12)
F_SMALL = font('JetBrainsMono-Regular.ttf', 11)
F_DAY = font('JetBrainsMono-Bold.ttf', 11)
F_TAG = font('JetBrainsMono-Bold.ttf', 10)


# WMO weather code -> (icon kind, label)
def describe(code):
    if code == 0:
        return 'clear', 'Clear'
    if code in (1, 2):
        return 'partly', 'Partly cloudy' if code == 2 else 'Mostly clear'
    if code == 3:
        return 'cloud', 'Overcast'
    if code in (45, 48):
        return 'fog', 'Fog'
    if 51 <= code <= 57:
        return 'rain', 'Drizzle'
    if 61 <= code <= 67 or 80 <= code <= 82:
        return 'rain', 'Heavy rain' if code in (65, 67, 82) else 'Rain'
    if 71 <= code <= 77 or code in (85, 86):
        return 'snow', 'Snow'
    if code >= 95:
        return 'storm', 'Thunderstorm'
    return 'cloud', f'Code {code}'


def draw_cloud(d, cx, cy, s, color):
    r = s * 0.22
    d.ellipse((cx - s * 0.42, cy - r * 0.2, cx - s * 0.42 + 2 * r, cy + r * 1.8), fill=color)
    d.ellipse((cx - s * 0.22, cy - s * 0.30, cx + s * 0.18, cy + s * 0.10), fill=color)
    d.ellipse((cx + s * 0.02, cy - s * 0.16, cx + s * 0.42, cy + s * 0.22), fill=color)
    d.rounded_rectangle((cx - s * 0.42 + r * 0.6, cy + s * 0.02, cx + s * 0.40, cy + r * 1.8),
                        radius=int(r), fill=color)


def draw_sun(d, cx, cy, s, color):
    r = s * 0.2
    for i in range(8):
        a = i * math.pi / 4
        d.line((cx + math.cos(a) * r * 1.5, cy + math.sin(a) * r * 1.5,
                cx + math.cos(a) * r * 2.2, cy + math.sin(a) * r * 2.2),
               fill=color, width=max(2, int(s / 18)))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)


def draw_moon(d, cx, cy, s, color, bg):
    r = s * 0.24
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    d.ellipse((cx - r * 0.35, cy - r * 1.15, cx + r * 1.45, cy + r * 0.65), fill=bg)


def draw_icon(d, cx, cy, s, kind, day=True, bg=BG):
    w = max(2, int(s / 16))
    if kind == 'clear':
        (draw_sun if day else lambda *a: draw_moon(*a, bg))(d, cx, cy, s, SUN if day else CLOUD)
        return
    if kind == 'partly':
        if day:
            draw_sun(d, cx - s * 0.14, cy - s * 0.14, s * 0.8, SUN)
        else:
            draw_moon(d, cx - s * 0.14, cy - s * 0.16, s * 0.8, CLOUD, bg)
        draw_cloud(d, cx + s * 0.06, cy + s * 0.12, s * 0.8, CLOUD)
        return
    if kind == 'fog':
        for i, k in enumerate((-0.24, -0.08, 0.08, 0.24)):
            off = s * 0.08 if i % 2 else 0
            d.line((cx - s * 0.38 + off, cy + s * k, cx + s * 0.38 - (s * 0.08 - off), cy + s * k),
                   fill=CLOUD, width=w + 1)
        return
    top = cy - s * 0.12
    draw_cloud(d, cx, top, s, DARK_CLOUD if kind in ('rain', 'storm') else CLOUD)
    base = top + s * 0.32
    if kind == 'rain':
        for x in (-0.2, 0.0, 0.2):
            d.line((cx + s * x, base, cx + s * (x - 0.06), base + s * 0.2), fill=RAIN, width=w)
    elif kind == 'snow':
        for x in (-0.2, 0.0, 0.2):
            rr = max(2, s * 0.045)
            d.ellipse((cx + s * x - rr, base + s * 0.08 - rr, cx + s * x + rr, base + s * 0.08 + rr),
                      fill=SNOW)
    elif kind == 'storm':
        p = [(cx + s * 0.04, base - s * 0.02), (cx - s * 0.1, base + s * 0.14),
             (cx + s * 0.0, base + s * 0.14), (cx - s * 0.08, base + s * 0.3),
             (cx + s * 0.14, base + s * 0.08), (cx + s * 0.03, base + s * 0.08)]
        d.polygon(p, fill=BOLT)


def fmt_ago(seconds):
    s = max(0, int(seconds))
    if s < 60:
        return 'just now'
    if s < 3600:
        return f'{s // 60}m ago'
    return f'{s // 3600}h ago'


def deg(v, unit='C'):
    """Format a Celsius value (Open-Meteo's unit) in the chosen unit."""
    return f'{round(v * 9 / 5 + 32 if unit == "F" else v)}°'


def load():
    try:
        with open(DATA) as f:
            return json.load(f)
    except Exception:
        return None


def save(data):
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    tmp = DATA + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, DATA)


def load_config():
    cfg = dict(DEFAULT_PLACE, use_gps=True, unit='C')
    try:
        with open(CONFIG) as f:
            raw = json.load(f)
        cfg.update(name=str(raw['name']), lat=float(raw['lat']), lon=float(raw['lon']))
        cfg['use_gps'] = bool(raw.get('use_gps', True))
        if raw.get('unit') in ('C', 'F'):
            cfg['unit'] = raw['unit']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return cfg


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + '.tmp'
    with open(tmp, 'w') as f:
        json.dump({k: cfg[k] for k in ('name', 'lat', 'lon', 'use_gps', 'unit')}, f)
    os.replace(tmp, CONFIG)


def locate():
    cfg = load_config()
    gps = read_gps() if cfg['use_gps'] else None
    if gps:
        return {'name': 'GPS', 'lat': gps[0], 'lon': gps[1], 'source': 'gps'}
    return {'name': cfg['name'], 'lat': cfg['lat'], 'lon': cfg['lon'], 'source': 'fixed'}


def fetch():
    place = locate()
    req = urllib.request.Request(URL.format(**place), headers={'User-Agent': 'zero-weather/1.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    data['place'] = place
    data['fetched_at'] = int(time.time())
    return data


def render(data, now=None, busy=False, error=None, unit='C'):
    now = now or time.time()
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)

    place = (data or {}).get('place') or dict(DEFAULT_PLACE, source='fixed')
    if place.get('source') == 'gps':
        icons.ic_gps(d, 12, 7, 12, GPS_TAG)
        d.text((30, 6), f"{place['lat']:.2f}, {place['lon']:.2f}", font=F_TITLE, fill=ACCENT)
    else:
        icons.ic_pin(d, 12, 6, 13, ACCENT, BG)
        d.text((30, 6), place['name'].upper(), font=F_TITLE, fill=ACCENT)
    clock = time.strftime('%a %H:%M', time.localtime(now))
    d.text((W - 12 - d.textlength(clock, font=F_TITLE), 6), clock, font=F_TITLE, fill=DIM)
    d.line((12, 25, W - 12, 25), fill=LINE)

    cur = (data or {}).get('current')
    daily = (data or {}).get('daily')
    if cur:
        kind, label = describe(cur['weather_code'])
        draw_icon(d, 42, 62, 56, kind, bool(cur.get('is_day', 1)))
        temp = deg(cur['temperature_2m'], unit)
        d.text((80, 34), temp, font=F_TEMP, fill=FG)
        d.text((82 + d.textlength(temp, font=F_TEMP), 40), unit, font=F_TITLE, fill=DIM)
        d.text((82, 80), label, font=F_TEXT, fill=DIM)
        x, s = 214, 11
        rows = [(icons.ic_thermo, WARN, deg(cur['apparent_temperature'], unit)),
                (icons.ic_wind, CLOUD, f"{round(cur['wind_speed_10m'])} km/h"),
                (icons.ic_drop, ACCENT, f"{cur['relative_humidity_2m']}%")]
        y = 34
        if daily:  # today's high / low
            hi = deg(daily['temperature_2m_max'][0], unit)
            icons.ic_tri(d, x, y + 2, s, HOT, True)
            d.text((x + 15, y), hi, font=F_TEXT, fill=FG)
            lx = x + 23 + d.textlength(hi, font=F_TEXT)
            icons.ic_tri(d, lx, y + 2, s, RAIN, False)
            d.text((lx + 15, y), deg(daily['temperature_2m_min'][0], unit), font=F_TEXT, fill=FG)
            y += 16
        for icon, col, val in rows:
            icon(d, x, y + 2, s, col)
            d.text((x + 15, y), val, font=F_TEXT, fill=DIM)
            y += 16
    else:
        d.text((12, 50), 'no weather data yet', font=F_TEXT, fill=DIM)

    d.line((12, 100, W - 12, 100), fill=LINE)
    if daily:
        col_w = (W - 24) / 3
        for i in range(min(3, len(daily['time']))):
            x0 = 12 + i * col_w
            name = 'Today' if i == 0 else time.strftime('%a', time.localtime(daily['time'][i]))
            kind, _ = describe(daily['weather_code'][i])
            d.text((x0 + 4, 106), name, font=F_DAY, fill=FG)
            draw_icon(d, x0 + col_w - 22, 115, 26, kind, True)
            hi = deg(daily['temperature_2m_max'][i], unit)
            d.text((x0 + 4, 122), hi, font=F_SMALL, fill=FG)
            d.text((x0 + 10 + d.textlength(hi, font=F_SMALL), 122),
                   deg(daily['temperature_2m_min'][i], unit), font=F_SMALL, fill=DIM)
            pop = daily.get('precipitation_probability_max', [None] * 3)[i]
            if pop is not None:
                pc = RAIN if pop >= 50 else DIM
                icons.ic_drop(d, x0 + 4, 138, 9, pc)
                d.text((x0 + 17, 136), f'{pop}%', font=F_SMALL, fill=pc)

    fetched = (data or {}).get('fetched_at')
    icon = icons.ic_clock
    if error:
        foot, col, icon = error[:22], HOT, None
    elif busy:
        foot, col, icon = 'updating...', DIM, icons.ic_refresh
    elif not fetched:
        foot, col, icon = 'waiting for data', WARN, None
    else:
        age = now - fetched
        foot, col = fmt_ago(age), WARN if age > STALE_AFTER else DIM
    if icon:
        icon(d, 12, H - 15, 10, col)
    d.text((26 if icon else 12, H - 16), foot, font=F_SMALL, fill=col)
    gear = lambda d, x, y, s, c: icons.ic_gear(d, x, y, s, c, BG)  # noqa: E731
    icons.key_hints(d, [(['S'], gear), (['R'], icons.ic_refresh), (['ESC'], icons.ic_power)],
                    F_TAG, DIM, W - 10, H - 16)
    return img


def to_rgb565(img):
    import numpy as np
    a = np.asarray(img, dtype=np.uint16)
    v = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
    return v.astype('<u2').tobytes()


def make_icon(path):
    img = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 96, 96), radius=20, fill=BG + (255,))
    draw_icon(d, 50, 52, 76, 'partly', True)
    img.save(path)


class Fetcher(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.wake = threading.Event()
        self.busy = False
        self.error = None
        self.version = 0

    def run(self):
        cached = load()
        if cached and time.time() - cached.get('fetched_at', 0) < POLL:
            self.wake.wait(POLL - (time.time() - cached['fetched_at']))
            self.wake.clear()
        while True:
            self.busy = True
            self.version += 1
            try:
                save(fetch())
                self.error = None
            except Exception as e:
                self.error = str(e) or type(e).__name__
            self.busy = False
            self.version += 1
            self.wake.wait(POLL)
            self.wake.clear()


def run():
    import signal
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    from hold_exit import Keyboard, ExitHold, bar, BAR_H
    kbd, hold = Keyboard(KBD), ExitHold()
    fetcher = Fetcher()
    fetcher.start()
    last_key, frame, settings = None, None, None
    with open(FB, 'r+b', buffering=0) as fb:
        try:
            while True:
                keys = kbd.read()
                now = time.time()
                if settings:
                    for code in keys:
                        result = settings.handle(code)
                        if result:
                            if result == 'saved' and not fetcher.busy:
                                fetcher.wake.set()
                            settings, last_key = None, None
                            break
                elif KEY_ESC in keys:
                    hold.press(now)
                elif KEY_S in keys:
                    from settings_ui import Settings
                    settings = Settings()
                    hold.cancel()
                elif KEY_R in keys and not fetcher.busy:
                    fetcher.wake.set()
                progress = None if settings else hold.progress(now, KEY_ESC in kbd.down)
                if progress is not None and progress >= 1:
                    break
                if settings:
                    if settings.dirty:
                        frame = to_rgb565(settings.render())
                else:
                    key = (fetcher.version, int(now // 30))
                    if key != last_key:
                        frame = to_rgb565(render(load(), now, fetcher.busy, fetcher.error,
                                                 load_config()['unit']))
                        last_key = key
                fb.seek(0)
                if progress is None:
                    fb.write(frame)
                else:  # the countdown bar replaces the bottom rows
                    fb.write(frame[:(H - BAR_H) * W * 2])
                    fb.write(to_rgb565(bar(progress, W, F_DAY)))
                if settings:
                    settings.tick()
                time.sleep(0.05 if settings or progress is not None else 0.2)
        except KeyboardInterrupt:
            pass
        finally:
            fb.seek(0)
            fb.write(b'\x00' * (W * H * 2))


def main(argv):
    net.prefer_ipv4()
    if '--fetch' in argv:
        data = fetch()
        save(data)
        print(json.dumps({'current': data['current'], 'daily': data['daily']}, indent=1))
    elif '--make-icon' in argv:
        make_icon(argv[argv.index('--make-icon') + 1])
    elif '--preview' in argv:
        out = argv[argv.index('--preview') + 1]
        data = load() or fetch()
        if '--as-gps' in argv:  # preview the GPS header without a fix
            data['place'] = {'name': 'GPS', 'lat': 43.6532, 'lon': -79.3832, 'source': 'gps'}
        if '--settings' in argv:  # preview settings screens: menu, input, results
            from settings_ui import Settings
            s = Settings()
            stem = out.rsplit('.', 1)[0]
            s.render().save(f'{stem}-menu.png')
            s.state, s.text = 'input', '100 queen st w toronto'
            s.render().save(f'{stem}-input.png')
            s.state = 'searching'
            s.tick()
            s.render().save(f'{stem}-results.png')
            return
        render(data, unit=load_config()['unit']).save(out)
    else:
        run()


if __name__ == '__main__':
    main(sys.argv[1:])
