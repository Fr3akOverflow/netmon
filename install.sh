#!/bin/bash
# netmon - Installationsskript (Raspberry Pi OS & Debian)
# Nutzung: sudo ./install.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte als root ausführen: sudo ./install.sh" >&2
    exit 1
fi

# Nur Debian / Raspberry Pi OS unterstützt
if ! grep -qiE "debian|raspbian" /etc/os-release; then
    echo "Fehler: Nur Debian und Raspberry Pi OS werden unterstützt." >&2
    exit 1
fi

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST=/opt/netmon
DATA=/var/lib/netmon

echo "[1/5] Installiere Abhängigkeiten (arp-scan, python3-flask) ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y arp-scan python3 python3-flask

echo "[2/5] Kopiere Dateien nach $DEST ..."
install -d "$DEST" "$DATA"
install -m 0755 "$SRC/netmon.py" "$DEST/"
install -m 0644 "$SRC/web.py" "$DEST/"

echo "[3/5] Registriere systemd-Services ..."
install -m 0644 "$SRC/systemd/netmon.service" /etc/systemd/system/
install -m 0644 "$SRC/systemd/netmon-web.service" /etc/systemd/system/
systemctl daemon-reload

echo "[4/5] Starte Services ..."
systemctl enable --now netmon.service netmon-web.service

echo "[5/5] Fertig."
echo
echo "Status:"
systemctl --no-pager --lines=3 status netmon.service netmon-web.service || true
echo
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):8081"
echo "CLI:       $DEST/netmon.py status | report | ping"