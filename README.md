# netmon – ARP-basierter LAN-Präsenzmonitor

Erkennt alle Geräte im Heimnetz per `arp-scan` und loggt Auftauchen/Gehen (MAC-basiert) mit Zeitstempel. Ergänzend misst er regelmäßig Ping-Latenz und -Verlust pro Gerät. Ein Flask-Dashboard zeigt alles im Browser.

Geeignet für Raspberry Pi OS und Debian.

## Funktionen

- Geräte im LAN automatisch erkennen (ARP-Scan, MAC-basiert)
- Online/Offline-Events mit Zeitstempel, Sitzungen (Verweilzeiten)
- Ping-Messung (Latenz + Verlust) alle 5 min pro Gerät, parallel
- Web-Dashboard (Port 8081, Auto-Refresh alle 20 s)
- CLI: `status`, `report`, `ping`
- systemd-Services für Monitoring und Webinterface

## Installation

```bash
sudo ./install.sh
```

Das Skript installiert `arp-scan` und `python3-flask`, kopiert die Dateien
nach `/opt/netmon`, legt den Datenspeicher `/var/lib/netmon` an und startet
die systemd-Services `netmon.service` und `netmon-web.service`.

## Dashboard

`http://<ip-des-pi>:8081`

## CLI

```bash
/opt/netmon/netmon.py status   # aktuell anwesende Geräte
/opt/netmon/netmon.py report   # Sitzungen (Ankunft -> Abfahrt -> Dauer)
/opt/netmon/netmon.py ping     # letzte Ping-Werte aller Geräte
```

## Daten

| Datei                 | Inhalt                                    |
|-----------------------|-------------------------------------------|
| `/var/lib/netmon/state.json`  | aktueller Zustand (anwesend, seit, Sessions) |
| `/var/lib/netmon/events.jsonl` | online/offline-Events (JSON-Lines)          |
| `/var/lib/netmon/ping.jsonl`   | Ping-Messungen (JSON-Lines)                 |

## Konfiguration (Umgebungsvariablen)

| Variable                 | Standard | Bedeutung                        |
|--------------------------|----------|----------------------------------|
| `NETMON_INTERVAL`        | `60`     | ARP-Scan-Intervall in Sekunden   |
| `NETMON_PING_INTERVAL`   | `300`    | Ping-Intervall in Sekunden       |

## Deinstallation

```bash
sudo ./uninstall.sh
```

## Voraussetzungen

- Raspberry Pi OS oder Debian
- Root-Zugriff (sudo)
- Internetzugang für `apt-get`

## Lizenz

MIT – siehe `LICENSE`.