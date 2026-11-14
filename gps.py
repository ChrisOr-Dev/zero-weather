"""Position from the Cap LoRa-1262 GNSS (NMEA on /dev/ttyS0)."""
import os
import select
import time

GPS_TTY = '/dev/ttyS0'
GPS_POWER = '/sys/class/leds/ext_5v_out/brightness'
GPS_WAIT = 4.0


def nmea_coord(value, hemi):
    if not value or not hemi:
        return None
    dot = value.index('.')
    degrees = float(value[:dot - 2])
    minutes = float(value[dot - 2:])
    v = degrees + minutes / 60
    return -v if hemi in 'SW' else v


def parse_nmea(line):
    """(lat, lon) from a valid RMC/GGA sentence with a fix, else None."""
    if not line.startswith('$') or '*' not in line:
        return None
    body, _, csum = line[1:].partition('*')
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    try:
        if calc != int(csum[:2], 16):
            return None
        f = body.split(',')
        if f[0].endswith('RMC') and len(f) > 6 and f[2] == 'A':
            lat, lon = nmea_coord(f[3], f[4]), nmea_coord(f[5], f[6])
        elif f[0].endswith('GGA') and len(f) > 6 and f[6] not in ('', '0'):
            lat, lon = nmea_coord(f[2], f[3]), nmea_coord(f[4], f[5])
        else:
            return None
    except (ValueError, IndexError):
        return None
    return (lat, lon) if lat is not None and lon is not None else None


def read_gps(wait=GPS_WAIT):
    """Position from the Cap LoRa-1262 GNSS, or None (no cap, no power, no fix)."""
    try:
        with open(GPS_POWER) as f:
            if int(f.read().strip() or 0) == 0:
                return None
        fd = os.open(GPS_TTY, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    except (OSError, ValueError):
        return None
    try:
        import termios
        a = termios.tcgetattr(fd)
        a[0] = 0
        a[1] = 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        a[3] = 0
        a[4] = a[5] = termios.B115200
        termios.tcsetattr(fd, termios.TCSANOW, a)
        buf, end = b'', time.time() + wait
        while time.time() < end:
            if not select.select([fd], [], [], 0.3)[0]:
                continue
            buf += os.read(fd, 4096)
            *lines, buf = buf.split(b'\n')
            for raw in lines:
                fix = parse_nmea(raw.decode('ascii', 'ignore').strip())
                if fix:
                    return fix
            buf = buf[-512:]
    except OSError:
        return None
    finally:
        os.close(fd)
    return None
