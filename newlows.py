"""New-low detection: when a miner's cheapest in-stock price drops below every in-stock price we logged for it before.

Shared by build_site.py (the "New lows this week" box on /price-per-th/) and scripts/new_lows.py (drafts for X posts).
Stdlib only. Non-USD prices use today's conversion rate from latest.json, same as the rest of the site.
"""
from datetime import datetime, timedelta, timezone

MIN_TRACK_DAYS = 2      # a "low" after less than 2 days of history means nothing


def _t(iso):
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def new_lows(models, offers, history, now, days=7, live=None):
    """List of dicts {kind ("drop" or "restock"), model, seller, offer_id, old_low, new_low, t, current} for drops to a new all-time (since tracking) low
    within the last `days`, where today's cheapest in-stock price is still at or below that low. Newest first."""
    out = []
    for mid in models if live is None else live:
        pts, first = [], None
        for o in offers:
            if o["model"] != mid or not o.get("price") or not o.get("price_usd_approx"):
                continue
            rate = o["price_usd_approx"] / o["price"]
            prev = None
            for p in history.get(o["id"], []):
                first = p["t"] if first is None or p["t"] < first else first
                if p.get("in_stock") and p.get("price") and prev is not None:   # a listing's first point is never an event
                    kind = "drop" if prev.get("price") and p["price"] < prev["price"] - 0.005 else ("restock" if not prev.get("in_stock") else "same")
                    pts.append((p["t"], p["price"] * rate, o, kind))
                elif p.get("in_stock") and p.get("price"):
                    pts.append((p["t"], p["price"] * rate, o, "first"))
                prev = p
        if not pts:
            continue
        cur_offers = [o for o in offers if o["model"] == mid and o.get("stock_status") == "in_stock" and o.get("price_usd_approx")]
        if not cur_offers:
            continue
        cur = min(cur_offers, key=lambda o: o["price_usd_approx"])
        lo, best = None, None
        for t, v, o, kind in sorted(pts, key=lambda x: x[0]):
            if lo is not None and v < lo - 0.005 and kind in ("drop", "restock") and _t(t) - _t(first) >= timedelta(days=MIN_TRACK_DAYS) and now - _t(t) <= timedelta(days=days):
                best = dict(kind=kind, model=mid, seller=o["seller"], offer_id=o["id"], old_low=lo, new_low=v, t=t, current=cur)
            lo = v if lo is None or v < lo else lo
        if best and cur["price_usd_approx"] <= best["new_low"] + 0.01:
            out.append(best)
    return sorted(out, key=lambda d: d["t"], reverse=True)
