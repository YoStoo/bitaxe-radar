"""The numbers behind the deal of the day. Plain Python + SQL, no AI.

Two data sources, the same ones the website uses:
  - data/latest.json  today's listings (price, stock) from the collector
  - data/prices.sql   the SQL price history (one row per listing per day; see docs/SQL.md)

Everything Claude sees comes from these functions (through tools.py), and the grounding check
(guard.py) and the eval answer key (evals/deal/) use the SAME functions. One source of truth:
if the AI and the checker disagree, the checker is right, because it is plain code over the data.

"Deal" rule (kept simple so anyone can check it by hand):
  typical price = the MEDIAN of the cheapest in-stock price on each of the previous 14 days
                  (median, not mean: one odd day can't fake a deal)
  drop %        = (typical - today) / typical x 100
  a real deal   = in stock today, at least MIN_HISTORY_DAYS days of history, and drop % >= MIN_DROP_PCT
  the deal of the day = the real deal with the biggest drop % (ties: new all-time low first, then cheaper)
"""
import json
import sqlite3
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collector"))
import price_db  # noqa: E402

WINDOW_DAYS = 14        # "recent" = the 14 days before today
MIN_HISTORY_DAYS = 3    # need at least 3 days of in-stock prices to call anything "typical"
MIN_DROP_PCT = 3.0      # smaller moves are mostly exchange-rate wiggle on EUR/CAD shops, not price cuts

SQL_DAILY_CHEAPEST = """
SELECT s.day, MIN(s.price_usd) AS usd, r.name AS shop
FROM price_snapshots s
JOIN offers o    ON o.id = s.offer_id
JOIN retailers r ON r.id = o.retailer_id
WHERE o.miner_id = ? AND s.in_stock = 1 AND s.price_usd IS NOT NULL AND s.day >= ? AND s.day < ?
GROUP BY s.day
ORDER BY s.day"""

SQL_LOW_BEFORE = """
SELECT s.day, s.price_usd AS usd, r.name AS shop
FROM price_snapshots s
JOIN offers o    ON o.id = s.offer_id
JOIN retailers r ON r.id = o.retailer_id
WHERE o.miner_id = ? AND s.in_stock = 1 AND s.price_usd IS NOT NULL AND s.day < ?
ORDER BY s.price_usd ASC, s.day ASC
LIMIT 1"""

SQL_FIRST_DAY = "SELECT MIN(day) FROM price_snapshots"

# The SAME listing's price in the shop's own currency (EUR/CAD shops), to tell a real price cut from exchange-rate noise.
SQL_OWN_CURRENCY = """
SELECT day, price FROM price_snapshots
WHERE offer_id = ? AND in_stock = 1 AND price IS NOT NULL AND currency = ? AND day >= ? AND day < ?
ORDER BY day"""


def r2(x):
    return None if x is None else round(float(x) + 0.0, 2)


def days_before(day, n):
    return (date.fromisoformat(day) - timedelta(days=n)).isoformat()


class PriceData:
    """Today's listings + a SQL connection to the price history. Built once per run."""

    def __init__(self, latest, con):
        self.latest = latest
        self.con = con
        self.today = latest["generated_at"][:10]          # UTC day of the collector run (same "day" as the SQL rows)
        self.generated_at = latest["generated_at"]
        self.models = latest.get("models") or {}
        self.sellers = latest.get("sellers") or {}
        self._facts = {}

    def __del__(self):
        try:
            self.con.close()
        except Exception:
            pass

    @classmethod
    def load(cls, root=ROOT):
        latest = json.loads((root / "data" / "latest.json").read_text())
        return cls(latest, price_db.connect(root / "data" / "prices.sql"))

    @classmethod
    def from_rows(cls, latest, snapshots):
        """For tests and evals: build the SQL history from a small list of
        (offer_id, day, price_usd, in_stock) or (offer_id, day, price_usd, in_stock, own_price, currency)."""
        con = sqlite3.connect(":memory:")
        con.executescript(price_db.SCHEMA)
        price_db.upsert_catalog(con, latest)
        for row in snapshots:
            oid, day, p, ins = row[:4]
            own, cur = (row[4], row[5]) if len(row) > 4 else (p, "USD")
            price_db.ensure_offer(con, oid)
            con.execute("INSERT INTO price_snapshots (offer_id, day, checked_at, price, currency, price_usd, in_stock) VALUES (?,?,?,?,?,?,?)",
                        (oid, day, day + "T12:00:00Z", own, cur, p, 1 if ins else 0))
        return cls(latest, con)

    # ---------- small helpers ----------
    def name(self, mid):
        return (self.models.get(mid) or {}).get("name", mid)

    def shop(self, sid):
        return (self.sellers.get(sid) or {}).get("name", sid)

    def resolve(self, text):
        """Miner id or name -> id (exact id, exact name, or a unique partial name). None if unknown or ambiguous."""
        t = (text or "").strip().lower()
        if t in self.models:
            return t
        by_name = [m for m, v in self.models.items() if (v.get("name") or "").lower() == t]
        if len(by_name) == 1:
            return by_name[0]
        part = [m for m, v in self.models.items() if t and t in (v.get("name") or "").lower()]
        return part[0] if len(part) == 1 else None

    def usable_offers(self, mid=None):
        """Today's in-stock listings with a USD price we actually read this run (stale ones are old prices, skipped)."""
        return [o for o in self.latest.get("offers") or []
                if (mid is None or o.get("model") == mid) and o.get("stock_status") == "in_stock" and not o.get("stale")
                and isinstance(o.get("price_usd_approx"), (int, float))]

    def best_offer(self, mid):
        offs = self.usable_offers(mid)
        return min(offs, key=lambda o: (o["price_usd_approx"], o["id"])) if offs else None

    # ---------- the facts for one miner ----------
    def facts(self, mid):
        """Everything we know about today's price for one miner vs its history. Cached; pure function of the data."""
        if mid in self._facts:
            return self._facts[mid]
        o = self.best_offer(mid)
        if not o:
            self._facts[mid] = None
            return None
        today_usd = r2(o["price_usd_approx"])
        since = days_before(self.today, WINDOW_DAYS)
        daily = [dict(day=d, usd=r2(u), shop=s) for d, u, s in self.con.execute(SQL_DAILY_CHEAPEST, (mid, since, self.today))]
        low = self.con.execute(SQL_LOW_BEFORE, (mid, self.today)).fetchone()
        typical = r2(statistics.median([d["usd"] for d in daily])) if len(daily) >= MIN_HISTORY_DAYS else None
        drop_usd = r2(typical - today_usd) if typical else None
        drop_pct = round(100 * (typical - today_usd) / typical, 1) if typical else None
        f = dict(
            miner_id=mid, miner_name=self.name(mid),
            offer_id=o["id"], retailer_id=o["seller"], retailer_name=self.shop(o["seller"]),
            price_usd=today_usd, price=r2(o["price"]), currency=o.get("currency", "USD"),
            shops_in_stock=len({x["seller"] for x in self.usable_offers(mid)}),
            history_days=len(daily), window_days=WINDOW_DAYS,
            typical_usd=typical, drop_usd=drop_usd, drop_pct=drop_pct,
            prior_low_usd=r2(low[1]) if low else None, prior_low_day=low[0] if low else None,
            lowest_ever=bool(low) and today_usd <= low[1] + 0.005,
            new_low=bool(low) and today_usd < low[1] - 0.005,
            window_low_usd=min((d["usd"] for d in daily), default=None),
            window_high_usd=max((d["usd"] for d in daily), default=None),
        )
        f["is_deal"] = typical is not None and drop_pct >= MIN_DROP_PCT
        f["fx_only"] = False
        if f["currency"] != "USD":
            # A EUR/CAD price converted to USD moves every day with the exchange rate. Only count it as a drop
            # (or a new low) if the shop's OWN price went down too (interview story #34).
            own = [p for _, p in self.con.execute(SQL_OWN_CURRENCY, (o["id"], f["currency"], "0000", self.today))]
            recent = [p for d, p in self.con.execute(SQL_OWN_CURRENCY, (o["id"], f["currency"], since, self.today))]
            cut = bool(recent) and o["price"] < statistics.median(recent) * (1 - MIN_DROP_PCT / 100)
            below_own_low = bool(own) and o["price"] < min(own) - 0.005
            if f["is_deal"] and not cut or f["new_low"] and not below_own_low:
                f["fx_only"] = True
            f["is_deal"] = f["is_deal"] and cut
            f["new_low"] = f["new_low"] and below_own_low
            f["lowest_ever"] = f["lowest_ever"] and (not own or o["price"] <= min(own) + 0.005)
        self._facts[mid] = f
        return f

    def all_facts(self):
        return [f for f in (self.facts(m) for m in self.models) if f]

    def ranked_deals(self):
        """Real deals, best first. Empty list = no standout deal today."""
        deals = [f for f in self.all_facts() if f["is_deal"]]
        return sorted(deals, key=lambda f: (-f["drop_pct"], not f["new_low"], f["price_usd"], f["miner_id"]))

    def answer_key(self):
        """What a correct agent must pick: a miner id, or None for 'no standout deal today'."""
        d = self.ranked_deals()
        return d[0]["miner_id"] if d else None

    # ---------- price history (same shape as the Worker's get_price_history, ported to Python) ----------
    def history(self, mid, days=30):
        """Cheapest in-stock USD price per day for the last N days, INCLUDING today's collector row."""
        since = days_before(self.today, days)
        tomorrow = days_before(self.today, -1)
        daily = [dict(day=d, usd=r2(u), shop=s) for d, u, s in self.con.execute(SQL_DAILY_CHEAPEST, (mid, since, tomorrow))]
        # Today's point = today's live price (latest.json, what the site shows), not the SQL row: the SQL row can carry an
        # earlier exchange rate, and two different "today" prices let a wrong number pass the check (interview story #36).
        daily = [d for d in daily if d["day"] != self.today]
        live = self.best_offer(mid)
        if live:
            daily.append(dict(day=self.today, usd=r2(live["price_usd_approx"]), shop=self.shop(live["seller"])))
        first = self.con.execute(SQL_FIRST_DAY).fetchone()[0]
        base = dict(miner_id=mid, miner_name=self.name(mid), window_days=days, history_starts=first)
        if not daily:
            return {**base, "note": "No in-stock price recorded for this miner in that window."}
        start, last = daily[0], daily[-1]
        change = r2(last["usd"] - start["usd"])
        return {**base, "start": start, "latest": last, "change_usd": change,
                "change_pct": round(100 * change / start["usd"], 1) if start["usd"] else None,
                "lowest_in_window": min(daily, key=lambda d: (d["usd"], d["day"])),
                "highest_in_window": max(daily, key=lambda d: (d["usd"], d["day"])),
                "days_with_price": len(daily), "points": sample(daily)}


def sample(rows, n=8):
    """First, last, lowest and evenly spaced points (max n), so a tool result stays small."""
    if len(rows) <= n:
        return rows
    keep = {0, len(rows) - 1, min(range(len(rows)), key=lambda i: rows[i]["usd"])}
    k = 1
    while len(keep) < n and k < n:
        keep.add(round(k * (len(rows) - 1) / (n - 1)))
        k += 1
    return [rows[i] for i in sorted(keep)]
