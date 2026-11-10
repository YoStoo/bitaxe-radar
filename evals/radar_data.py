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
