"""Print draft X posts for miners that just hit a new low price on Bitaxe Radar.

    python3 scripts/new_lows.py            # new lows in the last 24 hours (default)
    python3 scripts/new_lows.py --hours 72

Read-only: prints drafts, posts nothing. The afternoon X routine runs it and posts at most one, linking the model page.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import newlows  # noqa: E402

BASE = "https://bitaxeradar.com"


def drafts(hours=24):
    latest = json.loads((ROOT / "data" / "latest.json").read_text())
    history = json.loads((ROOT / "data" / "history.json").read_text())
    now = datetime.now(timezone.utc)
    sellers = latest.get("sellers", {})
    out = []
    for d in newlows.new_lows(latest["models"], latest["offers"], history, now, days=hours / 24):
        m = latest["models"][d["model"]]
        name = m.get("short") or m.get("name") or d["model"]
        shop = (sellers.get(d["current"]["seller"]) or {}).get("name", d["current"]["seller"])
        cur = d["current"]["price_usd_approx"]
        drop = d["old_low"] - cur
        approx = "≈" if d["current"].get("currency") != "USD" else ""
        lead = "New low" if d["kind"] == "drop" else "Back in stock at a new low"
        text = (f"{lead}: {name} is {approx}${cur:,.2f} at {shop}, ${drop:,.2f} under the lowest in-stock price we'd logged before "
                f"(${d['old_low']:,.2f}).\n\nAbout {m['hashrate_ths']:g} TH/s at {m['watts']:,g} W.\n{BASE}/models/{d['model']}/")
        out.append(dict(model=d["model"], since=d["t"], text=text))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ds = drafts(a.hours)
    if a.json:
        print(json.dumps(ds, indent=2))
    elif not ds:
        print(f"No new lows in the last {a.hours:g} hours.")
    for d in ds if not a.json else []:
        print(f"--- {d['model']} (new low logged {d['since']})\n{d['text']}\n")
