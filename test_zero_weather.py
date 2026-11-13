import unittest
from unittest import mock

import zero_weather as zw


def with_checksum(body):
    c = 0
    for ch in body:
        c ^= ord(ch)
    return f'${body}*{c:02X}'


class ParseNmeaTest(unittest.TestCase):
    def test_rmc_fix(self):
        lat, lon = zw.parse_nmea('$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A')
        self.assertAlmostEqual(lat, 48.1173, places=4)
        self.assertAlmostEqual(lon, 11.5167, places=4)

    def test_gga_fix(self):
        lat, lon = zw.parse_nmea('$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47')
        self.assertAlmostEqual(lat, 48.1173, places=4)

    def test_western_hemisphere_gn_talker(self):
        line = with_checksum('GNRMC,221500.00,A,4339.192,N,07922.992,W,0.1,,111126,,,A')
        lat, lon = zw.parse_nmea(line)
        self.assertAlmostEqual(lat, 43.6532, places=4)
        self.assertAlmostEqual(lon, -79.3832, places=4)

    def test_no_fix(self):
        self.assertIsNone(zw.parse_nmea(with_checksum('GNRMC,221500.00,V,,,,,,,111126,,,N')))
        self.assertIsNone(zw.parse_nmea(with_checksum('GNGGA,221500.00,,,,,0,00,99.99,,,,,,')))

    def test_bad_checksum_and_garbage(self):
        self.assertIsNone(zw.parse_nmea('$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*00'))
        self.assertIsNone(zw.parse_nmea('garbage'))
        self.assertIsNone(zw.parse_nmea(''))


class LocateTest(unittest.TestCase):
    def test_falls_back_to_fixed_without_fix(self):
        orig = zw.read_gps
        zw.read_gps = lambda wait=0: None
        try:
            place = zw.locate()
        finally:
            zw.read_gps = orig
        self.assertEqual(place['source'], 'fixed')

    def test_uses_gps_when_fixed(self):
        orig = zw.read_gps
        zw.read_gps = lambda wait=0: (43.65, -79.38)
        try:
            place = zw.locate()
        finally:
            zw.read_gps = orig
        self.assertEqual((place['source'], place['lat']), ('gps', 43.65))


class SettingsTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.orig_config = zw.CONFIG
        zw.CONFIG = f'{self.tmp.name}/zero-weather.json'

    def tearDown(self):
        zw.CONFIG = self.orig_config
        self.tmp.cleanup()

    def test_defaults_without_config(self):
        cfg = zw.load_config()
        self.assertEqual((cfg['name'], cfg['use_gps']), ('Toronto', True))

    def test_toggle_gps_saves(self):
        from settings_ui import Settings, K_ENTER
        self.assertEqual(Settings().handle(K_ENTER), 'saved')
        self.assertFalse(zw.load_config()['use_gps'])

    def test_search_and_pick_saves_location(self):
        from settings_ui import Settings, K_DOWN, K_ENTER
        s = Settings()
        s.handle(K_DOWN)
        s.handle(K_ENTER)
        self.assertEqual(s.state, 'input')
        for code in (24, 20, 20, 18):  # o t t e -> "otte"
            s.handle(code)
        s.handle(14)  # backspace
        self.assertEqual(s.text, 'ott')
        s.handle(K_ENTER)
        self.assertEqual(s.state, 'searching')
        s.tick(search=lambda q: [{'name': 'Ottawa', 'label': 'Ottawa, Ontario', 'lat': 45.42, 'lon': -75.70}])
        self.assertEqual(s.state, 'results')
        self.assertEqual(s.handle(K_ENTER), 'saved')
        cfg = zw.load_config()
        self.assertEqual((cfg['name'], cfg['lat']), ('Ottawa', 45.42))
        self.assertEqual(cfg['lon'], -75.70)

    def test_plain_f_x_navigate_without_fn(self):
        from settings_ui import Settings, K_ENTER
        KEY_F, KEY_X = 33, 45
        s = Settings()
        s.handle(KEY_X)
        self.assertEqual(s.sel, 1)
        s.handle(KEY_F)
        self.assertEqual(s.sel, 0)
        s.handle(KEY_X)
        s.handle(K_ENTER)
        s.handle(KEY_F)
        s.handle(KEY_X)
        self.assertEqual(s.text, 'fx')  # still letters while typing
        s.handle(K_ENTER)
        s.tick(search=lambda q: [{'name': n, 'label': n, 'lat': 0.0, 'lon': 0.0} for n in 'abc'])
        s.handle(KEY_X)
        s.handle(KEY_X)
        self.assertEqual(s.sel, 2)
        s.handle(KEY_F)
        self.assertEqual(s.sel, 1)

    def test_locate_skips_gps_when_disabled(self):
        zw.save_config(dict(zw.load_config(), use_gps=False))
        orig = zw.read_gps
        zw.read_gps = lambda wait=0: (1.0, 2.0)
        try:
            self.assertEqual(zw.locate()['source'], 'fixed')
        finally:
            zw.read_gps = orig

    def test_failed_search_shows_message(self):
        from settings_ui import Settings
        s = Settings()
        s.state, s.text = 'searching', 'x'
        s.tick(search=lambda q: [])
        self.assertEqual((s.state, s.results), ('results', []))
        self.assertIn('no results', s.msg)


class TestNet(unittest.TestCase):
    def test_ipv4_sorted_first(self):
        import socket
        import net
        v6 = (socket.AF_INET6, 1, 6, '', ('::1', 443, 0, 0))
        v4 = (socket.AF_INET, 1, 6, '', ('1.2.3.4', 443))
        with mock.patch.object(net, '_getaddrinfo', return_value=[v6, v6, v4]):
            self.assertEqual(net._ipv4_first('h', 443), [v4, v6, v6])


if __name__ == '__main__':
    unittest.main()
