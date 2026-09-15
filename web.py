#!/usr/bin/env python3
"""netmon-web - Dashboard für den LAN-Präsenzmonitor auf Port 8081.

Zeigt gefundene Geräte, Verweilzeit (Sitzungen) und Ping-Mittelwerte,
gelesen aus state.json / events.jsonl / ping.jsonl.
"""
import json, os, time
from datetime import datetime
from flask import Flask

STATE_FILE = "/var/lib/netmon/state.json"
EVENTS_FILE = "/var/lib/netmon/events.jsonl"
PING_FILE = "/var/lib/netmon/ping.jsonl"
MAX_PING_HISTORY = 8

app = Flask(__name__)


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def iso(ts):
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M:%S")


def dur(secs):
    secs = int(secs)
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def name(d):
    return d.get("host") or d.get("vendor") or d.get("mac", "?")


def sessions():
    s = {}
    for e in read_jsonl(EVENTS_FILE):
        if e["event"] == "online":
            s.setdefault(e["mac"], []).append([e["ts"], None])
        elif e["event"] == "offline":
            lst = s.get(e["mac"])
            if lst and lst[-1][1] is None:
                lst[-1][1] = e["ts"]
    return s


def latest_ping(mac, pings):
    lst = pings.get(mac, [])
    return lst[-1] if lst else None


def ping_history(mac, pings, n=MAX_PING_HISTORY):
    return [p["avg_ms"] for p in pings.get(mac, [])][-n:]


@app.route("/")
def page():
    state = read_json(STATE_FILE).get("devices", {})
    pings = {}
    for e in read_jsonl(PING_FILE):
        pings.setdefault(e["mac"], []).append(e)
    sess = sessions()

    now = time.time()
    rows = []
    for mac, d in sorted(state.items(), key=lambda kv: name(kv[1]).lower()):
        present = d.get("present")
        status = '<span class="on">anwesend</span>' if present else '<span class="off">abwesend</span>'
        if present:
            seams = f"seit {dur(now - d.get('since', now))}"
        else:
            last = sess.get(mac, [])
            last = next((s for s in reversed(last) if s[1]), None)
            seams = f"zuletzt {dur(last[1] - last[0])}" if last else "–"
        lp = latest_ping(mac, pings)
        if lp and lp["avg_ms"] is not None:
            ping = f"{lp['avg_ms']:.1f} ms"
            loss = f"{lp['loss_pct']:.0f}%"
        else:
            ping, loss = "–", "–"
        hist = " ".join(f"{v:.0f}" if v is not None else "·" for v in ping_history(mac, pings))
        rows.append(
            f"<tr><td class='nm'>{name(d)}</td><td>{d.get('ip', '')}</td>"
            f"<td>{status}</td><td>{seams}</td><td class='mono'>{ping}</td>"
            f"<td class='mono'>{loss}</td><td class='mono hist'>{hist}</td></tr>"
        )
    devices_html = "\n".join(rows) if rows else "<tr><td colspan=7>Noch keine Geräte erfasst.</td></tr>"

    srows = []
    for mac, ss in sorted(sess.items(), key=lambda kv: kv[1][-1][0], reverse=True):
        d = state.get(mac, {})
        for start, end in reversed(ss):
            if end is None:
                ankle = f'{iso(start)} <span class="off">(läuft)</span>'
                abfahrt, dauer = "–", f"{dur(now - start)}"
            else:
                ankle, abfahrt = iso(start), iso(end)
                dauer = dur(end - start)
            srows.append(f"<tr><td class='nm'>{name(d) or mac}</td><td class='mono'>{ankle}</td>"
                         f"<td class='mono'>{abfahrt}</td><td class='mono'>{dauer}</td></tr>")
    sess_html = "\n".join(srows) if srows else "<tr><td colspan=4>Noch keine Sitzungen erfasst.</td></tr>"

    return BASE.replace("__DEVICES__", devices_html).replace("__SESSIONS__", sess_html)


BASE = """<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="20">
<title>netmon – Geräteüberwachung</title><style>
body{font-family:sans-serif;margin:2em;background:#fafafa;color:#222}
h1{font-size:1.3em}h2{font-size:1.05em;margin-top:2em;border-bottom:1px solid #ddd;padding-bottom:.3em}
table{border-collapse:collapse;width:100%;font-size:.9em}
td,th{border:1px solid #ddd;padding:.4em .6em;text-align:left;vertical-align:top}
th{background:#eee}.nm{font-weight:600}.mono{font-family:monospace}
.hist{color:#666;letter-spacing:.1em}
.on{color:#1b7a1b;font-weight:600}.off{color:#b30000}
</style></head><body>
<h1>netmon – Geräte im LAN <small>Raspberry Pi eth0</small></h1>
<h2>Geräte</h2><table><tr><th>Gerät</th><th>IP</th><th>Status</th><th>Verweilzeit</th>
<th>Ping (&Oslash;)</th><th>Verlust</th><th>Verlauf (letzte 8, ms)</th></tr>
__DEVICES__
</table>
<h2>Sitzungen (Verweilzeiten)</h2><table><tr><th>Gerät</th><th>Ankunft</th><th>Abfahrt</th><th>Dauer</th></tr>
__SESSIONS__
</table>
<p style="color:#888;font-size:.8em">Auto-Refresh alle 20 s.</p>
</body></html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)