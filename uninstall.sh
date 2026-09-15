#!/bin/bash
# netmon - Deinstallationsskript
# Nutzung: sudo ./uninstall.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte als root ausführen: sudo ./uninstall.sh" >&2
    exit 1
fi

read -rp "Wirklich netmon entfernen (Services stoppen + Dateien löschen)? [j/N] " ans
case "$ans" in
    [jJyY]*) ;;
    *) echo "Abgebrochen."; exit 1 ;;
esac

systemctl disable --now netmon.service netmon-web.service 2>/dev/null || true
rm -f /etc/systemd/system/netmon.service /etc/systemd/system/netmon-web.service
systemctl daemon-reload

rm -rf /opt/netmon
rm -rf /var/lib/netmon

echo "netmon entfernt."