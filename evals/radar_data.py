"""The site's live miner data, plus the same math the Worker's tools do (worker/src/tools.js).

Why this file exists: an eval must know the RIGHT answer. Prices change every few hours, so we
never hardcode "the Gamma costs $67". Instead we download the same data the chat bot reads
(bitaxeradar.com/data.js) and work out the right answer in Python at the moment we run.
"""
import json
import re
import urllib.request
from pathlib import Path

SITE = "https://bitaxeradar.com"
ROOT = Path(__file__).resolve().parent.parent


def load_live(site=SITE):
    """Download data.js (looks like `window.RADAR = {...};`) and return its "latest" part."""
    req = urllib.request.Request(site + "/data.js", headers={"User-Agent": "bitaxe-radar-evals"})
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode("utf-8")
    json_text = text[text.index("=") + 1:].strip().rstrip(";")
    return json.loads(json_text)["latest"]


def load_local():
    """Offline fallback: the copy in this repo (may be a few hours older than the live site)."""
    return json.loads((ROOT / "data" / "latest.json").read_text())


def miner_row(latest, mid):
    """One miner's key numbers. Same rules as minerRow() in tools.js: cheapest in-stock, non-stale listing."""
    m = latest["models"][mid]
    usable = sorted(
        (o for o in latest.get("offers", [])
         if o.get("model") == mid and o.get("in_stock") and not o.get("stale")
         and isinstance(o.get("price_usd_approx"), (int, float))),
        key=lambda o: o["price_usd_approx"])
    th = m.get("hashrate_ths")
    price = round(usable[0]["price_usd_approx"], 2) if usable else None
    return {
        "id": mid, "name": m["name"], "brand": m.get("maker") or m["name"].split(" ")[0],
        "th_s": th, "watts": m.get("watts"),
        "j_per_th": round(m["watts"] / th, 1) if th and m.get("watts") else None,
        "cheapest_usd": price,
        "usd_per_th": round(price / th, 1) if price is not None and th else None,
        "shops": [latest.get("sellers", {}).get(o["seller"], {}).get("name", o["seller"]) for o in usable],
    }


SORT_KEYS = {"price": "cheapest_usd", "price_per_th": "usd_per_th", "efficiency": "j_per_th", "hashrate": "th_s"}


def norm(s):
    """Lowercase, drop (brackets) and punctuation. Same idea as norm() in tools.js."""
    s = re.sub(r"\([^)]*\)", " ", str(s or "").lower())
    return re.sub(r"[^a-z0-9+]+", " ", s).strip()


def rank(latest, sort_by="price", order=None, brand=None, max_price=None, min_th=None):
    """Ranked list of in-stock miners, like the search_miners tool. Returns rows, best first."""
    rows = [miner_row(latest, mid) for mid in latest["models"]]
    rows = [r for r in rows if r["cheapest_usd"] is not None]
    if brand:
        rows = [r for r in rows if norm(brand) in norm(f"{r['brand']} {r['name']} {r['id']}")]
    if max_price is not None:
        rows = [r for r in rows if r["cheapest_usd"] <= max_price]
    if min_th is not None:
        rows = [r for r in rows if (r["th_s"] or 0) >= min_th]
    key = SORT_KEYS[sort_by]
    rows = [r for r in rows if r[key] is not None]
    order = order or ("desc" if sort_by == "hashrate" else "asc")
    return sorted(rows, key=lambda r: r[key], reverse=(order == "desc"))


# ---------- finding miner names inside an answer ----------
def aliases(latest):
    """Every way an answer might name each miner: 'Bitaxe Gamma (601/602)' -> 'bitaxe gamma', ...
    Short names ('Gamma Duo') are kept only if they point to exactly one miner."""
    out, short = {}, {}
    for mid, m in latest["models"].items():
        full = norm(m["name"])
        names = {full, norm(mid.replace("-", " "))}
        out[mid] = names
        words = full.split()
        if len(words) > 1:
            short.setdefault(" ".join(words[1:]), set()).add(mid)   # drop the brand word
    for name, ids in short.items():
        if len(ids) == 1 and len(name) >= 4:
            out[next(iter(ids))].add(name)
    return out


def miners_in_text(text, latest):
    """Which miners does this text name, in the order they first appear?
    Longest names are matched first, so 'Bitaxe Gamma Duo' is not also counted as 'Bitaxe Gamma'."""
    t = " " + norm(text) + " "
    pairs = sorted(((a, mid) for mid, names in aliases(latest).items() for a in names), key=lambda p: -len(p[0]))
    found = {}
    for alias, mid in pairs:
        needle = " " + alias + " "
        i = t.find(needle)
        while i != -1:
            found.setdefault(mid, i)
            t = t[:i + 1] + "#" * len(alias) + t[i + 1 + len(alias):]   # blank it out so shorter names can't reuse it
            i = t.find(needle)
    return [mid for mid, _ in sorted(found.items(), key=lambda kv: kv[1])]


# ---------- price history (for get_price_history cases) ----------
# The grader works out the right history answer itself, from the SAME database file the Worker reads,
# using its own SQL. Two independent implementations agreeing = good evidence both are right.
import sqlite3  # noqa: E402
import tempfile  # noqa: E402
from datetime import date, timedelta  # noqa: E402

PRICES_DB_URL = SITE + "/prices.db"   # run_evals.py --prices-db overrides this (e.g. a test Worker's copy)
_db_cache = {}


def load_prices_db(url=None):
    """Open the price database. url can be a .db file, a .sql text copy, or a local path."""
    url = url or PRICES_DB_URL
    if url in _db_cache:
        return _db_cache[url]
    if url.startswith("http"):
        req = urllib.request.Request(url, headers={"User-Agent": "bitaxe-radar-evals"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    else:
        raw = Path(url).read_bytes()
    if url.endswith(".sql"):
        con = sqlite3.connect(":memory:")
        con.executescript(raw.decode("utf-8"))
    else:
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.write(raw)
        f.close()
        con = sqlite3.connect(f.name)
    _db_cache[url] = con
    return con


def price_history(con, mid, days=30):
    """Same facts as the Worker's get_price_history: start, latest, change, lows, cheapest shop."""
    last = con.execute("SELECT MAX(day) FROM price_snapshots").fetchone()[0]
    since = (date.fromisoformat(last) - timedelta(days=days)).isoformat()
    daily = {}
    for day, usd, shop in con.execute(
            """SELECT s.day, s.price_usd, r.name FROM price_snapshots s JOIN offers o ON o.id = s.offer_id
               JOIN retailers r ON r.id = o.retailer_id
               WHERE o.miner_id = ? AND s.in_stock = 1 AND s.price_usd IS NOT NULL AND s.day >= ?
               ORDER BY s.day, s.price_usd""", (mid, since)):
        daily.setdefault(day, (usd, shop))   # first row per day = cheapest (ordered by price)
    if not daily:
        return None
    days_sorted = sorted(daily)
    start, latest = daily[days_sorted[0]], daily[days_sorted[-1]]
    cheapest_count = {}
    for usd, shop in daily.values():
        cheapest_count[shop] = cheapest_count.get(shop, 0) + 1
    atl = con.execute(
        """SELECT s.day, s.price_usd, r.name FROM price_snapshots s JOIN offers o ON o.id = s.offer_id
           JOIN retailers r ON r.id = o.retailer_id WHERE o.miner_id = ? AND s.in_stock = 1 AND s.price_usd IS NOT NULL
           ORDER BY s.price_usd, s.day LIMIT 1""", (mid,)).fetchone()
    change = round(latest[0] - start[0], 2)
    return {"start_usd": start[0], "latest_usd": latest[0], "change_usd": change,
            "trend": "flat" if abs(change) < 0.01 else ("cheaper" if change < 0 else "pricier"),
            "low_usd": min(v[0] for v in daily.values()),
            "all_time_low": {"day": atl[0], "usd": atl[1], "shop": atl[2]},
            "top_shop": max(cheapest_count.items(), key=lambda kv: kv[1])[0]}
