"""Settings screen for zero_weather: GPS on/off and fixed-location search."""
import json
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

from zero_weather import (ACCENT, BG, DIM, F_SMALL, F_TEXT, F_TITLE, FG, GPS_TAG,
                          H, HOT, LINE, W, load_config, save_config)

GEOCODE_URL = ('https://nominatim.openstreetmap.org/search'
               '?format=jsonv2&addressdetails=1&limit=5&q={q}')

K_ESC, K_BACKSPACE, K_ENTER, K_UP, K_DOWN = 1, 14, 28, 103, 108
# Plain F/X move up/down in list screens (Fn+F/X sends K_UP/K_DOWN).
UP_KEYS, DOWN_KEYS = (K_UP, 33), (K_DOWN, 45)
KEYMAP = {57: ' ', 51: ',', 52: '.', 53: '/', 40: "'", 12: '-', 74: '-'}
for _i, _c in enumerate('1234567890'):
    KEYMAP[2 + _i] = _c
for _row, _start in (('qwertyuiop', 16), ('asdfghjkl', 30), ('zxcvbnm', 44)):
    for _i, _c in enumerate(_row):
        KEYMAP[_start + _i] = _c

MAX_INPUT = 60
ROW_H = 18
MENU_ROWS = 3  # GPS, fixed location, temperature unit


def place_name(item):
    a = item.get('address') or {}
    for key in ('city', 'town', 'village', 'municipality', 'county', 'state'):
        if a.get(key):
            return a[key]
    return (item.get('name') or item.get('display_name', '?').split(',')[0]).strip()


def geocode(query):
    url = GEOCODE_URL.format(q=urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={'User-Agent': 'zero-weather/1.0 (CardputerZero)'})
    with urllib.request.urlopen(req, timeout=20) as r:
        items = json.load(r)
    return [{'name': place_name(i), 'label': i.get('display_name', ''),
             'lat': float(i['lat']), 'lon': float(i['lon'])} for i in items]


def clip(d, text, font, width):
    if d.textlength(text, font=font) <= width:
        return text
    while text and d.textlength(text + '...', font=font) > width:
        text = text[:-1]
    return text + '...'


class Settings:
    """Keyboard-driven settings. handle() returns 'close', 'saved' or None."""

    def __init__(self):
        self.cfg = load_config()
        self.state = 'menu'  # menu | input | searching | results
        self.sel = 0
        self.text = ''
        self.results = []
        self.msg = ''
        self.dirty = True

    def handle(self, code):
        self.dirty = True
        if self.state == 'menu':
            return self._menu_key(code)
        if self.state == 'input':
            return self._input_key(code)
        if self.state == 'results':
            return self._results_key(code)
        return None

    def _menu_key(self, code):
        if code == K_ESC:
            return 'close'
        if code in UP_KEYS:
            self.sel = (self.sel - 1) % MENU_ROWS
        elif code in DOWN_KEYS:
            self.sel = (self.sel + 1) % MENU_ROWS
        elif code == K_ENTER and self.sel == 0:
            self.cfg['use_gps'] = not self.cfg['use_gps']
            save_config(self.cfg)
            return 'saved'
        elif code == K_ENTER and self.sel == 1:
            self.state, self.text, self.msg = 'input', '', ''
        elif code == K_ENTER:  # unit only changes the display, no refetch
            self.cfg['unit'] = 'F' if self.cfg['unit'] == 'C' else 'C'
            save_config(self.cfg)
            return 'close'
        return None

    def _input_key(self, code):
        if code == K_ESC:
            self.state = 'menu'
        elif code == K_BACKSPACE:
            self.text = self.text[:-1]
        elif code == K_ENTER and self.text.strip():
            self.state = 'searching'
        elif code in KEYMAP and len(self.text) < MAX_INPUT:
            self.text += KEYMAP[code]
        return None

    def _results_key(self, code):
        if code == K_ESC:
            self.state = 'input'
        elif code in UP_KEYS and self.results:
            self.sel = (self.sel - 1) % len(self.results)
        elif code in DOWN_KEYS and self.results:
            self.sel = (self.sel + 1) % len(self.results)
        elif code == K_ENTER and self.results:
            r = self.results[self.sel]
            self.cfg.update(name=r['name'], lat=r['lat'], lon=r['lon'])
            save_config(self.cfg)
            return 'saved'
        return None

    def tick(self, search=geocode):
        """Run a pending search; called by the main loop after a frame is drawn."""
        if self.state != 'searching':
            return
        try:
            self.results = search(self.text.strip())
            self.msg = '' if self.results else 'no results, ESC to edit'
        except Exception as e:
            self.results, self.msg = [], f'search failed: {e}'[:44]
        self.state, self.sel, self.dirty = 'results', 0, True

    def render(self):
        self.dirty = False
        img = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(img)
        titles = {'menu': 'SETTINGS', 'input': 'SEARCH ADDRESS',
                  'searching': 'SEARCH ADDRESS', 'results': 'SELECT LOCATION'}
        d.text((12, 6), titles[self.state], font=F_TITLE, fill=ACCENT)
        d.line((12, 25, W - 12, 25), fill=LINE)
        getattr(self, '_draw_' + ('input' if self.state == 'searching' else self.state))(d)
        return img

    def _row(self, d, y, selected, left, right='', right_fill=FG):
        if selected:
            d.rounded_rectangle((8, y - 2, W - 8, y + ROW_H - 4), radius=4, fill=LINE)
        d.text((14, y), left, font=F_TEXT, fill=FG)
        if right:
            right = clip(d, right, F_TEXT, 130)
            d.text((W - 14 - d.textlength(right, font=F_TEXT), y), right, font=F_TEXT, fill=right_fill)

    def _hint(self, d, text):
        d.text((12, H - 16), text, font=F_SMALL, fill=DIM)

    def _draw_menu(self, d):
        on = self.cfg['use_gps']
        self._row(d, 34, self.sel == 0, 'Use GPS (Cap LoRa)', 'ON' if on else 'OFF',
                  GPS_TAG if on else DIM)
        self._row(d, 56, self.sel == 1, 'Fixed location', self.cfg['name'])
        d.text((14, 73), f"{self.cfg['lat']:.4f}, {self.cfg['lon']:.4f}", font=F_SMALL, fill=DIM)
        self._row(d, 92, self.sel == 2, 'Temperature unit',
                  '°F' if self.cfg['unit'] == 'F' else '°C', ACCENT)
        d.text((14, 116), 'GPS is used when it has a fix;', font=F_SMALL, fill=DIM)
        d.text((14, 130), 'otherwise the fixed location.', font=F_SMALL, fill=DIM)
        self._hint(d, 'F/X select  ENTER change  ESC back')

    def _draw_input(self, d):
        d.text((14, 34), 'City or address (English):', font=F_SMALL, fill=DIM)
        d.rounded_rectangle((10, 52, W - 10, 76), radius=4, outline=ACCENT)
        shown = self.text
        while shown and d.textlength(shown + '_', font=F_TEXT) > W - 32:
            shown = shown[1:]
        d.text((16, 57), shown + ('' if self.state == 'searching' else '_'), font=F_TEXT, fill=FG)
        if self.state == 'searching':
            d.text((14, 86), 'Searching...', font=F_TEXT, fill=ACCENT)
        self._hint(d, 'ENTER search  DEL erase  ESC back')

    def _draw_results(self, d):
        if not self.results:
            d.text((14, 40), self.msg, font=F_TEXT, fill=HOT)
        for i, r in enumerate(self.results):
            y = 32 + i * ROW_H
            if i == self.sel:
                d.rounded_rectangle((8, y - 2, W - 8, y + ROW_H - 4), radius=4, fill=LINE)
            d.text((14, y), clip(d, r['label'], F_SMALL, W - 28), font=F_SMALL,
                   fill=FG if i == self.sel else DIM)
        self._hint(d, 'F/X select  ENTER choose  ESC back')
