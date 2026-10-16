#!/usr/bin/env python3
"""Bitaxe Radar collector (prototype).

Fetches public product data from a handful of sellers, normalises it, and writes:
  data/latest.json   - current snapshot (one "offer" per seller x model)
  data/history.json  - append-only price/stock history keyed by offer id

Standard library only. Safe to run on a schedule (cron / GitHub Actions):
    python3 collector/collect.py            # collect + write data/
    python3 build_site.py                   # copy data into site/data.js

Rules this script follows:
  * Only reads public product pages / public JSON feeds, low request volume, identifies itself.
  * Never invents a value. If a seller fails, its previous offers are carried forward flagged stale=true.
  * Sellers that cannot be scraped reliably are listed in latest.json -> unscrapable (with reason).
"""
import json, re, sys, time, urllib.parse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "BitaxeRadarPrototype/0.1 (+price comparison; read-only; contact TBD)"
TIMEOUT = 30

# --------------------------------------------------------------------------------------
# Canonical models we track. Keep this list small & explicit; add models by adding rows.
# --------------------------------------------------------------------------------------
MODELS = {
    "bitaxe-supra":     {"name": "Bitaxe Supra",              "chip": "BM1368", "hashrate_ths": 0.65, "watts": 15, "note": "Older gen, ~0.6-0.7 TH/s; largely superseded by Gamma"},
    "bitaxe-ultra":     {"name": "Bitaxe Ultra",              "chip": "BM1366", "hashrate_ths": 0.5,  "watts": 12, "note": "Older gen, ~0.5 TH/s"},
    "bitaxe-gamma":     {"name": "Bitaxe Gamma (601/602)",    "chip": "BM1370", "hashrate_ths": 1.2,  "watts": 18, "note": "Sellers state 1.1-1.5 TH/s at 15-18 W"},
    "bitaxe-gamma-duo": {"name": "Bitaxe Gamma Duo (650)",    "chip": "2x BM1370", "hashrate_ths": 1.63, "watts": 26, "note": "Two chips in the Gamma footprint"},
    "bitaxe-gt-801":    {"name": "Bitaxe GT / Gamma Turbo (801)", "chip": "2x BM1370", "hashrate_ths": 2.15, "watts": 43, "note": "Sellers state 2.0-2.4 TH/s"},
    "nerdaxe-gamma":    {"name": "Nerdaxe Gamma",             "chip": "BM1370", "hashrate_ths": 1.2,  "watts": 18, "note": "Gamma-class board with a color display"},
    "nerdaxe-gaia":     {"name": "Nerdaxe Gaia",              "chip": "BM1373", "hashrate_ths": 2.6,  "watts": 25, "note": "Sellers state 2.4-2.6 TH/s"},
    "nerdqaxe-pp":      {"name": "NerdQaxe++ (4.8 TH/s)",     "chip": "4x BM1370", "hashrate_ths": 4.8, "watts": 80, "note": "Revisions differ by seller (4.8 TH/s std, Rev 6.1 ~6 TH/s ~100 W, Rev 7)"},
}
# hashrate_ths / watts above are typical VENDOR-STATED figures used only for the cost estimate.
# They are approximate and must be labelled as such on the site.

SELLERS = {
    "bitcoinmerch": {"name": "Bitcoin Merch", "url": "https://bitcoinmerch.com", "currency": "USD", "method": "Shopify products.json",
                     "affiliate": "Program found via search (3.3% reported); not yet joined"},
    "solosatoshi":  {"name": "Solo Satoshi", "url": "https://www.solosatoshi.com", "currency": "USD", "method": "WooCommerce Store API (variation-level stock)",
                     "affiliate": "Unknown - not checked"},
    "bitaxede":     {"name": "Bitaxe.de", "url": "https://bitaxe.de", "currency": "EUR", "method": "Product-page schema.org JSON-LD",
                     "affiliate": "Reported via third-party article; not yet confirmed with seller"},
    "powermining":  {"name": "Power Mining", "url": "https://powermining.io", "currency": "EUR", "method": "Shopify products.json",
                     "affiliate": "Up to 10% via GoAffPro (powermining.io/pages/affiliate); not yet joined"},
}

# Explicit product mapping (seller -> model -> identifier). No fuzzy matching, so no mis-matches.
BITCOINMERCH = {  # Shopify handle
    "bitaxe-supra":     "bitcoin-merch®-bitaxe-400-bitcoin-miner-600gh-s",
    "bitaxe-ultra":     "bitcoin-merch-bitaxe-1366-solo-bitcoin-miner-up-to-500gh-s",
    "bitaxe-gamma":     "bitcoin-merch-bitaxe-601-gamma-power-supply-bitcoin-miner-1-5th-s",
    "bitaxe-gamma-duo": "bitcoin-merch®-bitaxe-gamma-duo-650-1-6th-s-w-power-supply",
    "bitaxe-gt-801":    "bitcoin-merch-bitaxe-801-gt-gamma-turbo-bm1370-asic-2-2th-s",
    "nerdaxe-gaia":     "bitcoin-merch®-nerdaxe-gaia-2-4th-s-bm1373-home-miner-w-power-supply",
    "nerdqaxe-pp":      ("nerdqaxe-plus-plus", "Black / Standard 4.8TH/s"),  # (handle, variant title)
}
SOLOSATOSHI = {  # WooCommerce slug
    "bitaxe-supra":     "bitaxe-supra",
    "bitaxe-gamma":     "bitaxe-gamma",
    "bitaxe-gamma-duo": "bitaxe-duo-bitcoin-solo-miner-650-model",
    "bitaxe-gt-801":    "bitaxe-gt-gamma-turbo",
    "nerdqaxe-pp":      "nerdqaxe-plus-plus",
}
BITAXEDE = {  # product page slug
    "bitaxe-gamma":  "bitaxe-gamma-601",
    "bitaxe-gt-801": "bitaxe-gt",
    "nerdaxe-gamma": "nerdaxe-gamma-601",
    "nerdaxe-gaia":  "nerdaxe-gaia-bitcoin-miner",
    "nerdqaxe-pp":   "nerdqaxe-plus-plus-48th",
}
POWERMINING = {  # Shopify handle
    "bitaxe-gamma":  "bitaxe-gamma",
    "nerdaxe-gamma": "nerdaxe-gamma",
    "nerdqaxe-pp":   "nerdqaxe",
}

UNSCRAPABLE = [
    {"seller": "MineShop (mineshop.eu)", "url": "https://mineshop.eu", "reason": "HTTP 403 (bot protection) from the collector box; its Shopify/Woo feeds are blocked. Needs manual checks or a partner feed."},
    {"seller": "NerdQaxe Store (nerdqaxestore.com)", "url": "https://nerdqaxestore.com", "reason": "TLS/connection failure from the collector box (curl exit 35) and HTTP 500 via WebFetch on 2026-10-16. Retry later / from another network."},
    {"seller": "Plebsource (plebsource.com)", "url": "https://plebsource.com", "reason": "TLS/connection failure from the collector box (curl exit 35) on 2026-10-16."},
    {"seller": "Altair Technology (altairtech.io)", "url": "https://altairtech.io", "reason": "WooCommerce Store API returned empty body and search returned HTTP 202 (bot challenge). Needs a browser-based scraper or manual entry."},
    {"seller": "TinyChipHub (tinychiphub.com)", "url": "https://tinychiphub.com", "reason": "JS-rendered Shopline storefront; no usable public product feed found. Not scraped."},
    {"seller": "Mining Now / MinerCompare (aggregators)", "url": "https://miningnow.com", "reason": "Competitors/aggregators - deliberately NOT scraped; used only as market research.", "internal": True},
    {"seller": "CryptoMinerBros, MillionMiner, bitaxehardware.com", "url": "", "reason": "Deliberately excluded for now: unvetted sellers (wire/crypto-only payment, anomalous $69-$79 Gamma prices, no price in structured data). Vet before listing.", "internal": True},
]


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def http_get(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(5 * (attempt + 1)); continue
            raise
        except Exception as e:  # network error
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def get_json(url):
    return json.loads(http_get(url, "application/json"))


def offer(seller, model, title, url, price, currency, status, in_stock, config, checked_at, source_url, extra=None):
    o = {
        "id": f"{seller}:{model}", "seller": seller, "model": model, "title": title, "url": url,
        "price": round(float(price), 2), "currency": currency, "stock_status": status, "in_stock": bool(in_stock),
        "config": config, "checked_at": checked_at, "source_url": source_url, "stale": False,
    }
    if extra: o.update(extra)
    return o


# --------------------------------------------------------------------------------------
# Seller adapters. Each returns a list of offers; raises on total failure.
# --------------------------------------------------------------------------------------
def fetch_shopify_all(base):
    products, page = [], 1
    while page <= 6:
        d = get_json(f"{base}/products.json?limit=250&page={page}")
        batch = d.get("products", [])
        if not batch: break
        products += batch
        if len(batch) < 250: break
        page += 1; time.sleep(1)
    return products


def collect_bitcoinmerch(ts):
    base = SELLERS["bitcoinmerch"]["url"]
    by_handle = {p["handle"]: p for p in fetch_shopify_all(base)}
    out, missing = [], []
    for model, key in BITCOINMERCH.items():
        handle, want_variant = (key if isinstance(key, tuple) else (key, None))
        p = by_handle.get(handle)
        if not p: missing.append(model); continue
        vs = p["variants"]
        if want_variant:
            vs = [v for v in vs if v["title"] == want_variant] or []
            if not vs: missing.append(model); continue
        avail = [v for v in vs if v["available"]]
        v = min(avail or vs, key=lambda v: float(v["price"]))
        cfg = "" if v["title"] == "Default Title" else f"Variant: {v['title']}"
        psu = "power supply included per product title" if "power supply" in p["title"].lower() else "power supply not mentioned in title (unverified)"
        cfg = (cfg + "; " if cfg else "") + psu
        url = f"{base}/products/{urllib.parse.quote(p['handle'])}"
        out.append(offer("bitcoinmerch", model, p["title"], url, v["price"], "USD",
                         "in_stock" if avail else "out_of_stock", bool(avail), cfg, ts, f"{base}/products.json",
                         {"compare_at": float(v["compare_at_price"]) if v.get("compare_at_price") else None}))
    return out, missing


def collect_solosatoshi(ts):
    base = SELLERS["solosatoshi"]["url"]
    api = f"{base}/wp-json/wc/store/v1/products"
    out, missing = [], []
    for model, slug in SOLOSATOSHI.items():
        res = get_json(f"{api}?slug={urllib.parse.quote(slug)}")
        if not res: missing.append(model); continue
        p = res[0]
        # IMPORTANT: for variable products the product-level is_in_stock flag is NOT reliable
        # (seen True while every variation was out of stock). Check each variation.
        def fetch_var(v):
            d = get_json(f"{api}/{v['id']}")
            time.sleep(0.2)
            return {"attrs": {a["name"]: a["value"] for a in v["attributes"]},
                    "price": int(d["prices"]["price"]) / 10 ** d["prices"]["currency_minor_unit"],
                    "in_stock": bool(d["is_in_stock"])}
        with ThreadPoolExecutor(max_workers=3) as vex:  # modest parallelism, still polite
            vars_ = list(vex.map(fetch_var, p.get("variations", [])))
        if not vars_:
            pr = p["prices"]
            vars_ = [{"attrs": {}, "price": int(pr["price"]) / 10 ** pr["currency_minor_unit"], "in_stock": bool(p["is_in_stock"])}]

        def na_psu(v):
            return v["attrs"].get("Power Supply", "").lower().startswith("north america") or v["attrs"].get("Power Supply", "").lower().startswith("north american")
        def bare(v):  # no stand / no rear fan add-ons
            return all(v["attrs"].get(k, "No") in ("None", "No") for k in ("Stand", "Rear Fan"))
        pool = [v for v in vars_ if na_psu(v) and bare(v)] or [v for v in vars_ if na_psu(v)] or vars_
        stocked = [v for v in pool if v["in_stock"]]
        v = min(stocked or pool, key=lambda v: v["price"])
        cfg = ", ".join(f"{k}: {val}" for k, val in v["attrs"].items()) or "single option"
        n_in = sum(1 for x in vars_ if x["in_stock"])
        out.append(offer("solosatoshi", model, re.sub(r"&#8211;", "-", p["name"]), p["permalink"], v["price"], "USD",
                         "in_stock" if stocked else "out_of_stock", bool(stocked), cfg, ts, f"{api}?slug={slug}",
                         {"variants_in_stock": n_in, "variants_total": len(vars_),
                          "lowest_any_variant": min(x["price"] for x in vars_)}))
    return out, missing


SCHEMA_STATUS = {"InStock": ("in_stock", True), "OutOfStock": ("out_of_stock", False), "PreOrder": ("preorder", False),
                 "BackOrder": ("backorder", False), "SoldOut": ("out_of_stock", False), "LimitedAvailability": ("in_stock", True)}


def collect_bitaxede(ts):
    base = SELLERS["bitaxede"]["url"]
    out, missing = [], []
    for model, slug in BITAXEDE.items():
        url = f"{base}/produkt/{slug}"
        html = http_get(url)
        prod = None
        for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, flags=re.S):
            try: d = json.loads(m)
            except ValueError: continue
            if isinstance(d, dict) and d.get("@type") == "Product": prod = d; break
        if not prod: missing.append(model); continue
        o = prod["offers"]; o = o[0] if isinstance(o, list) else o
        status, in_stock = SCHEMA_STATUS.get(o.get("availability", "").rsplit("/", 1)[-1], ("unknown", False))
        out.append(offer("bitaxede", model, prod["name"], url, o["price"], o["priceCurrency"], status, in_stock,
                         "Base price incl. VAT (listed 'inkl. MwSt.'); shipping extra", ts, url))
        time.sleep(1)
    return out, missing


def collect_powermining(ts):
    base = SELLERS["powermining"]["url"]
    by_handle = {p["handle"]: p for p in fetch_shopify_all(base)}
    out, missing = [], []
    for model, handle in POWERMINING.items():
        p = by_handle.get(handle)
        if not p: missing.append(model); continue
        # Skip variants literally named NONE (no-power-supply option); prefer the US-plug variant.
        vs = [v for v in p["variants"] if v["title"].strip().upper() != "NONE"] or p["variants"]
        us = [v for v in vs if re.search(r"\bUS\b", v["title"])]
        pool = us or vs
        avail = [v for v in pool if v["available"]]
        v = min(avail or pool, key=lambda v: float(v["price"]))
        url = f"{base}/products/{p['handle']}"
        # Shopify 'available' stays true for pre-orders, so read the product page text too.
        html = http_get(url)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)))
        pre = re.search(r"you can now pre-order|coming soon[^.]{0,80}pre-order", text, flags=re.I)
        ship = re.search(r"Shipping [^.!]{0,60}\d{4}!?", text) if pre else None
        status = "preorder" if pre else ("in_stock" if avail else "out_of_stock")
        cfg = f"Variant: {v['title']}; page lists power supply + stand in the box; EUR, tax basis not stated; shipping extra"
        out.append(offer("powermining", model, p["title"], url, v["price"], "EUR", status,
                         bool(avail) and not pre, cfg, ts, url,
                         {"compare_at": float(v["compare_at_price"]) if v.get("compare_at_price") else None,
                          "ship_note": ship.group(0) if ship else None}))
        time.sleep(1)
    return out, missing


ADAPTERS = {"bitcoinmerch": collect_bitcoinmerch, "solosatoshi": collect_solosatoshi,
            "bitaxede": collect_bitaxede, "powermining": collect_powermining}


def fetch_fx():
    try:
        d = get_json("https://api.frankfurter.dev/v1/latest?base=EUR&symbols=USD")
        return {"EUR_USD": d["rates"]["USD"], "date": d["date"], "source": "Frankfurter (ECB reference rates)"}
    except Exception as e:
        print("FX fetch failed:", e, file=sys.stderr)
        return None


def load(path, default):
    try: return json.loads(path.read_text())
    except Exception: return default


def main():
    DATA.mkdir(exist_ok=True)
    prev = load(DATA / "latest.json", {"offers": []})
    history = load(DATA / "history.json", {})
    ts = now_utc().isoformat().replace("+00:00", "Z")
    fx = fetch_fx() or prev.get("fx")

    results, errors, missing_all = {}, {}, {}

    def run(sid):
        try:
            return sid, ADAPTERS[sid](ts), None
        except Exception as e:
            return sid, None, f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=4) as ex:  # one thread per seller; each seller is hit sequentially
        for sid, res, err in ex.map(run, ADAPTERS):
            if err: errors[sid] = err; print(f"[{sid}] FAILED: {err}", file=sys.stderr)
            else:
                results[sid], missing_all[sid] = res
                print(f"[{sid}] ok: {len(res[0])} offers; unmapped: {res[1]}")

    offers = []
    for sid in ADAPTERS:
        if sid in results:
            offers += results[sid]
        else:  # carry forward last known data, flagged stale
            for o in prev.get("offers", []):
                if o["seller"] == sid:
                    o = dict(o); o["stale"] = True; offers.append(o)

    for o in offers:
        o["price_usd_approx"] = (round(o["price"] * fx["EUR_USD"], 2) if o["currency"] == "EUR" and fx
                                 else (o["price"] if o["currency"] == "USD" else None))

    # history: append when value changed, or when last point is >20h old
    for o in offers:
        if o["stale"]: continue
        pts = history.setdefault(o["id"], [])
        pt = {"t": o["checked_at"], "price": o["price"], "currency": o["currency"], "in_stock": o["in_stock"], "status": o["stock_status"]}
        if not pts or (pts[-1]["price"], pts[-1]["in_stock"], pts[-1]["status"]) != (pt["price"], pt["in_stock"], pt["status"]) \
           or (datetime.fromisoformat(pt["t"].replace("Z", "+00:00")) - datetime.fromisoformat(pts[-1]["t"].replace("Z", "+00:00"))).total_seconds() > 20 * 3600:
            pts.append(pt)

    latest = {
        "generated_at": ts, "fx": fx, "models": MODELS, "sellers": SELLERS, "offers": offers,
        "unmapped_products": {k: v for k, v in missing_all.items() if v}, "errors": errors, "unscrapable": UNSCRAPABLE,
    }
    (DATA / "latest.json").write_text(json.dumps(latest, indent=2, ensure_ascii=False))
    (DATA / "history.json").write_text(json.dumps(history, indent=1, ensure_ascii=False))
    print(f"wrote {len(offers)} offers at {ts}; errors: {list(errors) or 'none'}")
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
