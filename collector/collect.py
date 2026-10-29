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
    # ---- heater & home miners (category "home"): plug-in units for a living space. Figures are seller/maker-stated.
    "avalon-nano-3s":   {"name": "Canaan Avalon Nano 3S", "category": "home", "kind": "Desk miner / mini heater", "maker": "Canaan",
                         "hashrate_ths": 6, "watts": 140, "note": "Seller-stated 6 TH/s (+/- 5%) at up to 140 W"},
    "avalon-mini-3":    {"name": "Canaan Avalon Mini 3", "category": "home", "kind": "Room heater miner", "maker": "Canaan",
                         "hashrate_ths": 37.5, "watts": 800, "note": "Seller-stated 37.5 TH/s at up to 800 W, baseboard-heater shape"},
    "avalon-q":         {"name": "Canaan Avalon Q (90 TH/s)", "category": "home", "kind": "Large heater miner", "maker": "Canaan",
                         "hashrate_ths": 90, "watts": 1674, "note": "Seller-stated 90 TH/s at about 1,674 W"},
    "heatbit-trio":     {"name": "Heatbit Trio", "category": "home", "kind": "Space heater + air purifier + miner", "maker": "Heatbit",
                         "hashrate_ths": 10, "watts": 400, "heat_watts": 1500, "note": "Maker-stated 10 TH/s at 400 W of mining heat, plus 1,100 W of standard heating (1,500 W total)"},
    "heatbit-maxi":     {"name": "Heatbit Maxi", "category": "home", "kind": "Space heater + air purifier + miner", "maker": "Heatbit",
                         "hashrate_ths": 39, "watts": 1500, "note": "Maker-stated 39 TH/s with 1,500 W of mining heat (the Maxi Pro variant states 60 TH/s)"},
    "heatbit-canvas":   {"name": "Heatbit Canvas", "category": "home", "kind": "Wall heater + miner", "maker": "Heatbit",
                         "hashrate_ths": 10, "watts": 300, "note": "Maker-stated 10 TH/s at 300 W, wall-mounted"},
    "braiins-bmm-101":  {"name": "Braiins Mini Miner BMM 101", "category": "home", "kind": "Desk lottery miner", "maker": "Braiins",
                         "hashrate_ths": 1, "watts": 40, "note": "Maker-stated 1 TH/s at about 35-40 W"},
    "hammer-bc04":      {"name": "Hammer Miner BC04", "category": "home", "kind": "Desk miner", "maker": "Hammer",
                         "hashrate_ths": 6, "watts": 96, "note": "Seller-stated 6 TH/s at 96 W"},
    # ---- added 2026-10-21 from docs/MINER_CATALOG.md. Stock (default) settings only, never overclock figures.
    # category "board" = open-source boards: shown on category/best-for pages, kept off the Bitaxe-only home sections.
    "bitaxe-gamma-hex": {"name": "Bitaxe Gamma Hex (1300)", "category": "board", "chip": "6x BM1370", "hashrate_ths": 8.4, "watts": 140,
                         "note": "Seller-stated ~8.4 TH/s at 140 W at stock settings (Solo Satoshi); sold with an AIO liquid cooler. Bitcoin Merch's listing states 10.5 TH/s at the same 140 W"},
    "bitaxe-naja-duo":  {"name": "Bitaxe Naja Duo (1201)", "category": "board", "chip": "2x BM1373", "hashrate_ths": 4.4, "watts": 42,
                         "note": "Seller-stated ~4.4 TH/s at ~42 W at stock settings; the 8 TH/s figure some listings quote is an overclock at ~92 W"},
    "nerdoctaxe":       {"name": "NerdOCTaxe Gamma", "category": "board", "chip": "8x BM1370", "hashrate_ths": 9.6, "watts": 160,
                         "note": "Seller-stated 9.6 TH/s standard at ~160 W (D-Central measured ~208 W at the wall); 12 TH/s is an overclock at ~200 W"},
    "bitforge-nano":    {"name": "BitForge Nano", "category": "board", "chip": "2x BM1370", "hashrate_ths": 2.6, "watts": 40,
                         "note": "Seller-stated 2.6 TH/s factory default at about 15 J/TH, so roughly 40 W"},
    "heatbit-bitair":   {"name": "Heatbit Bitair", "category": "home", "kind": "Air purifier + miner", "maker": "Heatbit",
                         "hashrate_ths": 1.2, "watts": 25, "note": "Maker-stated 1.2 TH/s, 25 W total at max (17 W for the mining chip), USB-C powered"},
    "futurebit-apollo-iii": {"name": "FutureBit Apollo III", "category": "home", "kind": "Quiet home miner", "maker": "FutureBit",
                         "hashrate_ths": 12, "watts": 180, "note": "Maker-stated ~10-12 TH/s in Eco mode at about 15 W per TH/s (so ~180 W); Turbo mode states ~16-18 TH/s at higher power and noise"},
    "hammer-thor-p2":   {"name": "Hammer Miner Thor P2", "category": "home", "kind": "Desk miner", "maker": "Hammer",
                         "hashrate_ths": 10, "watts": 166, "note": "Seller-stated ~10 TH/s at ~155-166 W (2x BM1373)"},
    "hammer-bc08":      {"name": "Hammer Miner BC08", "category": "home", "kind": "Desk miner", "maker": "Hammer",
                         "hashrate_ths": 12, "watts": 210, "note": "Seller-stated 12 TH/s at 210 W max, air-cooled version with 5-inch touchscreen"},
    "gekko-kbox-22":    {"name": "GekkoScience KBox 22", "category": "home", "kind": "Small heater miner", "maker": "GekkoScience",
                         "hashrate_ths": 22, "watts": 330, "note": "Seller-stated up to 22 TH/s at about 322-330 W in its high mode (11 TH/s at ~178 W in low mode)"},
    "dcentral-stealthminer": {"name": "D-Central StealthMiner", "category": "home", "kind": "Room heater miner (refurbished)", "maker": "D-Central",
                         "hashrate_ths": 26, "watts": 860, "note": "Seller-stated 26 TH/s at 860 W for the base S19 Edition (S19j Pro and S19k Pro editions state 32-38 TH/s at 900-930 W); runs on a standard 120 V outlet; recycled, tested hardware"},
    # added 2026-10-21: Power Mining's own miner, pre-order from launch day (Bitcube Pro has no details yet, so not tracked)
    "bitcube":          {"name": "Power Mining Bitcube", "category": "home", "kind": "Desk lottery miner with touchscreen", "maker": "Power Mining",
                         "chip": "Avalon A3197", "hashrate_ths": 0.777, "watts": 25,
                         "note": "Maker-stated up to 777 GH/s in Turbo (550 GH/s Quiet) at 20-25 W from the wall, USB-C powered"},
    # added 2026-10-22: Heatbit's water heater element miner, pre-order (Genesis batch) from launch day
    "heatbit-bitwater": {"name": "Heatbit Bitwater", "category": "home", "kind": "Water heater miner (tank element)", "maker": "Heatbit",
                         "chip": "BM1370 x20", "hashrate_ths": 34, "watts": 600,
                         "note": "Maker-stated up to 34 TH/s and up to 600 W, from 12 J/TH; replaces the lower element of a 30-80 gal electric water heater"},
    # added 2026-10-23: NMMiner's dual-BM1373 desk miner (listed Sep 29, shipping since Oct 20). Normal mode figures, not Turbo.
    "nmqaxe-nexus":     {"name": "NMMiner NMQAxe++ Nexus", "category": "home", "kind": "Desk miner", "maker": "NMMiner",
                         "chip": "2x BM1373", "hashrate_ths": 8.5, "watts": 110,
                         "note": "Maker-stated ~8.5 TH/s at ~110 W in Normal mode (Eco ~6 TH/s at ~63 W; Turbo ~11 TH/s at ~172 W)"},
    # added 2026-10-25 from docs/MINER_CATALOG.md: four-chip AxeOS board sold by Bitcoin Merch (maker not named on the listing)
    "nerdqx":           {"name": "NerdQX (8.1 TH/s)", "category": "board", "chip": "4x BM1370", "hashrate_ths": 8.1, "watts": 138,
                         "note": "Seller-stated up to 8.1 TH/s at about 138 W (Bitcoin Merch); the listing does not name the maker"},
    # added 2026-10-29: six-chip BM1368 Bitaxe (Supra Hex 702) and the new Gaia Copper Pro (pre-order, ships from Nov 7, 2026), both at Bitaxe.de
    "bitaxe-702":       {"name": "Bitaxe 702 (Supra Hex)", "category": "board", "chip": "6x BM1368", "hashrate_ths": 4.2, "watts": 90,
                         "note": "Seller-stated ~4.2 TH/s at ~90 W (about 21.4 J/TH), older BM1368 chip generation"},
    "nerdaxe-gaia-copper-pro": {"name": "Nerdaxe Gaia Copper Pro", "category": "board", "chip": "BM1373", "hashrate_ths": 3.0, "watts": 33,
                         "note": "Seller-stated ~3 TH/s at ~33 W (about 11 J/TH) from the factory, Gaia board with an AXP60 copper cooler"},
}
# hashrate_ths / watts above are typical VENDOR-STATED figures used only for the cost estimate.
# They are approximate and must be labelled as such on the site.

SELLERS = {
    "bitcoinmerch": {"name": "Bitcoin Merch", "url": "https://bitcoinmerch.com", "currency": "USD", "method": "Shopify products.json",
                     "affiliate": "Program found via search (3.3% reported); not yet joined"},
    "solosatoshi":  {"name": "Solo Satoshi", "url": "https://www.solosatoshi.com", "currency": "USD", "method": "WooCommerce Store API (variation-level stock)",
                     "affiliate": "Unknown - not checked"},
    "bitaxede":     {"name": "Bitaxe.de", "url": "https://bitaxe.de", "currency": "EUR", "method": "Product-page schema.org JSON-LD",
                     "affiliate": "Affiliate program joined Oct 24, 2026 (5%, ref=bitaxeradar)"},
    "powermining":  {"name": "Power Mining", "url": "https://powermining.io", "currency": "EUR", "method": "Shopify products.json (US storefront via localization cookie: ex-VAT prices)",
                     "affiliate": "Up to 10% via GoAffPro (powermining.io/pages/affiliate); not yet joined"},
    "altair":       {"name": "Altair Technology", "url": "https://altairtech.io", "currency": "USD", "method": "Product page (WooCommerce variation data / JSON-LD)",
                     "affiliate": "Program exists; not yet approved - plain links only"},
    "heatbit":      {"name": "Heatbit", "url": "https://heatbit.com", "currency": "USD", "method": "Shopify products.json + product page pre-order check",
                     "affiliate": "5% via GoAffPro; not yet approved - plain links only"},
    "braiins":      {"name": "Braiins Forge", "url": "https://braiinsforge.com", "currency": "USD", "method": "Product-page schema.org JSON-LD",
                     "affiliate": "No store affiliate program"},
    "dtv":          {"name": "DTV Electronics", "url": "https://dtvelectronics.com", "currency": "USD", "method": "WooCommerce Store API",
                     "affiliate": "Applied; under review - plain links only"},
    "futurebit":    {"name": "FutureBit", "url": "https://shop.futurebit.io", "currency": "USD", "method": "Shopify products.json",
                     "affiliate": "None known"},
    "nmminer":      {"name": "NMMiner", "url": "https://www.nmminer.com", "currency": "USD", "method": "WooCommerce Store API (variation-level stock)",
                     "affiliate": "None known"},
    "dcentral":     {"name": "D-Central", "url": "https://d-central.tech", "currency": "CAD", "method": "WooCommerce Store API",
                     "affiliate": "Applied Oct 21; not yet approved - plain links only"},
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
    "bitaxe-gamma-hex": "bitcoin-merch®-bitaxe-gammahex-hydro-10-5th-s-w-power-supply",
    "bitaxe-naja-duo":  "bitcoin-merch®-bitaxe-naja-duo-bm1373-miner-w-power-supply",
    "nerdoctaxe":       ("bitcoin-merch-nerdoctaxe-9-6th-s", "Standard 9.6TH/s"),
    "bitforge-nano":    "bitcoin-merch®-bitforge-nano-2-6th-s-w-power-supply",
    "heatbit-bitair":   "bitcoin-merch®-heatbit-bitair-air-purifier-bitcoin-miner",
    "hammer-thor-p2":   "bitcoin-merch®-hammer-miner-thor-p2-10th-s-lottery-miner-w-power-supply",
    "gekko-kbox-22":    "bitcoin-merch®-gekkoscience-kbox-22th-s-bitcoin-miner-heater",
    "avalon-nano-3s":   "bitcoin-merch-avalon-nano-3s-bitcoin-miner-6-th-s",
    "nerdqx":           "bitcoin-merch®-nerdqx-8th-s-home-miner-w-power-supply",
}
SOLOSATOSHI = {  # WooCommerce slug
    "bitaxe-supra":     "bitaxe-supra",
    "bitaxe-gamma":     "bitaxe-gamma",
    "bitaxe-gamma-duo": "bitaxe-duo-bitcoin-solo-miner-650-model",
    "bitaxe-gt-801":    "bitaxe-gt-gamma-turbo",
    "nerdqaxe-pp":      "nerdqaxe-plus-plus",
    "avalon-nano-3s":   "avalon-nano-3s-bitcoin-solo-miner",
    "avalon-mini-3":    "canaan-avalon-mini-3-37-5th-bitcoin-home-mining-space-heater",
    "avalon-q":         "canaan-avalon-q-90th-bitcoin-home-miner",
    "bitaxe-gamma-hex": "bitaxe-gamma-hex",
    "bitaxe-naja-duo":  "bitaxe-naja-duo",
    "heatbit-bitair":   "heatbit-bitair-air-purifier-bitcoin-miner",
}
BITAXEDE = {  # product page slug
    "bitaxe-gamma":  "bitaxe-gamma-601",
    "bitaxe-gt-801": "bitaxe-gt",
    "nerdaxe-gamma": "nerdaxe-gamma-601",
    "nerdaxe-gaia":  "nerdaxe-gaia-bitcoin-miner",
    "nerdqaxe-pp":   "nerdqaxe-plus-plus-48th",
    "bitaxe-702":    "bitaxe-702",
    "nerdaxe-gaia-copper-pro": "nerdaxe-gaia-pro-bitcoin-miner",
}
POWERMINING = {  # Shopify handle
    "bitaxe-gamma":  "bitaxe-gamma",
    "nerdaxe-gamma": "nerdaxe-gamma",
    "nerdqaxe-pp":   "nerdqaxe",
    "bitcube":       "bitcube",
    "avalon-nano-3s": "canaan-avalon-nano-3s",
}

ALTAIR = {  # product slug -> (variation attribute filter or None)
    "avalon-nano-3s": ("canaan-avalon-nano-3s", None),
    "avalon-mini-3":  ("canaan-avalon-mini-3", None),
    "avalon-q":       ("avalon-q", ("attribute_power-plug", "USA")),
    "hammer-bc04":    ("hammer-miner-bc04-home-bitcoin-miner", None),
    "heatbit-bitair": ("heatbit-bitair-bitcoin-miner-air-purifier", None),
    "hammer-thor-p2": ("thor-p2-bitcoin-miner", ("attribute_power-supply", "US")),
    "hammer-bc08":    ("hammer-miner-bc08-12th-desktop-bitcoin-miner", None),
    "gekko-kbox-22":  ("gekkoscience-kbox-bitcoin-miner", None),
}
HEATBIT = {  # Shopify handle -> regex the US variant title must match
    "heatbit-trio":   ("heatbit-trio", r"/ US /"),
    "heatbit-maxi":   ("heatbit-maxi", r"/ US / Maxi$"),
    "heatbit-canvas": ("heatbit-canvas", r".*"),
    "heatbit-bitair": ("bitair", r".*"),
    "heatbit-bitwater": ("bitwater", r".*"),
}
BRAIINS = {"braiins-bmm-101": "bmm-101"}       # braiinsforge.com/products/<slug>
DCENTRAL = {"avalon-mini-3": "canaan-avalon-mini-3", "nerdoctaxe": "the-nerdoctaxe-gamma",
            "dcentral-stealthminer": "the-stealthminer"}  # WooCommerce slug
DTV = {"bitforge-nano": "bitforge-nano"}             # WooCommerce slug
NMMINER = {"nmqaxe-nexus": ("nmqaxe-nexus", "US")}   # WooCommerce slug, adapter variant
FUTUREBIT = {"futurebit-apollo-iii": "apollo-iii-standard"}   # Shopify handle (miner-only version)
# Every listing title for a home miner must contain these words (lower-case), or the listing is skipped as a possible mis-match.
TITLE_MUST = {
    "avalon-nano-3s": ["avalon", "nano 3s"], "avalon-mini-3": ["avalon", "mini 3"], "avalon-q": ["avalon q"],
    "heatbit-trio": ["trio"], "heatbit-maxi": ["maxi"], "heatbit-canvas": ["canvas"],
    "braiins-bmm-101": ["bmm 101"], "hammer-bc04": ["hammer", "bc04"],
    # strict title words for the 2026-10-21 additions: a different product (stand, screen, Ghost edition, Thor X1...) never attaches
    "bitaxe-gamma-hex": ["hex", "1300"], "bitaxe-naja-duo": ["naja duo"], "nerdoctaxe": ["nerdoctaxe"],
    "bitforge-nano": ["bitforge nano"], "heatbit-bitair": ["bitair"], "heatbit-bitwater": ["bitwater"], "futurebit-apollo-iii": ["apollo iii"],
    "hammer-thor-p2": ["thor p2"], "hammer-bc08": ["bc08"], "gekko-kbox-22": ["kbox"], "dcentral-stealthminer": ["stealthminer"],
    "nmqaxe-nexus": ["nmqaxe", "nexus"], "nerdqx": ["nerdqx"],
}
TITLE_NOT = {  # words that mean a different product (accessory, other edition)
    "bitforge-nano": ["ghost"], "nerdoctaxe": ["stand", "screen", "fan", "heatsink", "hydro"], "bitaxe-naja-duo": ["stand", ".stl"],
    "hammer-bc08": ["hydro"], "futurebit-apollo-iii": ["full node", "apollo ii "], "heatbit-bitair": ["filter"],
}


def title_ok(model, title):
    t = re.sub(r"\s+", " ", title.lower()) + " "
    return all(w in t for w in TITLE_MUST.get(model, [])) and not any(w in t for w in TITLE_NOT.get(model, []))


def ship_wait(text):
    """'Ships in 4-6 weeks' / 'Pre-order' wording near the top of a listing -> (status, note). None if it reads as ready to ship."""
    t = re.sub(r"\s+", " ", text or "")[:400]
    if re.search(r"pre-?order", t, re.I):
        m = re.search(r"(?:shipping|ships) (?:with)?in \d+\s*[-–]\s*\d+ weeks", t, re.I)
        return "preorder", (m.group(0).capitalize() if m else "Pre-order")
    m = re.search(r"ships in (\d+)\s*[-–]\s*(\d+) weeks", t, re.I)
    if m:
        return "backorder", f"Ships in {m.group(1)}-{m.group(2)} weeks (per the shop)"
    return None


UNSCRAPABLE = [
    {"seller": "MineShop (mineshop.eu)", "url": "https://mineshop.eu", "reason": "HTTP 403 (bot protection) from the collector box; its Shopify/Woo feeds are blocked. Needs manual checks or a partner feed."},
    {"seller": "NerdQaxe Store (nerdqaxestore.com)", "url": "https://nerdqaxestore.com", "reason": "TLS/connection failure from the collector box (curl exit 35) and HTTP 500 via WebFetch on 2026-10-16. Retry later / from another network."},
    {"seller": "Plebsource (plebsource.com)", "url": "https://plebsource.com", "reason": "TLS/connection failure from the collector box (curl exit 35) on 2026-10-16."},
    {"seller": "Canaan official shop (shop.canaan.io)", "url": "https://shop.canaan.io", "reason": "HTTP 403 (bot protection) on 2026-10-21. Avalon models are tracked at authorized US resellers instead."},
    {"seller": "TinyChipHub (tinychiphub.com)", "url": "https://tinychiphub.com", "reason": "JS-rendered Shopline storefront; no usable public product feed found. Not scraped."},
    {"seller": "Mining Now / MinerCompare (aggregators)", "url": "https://miningnow.com", "reason": "Competitors/aggregators - deliberately NOT scraped; used only as market research.", "internal": True},
    {"seller": "CryptoMinerBros, MillionMiner, bitaxehardware.com", "url": "", "reason": "Deliberately excluded for now: unvetted sellers (wire/crypto-only payment, anomalous $69-$79 Gamma prices, no price in structured data). Vet before listing.", "internal": True},
]


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def http_get(url, accept="*/*", headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, **(headers or {})})
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


def get_json(url, headers=None):
    return json.loads(http_get(url, "application/json", headers))


def offer(seller, model, title, url, price, currency, status, in_stock, config, checked_at, source_url, extra=None):
    o = {
        "id": f"{seller}:{model}", "seller": seller, "model": model, "title": title, "url": url,
        "price": round(float(price), 2), "currency": currency, "stock_status": status, "in_stock": bool(in_stock),
        "config": config, "checked_at": checked_at, "source_url": source_url, "stale": False,
    }
    if extra: o.update(extra)
    return o


def strip_html(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S))).strip()


def woo_status(d):
    """Stock status from a WooCommerce Store API product/variation. The stock_availability text/class is what the shop
    shows shoppers; the bare is_in_stock flag can disagree with it (it stays True for backorders), so it is only a fallback."""
    sa = d.get("stock_availability") or {}
    cls, txt = (sa.get("class") or "").lower(), (sa.get("text") or "").lower()
    if "out-of-stock" in cls or "out of stock" in txt or "sold out" in txt:
        return "out_of_stock"
    if re.search(r"pre-?order", txt):
        return "preorder"
    if "backorder" in cls or "backorder" in txt:
        return "backorder"
    if "in-stock" in cls or "in stock" in txt:
        return "in_stock"
    return "in_stock" if d.get("is_in_stock") else "out_of_stock"


def text_status(txt):
    t = (txt or "").lower()
    if "out of stock" in t or "sold out" in t: return "out_of_stock"
    if re.search(r"pre-?order", t): return "preorder"
    if "backorder" in t: return "backorder"
    if "in stock" in t: return "in_stock"
    return "unknown"


def ld_nodes(html):
    out = []
    for m in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S):
        try: d = json.loads(m)
        except ValueError: continue
        for n in (d if isinstance(d, list) else d.get("@graph", [d])):
            if isinstance(n, dict): out.append(n)
    return out


def ld_image(n):
    img = n.get("image")
    img = img[0] if isinstance(img, list) and img else img
    return img.get("url") if isinstance(img, dict) else img


# --------------------------------------------------------------------------------------
# Seller adapters. Each returns a list of offers; raises on total failure.
# --------------------------------------------------------------------------------------
def fetch_shopify_all(base, headers=None):
    products, page = [], 1
    while page <= 6:
        d = get_json(f"{base}/products.json?limit=250&page={page}", headers)
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
        if not p or not title_ok(model, p["title"]): missing.append(model); continue
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
        if float(v["price"]) <= 0: missing.append(model); continue
        wait = ship_wait(strip_html(p.get("body_html") or "")) if avail and model in TITLE_MUST else None
        status = wait[0] if wait else ("in_stock" if avail else "out_of_stock")
        out.append(offer("bitcoinmerch", model, p["title"], url, v["price"], "USD",
                         status, status == "in_stock", cfg, ts, f"{base}/products.json",
                         {"compare_at": float(v["compare_at_price"]) if v.get("compare_at_price") else None,
                          "ship_note": wait[1] if wait else None,
                          "image_src": (p.get("images") or [{}])[0].get("src")}))
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
            st = woo_status(d)
            return {"attrs": {a["name"]: a["value"] for a in v["attributes"]},
                    "price": int(d["prices"]["price"]) / 10 ** d["prices"]["currency_minor_unit"],
                    "status": st, "in_stock": st == "in_stock"}
        with ThreadPoolExecutor(max_workers=3) as vex:  # modest parallelism, still polite
            vars_ = list(vex.map(fetch_var, p.get("variations", [])))
        if not vars_:
            pr = p["prices"]
            st = woo_status(p)
            vars_ = [{"attrs": {}, "price": int(pr["price"]) / 10 ** pr["currency_minor_unit"], "status": st, "in_stock": st == "in_stock"}]

        def na_psu(v):
            return v["attrs"].get("Power Supply", "").lower().startswith("north america") or v["attrs"].get("Power Supply", "").lower().startswith("north american")
        def bare(v):  # no stand / no rear fan add-ons
            return all(v["attrs"].get(k, "No") in ("None", "No") for k in ("Stand", "Rear Fan"))
        pool = [v for v in vars_ if na_psu(v) and bare(v)] or [v for v in vars_ if na_psu(v)] or vars_
        stocked = [v for v in pool if v["in_stock"]]
        v = min(stocked or pool, key=lambda v: v["price"])
        cfg = ", ".join(f"{k}: {val}" for k, val in v["attrs"].items()) or "single option"
        n_in = sum(1 for x in vars_ if x["in_stock"])
        name = re.sub(r"&#8211;", "-", p["name"])
        if not title_ok(model, name) or v["price"] <= 0: missing.append(model); continue
        status = "in_stock" if stocked else ("preorder" if any(x["status"] == "preorder" for x in pool) else
                                             "backorder" if any(x["status"] == "backorder" for x in pool) else "out_of_stock")
        out.append(offer("solosatoshi", model, name, p["permalink"], v["price"], "USD",
                         status, bool(stocked), cfg, ts, f"{api}?slug={slug}",
                         {"variants_in_stock": n_in, "variants_total": len(vars_),
                          "lowest_any_variant": min(x["price"] for x in vars_),
                          "image_src": (p.get("images") or [{}])[0].get("src")}))
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


# Power Mining (Latvia) shows EU visitors prices incl. 21% VAT and everyone else the ex-VAT price. Without a
# localization cookie Shopify serves the EU (LV) price, so ask for the US storefront explicitly.
POWERMINING_US = {"Cookie": "localization=US"}


def shopify_country(html):
    m = re.search(r'Shopify\.country\s*=\s*"([A-Z]{2})"', html)
    return m.group(1) if m else None


def collect_powermining(ts):
    base = SELLERS["powermining"]["url"]
    # Guard: if the US storefront isn't served, fail the seller (previous offers carry forward as stale)
    # rather than write VAT-inclusive EU prices over the US ones.
    country = shopify_country(http_get(f"{base}/products/{next(iter(POWERMINING.values()))}", headers=POWERMINING_US))
    if country != "US":
        raise RuntimeError(f"US storefront not served (Shopify.country={country!r}); refusing EU VAT prices")
    by_handle = {p["handle"]: p for p in fetch_shopify_all(base, POWERMINING_US)}
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
        html = http_get(url, headers=POWERMINING_US)
        if shopify_country(html) != "US":
            raise RuntimeError(f"US storefront not served for {handle}")
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)))
        pre = re.search(r"you can now pre-order|coming soon[^.]{0,80}pre-order|pre-orders open", text, flags=re.I)
        ship = (re.search(r"Shipping [^.!]{0,60}\d{4}!?", text) or re.search(r"Christmas delivery", text, flags=re.I)) if pre else None
        status = "preorder" if pre else ("in_stock" if avail else "out_of_stock")
        cfg = (f"Variant: {v['title']}; USB-C power supply and cable in the box; US price, no VAT (EU buyers pay 21% VAT on top); shipping extra" if model == "bitcube"
               else f"Variant: {v['title']}; page says a 140 W power supply is included; US price, no VAT (EU buyers pay 21% VAT on top); shipping extra" if model == "avalon-nano-3s"
               else f"Variant: {v['title']}; page lists power supply + stand in the box; US price, no VAT (EU buyers pay 21% VAT on top); shipping extra")
        out.append(offer("powermining", model, p["title"], url, v["price"], "EUR", status,
                         bool(avail) and not pre, cfg, ts, url,
                         {"compare_at": float(v["compare_at_price"]) if v.get("compare_at_price") else None,
                          "ship_note": ("Seller says delivery by Christmas" if ship and ship.group(0).lower() == "christmas delivery" else ship.group(0) if ship else None)}))
        time.sleep(1)
    return out, missing


def collect_altair(ts):
    """Altair's Store API is blocked, but its product pages are not: variable products embed WooCommerce's
    data-product_variations JSON (price + availability per variation); simple products carry schema.org Product JSON-LD."""
    import html as _h
    base = SELLERS["altair"]["url"]
    out, missing = [], []
    for model, (slug, want) in ALTAIR.items():
        url = f"{base}/product/{slug}/"
        page = http_get(url)
        nodes = ld_nodes(page)
        prod = next((n for n in nodes if n.get("@type") in ("Product", "ProductGroup")), None)
        title = (prod or {}).get("name") or _h.unescape(re.search(r"<title>(.*?)</title>", page, re.S).group(1)).split(" - ")[0]
        if not title_ok(model, title): missing.append(model); continue
        m = re.search(r'data-product_variations="([^"]+)"', page)
        if m:
            vs = json.loads(_h.unescape(m.group(1)))
            if not isinstance(vs, list) or not vs: missing.append(model); continue
            if want:
                vs = [v for v in vs if v["attributes"].get(want[0]) == want[1]]
                if not vs: missing.append(model); continue
            for v in vs:
                v["_status"] = text_status(strip_html(v.get("availability_html", ""))) if v.get("availability_html") else ("in_stock" if v.get("is_in_stock") else "out_of_stock")
            avail = [v for v in vs if v["_status"] == "in_stock"]
            v = min(avail or vs, key=lambda v: float(v["display_price"]))
            price, status = float(v["display_price"]), v["_status"]
            cfg = ", ".join(f"{k.replace('attribute_', '').replace('-', ' ').title()}: {val}" for k, val in v["attributes"].items()) or "single option"
            extra = {"variants_in_stock": len(avail), "variants_total": len(vs)}
        elif prod and prod.get("@type") == "Product" and prod.get("offers"):
            o = prod["offers"]; o = o[0] if isinstance(o, list) else o
            if o.get("priceCurrency", "USD") != "USD": missing.append(model); continue
            price = float(o["price"])
            ld_st = SCHEMA_STATUS.get(str(o.get("availability", "")).rsplit("/", 1)[-1], ("unknown", False))[0]
            am = re.search(r"Availability:\s*([A-Za-z \-]{2,40})", strip_html(page))
            page_st = text_status(am.group(1)) if am else "unknown"
            status = page_st if page_st != "unknown" else ld_st      # the text shoppers see wins if the two disagree
            if re.search(r"preorder now|pre-order now", strip_html(page), re.I):
                status = "preorder"
            cfg, extra = "single option", {}
        else:
            missing.append(model); continue
        extra["image_src"] = ld_image(prod) if prod else None
        out.append(offer("altair", model, _h.unescape(title), url, price, "USD", status, status == "in_stock",
                         cfg + "; ships from St. Louis, MO", ts, url, extra))
        time.sleep(1)
    return out, missing


HEATBIT_LAUNCH = {"heatbit-bitwater"}   # brand-new products on pre-order: show the stated ship window, not the "sold out this season" note


def heatbit_ship_note(text):
    m = re.search(r"(?i:ships) (?:in )?(Q[1-4] \d{4}|(?:early|mid|late) \d{4}|[A-Z][a-z]+ \d{4})", text or "")
    return f"Pre-order. Seller says it ships {m.group(1)}" if m else "Pre-order. Read the seller's shipping note"


def collect_heatbit(ts):
    base = SELLERS["heatbit"]["url"]
    by_handle = {p["handle"]: p for p in fetch_shopify_all(base)}
    out, missing = [], []
    for model, (handle, vpat) in HEATBIT.items():
        p = by_handle.get(handle)
        if not p or not title_ok(model, p["title"]): missing.append(model); continue
        vs = [v for v in p["variants"] if re.search(vpat, v["title"])]
        if not vs: missing.append(model); continue
        avail = [v for v in vs if v["available"]]
        v = min(avail or vs, key=lambda v: float(v["price"]))
        url = f"{base}/products/{handle}"
        # Shopify 'available' stays true for pre-orders. Heatbit tags pre-order products and shows a
        # "Sold Out for This Season - Preorder Now" banner on those pages, so check both.
        page_txt = strip_html(http_get(url))
        pre = ("pre-order" in [t.lower() for t in p.get("tags", [])]) or bool(re.search(r"sold out for this season|pre-?order now", page_txt, re.I))
        status = "preorder" if (avail and pre) else ("in_stock" if avail else "out_of_stock")
        cfg = ("" if v["title"] == "Default Title" else f"Variant: {v['title']}; ") + "sold direct by the maker; shipping and tax extra"
        out.append(offer("heatbit", model, p["title"], url, v["price"], "USD", status, status == "in_stock", cfg, ts, f"{base}/products.json",
                         {"compare_at": float(v["compare_at_price"]) if v.get("compare_at_price") else None,
                          "ship_note": (heatbit_ship_note(strip_html(p.get("body_html") or "") + " " + page_txt) if model in HEATBIT_LAUNCH else "Seller says this season's stock is sold out; pre-orders open") if status == "preorder" else None,
                          "image_src": (p.get("images") or [{}])[0].get("src")}))
        time.sleep(1)
    return out, missing


def collect_braiins(ts):
    base = SELLERS["braiins"]["url"]
    out, missing = [], []
    for model, slug in BRAIINS.items():
        url = f"{base}/products/{slug}"
        prod = next((n for n in ld_nodes(http_get(url)) if n.get("@type") == "Product"), None)
        if not prod or not title_ok(model, prod.get("name", "")): missing.append(model); continue
        o = prod["offers"]; o = o[0] if isinstance(o, list) else o
        if o.get("priceCurrency") != "USD": missing.append(model); continue
        status, ins = SCHEMA_STATUS.get(str(o.get("availability", "")).rsplit("/", 1)[-1], ("unknown", False))
        out.append(offer("braiins", model, prod["name"], url, o["price"], "USD", status, ins,
                         "Sold direct by the maker (US store); shipping and tax extra", ts, url, {"image_src": ld_image(prod)}))
    return out, missing


def collect_dcentral(ts):
    base = SELLERS["dcentral"]["url"]
    api = f"{base}/wp-json/wc/store/v1/products"
    out, missing = [], []
    for model, slug in DCENTRAL.items():
        res = get_json(f"{api}?slug={urllib.parse.quote(slug)}")
        if not res or not title_ok(model, res[0]["name"]): missing.append(model); continue
        p = res[0]; pr = p["prices"]
        if pr["currency_code"] != "CAD" or int(pr["price"]) <= 0: missing.append(model); continue   # CA$0 "Planned Board" placeholders
        status = woo_status(p)
        out.append(offer("dcentral", model, p["name"], p["permalink"], int(pr["price"]) / 10 ** pr["currency_minor_unit"], "CAD",
                         status, status == "in_stock", "Canadian dollars; ships from Canada (import costs may apply)", ts, f"{api}?slug={slug}",
                         {"image_src": (p.get("images") or [{}])[0].get("src")}))
    return out, missing


def collect_dtv(ts):
    base = SELLERS["dtv"]["url"]
    api = f"{base}/wp-json/wc/store/v1/products"
    out, missing = [], []
    for model, slug in DTV.items():
        res = get_json(f"{api}?slug={urllib.parse.quote(slug)}")
        if not res or not title_ok(model, res[0]["name"]): missing.append(model); continue
        p = res[0]; pr = p["prices"]
        price = int(pr["price"]) / 10 ** pr["currency_minor_unit"]
        if pr["currency_code"] != "USD" or price <= 0: missing.append(model); continue
        status = woo_status(p)
        out.append(offer("dtv", model, re.sub(r"&#8211;|&#124;", "-", p["name"]), p["permalink"], price, "USD", status, status == "in_stock",
                         "Power supply included per listing; shipping and tax extra", ts, f"{api}?slug={slug}",
                         {"image_src": (p.get("images") or [{}])[0].get("src")}))
    return out, missing


def collect_nmminer(ts):
    base = SELLERS["nmminer"]["url"]
    api = f"{base}/wp-json/wc/store/v1/products"
    out, missing = [], []
    for model, (slug, plug) in NMMINER.items():
        res = get_json(f"{api}?slug={urllib.parse.quote(slug)}")
        if not res or not title_ok(model, res[0]["name"]): missing.append(model); continue
        p = res[0]
        # product-level is_in_stock can be wrong for variable products: read the US-adapter variation itself
        var = next((v for v in p.get("variations", []) if any(a["value"] == plug for a in v["attributes"])), None)
        d = get_json(f"{api}/{var['id']}") if var else p
        pr = d["prices"]
        price = int(pr["price"]) / 10 ** pr["currency_minor_unit"]
        if pr["currency_code"] != "USD" or price <= 0: missing.append(model); continue
        status = woo_status(d)
        reg = int(pr.get("regular_price") or 0) / 10 ** pr["currency_minor_unit"]
        out.append(offer("nmminer", model, re.sub(r"&#8212;|&#8211;", "-", p["name"]), p["permalink"], price, "USD", status, status == "in_stock",
                         f"Adapter: {plug}; sold direct by the maker; shipping and tax extra", ts, f"{api}?slug={slug}",
                         {"compare_at": reg if reg > price else None, "image_src": (p.get("images") or [{}])[0].get("src")}))
    return out, missing


def collect_futurebit(ts):
    base = SELLERS["futurebit"]["url"]
    by_handle = {p["handle"]: p for p in fetch_shopify_all(base)}
    out, missing = [], []
    for model, handle in FUTUREBIT.items():
        p = by_handle.get(handle)
        if not p or not title_ok(model, p["title"]): missing.append(model); continue
        vs = p["variants"]
        avail = [v for v in vs if v["available"]]
        v = min(avail or vs, key=lambda v: float(v["price"]))
        if float(v["price"]) <= 0: missing.append(model); continue
        wait = ship_wait(p["title"] + " " + strip_html(p.get("body_html") or "")) if avail else None
        status = wait[0] if wait else ("in_stock" if avail else "out_of_stock")
        out.append(offer("futurebit", model, p["title"], f"{base}/products/{handle}", v["price"], "USD", status, status == "in_stock",
                         "Miner-only Standard version, sold direct by the maker; the Full Node version costs more", ts, f"{base}/products.json",
                         {"ship_note": wait[1] if wait else None, "image_src": (p.get("images") or [{}])[0].get("src")}))
    return out, missing


ADAPTERS = {"bitcoinmerch": collect_bitcoinmerch, "solosatoshi": collect_solosatoshi,
            "bitaxede": collect_bitaxede, "powermining": collect_powermining,
            "altair": collect_altair, "heatbit": collect_heatbit, "braiins": collect_braiins, "dcentral": collect_dcentral,
            "dtv": collect_dtv, "futurebit": collect_futurebit, "nmminer": collect_nmminer}


def fetch_fx():
    try:
        d = get_json("https://api.frankfurter.dev/v1/latest?base=EUR&symbols=USD,CAD")
        return {"EUR_USD": d["rates"]["USD"], "CAD_USD": round(d["rates"]["USD"] / d["rates"]["CAD"], 6),
                "date": d["date"], "source": "Frankfurter (ECB reference rates)"}
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

    with ThreadPoolExecutor(max_workers=8) as ex:  # one thread per seller; each seller is hit sequentially
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
        rate = (fx or {}).get(f'{o["currency"]}_USD')
        o["price_usd_approx"] = o["price"] if o["currency"] == "USD" else (round(o["price"] * rate, 2) if rate else None)

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
