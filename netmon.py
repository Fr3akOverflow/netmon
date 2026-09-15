#!/usr/bin/env python3
"""netmon - ARP-basierter LAN-Präsenzmonitor.

Loggt Auftauchen/Gehen jedes Geräts im LAN (MAC-basiert) mit Zeitstempel.
Nutzen:
  netmon.py              Monitor-Schleife (für systemd)
  netmon.py status       Aktuell anwesende Geräte + seit wann
  netmon.py report       Sitzungen mit Start/Bis/Dauer
"""
import concurrent.futures
import json, os, re, shutil, socket, subprocess, sys, time
from datetime import datetime

STATE_FILE = "/var/lib/netmon/state.json"
EVENTS_FILE = "/var/lib/netmon/events.jsonl"
PING_FILE = "/var/lib/netmon/ping.jsonl"
INTERVAL = int(os.environ.get("NETMON_INTERVAL", "60"))
PING_INTERVAL = int(os.environ.get("NETMON_PING_INTERVAL", "300"))
GRACE = 2 * INTERVAL
IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}\t")


def lnow():
    return time.time()


def iso(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def interface():
    out = subprocess.check_output(["ip", "-4", "route", "show", "default"]).decode()
    return out.split(" dev ")[1].split()[0]


def scan(iface):
    arp_scan = shutil.which("arp-scan") or "/usr/sbin/arp-scan"
    p = subprocess.run([arp_scan, "--interface", iface, "--localnet", "--retry=2"],
                       capture_output=True, text=True, timeout=90)
    seen = {}
    for line in p.stdout.splitlines():
        if not IPV4.match(line):
            continue
        parts = line.split("\t")
        seen[parts[1].lower()] = {"ip": parts[0], "vendor": parts[2] if len(parts) > 2 else ""}
    return seen


def resolve_host(ip, old):
    if old:
        return old
    try:
        return socket.gethostbyaddr(ip)[0].rsplit(".", 1)[0]
    except Exception:
        return ""


def ping_test(ip):
    p = subprocess.run(["ping", "-c", "4", "-q", "-W", "1", "-i", "0.2", ip],
                       capture_output=True, text=True, timeout=15)
    loss = float(re.search(r"(\d+(?:\.\d+)?)% packet loss", p.stdout).group(1))
    m = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", p.stdout)
    avg = float(m.group(1)) if m else None
    return avg, loss


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"devices": {}}


def append_event(ev, mac, d):
    rec = {"iso": iso(lnow()), "ts": lnow(), "event": ev, "mac": mac,
           "ip": d.get("ip", ""), "host": d.get("host", ""), "vendor": d.get("vendor", "")}
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def loop():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    st = load(STATE_FILE)
    iface = interface()
    last_ping = 0.0
    print(f"netmon läuft auf {iface}, Scan-Intervall {INTERVAL}s, Ping-Intervall {PING_INTERVAL}s", flush=True)
    while True:
        try:
            seen = scan(iface)
        except Exception as e:
            print(f"Scan fehlgeschlagen: {e}", flush=True)
            time.sleep(INTERVAL)
            continue
        now = lnow()
        for mac, s in seen.items():
            d = st["devices"].setdefault(mac, {})
            if not d.get("present"):
                d.update(present=True, since=now)
                d["sessions"] = d.get("sessions", 0) + 1
                d.setdefault("first_seen", now)
                d["host"] = resolve_host(s["ip"], d.get("host"))
                d["ip"] = s["ip"]
                d["vendor"] = s.get("vendor") or d.get("vendor", "")
                append_event("online", mac, d)
            d["last_seen"] = now
        for mac, d in list(st["devices"].items()):
            if d.get("present") and now - d.get("last_seen", 0) > GRACE:
                d["present"] = False
                append_event("offline", mac, d)
        with open(STATE_FILE, "w") as f:
            json.dump(st, f, indent=1)
        # ping: alle PING_INTERVAL s, 4 Messungen je Gerät, parallel über Threads
        if now - last_ping >= PING_INTERVAL:
            last_ping = now
            devs = [(mac, d) for mac, d in st["devices"].items() if d.get("present")]
            if devs:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(devs))) as ex:
                    results = ex.map(lambda md: ping_test(md[1]["ip"]), devs)
                    for (mac, d), (avg, loss) in zip(devs, results):
                        rec = {"iso": iso(lnow()), "ts": lnow(), "mac": mac, "ip": d["ip"],
                               "host": d.get("host", ""), "avg_ms": avg, "loss_pct": loss}
                        with open(PING_FILE, "a") as f:
                            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        time.sleep(INTERVAL)


def name(d):
    return d.get("host") or d.get("vendor") or d.get("mac", "?")


def status():
    st = load(STATE_FILE)
    devs = [d for d in st["devices"].values() if d.get("present")]
    if not devs:
        print("Keine Geräte im Netz.")
        return
    for d in sorted(devs, key=lambda d: name(d).lower()):
        seit = int((lnow() - d.get("since", lnow())) // 60)
        print(f"{name(d):<22} {d.get('ip',''):<16} {d.get('vendor',''):<24} seit {seit} min")


def report():
    if not os.path.exists(EVENTS_FILE):
        print("Noch keine Events.")
        return
    sess = {}
    for line in open(EVENTS_FILE):
        e = json.loads(line)
        if e["event"] == "online":
            sess[e["mac"]] = {"d": e, "start": e["ts"]}
        elif e["event"] == "offline" and e["mac"] in sess and sess[e["mac"]]["start"]:
            d = sess[e["mac"]]["d"]
            end = e["ts"]
            print(f"{d.get('host') or d.get('vendor') or e['mac']:<22} "
                  f"{d.get('ip',''):<16} {iso(d['start'])}  ->  {iso(end)}  "
                  f"({int(end - d['start'])} s)")
            sess[e["mac"]]["start"] = None
    for mac, s in sess.items():
        if s["start"] and s["d"].get("host"):
            print(f"{name(s['d']):<22} {s['d'].get('ip',''):<16} {iso(s['start'])}  ->  läuft weiter")


def ping_status():
    if not os.path.exists(PING_FILE):
        print("Noch keine Pings.")
        return
    last = {}
    for line in open(PING_FILE):
        e = json.loads(line)
        last[e["mac"]] = e
    for mac, e in sorted(last.items(), key=lambda kv: (kv[1]["host"] or kv[1]["ip"]).lower()):
        name = e["host"] or e.get("vendor", "") or mac
        avg = f"{e['avg_ms']:.1f} ms" if e["avg_ms"] is not None else "--"
        print(f"{name:<22} {e['ip']:<16} {avg:<10} Loss {e['loss_pct']:.0f}%  {e['iso']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status()
    elif len(sys.argv) > 1 and sys.argv[1] == "report":
        report()
    elif len(sys.argv) > 1 and sys.argv[1] == "ping":
        ping_status()
    else:
        loop()