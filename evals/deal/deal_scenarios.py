"""Turn a small hand-written eval case into the same PriceData the real agent reads.

A case lists listings like:
  {"seller": "solosatoshi", "miner": "bitaxe-gamma", "today": 59.99, "history": [67, 67, ...]}
history = THIS listing's USD price on each of the days before today, oldest first
          (null = out of stock that day). today = today's price, or null for out of stock.
Optional: "stock": "out_of_stock" | "preorder", "stale": true, "currency": "EUR",
          "own_today": 59.0 and "own_history": [...] (the shop's own-currency prices).
The answer key is NOT typed by hand: answer_key() computes it from the data with facts.py.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from deal_agent.facts import PriceData  # noqa: E402

TODAY = "2026-11-10"
SELLERS = {"solosatoshi": "Solo Satoshi", "bitcoinmerch": "Bitcoin Merch", "altair": "Altair Technology",
           "bitaxede": "Bitaxe.de", "dcentral": "D-Central"}
MINERS = {"bitaxe-gamma": "Bitaxe Gamma (601/602)", "bitaxe-gamma-duo": "Bitaxe Gamma Duo (650)",
          "nerdqaxe-pp": "NerdQaxe++ (4.8 TH/s)", "avalon-nano-3s": "Canaan Avalon Nano 3S",
          "hammer-bc04": "Hammer Miner BC04", "bitaxe-touch": "Bitaxe Touch", "avalon-mini-3": "Canaan Avalon Mini 3"}
CUR = {"bitaxede": "EUR", "dcentral": "CAD"}


def build(case, today=TODAY):
    t = date.fromisoformat(today)
    offers, snaps = [], []
    for L in case["listings"]:
        oid = f'{L["seller"]}:{L["miner"]}'
        cur = L.get("currency", CUR.get(L["seller"], "USD"))
        hist = L.get("history", [])
        own_hist = L.get("own_history", hist)
        for i, p in enumerate(hist):
            day = (t - timedelta(days=len(hist) - i)).isoformat()
            if p is not None:
                snaps.append((oid, day, p, True, own_hist[i], cur))
        status = L.get("stock", "in_stock" if L.get("today") is not None else "out_of_stock")
        price = L.get("today") if L.get("today") is not None else (hist[-1] if hist and hist[-1] is not None else 100.0)
        offers.append(dict(id=oid, seller=L["seller"], model=L["miner"], title=f'{MINERS[L["miner"]]} at {SELLERS[L["seller"]]}',
                           url=f'https://example.com/{oid.replace(":", "/")}', price=L.get("own_today", price), currency=cur,
                           price_usd_approx=price, stock_status=status, in_stock=status == "in_stock",
                           stale=bool(L.get("stale")), checked_at=today + "T12:00:00Z"))
        if status == "in_stock" and not L.get("stale"):
            snaps.append((oid, today, price, True, L.get("own_today", price), cur))
    used_m = {L["miner"] for L in case["listings"]}
    used_s = {L["seller"] for L in case["listings"]}
    latest = dict(generated_at=today + "T12:00:00Z", fx={},
                  models={m: dict(name=MINERS[m], hashrate_ths=1.0, watts=20) for m in MINERS if m in used_m},
                  sellers={s: dict(name=SELLERS[s], url=f"https://{s}.example", currency=CUR.get(s, "USD")) for s in SELLERS if s in used_s},
                  offers=offers)
    return PriceData.from_rows(latest, snaps)
