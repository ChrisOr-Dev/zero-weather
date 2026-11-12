#!/bin/sh
# Register Weather with APPLaunch. Copy this folder to ~/zero-weather on the
# CardputerZero, then run:  sudo sh ~/zero-weather/install.sh
# The launcher entry is a small wrapper owned by pi; the app itself stays in
# ~/zero-weather, so later updates need no sudo.
set -eu
cd "$(dirname "$0")"
L=/usr/share/APPLaunch
APP_DIR=$(pwd)
printf '#!/bin/sh\nexec /usr/bin/python3 %s/zero_weather.py "$@"\n' "$APP_DIR" > "$L/bin/zero-weather"
chown pi:pi "$L/bin/zero-weather"
chmod 755 "$L/bin/zero-weather"
install -m 644 zero-weather.desktop "$L/applications/zero-weather.desktop"
python3 zero_weather.py --make-icon "$L/share/images/zero-weather.png"
chmod 644 "$L/share/images/zero-weather.png"
echo "Installed. Restart the launcher as pi: systemctl --user restart APPLaunch"
