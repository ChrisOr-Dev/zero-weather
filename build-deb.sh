#!/bin/sh
# Build the AppStore package. Needs dpkg-deb and python3-pil, so run it on the
# CardputerZero (or any Debian box):  sh build-deb.sh "Name <email>"
# Output: zero-weather_<version>_all.deb in this folder.
set -eu
cd "$(dirname "$0")"
VERSION=$(python3 -c "import json; print(json.load(open('app-builder.json'))['version'])")
PKG=zero-weather
MAINTAINER=${1:?usage: build-deb.sh "Name <email>"}

umask 022
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
chmod 755 "$ROOT"
APP=$ROOT/usr/share/$PKG
L=$ROOT/usr/share/APPLaunch
mkdir -p "$APP" "$L/bin" "$L/applications" "$L/share/images" "$ROOT/DEBIAN"

install -m 644 zero_weather.py settings_ui.py hold_exit.py net.py "$APP/"
printf '#!/bin/sh\nexec /usr/bin/python3 /usr/share/%s/zero_weather.py "$@"\n' "$PKG" > "$L/bin/$PKG"
chmod 755 "$L/bin/$PKG"
install -m 644 zero-weather.desktop "$L/applications/$PKG.desktop"
python3 zero_weather.py --make-icon "$L/share/images/$PKG.png"
chmod 644 "$L/share/images/$PKG.png"

cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Architecture: all
Maintainer: $MAINTAINER
Depends: python3, python3-pil, python3-numpy
Section: utils
Priority: optional
Installed-Size: $(du -sk "$ROOT/usr" | cut -f1)
Description: Current weather and 3-day forecast for CardputerZero
 Shows current conditions and a 3-day forecast from Open-Meteo. Location
 comes from the Cap LoRa-1262 GPS when it has a fix, otherwise from a fixed
 place searched in the in-app settings (S key).
EOF

dpkg-deb --root-owner-group --build "$ROOT" "${PKG}_${VERSION}_all.deb"
