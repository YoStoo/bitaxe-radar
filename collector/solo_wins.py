#!/usr/bin/env python3
"""Recent solo-mined Bitcoin blocks -> data/solo_wins.json. Stdlib only, a handful of requests per run.

Sources (both public, read-only, polled once per collector run, i.e. every 6 hours):
  * mempool.space mining API: blocks whose coinbase tag mempool.space attributes to a solo pool
    (Solo CKPool, Public Pool, Parasite, Braiins Solo, SoloPool.com). This is the block list.
  * SoloLuck.io "The Solo Block Record" (CC BY 4.0, https://sololuck.io/legends): adds solo blocks found on
    other solo setups, and the winning miner's hashrate/hardware only where the miner publicly reported it.

Never invents attribution: hardware/hashrate stay null unless SoloLuck lists a reported figure.
On any fetch failure the previous entries are kept (union by block height), so a bad run never empties the list.
"""
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "solo_wins.json"
UA = "bitaxeradar-collector/1.0 (+https://bitaxeradar.com; contact@bitaxeradar.com)"
MEMPOOL = "https://mempool.space/api/v1/mining/pool/{slug}/blocks"
SOLOLUCK_CSV = "https://sololuck.io/api/legends/v1/blocks.csv"
SOLO_POOLS = {"solock": "Solo CKPool", "publicpool": "Public Pool", "parasite": "Parasite Pool",
              "braiinssolo": "Braiins Solo", "solopoolcom": "SoloPool.com"}
SKIP_SOLOLUCK_POOLS = {"untagged coinbase"}     # inferred from payout patterns, not a declared solo tag: left out
MIN_HEIGHT = 840_000                            # April 2024 halving onward (3.125 BTC subsidy era)


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def iso(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_mempool(fetch=get):
    out = {}
    for slug, name in SOLO_POOLS.items():
        for b in json.loads(fetch(MEMPOOL.format(slug=slug))):
            h = int(b["height"])
            if h < MIN_HEIGHT:
                continue
            ex = b.get("extras") or {}
            out[h] = {"height": h, "hash": b["id"], "time": iso(b["timestamp"]), "pool": name,
                      "reward_btc": round(int(ex.get("reward", 0)) / 1e8, 8) or None}
    return out


def hardware_name(text):
    """The device name SoloLuck gives before ' — ', only when it reads like a device (not 'home miner')."""
    if not text or "—" not in text:
        return None
    name = text.split("—", 1)[0].strip()
    if name.lower().startswith("a single "):
        name = name[9:]
    return None if not name or name.lower().startswith(("home miner", "hashrate", "a ", "~")) else name


def from_sololuck(fetch=get):
    out = {}
    for r in csv.DictReader(io.StringIO(fetch(SOLOLUCK_CSV))):
        h = int(r["height"])
        if h < MIN_HEIGHT or r["pool"].strip().lower() in SKIP_SOLOLUCK_POOLS:
            continue
        hs = float(r["hashrate_hs"]) if (r.get("hashrate_hs") or "").strip() else None
        rented = "rented" in (r.get("hardware") or "").lower()
        out[h] = {"height": h, "date": r["date"], "pool": r["pool"].strip(), "reward_btc": float(r["reward_btc"]) if r.get("reward_btc") else None,
                  "hashrate_hs": None if rented else hs, "hardware": hardware_name(r.get("hardware")) if hs and not rented else None,
                  "rented": rented}
    return out


def merge(old, mp, sl):
    wins = {int(w["height"]): dict(w) for w in old.get("wins", [])}
    for h, w in mp.items():
        wins[h] = {**wins.get(h, {}), **w, "source": "mempool.space"}
    for h, s in sl.items():
        w = wins.get(h, {"height": h, "hash": None, "time": s["date"] + "T00:00:00Z", "pool": s["pool"], "reward_btc": s["reward_btc"], "source": "sololuck.io"})
        w["hashrate_hs"], w["hardware"], w["rented"] = s["hashrate_hs"], s["hardware"], s["rented"]
        wins[h] = w
    for w in wins.values():
        w.setdefault("hashrate_hs", None)
        w.setdefault("hardware", None)
        w.setdefault("rented", False)
    return sorted(wins.values(), key=lambda w: -w["height"])


def run(fetch=get, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        old = json.loads(OUT.read_text())
    except Exception:
        old = {}
    status = {}
    mp, sl = {}, {}
    try:
        mp = from_mempool(fetch)
        status["mempool.space"] = "ok"
    except Exception as e:
        status["mempool.space"] = f"failed: {type(e).__name__}"
        print("solo wins: mempool.space fetch failed, keeping last data:", e, file=sys.stderr)
    try:
        sl = from_sololuck(fetch)
        status["sololuck.io"] = "ok"
    except Exception as e:
        status["sololuck.io"] = f"failed: {type(e).__name__}"
        print("solo wins: sololuck.io fetch failed, keeping last data:", e, file=sys.stderr)
    wins = merge(old, mp, sl)
    if not wins:
        print("solo wins: no data at all; leaving file untouched", file=sys.stderr)
        return old
    ok = mp or sl
    data = {"fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ") if ok else old.get("fetched_at"),
            "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "status": status, "wins": wins}
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"solo wins: {len(wins)} blocks, newest {wins[0]['height']} ({wins[0]['time'][:10]})", status)
    return data


if __name__ == "__main__":
    run()
