#!/usr/bin/env python3
"""Build the Bitaxe Radar static site from data/latest.json + data/history.json. Stdlib only.

Run after the collector (the GitHub Actions workflow does: collect -> build_site.py -> deploy `site/`).

Outputs
  site/data.js                      data for the interactive home page tables/chart (app.js)
  site/index.html                   home page = templates/home.html + pre-rendered summary, canonical, OG, JSON-LD
  site/models/<id>/index.html       one pre-rendered page per tracked model
  site/compare/<a>-vs-<b>/          model-vs-model pages
  site/sellers/<id>/                one page per tracked seller
  site/where-to-buy-bitaxe/, site/in-stock/, site/deals/, site/how-we-track/, site/advertise/
  site/sitemap.xml, site/robots.txt, site/404.html

Every number on every page comes from the data files (nothing is invented); the hand-written text is
spec context, buying checklists and honest caveats. Pages that would be thin are marked noindex.
"""
import html as _html
import json
import math
import re
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from pathlib import Path

import earnings as E
import newsletter as NL
import newlows

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
BASE = "https://bitaxeradar.com"
CONTACT = "contact@bitaxeradar.com"
METHODOLOGY_UPDATED = "2026-10-21"      # bump when the hand-written methodology text changes
NETWORK_EH_ILLUSTRATION = 1000          # EH/s, round number for the lottery illustration only (labelled as such on pages)
BLOCKS_PER_YEAR = 52560                 # 144 blocks/day * 365
ELEC_RATES = (0.10, 0.15, 0.25)         # $/kWh scenarios (assumptions, labelled as such)

latest = json.loads((ROOT / "data" / "latest.json").read_text())
history = json.loads((ROOT / "data" / "history.json").read_text())
latest = dict(latest, unscrapable=[u for u in latest["unscrapable"] if not u.get("internal")])

# ---------------------------------------------------------------------------------------------
# 1) data.js for the interactive home page (unchanged behaviour)
# ---------------------------------------------------------------------------------------------
_PUBLIC_SELLER_KEYS = ("name", "url", "currency")
_public_latest = {k: v for k, v in latest.items() if k not in ("unscrapable", "errors", "unmapped_products")}
_public_latest["sellers"] = {sid: {k: s[k] for k in _PUBLIC_SELLER_KEYS if k in s} for sid, s in latest["sellers"].items()}
payload = {"latest": _public_latest, "history": history}
(SITE / "data.js").write_text("window.RADAR = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
print("wrote site/data.js:", len(latest["offers"]), "offers,", len(history), "history series")

# ---------------------------------------------------------------------------------------------
# 2) shared config parsed from app.js (single source of truth for affiliate params + signup Worker)
# ---------------------------------------------------------------------------------------------
_app = (SITE / "app.js").read_text()
AFFILIATE = dict(re.findall(r'(\w+)\s*:\s*"([^"]+)"', re.search(r"var AFFILIATE\s*=\s*\{(.*?)\};", _app, re.S).group(1)))
WORKER_URL = re.search(r'var WORKER_URL\s*=\s*"([^"]+)"', _app).group(1)
TURNSTILE_SITEKEY = re.search(r'var TURNSTILE_SITEKEY\s*=\s*"([^"]+)"', _app).group(1)
SIGNUP_ENABLED = re.search(r"var SIGNUP_ENABLED\s*=\s*(true|false)", _app).group(1) == "true"
_cfb = re.search(r'var CF_BEACON_TOKEN\s*=\s*"([^"]*)"', _app)
CF_BEACON_TOKEN = _cfb.group(1) if _cfb else ""     # Cloudflare Web Analytics site token (public); empty = no analytics tag
ANALYTICS = (f"<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" data-cf-beacon='{{\"token\": \"{CF_BEACON_TOKEN}\"}}'></script>\n"
             if re.fullmatch(r"[0-9a-f]{32}", CF_BEACON_TOKEN or "") else "")

# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
MODELS = latest["models"]
SELLERS = latest["sellers"]
OFFERS = latest["offers"]
FX = latest.get("fx") or {}
GEN = datetime.strptime(latest["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
STATUS = {"in_stock": "In stock", "out_of_stock": "Out of stock", "preorder": "Pre-order", "backorder": "Backorder", "unknown": "Unknown"}
NET, NET_OK = E.load_network(ROOT / "data" / "network.json")   # live mining inputs (mempool.space), cached; hidden if older than 48h
AVAIL = {"in_stock": "https://schema.org/InStock", "out_of_stock": "https://schema.org/OutOfStock",
         "preorder": "https://schema.org/PreOrder", "backorder": "https://schema.org/BackOrder"}


def esc(s):
    return _html.escape(str(s), quote=True)


def parse_t(iso):
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def money(v, cur="USD"):
    return {"USD": "$", "EUR": "€", "CAD": "CA$"}.get(cur, cur + " ") + f"{v:,.2f}"


ET = ZoneInfo("America/New_York")


def fmt_time(iso):
    """Shown in US Eastern, where most visitors are: 'Oct 23, 2026 8:44 AM ET'."""
    d = parse_t(iso).astimezone(ET)
    return f"{d:%b} {d.day}, {d.year} {d.hour % 12 or 12}:{d:%M} {'AM' if d.hour < 12 else 'PM'} ET"


def fmt_day(iso_or_dt):
    d = iso_or_dt if isinstance(iso_or_dt, datetime) else parse_t(iso_or_dt)
    return f"{d:%b} {d.day}"


def tag_time(iso):
    return f'<time datetime="{esc(iso)}">{esc(fmt_time(iso))}</time>'


def shorten(text, n):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= n:
        return text
    cut = text[: n - 1].rsplit(" ", 1)[0].rstrip(",;:-– ")
    return cut + "…"


def jsonld_tag(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def sig2(x):
    """round to 2 significant figures, with thousands separators"""
    if x <= 0:
        return "0"
    d = 10 ** (int(math.floor(math.log10(x))) - 1)
    return f"{int(round(x / d) * d):,}"


def sname(sid):
    return (SELLERS.get(sid) or {}).get("name", sid)


def aff_param(sid):
    return AFFILIATE.get(sid)


def offer_href(o):
    p = aff_param(o["seller"])
    return o["url"] + (("&" if "?" in o["url"] else "?") + p) if p else o["url"]


def store_link(sid):
    """Link to a shop's home page, with its affiliate code when it has one (same logic as product links)."""
    s = SELLERS[sid]
    aff = aff_param(sid)
    rel = "sponsored nofollow noopener" if aff else "nofollow noopener"
    href = offer_href(dict(seller=sid, url=s["url"]))
    return (f'<a href="{esc(href)}" rel="{rel}" target="_blank">{esc(s["url"].replace("https://", "").rstrip("/"))}</a>'
            + (' <span class="ph">affiliate link</span>' if aff else ""))


def offer_link(o, text=None, cls="btn"):
    aff = aff_param(o["seller"])
    rel = "sponsored nofollow noopener" if aff else "nofollow noopener"
    t = text or f"View at {sname(o['seller'])} ↗"
    a = f'<a class="{cls}" href="{esc(offer_href(o))}" target="_blank" rel="{rel}">{esc(t)}</a>'
    return a + ('<div class="ph">affiliate link</div>' if aff else "")


def best_cta(st):
    """Above-the-fold 'go to the best deal' box: cheapest in-stock listing, plus the cheapest USD-priced one if different."""
    best, usd_best = st["best"], st["best_usd"]
    if not best:
        return ""
    picks = [("Cheapest in stock", best)]
    if usd_best and usd_best["id"] != best["id"]:
        picks.append(("Cheapest at a US shop", usd_best))
    items = "".join(
        f'<div><small>{esc(lbl)}</small><b>{money(o["price"], o["currency"])}</b>'
        + f'<p class="hint">at <strong>{esc(sname(o["seller"]))}</strong>'
        + (f' · ≈ {money(usd(o))}' if o["currency"] != "USD" and usd(o) is not None else "") + ' ' + badge(o["stock_status"]) + '</p>'
        + f'{offer_link(o, "Go to " + sname(o["seller"]) + " ↗")}</div>'
        for lbl, o in picks)
    return f'<div class="cta" role="region" aria-label="Best deal right now">{items}</div>'


def preorder_cta(st):
    """No stock anywhere, but someone takes pre-orders: show the cheapest pre-order, clearly labelled as not in stock."""
    pre = [o for o in st["offers"] if o["stock_status"] in ("preorder", "backorder") and usd(o) is not None]
    if not pre:
        return ""
    o = min(pre, key=usd)
    return (f'<div class="cta" role="region" aria-label="Pre-order"><div><small>{esc(STATUS[o["stock_status"]])} (not in stock yet)</small><b>{money(o["price"], o["currency"])}</b>'
            f'<p class="hint">at <strong>{esc(sname(o["seller"]))}</strong> {badge(o["stock_status"])}</p>'
            f'{offer_link(o, "Go to " + sname(o["seller"]) + " ↗")}</div></div>')


SPONSOR_SLOT = ('<aside class="sponsor" aria-label="Sponsor spot"><small>Sponsor</small> '
                '<span>Sell miners or accessories? <a href="/advertise/">Your shop could be featured here</a>.</span></aside>')


def badge(status):
    return f'<span class="badge b-{esc(status)}">{esc(STATUS.get(status, status))}</span>'


# ---------------------------------------------------------------------------------------------
# model & seller metadata (hand-written; numbers are computed, not typed)
# ---------------------------------------------------------------------------------------------
SHORT = {"bitaxe-supra": "Bitaxe Supra", "bitaxe-ultra": "Bitaxe Ultra", "bitaxe-gamma": "Bitaxe Gamma",
         "bitaxe-gamma-duo": "Bitaxe Gamma Duo", "bitaxe-gt-801": "Bitaxe GT 801", "nerdaxe-gamma": "Nerdaxe Gamma",
         "nerdaxe-gaia": "Nerdaxe Gaia", "nerdqaxe-pp": "NerdQaxe++",
         "avalon-nano-3s": "Avalon Nano 3S", "avalon-mini-3": "Avalon Mini 3", "avalon-q": "Avalon Q", "heatbit-trio": "Heatbit Trio",
         "heatbit-maxi": "Heatbit Maxi", "heatbit-canvas": "Heatbit Canvas", "braiins-bmm-101": "Braiins Mini Miner", "hammer-bc04": "Hammer BC04",
         "bitaxe-gamma-hex": "Bitaxe Gamma Hex", "bitaxe-naja-duo": "Bitaxe Naja Duo", "nerdoctaxe": "NerdOCTaxe Gamma", "bitforge-nano": "BitForge Nano",
         "heatbit-bitair": "Heatbit Bitair", "futurebit-apollo-iii": "FutureBit Apollo III", "hammer-thor-p2": "Hammer Thor P2", "hammer-bc08": "Hammer BC08",
         "gekko-kbox-22": "GekkoScience KBox 22", "dcentral-stealthminer": "D-Central StealthMiner", "bitcube": "Bitcube", "heatbit-bitwater": "Heatbit Bitwater", "nmqaxe-nexus": "NMQAxe++ Nexus", "nerdqx": "NerdQX"}
NOINDEX_MODELS = {"bitaxe-supra", "bitaxe-ultra"}   # older generations: pages exist for completeness but stay out of the index/sitemap

MODEL_COPY = {
    "bitaxe-gamma": dict(
        intro="The Bitaxe Gamma is a single-chip open-source home miner built around the BM1370 ASIC. Sellers state roughly 1.1–1.5 TH/s depending on clock settings, cooling and power supply, at about 15–18 W. The name covers the 601 and 602 board revisions; boards with two chips are sold separately as the Gamma Duo and the GT 801, and we track those on their own pages.",
        who="Someone who wants a low-cost first ASIC to learn on or to run quietly on a desk, and who understands the payoff is a lottery ticket, not income.",
        check=["Power supply: some listings include one and some do not, and the plug type depends on the region option you pick (Solo Satoshi lists a North America option).",
               "Revision and extras: 601 vs 602, and whether a stand or fan is part of the price.",
               "Status: Pre-order and Backorder mean it is not in stock yet, even if the page has an Add to cart button."]),
    "bitaxe-gamma-duo": dict(
        intro="The Gamma Duo (model 650) puts two BM1370 chips into the same footprint as the single-chip Gamma. Sellers state about 1.6 TH/s at roughly 26 W, so it adds hashrate without moving to a larger case. It is a different board from the GT 801, which also has two BM1370 chips but is tuned for higher output.",
        who="Gamma owners who want more hashrate in the same small footprint and are fine paying for it.",
        check=["Confirm the listing is the 650 Duo, not a Gamma or GT with a similar name.",
               "Power supply: a two-chip board draws more than a Gamma, so check the supplied adapter's rating.",
               "Stand and fan options differ by seller and change the price."]),
    "bitaxe-gt-801": dict(
        intro="The Bitaxe GT (also sold as Gamma Turbo, model 801) is a two-chip BM1370 board. Sellers state 2.0–2.4 TH/s at about 43 W, which makes it the fastest of the Bitaxe-branded boards we track but also one of the hungrier ones. Because it runs hotter than a single-chip Gamma, the cooling that comes with it matters.",
        who="People who want the most hashrate from a Bitaxe-style open-source board and are comfortable with higher power draw and heat.",
        check=["Whether a power supply is included: Bitcoin Merch's listing doesn't say, so check before ordering.",
               "Cooling: look for the fan and heatsink setup the seller ships.",
               "Seller-quoted hashrate ranges are optimistic ranges, not guarantees."]),
    "nerdaxe-gamma": dict(
        intro="The Nerdaxe Gamma is a Gamma-class board (one BM1370 chip) with a color display, from the Nerdaxe line rather than the Bitaxe line. Sellers state the same ballpark hashrate and power as the Bitaxe Gamma, about 1.2 TH/s at 18 W, so the question is mainly whether the display and enclosure are worth the price difference.",
        who="Buyers who like the Gamma's numbers but want a built-in screen to see status at a glance.",
        check=["Compare against the Bitaxe Gamma's price: the silicon is the same class, so you are paying for display and case.",
               "Region variant: Power Mining lists a US version; Bitaxe.de prices include VAT.",
               "Stock changes quickly, so check the stock badge before planning around it."]),
    "nerdaxe-gaia": dict(
        intro="The Nerdaxe Gaia uses a newer BM1373 chip. Sellers state 2.4–2.6 TH/s at about 25 W, which is the best hashrate-per-watt of the miners we track on paper. It is also one of the pricier small miners, and as a newer design it has fewer long-term user reports than the Gamma family.",
        who="Buyers who care most about efficiency and are willing to pay a premium for a newer chip.",
        check=["Efficiency figures are seller-stated; treat them as targets rather than measurements.",
               "Pre-order listings may ship weeks later: read the shipping note on the seller's page.",
               "Prices can differ a lot between sellers, so compare what each listing includes."]),
    "nerdqaxe-pp": dict(
        intro="The NerdQaxe++ combines four BM1370 chips on one board. The standard version is stated at about 4.8 TH/s and 80 W; some sellers also list newer revisions (Rev 6.1 at roughly 6 TH/s and about 100 W, and Rev 7) that are not the same product at the same price. It is the highest-hashrate miner on this site, and it is closer to a small space heater than the single-chip boards.",
        who="Hobbyists who want the most hashrate from a compact open-source miner and have somewhere to put the heat and fan noise.",
        check=["Revision: 4.8 TH/s standard, Rev 6.1 and Rev 7 are different configurations, so read each listing's details before comparing prices.",
               "Fan and stand options change the price (Solo Satoshi lists them as separate choices).",
               "Power: at around 80 W or more it needs a proper supply rated for it."]),
    "bitaxe-supra": dict(
        intro="The Bitaxe Supra uses the older BM1368 chip at about 0.6–0.7 TH/s and 15 W. It has largely been superseded by the Gamma, which our data shows is available for similar money, so this page exists mostly for people who find an old listing and want to know what it is.",
        who="Mostly people who already own one. A new buyer will usually get more hashrate per dollar from a Gamma.",
        check=["Compare against a current Gamma listing before buying an older board.",
               "Make sure a power supply is included."]),
    "bitaxe-ultra": dict(
        intro="The Bitaxe Ultra uses the older BM1366 chip at about 0.4–0.5 TH/s and 12 W. It is slower than the current Gamma at a similar price, so this page is for reference.",
        who="Collectors and people who already own one.",
        check=["Compare against a current Gamma listing before buying an older board.",
               "Make sure a power supply is included."]),
}

HOME_COPY = {
    "avalon-nano-3s": dict(
        intro="The Avalon Nano 3S is Canaan's small desk miner. Sellers state about 6 TH/s at up to 140 W, roughly five times a Bitaxe Gamma's hashrate, in a finished case with an included power adapter and Wi-Fi. At 140 W it gives off about as much warmth as a small personal heater, so it doubles as a desk or foot warmer.",
        who="Someone who wants more hashrate than a Bitaxe in a finished, quiet box, for a desk, office or bedroom.",
        check=["Color: black and white are usually the same price.",
               "Solo or pool: it can do either. Pick in its settings (see our solo vs pool guide).",
               "Prices are before shipping and sales tax."]),
    "avalon-mini-3": dict(
        intro="The Avalon Mini 3 is a heater miner shaped like a baseboard heater. Sellers state 37.5 TH/s at up to 800 W, so it heats a room like a mid-size electric heater while it mines. Sellers list app control and several modes (for example a quieter night mode and an extra-heat mode).",
        who="Someone who already heats a room with electricity in winter and would rather that heat also mine Bitcoin.",
        check=["At about 800 W it runs on a normal household outlet, but don't share that circuit with other big heaters.",
               "Noise depends on the mode: sellers list roughly 33 to 55 dB.",
               "D-Central prices it in Canadian dollars and ships from Canada, so US import costs may apply. Our dollar figure is an estimate."]),
    "avalon-q": dict(
        intro="The Avalon Q is Canaan's big home miner, a tower that sellers state at 90 TH/s and about 1,674 W. That's as much heat as a full-size space heater on high, so it suits a large room, garage or basement in winter.",
        who="Someone who wants the most hashrate from a plug-in home unit and has a room that can use about 1.7 kW of heat.",
        check=["Power: about 1,674 W is close to the limit of a standard 15 A, 120 V household circuit. Check the maker's circuit guidance, use a lower power mode, or run it on a dedicated circuit.",
               "Its plug option should match your country (Altair lists a USA plug).",
               "Mine in a pool if you want small, steady payouts rather than a lottery ticket."]),
    "heatbit-trio": dict(
        intro="The Heatbit Trio is a space heater, an air purifier and a Bitcoin miner in one tall cylinder. Heatbit states 10 TH/s from 400 W of mining heat, plus another 1,100 W of ordinary electric heating for 1,500 W in total. That means only part of its heat comes from mining.",
        who="Someone who wants a room heater and air purifier anyway and likes the idea of it earning a few sats.",
        check=["It's a pre-order right now. Heatbit says this season's stock is sold out, so read the ship timing on its page.",
               "HEPA filters are a running cost. Heatbit sells replacement filters separately.",
               "Pick the US / 120 V version."]),
    "heatbit-maxi": dict(
        intro="The Heatbit Maxi is Heatbit's larger heater miner. Heatbit states 39 TH/s with 1,500 W of mining heat, so all of its heat comes from mining, plus air purification. A Maxi Pro version is listed at 60 TH/s for more money.",
        who="Someone heating a bigger room who wants the heat itself to do the mining.",
        check=["It's a pre-order right now. Heatbit says this season's stock is sold out, so read the ship timing on its page.",
               "1,500 W is the most a standard 15 A, 120 V outlet should power continuously, so give it its own circuit.",
               "Maxi and Maxi Pro look the same but differ in hashrate and price. We track the Maxi."]),
    "heatbit-canvas": dict(
        intro="The Heatbit Canvas is a flat heater miner you hang on a wall or stand up, with art on the front. Heatbit states 10 TH/s at 300 W, about 1,020 BTU of heat, for a room of up to about 150 sq ft.",
        who="Someone who wants a little warmth in a small room and a miner that looks like decor.",
        check=["It's a pre-order right now. Heatbit says this season's stock is sold out, so read the ship timing on its page.",
               "At 300 W it adds heat but won't heat a large room on its own.",
               "Color and artwork options can change the price."]),
    "braiins-bmm-101": dict(
        intro="The Braiins Mini Miner (BMM 101) is a desk lottery miner from Braiins, the company behind the Braiins Pool. Braiins states about 1 TH/s at 35–40 W, in a metal case with a touchscreen. That's a similar class to a Bitaxe Gamma, in a more finished box.",
        who="Someone who wants a solo lottery miner that looks good on a desk and doesn't need tinkering.",
        check=["It's sold direct by Braiins on its own store.",
               "At about 1 TH/s, solo mining is a long-shot lottery, and pool payouts are tiny.",
               "Prices are before shipping and sales tax."]),
    "hammer-bc04": dict(
        intro="The Hammer Miner BC04 is a compact desk miner that sellers state at 6 TH/s and 96 W, in the same hashrate class as the Avalon Nano 3S but at a lower stated power draw.",
        who="Someone comparing small 6 TH/s desk miners on price and power use.",
        check=["Compare it with the Avalon Nano 3S: same stated hashrate, different power, noise and price.",
               "Check what power supply comes in the box.",
               "Prices are before shipping and sales tax."]),
}
MODEL_COPY.update(HOME_COPY)

NEW_COPY = {   # added 2026-10-21 (docs/MINER_CATALOG.md). Stock settings only; overclock figures are named as such.
    "bitaxe-gamma-hex": dict(
        intro="The Bitaxe Gamma Hex (model 1300) puts six BM1370 chips on one Bitaxe board and comes with an all-in-one liquid cooler. Solo Satoshi states about 8.4 TH/s at 140 W at stock settings. Bitcoin Merch's listing states 10.5 TH/s at the same 140 W; we use the lower figure.",
        who="Bitaxe fans who want the most hashrate from a single open-source board and don't mind a cooler and radiator on the desk.",
        check=["Hashrate claims differ by seller (8.4 vs 10.5 TH/s at 140 W). Higher numbers need overclocking.",
               "Power supply: pick the North America option where offered, or check one is included.",
               "It has RGB lighting on the cooler; Solo Satoshi notes it can't be switched off."]),
    "bitaxe-naja-duo": dict(
        intro="The Bitaxe Naja Duo (model 1201) uses two of Bitmain's newer BM1373 chips. Sellers state about 4.4 TH/s at roughly 42 W at stock, about the power of a GT 801 for twice the hashrate. Listings that say 8 TH/s are quoting an overclock at about 92 W.",
        who="Bitaxe owners who want a big efficiency jump in a small, quiet board.",
        check=["8 TH/s is an overclock, not the stock figure.",
               "Some listings are pre-orders with multi-week shipping. Check the badge.",
               "Power supply: pick the North America option where offered."]),
    "nerdoctaxe": dict(
        intro="The NerdOCTaxe Gamma is the biggest open-source board in the Nerd family: eight BM1370 chips on one board. Sellers state 9.6 TH/s as the standard setting at about 160 W (D-Central measured nearer 208 W at the wall). 12 TH/s is an overclock.",
        who="Hobbyists who want about ten Bitaxe Gammas' worth of hashrate in one open-source box.",
        check=["12 TH/s listings are overclocked; the standard setting is about 9.6 TH/s.",
               "It needs a 12 V supply rated for about 216-240 W. Check one is included.",
               "Hydro versions are a different product and are not tracked here."]),
    "bitforge-nano": dict(
        intro="The BitForge Nano is a compact two-chip (BM1370) miner in a fully enclosed case. Sellers state 2.6 TH/s at the factory default and about 15 J/TH, so roughly 40 W. Bitcoin Merch lists it at about 29 dB.",
        who="Someone who wants a GT-class lottery miner in a closed, quiet case rather than a bare board.",
        check=["The Ghost Edition is a different listing at a different price and is not tracked here.",
               "Power supply included per the listings.",
               "Prices are before shipping and sales tax."]),
    "heatbit-bitair": dict(
        intro="The Heatbit Bitair is a tabletop HEPA air purifier with a small Bitcoin miner inside. Heatbit states 1.2 TH/s and 25 W in total at max (17 W for the mining chip), USB-C powered, for rooms up to about 200 sq ft.",
        who="Someone who wants an air purifier anyway and likes the idea of it taking a tiny solo-mining shot.",
        check=["At 1.2 TH/s it's a solo lottery ticket. Pool payouts would be tiny.",
               "Replacement filters are a running cost.",
               "Some shops list it as a pre-order. Check the badge."]),
    "futurebit-apollo-iii": dict(
        intro="The FutureBit Apollo III is a 6-inch cube home miner designed and assembled in the USA, with a built-in power supply. FutureBit states about 10-12 TH/s in Eco mode at around 15 W per TH/s (so about 180 W), and about 16-18 TH/s in Turbo mode with more power and noise. A Full Node version adds a Bitcoin node.",
        who="Someone who wants a polished, quiet US-made miner for a room or office, with the option of running a node.",
        check=["It ships in several weeks; the shop says so in the listing.",
               "We track the miner-only Standard version. The Full Node version costs more.",
               "Turbo mode adds hashrate but also heat and noise."]),
    "hammer-thor-p2": dict(
        intro="The Hammer Thor P2 is a desk miner with two BM1373 chips. Sellers state about 10 TH/s at roughly 155-166 W and about 38-40 dB.",
        who="Someone who wants about 10 TH/s on a desk without a heater-sized power draw.",
        check=["Pick the US power supply option.",
               "One shop lists multi-week shipping. Check the badge.",
               "The Thor X1 is a different, smaller model."]),
    "hammer-bc08": dict(
        intro="The Hammer BC08 is a desktop miner with eight BM1370 chips and a 5-inch touchscreen. Altair states 12 TH/s at 210 W max and about 38 dB, with a power supply in the box.",
        who="Someone who wants about 12 TH/s with a screen on a desk, quietly.",
        check=["We track the air-cooled version only. The Hydro version is a different product.",
               "At 210 W it gives off about as much heat as a small heater.",
               "Prices are before shipping and sales tax."]),
    "gekko-kbox-22": dict(
        intro="The GekkoScience KBox 22 is an all-in-one miner sold as a miner and small heater, assembled in the USA. Sellers state up to 22 TH/s at about 322-330 W in its high mode, with low (11 TH/s, ~178 W) and medium (17 TH/s, ~242 W) modes and about 38-47 dB.",
        who="Someone who wants a quiet, plug-in miner that also warms a small room.",
        check=["Hashrate and noise depend on the power mode you pick.",
               "One shop sells it as a pre-order with weeks of shipping. Check the badge.",
               "At ~330 W it adds heat but won't heat a large room on its own."]),
    "dcentral-stealthminer": dict(
        intro="The StealthMiner from D-Central is a recycled Antminer S19-class hashboard rebuilt to run on a normal 120 V outlet, with quiet Noctua fans. D-Central states 26 TH/s at 860 W for the base S19 Edition (S19j Pro and S19k Pro editions state 32-38 TH/s at 900-930 W), under 60 dB, for about 150-200 sq ft.",
        who="Someone heating a room in winter who wants an industrial-class hashboard tamed for a home outlet.",
        check=["It's refurbished, recycled hardware with a 90-day warranty.",
               "Price is in Canadian dollars and ships from Canada, so US import costs may apply.",
               "D-Central recommends a dedicated 15 A circuit."]),
    "bitcube": dict(
        intro="The Bitcube is Power Mining's own small home miner: a 74 mm cube with a 2.73-inch touchscreen, built on Canaan's Avalon A3197 chip. Power Mining states up to 777 GH/s in Turbo mode and 550 GH/s in Quiet mode, at about 20–25 W from the wall over USB-C. It's open source, runs on Wi-Fi, and can solo or pool mine.",
        who="Someone who wants a cute, quiet solo lottery miner for a desk or shelf, with nothing to build.",
        check=["It's a pre-order. Power Mining says it will deliver by Christmas.",
               "Each order includes a free 777 GH/s of hosted solo hashrate from the order date until your Bitcube arrives.",
               "The price shown is what US buyers pay, in euros with no VAT. EU buyers pay 21% VAT on top. Shipping and any import fees are extra."]),
    "heatbit-bitwater": dict(
        intro="The Heatbit Bitwater is a water heater element with a Bitcoin miner built in. It screws into the lower element port of a regular electric tank water heater and heats your water with mining chips instead of a resistance wire. Heatbit states 20 BM1370 chips, up to 34 TH/s and up to 600 W, from 12 J/TH. The water cools the chips, so there are no fans.",
        who="A homeowner with an electric tank water heater who pays for hot water anyway and wants that heat to mine Bitcoin, with no noise and no box in the room.",
        check=["It's a pre-order (Genesis batch at $899). Heatbit says later batches cost up to $1,299 and it ships Q1 2027 to the US and Canada.",
               "It only fits standard electric tank heaters (30 to 80 gallons, 1-inch NPSM element port). Not gas or heat-pump water heaters.",
               "It replaces the lower element; the upper element and thermostat stay. Heatbit says install takes 30 to 45 minutes, and the controller plugs into a normal outlet.",
               "It only mines while your tank needs heat, so real hashrate depends on how much hot water you use.",
               "Mines solo to your own address by default, or to any pool. 1-year warranty."]),
    "nmqaxe-nexus": dict(
        intro="The NMQAxe++ Nexus is a desk miner from NMMiner with two Bitmain BM1373 chips, a color screen and a big tower cooler. NMMiner states three modes: Eco about 6 TH/s at about 63 W, Normal about 8.5 TH/s at about 110 W, and Turbo about 11 TH/s at about 172 W. We use the Normal figures here.",
        who="Someone who wants a step up from a Bitaxe or NerdQaxe++ for solo mining, or a small, steady pool miner, on a normal desk outlet.",
        check=["It's sold direct by NMMiner. Its store page says it's available now and ships within 24 hours.",
               "Its listing says it runs on a 12 V / 15 A adapter (180 W max), and you pick the plug type (US, EU, UK or AUS) at checkout.",
               "The shop's pages don't say where orders ship from, and we couldn't find a warranty stated. Ask the shop before you buy.",
               "Turbo mode means more heat and fan noise. The listing doesn't state a noise level."]),
    "nerdqx": dict(
        intro="The NerdQX is a four-chip open-source style board (four Bitmain BM1370 chips) that runs AxeOS, the same web dashboard as a Bitaxe. Bitcoin Merch states up to 8.1 TH/s at about 138 W, with three fans.",
        who="Someone who wants NerdQaxe++-class hashrate or more in one box for solo mining, and is happy to buy from one US shop.",
        check=["Right now only Bitcoin Merch sells it among the shops we track, and its listing says it ships in 2-3 weeks.",
               "The listing doesn't name who makes the board, so ask the shop about warranty before you buy.",
               "The power supply is included, per the listing title.",
               "Compare the price per TH/s with the NerdQaxe++ and the Naja Duo before you buy."]),
}
MODEL_COPY.update(NEW_COPY)

COMPARE_PAIRS = [("bitaxe-gamma", "nerdqaxe-pp"), ("bitaxe-gamma", "bitaxe-gt-801"), ("bitaxe-gamma", "nerdaxe-gamma"),
                 ("bitaxe-gamma", "bitaxe-supra"), ("nerdqaxe-pp", "nerdaxe-gaia")]
COMPARE_COPY = {
    ("bitaxe-gamma", "nerdqaxe-pp"): dict(
        angle="One chip versus four: the Gamma is the small, quiet, cheap option; the NerdQaxe++ buys roughly four times the hashrate for a much larger power bill and a louder, hotter box.",
        a_for="you want the lowest entry cost, a quiet desk setup and minimal heat.",
        b_for="you want the most hashrate in a compact open-source miner and can handle ~80 W of heat and fan noise."),
    ("bitaxe-gamma", "bitaxe-gt-801"): dict(
        angle="Both use BM1370 silicon, but the GT 801 has two chips and is driven harder, so it trades power draw and heat for roughly double the hashrate.",
        a_for="you want the cheapest and coolest-running option.",
        b_for="you want about twice the hashrate and accept about 2.4× the power draw."),
    ("bitaxe-gamma", "nerdaxe-gamma"): dict(
        angle="Same chip class and the same stated hashrate and power, so the comparison is really about price, display and enclosure.",
        a_for="you only care about hashrate per dollar.",
        b_for="you want the color display and are fine paying the difference."),
    ("bitaxe-gamma", "bitaxe-supra"): dict(
        angle="The Supra is the older generation (BM1368). The Gamma uses a newer chip and states nearly double the hashrate at similar wattage, so the interesting question is whether any Supra listing is cheap enough to matter.",
        a_for="you are buying new and want the better efficiency.",
        b_for="you already own a Supra or found one at a clearly lower price."),
    ("nerdqaxe-pp", "nerdaxe-gaia"): dict(
        angle="Both are premium small miners, but they get there differently: the NerdQaxe++ uses four BM1370 chips, while the Gaia uses one newer BM1373 chip and states a much lower power draw along with a lower hashrate.",
        a_for="you want the highest hashrate and do not mind the power draw.",
        b_for="you care more about hashrate per watt and want a quieter, cooler device."),
}

SELLER_COPY = {
    "bitcoinmerch": dict(
        region="USD prices",
        about="A US shop that carries most of the Bitaxe-family miners, priced in US dollars. Most listings include a power supply.",
        notes=["Most listings say a power supply is included. The Bitaxe GT 801 listing doesn't say, so check before you buy.",
               "Prices are before shipping and sales tax."]),
    "solosatoshi": dict(
        region="USD prices",
        about="A US shop (Houston) and often one of the cheapest places for a Bitaxe, priced in US dollars with a North America power-supply option.",
        notes=["The price we show is for the North America power supply with no stand or extra fan, so it compares fairly with other shops' bundles.",
               "Stands and extra fans are optional add-ons that change the price.",
               "Prices are before shipping and sales tax."]),
    "powermining": dict(
        region="EUR prices (US price, no VAT)",
        about="A European shop that lists a US variant for some miners and says it ships to the US and Canada. Prices are in euros; the dollar figures are estimates.",
        notes=["We show the price US visitors see, which has no VAT. EU buyers pay 21% VAT on top.",
               "Pre-orders are labelled as such, with the seller's own ship-date wording when it gives one.",
               "Its FAQ says it ships to the US and Canada (express 2–4 days, standard 4–6 days; customs can add time).",
               "Shipping and import duties are not included, so the real US price will be higher than the figure shown."]),
    "altair": dict(
        region="USD prices",
        about="A US shop in St. Louis, Missouri that carries a wide range of home miners, including the Avalon line and Hammer miners, priced in US dollars.",
        notes=["Product pages say orders ship from St. Louis, MO.",
               "Prices are before shipping and sales tax."]),
    "heatbit": dict(
        region="USD prices (sold direct)",
        about="The maker of the Heatbit heater miners, selling direct from its own store in US dollars.",
        notes=["Heatbit's heater models are pre-order right now. Its site says this season's stock is sold out.",
               "We track the US / 120 V version where there's a choice.",
               "Prices are before shipping and sales tax."]),
    "braiins": dict(
        region="USD prices (sold direct)",
        about="Braiins' own hardware store (Braiins Forge), the company behind Braiins Pool and Braiins OS, selling its Mini Miner direct.",
        notes=["Prices shown are from the US version of the store.", "Prices are before shipping and sales tax."]),
    "dtv": dict(
        region="USD prices",
        about="A US electronics shop that sells Bitaxe-class miners, including the BitForge Nano, priced in US dollars.",
        notes=["Prices are before shipping and sales tax.", "Check the listing for the power-supply plug type."]),
    "futurebit": dict(
        region="USD prices (sold direct)",
        about="FutureBit's own store. FutureBit designs and assembles the Apollo home miners in the USA.",
        notes=["Some Apollo listings ship in several weeks; the listing says how long.", "Prices are before shipping and sales tax."]),
    "nmminer": dict(
        region="USD prices (sold direct)",
        about="NMMiner's own store. NMMiner makes the NMAxe and NMQAxe++ miners and the NMMiner ESP32 lottery miners, and sells them in US dollars.",
        notes=["We track the US-plug version.", "Its pages don't say where orders ship from, so check delivery time and any import fees at checkout.",
               "Prices are before shipping and sales tax."]),
    "dcentral": dict(
        region="CAD prices (ships from Canada)",
        about="A Canadian shop that sells miners, heater builds and parts, priced in Canadian dollars.",
        notes=["Prices are in Canadian dollars. Our US-dollar figures are estimates at the latest exchange rate.",
               "Orders ship from Canada, so US buyers may pay import costs on top.",
               "Its pages list a lead time on some items. Read the shipping line before you order."]),
    "bitaxede": dict(
        region="EUR prices incl. VAT",
        about="A European shop. Prices are in euros and include VAT; shipping is extra.",
        notes=["It delivers to the EU plus Switzerland, Norway, Iceland and Liechtenstein, so it's mainly useful for European buyers.",
               "Because VAT is included and shipping isn't, its dollar estimates aren't directly comparable to a US shop's pre-tax prices."]),
}

# Shop facts table (/sellers/ and each shop page). Only what the shop's own pages say (checked Oct 22, 2026);
# None means we couldn't find it stated, and the page says so instead of guessing.
SELLER_FACTS = {
    "bitcoinmerch": dict(ships="United States", warranty=None, returns="30 days", src="https://bitcoinmerch.com/policies/refund-policy"),
    "solosatoshi": dict(ships="Houston, Texas", warranty=None, returns=None, src=None),
    "powermining": dict(ships="Europe (ships to the US and Canada)", warranty=None, returns=None, src=None),
    "altair": dict(ships="St. Louis, Missouri", warranty="14 days against defects (items with a maker's warranty excluded)", returns=None, src="https://altairtech.io/refund_returns/"),
    "heatbit": dict(ships=None, warranty="12 months from shipping", returns=None, src="https://heatbit.com/policies/refund-policy"),
    "braiins": dict(ships="Warehouses in the US and the EU", warranty="2 years from delivery", returns=None, src="https://braiinsforge.com/terms"),
    "dtv": dict(ships="United States", warranty=None, returns=None, src=None),
    "futurebit": dict(ships="United States", warranty=None, returns="14 days", src="https://shop.futurebit.io/policies/refund-policy"),
    "nmminer": dict(ships=None, warranty=None, returns="30 days, unused and in original packaging", src="https://www.nmminer.com/refund_returns/"),
    "dcentral": dict(ships="Montreal, Canada", warranty="Defects reported within 30 days of delivery; in-house repair bench", returns="30 days for DOA or defects", src="https://d-central.tech/warranty/"),
    "bitaxede": dict(ships="Europe (EU, Switzerland, Norway, Iceland, Liechtenstein only)", warranty=None, returns=None, src=None),
}


def stock_rate(sid):
    """Share of all our checks of this shop's listings that found the item in stock (ready to ship)."""
    pts = [p for oid, ps in history.items() if oid.split(":", 1)[0] == sid for p in ps]
    if not pts:
        return None
    return dict(pct=round(100 * sum(1 for p in pts if p.get("in_stock")) / len(pts)), n=len(pts), first=min(p["t"] for p in pts))


def facts_cells(sid):
    f = SELLER_FACTS.get(sid, {})
    nf = '<span class="cfg">Not stated</span>'
    wr = esc(f["warranty"]) if f.get("warranty") else nf
    if f.get("returns"):
        wr += f'<br><span class="cfg">Returns: {esc(f["returns"])}</span>'
    sr = stock_rate(sid)
    rate = f'{sr["pct"]}%<br><span class="cfg">of {sr["n"]} checks</span>' if sr else "–"
    return esc(f["ships"]) if f.get("ships") else nf, wr, rate


def facts_table(sids):
    rows = []
    for sid in sids:
        ships, wr, rate = facts_cells(sid)
        rows.append(f'<tr><td><a href="/sellers/{sid}/">{esc(SELLERS[sid]["name"])}</a></td><td>{ships}</td><td>{wr}</td><td class="num">{rate}</td></tr>')
    return ('<div class="tablewrap"><table class="facts"><thead><tr><th>Shop</th><th>Ships from</th><th>Warranty</th><th class="num">In stock when we checked</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


FACTS_NOTE = ('<p class="hint">Ships from and warranty come from each shop\'s own pages. "Not stated" means we couldn\'t find it, so ask the shop. '
              'In stock counts every check of every miner the shop lists since we started tracking; pre-orders count as not in stock.</p>')

# Same menu on every page, desktop and phone (docs/NAV_AUDIT.md): All miners · Deals · Find my miner · Guides + Alerts button
NAV = [("/miners/", "All miners", "Miners"), ("/deals/", "Deals", "Deals"), ("/find-my-miner/", "Find my miner", "Find"), ("/guides/", "Guides", "Guides")]
NAV_SECTIONS = {"/miners/": ("/miners/", "/solo-miners/", "/pool-miners/", "/heater-miners/", "/models/", "/home-miners/"),
                "/deals/": ("/deals/", "/in-stock/", "/price-per-th/", "/bitaxe-black-friday/"), "/find-my-miner/": ("/find-my-miner/",),
                "/guides/": ("/guides/", "/solo-odds/", "/heat-calculator/", "/solo-wins/", "/best/", "/compare/", "/how-we-track/", "/where-to-buy-bitaxe/", "/sellers/")}

# Browse-by-type categories. Any miner can solo or pool mine; these say what each is best suited to. A miner can be in several.
SOLO_SET = ["bitaxe-gamma", "bitaxe-gamma-duo", "bitaxe-gt-801", "nerdaxe-gamma", "nerdaxe-gaia", "nerdqaxe-pp",
            "braiins-bmm-101", "avalon-nano-3s", "hammer-bc04", "bitaxe-supra", "bitaxe-ultra",
            "bitaxe-naja-duo", "bitforge-nano", "heatbit-bitair", "bitaxe-gamma-hex", "nerdoctaxe", "hammer-thor-p2", "hammer-bc08", "futurebit-apollo-iii", "bitcube", "nmqaxe-nexus", "nerdqx"]
POOL_SET = ["avalon-nano-3s", "hammer-bc04", "heatbit-canvas", "heatbit-trio", "avalon-mini-3", "heatbit-maxi", "avalon-q",
            "bitaxe-gamma-hex", "nerdoctaxe", "hammer-thor-p2", "hammer-bc08", "futurebit-apollo-iii", "gekko-kbox-22", "dcentral-stealthminer", "heatbit-bitwater", "nmqaxe-nexus"]
HEAT_SET = ["avalon-nano-3s", "heatbit-canvas", "heatbit-trio", "avalon-mini-3", "heatbit-maxi", "avalon-q", "gekko-kbox-22", "dcentral-stealthminer"]
CATS = [  # key, path, nav/tag label, h1, set, photo for the browse tile
    ("solo", "/solo-miners/", "Solo", "Best for solo mining", SOLO_SET, "bitaxe-gamma"),
    ("pool", "/pool-miners/", "Pool", "Best for pool mining", POOL_SET, "avalon-q"),
    ("heat", "/heater-miners/", "Heaters", "Heater miners", HEAT_SET, "heatbit-maxi"),
]

# ---- brand assets (inline SVG; the radar mark follows the @BitaxeRadar avatar) --------------
LOGO_SVG = ('<svg class="logo-mark" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
            '<circle cx="32" cy="32" r="31" fill="#0f1a2e"/>'
            '<g fill="none" stroke="#5b74a6" stroke-width="3.2"><circle cx="32" cy="32" r="25"/><circle cx="32" cy="32" r="16.5"/><circle cx="32" cy="32" r="8"/></g>'
            '<path d="M32 32 L40.6 8.5 A25 25 0 0 1 53.2 18.8 Z" fill="#f7931a" fill-opacity=".55"/>'
            '<circle cx="45" cy="17.5" r="4" fill="#f7931a"/><circle cx="32" cy="32" r="4" fill="#f7931a"/></svg>')
WORDMARK = f'{LOGO_SVG}<span>Bitaxe <b>Radar</b></span>'
RADAR_BG = ('<svg class="radar-bg" viewBox="0 0 200 200" aria-hidden="true" focusable="false"><g fill="none" stroke="#8fa6d6" stroke-width="1.5">'
            '<circle cx="100" cy="100" r="96"/><circle cx="100" cy="100" r="72"/><circle cx="100" cy="100" r="48"/><circle cx="100" cy="100" r="24"/>'
            '<path d="M100 0v200M0 100h200" stroke-opacity=".5"/></g><path d="M100 100 L132.8 9.8 A96 96 0 0 1 178.6 45 Z" fill="#f7931a" fill-opacity=".8"/></svg>')
CHIPS = {"bitaxe-supra": 1, "bitaxe-ultra": 1, "bitaxe-gamma": 1, "bitaxe-gamma-duo": 2, "bitaxe-gt-801": 2,
         "nerdaxe-gamma": 1, "nerdaxe-gaia": 1, "nerdqaxe-pp": 4, "nerdoctaxe": 4, "nerdqx": 4, "dcentral-stealthminer": 4}
SCREEN = {"nerdaxe-gamma", "nerdaxe-gaia"}


# Product photos: each one is the seller's own product image for that exact model (sources in docs/IMAGE_SOURCES.md),
# background-trimmed and resized to WebP. Models without a reliable photo fall back to the drawn placeholder.
MODEL_IMG = {
    "bitaxe-gamma": (627, 864, "Bitaxe Gamma 602 solo Bitcoin miner"),
    "bitaxe-gamma-duo": (606, 824, "Bitaxe Gamma Duo 650 dual-chip solo Bitcoin miner"),
    "bitaxe-gt-801": (827, 864, "Bitaxe GT 801 (Gamma Turbo) solo Bitcoin miner in its heatsink case"),
    "nerdaxe-gamma": (644, 864, "Nerdaxe Gamma solo Bitcoin miner with color display"),
    "nerdaxe-gaia": (752, 841, "Nerdaxe Gaia BM1373 solo Bitcoin miner"),
    "nerdqaxe-pp": (463, 721, "NerdQaxe++ 4.8 TH/s four-chip solo Bitcoin miner"),
    "bitaxe-supra": (595, 864, "Bitaxe Supra 403 solo Bitcoin miner"),
    "avalon-nano-3s": (800, 377, "Canaan Avalon Nano 3S desk Bitcoin miner"),
    "avalon-mini-3": (800, 560, "Canaan Avalon Mini 3 baseboard heater Bitcoin miner"),
    "avalon-q": (443, 800, "Canaan Avalon Q tower home Bitcoin miner"),
    "heatbit-trio": (333, 800, "Heatbit Trio space heater and Bitcoin miner, silver"),
    "heatbit-maxi": (311, 800, "Heatbit Maxi heater Bitcoin miner, black"),
    "heatbit-canvas": (800, 714, "Heatbit Canvas wall heater Bitcoin miner panels with artwork"),
    "braiins-bmm-101": (800, 500, "Braiins Mini Miner BMM 101 with touchscreen"),
    "hammer-bc04": (565, 800, "Hammer Miner BC04 desk Bitcoin miner on its stand"),
    "bitaxe-gamma-hex": (796, 697, "Bitaxe Gamma Hex 1300 six-chip miner with liquid cooler"),
    "bitaxe-naja-duo": (559, 452, "Bitaxe Naja Duo 1201 dual BM1373 miner with screen"),
    "bitforge-nano": (800, 797, "BitForge Nano enclosed two-chip Bitcoin miner"),
    "heatbit-bitair": (459, 800, "Heatbit Bitair air purifier with built-in Bitcoin miner"),
    "futurebit-apollo-iii": (800, 761, "FutureBit Apollo III cube home Bitcoin miner"),
    "hammer-thor-p2": (800, 706, "Hammer Miner Thor P2 desk Bitcoin miner"),
    "hammer-bc08": (800, 738, "Hammer Miner BC08 desktop Bitcoin miner with touchscreen"),
    "gekko-kbox-22": (800, 457, "GekkoScience KBox 22 all-in-one Bitcoin miner and heater"),
    "heatbit-bitwater": (800, 639, "Heatbit Bitwater water heater element with a built-in Bitcoin miner"),
    "nmqaxe-nexus": (495, 800, "NMMiner NMQAxe++ Nexus desk Bitcoin miner with a color screen and tower cooler"),
    "bitcube": (800, 613, "Power Mining Bitcube cube Bitcoin miner with 777 GH/s on its touchscreen"),
}
MODEL_IMG = {k: v for k, v in MODEL_IMG.items() if (SITE / "img" / "models" / f"{k}.webp").exists()}


def model_img(mid, *, lazy=True):
    if mid not in MODEL_IMG:
        return miner_art(mid)
    w, h, alt = MODEL_IMG[mid]
    attrs = 'loading="lazy" decoding="async"' if lazy else 'fetchpriority="high" decoding="async"'
    return f'<img src="/img/models/{mid}.webp" width="{w}" height="{h}" alt="{esc(alt)}" {attrs}>'


def miner_art(mid):
    """Generic illustration of a small miner board (we have no licensed product photos yet): chip count from the model's chip field."""
    n = CHIPS.get(mid, 1)
    w = 26 if n < 4 else 20
    gap = 8
    total = n * w + (n - 1) * gap
    x0 = 60 - total / 2 + (10 if mid in SCREEN else 0)
    chips = "".join(
        f'<rect x="{x0 + i * (w + gap):.1f}" y="{40 - w / 2:.1f}" width="{w}" height="{w}" rx="3" fill="#0c1324" stroke="#f7931a" stroke-width="1.6"/>'
        f'<g stroke="#f7931a" stroke-opacity=".55" stroke-width="1.2">' + "".join(
            f'<path d="M{x0 + i * (w + gap) + 5 + k * (w - 10) / 3:.1f} {40 - w / 2 + 5:.1f}v{w - 10}"/>' for k in range(4)) + "</g>"
        for i in range(n))
    screen = ('<rect x="14" y="27" width="22" height="26" rx="2" fill="#0c1324" stroke="#5b74a6" stroke-width="1.4"/>'
              '<path d="M18 34h14M18 39h10M18 44h12" stroke="#34d399" stroke-width="1.6" stroke-linecap="round"/>') if mid in SCREEN else ""
    return ('<svg viewBox="0 0 120 80" aria-hidden="true" focusable="false">'
            '<rect x="4" y="10" width="112" height="60" rx="8" fill="#16223d" stroke="#2f4270" stroke-width="1.5"/>'
            '<circle cx="12" cy="18" r="2" fill="#2f4270"/><circle cx="108" cy="18" r="2" fill="#2f4270"/><circle cx="12" cy="62" r="2" fill="#2f4270"/><circle cx="108" cy="62" r="2" fill="#2f4270"/>'
            '<rect x="100" y="56" width="10" height="7" rx="1.5" fill="#24365e"/><circle cx="104" cy="25" r="1.8" fill="#34d399"/>'
            + screen + chips + "</svg>")


# ---------------------------------------------------------------------------------------------
# derived numbers
# ---------------------------------------------------------------------------------------------
def in_stock(o):
    return o["stock_status"] == "in_stock"


def usd(o):
    return o.get("price_usd_approx")


def offers_for(mid):
    return [o for o in OFFERS if o["model"] == mid]


def cheapest(offers):
    offers = [o for o in offers if usd(o) is not None]
    return min(offers, key=usd) if offers else None


def jth(mid):
    m = MODELS[mid]
    return m["watts"] / m["hashrate_ths"]


def kwh_year(mid):
    return MODELS[mid]["watts"] * 24 * 365 / 1000


def lottery_years(mid):
    share = MODELS[mid]["hashrate_ths"] / (NETWORK_EH_ILLUSTRATION * 1e6)
    return 1 / (share * BLOCKS_PER_YEAR)


def stats(mid):
    offs = offers_for(mid)
    ins = [o for o in offs if in_stock(o)]
    ins_usd = [o for o in ins if o["currency"] == "USD"]
    best = cheapest(ins)
    return dict(
        offers=offs, in_stock=ins, best=best, best_usd=cheapest(ins_usd),
        low_any=cheapest(offs), high_any=max([o for o in offs if usd(o) is not None], key=usd, default=None),
        sellers=len({o["seller"] for o in offs}), checked=max((o["checked_at"] for o in offs), default=latest["generated_at"]),
        per_th=(usd(best) / MODELS[mid]["hashrate_ths"]) if best else None)


def cat(mid):
    return MODELS[mid].get("category", "bitaxe")


def is_home(mid):
    return cat(mid) == "home"


STATS = {mid: stats(mid) for mid in MODELS}
TRACKED = [mid for mid in MODELS if STATS[mid]["offers"]]
BITAXE_TRACKED = [m for m in TRACKED if not is_home(m)]     # Bitaxe-family + open-source boards ("board"), ranked together
CORE_TRACKED = [m for m in TRACKED if cat(m) == "bitaxe"]   # the original Bitaxe set used by the Bitaxe-only pages
HOME_TRACKED = [m for m in TRACKED if is_home(m)]
LIVE_TRACKED = [m for m in TRACKED if m not in NOINDEX_MODELS]
BITAXE_OFFERS = [o for o in OFFERS if cat(o["model"]) == "bitaxe"]
EFF_RANK, PTH_RANK, RANK_N, PTH_N = {}, {}, {}, {}
for _grp in (BITAXE_TRACKED, HOME_TRACKED):       # ranks are within a category (a Bitaxe is not compared with a heater)
    for i, mid in enumerate(sorted(_grp, key=jth)):
        EFF_RANK[mid], RANK_N[mid] = i + 1, len(_grp)
    _pth = sorted([m for m in _grp if STATS[m]["per_th"] is not None], key=lambda m: STATS[m]["per_th"])
    for i, mid in enumerate(_pth):
        PTH_RANK[mid], PTH_N[mid] = i + 1, len(_pth)


def btu(watts):
    return watts * 3.412


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def hist_pts(oid):
    return history.get(oid, [])


def hist_summary(o):
    pts = hist_pts(o["id"])
    if not pts:
        return None
    prices = [p["price"] for p in pts]
    return dict(n=len(pts), first=pts[0]["t"], lo=min(prices), hi=max(prices), n_in=sum(1 for p in pts if p.get("in_stock")), cur=o["currency"])


def price_changes(days=7):
    """(offer, old_price, new_price, t) for consecutive logged points whose price differs, within the last N days."""
    out = []
    byid = {o["id"]: o for o in OFFERS}
    for oid, pts in history.items():
        o = byid.get(oid)
        if not o:
            continue
        for a, b in zip(pts, pts[1:]):
            if a["price"] != b["price"] and GEN - parse_t(b["t"]) <= timedelta(days=days):
                out.append((o, a["price"], b["price"], b["t"]))
    return sorted(out, key=lambda x: x[3], reverse=True)


# ---------------------------------------------------------------------------------------------
# page layout
# ---------------------------------------------------------------------------------------------
PAGES = []   # dicts: path, lastmod (indexable pages only, for sitemap.xml)


def breadcrumb_ld(trail):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": BASE + p} for i, (n, p) in enumerate(trail)]}


def crumbs_html(trail):
    parts = [f'<a href="{esc(p)}">{esc(n)}</a>' for n, p in trail[:-1]] + [f'<span aria-current="page">{esc(trail[-1][0])}</span>']
    return '<nav class="crumbs" aria-label="Breadcrumb">' + " › ".join(parts) + "</nav>"


FOOT_DISCLOSURE = ('<strong>Affiliate disclosure:</strong> some shop links are affiliate links (labelled "affiliate link"). '
                   "If you buy through one we may earn a commission at no extra cost to you. It never changes how prices are ranked.")


def header_html(path=""):
    def cur(p):
        return ' aria-current="page"' if any(path.startswith(x) for x in NAV_SECTIONS[p]) else ""
    nav = "".join(f'<a href="{p}"{cur(p)}>' + (f'<span class="hide-sm">{esc(n)}</span><span class="show-sm">{esc(sm)}</span>' if sm != n else esc(n)) + "</a>"
                  for p, n, sm in NAV) + ('<a class="nav-cta" href="/alerts/"' + (' aria-current="page"' if path == "/alerts/" else "")
                                         + '><span class="hide-sm">Price alerts</span><span class="show-sm">Alerts</span></a>')
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
  <a class="brand" href="/" aria-label="Bitaxe Radar home">{WORDMARK}</a>
  <nav aria-label="Main">{nav}</nav>
</div></header>"""


FOOT_GROUPS = [
    ("Miners", [("/miners/", "All miners"), ("/solo-miners/", "Solo miners"), ("/pool-miners/", "Pool miners"), ("/heater-miners/", "Heater miners"),
                ("/solo-odds/", "Solo odds"), ("/solo-wins/", "Solo wins"), ("/heat-calculator/", "Room heat calculator"), ("/deals/", "Deals"), ("/price-per-th/", "Price per TH/s"), ("/in-stock/", "In stock now"), ("/find-my-miner/", "Find my miner")]),
    ("Help", [("/guides/", "Guides"), ("/best/", "Best for…"), ("/compare/", "Compare"), ("/sellers/", "Shops"),
              ("/where-to-buy-bitaxe/", "Where to buy"), ("/alerts/", "Price alerts"), ("/newsletter/", "Newsletter")]),
    ("About", [("/how-we-track/", "About & how we track"), ("/advertise/", "Advertise"), ("/bitaxe-black-friday/", "Black Friday 2026"), (f"mailto:{CONTACT}", CONTACT)]),
]


def footer_html(extra=""):
    cols = "".join(f'<div><b>{esc(h)}</b>' + "".join(f'<a href="{p}">{esc(n)}</a>' for p, n in links) + "</div>" for h, links in FOOT_GROUPS)
    return f"""<footer class="foot"><div class="wrap">
  <a class="brand" href="/">{WORDMARK}</a>
  <p>Prices and stock for home Bitcoin miners, from Bitaxe boards to room heaters, at US, Canadian and EU shops. Checked every 6 hours.</p>
  <nav class="foot-cols" aria-label="Footer">{cols}</nav>
  {extra}<p>{FOOT_DISCLOSURE}</p>
  <p>Solo mining is a lottery, not income. Prices can change fast, so check the shop's page before buying. Not financial advice.</p>
  <small>Bitaxe Radar is independent and not affiliated with the Bitaxe project, Open Source Miners United or any shop listed.</small>
</div></footer>"""


def layout(path, title, desc, body, *, crumbs=None, jsonld=(), noindex=False, lastmod=None, scripts="", og_type="website", index_in_sitemap=True):
    url = BASE + (path if path != "/404.html" else "/")
    desc = shorten(desc, 158)
    title = shorten(title, 90)
    ld = list(jsonld)
    if crumbs:
        ld.append(breadcrumb_ld(crumbs))
    robots = '<meta name="robots" content="noindex,follow">\n' if noindex else ""
    canon = f'<link rel="canonical" href="{esc(url)}">\n' if path != "/404.html" else ""
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b1222">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}{canon}<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta property="og:site_name" content="Bitaxe Radar">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{BASE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/style.css">
{"".join(jsonld_tag(x) for x in ld)}
</head>
<body>
{header_html(path)}
<main class="wrap" id="main">
{crumbs_html(crumbs) if crumbs else ""}
{body}
</main>
{footer_html()}
{scripts}{calc_scripts() if "data-calc=" in body else ""}{ANALYTICS}
</body>
</html>
"""
    out = SITE / "404.html" if path == "/404.html" else SITE / path.strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    if index_in_sitemap and not noindex:
        PAGES.append(dict(path=path, lastmod=lastmod or latest["generated_at"]))


CFG_CLEAN = [(r"\s*per product title", ""), (r"power supply not mentioned in title \(unverified\)", "power supply not mentioned, check the listing"),
             (r"\s*\(listed 'inkl\. MwSt\.'\)", ""), (r"EUR, tax basis not stated; ", ""), (r"page lists power supply \+ stand in the box", "power supply + stand included"),
             (r"^Base price incl", "Incl")]


def cfg_text(o):
    """Shopper-facing version of the collector's config note (drops our internal sourcing remarks)."""
    t = o["config"]
    for a, b in CFG_CLEAN:
        t = re.sub(a, b, t)
    return t + (f" · {o['ship_note']}" if o.get("ship_note") else "")


def offers_table(offers, *, show_model=False, best_id=None):
    rows = []
    for o in offers:
        cur = money(o["price"], o["currency"])
        approx = f'<div class="cfg">≈ {money(usd(o))}</div>' if o["currency"] != "USD" and usd(o) is not None else ""
        cmp_at = f'<div class="cfg">seller-listed was {money(o["compare_at"], o["currency"])}</div>' if o.get("compare_at") and o["compare_at"] > o["price"] else ""
        cfg = esc(cfg_text(o))
        is_best = best_id and o["id"] == best_id
        best = ' class="best"' if is_best else ""
        tagb = '<span class="tag-best">Cheapest</span>' if is_best else ""
        stale = '<div class="stale">may be out of date</div>' if o.get("stale") else ""
        first = (f'<td class="model-cell"><a href="/models/{o["model"]}/">{esc(SHORT[o["model"]])}</a></td>' if show_model else "")
        rows.append(f'<tr{best}>{first}<td class="seller-cell"><a href="/sellers/{esc(o["seller"])}/">{esc(sname(o["seller"]))}</a>{tagb}{stale}</td>'
                    f'<td class="num price-cell">{cur}{approx}{cmp_at}</td><td class="status-cell">{badge(o["stock_status"])}</td><td class="cfg">{cfg}</td>'
                    f'<td class="cfg checked-cell">{tag_time(o["checked_at"])}</td><td class="buy-cell">{offer_link(o, cls="btn" if is_best else "btn ghost")}</td></tr>')
    head = ("<th>Model</th>" if show_model else "") + '<th>Shop</th><th class="num">Price</th><th>Stock</th><th>Details</th><th>Checked</th><th><span class="sr">Buy</span></th>'
    return f'<div class="tablewrap"><table class="offers"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def sort_offers(offers):
    return sorted(offers, key=lambda o: (not in_stock(o), usd(o) if usd(o) is not None else 1e9))


# ---- static SVG price-history chart --------------------------------------------------------
COLORS = ["#f7931a", "#6ea8fe", "#3ecf8e", "#d58cff", "#f5c04a", "#ef6b6b"]


def to_usd(p):
    if p["currency"] == "USD":
        return p["price"]
    rate = FX.get(f'{p["currency"]}_USD')
    return p["price"] * rate if rate else None


def chart_svg(mid):
    series = []
    for i, o in enumerate(sort_offers(offers_for(mid))):
        pts = [(parse_t(p["t"]), to_usd(p), p) for p in hist_pts(o["id"])]
        pts = [x for x in pts if x[1] is not None]
        if pts:
            series.append((o, COLORS[i % len(COLORS)], pts))
    if not series or max(len(s[2]) for s in series) < 2:
        return ""
    W, Hh, ml, mr, mt, mb = 640, 320, 58, 14, 14, 34
    allp = [p for s in series for p in s[2]]
    tmin, tmax = min(p[0] for p in allp), max(p[0] for p in allp)
    vmin, vmax = min(p[1] for p in allp), max(p[1] for p in allp)
    pad = max((vmax - vmin) * 0.15, vmax * 0.05)
    vmin, vmax = max(0, vmin - pad), vmax + pad
    span = (tmax - tmin).total_seconds() or 1

    def X(t):
        return ml + (t - tmin).total_seconds() / span * (W - ml - mr)

    def Y(v):
        return Hh - mb - (v - vmin) / (vmax - vmin) * (Hh - mt - mb)
    g = []
    for i in range(5):
        v = vmin + (vmax - vmin) * i / 4
        g.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#24324f"/><text x="{ml - 8}" y="{Y(v) + 5:.1f}" text-anchor="end" fill="#97a3bb" font-size="15">${v:.0f}</text>')
    g.append(f'<text x="{ml}" y="{Hh - 8}" fill="#97a3bb" font-size="15">{fmt_day(tmin)}</text><text x="{W - mr}" y="{Hh - 8}" text-anchor="end" fill="#97a3bb" font-size="15">{fmt_day(tmax)}</text>')
    legend = []
    for o, col, pts in series:
        if len(pts) > 1:
            g.append(f'<polyline fill="none" stroke="{col}" stroke-width="3" stroke-linejoin="round" points="{" ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v, _ in pts)}"/>')
        for t, v, p in pts:
            fill = col if p.get("in_stock") else "#131d35"
            g.append(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="5" fill="{fill}" stroke="{col}" stroke-width="2.5"><title>{esc(sname(o["seller"]))}: {esc(money(p["price"], p["currency"]))} ({esc(STATUS.get(p["status"], p["status"]))}) {esc(fmt_time(p["t"]))}</title></circle>')
        legend.append(f'<span><i style="background:{col}"></i>{esc(sname(o["seller"]))}</span>')
    legend.append("<span>● in stock · ○ not in stock</span>")
    return (f'<div class="chart"><svg viewBox="0 0 {W} {Hh}" role="img" aria-label="Price history for {esc(SHORT[mid])} in USD (EUR sellers converted at the latest rate)">{"".join(g)}</svg></div>'
            f'<div class="legend">{"".join(legend)}</div>')


def history_log_table(mid):
    rows = []
    for o in sort_offers(offers_for(mid)):
        s = hist_summary(o)
        if not s:
            continue
        rng = money(s["lo"], s["cur"]) if s["lo"] == s["hi"] else f'{money(s["lo"], s["cur"])} – {money(s["hi"], s["cur"])}'
        rows.append(f'<tr><td>{esc(sname(o["seller"]))}</td><td>{esc(fmt_day(s["first"]))}</td><td class="num">{s["n"]}</td><td class="num">{rng}</td><td class="num">{s["n_in"]} of {s["n"]}</td></tr>')
    if not rows:
        return ""
    return ('<div class="tablewrap"><table><thead><tr><th>Seller</th><th>Tracking since</th><th class="num">Data points logged</th><th class="num">Price range logged</th><th class="num">In stock at</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


HIST_NOTE = '<p class="hint">Euro prices are shown in dollars at the latest exchange rate.</p>'


# ---- signup form ---------------------------------------------------------------------------
def signup_html(default_model="any"):
    if not SIGNUP_ENABLED:
        return ""
    opts = '<option value="any">Any miner</option>' + "".join(
        f'<option value="{esc(m)}"{" selected" if m == default_model else ""}>{esc(MODELS[m]["name"])}</option>' for m in TRACKED)
    return f"""<section id="alerts" aria-labelledby="h-alerts">
<h2 id="h-alerts">Get an email when the price drops</h2>
<p class="lede">Pick a miner and your price. We email you once it's in stock at or under it.</p>
<form id="signup" class="signup" novalidate>
  <div class="row">
    <label>Email <input type="email" id="email" name="email" autocomplete="email" placeholder="you@example.com" maxlength="254" required></label>
    <label>Miner <select id="alertModel" name="model">{opts}</select></label>
    <label>My price (USD) <input type="number" min="1" max="100000" step="1" id="alertPrice" name="target_price" placeholder="e.g. 120" inputmode="numeric" required></label>
  </div>
  <div style="position:absolute;left:-9999px" aria-hidden="true"><label>Website <input type="text" id="website" name="website" tabindex="-1" autocomplete="off"></label></div>
  <div class="row signup-actions"><div id="turnstile" class="turnstile-slot"></div><button type="submit" id="signupBtn">Email me when it drops</button></div>
  <p class="hint">Free. You'll get one email to confirm first. No spam, never sold, unsubscribe in one click.</p>
  <p class="hint" id="signupMsg" role="status" aria-live="polite"></p>
  <noscript><p class="hint">The sign-up form needs JavaScript for its bot check.</p></noscript>
</form>
</section>"""


SIGNUP_SCRIPTS = (f'<script>window.RADAR_SIGNUP={json.dumps({"workerUrl": WORKER_URL, "sitekey": TURNSTILE_SITEKEY})};</script>\n<script src="/signup.js" defer></script>'
                  if SIGNUP_ENABLED else "")


# ---------------------------------------------------------------------------------------------
# MODEL PAGES
# ---------------------------------------------------------------------------------------------
def related_compare(mid):
    return [(a, b) for a, b in COMPARE_PAIRS if mid in (a, b)]


def compare_url(a, b):
    return f"/compare/{a}-vs-{b}/"


def compare_label(a, b):
    return f"{SHORT[a]} vs {SHORT[b]}"


def build_model_page(mid):
    m, st, cp = MODELS[mid], STATS[mid], MODEL_COPY[mid]
    short = SHORT[mid]
    home = is_home(mid)
    path = f"/models/{mid}/"
    best, low = st["best"], st["low_any"]
    n_in = len(st["in_stock"])
    day = fmt_day(GEN)
    trail = model_trail(mid, short, path)
    pre = [o for o in st["offers"] if o["stock_status"] in ("preorder", "backorder")]

    if not best and pre and low and low["stock_status"] in ("preorder", "backorder"):
        head = (f'<strong>Not in stock right now; {esc(STATUS[low["stock_status"]].lower())} only.</strong> Lowest listed: {money(usd(low))} at {esc(sname(low["seller"]))}.'
                + (f' {esc(low["ship_note"])}.' if low.get("ship_note") else "") + " Set an alert below and we'll tell you when it's in stock.")
        title = f"{short} price: {money(usd(low))} {STATUS[low['stock_status']].lower()} ({day}) | Bitaxe Radar"
        desc = (f"{short} at {plural(st['sellers'], 'seller')}: {STATUS[low['stock_status']].lower()} from {money(usd(low))} at {sname(low['seller'])}, not in stock yet. "
                f"Specs, heat output, running cost and stock alerts. Updated {day}.")
    elif best:
        head = (f'In stock at {n_in} of {plural(st["sellers"], "shop")}. Cheapest right now: <strong>{money(usd(best))}</strong> at {esc(sname(best["seller"]))}.')
        title = f"{short} price: {money(usd(best))} in stock ({day}) | Bitaxe Radar"
        desc = (f"{short} prices at {plural(st['sellers'], 'seller')}: cheapest in stock {money(usd(best))} at {sname(best['seller'])}, "
                f"listed {money(usd(low))}–{money(usd(st['high_any']))}. Stock, price log, running cost. Updated {day}.")
    else:
        head = (f'<strong>Sold out everywhere we check right now.</strong> Lowest listed price: {money(usd(low))} at {esc(sname(low["seller"]))} ({esc(STATUS[low["stock_status"]].lower())}). Set an alert below and we\'ll tell you when it\'s back.')
        title = f"{short} price: sold out or pre-order only ({day}) | Bitaxe Radar"
        desc = (f"{short} at {plural(st['sellers'], 'seller')}: none has it in stock at the last check ({day}). "
                f"Lowest listed {money(usd(low))} at {sname(low['seller'])}. Stock status, price log and price alerts.")

    if len(desc) > 158:      # long names: drop the trailing sentence rather than truncate mid-word
        desc = desc.rsplit(". ", 1)[0] + "."
    avail_note = ""
    if best and low and low["id"] != best["id"] and not in_stock(low):
        avail_note = (f'<p class="avail">Listed cheaper at {esc(sname(low["seller"]))} ({money(usd(low))}), but it\'s {esc(STATUS[low["stock_status"]].lower())}.</p>')

    offers_html = offers_table(sort_offers(st["offers"]), best_id=best["id"] if best else None)

    per_th = st["per_th"]
    rows = [("Hashrate", f"≈ {m['hashrate_ths']:g} TH/s (seller-stated)"),
            ("Power", f"≈ {m['watts']:g} W (seller-stated)"),
            ("Efficiency", f"≈ {jth(mid):.1f} J/TH · {ordinal(EFF_RANK[mid])} best of {RANK_N[mid]}" + (" home miners" if home else "")),
            (("Type", m["kind"]) if home else ("Chip", m["chip"])),
            ("Price per TH/s", (f"{money(per_th)} · {ordinal(PTH_RANK[mid])} cheapest of {PTH_N[mid]} · {price_check(mid)[1]}") if per_th else "n/a, none in stock"),
            ("Energy", f"≈ {kwh_year(mid):,.0f} kWh a year if run 24/7")]
    if home:
        hw = m.get("heat_watts", m["watts"])
        rows.insert(2, ("Heat output", f"≈ {btu(hw):,.0f} BTU/h at full power (≈ {hw:,g} W of heat" + (", including non-mining heat)" if "heat_watts" in m else ")")))
    spec_tbl = '<div class="tablewrap"><table><tbody>' + "".join(f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in rows) + "</tbody></table></div>"
    kwh = kwh_year(mid)
    elec_tbl = ('<div class="tablewrap"><table><thead><tr><th>Power price</th>' + "".join(f'<th class="num">${r:.2f}/kWh</th>' for r in ELEC_RATES) + "</tr></thead>"
                f'<tbody><tr><th scope="row">Cost per year, 24/7</th>{"".join(f"<td class=num>${kwh * r:,.0f}</td>" for r in ELEC_RATES)}</tr></tbody></table></div>')
    spec_note = (f'<p class="hint">{esc(m["note"])}. Running cost assumes full power 24/7; heater miners usually cycle with a thermostat, so real use is often lower.</p>' if home else
                 f'<p class="hint">{esc(m["note"])}. Want your own rate? Use the <a href="/#cost">power-cost calculator</a>.</p>')

    yrs = lottery_years(mid)
    rel_c = related_compare(mid)
    rel_links = "".join(f'<li><a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a></li>' for a, b in rel_c)
    others = [x for x in TRACKED if x != mid and x not in NOINDEX_MODELS and cat(x) == cat(mid)][:6]
    other_links = "".join(f'<li><a href="/models/{x}/">{esc(SHORT[x])}' + (f' <span class="hint">from {money(usd(STATS[x]["best"]))}</span>' if STATS[x]["best"] else ' <span class="hint">sold out</span>') + "</a></li>" for x in others)

    chart = chart_svg(mid)
    log = history_log_table(mid)
    firsts = [h["first"] for o in st["offers"] for h in [hist_summary(o)] if h]
    first_day = min(firsts) if firsts else None
    since = f'<p class="hint">Tracking since {esc(fmt_day(first_day))}.</p>' if first_day else ""
    if chart or log:
        hist_html = since + chart + (f'<details class="more"><summary>Price log by shop</summary>{log}{HIST_NOTE}</details>' if log else "")
    else:
        hist_html = "<p>No history yet for this model.</p>"

    faq = []
    if best:
        a1 = (f"At our last check ({fmt_time(st['checked'])}) the cheapest in-stock listing was {money(usd(best))} at {sname(best['seller'])}"
              + (f", from {money(best['price'], best['currency'])}" if best["currency"] != "USD" else "") + ". Prices exclude shipping and tax, and bundles differ, so check the details line.")
    else:
        a1 = f"Nothing is in stock at the shops we check right now. The lowest listed price is {money(usd(low))} at {sname(low['seller'])}, which is {STATUS[low['stock_status']].lower()}."
    faq.append((f"What is the cheapest {short} right now?", a1, False))
    stock_lines = "; ".join(f"{sname(o['seller'])}: {STATUS[o['stock_status']].lower()}" for o in sort_offers(st["offers"]))
    faq.append((f"Is the {short} in stock?", f"At the last check: {stock_lines}. Stock changes fast, so confirm on the shop's page.", False))
    faq.append((f"How much electricity does the {short} use?",
                f"Sellers state about {m['watts']:g} W, roughly {kwh:,.0f} kWh a year if it runs 24/7. At $0.10, $0.15 and $0.25 per kWh that's about ${kwh * 0.10:,.0f}, ${kwh * 0.15:,.0f} and ${kwh * 0.25:,.0f} a year.", False))
    if home:
        hw = m.get("heat_watts", m["watts"])
        faq.append((f"How much heat does the {short} give off?",
                    f"Almost all the electricity a miner uses comes out as heat, like an electric space heater. At full power that's about {hw:,g} W, or roughly {btu(hw):,.0f} BTU per hour"
                    + (f", of which about {m['watts']:g} W comes from mining." if "heat_watts" in m else ".")
                    + ' <a href="/guides/how-heater-miners-work/">How heater miners work</a>.', True))
        faq.append((f"Will the {short} pay for its electricity?",
                    "Usually not all of it, and nothing is guaranteed. Pointed at a mining pool, it earns small, steady amounts of bitcoin that can offset part of the power bill. "
                    "How much depends on Bitcoin's price, the network's total hashrate and your electricity rate, and all three change. Pointed at solo mining, it's a lottery ticket for a whole block. "
                    '<a href="/guides/solo-vs-pool-mining/">Solo vs pool, explained</a>.', True))
    else:
      faq.append((f"Can a {short} make money?",
                f"Almost certainly not. It's a solo \"lottery\" miner: it either finds a whole Bitcoin block (a huge reward) or nothing. As a rough illustration, on a {NETWORK_EH_ILLUSTRATION:,} EH/s network it would find a block about once every {sig2(yrs)} years on average, while electricity costs money every year. Buy it as a hobby, not an investment.", False))
    faq.append((f"How do I get told when the {short} price drops?",
                "Use the alert form on this page: pick your price and we email you once it's in stock at or under it. Free, and you can unsubscribe in one click.", False))
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{a if raw else esc(a)}</p></details>" for q, a, raw in faq)

    check_html = "".join(f"<li>{esc(c)}</li>" for c in cp["check"])
    body = f"""<article>
<header class="hero"><h1>{esc(short)}</h1>
<p class="lede">{head}</p>
<p class="meta">≈{m['hashrate_ths']:g} TH/s · ≈{m['watts']:,g} W{f" mining ({m['heat_watts']:,g} W total heat)" if m.get('heat_watts') else ""} · {esc(m['kind'] if home else m['chip'])} · checked {tag_time(st['checked'])}</p>{cat_tags(mid)}</header>
<div class="model-top"><figure class="model-photo{"" if mid in MODEL_IMG else " placeholder"}">{model_img(mid, lazy=False)}</figure>
<div class="model-deal">{best_cta(st) or preorder_cta(st) or '<div class="cta"><div><small>Sold out right now</small><p class="hint">Set a price alert below and we\'ll email you when it\'s back.</p></div></div>'}
{avail_note}</div></div>
{earn_box(mid)}{solo_win_html(mid) if mid in SOLO_SET else ''}
<section aria-labelledby="h-offers"><h2 id="h-offers">Prices by shop</h2>
{offers_html}
<p class="hint">Before shipping and tax. Euro and Canadian-dollar prices are converted to US dollars as an estimate. Updated every 6 hours.</p></section>
{SPONSOR_SLOT}
<section aria-labelledby="h-hist"><h2 id="h-hist">Price history</h2>{hist_html}</section>
{signup_html(mid)}
<section aria-labelledby="h-about"><h2 id="h-about">Good to know</h2>
<details><summary>About the {esc(short)}</summary><p>{esc(cp['intro'])}</p><p><strong>Best for:</strong> {esc(cp['who'])}</p></details>
<details><summary>Check before you buy</summary><ul>{check_html}</ul></details>
<details><summary>Specs and running cost</summary>{spec_tbl}<br>{elec_tbl}{spec_note}</details>
</section>
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{faq_html}</section>
<section aria-labelledby="h-more"><h2 id="h-more">Keep comparing</h2>
{'<ul class="links">' + rel_links + "</ul>" if rel_links else ""}
<ul class="links">{other_links}</ul>
{'<p><a href="/heater-miners/">Heater miners</a> · <a href="/pool-miners/">Best for pool mining</a> · <a href="/guides/how-heater-miners-work/">How heater miners work</a> · <a href="/guides/solo-vs-pool-mining/">Solo vs pool</a></p>' if home else ""}</section>
</article>"""

    offer_ld = []
    for o in sort_offers(st["offers"]):
        offer_ld.append({"@type": "Offer", "url": o["url"], "price": f'{o["price"]:.2f}', "priceCurrency": o["currency"],
                         "availability": AVAIL.get(o["stock_status"], "https://schema.org/OutOfStock"),
                         "seller": {"@type": "Organization", "name": sname(o["seller"]), "url": SELLERS[o["seller"]]["url"]}})
    product = {"@context": "https://schema.org", "@type": "Product", "name": m["name"],
               "description": shorten(cp["intro"], 300), "url": BASE + path}
    if mid in MODEL_IMG:
        product["image"] = f"{BASE}/img/models/{mid}.webp"
    if best:
        ins_prices = [usd(o) for o in st["in_stock"] if usd(o) is not None]
        product["offers"] = {"@type": "AggregateOffer", "priceCurrency": "USD", "lowPrice": f"{min(ins_prices):.2f}", "highPrice": f"{max(ins_prices):.2f}",
                             "offerCount": len(offer_ld), "offers": offer_ld}
    else:
        product["offers"] = offer_ld
    layout(path, title, desc, body, crumbs=trail, jsonld=[product], noindex=mid in NOINDEX_MODELS, scripts=SIGNUP_SCRIPTS)


# ---------------------------------------------------------------------------------------------
# COMPARE PAGES
# ---------------------------------------------------------------------------------------------
def ratio_text(hi, lo):
    r = hi / lo
    return f"{r:.1f}× the hashrate" if r >= 1.05 else "about the same hashrate"


def build_compare_page(a, b):
    sa, sb = SHORT[a], SHORT[b]
    ma, mb, ta, tb = MODELS[a], MODELS[b], STATS[a], STATS[b]
    cc = COMPARE_COPY[(a, b)]
    path = compare_url(a, b)
    trail = [("Home", "/"), (compare_label(a, b), path)]
    ba, bb = ta["best"], tb["best"]
    lines = []
    if ba and bb:
        pa, pb = usd(ba), usd(bb)
        if pa <= pb:
            lines.append(f"<strong>Price:</strong> the cheapest in-stock {esc(sa)} is {money(pa)} ({esc(sname(ba['seller']))}); the cheapest in-stock {esc(sb)} is {money(pb)} ({esc(sname(bb['seller']))}), {money(pb - pa)} more ({pb / pa:.1f}×).")
        else:
            lines.append(f"<strong>Price:</strong> the cheapest in-stock {esc(sb)} is {money(pb)} ({esc(sname(bb['seller']))}), {money(pa - pb)} less than the cheapest in-stock {esc(sa)} at {money(pa)} ({esc(sname(ba['seller']))}).")
    else:
        for s, t in ((sa, ta), (sb, tb)):
            if not t["best"]:
                lo = t["low_any"]
                lines.append(f"<strong>{esc(s)}:</strong> not in stock at any tracked seller at the last check (lowest listed {money(usd(lo))}, {esc(STATUS[lo['stock_status']].lower())}).")
    hi_m, lo_m = (a, b) if ma["hashrate_ths"] >= mb["hashrate_ths"] else (b, a)
    lines.append(f"<strong>Hashrate:</strong> {esc(SHORT[hi_m])} states ≈{MODELS[hi_m]['hashrate_ths']:g} TH/s versus ≈{MODELS[lo_m]['hashrate_ths']:g} TH/s for {esc(SHORT[lo_m])} ({ratio_text(MODELS[hi_m]['hashrate_ths'], MODELS[lo_m]['hashrate_ths'])} on paper).")
    ea, eb = jth(a), jth(b)
    if abs(ea - eb) / max(ea, eb) > 0.05:
        better = a if ea < eb else b
        lines.append(f"<strong>Efficiency:</strong> {esc(sa)} ≈{ea:.1f} J/TH, {esc(sb)} ≈{eb:.1f} J/TH, so the {esc(SHORT[better])} gets more hashrate per watt (lower is better).")
    else:
        lines.append(f"<strong>Efficiency:</strong> {esc(sa)} ≈{ea:.1f} J/TH, {esc(sb)} ≈{eb:.1f} J/TH: effectively the same (lower is better).")
    if ta["per_th"] and tb["per_th"]:
        cheaper = a if ta["per_th"] < tb["per_th"] else b
        lines.append(f"<strong>Price per TH/s:</strong> {esc(sa)} {money(ta['per_th'])}, {esc(sb)} {money(tb['per_th'])} at their cheapest in-stock prices; the {esc(SHORT[cheaper])} is the better value per stated TH/s.")
    lines.append(f"<strong>Running cost:</strong> about ${kwh_year(a) * 0.15:,.0f} a year for the {esc(sa)} versus ${kwh_year(b) * 0.15:,.0f} for the {esc(sb)} at an assumed $0.15/kWh, running 24/7.")

    def col(mid, t):
        b_ = t["best"]
        return [f'<a href="/models/{mid}/">{esc(SHORT[mid])}</a>', esc(MODELS[mid]["chip"]), f"≈ {MODELS[mid]['hashrate_ths']:g} TH/s", f"≈ {MODELS[mid]['watts']:g} W", f"≈ {jth(mid):.1f} J/TH",
                (money(usd(b_)) + f" ({esc(sname(b_['seller']))})") if b_ else "none in stock",
                money(t["per_th"]) if t["per_th"] else "n/a",
                f"${kwh_year(mid) * 0.15:,.0f}", f"{len(t['in_stock'])} of {t['sellers']}"]
    labels = ["", "Chip", "Stated hashrate", "Stated power", "Efficiency", "Cheapest in stock", "Price per TH/s", "Yearly electricity at $0.15/kWh", "Sellers with stock"]
    ca, cb = col(a, ta), col(b, tb)
    tbl = '<div class="tablewrap"><table class="cmp"><thead><tr><th></th><th>' + ca[0] + "</th><th>" + cb[0] + "</th></tr></thead><tbody>" + "".join(
        f'<tr><th scope="row">{labels[i]}</th><td>{ca[i]}</td><td>{cb[i]}</td></tr>' for i in range(1, len(labels))) + "</tbody></table></div>"

    def best_block(mid, t):
        if not t["best"]:
            return f'<p>No in-stock listing for {esc(SHORT[mid])} at the last check. <a href="/models/{mid}/">See all listings</a>.</p>'
        top = sort_offers(t["offers"])[:3]
        return offers_table(top, best_id=t["best"]["id"]) + f'<p class="hint"><a href="/models/{mid}/">All {len(t["offers"])} listings and history for the {esc(SHORT[mid])}</a></p>'

    olinks = "".join(f'<li><a href="{compare_url(*p)}">{esc(compare_label(*p))}</a></li>' for p in COMPARE_PAIRS if p != (a, b))
    price_bit = f"in stock from {money(usd(ba))} vs {money(usd(bb))}" if ba and bb else "prices, stock and running cost"
    title = f"{sa} vs {sb}: price, hashrate, power cost ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"{sa} vs {sb}: {price_bit}, {ma['hashrate_ths']:g} vs {mb['hashrate_ths']:g} TH/s stated, {ea:.1f} vs {eb:.1f} J/TH, yearly electricity cost. Updated {fmt_day(GEN)}."
    body = f"""<article>
<header class="hero"><h1>{esc(sa)} vs {esc(sb)}</h1>
<p class="lede">{esc(cc['angle'])}</p>
<p class="meta">Prices checked {tag_time(max(ta['checked'], tb['checked']))}</p></header>
<section aria-labelledby="h-v"><h2 id="h-v">The numbers, in plain words</h2><ul>{"".join(f"<li>{x}</li>" for x in lines)}</ul>
<p class="hint">Hashrate and power are seller-stated. More hashrate raises your lottery odds, but they stay tiny either way.</p></section>
<section aria-labelledby="h-t"><h2 id="h-t">Side by side</h2>{tbl}</section>
<section aria-labelledby="h-w"><h2 id="h-w">Which one fits you?</h2>
<p><strong>Pick the {esc(sa)} if</strong> {esc(cc['a_for'])}</p>
<p><strong>Pick the {esc(sb)} if</strong> {esc(cc['b_for'])}</p>
<p class="hint">Neither is an income source: solo mining is a lottery.</p></section>
<section aria-labelledby="h-a"><h2 id="h-a">Where to buy the {esc(sa)}</h2>{best_block(a, ta)}</section>
<section aria-labelledby="h-b"><h2 id="h-b">Where to buy the {esc(sb)}</h2>{best_block(b, tb)}</section>
<section aria-labelledby="h-al"><h2 id="h-al">Price alerts</h2><p>Want a nudge when one of them drops? Use the form on the <a href="/models/{a}/#alerts">{esc(sa)} page</a> or the <a href="/models/{b}/#alerts">{esc(sb)} page</a>.</p></section>
<section><h2>More comparisons</h2><ul class="links">{olinks}</ul></section>
</article>"""
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{sa} vs {sb}", "url": BASE + path,
          "dateModified": latest["generated_at"], "about": [{"@type": "Product", "name": MODELS[a]["name"], "url": BASE + f"/models/{a}/"},
                                                            {"@type": "Product", "name": MODELS[b]["name"], "url": BASE + f"/models/{b}/"}]}
    layout(path, title, desc, body, crumbs=trail, jsonld=[ld])


# ---------------------------------------------------------------------------------------------
# SELLER PAGES
# ---------------------------------------------------------------------------------------------
def build_seller_page(sid):
    s, cp = SELLERS[sid], SELLER_COPY[sid]
    offs = sorted([o for o in OFFERS if o["seller"] == sid], key=lambda o: list(MODELS).index(o["model"]))
    path = f"/sellers/{sid}/"
    n_in = sum(1 for o in offs if in_stock(o))
    aff = aff_param(sid)
    trail = [("Home", "/"), ("Shops", "/sellers/"), (s["name"], path)]
    rows = []
    for o in offs:
        ins = sorted(STATS[o["model"]]["in_stock"], key=usd)
        rank = ""
        if in_stock(o) and len(ins) > 1:
            rank = f"{ordinal([x['id'] for x in ins].index(o['id']) + 1)} cheapest of {len(ins)} in-stock listings"
        elif in_stock(o):
            rank = "only in-stock listing"
        cur = money(o["price"], o["currency"]) + (f' <span class="cfg">≈ {money(usd(o))}</span>' if o["currency"] != "USD" else "")
        rows.append(f'<tr><td><a href="/models/{o["model"]}/">{esc(SHORT[o["model"]])}</a></td><td class="num">{cur}</td><td>{badge(o["stock_status"])}</td><td class="cfg">{esc(rank) or "–"}</td><td class="cfg">{tag_time(o["checked_at"])}</td><td>{offer_link(o, "View ↗")}</td></tr>')
    tbl = ('<div class="tablewrap"><table><thead><tr><th>Model</th><th class="num">Price</th><th>Stock</th><th>Versus other shops</th><th>Checked</th><th><span class="sr">Buy</span></th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table></div>')
    log_rows = []
    for o in offs:
        hs = hist_summary(o)
        if hs:
            rng = money(hs["lo"], hs["cur"]) if hs["lo"] == hs["hi"] else f'{money(hs["lo"], hs["cur"])} – {money(hs["hi"], hs["cur"])}'
            log_rows.append(f'<tr><td>{esc(SHORT[o["model"]])}</td><td>{esc(fmt_day(hs["first"]))}</td><td class="num">{hs["n"]}</td><td class="num">{rng}</td><td class="num">{hs["n_in"]} of {hs["n"]}</td></tr>')
    log = ('<div class="tablewrap"><table><thead><tr><th>Model</th><th>Tracking since</th><th class="num">Data points</th><th class="num">Price range logged</th><th class="num">In stock at</th></tr></thead>'
           f'<tbody>{"".join(log_rows)}</tbody></table></div>') + HIST_NOTE
    cheapest_cnt = sum(1 for o in offs if in_stock(o) and STATS[o["model"]]["best"]["id"] == o["id"])
    summary = (f"We track {plural(len(offs), 'model')} at {esc(s['name'])}; {n_in} {'is' if n_in == 1 else 'are'} in stock right now"
               + (f", and {cheapest_cnt} of {'it' if n_in == 1 else 'those'} {'is' if cheapest_cnt == 1 else 'are'} the cheapest in-stock price we see for {'that model' if cheapest_cnt == 1 else 'those models'}." if cheapest_cnt else "."))
    aff_txt = (f'<p class="hint">Links to {esc(s["name"])} are affiliate links: if you buy after clicking, we may earn a commission at no extra cost to you. It never changes how we rank prices.</p>'
               if aff else "")
    notes = "".join(f"<li>{esc(n)}</li>" for n in cp["notes"])
    src = SELLER_FACTS.get(sid, {}).get("src")
    src_txt = f'<p class="hint">Source: <a href="{esc(src)}" rel="nofollow noopener" target="_blank">{esc(s["name"])} policy page</a>.</p>' if src else ""
    unverified = '<p class="hint">Check the shop\'s own shipping, warranty and return pages before you pay.</p>'
    kind_txt = "heater and home miners" if all(is_home(o["model"]) for o in offs) else ("Bitaxe-family and home miners" if any(is_home(o["model"]) for o in offs) else "Bitaxe-family miners")
    title = f"{s['name']} miner prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"{s['name']}: {len(offs)} {kind_txt} tracked, {n_in} in stock now ({cp['region']}). Prices, stock, price log and buying notes."
    body = f"""<article>
<header class="hero"><h1>{esc(s['name'])}: prices and stock</h1><p class="lede">{esc(cp['about'])}</p>
<p class="meta">{summary}</p></header>
<section aria-labelledby="h-p"><h2 id="h-p">What {esc(s['name'])} has right now</h2>{tbl}
<p class="hint">Store: {store_link(sid)}. Prices are before shipping and tax.</p></section>
<section aria-labelledby="h-f"><h2 id="h-f">Shop facts</h2>{facts_table([sid])}{src_txt}{FACTS_NOTE}</section>
<section aria-labelledby="h-n"><h2 id="h-n">Good to know</h2><ul>{notes}</ul>{unverified}{aff_txt}</section>
<section aria-labelledby="h-l"><h2 id="h-l">Price log</h2><details class="more"><summary>Show price log</summary>{log}</details></section>
<section><h2>See also</h2><ul class="links"><li><a href="/miners/">All home miners</a></li><li><a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a></li><li><a href="/in-stock/">Everything in stock</a></li><li><a href="/deals/">Best deals</a></li></ul></section>
</article>"""
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{s['name']} prices and stock", "url": BASE + path,
          "dateModified": latest["generated_at"], "about": {"@type": "Organization", "name": s["name"], "url": s["url"]}}
    layout(path, title, desc, body, crumbs=trail, jsonld=[ld])


# ---------------------------------------------------------------------------------------------
# HUB PAGES
# ---------------------------------------------------------------------------------------------
def itemlist(name, items):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name,
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": BASE + p, "name": n} for i, (n, p) in enumerate(items)]}


def model_summary_table(models, *, usd_only=False):
    rows = []
    for mid in models:
        st = STATS[mid]
        b = st["best_usd"] if usd_only else st["best"]
        if b:
            price = money(usd(b)) + ("" if b["currency"] == "USD" else ' <span class="cfg">(converted)</span>')
            seller = f'<a href="/sellers/{b["seller"]}/">{esc(sname(b["seller"]))}</a>'
        else:
            price, seller = '<span class="stale">none in stock</span>', "–"
        rows.append(f'<tr><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td><td class="num">{price}</td><td>{seller}</td>'
                    f'<td class="num">{len(st["in_stock"])} of {st["sellers"]}</td><td class="cfg">≈{MODELS[mid]["hashrate_ths"]:g} TH/s · ≈{MODELS[mid]["watts"]:g} W</td></tr>')
    return ('<div class="tablewrap"><table><thead><tr><th>Model</th><th class="num">Cheapest in stock</th><th>Seller</th><th class="num">Sellers with stock</th><th>Stated spec</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


CURRENT_MODELS = [m for m in CORE_TRACKED if m not in NOINDEX_MODELS]
N_MODELS = len([m for m in TRACKED if m not in NOINDEX_MODELS])   # the one model count shown anywhere on the site


def build_where_to_buy():
    path = "/where-to-buy-bitaxe/"
    trail = [("Home", "/"), ("Where to buy a Bitaxe", path)]
    bx_sellers = [sid for sid in SELLERS if any(o["seller"] == sid for o in BITAXE_OFFERS)]
    usd_sellers = [sid for sid in bx_sellers if SELLERS[sid]["currency"] == "USD"]
    eur_sellers = [sid for sid in bx_sellers if SELLERS[sid]["currency"] != "USD"]
    qa = []
    g = STATS["bitaxe-gamma"]
    if g["best_usd"]:
        qa.append(f"Cheapest <strong>Bitaxe Gamma</strong> in stock at a USD-priced seller: <strong>{money(g['best_usd']['price'])}</strong> at {esc(sname(g['best_usd']['seller']))}.")
    gl = g["low_any"]
    if gl and not in_stock(gl):
        qa.append(f"The cheapest listed Gamma, {money(usd(gl))} at {esc(sname(gl['seller']))}, is {esc(STATUS[gl['stock_status']].lower())} at the last check.")
    ins_usd = [o for o in BITAXE_OFFERS if in_stock(o) and o["currency"] == "USD"]
    qa.append(f"Right now {len(ins_usd)} of our {sum(1 for o in BITAXE_OFFERS if o['currency'] == 'USD')} USD-priced listings are in stock, across {len({o['seller'] for o in ins_usd})} sellers.")
    qa_html = "".join(f"<li>{x}</li>" for x in qa)

    def seller_row(sid):
        s, cp = SELLERS[sid], SELLER_COPY[sid]
        offs = [o for o in BITAXE_OFFERS if o["seller"] == sid]
        n_in = sum(1 for o in offs if in_stock(o))
        return (f'<tr><td><a href="/sellers/{sid}/">{esc(s["name"])}</a></td><td>{esc(cp["region"])}</td><td class="num">{len(offs)}</td><td class="num">{n_in}</td>'
                f'<td class="cfg">{tag_time(max(o["checked_at"] for o in offs))}</td></tr>')
    sellers_tbl = ('<div class="tablewrap"><table><thead><tr><th>Shop</th><th>Pricing</th><th class="num">Models</th><th class="num">In stock</th><th>Last checked</th></tr></thead>'
                   f'<tbody>{"".join(seller_row(s) for s in usd_sellers + eur_sellers)}</tbody></table></div>')
    title = f"Where to buy a Bitaxe in the US: prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = (f"Where to buy a Bitaxe or NerdQaxe: {len(bx_sellers)} sellers tracked, {len(ins_usd)} USD-priced listings in stock. "
            f"Cheapest in-stock Gamma {money(g['best_usd']['price']) if g['best_usd'] else 'n/a'}. Updated {fmt_day(GEN)}.")
    body = f"""<article>
<header class="hero"><h1>Where to buy a Bitaxe (US-first)</h1>
<p class="lede">Who has each miner in stock right now, and for how much. US-dollar shops first, European shops below for comparison.</p>
<p class="meta">Data collected {tag_time(latest['generated_at'])}</p></header>
<section aria-labelledby="h-q"><h2 id="h-q">The short answer today</h2><ul>{qa_html}</ul></section>
<section aria-labelledby="h-m"><h2 id="h-m">Cheapest in stock at a USD-priced seller</h2>
{model_summary_table(CURRENT_MODELS, usd_only=True)}
<p class="hint">"None in stock" means no US-dollar shop has it right now; a European shop may, so open the model page. Prices are before shipping and tax.</p></section>
<section aria-labelledby="h-s"><h2 id="h-s">Shops we check</h2>{sellers_tbl}
<p class="hint">Euro prices are converted to dollars as an estimate; shipping, VAT and import duties will change the real US cost.</p></section>
<section aria-labelledby="h-c"><h2 id="h-c">Before you buy: a checklist</h2><ul>
<li><strong>What is in the box.</strong> Power supply, stand and fan are included by some sellers and sold separately by others. A cheap listing without a power supply is not cheaper.</li>
<li><strong>Which revision.</strong> Gamma 601 vs 602, NerdQaxe++ 4.8 TH/s vs Rev 6.1 vs Rev 7: they are different products at different prices.</li>
<li><strong>Pre-order or in stock.</strong> Pre-order and backorder items can take weeks. We label these separately.</li>
<li><strong>Total cost.</strong> Add shipping, sales tax or import duty, and the electricity to run it.</li>
<li><strong>Payment safety.</strong> Be wary of a price far below every other shop, or a shop that only takes wire or crypto.</li>
<li><strong>Look-alikes.</strong> Prefer sellers that name the exact board and revision in the title.</li></ul></section>
<section><h2>Browse by miner</h2><ul>{"".join(f'<li><a href="/models/{m}/">{esc(SHORT[m])}</a></li>' for m in CURRENT_MODELS)}</ul>
<p><a href="/in-stock/">Everything in stock now</a> · <a href="/deals/">Best deals</a> · <a href="/how-we-track/">How we track</a></p></section>
</article>"""
    items = [(SHORT[m], f"/models/{m}/") for m in home_picks()]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Bitaxe-class miners tracked by Bitaxe Radar", items)])


def deal_pills(current):
    return ('<nav class="browse" aria-label="Deals filter">' + "".join(f'<a href="{p}"' + (' aria-current="page"' if p == current else "") + f'>{l}</a>'
            for p, l in (("/deals/", "All deals"), ("/price-per-th/", "Price per TH/s"), ("/in-stock/", "In stock only"), (BF_PATH, "Black Friday 2026"))) + "</nav>")


def build_in_stock():
    path = "/in-stock/"
    trail = [("Home", "/"), ("Deals", "/deals/"), ("In stock now", path)]
    order = {m: i for i, m in enumerate(MODELS)}

    def srt(lst):
        return sorted(lst, key=lambda o: (order[o["model"]], usd(o) if usd(o) is not None else 1e9))
    ins = srt([o for o in OFFERS if in_stock(o)])
    pre = srt([o for o in OFFERS if o["stock_status"] in ("preorder", "backorder")])
    oos = srt([o for o in OFFERS if o["stock_status"] in ("out_of_stock", "unknown")])
    none = [m for m in LIVE_TRACKED if not STATS[m]["in_stock"]]
    notes = []
    for mid in LIVE_TRACKED:
        st = STATS[mid]
        if st["best"] and st["low_any"]["id"] != st["best"]["id"] and not in_stock(st["low_any"]):
            notes.append(f"The cheapest listed {esc(SHORT[mid])}, {money(usd(st['low_any']))} at {esc(sname(st['low_any']['seller']))}, is {esc(STATUS[st['low_any']['stock_status']].lower())}. Cheapest in stock: {money(usd(st['best']))} at {esc(sname(st['best']['seller']))}.")
    if none:
        notes.append("Sold out everywhere we check: " + ", ".join(f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' for m in none) + ".")
    n_sellers = len({o["seller"] for o in ins})
    title = f"Home Bitcoin miners in stock now: {len(ins)} listings at {plural(n_sellers, 'seller')} ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"What is in stock right now: {len(ins)} of {len(OFFERS)} tracked home miner listings (Bitaxe to heaters), plus {len(pre)} pre-order or backorder. Updated {fmt_day(GEN)}."
    body = f"""<article>
<header class="hero"><h1>Home miners in stock now</h1>
{deal_pills("/in-stock/")}
{bf_banner()}
<p class="lede">{len(ins)} of {len(OFFERS)} tracked listings are in stock at the last check. Another {len(pre)} are pre-order or backorder (not in stock yet) and {len(oos)} are sold out.</p>
<p class="meta">Checked {tag_time(latest['generated_at'])} · updated every 6 hours</p></header>
<section aria-labelledby="h-n"><h2 id="h-n">What the stock picture means today</h2><ul>{"".join(f"<li>{x}</li>" for x in notes) or "<li>Nothing unusual at the last check.</li>"}</ul></section>
<section aria-labelledby="h-i"><h2 id="h-i">In stock ({len(ins)})</h2>{offers_table(ins, show_model=True) if ins else "<p>Nothing is in stock at the tracked sellers at the last check.</p>"}</section>
<section aria-labelledby="h-p"><h2 id="h-p">Pre-order and backorder ({len(pre)})</h2><p class="hint">Not in stock. Read the seller's shipping note before ordering.</p>{offers_table(pre, show_model=True) if pre else "<p>None right now.</p>"}</section>
<section aria-labelledby="h-o"><h2 id="h-o">Sold out ({len(oos)})</h2>{offers_table(oos, show_model=True) if oos else "<p>None right now.</p>"}</section>
<section><h2>Related</h2><p><a href="/miners/">All miners</a> · <a href="/deals/">Best deals</a> · <a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a> · <a href="/how-we-track/">How we track</a></p></section>
</article>"""
    items = [(f"{SHORT[o['model']]} at {sname(o['seller'])}", f"/models/{o['model']}/") for o in ins]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Home Bitcoin miners in stock now", items)])


def build_deals():
    path = "/deals/"
    trail = [("Home", "/"), ("Deals", path)]
    cand = [m for m in LIVE_TRACKED if STATS[m]["best"]]
    ranked = sorted(cand, key=lambda m: STATS[m]["per_th"])
    rows = []
    for i, mid in enumerate(ranked, 1):
        st, b = STATS[mid], STATS[mid]["best"]
        rows.append(f'<tr><td class="num">{i}</td><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td><td class="num">{money(usd(b))}</td><td>{esc(sname(b["seller"]))}</td>'
                    f'<td class="num">{money(st["per_th"])}</td><td class="num">≈{jth(mid):.1f}</td><td>{offer_link(b, "View ↗")}</td></tr>')
    rank_tbl = ('<div class="tablewrap"><table><thead><tr><th class="num">#</th><th>Model</th><th class="num">Cheapest in stock</th><th>Seller</th><th class="num">$ per stated TH/s</th><th class="num">J/TH</th><th>Buy</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>')
    disc = [o for o in OFFERS if o.get("compare_at") and o["compare_at"] > o["price"]]
    disc_rows = "".join(f'<tr><td><a href="/models/{o["model"]}/">{esc(SHORT[o["model"]])}</a></td><td>{esc(sname(o["seller"]))}</td><td class="num">{money(o["price"], o["currency"])}</td>'
                        f'<td class="num">{money(o["compare_at"], o["currency"])}</td><td class="num">{(1 - o["price"] / o["compare_at"]) * 100:.0f}%</td><td>{badge(o["stock_status"])}</td></tr>' for o in disc)
    disc_html = (('<div class="tablewrap"><table><thead><tr><th>Model</th><th>Seller</th><th class="num">Price now</th><th class="num">Seller\'s compare-at price</th><th class="num">Difference</th><th>Stock</th></tr></thead>'
                  f'<tbody>{disc_rows}</tbody></table></div><p class="hint">The compare-at price is whatever the seller entered as the "was" price. We have not verified it was ever the selling price, so treat it as the seller\'s claim.</p>')
                 if disc else "<p>No tracked seller shows a compare-at (&ldquo;was&rdquo;) price at the last check.</p>")
    ch = price_changes(7)
    ch_rows = "".join(f'<tr><td><a href="/models/{o["model"]}/">{esc(SHORT[o["model"]])}</a></td><td>{esc(sname(o["seller"]))}</td><td class="num">{money(old, o["currency"])}</td><td class="num">{money(new, o["currency"])}</td>'
                      f'<td class="num">{(new / old - 1) * 100:+.1f}%</td><td>{esc(fmt_day(t))}</td></tr>' for o, old, new, t in ch)
    ch_html = (f'<div class="tablewrap"><table><thead><tr><th>Model</th><th>Seller</th><th class="num">Was</th><th class="num">Now</th><th class="num">Change</th><th>When</th></tr></thead><tbody>{ch_rows}</tbody></table></div>'
               if ch else "<p>No price changes in the last 7 days.</p>")
    gaps = [(mid, STATS[mid]) for mid in LIVE_TRACKED if STATS[mid]["best"] and STATS[mid]["low_any"]["id"] != STATS[mid]["best"]["id"] and not in_stock(STATS[mid]["low_any"])]
    gap_rows = "".join(f'<tr><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td><td>{esc(sname(st["low_any"]["seller"]))}</td><td class="num">{money(usd(st["low_any"]))}</td><td>{badge(st["low_any"]["stock_status"])}</td>'
                       f'<td class="num">{money(usd(st["best"]))}</td><td class="num">{money(usd(st["best"]) - usd(st["low_any"]))}</td></tr>' for mid, st in gaps)
    gap_html = (('<div class="tablewrap"><table><thead><tr><th>Model</th><th>Cheapest listing</th><th class="num">Price</th><th>Status</th><th class="num">Cheapest in stock</th><th class="num">Premium</th></tr></thead>'
                 f"<tbody>{gap_rows}</tbody></table></div>") if gaps else "<p>At the last check the cheapest listing for every model was also in stock.</p>")
    spread = []
    for mid in LIVE_TRACKED:
        ins = sorted(STATS[mid]["in_stock"], key=usd)
        if len(ins) >= 2:
            spread.append((mid, ins[0], ins[-1]))
    spread_rows = "".join(f'<tr><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td><td class="num">{money(usd(lo))}</td><td>{esc(sname(lo["seller"]))}</td><td class="num">{money(usd(hi))}</td><td>{esc(sname(hi["seller"]))}</td>'
                          f'<td class="num">{money(usd(hi) - usd(lo))}</td></tr>' for mid, lo, hi in spread)
    spread_html = (('<div class="tablewrap"><table><thead><tr><th>Model</th><th class="num">Lowest</th><th>Seller</th><th class="num">Highest</th><th>Seller</th><th class="num">Spread</th></tr></thead>'
                    f'<tbody>{spread_rows}</tbody></table></div><p class="hint">Configurations differ (power supply, stand, region), so part of any spread is the bundle, not the seller.</p>')
                   if spread else "<p>No model has two or more in-stock sellers at the last check.</p>")
    top = ranked[0] if ranked else None
    title = (f"Best home miner deals today: {SHORT[top]} cheapest per TH/s ({fmt_day(GEN)}) | Bitaxe Radar" if top else f"Best home miner deals today ({fmt_day(GEN)}) | Bitaxe Radar")
    desc = f"Best home Bitcoin miner deals: cheapest in-stock price per model ranked by cost per TH/s, plus discounts and price drops. Updated {fmt_day(GEN)}."
    body = f"""<article>
<header class="hero"><h1>Best deals right now</h1>
{deal_pills("/deals/")}
{bf_banner()}
<p class="lede">The cheapest in-stock price for each miner, ranked by how much hashrate you get per dollar.</p>
<p class="meta">Data collected {tag_time(latest['generated_at'])}</p></header>
<section aria-labelledby="h-r"><h2 id="h-r">Cheapest in stock, ranked by price per TH/s</h2>{rank_tbl}
<p class="hint">Uses seller-stated hashrate and ignores power cost, shipping and bundle differences.</p></section>
<section aria-labelledby="h-d"><h2 id="h-d">Seller-listed discounts</h2>{disc_html}</section>
<section aria-labelledby="h-c"><h2 id="h-c">Price changes in the last 7 days</h2>{ch_html}</section>
<section aria-labelledby="h-g"><h2 id="h-g">Cheaper listings that are not in stock</h2><p>Some of the lowest prices we see are on sold-out, backorder or pre-order listings. This shows how much more the cheapest in-stock listing costs.</p>{gap_html}</section>
<section aria-labelledby="h-s"><h2 id="h-s">Price spread between sellers (in stock)</h2>{spread_html}</section>
<section><h2>Want a heads-up?</h2><p>Pick a model and a target price on its page and we email you once when it is in stock at or under that price: <a href="/alerts/">set an alert</a>.</p>
<p><a href="/in-stock/">Everything in stock now</a> · <a href="/where-to-buy-bitaxe/">Where to buy</a> · <a href="/bitaxe-black-friday/">Black Friday 2026 tracker</a></p></section>
</article>"""
    items = [(f"{SHORT[m]} {money(usd(STATS[m]['best']))}", f"/models/{m}/") for m in ranked]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Cheapest in-stock home miners by price per TH/s", items)])


BF_DATES = dict(bf="2026-11-27", cm="2026-11-30")   # Black Friday / Cyber Monday 2026
BF_BANNER = ("2026-11-20", "2026-12-01")              # the site-wide Black Friday banner shows on these dates (inclusive, US Eastern)
BF_PATH = "/bitaxe-black-friday/"
BF_GROUPS = [  # key, heading, one-line who-it's-for
    ("bitaxe", "Bitaxe-class solo miners", "Small open-source boards like the Bitaxe and NerdQaxe. Cheap to run, mostly bought as a solo lottery ticket."),
    ("home", "Home and desk miners", "Finished boxes for a desk or shelf, from small lottery miners to quiet 10 TH/s+ home units."),
    ("heater", "Heater miners", "Miners built to heat a room (or your water) while they mine. Most useful in the cold months."),
]


def bf_group(mid):
    """Which Black Friday group a miner belongs to: Bitaxe-class boards, heater miners, or other home/desk miners."""
    if not is_home(mid):
        return "bitaxe"
    kind = (MODELS[mid].get("kind") or "").lower()
    return "heater" if "heater" in kind and not kind.startswith("desk") else "home"


def bf_today(now=None):
    """Calendar date in US Eastern (UTC-5 is close enough for a day-level banner)."""
    return ((now or GEN) - timedelta(hours=5)).date()


def bf_banner(now=None):
    """Site-wide Black Friday banner. Empty outside BF_BANNER, so it switches itself on and off with the 6-hourly rebuilds."""
    d = bf_today(now)
    lo, hi = (datetime.strptime(x, "%Y-%m-%d").date() for x in BF_BANNER)
    if not lo <= d <= hi:
        return ""
    bf, cm = (datetime.strptime(BF_DATES[k], "%Y-%m-%d").date() for k in ("bf", "cm"))
    if d < bf:
        n = (bf - d).days
        msg = f"Black Friday is Friday, November 27 ({'tomorrow' if n == 1 else f'in {n} days'})."
    elif d < cm:
        msg = "Black Friday weekend is on."
    elif d == cm:
        msg = "It's Cyber Monday."
    else:
        msg = "Some Cyber Monday deals run through today."
    return (f'<aside class="bf-banner" aria-label="Black Friday 2026"><p><b>{esc(msg)}</b> See every miner\'s price today next to the lowest price we\'ve logged so far. '
            f'<a class="btn sm" href="{BF_PATH}">Black Friday tracker →</a></p></aside>')


def bf_row(mid):
    """(table row html, at-our-low?) for one miner: cheapest in stock now vs the lowest in-stock price we've logged so far."""
    st, b = STATS[mid], STATS[mid]["best"]
    lo, lo_t, first = model_price_low(mid)
    now = usd(b) if b else None
    at_low = False
    if now is not None and lo is not None and now <= lo + 0.01:
        verdict, at_low = '<span class="badge pc-low">At the lowest we\'ve logged so far</span>', True
    elif now is not None and lo is not None:
        verdict = f"{money(now - lo)} above it ({(now / lo - 1) * 100:.0f}%)"
    elif now is not None:
        verdict = "No earlier in-stock price logged yet"
    else:
        c = st["low_any"]
        verdict = (f"Not in stock now. {esc(STATUS.get(c['stock_status'], c['stock_status']))}: {'≈ ' if c['currency'] != 'USD' else ''}{money(usd(c))} at {esc(sname(c['seller']))}"
                   if c else "Not in stock now")
    now_cell = (("≈ " if b["currency"] != "USD" else "") + money(now)) if b else "&ndash;"
    lo_cell = f'{money(lo)}<br><small>{esc(fmt_day(lo_t))}</small>' if lo is not None else "&ndash;"
    buy = offer_link(b, "View ↗") if b else f'<a href="/models/{mid}/#alerts">Get alert</a>'
    # data-label = the column name, shown above each value when the row turns into a card on phones (see .bf-table in style.css)
    return (f'<tr><td class="bf-miner"><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td>'
            f'<td class="num bf-now" data-label="Cheapest in stock">{now_cell}</td>'
            f'<td class="bf-shop" data-label="Shop">{esc(sname(b["seller"])) if b else "&ndash;"}</td>'
            f'<td class="num bf-low" data-label="Lowest we\'ve logged">{lo_cell}</td>'
            f'<td class="bf-vs" data-label="Today vs that low">{verdict}</td><td class="bf-buy">{buy}</td></tr>'), at_low


def bf_sort_key(mid):
    """In-stock miners first (cheapest first), then the rest by their cheapest listing."""
    b, c = STATS[mid]["best"], STATS[mid]["low_any"]
    price = usd(b) if b else (usd(c) if c else None)
    return (b is None, price if price is not None else 1e9)


def build_black_friday():
    path = BF_PATH
    trail = [("Home", "/"), ("Deals", "/deals/"), ("Black Friday 2026", path)]
    first = min((pts[0]["t"] for pts in history.values() if pts), default=latest["generated_at"])
    days = max(0, (GEN - parse_t(first)).days)
    head = ('<thead><tr><th>Miner</th><th class="num">Cheapest in stock</th><th>Shop</th>'
            '<th class="num" title="Lowest in-stock price we\'ve logged so far">Lowest we\'ve logged</th>'
            '<th>Today vs that low</th><th>Buy</th></tr></thead>')
    sections, jump, items, n_all, n_low_all = [], [], [], 0, 0
    for key, h, blurb in BF_GROUPS:
        mids = sorted([m for m in LIVE_TRACKED if bf_group(m) == key], key=bf_sort_key)
        if not mids:
            continue
        rows = [bf_row(m) for m in mids]
        n_ins = sum(1 for m in mids if STATS[m]["best"])
        n_low = sum(1 for _, at in rows if at)
        n_all, n_low_all = n_all + len(mids), n_low_all + n_low
        items += [(SHORT[m], f"/models/{m}/") for m in mids]
        jump.append(f'<a href="#bf-{key}">{esc(h)} ({len(mids)})</a>')
        sections.append(f'<section aria-labelledby="bf-{key}" class="bf-group"><h2 id="bf-{key}">{esc(h)}</h2><p>{esc(blurb)}</p>'
                        f'<p class="meta">{len(mids)} miners · {n_ins} in stock now · {n_low} at the lowest in-stock price we\'ve logged so far</p>'
                        f'<div class="tablewrap bf-wrap"><table class="bf-table">{head}<tbody>{"".join(r for r, _ in rows)}</tbody></table></div></section>')
    title = "Bitaxe & home miner Black Friday 2026 deals: live prices vs our price log | Bitaxe Radar"
    desc = f"Black Friday 2026 deals on {n_all} home Bitcoin miners (Bitaxe, desk and heater miners): today's price vs the lowest we've logged so far."
    body = f"""<article>
<header class="hero"><h1>Bitaxe and home miner Black Friday 2026 deals</h1>
{deal_pills(path)}
<p class="lede">Black Friday is November 27 and Cyber Monday is November 30. We check every shop every 6 hours, so this page shows how today's price compares with the lowest in-stock price we've logged so far, for every miner we track.</p>
<p class="meta">Prices checked {tag_time(latest['generated_at'])} · tracking since {esc(fmt_day(first))} · {n_low_all} of {n_all} miners at the lowest we've logged so far</p>
<nav class="browse" aria-label="Miner types">{"".join(jump)}</nav></header>
{"".join(sections)}
<p class="hint">We started tracking on {esc(fmt_day(first))}, so "the lowest we've logged so far" only covers the last {plural(days, "day")} and only the shops we check. Treat it as a rough guide until we have a few months of history. Prices are before shipping and tax; euro and Canadian-dollar prices are converted to US dollars as an estimate.</p>
<section aria-labelledby="h-a"><h2 id="h-a">Get a Black Friday price alert</h2><p>Pick a miner and your target price. We email you once when it's in stock at or under that price, so you don't have to refresh shop pages all week.</p>{signup_html("any")}</section>
<section aria-labelledby="h-h"><h2 id="h-h">How to spot a real Black Friday deal</h2><ul>
<li>Compare against the price history on each miner's page, not the shop's "was" price.</li>
<li>Check what's in the box: some bundles include a power supply or stand, some don't.</li>
<li>Stock moves fast on popular models. Sold-out listings drop off the "cheapest in stock" column.</li>
<li>Heater miners on pre-order may not ship before winter. Read the shop's shipping date before you pay.</li>
<li>A small miner is a lottery ticket, not an investment. Buy one because you want to run it.</li></ul></section>
<section><h2>More</h2><p><a href="/deals/">Best deals right now</a> · <a href="/price-per-th/">Price per TH/s</a> · <a href="/in-stock/">Everything in stock</a> · <a href="/heater-miners/">Heater miners</a> · <a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a></p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, scripts=SIGNUP_SCRIPTS, jsonld=[itemlist("Home Bitcoin miners on the Black Friday 2026 tracker", items)])



# ---------------------------------------------------------------------------------------------
# HEATER & HOME MINERS hub + plain-language guides
# ---------------------------------------------------------------------------------------------
HEATER_GROUP = ["avalon-mini-3", "avalon-q", "heatbit-trio", "heatbit-maxi", "heatbit-canvas", "gekko-kbox-22", "dcentral-stealthminer"]
DESK_GROUP = ["avalon-nano-3s", "hammer-bc04", "braiins-bmm-101", "heatbit-bitair", "bitcube", "futurebit-apollo-iii", "hammer-thor-p2", "hammer-bc08", "nmqaxe-nexus"]
GUIDE_UPDATED = "2026-10-21"
NETWORK_EH_SEEN = "about 1,050 EH/s"       # mempool.space /api/v1/mining/hashrate/3d on 2026-10-21 (see docs/HOME_MINING_HUB_PLAN.md)


# ---------------------------------------------------------------------------------------------
# earnings estimates (live network inputs via earnings.py; hidden when the inputs are stale)
# ---------------------------------------------------------------------------------------------
def draw_watts(mid):
    """Most heat it can put out (Heatbit Trio adds plain electric heating on top of mining). For room-heat fit only."""
    m = MODELS[mid]
    return m.get("heat_watts", m["watts"])


def mine_watts(mid):
    """Watts used by mining. All earnings, power-cost and break-even figures use this, never the extra heater-mode draw."""
    return MODELS[mid]["watts"]


def earn(mid):
    if not (NET and NET_OK):
        return None
    m = MODELS[mid]
    return dict(pool=E.pool_estimate(m["hashrate_ths"], NET), power=E.power_shown(mine_watts(mid)),
                solo=E.solo_odds(m["hashrate_ths"], NET))


def calc_attrs(mid):
    return f' data-th="{float(MODELS[mid]["hashrate_ths"])!r}" data-w="{float(mine_watts(mid))!r}"'


def net_cls(mid):
    n = E.net_month(MODELS[mid]["hashrate_ths"], mine_watts(mid), NET)
    return "pos" if n >= 0.01 else "neg" if n <= -0.01 else ""


def net_text(mid):
    return E.net_words(MODELS[mid]["hashrate_ths"], mine_watts(mid), NET)


def heater_net(mid):
    """Net monthly figure when the miner replaces electric heat: power cost minus the heat you'd buy anyway minus the pool estimate.
    The heat is worth exactly the power it uses, so the net is the pool estimate coming back to you, at any power price."""
    e = earn(mid)
    return e["pool"]["usd_month_shown"] if e else None


def heat_line(mid):
    a = calc_attrs(mid)
    e = earn(mid)
    m = MODELS[mid]
    extra = (f" Its extra heater mode (up to {m['heat_watts']:,g} W) is plain electric heat and isn't counted here." if m.get("heat_watts") else "")
    return (f'<p class="heatv">As a heater: the ≈<span data-calc="power"{a}>{E.fmt_usd(e["power"])}</span>/mo of power is heat you\'d pay for anyway, '
            f'so the pool estimate is your net: <b>about {E.fmt_usd(heater_net(mid))}/mo back</b></p>'
            f'<p class="hint">Only if it replaces an electric space heater you\'d run anyway, and only while you need the heat. '
            f"A heat pump or gas is usually cheaper per unit of heat.{extra}</p>")


def earn_line(mid, heat=False):
    """One neutral line for cards: running cost, plus block odds (or, for heaters, the net once the heat is counted)."""
    e = earn(mid)
    if not e:
        return ""
    a = calc_attrs(mid)
    parts = [f'≈<span data-calc="power"{a}>{E.fmt_usd(e["power"])}</span>/mo power']
    if heat and mid in HEAT_SET:
        parts.append(f'as a heater, nets ≈{E.fmt_usd(e["pool"]["usd_month_shown"])}/mo back')
    else:
        parts.append(f'1 in {E.fmt_big(e["solo"]["one_in_year"])}/yr block odds')
    return (f'<div class="cardline" title="Estimates at your electricity price; change with Bitcoin price and network difficulty">'
            + " · ".join(parts) + "</div>")


def rate_box(anchor=False):
    """Electricity price input. Hidden until calc.js runs; without JS the page shows the $0.15 default figures."""
    if not (NET and NET_OK):
        return ""
    return (f'<form class="ratebox"{" id=\"rate\"" if anchor else ""} hidden><label>Your electricity price '
            f'<span class="rin">$<input type="number" inputmode="decimal" min="0" max="2" step="0.01" value="{E.POWER_RATE}" aria-label="Electricity price in US dollars per kWh">/kWh</span></label>'
            '<small>Saved on this device. Updates every estimate on the page.</small></form>')


def calc_scripts():
    if not (NET and NET_OK):
        return ""
    data = {k: NET[k] for k in ("network_hashrate_hs", "subsidy_btc", "avg_fees_btc", "btc_usd")}
    data.update(pool_fee=E.POOL_FEE, haircut=E.HAIRCUT, default_rate=E.POWER_RATE)
    return f'<script>window.RADAR_NET={json.dumps(data)};</script>\n<script src="/calc.js" defer></script>\n'


def breakeven_line(mid):
    be = E.breakeven_rate(MODELS[mid]["hashrate_ths"], mine_watts(mid), NET)
    txt = f"about {E.fmt_rate(be)}/kWh" if be >= 0.001 else "under $0.001/kWh"
    return (f'<p class="beline">Break-even power price: <b>{txt}</b></p>'
            '<p class="hint">Above this price the power costs more than the pool estimate.</p>')


def block_usd_text(so):
    return f"${float(format(so['block_usd'], '.2g')):,.0f}"


EARN_NOTE = "Estimate. Changes with Bitcoin price and network difficulty."


def earn_box(mid):
    e = earn(mid)
    if not e:
        return ""
    pe, solo_best, heater = e["pool"], mid in SOLO_SET, mid in HEAT_SET
    tiles = [("If you pool mine", f'{E.fmt_usd(pe["usd_month_shown"])}<small>/month</small>',
              f'about {E.fmt_usd(pe["usd_day_shown"])} a day, before electricity' + (". Tiny, so most owners solo mine" if solo_best and mid not in POOL_SET else "")),
             ("Power cost", f'<span data-calc="power"{calc_attrs(mid)}>{E.fmt_usd(e["power"])}</span><small>/month</small>',
              f'≈ {mine_watts(mid):,g} W{" mining" if MODELS[mid].get("heat_watts") else ""}, 24/7 at <span data-calc="rate">{E.fmt_rate(E.POWER_RATE)}</span>/kWh' + (". The heat offsets this" if heater else ""))]
    if solo_best:
        so = e["solo"]
        tiles.append(("Solo block chance", f'1 in {E.fmt_big(so["one_in_year"])}<small>/year</small>',
                      f'about 1 in {E.fmt_big(so["one_in_day"])} a day. A block is worth ≈ {block_usd_text(so)}'))
    t = "".join(f'<div class="etile"><small>{esc(a)}</small><b>{b}</b><span>{c if "data-calc" in c else esc(c)}</span></div>' for a, b, c in tiles)
    nets = (f'<p class="netline-wrap"><small>If you pool mine:</small> <span class="netline {net_cls(mid)}" data-calc="net"{calc_attrs(mid)}>{esc(net_text(mid))}</span></p>'
            + breakeven_line(mid) + (heat_line(mid) if heater else ""))
    basis = (f'Uses BTC ≈ ${NET["btc_usd"]:,.0f}, network ≈ {NET["network_hashrate_hs"] / 1e18:,.0f} EH/s and the seller-stated hashrate, '
             f'minus a 2% pool fee and a 10% safety margin, rounded down. Updated {fmt_time(NET["fetched_at"])}.')
    return (f'<section class="earnbox" aria-labelledby="h-earn"><h2 id="h-earn">What it could earn</h2>{rate_box()}<div class="etiles">{t}</div>{nets}'
            f'<p class="hint">{EARN_NOTE} <span class="basis">{esc(basis)}</span> <a href="/guides/solo-vs-pool-mining/">Solo vs pool</a></p></section>')


def cat_tags(mid):
    tags = [(path, label) for key, path, label, h1, members, _ in CATS if mid in members]
    if not tags:
        return ""
    return '<p class="tags">Best for: ' + "".join(f'<a class="tag" href="{p}">{esc(l)}</a>' for p, l in tags) + "</p>"


def browse_pills(current=None):
    items = [("/miners/", "All")] + [(path, label) for key, path, label, *_ in CATS]
    return ('<nav class="browse" aria-label="Browse miners">' + "".join(
        f'<a href="{p}"' + (' aria-current="page"' if p == current else "") + f'>{esc(l)}</a>' for p, l in items) + "</nav>")


def browse_tiles():
    tiles = []
    for key, path, label, h1, members, photo in CATS:
        n = len([m for m in members if m in TRACKED and m not in NOINDEX_MODELS])
        img = (f'<img src="/img/models/{photo}.webp" width="{MODEL_IMG[photo][0]}" height="{MODEL_IMG[photo][1]}" alt="{esc(MODEL_IMG[photo][2])}" loading="lazy" decoding="async">'
               if photo in MODEL_IMG else "")
        tiles.append(f'<a class="btile" href="{path}"><span class="bimg">{img}</span><b>{esc(label)}</b><small>{n} miners</small></a>')
    tag = ('<svg viewBox="0 0 48 48" aria-hidden="true" focusable="false"><path d="M6 24 24 6h16a2 2 0 0 1 2 2v16L24 42a2 2 0 0 1-2.8 0L6 26.8A2 2 0 0 1 6 24Z" fill="#f7931a"/>'
           '<circle cx="34" cy="14" r="3.5" fill="#0f1a2e"/></svg>')
    tiles.append(f'<a class="btile" href="/deals/"><span class="bimg">{tag}</span><b>Deals</b><small>Price drops</small></a>')
    return '<section class="browse-tiles" aria-label="Browse by type"><div class="btiles">' + "".join(tiles) + "</div></section>"


def hub_card(mid, heat=True, rank=None, why="", attrs=""):
    st, m = STATS[mid], MODELS[mid]
    b = st["best"]
    pre = [o for o in st["offers"] if o["stock_status"] in ("preorder", "backorder") and usd(o) is not None]
    hw = m.get("heat_watts", m["watts"])
    if b:
        conv = b["currency"] != "USD"
        price = f'{"≈ " if conv else ""}{money(usd(b))}' + (f'<small>{"CA" if b["currency"] == "CAD" else "EU"} shop</small>' if conv else "")
        where = f'at {esc(sname(b["seller"]))}' + (f' · in stock at {plural(len(st["in_stock"]), "shop")}' if len(st["in_stock"]) > 1 else "")
        status, cls = badge("in_stock"), "card"
    elif pre:
        o = min(pre, key=usd)
        conv = o["currency"] != "USD"
        price = f'{"≈ " if conv else ""}{money(usd(o))}' + (f'<small>{"CA" if o["currency"] == "CAD" else "EU"} shop</small>' if conv else "")
        where = f'at {esc(sname(o["seller"]))} · not in stock yet'
        status, cls = badge(o["stock_status"]), "card"
    else:
        low = st["low_any"]
        price, where = "Sold out", (f'Last listed {money(usd(low))}' if low else "")
        status, cls = '<span class="badge b-out_of_stock">Sold out</span>', "card soldout"
    rib = f'<span class="ribbon rank">#{rank}</span>' if rank else ""
    return (f'<article class="{cls}"{attrs}>{rib}<div class="art{" photo" if mid in MODEL_IMG else ""}">{model_img(mid)}</div><div class="body">'
            f'<h3><a href="/models/{mid}/">{esc(SHORT[mid])}</a></h3>'
            + (f'<div class="why">{esc(why)}</div>' if why else "") +
            f'<div class="spec">≈{m["hashrate_ths"]:g} TH/s · ≈{m["watts"]:,g} W' + (f' · ≈{btu(m["watts"]):,.0f} BTU/h heat' if heat else "")
            + (f' (up to {btu(hw):,.0f} with heater on)' if heat and hw != m["watts"] else "") + '</div>'
            f'<div class="price">{price}</div><div class="where">{where}</div>{earn_line(mid, heat)}'
            f'<div class="row">{status}<a class="btn sm" href="/models/{mid}/" aria-label="See {esc(SHORT[mid])} prices">See prices</a></div>'
            "</div></article>")


def build_home_miners():
    path = "/home-miners/"
    trail = [("Home", "/"), ("Heater & home miners", path)]
    heaters = [m for m in HEATER_GROUP if m in HOME_TRACKED]
    desk = [m for m in DESK_GROUP if m in HOME_TRACKED]
    home_offers = [o for o in OFFERS if is_home(o["model"])]
    n_in = sum(1 for o in home_offers if in_stock(o))
    cheapest_heater = cheapest([o for m in heaters for o in STATS[m]["in_stock"]])
    title = f"Bitcoin heater miners & home miners: prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = (f"Heater miners and home Bitcoin miners compared: Avalon, Heatbit, Braiins and Hammer prices and stock at US shops, "
            f"{n_in} of {len(home_offers)} listings in stock. Updated {fmt_day(GEN)}.")
    lead_bits = f' Cheapest heater miner in stock today: <strong>{money(usd(cheapest_heater))}</strong> ({esc(SHORT[cheapest_heater["model"]])} at {esc(sname(cheapest_heater["seller"]))}).' if cheapest_heater else ""
    body = f"""<article>
<header class="hero"><h1>Heater &amp; home miners</h1>
<p class="lede">Miners built to live in your home: they warm a room like a space heater while they mine Bitcoin. Prices and stock from the shops, checked every 6 hours.{lead_bits}</p>
<p class="meta">{n_in} of {len(home_offers)} listings in stock · checked {tag_time(latest['generated_at'])}</p>
{browse_pills()}</header>
<section aria-labelledby="h-heat"><div class="sec-head"><h2 id="h-heat">Heater miners</h2><a href="/guides/how-heater-miners-work/">How they work →</a></div>
<div class="cards">{"".join(hub_card(m) for m in heaters)}</div></section>
<section aria-labelledby="h-desk"><div class="sec-head"><h2 id="h-desk">Desk &amp; small home miners</h2><a href="/#miners">Bitaxe miners →</a></div>
<div class="cards">{"".join(hub_card(m) for m in desk)}</div></section>
<section aria-labelledby="h-explain"><h2 id="h-explain">New to this? Two-minute reads</h2><ul class="links">
<li><a href="/guides/how-heater-miners-work/">How a heater miner works</a></li>
<li><a href="/guides/solo-vs-pool-mining/">Solo vs pool mining, in plain words</a></li></ul></section>
<section id="faq" aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>
<details><summary>What is a heater miner?</summary><p>A Bitcoin miner made to sit in a room and heat it. A mining chip turns almost all of its electricity into heat, like an electric space heater, so these units are built to be quiet, safe on a household outlet and controlled like a heater. The difference is that the heat also does mining work. <a href="/guides/how-heater-miners-work/">More</a>.</p></details>
<details><summary>Will it pay my power bill?</summary><p>Part of it at best, and nothing is guaranteed. In a mining pool it earns small, steady amounts of bitcoin that offset some of the electricity cost. How much changes with Bitcoin's price, the network's total hashrate and your power rate. If you'd buy an electric heater anyway, that offset is the appeal.</p></details>
<details><summary>Solo or pool: which should I pick?</summary><p>Pool if you want small, regular payouts. Solo if you want a long-shot chance at a whole block (about 3.125 BTC plus fees) and are fine with probably getting nothing. Most heater-miner owners pool. <a href="/guides/solo-vs-pool-mining/">Solo vs pool explained</a>.</p></details>
<details><summary>Can I plug it into a normal outlet?</summary><p>Smaller units, yes. A standard US 15 A, 120 V circuit should carry about 1,440 W continuously (the 80% rule), so 1,500 W-class units are best on their own circuit, and don't share a circuit with another heater. Check the maker's guidance.</p></details>
<details><summary>Why do some show "Pre-order"?</summary><p>The shop takes orders but doesn't have stock to ship yet. We label these separately from in-stock listings, and the shop's page has its ship timing.</p></details>
</section>
<p class="hint">Hashrate, watts and heat are the sellers' stated figures. BTU/h = watts × 3.412. Prices are before shipping and tax; Canadian-dollar prices are converted as an estimate.</p>
</article>"""
    items = [(SHORT[m], f"/models/{m}/") for m in heaters + desk]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Heater and home Bitcoin miners tracked by Bitaxe Radar", items)])


CAT_COPY = {
    "solo": dict(lede="Small, low-power miners that take a shot at a whole Bitcoin block. Any miner can solo or pool mine; these suit the solo lottery best.",
                 title="Best miners for solo mining: Bitaxe, NerdQaxe & desk miners", what="solo lottery miners: Bitaxe, NerdQaxe, Nerdaxe and small desk miners"),
    "pool": dict(lede="Stronger miners where a pool's small, steady payouts make more sense than the solo lottery. Any miner can do either.",
                 title="Best miners for pool mining at home: Avalon, Heatbit & more", what="home miners with enough hashrate for pool mining: Avalon, Heatbit, Hammer"),
    "heat": dict(lede="Miners that warm a room like a space heater while they mine Bitcoin.",
                 title="Bitcoin heater miners: Heatbit, Avalon Mini 3 & more", what="heater miners that warm a room while they mine: Heatbit, Avalon"),
}


def card_sort_key(mid):
    st = STATS[mid]
    rank = 0 if st["best"] else 1 if any(o["stock_status"] in ("preorder", "backorder") for o in st["offers"]) else 2
    return (rank, show_price(mid) or 1e9, -MODELS[mid]["hashrate_ths"])   # cheapest first within in stock / pre-order / sold out


def build_category(key):
    _, path, label, h1, members, _ = next(c for c in CATS if c[0] == key)
    cp = CAT_COPY[key]
    ms = sorted([m for m in members if m in TRACKED and m not in NOINDEX_MODELS], key=card_sort_key)
    older = [m for m in members if m in TRACKED and m in NOINDEX_MODELS]
    offs = [o for m in ms for o in STATS[m]["offers"]]
    n_in = sum(1 for o in offs if in_stock(o))
    trail = [("Home", "/"), ("All miners", "/miners/"), (label + (" miners" if key != "heat" else ""), path)]
    title = f"{cp['title']} ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"Prices and stock for {cp['what']}. {n_in} of {len(offs)} listings in stock, checked every 6 hours."
    older_html = ('<p class="older">Older models: ' + " · ".join(
        f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' + (f' from {money(usd(STATS[m]["best"]))}' if STATS[m]["best"] else " (sold out)") for m in older) + "</p>") if older else ""
    guide = ('<a href="/heat-calculator/">Which one fits my room?</a> · <a href="/guides/how-heater-miners-work/">How heater miners work</a> · <a href="/guides/solo-vs-pool-mining/">Solo vs pool</a>' if key == "heat"
             else '<a href="/guides/solo-vs-pool-mining/">Solo vs pool, in plain words</a>' + (' · <a href="/guides/how-heater-miners-work/">How heater miners work</a>' if key == "pool" else ""))
    solo_line = ""
    if key == "solo" and NET and NET_OK:
        so = E.solo_odds(1.2, NET)
        solo_line = (f'<p class="older">A solo block is worth ≈ {block_usd_text(so)} right now. '
                     f'Each miner page shows its odds. Pool estimates for these are tiny. '
                     f'<a href="/solo-odds/">Solo odds calculator</a> · <a href="/solo-wins/">Recent solo wins</a></p>')
    earn_hint = f'<p class="hint">Pool and power figures are estimates: pool payout before electricity, power at <span data-calc="rate">{E.fmt_rate(E.POWER_RATE)}</span>/kWh. {EARN_NOTE}</p>' if NET and NET_OK else ""
    body = f"""<article>
<header class="hero"><h1>{esc(h1)}</h1>
<p class="lede">{esc(cp['lede'])}</p>
<p class="meta">{n_in} of {len(offs)} listings in stock · checked {tag_time(latest['generated_at'])}</p>
{browse_pills(path)}
{best_pills()}
{rate_box()}</header>
<section aria-label="{esc(h1)}"><div class="cards">{"".join(hub_card(m, heat=(key == "heat")) for m in ms)}</div>
{solo_line}</section>
<section class="guides-line"><p>New to this? {guide}</p>{earn_hint}
<p class="hint">Hashrate and watts are the sellers' stated figures. Prices are before shipping and tax; euro and Canadian-dollar prices are converted as an estimate.</p></section>
</article>"""
    items = [(SHORT[m], f"/models/{m}/") for m in ms]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist(f"{h1}: miners tracked by Bitaxe Radar", items)])


# ---------------------------------------------------------------------------------------------
# "Best for" pages: ranked picks with a one-line why. Noise figures are the makers'/sellers' stated numbers.
# ---------------------------------------------------------------------------------------------
NOISE = {   # (max stated dB or 0 for fanless, text, source)
    "heatbit-canvas": (0, "No fans, so it runs silent (maker-stated)", "heatbit.com Canvas FAQ"),
    "hammer-bc04": (36, "32–36 dB stated", "Altair Technology Hammer series guide"),
    "avalon-nano-3s": (40, "33–40 dB stated", "Canaan shop listing"),
    "braiins-bmm-101": (40, "About 40 dB stated", "Braiins Forge product page"),
    "heatbit-trio": (45, "Up to about 45 dB stated", "heatbit.com Trio FAQ"),
    "avalon-mini-3": (55, "About 33–55 dB stated, by mode", "seller listings"),
    "heatbit-maxi": (55, "About 45–55 dB stated, by mode", "heatbit.com Maxi FAQ"),
    "bitforge-nano": (29, "About 29 dB stated", "Bitcoin Merch listing"),
    "bitaxe-gamma-hex": (30, "About 30 dB stated (liquid-cooled)", "Solo Satoshi listing"),
    "hammer-bc08": (38, "About 38 dB stated", "Altair Technology listing"),
    "hammer-thor-p2": (40, "About 38–40 dB stated", "Altair / Bitcoin Merch listings"),
    "heatbit-bitair": (44, "25–44 dB stated", "Heatbit / Altair listings"),
    "gekko-kbox-22": (47, "About 38–47 dB stated, by mode", "Altair Technology listing"),
    "dcentral-stealthminer": (60, "Under 60 dB stated", "D-Central listing"),
    "heatbit-bitwater": (0, "No fans; the water in the tank cools the chips (maker-stated)", "heatbit.com Bitwater page"),
}


def under_price(limit):
    ms = [m for m in TRACKED if m not in NOINDEX_MODELS and STATS[m]["best"] and usd(STATS[m]["best"]) is not None and usd(STATS[m]["best"]) < limit]
    return sorted(ms, key=lambda m: usd(STATS[m]["best"]))


def best_defs():
    """slug -> dict(h1, label, lede, picks=[(mid, why)], faq=[(q, a)], title, desc). Pages without honest picks are skipped."""
    d = {}
    beg = [("bitaxe-gamma", "Cheapest way in. Small, open-source, about 18 W, huge community for help."),
           ("avalon-nano-3s", "Finished box with an app, Wi-Fi and the power adapter in the box. Plug in and go."),
           ("braiins-bmm-101", "Metal case and touchscreen with Braiins OS already set up. No tinkering."),
           ("nerdaxe-gamma", "Same class as the Bitaxe Gamma, with a color screen to see what it's doing."),
           ("heatbit-bitair", "An air purifier with a tiny miner inside. USB-C, about 25 W, nothing to build."),
           ("bitcube", "A small cube with a touchscreen. USB-C, about 25 W, set up in minutes. Pre-order for Christmas.")]
    d["beginners"] = dict(label="Beginners", h1="Best Bitcoin miner for beginners",
        lede="Cheap, simple, low-power miners that are easy to set up. Start small and learn how mining works.",
        picks=[x for x in beg if x[0] in TRACKED],
        title="Best Bitcoin miner for beginners: easy, cheap home miners",
        what="beginner-friendly Bitcoin miners: Bitaxe Gamma, Avalon Nano 3S, Braiins Mini Miner",
        faq=[("What is the best Bitcoin miner for a beginner?", "A Bitaxe Gamma if you want the cheapest start and like to tinker a little. An Avalon Nano 3S or Braiins Mini Miner if you want a finished box with an app or screen."),
             ("Will a beginner miner make money?", "Don't expect it to. Small miners earn tiny amounts in a pool, or take a long-shot chance at a whole block solo. Treat it as a hobby and a way to learn."),
             ("How much power does a beginner miner use?", "About 18 to 140 W for the miners on this page, roughly a light bulb to a small heater. Each miner page shows the running cost.")])
    q = sorted([m for m in NOISE if m in TRACKED and NOISE[m][0] <= 45], key=lambda m: (NOISE[m][0], MODELS[m]["watts"]))
    d["quiet"] = dict(label="Quiet", h1="Quietest Bitcoin miners",
        lede="Miners whose makers or sellers state a low noise level, quietest first. Good for a bedroom or office.",
        picks=[(m, NOISE[m][1] + ".") for m in q],
        title="Quietest Bitcoin miners for a bedroom or office",
        what="the quietest home Bitcoin miners by stated noise: Heatbit Canvas, Hammer BC04, Avalon Nano 3S",
        faq=[("What is the quietest Bitcoin miner?", f"Of the miners we track, the {SHORT[q[0]]}: {NOISE[q[0]][1][0].lower() + NOISE[q[0]][1][1:]}." if q else ""),
             ("Are Bitaxe miners quiet?", "They're small with one little fan, so they're fairly quiet, but shops don't publish a noise figure, so we don't rank them here."),
             ("How loud is 40 dB?", "About a quiet library or a soft hum. Lower power modes on most miners also lower the noise.")],
        hint="Noise figures are the makers' or sellers' own numbers, not our measurements. Lower power modes are usually quieter.")
    u = under_price(100)
    if u:
        d["under-100"] = dict(label="Under $100", h1="Best Bitcoin miners under $100",
            lede="In-stock miners under $100 right now, cheapest first. Prices are before shipping and tax.",
            picks=[(m, f"About {money(STATS[m]['per_th'])} per TH/s, {MODELS[m]['watts']:g} W of power.") for m in u],
            more=[m for m in under_price(150) if m not in u],
            title="Best Bitcoin miners under $100, in stock now",
            what="Bitcoin miners in stock under $100, checked every 6 hours, cheapest first",
            faq=[("What is the best Bitcoin miner under $100?", f"Right now the {SHORT[u[0]]}, in stock for {money(usd(STATS[u[0]]['best']))} at {sname(STATS[u[0]]['best']['seller'])}. Prices change, so check the shop."),
                 ("Is a cheap miner worth it?", "As a hobby and a solo-mining lottery ticket, yes. As income, no: small miners earn very little, and electricity costs money."),
                 ("Does the price include a power supply?", "Often, but not always. Check the listing details on each miner's page before you buy.")])
    heat = [("avalon-mini-3", "Built like a baseboard heater. About 800 W, enough for a medium room."),
            ("heatbit-maxi", "All 1,500 W of its heat comes from mining, plus air purifying. For a bigger room."),
            ("heatbit-trio", "Space heater and air purifier in one, up to 1,500 W. Only 400 W of that is mining."),
            ("dcentral-stealthminer", "About 860 W through quiet Noctua fans on a normal 120 V outlet. Refurbished, ships from Canada."),
            ("avalon-q", "Most heat, about 1,674 W. Best for a garage or basement; louder at full power.")]
    d["heating-a-room"] = dict(label="Heating a room", h1="Best miners for heating a room",
        lede="Miners built to heat a whole room like a space heater while they mine.",
        picks=[x for x in heat if x[0] in TRACKED], heat=True,
        title="Best Bitcoin miners for heating a room this winter",
        what="Bitcoin heater miners for heating a room: Avalon Mini 3, Heatbit Maxi, Heatbit Trio, Avalon Q",
        faq=[("What is the best heater miner?", "For a medium room, the Avalon Mini 3 (about 800 W). For a bigger room, the Heatbit Maxi or Trio (up to 1,500 W). The Avalon Q gives the most heat but suits a garage or basement."),
             ("Does a heater miner heat as well as a space heater?", "Yes, watt for watt. Nearly all the electricity becomes heat, just like an electric heater."),
             ("Will it pay my heating bill?", "Part of it at best, and nothing is guaranteed. In a pool it earns small amounts that offset some of the power cost.")],
        hint="Smaller heater miners like the Heatbit Canvas and Avalon Nano 3S warm a person or desk rather than a whole room: see all heater miners.")
    for k, v in d.items():
        v["faq"] = [(a, b) for a, b in v["faq"] if b]
    return {k: v for k, v in d.items() if v["picks"]}


def faq_ld(faq):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}


def best_pills(current=None):
    return ('<nav class="browse best-row" aria-label="Best for"><span>Best for</span>' + "".join(
        f'<a href="/best/{k}/"' + (' aria-current="page"' if k == current else "") + f'>{esc(v["label"])}</a>' for k, v in BEST.items()) + "</nav>")


def build_best(slug):
    b = BEST[slug]
    path = f"/best/{slug}/"
    trail = [("Home", "/"), ("Best for", "/best/"), (b["label"], path)]
    title = f"{b['title']} ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = shorten(f"Ranked picks: {b['what']}. Live prices and stock, updated every 6 hours.", 158)
    cards = "".join(hub_card(m, heat=b.get("heat", False), rank=i + 1, why=why) for i, (m, why) in enumerate(b["picks"]))
    more = b.get("more") or []
    more_html = (f'<section aria-labelledby="h-more"><h2 id="h-more">Just over $100</h2><div class="cards">{"".join(hub_card(m, heat=False) for m in more)}</div></section>') if more else ""
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in b["faq"])
    hint = f'<p class="hint">{esc(b["hint"])}</p>' if b.get("hint") else ""
    body = f"""<article>
<header class="hero"><h1>{esc(b['h1'])}</h1>
<p class="lede">{esc(b['lede'])}</p>
<p class="meta">checked {tag_time(latest['generated_at'])}</p>
{best_pills(slug)}
{rate_box()}</header>
<section aria-label="Ranked picks"><div class="cards">{cards}</div>{hint}</section>
{more_html}
<section id="faq" aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{faq_html}</section>
<section class="guides-line"><p>Browse: <a href="/miners/">All miners</a> · <a href="/solo-miners/">Solo</a> · <a href="/pool-miners/">Pool</a> · <a href="/heater-miners/">Heaters</a> · <a href="/guides/solo-vs-pool-mining/">Solo vs pool</a></p>
<p class="hint">Hashrate and watts are the sellers' stated figures. Prices are before shipping and tax. Pool and power figures are estimates; {EARN_NOTE.lower()}</p></section>
</article>"""
    items = [(SHORT[m], f"/models/{m}/") for m, _ in b["picks"]]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist(b["h1"], items), faq_ld(b["faq"])])


BEST = {}


# ---------------------------------------------------------------------------------------------
# llms.txt: plain-text summary for AI assistants and search tools
# ---------------------------------------------------------------------------------------------
def miner_line(m):
    st = STATS[m]
    if st["best"]:
        p = f'in stock from {money(usd(st["best"]))} at {sname(st["best"]["seller"])}'
    elif st["low_any"]:
        p = f'not in stock; lowest listed {money(usd(st["low_any"]))} at {sname(st["low_any"]["seller"])} ({STATUS[st["low_any"]["stock_status"]].lower()})'
    else:
        p = "no listings"
    mm = MODELS[m]
    return f"- [{SHORT[m]}]({BASE}/models/{m}/): ≈{mm['hashrate_ths']:g} TH/s, ≈{mm['watts']:,g} W; {p}"


def solo_llms():
    if not SOLO_WINS:
        return ""
    w = SOLO_WINS[0]
    return f" Last solo win: {fmt_date(w['time'])} (pool: {w['pool']}; device: {win_device(w)[0].split(': ', 1)[1]}); {len(wins_last_year())} in the past 12 months."


def build_llms():
    live = [m for m in TRACKED if m not in NOINDEX_MODELS]
    cats = "\n".join(f"- [{h1}]({BASE}{path})" for _, path, _, h1, _, _ in CATS)
    bests = "\n".join(f"- [{v['h1']}]({BASE}/best/{k}/)" for k, v in BEST.items())
    answers = "\n".join(f"- {v['faq'][0][0]} {v['faq'][0][1]} ({BASE}/best/{k}/)" for k, v in BEST.items())
    head = f"""# Bitaxe Radar

> Price and stock tracker for small home Bitcoin miners (Bitaxe, NerdQaxe, Nerdaxe) and heater and home miners (Avalon, Heatbit, Braiins, Hammer). Prices come from each shop's own pages and are checked every 6 hours. Prices are before shipping and tax. Last update: {latest['generated_at']}.

Bitaxe Radar is independent. Some shop links are affiliate links; they never change prices or rankings. Mining earnings are never guaranteed: small miners are a solo "lottery", and pool payouts change with Bitcoin's price and network difficulty.

## Browse by type
{cats}
- [All miners, with filters]({BASE}/miners/)
- [Find my miner: 3-question quiz]({BASE}/find-my-miner/)
- [Price alerts]({BASE}/alerts/)
- [Deals and price drops]({BASE}/deals/)
- [Everything in stock]({BASE}/in-stock/)

## Best for
{bests}

## Quick answers
{answers}

## Miners and current best price
{chr(10).join(miner_line(m) for m in live)}

## Guides
- [Is home mining worth it?]({BASE}/guides/is-home-mining-worth-it/): depends on your electricity price; each miner page has a break-even power price.
- [Solo odds calculator]({BASE}/solo-odds/): chance of finding a block per day, per year and over 5 years for any hashrate, from the live network hashrate. Solo mining is a lottery.
- [Solo block wins]({BASE}/solo-wins/): recent Bitcoin blocks found by solo miners, with date, pool (the service the winner mined through), reward and device (only when the winner shared it).{solo_llms()}
- [Can solar power a Bitcoin miner?]({BASE}/guides/solar-bitcoin-mining/): how many 400 W panels each miner needs (example: 4 peak sun hours, 14% losses), daytime-only vs batteries.
- [Mining to heat your home]({BASE}/guides/bitcoin-mining-heat-your-home/): a miner heats like an electric space heater and pays a little back; it beats a space heater but usually not a heat pump (DOE: about 50% less electricity).
- [Solo vs pool mining]({BASE}/guides/solo-vs-pool-mining/): solo is a lottery for a whole block; pool pays small, steady amounts.
- [Which mining pool should I use?]({BASE}/guides/bitcoin-mining-pools/): Public Pool (solo, no fee), Solo CKPool (solo, 2%), Parasite Pool (hybrid: 1 BTC to the block finder, no fee), OCEAN (shared, 2%, 1% with DATUM), Braiins Pool (FPPS, 2.5%), with live sats per day per miner.
- [How heater miners work]({BASE}/guides/how-heater-miners-work/): a miner turns its electricity into heat like a space heater.
- [Room heat calculator]({BASE}/heat-calculator/): room size in, heat needed (about 10 W per sq ft as a rule of thumb) and which tracked miners can heat it.
- [Price per TH/s leaderboard]({BASE}/price-per-th/): miners ranked by price per stated TH/s at today's cheapest in-stock price, with J/TH and a check against the lowest price we have logged.
- [Where to buy a Bitaxe]({BASE}/where-to-buy-bitaxe/)
- [How we track prices]({BASE}/how-we-track/)
- [All guides]({BASE}/guides/)
- [All shops we check]({BASE}/sellers/)

## Optional
- [Full details for every miner]({BASE}/llms-full.txt)
- Contact: {CONTACT}
"""
    (SITE / "llms.txt").write_text(head)
    parts = [head.replace("## Optional\n- [Full details for every miner](" + BASE + "/llms-full.txt)\n", "## Optional\n"), "\n## Miner details\n"]
    for m in live:
        mm, cp, st = MODELS[m], MODEL_COPY[m], STATS[m]
        offers = "\n".join(f"  - {sname(o['seller'])}: {money(o['price'], o['currency'])}" + (f" (≈ {money(usd(o))})" if o["currency"] != "USD" and usd(o) else "")
                           + f", {STATUS[o['stock_status']].lower()}" for o in sort_offers(st["offers"]))
        tags = ", ".join(h1 for _, _, _, h1, members, _ in CATS if m in members)
        e = earn(m)
        est = (f"\nEstimate (changes with Bitcoin price and network difficulty): pool about {E.fmt_usd(e['pool']['usd_month_shown'])}/month before electricity; "
               f"power about {E.fmt_usd(e['power'])}/month at ${E.POWER_RATE:.2f}/kWh.") if e else ""
        noise = f"\nNoise: {NOISE[m][1]}." if m in NOISE else ""
        parts.append(f"\n### {SHORT[m]}\n{BASE}/models/{m}/\n{cp['intro']}\nBest for: {cp['who']}\nGood for: {tags}.{noise}{est}\nPrices:\n{offers}\n")
    (SITE / "llms-full.txt").write_text("".join(parts))


def guide_ld(path, headline, desc):
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline, "description": desc, "url": BASE + path,
            "datePublished": GUIDE_UPDATED, "dateModified": GUIDE_UPDATED, "image": f"{BASE}/og-image.png",
            "author": {"@type": "Organization", "name": "Bitaxe Radar", "url": BASE + "/"},
            "publisher": {"@type": "Organization", "name": "Bitaxe Radar", "url": BASE + "/"}}


def build_guide_heaters():
    path = "/guides/how-heater-miners-work/"
    trail = [("Home", "/"), ("Guides", "/guides/"), ("How heater miners work", path)]
    title = "How a Bitcoin heater miner works (plain English) | Bitaxe Radar"
    desc = "How a Bitcoin heater miner works: why a miner heats a room like a space heater, how pool mining offsets part of the power bill, and what to check first."
    ex = [m for m in ("avalon-nano-3s", "avalon-mini-3", "heatbit-maxi") if m in HOME_TRACKED]
    ex_rows = "".join(f'<tr><td><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num">≈{MODELS[m]["watts"]:,g} W</td><td class="num">≈{btu(MODELS[m]["watts"]):,.0f}</td></tr>' for m in ex)
    ex_tbl = (f'<div class="tablewrap"><table><thead><tr><th>Miner</th><th class="num">Stated power</th><th class="num">Heat (BTU/h)</th></tr></thead><tbody>{ex_rows}</tbody></table></div>'
              '<p class="hint">Heat = stated watts × 3.412, at full power.</p>') if ex else ""
    body = f"""<article>
<header class="hero"><h1>How a heater miner works</h1>
<p class="lede">The short version: a Bitcoin miner is a space heater that also does mining work. Here's what that means for your room and your power bill.</p>
<p class="meta">Updated <time datetime="{GUIDE_UPDATED}">Oct 21, 2026</time> · 2-minute read</p></header>
<section aria-labelledby="h-1"><h2 id="h-1">1. Electricity in, heat out</h2>
<p>A mining chip does billions of calculations a second, and nearly every watt it uses ends up as heat, just like an electric space heater. So a 1,000 W miner warms a room about as much as a 1,000 W heater.</p>
<p>A heater miner puts that chip in a quiet, room-friendly case with a fan, a thermostat or app, and heater-style modes. You run it when you want heat, and it mines while it does.</p>
{ex_tbl}</section>
<section aria-labelledby="h-2"><h2 id="h-2">2. Where the money comes from</h2>
<p>While it heats, the miner can earn bitcoin. There are two ways to run it:</p>
<ul><li><strong>Pool mining:</strong> you join thousands of other miners. The pool finds blocks often and pays you a small share for your work, minus a pool fee. You get small, steady payouts that knock part of the power bill back down.</li>
<li><strong>Solo mining:</strong> you try to find a whole block on your own. If you do, you get the full reward (about 3.125 BTC plus fees), but for one home miner that's a long-shot lottery, and most of the time you get nothing.</li></ul>
<p>Most heater-miner owners pool. <a href="/guides/solo-vs-pool-mining/">Solo vs pool, explained</a>.</p></section>
<section aria-labelledby="h-3"><h2 id="h-3">3. What it won't do</h2>
<ul><li><strong>It won't usually cover your whole power bill.</strong> Pool earnings rise and fall with Bitcoin's price and the network's total hashrate. Your electricity rate decides how much they offset. We don't show earnings promises.</li>
<li><strong>It's not the cheapest heat.</strong> A heat pump can move several units of heat for each unit of electricity, so it heats for less than any electric heater, miners included. Heater miners make the most sense in place of a plain electric heater.</li>
<li><strong>It's not free in summer.</strong> If you don't need the heat, you're paying for power just to mine.</li></ul></section>
<section aria-labelledby="h-4"><h2 id="h-4">4. Before you buy</h2>
<ul><li><strong>Size:</strong> about 300–800 W suits a small or medium room. 1,500 W-class units are like a full-size space heater on high.</li>
<li><strong>Circuit:</strong> a US 15 A, 120 V circuit should carry about 1,440 W continuously. Put big units on their own circuit, and follow the maker's guidance.</li>
<li><strong>Noise:</strong> fans are louder in high-heat modes. Check the stated decibels.</li>
<li><strong>Stock:</strong> many heater miners sell out before winter, and pre-orders ship later. Check the badge on each listing.</li></ul></section>
<section><h2>Compare heater miners</h2><p><a class="btn" href="/heater-miners/">See heater miners</a> <a class="btn ghost" href="/heat-calculator/">Which one fits my room?</a></p>
<p><a href="/guides/bitcoin-mining-heat-your-home/">Does it save money? Miner vs space heater vs heat pump →</a></p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, jsonld=[guide_ld(path, "How a Bitcoin heater miner works", desc)], lastmod=GUIDE_UPDATED, og_type="article")


def build_guide_pool():
    path = "/guides/solo-vs-pool-mining/"
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Solo vs pool mining", path)]
    title = "Solo vs pool mining, explained simply | Bitaxe Radar"
    desc = "Solo vs pool Bitcoin mining in plain words: solo is a lottery for a whole block, pool pays small steady amounts. Which suits a Bitaxe or a heater miner."
    ex = [m for m in ("bitaxe-gamma", "avalon-nano-3s", "avalon-mini-3", "avalon-q") if m in TRACKED]
    rows = "".join(f'<tr><td><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num">≈{MODELS[m]["hashrate_ths"]:g} TH/s</td><td class="num">~{sig2(lottery_years(m))} yrs</td></tr>' for m in ex)
    tbl = (f'<div class="tablewrap"><table><thead><tr><th>Miner</th><th class="num">Stated hashrate</th><th class="num">Avg. wait for a solo block</th></tr></thead><tbody>{rows}</tbody></table></div>'
           f'<p class="hint">Illustration only: assumes a network of {NETWORK_EH_ILLUSTRATION:,} EH/s (mempool.space showed {NETWORK_EH_SEEN} on Oct 21, 2026) and 144 blocks a day. '
           "It's an average: a block could come tomorrow or never, and the network keeps growing, which makes the odds worse.</p>") if ex else ""
    body = f"""<article>
<header class="hero"><h1>Solo vs pool mining</h1>
<p class="lede">Every miner, from a Bitaxe to a heater miner, can run one of two ways. One is a lottery ticket, the other is a small, steady paycheck.</p>
<p class="meta">Updated <time datetime="{GUIDE_UPDATED}">Oct 21, 2026</time> · 2-minute read</p></header>
<section aria-labelledby="h-s"><h2 id="h-s">Solo: the lottery</h2>
<p>Your miner tries to find the next Bitcoin block by itself. If it wins, you get the whole block reward, about 3.125 BTC plus fees. If it doesn't, you get nothing. For a home miner the odds are tiny, but small solo miners have won blocks, and that thrill is why many Bitaxe owners run solo.</p>
{tbl}</section>
<section aria-labelledby="h-p"><h2 id="h-p">Pool: the steady paycheck</h2>
<p>Thousands of miners combine their hashrate in a pool. The pool finds blocks regularly and splits each reward by how much work everyone did, minus a pool fee. You get small, regular payouts instead of all or nothing.</p>
<p>On average a pool pays about what solo mining would over a very long time, just smoothed out, minus the fee. Pool payouts move with Bitcoin's price and the network's total hashrate, so nobody can promise a fixed amount.</p></section>
<section aria-labelledby="h-w"><h2 id="h-w">Which should you pick?</h2>
<ul><li><strong>Bitaxe and other tiny miners:</strong> usually solo. A pool would pay them very little, so the long-shot is the fun part. <a href="/solo-miners/">Best for solo mining</a>.</li>
<li><strong>Heater miners:</strong> usually pool, so the heat you'd pay for anyway earns a little back. <a href="/pool-miners/">Best for pool mining</a> · <a href="/heater-miners/">Heater miners</a>.</li>
<li><strong>You can switch anytime.</strong> It's a setting in the miner (the pool address), not a different device.</li></ul></section>
<section><h2>Keep reading</h2><ul class="links"><li><a href="/guides/bitcoin-mining-pools/">Which mining pool should I use?</a></li><li><a href="/guides/how-heater-miners-work/">How a heater miner works</a></li><li><a href="/miners/">All miner prices</a></li><li><a href="/#miners">Bitaxe prices</a></li></ul>
<p class="hint">Not financial advice. Mining costs electricity, and earnings aren't guaranteed.</p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, jsonld=[guide_ld(path, "Solo vs pool mining, explained simply", desc)], lastmod=GUIDE_UPDATED, og_type="article")


def build_guide_worth():
    path = "/guides/is-home-mining-worth-it/"
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Is it worth it?", path)]
    title = "Is home Bitcoin mining worth it at your electricity price? | Bitaxe Radar"
    desc = "Is a home Bitcoin miner worth it? It depends on your power price. Plain answer with live break-even prices, the solo lottery and the heat offset."
    if not (NET and NET_OK):
        return
    ex = [m for m in ("bitaxe-gamma", "nerdqaxe-pp", "avalon-nano-3s", "hammer-thor-p2", "gekko-kbox-22", "avalon-mini-3", "avalon-q") if m in TRACKED]
    rows = "".join(f'<tr><td><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num">{E.fmt_usd(earn(m)["pool"]["usd_month_shown"])}</td>'
                   f'<td class="num" data-calc="power"{calc_attrs(m)}>{E.fmt_usd(earn(m)["power"])}</td>'
                   f'<td class="num net {net_cls(m)}" data-calc="netnum"{calc_attrs(m)}>{E.net_short(MODELS[m]["hashrate_ths"], mine_watts(m), NET)}</td>'
                   f'<td class="num">{E.fmt_rate(E.breakeven_rate(MODELS[m]["hashrate_ths"], mine_watts(m), NET))}</td></tr>' for m in ex)
    tbl = (f'<div class="tablewrap"><table class="calc-tbl"><thead><tr><th>Miner</th><th class="num">Pool /mo</th><th class="num">Power /mo</th><th class="num">Net /mo</th><th class="num">Break-even /kWh</th></tr></thead>'
           f'<tbody>{rows}</tbody></table></div>')
    g = "bitaxe-gamma" if "bitaxe-gamma" in TRACKED else ex[0]
    so = E.solo_odds(MODELS[g]["hashrate_ths"], NET)
    h = next((m for m in ("avalon-mini-3", "heatbit-maxi", "avalon-q") if m in TRACKED), None)
    heat_p = ""
    if h:
        heat_p = (f"<p>Example: the {esc(SHORT[h])} draws about {mine_watts(h):,g} W. An electric space heater of the same size would cost about "
                  f'<b data-calc="heat"{calc_attrs(h)}>{E.fmt_usd(E.heat_value_month(mine_watts(h)))}</b>/mo to run 24/7 at <span data-calc="rate">{E.fmt_rate(E.POWER_RATE)}</span>/kWh. '
                  f"The miner makes the same heat and its pool estimate is about {E.fmt_usd(earn(h)['pool']['usd_month_shown'])}/mo back. That's an estimate, and only real if you'd run electric heat anyway.</p>")
    faq = [("Is home Bitcoin mining worth it?", "Usually not for the money at typical US power prices. A small miner's pool estimate is often less than its power bill. It can make sense with very cheap power, as a heater you'd run anyway, or as a hobby and a solo lottery ticket."),
           ("What electricity price makes mining break even?", "It depends on the miner's efficiency. Each miner page shows a break-even power price; for the miners we track today it is roughly "
            f"${min(E.breakeven_rate(MODELS[m]['hashrate_ths'], mine_watts(m), NET) for m in ex):.2f} to ${max(E.breakeven_rate(MODELS[m]['hashrate_ths'], mine_watts(m), NET) for m in ex):.2f} per kWh, and it moves with Bitcoin's price and difficulty."),
           ("Does a heater miner save money?", "Only against electric resistance heat you'd use anyway. Then the power is heat you'd pay for regardless and the mining is a small rebate. A heat pump or gas heat is usually cheaper per unit of heat.")]
    body = f"""<article>
<header class="hero"><h1>Is home mining worth it?</h1>
<p class="lede">Short answer: for the money alone, usually not at typical US power prices. It depends on what you pay for electricity, and whether you want the heat or the lottery.</p>
<p class="meta">Updated <time datetime="{GUIDE_UPDATED}">Oct 21, 2026</time> · 2-minute read · live numbers</p>
{rate_box()}</header>
<section aria-labelledby="h-p"><h2 id="h-p">1. It depends on your power price</h2>
<p>A miner earns a little bitcoin and spends electricity all day. If the power costs more than the bitcoin is worth, you lose money each month. Type your price above and the table updates.</p>
{tbl}
<p class="hint">Pool estimate: share of the network × 144 blocks a day × the block reward, minus a 2% pool fee and a 10% safety margin, rounded down. Power runs 24/7 at full draw. {EARN_NOTE} Reddit commenters often quote about $0.06/kWh as a cut-off; the break-even column shows it varies by miner.</p>
<p><a href="/miners/#rate">Check every miner at your price →</a></p></section>
<section aria-labelledby="h-s"><h2 id="h-s">2. Solo mining is a lottery</h2>
<p>Run solo and a miner either finds a whole block, worth about {block_usd_text(so)} right now, or gets nothing. A {esc(SHORT[g])} has about a 1 in {E.fmt_big(so["one_in_year"])} chance a year. People do win, but plan on paying the power bill for a ticket, not for income. <a href="/guides/solo-vs-pool-mining/">Solo vs pool</a>.</p></section>
<section aria-labelledby="h-h"><h2 id="h-h">3. Heat changes the math</h2>
<p>A miner turns almost all its power into heat, like an electric space heater. If you'd heat a room with electric heat anyway, that power is a cost you'd have paid regardless, and the mining earns a little of it back.</p>
{heat_p}
<p><a href="/heater-miners/">Heater miners</a> · <a href="/best/heating-a-room/">Best for heating a room</a> · <a href="/guides/how-heater-miners-work/">How heater miners work</a> · <a href="/guides/bitcoin-mining-heat-your-home/">Mining to heat your home</a></p></section>
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{"".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)}</section>
<section><p class="hint">Not financial advice. Earnings aren't guaranteed and change with Bitcoin's price and network difficulty.</p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, jsonld=[guide_ld(path, "Is home Bitcoin mining worth it?", desc), faq_ld(faq)], lastmod=GUIDE_UPDATED, og_type="article")


# Solar guide (/guides/solar-bitcoin-mining/). Assumptions are stated on the page and sourced:
# NREL PVWatts default 14% system losses; US peak sun hours roughly 3 to 6.5 a day (we use 4 as a middle-of-the-road example);
# a 400 W panel as an example of a common modern residential panel. Watts are each miner's maker-stated figure.
SOLAR_PANEL_W = 400
SOLAR_SUN_HOURS = 4
SOLAR_LOSS = 0.14


def solar_panel_kwh_day():
    return SOLAR_PANEL_W * SOLAR_SUN_HOURS * (1 - SOLAR_LOSS) / 1000


def build_guide_solar():
    path = "/guides/solar-bitcoin-mining/"
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Solar mining", path)]
    title = "Can solar power a Bitcoin miner? Panels needed per miner | Bitaxe Radar"
    desc = "Can you run a Bitaxe or home Bitcoin miner on solar? Plain-words math: how many 400 W panels each miner needs, daytime-only vs batteries, and today's prices."
    pk = solar_panel_kwh_day()
    ex = [m for m in ("bitaxe-gamma", "nerdqaxe-pp", "avalon-nano-3s", "nmqaxe-nexus", "hammer-thor-p2", "avalon-mini-3", "heatbit-maxi", "avalon-q") if m in TRACKED]

    def price_cell(m):
        c = cheapest([o for o in offers_for(m) if in_stock(o)])
        return f'<a href="/models/{m}/">from ${usd(c):,.0f}</a>' if c else f'<a href="/models/{m}/">see shops</a>'
    rows = "".join(f'<tr><td><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num">≈{mine_watts(m):,g} W</td>'
                   f'<td class="num">{mine_watts(m) * 24 / 1000:,.1f}</td><td class="num">{max(1, math.ceil(mine_watts(m) * 24 / 1000 / pk)):,}</td>'
                   f'<td class="num">{price_cell(m)}</td></tr>' for m in ex)
    tbl = (f'<div class="tablewrap"><table><thead><tr><th>Miner</th><th class="num">Stated power</th><th class="num">kWh a day (24/7)</th>'
           f'<th class="num">400 W panels for 24/7*</th><th class="num">Price today</th></tr></thead><tbody>{rows}</tbody></table></div>'
           f'<p class="hint">*Example only: one {SOLAR_PANEL_W} W panel × {SOLAR_SUN_HOURS} peak sun hours × (1 − {SOLAR_LOSS:.0%} losses) ≈ {pk:.2f} kWh a day. '
           'Running 24/7 also needs a battery big enough to cover the night, and winter or cloudy days make less. Rounded up to whole panels. '
           'Prices are the cheapest in-stock listing we found, before shipping and tax.</p>')
    g = "bitaxe-gamma" if "bitaxe-gamma" in TRACKED else (ex[0] if ex else None)
    small = ""
    if g:
        small = (f"<p>A {esc(SHORT[g])} draws about {mine_watts(g):,g} W. That's tiny: a single {SOLAR_PANEL_W} W panel in full sun makes many times more than it needs. "
                 f"Over a whole day it uses about {mine_watts(g) * 24 / 1000:.1f} kWh, which one panel can cover on a decent day, as long as a battery carries it through the night.</p>")
    faq = [("Can a solar panel run a Bitaxe?", "Yes. A Bitaxe-class miner draws around 15 to 25 W, so one normal home panel makes more than enough in daylight. For night-time mining you need a battery and a charge controller or a small power station."),
           ("Can I mine only when the sun is out?", "Yes. A miner can be switched on and off, so daytime-only mining with no battery works. It just mines fewer hours, so it earns less and has lower solo odds than running 24/7."),
           ("Is solar mining free?", "Not quite. The panels and batteries cost money, and power you'd otherwise use in your home or sell back to the grid has value. Solar makes the most sense with spare power you can't use or sell for much."),
           ("How many panels does a big home miner need?", f"Roughly the miner's watts × 24 hours, divided by what one panel makes in a day. With our example of about {pk:.2f} kWh per {SOLAR_PANEL_W} W panel a day, a 500 W miner needs about 9 panels plus a battery to run around the clock.")]
    body = f"""<article>
<header class="hero"><h1>Can solar power a Bitcoin miner?</h1>
<p class="lede">Short answer: yes. Small miners like a Bitaxe need only one panel. Big heater-size miners need a whole roof, plus batteries if you want them running at night.</p>
<p class="meta">Updated <time datetime="2026-10-24">Oct 24, 2026</time> · 3-minute read · live prices</p></header>
<section aria-labelledby="h-1"><h2 id="h-1">1. The simple math</h2>
<p>Every miner draws a steady number of watts. Run it all day and it uses watts × 24 hours of energy. A solar panel makes its rated watts only in full sun, so what it makes in a day depends on how many hours of strong sun you get.</p>
<p>Solar people call that <strong>peak sun hours</strong>. Across the US it ranges from about 3 to 6.5 a day depending on where you live (see <a href="https://www.unboundsolar.com/solar-information/sun-hours-us-map" rel="nofollow noopener" target="_blank">this US sun-hours map</a>). Real systems also lose a bit to dust, wiring and shade. NREL's PVWatts calculator uses <a href="https://pvwatts.nlr.gov/docs/help_system_sysloss.php" rel="nofollow noopener" target="_blank">14% losses</a> by default.</p>
<p>So in our example, one {SOLAR_PANEL_W} W panel with {SOLAR_SUN_HOURS} peak sun hours makes about <strong>{pk:.2f} kWh a day</strong>.</p>
{tbl}</section>
<section aria-labelledby="h-2"><h2 id="h-2">2. Small miners: easy</h2>
{small}
<p>That makes a Bitaxe a fun first solar project: a panel, a small battery or power station, and a USB-C or 5 V supply. It's a solo lottery ticket powered by the sun. <a href="/solo-odds/">Check the solo odds</a>.</p></section>
<section aria-labelledby="h-3"><h2 id="h-3">3. Big miners: a roof's worth</h2>
<p>Heater-size miners draw hundreds of watts or more, so running one 24/7 takes many panels and a large battery. Most home solar owners with a big miner run it in the daytime only, when the panels make more than the house uses, instead of sending that power back to the grid for a low buy-back rate.</p>
<p>In winter the sun is weaker but you need heat anyway, so a <a href="/heater-miners/">heater miner</a> can still make sense on grid power. <a href="/guides/how-heater-miners-work/">How heater miners work</a> · <a href="/heat-calculator/">Room heat calculator</a>.</p></section>
<section aria-labelledby="h-4"><h2 id="h-4">4. Daytime only or 24/7?</h2>
<ul><li><strong>Daytime only:</strong> no battery, cheapest setup. The miner runs fewer hours, so it earns less and gets fewer solo chances.</li>
<li><strong>24/7 with a battery:</strong> more hours mining, but batteries cost money and lose some energy charging and discharging.</li>
<li><strong>Grid-tied panels:</strong> if you already have solar on the roof, the real question is what your spare power is worth. Compare it with the break-even power price on each <a href="/miners/">miner page</a>.</li></ul></section>
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{"".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)}</section>
<section><h2>Keep reading</h2><ul class="links"><li><a href="/guides/is-home-mining-worth-it/">Is home mining worth it?</a></li><li><a href="/price-per-th/">Most hashrate per dollar</a></li><li><a href="/miners/">All miner prices</a></li></ul>
<p class="hint">Not financial advice. These are rough examples; a solar installer or NREL's PVWatts calculator can estimate your own roof. Earnings aren't guaranteed.</p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, jsonld=[guide_ld(path, "Can solar power a Bitcoin miner?", desc), faq_ld(faq)], lastmod="2026-10-24", og_type="article")


# Heat-reuse guide (/guides/bitcoin-mining-heat-your-home/). The heat-pump comparison uses the US DOE's statement that modern
# air-source heat pumps cut electricity use for heating by about 50% vs electric resistance heat (energy.gov "Pump Up Your Savings
# with Heat Pumps"). So a heat pump makes the same heat for about half the power, and a heater miner (power cost minus its pool
# estimate) is cheaper only while the pool estimate is more than half its power bill: below 2 x its break-even power price.
HEAT_PUMP_POWER_SHARE = 0.5
HEAT_GUIDE_PATH = "/guides/bitcoin-mining-heat-your-home/"


def heat_pump_beat_rate(mid):
    """Power price ($/kWh) below which a heater miner's net heat cost is lower than a heat pump making the same heat."""
    return E.breakeven_rate(MODELS[mid]["hashrate_ths"], mine_watts(mid), NET) / HEAT_PUMP_POWER_SHARE


def build_guide_heat_home():
    if not (NET and NET_OK):
        return
    path = HEAT_GUIDE_PATH
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Heat your home", path)]
    title = "Mining Bitcoin to heat your home: does it save money? | Bitaxe Radar"
    desc = "Can a Bitcoin miner heat your home for less? Plain-words math with live numbers: miner vs space heater vs heat pump, and which heater miners fit."
    ex = [m for m in HEAT_SET if m in TRACKED]
    ex.sort(key=lambda m: mine_watts(m))

    def price_cell(m):
        c = cheapest([o for o in offers_for(m) if in_stock(o)])
        return f'<a href="/models/{m}/">from ${usd(c):,.0f}</a>' if c else f'<a href="/models/{m}/">see shops</a>'
    rows = "".join(f'<tr><td><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num">≈{btu(mine_watts(m)):,.0f}</td>'
                   f'<td class="num" data-calc="power"{calc_attrs(m)}>{E.fmt_usd(earn(m)["power"])}</td>'
                   f'<td class="num">{E.fmt_usd(earn(m)["pool"]["usd_month_shown"])}</td>'
                   f'<td class="num">{E.fmt_rate(heat_pump_beat_rate(m))}</td><td class="num">{price_cell(m)}</td></tr>' for m in ex)
    tbl = (f'<div class="tablewrap"><table class="calc-tbl"><thead><tr><th>Miner</th><th class="num">Heat (BTU/h)</th><th class="num">Power /mo</th>'
           f'<th class="num">Mining pays back /mo</th><th class="num">Beats a heat pump below</th><th class="num">Price today</th></tr></thead><tbody>{rows}</tbody></table></div>'
           f'<p class="hint">Running 24/7 at the stated mining watts. Heat = watts × 3.412. "Mining pays back" is the pool estimate, which changes with Bitcoin\'s price and network difficulty. '
           '"Beats a heat pump below" is the power price under which the miner\'s heat, after the mining payback, costs less than a heat pump making the same heat with about half the electricity. '
           'Prices are the cheapest in-stock listing we found, before shipping and tax.</p>') if ex else ""
    h = next((m for m in ("avalon-mini-3", "heatbit-maxi", "avalon-q") if m in ex), ex[0] if ex else None)
    worked = ""
    if h:
        e = earn(h)
        p, back = e["power"], e["pool"]["usd_month_shown"]
        worked = (f"<p>Take the {esc(SHORT[h])}. It mines at about {mine_watts(h):,g} W, so running it all month costs about "
                  f"<b>{E.fmt_usd(p)}</b> at {E.fmt_rate(E.POWER_RATE)}/kWh. "
                  f"{'An' if str(int(mine_watts(h)))[0] == '8' else 'A'} {mine_watts(h):,g} W space heater would cost the same and give the same heat. The miner also pays back about {E.fmt_usd(back)}/mo from pool mining, "
                  f"so your heat costs about {E.fmt_usd(max(0, p - back))}/mo instead of {E.fmt_usd(p)}.</p>")
    bw = ""
    if "heatbit-bitwater" in TRACKED:
        bw = (f'<p>Hot water is the other big heat bill. The <a href="/models/heatbit-bitwater/">Heatbit Bitwater</a> swaps the lower element in an electric tank water heater for mining chips, '
              "so the tank heats your water while it mines. It's a pre-order that Heatbit says ships in early 2027, and it only fits standard electric tank heaters.</p>")
    faq = [("Can a Bitcoin miner heat a room?", "Yes. Nearly every watt a miner uses comes out as heat, like an electric space heater, so a 1,000 W miner warms a room about as much as a 1,000 W heater."),
           ("Is a heater miner cheaper than a space heater?", "Usually a little. Both turn the same power into the same heat, and the miner also earns a small amount from pool mining, so your heat costs a bit less. How much depends on Bitcoin's price and the network."),
           ("Is a heater miner cheaper than a heat pump?", "Usually not at typical US power prices. The US Department of Energy says a modern heat pump uses about half the electricity of electric resistance heat for the same warmth. The table shows the power price below which each miner wins."),
           ("What about summer?", "If you don't need the heat, the power is just a mining cost. Most owners turn heater miners down or off in warm months, or run them only on cheap power.")]
    body = f"""<article>
<header class="hero"><h1>Mining to heat your home</h1>
<p class="lede">Short answer: a miner heats a room exactly like an electric space heater, and pays a little back while it does. It beats a plain space heater, but usually not a heat pump.</p>
<p class="meta">Updated <time datetime="2026-10-24">Oct 24, 2026</time> · 3-minute read · live numbers</p>
{rate_box()}</header>
<section aria-labelledby="h-1"><h2 id="h-1">1. The heat isn't wasted</h2>
<p>A mining chip turns almost all of its electricity into heat. In a data center that heat is a problem someone pays to blow away. In your home in winter, it's heat you'd pay for anyway. That's the whole idea: use one bill twice, once for warmth and once for mining.</p>
{worked}</section>
<section aria-labelledby="h-2"><h2 id="h-2">2. Heater miners side by side</h2>
<p>Type your power price above and the power column updates.</p>
{tbl}
<p><a href="/heat-calculator/">Which one fits my room?</a> · <a href="/heater-miners/">All heater miners</a></p></section>
<section aria-labelledby="h-3"><h2 id="h-3">3. What it beats, and what it doesn't</h2>
<ul><li><strong>Beats a plain electric space heater or baseboard heat:</strong> same power, same heat, plus the mining payback.</li>
<li><strong>Usually loses to a heat pump:</strong> a heat pump moves heat in from outside instead of making it, and the <a href="https://www.energy.gov/articles/pump-your-savings-heat-pumps" rel="nofollow noopener" target="_blank">US Department of Energy</a> says that cuts electricity for heating by about 50%. A miner only wins with cheap power, as the last column shows.</li>
<li><strong>Gas heat:</strong> depends on your gas and power prices. Compare your bills before switching.</li></ul></section>
<section aria-labelledby="h-4"><h2 id="h-4">4. Other ways to reuse the heat</h2>
{bw}
<ul><li><strong>Run it only in heating season:</strong> on in the cold months, down or off in summer, so you only pay for heat you want.</li>
<li><strong>Put it where you need warmth:</strong> a cold bedroom, a home office, a basement or a garage workshop.</li>
<li><strong>Use a thermostat or low mode:</strong> most heater miners can run cooler, so a big one won't overheat a small room.</li></ul></section>
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{"".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)}</section>
<section><h2>Keep reading</h2><ul class="links"><li><a href="/guides/how-heater-miners-work/">How a heater miner works</a></li><li><a href="/guides/solar-bitcoin-mining/">Can solar power a miner?</a></li><li><a href="/guides/is-home-mining-worth-it/">Is home mining worth it?</a></li><li><a href="/best/heating-a-room/">Best for heating a room</a></li></ul>
<p class="hint">Not financial advice. These are estimates; mining earnings aren't guaranteed and change with Bitcoin's price and network difficulty. Follow the maker's guidance on circuits and placement.</p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, jsonld=[guide_ld(path, "Mining Bitcoin to heat your home", desc), faq_ld(faq)], lastmod="2026-10-24", og_type="article")


# Pool guide (/guides/bitcoin-mining-pools/). Pool facts as published on each pool's own page, checked 2026-10-26:
# Public Pool web.public-pool.io ("NO FEES", Solo and PPLNS modes); solo.ckpool.org ("2% fee", solo, no registration);
# ocean.xyz ("2% fee, 1% fee for miners who make their own blocks using DATUM", TIDES, payout threshold 0.01048576 BTC);
# Braiins Academy rewards-and-payouts (FPPS, pool fee 2.5%, Lightning payouts from 1 sat, on-chain minimum 0.0002 BTC);
# Parasite Pool (1 BTC to the block finder, rest split by shares since the pool's last block, no fee, Lightning payouts)
# per CoinDesk, Apr 18 2026 (parasite.space itself is a JS app with no readable terms).
POOL_GUIDE_PATH = "/guides/bitcoin-mining-pools/"
POOLS_CHECKED = "2026-10-26"
OCEAN_THRESHOLD_BTC = 0.01048576
POOLS = [
    # name, url, type, fee text, how you get paid, best for
    ("Public Pool", "https://web.public-pool.io/", "Solo (also a shared mode)", "No fee",
     "Solo: if your miner finds a block, the reward goes straight to your Bitcoin address.", "Bitaxe-class solo miners who want zero fees"),
    ("Solo CKPool", "https://solo.ckpool.org/", "Solo", "2% of a block you find",
     "Only if your miner finds a block, paid to your address. No account needed.", "Solo miners who want a long-running service (since 2014)"),
    ("Parasite Pool", "https://parasite.space/", "Hybrid", "No fee",
     "The miner that finds a block gets 1 BTC. The rest is split by work done since the pool's last block, paid over Lightning.", "Small miners who want a lottery shot plus a share"),
    ("OCEAN", "https://ocean.xyz/", "Shared (TIDES)", "2% (1% with DATUM)",
     "Paid from blocks the pool finds, once you pass about 0.0105 BTC.", "Bigger miners who want payouts straight from the block"),
    ("Braiins Pool", "https://braiins.com/pool", "Shared (FPPS)", "2.5%",
     "Steady daily payouts whether or not the pool found a block. Lightning payouts from 1 sat.", "Heater and home miners who want small, steady sats"),
]


def build_guide_pools():
    if not (NET and NET_OK):
        return
    path = POOL_GUIDE_PATH
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Which pool?", path)]
    title = "Best Bitcoin mining pool for a Bitaxe or home miner (fees compared) | Bitaxe Radar"
    desc = "Which Bitcoin mining pool should a home miner use? Public Pool, CKPool, Parasite, OCEAN and Braiins compared: fees, payouts and live sats per miner."
    # data-label = column name shown above each value when the row becomes a card on phones (.pool-tbl in style.css)
    prow = "".join(f'<tr><td class="pool-name"><a href="{esc(u)}" rel="nofollow noopener" target="_blank">{esc(n)}</a></td><td data-label="Type">{esc(t)}</td>'
                   f'<td data-label="Fee">{esc(f)}</td><td class="pool-wide" data-label="How you get paid">{esc(how)}</td><td class="pool-wide" data-label="Good for">{esc(best)}</td></tr>'
                   for n, u, t, f, how, best in POOLS)
    ptbl = (f'<div class="tablewrap pool-wrap"><table class="pool-tbl"><thead><tr><th>Pool</th><th>Type</th><th>Fee</th><th>How you get paid</th><th>Good for</th></tr></thead><tbody>{prow}</tbody></table></div>'
            f'<p class="hint">Fees and payout rules as each pool states them on its own site, checked <time datetime="{POOLS_CHECKED}">Oct 26, 2026</time>. Parasite Pool\'s rules are as reported by CoinDesk (Apr 2026). Pools can change their terms, so check before you switch. Bitcoin only.</p>')
    ex = [m for m in ("bitaxe-gamma", "nerdqaxe-pp", "avalon-nano-3s", "avalon-mini-3", "avalon-q") if m in TRACKED]

    def sats(btc):
        s = btc * 1e8
        return f"{s:,.0f}" if s >= 100 else f"{s:.0f}"
    rows = []
    for m in ex:
        th = MODELS[m]["hashrate_ths"]
        fpps = E.pool_estimate(th, NET, fee=0.025)
        tides = E.pool_estimate(th, NET, fee=0.02)
        wait = E.fmt_wait(OCEAN_THRESHOLD_BTC / tides["btc_day"]) if tides["btc_day"] > 0 else "n/a"
        rows.append(f'<tr><td class="pool-name"><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num" data-label="Stated hashrate">≈{th:g} TH/s</td>'
                    f'<td class="num" data-label="Shared pool, per day">≈{sats(fpps["btc_day"])} sats</td><td class="num" data-label="To reach OCEAN\'s payout">{wait}</td>'
                    f'<td class="num" data-label="Avg. wait for a solo block">{E.fmt_wait(1 / E.solo_rate(th, NET))}</td></tr>')
    ltbl = (f'<div class="tablewrap pool-wrap"><table class="pool-tbl"><thead><tr><th>Miner</th><th class="num">Stated hashrate</th><th class="num">Shared pool, per day</th>'
            f'<th class="num">To reach OCEAN\'s payout</th><th class="num">Avg. wait for a solo block</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class="hint">Live estimate from mempool.space network data (BTC ≈ ${NET["btc_usd"]:,.0f}, network ≈ {NET["network_hashrate_hs"] / 1e18:,.0f} EH/s). '
            "Shared-pool sats use Braiins' 2.5% fee, the OCEAN column its 2% fee, both with a 10% safety margin, so real payouts can be a bit higher or lower and change every day. "
            "The solo wait is an average: a block could come tomorrow or never.</p>") if rows else ""
    g = "bitaxe-gamma" if "bitaxe-gamma" in TRACKED else (ex[0] if ex else None)
    gline = ""
    if g:
        so = E.solo_odds(MODELS[g]["hashrate_ths"], NET)
        gline = (f"<p>Example: a {esc(SHORT[g])} has about a 1 in {E.fmt_big(so['one_in_year'])} chance a year of finding a block. "
                 f"Solo, that win is the whole reward, about {block_usd_text(so)} minus any fee. On Parasite Pool the same win pays 1 BTC, "
                 "and each time the pool finds a block you also get a small share of it. Same odds, different prize.</p>")
    picks = []
    for m, why in (("bitaxe-gamma", "the usual first solo miner"), ("avalon-nano-3s", "a quiet desk miner and small heater"), ("avalon-mini-3", "a room heater that pool-mines")):
        if m in TRACKED and STATS[m]["best"]:
            o = STATS[m]["best"]
            picks.append(f'<li><p><a href="/models/{m}/"><b>{esc(SHORT[m])}</b></a>: {esc(why)}. From {money(o["price"], o["currency"])} at {esc(sname(o["seller"]))} today.</p>{offer_link(o, "Go to " + sname(o["seller"]) + " ↗", cls="btn ghost")}</li>')
    pick_sec = (f'<section aria-labelledby="h-buy"><h2 id="h-buy">Still picking a miner?</h2><ul class="pool-picks">{"".join(picks)}</ul>'
                '<p><a href="/solo-miners/">Best for solo</a> · <a href="/pool-miners/">Best for pool</a> · <a href="/find-my-miner/">Find my miner</a></p></section>') if picks else ""
    faq = [("What is the best mining pool for a Bitaxe?", "Most Bitaxe owners mine solo, because a shared pool pays a tiny miner only a few sats a day. Public Pool (no fee) and Solo CKPool (2% of a block you find) are the common solo picks. Parasite Pool is a middle ground: 1 BTC if your miner finds the block, plus a share of every block the pool finds."),
           ("Which pool should a heater miner use?", "Usually a shared pool, so the heat you'd pay for anyway earns a little back each day. An FPPS pool like Braiins pays daily whether or not it found a block. OCEAN pays from the blocks it finds, once you pass its payout threshold."),
           ("Does the pool change my chance of finding a block?", "No. Your chance depends on your miner's hashrate versus the whole network. The pool only decides how a block's reward is shared and what fee you pay."),
           ("Can I switch pools?", "Yes, anytime. It's a setting in your miner (the pool address and your Bitcoin address). Most miners also have a fallback pool setting in case the main one goes down."),
           ("Do I need an account?", "Not for Public Pool, Solo CKPool or OCEAN: you use your Bitcoin address as the username. Braiins Pool uses an account.")]
    body = f"""<article>
<header class="hero"><h1>Which mining pool should I use?</h1>
<p class="lede">Short answer: tiny miners like a Bitaxe usually go solo, heater miners usually join a shared pool, and a hybrid pool sits in between. Here's how the popular Bitcoin pools compare.</p>
<p class="meta">Updated <time datetime="{POOLS_CHECKED}">Oct 26, 2026</time> · 3-minute read · live numbers</p></header>
<section aria-labelledby="h-1"><h2 id="h-1">1. Three kinds of pool</h2>
<ul><li><strong>Solo:</strong> your miner works alone. Find a block and you keep the whole reward; otherwise you get nothing. A lottery ticket.</li>
<li><strong>Shared:</strong> thousands of miners split every block the pool finds, minus a fee. Small, steady payouts.</li>
<li><strong>Hybrid:</strong> the miner that finds a block gets a big prize, and everyone else shares the rest.</li></ul>
<p>The pool never changes your odds of finding a block. It only decides who gets paid what. <a href="/guides/solo-vs-pool-mining/">Solo vs pool, in plain words</a>.</p></section>
<section aria-labelledby="h-2"><h2 id="h-2">2. Popular pools side by side</h2>
{ptbl}</section>
<section aria-labelledby="h-3"><h2 id="h-3">3. What each choice means for your miner</h2>
<p>How many sats a shared pool would pay each miner, how long it takes to reach OCEAN's payout threshold, and the average wait for a solo block.</p>
{ltbl}
{gline}</section>
<section aria-labelledby="h-4"><h2 id="h-4">4. Which should you pick?</h2>
<ul><li><strong>Bitaxe or another tiny miner:</strong> solo on Public Pool or Solo CKPool, or Parasite Pool if you'd like a few sats along the way. A shared pool pays these miners only pennies.</li>
<li><strong>Desk miner (5–10 TH/s):</strong> either. Solo is still a long shot; a shared pool like Braiins pays a small amount every day over Lightning (see the table).</li>
<li><strong>Heater miner:</strong> a shared pool, so your heat earns a little back. Braiins for daily payouts, OCEAN if you're fine waiting for its threshold.</li></ul></section>
<section aria-labelledby="h-5"><h2 id="h-5">5. Safety tips</h2>
<ul><li><strong>Use your own Bitcoin address</strong> from a wallet you control. Never type in an address someone sends you.</li>
<li><strong>Set a fallback pool.</strong> New pools sometimes go offline, so give your miner a second pool to switch to.</li>
<li><strong>Watch for hidden fees in firmware.</strong> Some modified firmware on used miners sends part of your hashrate elsewhere. Stick to the maker's firmware or open-source builds.</li>
<li><strong>Be wary of "pools" that sell tokens or cloud contracts.</strong> A real Bitcoin pool just needs your miner and your address.</li></ul></section>
{pick_sec}
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{"".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)}</section>
<section><h2>Keep reading</h2><ul class="links"><li><a href="/solo-odds/">Solo odds calculator</a></li><li><a href="/solo-wins/">Recent solo block wins</a></li><li><a href="/guides/is-home-mining-worth-it/">Is home mining worth it?</a></li></ul>
<p class="hint">Not financial advice. We're not paid by any pool. Earnings aren't guaranteed and change with Bitcoin's price and network difficulty.</p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, jsonld=[guide_ld(path, "Which Bitcoin mining pool should I use?", desc), faq_ld(faq)], lastmod=POOLS_CHECKED, og_type="article")


# ---------------------------------------------------------------------------------------------
# Solo odds calculator (/solo-odds/) and solo wins feed (/solo-wins/). Odds use the same network inputs as earnings.py.
# Wins come from data/solo_wins.json (collector/solo_wins.py: mempool.space pool tags + SoloLuck.io's CC BY 4.0 record).
# ---------------------------------------------------------------------------------------------
def _load_wins():
    try:
        d = json.loads((ROOT / "data" / "solo_wins.json").read_text())
        return d, [w for w in d.get("wins", []) if w.get("time")]
    except Exception:
        return {}, []


SOLO_DATA, SOLO_WINS = _load_wins()
NOW = datetime.now(timezone.utc)
SOLO_CREDIT = ('Block list from <a href="https://mempool.space/mining">mempool.space</a> pool tags (Solo CKPool, Public Pool, Parasite, Braiins Solo, SoloPool.com). '
               'Extra solo blocks and reported miner details from SoloLuck.io, '
               '<a href="https://sololuck.io/legends">“The Solo Block Record”</a>, '
               '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.')


def fmt_date(iso):
    d = parse_t(iso)
    return f"{d:%b} {d.day}, {d.year}"


def fmt_hs(hs):
    for div, unit in ((1e15, "PH/s"), (1e12, "TH/s"), (1e9, "GH/s")):
        if hs >= div:
            return f"{float(f'{hs / div:.3g}'):g} {unit}"
    return f"{hs:,.0f} H/s"


def fmt_ths(th):
    return fmt_hs(th * 1e12)


def win_url(w):
    return f"https://mempool.space/block/{w.get('hash') or w['height']}"


def win_device(w):
    """(text, known) for the winning machine, from the winner's own public report only. Never guessed."""
    if w.get("rented"):
        return "Device: rented hashrate", True
    if w.get("hashrate_hs"):
        name = w.get("hardware") or "not named"
        return f'Device: {name} (≈{fmt_hs(w["hashrate_hs"])}, reported by winner)', True
    return "Device: unknown", False


def device_html(w):
    t, known = win_device(w)
    return f'<span class="dev{"" if known else " unk"}">{esc(t)}</span>'


def days_since(w):
    return max(0, (NOW - parse_t(w["time"])).days)


def size_match(mid):
    """Newest win whose publicly reported hashrate is within half to double this model's hashrate."""
    th = MODELS[mid]["hashrate_ths"]
    return next((w for w in SOLO_WINS if w.get("hashrate_hs") and not w.get("rented") and 0.5 <= w["hashrate_hs"] / 1e12 / th <= 2), None)


def solo_win_html(mid):
    if not SOLO_WINS:
        return ""
    w = SOLO_WINS[0]
    d = days_since(w)
    lines = [f'<p>Last solo block win: <b>{fmt_date(w["time"])}</b> ({plural(d, "day")} ago)<br>Pool: {esc(w["pool"])} · {device_html(w)}</p>']
    s = size_match(mid)
    if s:
        lines.append(f'<p>Last win by a miner this size: <b>{fmt_date(s["time"])}</b><br>Pool: {esc(s["pool"])} · {device_html(s)}</p>')
    th = MODELS[mid]["hashrate_ths"]
    return (f'<section class="solowin" aria-label="Solo block wins">{"".join(lines)}'
            f'<p class="hint"><a href="/solo-odds/?th={th:g}">Your solo odds</a> · <a href="/solo-wins/">All solo wins</a>'
            + (" · “This size” = winner-reported hashrate within 2× of this one." if s else "") + "</p></section>")


def wins_last_year():
    return [w for w in SOLO_WINS if NOW - parse_t(w["time"]) <= timedelta(days=365)]


def odds_tiles(th):
    rows, wait = E.solo_rows(th, NET)
    lab = {"day": "Per day", "year": "Per year", "5y": "Over 5 years"}
    t = "".join(f'<div class="etile"><small>{lab[k]}</small><b data-solo="{k}-in">{esc(one)}</b><span data-solo="{k}-pct">{esc(pct)}</span></div>' for k, pct, one in rows)
    t += f'<div class="etile"><small>Average wait</small><b data-solo="wait">{esc(wait.replace("about ", ""))}</b><span>for one block, on average</span></div>'
    return t


def build_solo_odds():
    if not NET:
        return
    path = "/solo-odds/"
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Solo odds calculator", path)]
    title = "Solo mining odds calculator: your chance of a Bitcoin block | Bitaxe Radar"
    desc = "Solo Bitcoin mining odds for any hashrate: your chance of a block per day, per year and over 5 years at today's network hashrate. Honest: it's a lottery."
    g = "bitaxe-gamma" if "bitaxe-gamma" in TRACKED else SOLO_SET[0]
    gth = MODELS[g]["hashrate_ths"]
    so = E.solo_odds(gth, NET)
    opts = "".join(f'<option value="{MODELS[m]["hashrate_ths"]:g}"{" selected" if m == g else ""}>{esc(SHORT[m])} ({fmt_ths(MODELS[m]["hashrate_ths"])})</option>'
                   for m in sorted(LIVE_TRACKED, key=lambda m: (MODELS[m]["hashrate_ths"], SHORT[m])))
    form = (f'<form class="solobox" id="solo-form" hidden><label for="solo-m">Pick a miner</label>'
            f'<select id="solo-m"><option value="">Your own hashrate</option>{opts}</select>'
            f'<label for="solo-h">or type your hashrate</label><span class="sin"><input id="solo-h" type="number" inputmode="decimal" min="0" step="any" value="{gth:g}">'
            '<select id="solo-u" aria-label="Unit"><option value="gh">GH/s</option><option value="th" selected>TH/s</option><option value="ph">PH/s</option></select></span></form>')
    ex = sorted([m for m in SOLO_SET if m in LIVE_TRACKED], key=lambda m: MODELS[m]["hashrate_ths"])
    rows = ""
    for m in ex:
        th = MODELS[m]["hashrate_ths"]
        r, wait = E.solo_rows(th, NET)
        rows += (f'<tr><td><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num">{fmt_ths(th)}</td><td class="num nw">{esc(r[1][2])}</td>'
                 f'<td class="num nw">{esc(wait.replace("about ", ""))}</td></tr>')
    tbl = (f'<div class="tablewrap"><table class="calc-tbl"><thead><tr><th>Miner</th><th class="num">Hashrate</th><th class="num">Chance per year</th>'
           f'<th class="num">Avg. wait</th></tr></thead><tbody>{rows}</tbody></table></div>')
    ly = wins_last_year()
    small = [w for w in SOLO_WINS if w.get("hashrate_hs") and not w.get("rented") and w["hashrate_hs"] <= 10e12]
    eh = NET["network_hashrate_hs"] / 1e18
    faq = [("What are my odds of solo mining a Bitcoin block?",
            f"Your share of the network's hashrate, times 144 blocks a day. With the network at about {eh:,.0f} EH/s, a {SHORT[g]} ({fmt_ths(gth)}) has about a 1 in {E.fmt_big(so['one_in_year'])} chance a year. Type your own hashrate above."),
           ("Has anyone actually won a block with a small miner?",
            f"Yes, rarely. Solo pools found {len(ly)} blocks in the past 12 months"
            + (f", and some winners reported small miners, for example ≈{fmt_hs(small[0]['hashrate_hs'])} on {fmt_date(small[0]['time'])}" if small else "")
            + ". Thousands of people solo mine, so a few lucky ones win while almost everyone wins nothing."),
           ("If I keep mining longer, am I due for a win?",
            "No. Every block is a fresh draw, and past attempts don't add up. The 5-year figure is the chance of at least one block in 5 years if the network stayed the same size. It usually grows, which makes the odds worse."),
           ("Is solo mining worth it?",
            "Not as income. Think of it as a lottery ticket you pay for with electricity. A tiny miner costs a few dollars a month to run, and the most likely result is no block at all."),
           ("Why do the odds change?",
            "They depend on the network's total hashrate, which changes daily as miners join or leave. Bitcoin's difficulty adjusts about every two weeks to keep blocks near 10 minutes apart.")]
    body = f"""<article>
<header class="hero"><h1>Solo odds calculator</h1>
<p class="lede">Your real chance of finding a whole Bitcoin block on your own. Plain truth first: solo mining is a lottery, and most solo miners never win.</p>
<p class="meta">Network ≈ {eh:,.0f} EH/s from mempool.space · updated {tag_time(NET["fetched_at"])}</p>
{form}</header>
<section class="earnbox" aria-labelledby="h-odds"><h2 id="h-odds">Chance of finding a block at <span data-solo="th">{fmt_ths(gth)}</span></h2>
<div class="etiles four">{odds_tiles(gth)}</div>
<p class="netline">A block pays about {block_usd_text(so)} right now (≈{E.block_btc(NET):.3f} BTC), all to the one miner who finds it.</p>
<p class="hint">The math: your share of the network's hashrate × 144 blocks a day. Assumes the network stays its current size. Odds, not a forecast. Not financial advice.</p></section>
<section aria-labelledby="h-ours"><h2 id="h-ours">Odds for the solo miners we track</h2>{tbl}
<p class="hint">Seller-stated hashrate. <a href="/solo-miners/">Prices for solo miners →</a></p></section>
<section aria-labelledby="h-wins"><h2 id="h-wins">People do win, sometimes</h2>
<p>{solo_wins_line()}</p><p><a class="btn ghost" href="/solo-wins/">See recent solo wins</a></p></section>
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{"".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)}
<p><a href="/guides/solo-vs-pool-mining/">Solo vs pool, in plain words</a> · <a href="/guides/is-home-mining-worth-it/">Is home mining worth it?</a></p></section>
</article>"""
    scripts = f'<script>window.RADAR_SOLO={json.dumps({"network_hashrate_hs": NET["network_hashrate_hs"]})};</script>\n<script src="/solo.js" defer></script>\n'
    app = {"@context": "https://schema.org", "@type": "WebApplication", "name": "Solo mining odds calculator", "url": BASE + path, "applicationCategory": "UtilitiesApplication",
           "operatingSystem": "Any", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "description": desc}
    layout(path, title, desc, body, crumbs=trail, jsonld=[app, faq_ld(faq)], scripts=scripts)


def solo_wins_line():
    if not SOLO_WINS:
        return "Solo blocks are rare: across all public solo pools, about one a month."
    w, n = SOLO_WINS[0], len(wins_last_year())
    return (f"The last solo block was found {plural(days_since(w), 'day')} ago, on {fmt_date(w['time'])} (pool: {esc(w['pool'])}). "
            f"Solo pools found {plural(n, 'block')} in the past 12 months, out of about 52,000.")


def build_solo_wins():
    if not SOLO_WINS:
        return
    path = "/solo-wins/"
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Solo wins", path)]
    w0, ly = SOLO_WINS[0], wins_last_year()
    title = f"Solo Bitcoin block wins: latest {fmt_date(w0['time'])} ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = (f"Recent Bitcoin blocks found by solo miners: {len(ly)} in the past 12 months. Last one {fmt_date(w0['time'])} on {w0['pool']}. Dates, pools, rewards and reported miners.")

    def li(w):
        rw = f'{w["reward_btc"]:.3f} BTC' if w.get("reward_btc") else ""
        return (f'<li><div class="wtop"><b>{fmt_date(w["time"])}</b><span>{rw}</span></div>'
                f'<div class="wpool">Pool: {esc(w["pool"])}</div><div class="wminer">{device_html(w)}</div>'
                f'<a href="{esc(win_url(w))}" rel="noopener">Block {w["height"]:,} on mempool.space ↗</a></li>')
    first, rest = SOLO_WINS[:20], SOLO_WINS[20:]
    since = SOLO_WINS[-1]
    body = f"""<article>
<header class="hero"><h1>Solo block wins</h1>
<p class="lede">Every Bitcoin block found by a solo miner gives the whole reward to one person. Here are the recent ones we know of.</p>
<p class="bigline"><b>{plural(days_since(w0), "day")}</b> since the last solo win ({fmt_date(w0["time"])}, pool: {esc(w0["pool"])})</p>
<p class="hint">Pool = the service the winner mined through. Device = the machine they used, if they shared it.</p>
<p class="meta">{plural(len(ly), "solo block")} in the past 12 months · checked {tag_time(SOLO_DATA.get("checked_at") or SOLO_DATA.get("fetched_at"))}</p></header>
<section aria-labelledby="h-list"><h2 id="h-list">Recent solo wins</h2>
<ul class="wins">{"".join(li(w) for w in first)}</ul>
{f'<details class="more"><summary>Older wins, back to {fmt_date(since["time"])}</summary><ul class="wins">{"".join(li(w) for w in rest)}</ul></details>' if rest else ""}
<p class="hint">Most winners never share their device, so it shows as unknown. We don't guess. Reward = block subsidy + fees.</p></section>
<section aria-labelledby="h-odds"><h2 id="h-odds">What are your odds?</h2>
<p>About 52,000 blocks are found a year and solo miners get only a handful. For one small miner it's a long-shot lottery.</p>
<p><a class="btn" href="/solo-odds/">Check your solo odds</a></p>
<p><a href="/solo-miners/">Best miners for solo mining</a> · <a href="/guides/solo-vs-pool-mining/">Solo vs pool</a></p></section>
<section><p class="hint">Data: {SOLO_CREDIT} Blocks since the April 2024 halving. Checked every 6 hours.</p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, lastmod=SOLO_DATA.get("fetched_at"))


# ---------------------------------------------------------------------------------------------
# Room heat calculator (/heat-calculator/). Mirrors site/heat.js (tests/test_heat_calc.py).
# ---------------------------------------------------------------------------------------------
HEAT_WPSF = {"good": 7, "average": 10, "poor": 13}     # rule-of-thumb watts of heat per sq ft (8 ft ceiling)
HEAT_FIT_LABEL = {"fits": "Can heat this room", "helps": "Adds warmth, won't heat it alone", "big": "More heat than this room needs",
                  "small": "Too small for this room"}


def heat_need(sqft, ins="average"):
    return sqft * HEAT_WPSF.get(ins, HEAT_WPSF["average"])


def heat_fit(heat_w, need_w):
    r = heat_w / need_w
    return "big" if r > 1.6 else "fits" if r >= 0.8 else "helps" if r >= 0.3 else "small"


def heat_rank(heat_w, need_w):
    return {"fits": 0, "helps": 1, "big": 2, "small": 3}[heat_fit(heat_w, need_w)] * 1e6 + abs(heat_w - need_w)


NOT_ROOM_HEAT = {"heatbit-bitwater"}   # heats a water tank, not the room


def heat_candidates():
    """Miners that give off enough heat to matter in a room (100 W+), with a price a shopper can see."""
    return [m for m in LIVE_TRACKED if draw_watts(m) >= 100 and show_price(m) is not None and m not in NOT_ROOM_HEAT]


def build_heat_calc():
    path = "/heat-calculator/"
    ms = heat_candidates()
    if not ms:
        return
    trail = [("Home", "/"), ("Guides", "/guides/"), ("Room heat calculator", path)]
    title = "Room heat calculator: which Bitcoin heater miner fits your room? | Bitaxe Radar"
    desc = "Type your room size and see how much heat it needs, and which heater and home Bitcoin miners can heat it, with today's prices."
    sq0, ins0 = 150, "average"
    n0 = heat_need(sq0, ins0)

    def li(m):
        hw, ft = draw_watts(m), heat_fit(draw_watts(m), n0)
        st = STATS[m]
        price = f"from {money(show_price(m))}" + ("" if st["best"] else " (pre-order)")
        return (f'<li data-w="{hw:g}"{" hidden" if ft == "small" else ""}><a class="hn" href="/models/{m}/">{esc(SHORT[m])}</a><span class="hp">{price}</span>'
                f'<span class="hs">≈{hw:,g} W · ≈{btu(hw):,.0f} BTU/h at full power</span><span class="fit f-{ft}">{esc(HEAT_FIT_LABEL[ft])}</span></li>')
    items = "".join(li(m) for m in sorted(ms, key=lambda m: heat_rank(draw_watts(m), n0)))
    form = ('<form class="solobox" id="heat-form" hidden><label for="heat-a">Room size</label>'
            f'<span class="sin"><input id="heat-a" type="number" inputmode="decimal" min="1" step="any" value="{sq0}">'
            '<select id="heat-u" aria-label="Unit"><option value="sqft" selected>sq ft</option><option value="m2">m²</option></select></span>'
            '<label for="heat-i">How well does the room hold heat?</label><select id="heat-i">'
            '<option value="good">Well (newer home, good windows)</option><option value="average" selected>Average</option>'
            '<option value="poor">Poorly (drafty, old windows, basement)</option></select></form>')
    faq = [("How much heat does a room need?",
            "A common rule of thumb for electric heat is about 10 watts per square foot for an average room with an 8-foot ceiling. "
            "Use less for a well-sealed room and more for a drafty one. It's a starting point, not an exact number."),
           ("Does a miner heat as well as a space heater?",
            "Yes, watt for watt. Nearly all the electricity a miner uses comes out as heat, like an electric space heater."),
           ("What if the miner gives more heat than my room needs?",
            "Most heater miners have lower power modes or a thermostat, so they can run cooler. At full power a big one will overheat a small room."),
           ("What does 1,500 W mean for my outlet?",
            "A US 15 A, 120 V circuit should carry about 1,440 W continuously. Put big units on their own circuit and follow the maker's guidance.")]
    body = f"""<article>
<header class="hero"><h1>Room heat calculator</h1>
<p class="lede">Type your room size. See how much heat it needs and which miners can warm it while they mine.</p>
{form}</header>
<section class="earnbox" aria-labelledby="h-need"><h2 id="h-need">Your room needs about <span data-heat="w">{n0:,.0f} W</span></h2>
<p class="netline">That's about <span data-heat="btu">{btu(n0):,.0f} BTU/h</span> of heat to keep it warm on a cold day.</p>
<p class="hint">Rule of thumb: about 10 W per sq ft for an average room with an 8 ft ceiling (7 W if it holds heat well, 13 W if it's drafty). An estimate, not a heating survey.</p></section>
<section aria-labelledby="h-fit"><h2 id="h-fit">Miners that fit</h2>
<ul class="heatlist" id="heat-list">{items}</ul>
<p id="heat-none" hidden>None of the miners we track give off enough heat for a room this big. Try a smaller room, or use a miner as a top-up next to your normal heat.</p>
<p class="hint">Heat = stated full-power watts × 3.412. Prices are before shipping and tax. <a href="/heater-miners/">All heater miners →</a></p></section>
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{"".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)}
<p><a href="/guides/how-heater-miners-work/">How heater miners work</a> · <a href="/best/heating-a-room/">Best for heating a room</a> · <a href="/guides/is-home-mining-worth-it/">Is home mining worth it?</a></p></section>
</article>"""
    app = {"@context": "https://schema.org", "@type": "WebApplication", "name": "Room heat calculator for Bitcoin heater miners", "url": BASE + path,
           "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "description": desc}
    layout(path, title, desc, body, crumbs=trail, jsonld=[app, faq_ld(faq)], scripts='<script src="/heat.js" defer></script>\n')

# ---------------------------------------------------------------------------------------------
# $/TH leaderboard (/price-per-th/): best value per stated TH/s, plus "is this a good price now?" from our own price log
# ---------------------------------------------------------------------------------------------
def model_price_low(mid):
    """Lowest in-stock USD price we have logged for this model at any tracked shop, and when tracking started.
    Non-USD points use today's conversion rate (same as the offer's current estimate)."""
    lo, lo_t, first = None, None, None
    for o in STATS[mid]["offers"]:
        rate = (usd(o) / o["price"]) if usd(o) and o["price"] else None
        if not rate:
            continue
        for pt in hist_pts(o["id"]):
            first = pt["t"] if first is None or pt["t"] < first else first
            if pt.get("in_stock") and pt.get("price"):
                v = pt["price"] * rate
                if lo is None or v < lo - 0.005:
                    lo, lo_t = v, pt["t"]
    return lo, lo_t, first


def price_check(mid):
    """(css class, short verdict) comparing today's cheapest in-stock price with the lowest we've logged."""
    b = STATS[mid]["best"]
    if not b:
        return "", "Not in stock"
    cur = usd(b)
    lo, lo_t, first = model_price_low(mid)
    if lo is None or first is None:
        return "", "New, no history yet"
    days = (GEN - parse_t(first)).days
    if days < 2:
        return "", f"Tracking since {fmt_day(first)}"
    if cur <= lo + 0.01:
        return "pc-low", f"Lowest since {fmt_day(first)}"
    pct = (cur / lo - 1) * 100
    if pct <= 5:
        return "pc-near", f"Within {max(pct, 1):.0f}% of our low ({money(lo)})"
    return "pc-high", f"{pct:.0f}% above our low of {money(lo)} ({fmt_day(lo_t)})"


def new_lows_box():
    """'New lows this week' on /price-per-th/: miners whose cheapest in-stock price fell below every in-stock price we logged before, and still is."""
    lows = newlows.new_lows(MODELS, OFFERS, history, GEN, days=7, live=LIVE_TRACKED)
    if not lows:
        return ('<section aria-labelledby="h-lows" class="newlows"><h2 id="h-lows">New lows this week</h2>'
                '<p>No miner hit a new low price in the last 7 days. We check every 6 hours.</p></section>')
    items = []
    for d in lows:
        c = d["current"]
        how = "Price dropped" if d["kind"] == "drop" else "Back in stock"
        items.append(f'<li><a href="/models/{d["model"]}/"><b>{esc(SHORT[d["model"]])}</b></a> {"≈ " if c["currency"] != "USD" else ""}<b>{money(usd(c))}</b> at {esc(sname(c["seller"]))}. '
                     f'{how} {esc(fmt_day(d["t"]))}, {money(d["old_low"] - usd(c))} under our previous low of {money(d["old_low"])}. {offer_link(c, "View ↗", cls="lnk")}</li>')
    return (f'<section aria-labelledby="h-lows" class="newlows"><h2 id="h-lows">New lows this week</h2><ul>{"".join(items)}</ul>'
            '<p class="hint">Compared with the lowest in-stock price we have logged for that miner at any shop we track. Shown only while the price is still that low.</p></section>')


PTH_GROUPS = [("bitaxe", "Bitaxe and open-source miners", "Small boards and desk miners, mostly bought as a solo lottery ticket."),
              ("home", "Home, heater and bigger miners", "Finished boxes, heaters and 10 TH/s+ home miners.")]


def build_price_per_th():
    path = "/price-per-th/"
    trail = [("Home", "/"), ("Deals", "/deals/"), ("Price per TH/s", path)]
    groups = {"bitaxe": [m for m in BITAXE_TRACKED if m in LIVE_TRACKED], "home": [m for m in HOME_TRACKED if m in LIVE_TRACKED]}
    ranked_all, sections = [], []
    for key, h2, sub in PTH_GROUPS:
        ms = sorted([m for m in groups[key] if STATS[m]["per_th"]], key=lambda m: STATS[m]["per_th"])
        if not ms:
            continue
        ranked_all += ms
        rows = []
        for i, mid in enumerate(ms, 1):
            st, b = STATS[mid], STATS[mid]["best"]
            cls, verdict = price_check(mid)
            rows.append(f'<tr><td class="num">{i}</td><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a><br><small>≈{MODELS[mid]["hashrate_ths"]:g} TH/s · ≈{MODELS[mid]["watts"]:,g} W</small></td>'
                        f'<td class="num"><b>{money(st["per_th"])}</b></td><td class="num">{"≈ " if b["currency"] != "USD" else ""}{money(usd(b))}<br><small>{esc(sname(b["seller"]))}</small></td>'
                        f'<td class="num">≈{jth(mid):.1f}</td><td><span class="pc {cls}">{esc(verdict)}</span></td><td>{offer_link(b, "View ↗")}</td></tr>')
        sections.append(f'<section aria-labelledby="h-{key}"><h2 id="h-{key}">{esc(h2)}</h2><p class="hint">{esc(sub)}</p>'
                        '<div class="tablewrap"><table><thead><tr><th class="num">#</th><th>Miner</th><th class="num">$ per TH/s</th><th class="num">Cheapest in stock</th>'
                        f'<th class="num">J/TH</th><th>Price check</th><th>Buy</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')
    pre = sorted([m for m in LIVE_TRACKED if not STATS[m]["best"] and show_price(m) is not None], key=lambda m: show_price(m) / MODELS[m]["hashrate_ths"])
    pre_rows = "".join(f'<tr><td><a href="/models/{m}/">{esc(SHORT[m])}</a></td><td class="num">{money(show_price(m) / MODELS[m]["hashrate_ths"])}</td>'
                       f'<td class="num">{money(show_price(m))}</td><td class="num">≈{jth(m):.1f}</td><td>{badge(STATS[m]["low_any"]["stock_status"])}</td></tr>' for m in pre)
    pre_html = (f'<section aria-labelledby="h-pre"><h2 id="h-pre">Pre-order and sold out</h2><p class="hint">Not in stock, so not ranked. The price per TH/s uses the lowest listed price.</p>'
                '<div class="tablewrap"><table><thead><tr><th>Miner</th><th class="num">$ per TH/s</th><th class="num">Lowest listed</th><th class="num">J/TH</th><th>Status</th></tr></thead>'
                f'<tbody>{pre_rows}</tbody></table></div></section>') if pre else ""
    top = {k: next((m for m in ranked_all if m in groups[k]), None) for k in groups}
    first_t = min((p["t"] for pts in history.values() for p in pts), default=latest["generated_at"])
    lead = " ".join(f"Best value {lbl}: <strong>{esc(SHORT[m])}</strong> at {money(STATS[m]['per_th'])} per TH/s." for k, lbl in (("bitaxe", "small miner"), ("home", "home miner")) if (m := top.get(k)))
    faq = [("What does price per TH/s mean?",
            "The price you pay for each terahash per second of mining power: today's cheapest in-stock price divided by the hashrate the maker states. Lower means more hashrate for your money."),
           ("Is the cheapest price per TH/s always the best buy?",
            "Not always. J/TH (power per terahash) decides your electricity bill, which over a year can cost more than the miner. Noise, heat and size matter too. A cheap-per-TH miner that is loud or power hungry may not suit a bedroom."),
           ("How do you know if a price is good right now?",
            f"We log every tracked listing's price and stock about every 6 hours since {fmt_day(first_t)}. Price check compares today's cheapest in-stock price with the lowest in-stock price we have logged for that miner at any tracked shop. Our history is short, so it can't say whether a price is low for the year."),
           ("Do you include shipping and tax?",
            "No. Prices are before shipping, tax and import fees. Euro and Canadian-dollar prices are converted to US dollars as an estimate.")]
    body = f"""<article>
<header class="hero"><h1>Price per TH/s leaderboard</h1>
{deal_pills(path)}
{bf_banner()}
<p class="lede">Which miners give you the most hashrate per dollar today, and whether today's price is a good one.</p>
<p>{lead}</p>
<p class="meta">Checked {tag_time(latest['generated_at'])} · updated every 6 hours · hashrate is the maker's stated figure</p></header>
{new_lows_box()}
{"".join(sections)}
{pre_html}
<section aria-labelledby="h-faq"><h2 id="h-faq">Questions</h2>{"".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)}</section>
<section><h2>Related</h2><p><a href="/deals/">Best deals</a> · <a href="/in-stock/">In stock now</a> · <a href="/find-my-miner/">Find my miner</a> · <a href="/guides/is-home-mining-worth-it/">Is home mining worth it?</a> · <a href="/alerts/">Price alerts</a></p></section>
</article>"""
    title = f"Bitcoin miner price per TH/s: best value home miners ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = "Home Bitcoin miners ranked by price per TH/s at today's cheapest in-stock price, with J/TH and a price check against our own price log."
    items = [(SHORT[m], f"/models/{m}/") for m in ranked_all]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Bitcoin miners ranked by price per TH/s", items), faq_ld(faq)])



def build_method():
    path = "/how-we-track/"
    trail = [("Home", "/"), ("About & how we track", path)]
    src_rows = "".join(f'<tr><td><a href="/sellers/{sid}/">{esc(s["name"])}</a></td><td>{esc(s["currency"])}</td><td>{esc(SELLER_COPY.get(sid, {}).get("region", ""))}</td></tr>' for sid, s in SELLERS.items())
    title = "How Bitaxe Radar tracks prices and stock (methodology) | Bitaxe Radar"
    desc = "How Bitaxe Radar collects Bitaxe and NerdQaxe prices and stock: sources, schedule, currency conversion, history, which sellers we list and affiliate income."
    body = f"""<article>
<header class="hero"><h1>About Bitaxe Radar</h1>
<p class="lede">We check the shops that sell Bitaxe-style miners and heater and home miners every 6 hours, and show you who has each one in stock and for how much.</p></header>
<section><h2>Where the prices come from</h2>
<p>Straight from each shop's own product pages. We show the price and stock status the shop itself reports, and link you to that page so you can check it. Last check: {tag_time(latest['generated_at'])}.</p>
<div class="tablewrap"><table><thead><tr><th>Shop</th><th>Currency</th><th>Pricing</th></tr></thead><tbody>{src_rows}</tbody></table></div></section>
<section><h2>What a price means</h2><ul>
<li>The shop's listed price for the bundle shown, <strong>before</strong> shipping, import duties and (unless noted) tax.</li>
<li>Euro and Canadian-dollar prices are converted to US dollars at the ECB reference rates (€1 = ${esc(FX.get('EUR_USD', 'n/a'))}, CA$1 = ${esc(FX.get('CAD_USD', 'n/a'))} on {esc(FX.get('date', ''))}), so treat them as estimates.</li>
<li>Bundles differ (power supply, stand, fan, revision). We note what's included when the shop says so.</li>
<li>Hashrate and power are the shop's stated figures, not our own measurements.</li></ul></section>
<section><h2>What "in stock" means</h2><p>Only listings the shop says are available now. Pre-orders and backorders are labelled separately because they ship later. Stock can change within minutes, so always confirm on the shop's page.</p></section>
<section><h2>Price history</h2><p>We log a point whenever a price or stock status changes, and about once a day otherwise. Charts start when we started tracking; nothing is filled in after the fact.</p></section>
<section><h2>Which shops we list</h2><p>Shops with real stock, consistent prices and normal payment methods. We leave out shops we can't vet, like ones with prices far below everyone else or wire/crypto-only payment.</p></section>
<section><h2>How Bitaxe Radar earns money</h2>
<p>Some shop links are affiliate links: if you buy through one, we may earn a commission at no extra cost to you. They're labelled "affiliate link" and never change prices, rankings or sort order. Any sponsored placement is clearly labelled (see <a href="/advertise/">advertise</a>).</p>
<p>We don't publish ratings or reviews, because we haven't tested the hardware, and nothing here is financial advice. Solo mining with a small miner is a lottery: once you count electricity, you should expect to lose money.</p></section>
<section><h2>Spotted a mistake?</h2><p>Write to <a href="mailto:{CONTACT}">{CONTACT}</a>. Shops can ask us to correct a listing the same way.</p></section>
</article>"""
    ld = {"@context": "https://schema.org", "@type": "AboutPage", "name": "How Bitaxe Radar tracks prices and stock", "url": BASE + path, "dateModified": METHODOLOGY_UPDATED}
    layout(path, title, desc, body, crumbs=trail, jsonld=[ld], lastmod=METHODOLOGY_UPDATED)


def build_advertise():
    path = "/advertise/"
    trail = [("Home", "/"), ("Advertise", path)]
    n_models = N_MODELS
    mail = f"mailto:{CONTACT}?subject=" + "Sponsor%20spot%20on%20Bitaxe%20Radar"
    title = "Advertise on Bitaxe Radar: sponsor spots for Bitaxe sellers | Bitaxe Radar"
    desc = "Sponsor spots on Bitaxe Radar, the price and stock tracker for Bitaxe and NerdQaxe miners. For sellers, builders and accessory makers. Always labelled."
    body = f"""<article>
<header class="hero"><h1>Advertise on Bitaxe Radar</h1>
<p class="lede">People come to Bitaxe Radar when they're deciding where to buy a miner. That's the moment you want your shop in front of them.</p>
<p><a class="btn" href="{esc(mail)}">Email {CONTACT}</a></p></header>
<section><h2>What is available</h2><ul>
<li><strong>Featured shop spot</strong> on our {n_models} miner pages, right under the price table, labelled "Sponsor".</li>
<li><strong>Accessory spot</strong> for stands, cases, heatsinks, fans and power supplies.</li>
<li><strong>Get listed in the tracker</strong>: if you sell Bitaxe-class miners and we don't track you yet, write to us. Being listed in the price table is free and never paid for.</li></ul></section>
<section><h2>The rules</h2><ul>
<li>Every sponsored placement is clearly labelled and uses rel="sponsored" links.</li>
<li>Sponsors never change price rankings, sort order or stock data. The cheapest in-stock listing is always shown first.</li>
<li>We only take sponsors we would be comfortable sending readers to (real stock, consistent prices, normal payment methods).</li></ul></section>
<section><h2>Stats and pricing</h2><p>Contact us for current stats and rates. Early sponsors get introductory pricing.</p>
<p><a class="btn" href="{esc(mail)}">Email {CONTACT}</a></p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, lastmod=METHODOLOGY_UPDATED)


def build_404():
    body = '<article><header class="hero"><h1>Page not found</h1><p class="lede">That page does not exist. Try the <a href="/">home page</a>, <a href="/in-stock/">what is in stock now</a> or <a href="/where-to-buy-bitaxe/">where to buy</a>.</p></header></article>'
    layout("/404.html", "Page not found | Bitaxe Radar", "This page does not exist on Bitaxe Radar.", body, noindex=True, index_in_sitemap=False)


# ---------------------------------------------------------------------------------------------
# HOME PAGE (template + pre-rendered summary)
# ---------------------------------------------------------------------------------------------
HOME_TIERS = [(0, 1.5), (1.5, 2), (2, 3), (3, 5), (5, 9), (9, 1e9)]   # TH/s size bands, one pick each


def pick_price(mid):
    """Offer a home card shows: the cheapest US-dollar listing in stock, else the cheapest anywhere."""
    st = STATS[mid]
    return st["best_usd"] or st["best"]


def home_picks():
    """One Bitaxe-class desk miner (no heaters or boxed home miners) per size band by best $/TH, US shops first; never two with the same hashrate and watts."""
    cands = [m for m in LIVE_TRACKED if m not in NOINDEX_MODELS and MODELS[m].get("category") != "home" and pick_price(m)]
    def key(m):
        o = pick_price(m)
        return (o["currency"] != "USD", usd(o) / MODELS[m]["hashrate_ths"], usd(o))
    seen, uniq = set(), []
    for m in sorted(cands, key=key):
        spec = (MODELS[m]["hashrate_ths"], MODELS[m]["watts"])
        if spec not in seen:
            seen.add(spec)
            uniq.append(m)
    picks = []
    for lo, hi in HOME_TIERS:
        tier = [m for m in uniq if lo <= MODELS[m]["hashrate_ths"] < hi]
        if tier:
            picks.append(min(tier, key=key))
    return sorted(picks, key=lambda m: (pick_price(m)["currency"] != "USD", MODELS[m]["hashrate_ths"]))


def home_card(mid, best_value):
    st, m = STATS[mid], MODELS[mid]
    b = pick_price(mid)
    ribbon = '<span class="ribbon" title="Most hashrate per dollar">Best value</span>' if mid == best_value else ""
    if b:
        eu = b["currency"] != "USD"
        price = (f'{"≈ " if eu else ""}{money(usd(b))}' + ('<small>EU shop</small>' if eu else ""))
        where = f'at {esc(sname(b["seller"]))}' + (f' · in stock at {plural(len(st["in_stock"]), "shop")}' if len(st["in_stock"]) > 1 else "")
        status, cls = badge("in_stock"), "card"
    else:
        low = st["low_any"]
        price = "Sold out"
        where = f'Last listed {money(usd(low))}' if low else ""
        status, cls = '<span class="badge b-out_of_stock">Sold out</span>', "card soldout"
    return (f'<article class="{cls}">{ribbon}<div class="art{" photo" if mid in MODEL_IMG else ""}">{model_img(mid)}</div><div class="body">'
            f'<h3><a href="/models/{mid}/">{esc(SHORT[mid])}</a></h3>'
            f'<div class="spec">≈{m["hashrate_ths"]:g} TH/s · ≈{m["watts"]:g} W</div>'
            f'<div class="price">{price}</div><div class="where">{where}</div>{earn_line(mid)}'
            f'<div class="row">{status}<a class="btn sm" href="/models/{mid}/" aria-label="See {esc(SHORT[mid])} prices">See prices</a></div>'
            "</div></article>")


def build_home():
    tpl = (ROOT / "templates" / "home.html").read_text().replace("<!--N-SHOPS-->", str(len(SELLERS))).replace("<!--N-MODELS-->", str(N_MODELS))
    t = re.search(r"<title>(.*?)</title>", tpl, re.S).group(1)
    d = re.search(r'<meta name="description" content="(.*?)">', tpl, re.S).group(1)
    items = [(SHORT[m], f"/models/{m}/") for m in home_picks()]
    head = f"""<link rel="canonical" href="{BASE}/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta property="og:site_name" content="Bitaxe Radar"><meta property="og:type" content="website">
<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">
<meta property="og:url" content="{BASE}/"><meta property="og:image" content="{BASE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
{jsonld_tag({"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "@id": BASE + "/#org", "name": "Bitaxe Radar", "url": BASE + "/", "email": CONTACT},
    {"@type": "WebSite", "@id": BASE + "/#site", "name": "Bitaxe Radar", "url": BASE + "/", "publisher": {"@id": BASE + "/#org"}}]})}
{jsonld_tag(itemlist("Bitaxe-class miners tracked by Bitaxe Radar", items))}"""
    ins = [o for o in OFFERS if in_stock(o)]
    chips = (f'<ul class="chips"><li class="live"><strong>{len(ins)}</strong> listings in stock</li>'
             f'<li><strong>{N_MODELS}</strong> miners tracked</li><li><strong>{len(SELLERS)}</strong> shops checked</li>'
             f'<li>Updated <time id="freshness" datetime="{esc(latest["generated_at"])}">{esc(fmt_time(latest["generated_at"]))}</time></li></ul>')
    picks = home_picks()
    best_value = min(picks, key=lambda m: usd(pick_price(m)) / MODELS[m]["hashrate_ths"], default=None)
    older = [m for m in TRACKED if m in NOINDEX_MODELS]
    older_html = ('<p class="older">Older models: ' + " · ".join(
        f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' + (f' from {money(usd(STATS[m]["best"]))}' if STATS[m]["best"] else " (sold out)") for m in older) + "</p>") if older else ""
    cards = f"""<section id="miners" aria-labelledby="h-miners">
    <div class="sec-head"><h2 id="h-miners">Today's best prices</h2><a href="/in-stock/">Everything in stock →</a></div>
    <p class="hint">The best price per TH/s in each size, from today's in-stock listings. US shops first.</p>
    <div class="cards">{"".join(home_card(m, best_value) for m in picks)}</div>
    {older_html}
    <p class="older">Want one that heats a room too? <a href="/heater-miners/">See heater miners →</a></p>
  </section>"""
    compare_links = '<ul class="links">' + "".join(f'<li><a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a></li>' for a, b in COMPARE_PAIRS) + "</ul>"
    sellers_line = ('<p>Shops we check: ' + " · ".join(f'<a href="/sellers/{sid}/">{esc(s["name"])}</a>' for sid, s in SELLERS.items() if sid in SELLER_COPY) + "</p>\n  ")
    out = (tpl.replace("<!--HEAD-->", head).replace("<!--HEADER-->", header_html()).replace("<!--RADAR-BG-->", RADAR_BG)
           .replace("<!--HERO-CHIPS-->", chips).replace("<!--BROWSE-->", bf_banner() + browse_tiles() + "\n" + best_pills()).replace("<!--CARDS-->", cards).replace("<!--SIGNUP-->", signup_html("any"))
           .replace("<!--COMPARE-LINKS-->", compare_links).replace("<!--FOOTER-->", footer_html())
           .replace('<script src="/app.js"></script>', '<script src="/app.js"></script>\n' + SIGNUP_SCRIPTS)
           .replace("</body>", ANALYTICS + "</body>"))
    assert "<!--" not in out, "unfilled placeholder in home template"
    (SITE / "index.html").write_text(out)
    PAGES.append(dict(path="/", lastmod=latest["generated_at"]))


# ---------------------------------------------------------------------------------------------
# sitemap, robots
# ---------------------------------------------------------------------------------------------
def write_sitemap():
    PAGES.sort(key=lambda p: (p["path"] != "/", p["path"]))
    urls = "".join(f"  <url><loc>{BASE}{p['path']}</loc><lastmod>{p['lastmod']}</lastmod></url>\n" for p in PAGES)
    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\n# Plain-text site summary for AI assistants: {BASE}/llms.txt (full: {BASE}/llms-full.txt)\nSitemap: {BASE}/sitemap.xml\n")


# ---------------------------------------------------------------------------------------------
# NAVIGATION BUILD (docs/NAV_AUDIT.md): /miners/ with filters, /find-my-miner/ quiz, /alerts/,
# index pages for /models/ /sellers/ /best/ /guides/ /compare/, and /home-miners/ -> /miners/.
# ---------------------------------------------------------------------------------------------
CAT_CRUMB = {"solo": ("Solo miners", "/solo-miners/"), "pool": ("Pool miners", "/pool-miners/"), "heat": ("Heater miners", "/heater-miners/")}


def primary_cat(mid):
    if mid in HEAT_SET and mid not in SOLO_SET:
        return "heat"
    if mid in SOLO_SET:
        return "solo"
    if mid in POOL_SET:
        return "pool"
    return None


def model_trail(mid, short, path):
    c = primary_cat(mid)
    return [("Home", "/"), ("All miners", "/miners/")] + ([CAT_CRUMB[c]] if c else []) + [(short, path)]


def show_price(mid):
    """USD price a shopper would see on the card: cheapest in stock, else cheapest pre-order/backorder, else None."""
    st = STATS[mid]
    if st["best"]:
        return usd(st["best"])
    pre = [usd(o) for o in st["offers"] if o["stock_status"] in ("preorder", "backorder") and usd(o) is not None]
    return min(pre) if pre else None


def card_data(mid):
    st, m = STATS[mid], MODELS[mid]
    types = " ".join(k for k, _, _, _, members, _ in CATS if mid in members)
    p = show_price(mid)
    stock = 2 if st["best"] else 1 if p is not None else 0
    noise = NOISE[mid][0] if mid in NOISE else ""
    return (f' data-mid="{mid}" data-type="{types}" data-price="{"" if p is None else round(p, 2)}" data-w="{m["watts"]:g}" '
            f'data-hw="{m.get("heat_watts", m["watts"]):g}" data-th="{m["hashrate_ths"]:g}" data-stock="{stock}" data-db="{noise}"')


def miners_sorted():
    return sorted(LIVE_TRACKED, key=card_sort_key)


FILTERS = [("type", "Type", [("", "All"), ("solo", "Solo"), ("pool", "Pool"), ("heat", "Heater")]),
           ("price", "Price", [("", "Any"), ("0-100", "Under $100"), ("100-300", "$100–300"), ("300-1000", "$300–1,000"), ("1000-", "$1,000+")]),
           ("power", "Power", [("", "Any"), ("0-100", "Under 100 W"), ("100-500", "100–500 W"), ("500-", "500 W+")])]

MINERS_JS = """<script>
(function(){
var f=document.getElementById('mf'),grid=document.getElementById('grid'),n=document.getElementById('mcount');if(!f||!grid)return;
f.hidden=false;[].forEach.call(document.querySelectorAll('.nojs'),function(e){e.hidden=true;});var cards=[].slice.call(grid.children),q=new URLSearchParams(location.search);
['type','price','power','sort'].forEach(function(k){var v=q.get(k);if(v===null)return;var el=f.querySelector('[name="'+k+'"][value="'+v+'"]')||(k==='sort'&&f.elements.sort);if(el){if(el.tagName==='SELECT')el.value=v;else el.checked=true;}});
if(q.get('stock')==='1')f.elements.stock.checked=true;
function rng(v,x){if(!v)return true;if(x==='')return false;var p=v.split('-');x=+x;return x>=+p[0]&&(p[1]===''||x<+p[1]);}
function val(k){var el=f.querySelector('[name="'+k+'"]:checked');return el?el.value:'';}
function run(){var t=val('type'),pr=val('price'),pw=val('power'),st=f.elements.stock.checked,so=f.elements.sort.value,shown=0;
 cards.forEach(function(c){var d=c.dataset,ok=(!t||d.type.split(' ').indexOf(t)>-1)&&rng(pr,d.price)&&rng(pw,d.w)&&(!st||d.stock==='2');c.hidden=!ok;if(ok)shown++;});
 var s=cards.slice().sort(function(a,b){var A=a.dataset,B=b.dataset;
  if(so==='th')return (+B.th)-(+A.th);
  var pa=A.price===''?1e9:+A.price,pb=B.price===''?1e9:+B.price;return (B.stock-A.stock)||(pa-pb);});
 s.forEach(function(c){grid.appendChild(c);});
 n.textContent='Showing '+shown+' of '+cards.length;
 var o=new URLSearchParams();if(t)o.set('type',t);if(pr)o.set('price',pr);if(pw)o.set('power',pw);if(st)o.set('stock','1');if(so!=='price')o.set('sort',so);
 history.replaceState(null,'',location.pathname+(o.toString()?'?'+o:''));}
f.addEventListener('change',run);f.addEventListener('submit',function(e){e.preventDefault();});
document.getElementById('mreset').addEventListener('click',function(){f.reset();run();});run();
})();
</script>"""


def build_miners():
    path = "/miners/"
    ms = miners_sorted()
    offs = [o for m in ms for o in STATS[m]["offers"]]
    n_in = sum(1 for o in offs if in_stock(o))
    groups = "".join(f'<fieldset><legend>{esc(lab)}</legend><div class="opts">' + "".join(
        f'<label><input type="radio" name="{k}" value="{v}"{" checked" if v == "" else ""}><span>{esc(t)}</span></label>' for v, t in opts) + "</div></fieldset>"
        for k, lab, opts in FILTERS)
    form = f"""<form id="mf" class="filters" hidden aria-label="Filter miners">
{groups}
<div class="frow"><label class="tog"><input type="checkbox" name="stock" value="1"><span>In stock only</span></label>
<label class="sortby">Sort <select name="sort"><option value="price">Price, low to high</option><option value="th">Hashrate, high to low</option></select></label>
<button type="button" class="btn ghost sm" id="mreset">Reset</button></div>
<p class="meta" id="mcount" role="status" aria-live="polite"></p>
</form>"""
    older = [m for m in TRACKED if m in NOINDEX_MODELS]
    older_html = ('<p class="older">Older models: ' + " · ".join(f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' for m in older) + "</p>") if older else ""
    cards = "".join(hub_card(m, heat=(m in HEAT_SET), attrs=card_data(m)) for m in ms)
    body = f"""<article>
<header class="hero"><h1>All home Bitcoin miners</h1>
<p class="lede">Every miner we track, from small Bitaxe boards to room heaters. Not sure? <a href="/find-my-miner/">Find my miner</a>.</p>
<p class="meta">{len(ms)} miners · {n_in} of {len(offs)} listings in stock · checked {tag_time(latest['generated_at'])}</p>
<div class="nojs">{browse_pills("/miners/")}</div>
{best_pills()}</header>
{form}
{rate_box(anchor=True)}
<section aria-label="Miners"><div class="cards" id="grid">{cards}</div>{older_html}</section>
<section class="guides-line"><p>By type: <a href="/solo-miners/">Solo miners</a> · <a href="/pool-miners/">Pool miners</a> · <a href="/heater-miners/">Heater miners</a></p>
<p>New to this? <a href="/guides/solo-vs-pool-mining/">Solo vs pool</a> · <a href="/guides/how-heater-miners-work/">How heater miners work</a></p>
<p class="hint">Hashrate and watts are the sellers' stated figures. Prices are before shipping and tax; euro and Canadian-dollar prices are converted as an estimate. Pool and power figures are estimates; {EARN_NOTE.lower()}</p></section>
</article>"""
    title = f"All home Bitcoin miners: prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"All {N_MODELS} home Bitcoin miners we track, Bitaxe to heaters: {n_in} listings in stock. Filter by type, price and power. Checked every 6 hours."
    layout(path, title, desc, body, crumbs=[("Home", "/"), ("All miners", path)], scripts=MINERS_JS,
           jsonld=[itemlist("Home Bitcoin miners tracked by Bitaxe Radar", [(SHORT[m], f"/models/{m}/") for m in ms])])


def build_redirect(old, new, label):
    out = SITE / old.strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Moved to {esc(label)} | Bitaxe Radar</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="This page moved to {esc(label)} on Bitaxe Radar.">
<meta name="robots" content="noindex,follow"><link rel="canonical" href="{BASE}{new}">
<meta http-equiv="refresh" content="0; url={new}"><script>location.replace("{new}"+location.search+location.hash)</script></head>
<body><h1>This page moved</h1><p>Go to <a href="{new}">{esc(label)}</a>.</p></body></html>
""")


QUIZ = [("budget", "What's your budget?", [("100", "Under $100"), ("500", "$100 to $500"), ("500up", "$500 or more")]),
        ("goal", "What do you want it to do?", [("solo", "Take a lottery shot at a whole block"), ("pool", "Earn small, steady payouts"), ("heat", "Heat a room while it mines")]),
        ("place", "Where will it live?", [("desk", "On my desk or in a bedroom (quiet)"), ("room", "A room I use (some fan noise is OK)"), ("garage", "Garage or basement (noise is fine)")])]

QUIZ_JS = """<script>
(function(){
var f=document.getElementById('quiz'),out=document.getElementById('qres'),pool=[].slice.call(document.querySelectorAll('#qpool article'));if(!f)return;
f.hidden=false;
function v(k){var e=f.querySelector('[name="'+k+'"]:checked');return e?e.value:null;}
function money(x){return '$'+Math.round(x).toLocaleString('en-US');}
function quiet(d,place){var db=d.db===''?null:+d.db,w=+d.w;if(place==='desk')return db!==null?db<=40:w<=60;if(place==='room')return db!==null?db<=50:w<=200;return true;}
function inBudget(b,x){return b==='500up'?x>=500:x<=+b;}
function pick(b,g,p,relax){return pool.filter(function(c){var d=c.dataset;if(d.price==='')return false;
  if(d.type.split(' ').indexOf(g)<0)return false;if(relax<2&&!inBudget(b,+d.price))return false;if(relax<1&&!quiet(d,p))return false;return true;});}
function score(d,g){return g==='heat'?+d.hw:+d.th;}
function why(d,g,b,p){var s=[];
  if(g==='solo')s.push((+d.th).toLocaleString('en-US')+' TH/s of lottery tickets for '+money(+d.price));
  if(g==='pool')s.push('Most hashrate'+(b==='500up'?'':' under '+money(+b))+': '+(+d.th).toLocaleString('en-US')+' TH/s');
  if(g==='heat')s.push('About '+Math.round(+d.hw*3.412).toLocaleString('en-US')+' BTU/h of heat');
  if(d.db!==''&&p!=='garage')s.push(+d.db===0?'silent, no fans':d.db+' dB stated');
  if(d.stock!=='2')s.push('not in stock yet');return s.join(' · ');}
f.addEventListener('submit',function(e){e.preventDefault();var b=v('budget'),g=v('goal'),p=v('place');
  if(!b||!g||!p){out.innerHTML='<p class="hint">Pick one answer for each question.</p>';return;}
  function rank(l,byPrice){return l.sort(function(A,B){var a=A.dataset,c=B.dataset;return (c.stock-a.stock)||(byPrice?(a.price-c.price):(score(c,g)-score(a,g)))||(a.price-c.price);});}
  var list=[],seen={},relax=0;
  function add(more){more.forEach(function(c){var k=c.dataset.th+'|'+c.dataset.w;if(list.length<3&&list.indexOf(c)<0&&!seen[k]){seen[k]=1;list.push(c);}});}
  add(rank(pick(b,g,p,0),false));
  if(list.length<3){var n0=list.length;add(rank(pick(b,g,p,1),false));if(list.length>n0)relax=1;}
  if(!list.length){relax=2;var edge=b==='500up'?500:+b;
    add(pick(b,g,p,2).sort(function(A,B){return (B.dataset.stock-A.dataset.stock)||(Math.abs(A.dataset.price-edge)-Math.abs(B.dataset.price-edge));}));}
  out.innerHTML='';var h=document.createElement('h2');h.textContent=list.length===1?'Your best match':'Your top '+list.length;out.appendChild(h);
  var note=relax===1?'Some picks may be louder than you asked for, because fewer than 3 matched every answer.':relax===2?'Nothing matched your budget, so these are the closest picks outside it.':list.length<3?'Only '+list.length+' miner'+(list.length===1?'':'s')+' matched all your answers.':'';
  if(note){var n=document.createElement('p');n.className='hint';n.textContent=note;out.appendChild(n);}
  var g2=document.createElement('div');g2.className='cards';
  list.slice(0,3).forEach(function(c,i){var k=c.cloneNode(true);var w=k.querySelector('.why');w.textContent=why(c.dataset,g,b,p);w.hidden=false;
   var r=k.querySelector('.ribbon');r.textContent='#'+(i+1);g2.appendChild(k);});
  out.appendChild(g2);var m=document.createElement('p');m.innerHTML='<a href="/miners/">See all miners →</a>';out.appendChild(m);
  out.scrollIntoView({behavior:'smooth',block:'start'});});
})();
</script>"""


def build_quiz():
    path = "/find-my-miner/"
    qs = "".join(f'<fieldset class="q"><legend><i>{i}</i>{esc(t)}</legend><div class="opts col">' + "".join(
        f'<label><input type="radio" name="{k}" value="{v}" required><span>{esc(lab)}</span></label>' for v, lab in opts) + "</div></fieldset>"
        for i, (k, t, opts) in enumerate(QUIZ, 1))
    cards = "".join(hub_card(m, heat=(m in HEAT_SET), rank=1, why=" ", attrs=card_data(m)).replace('<div class="why"> </div>', '<div class="why" hidden></div>')
                    for m in miners_sorted() if show_price(m) is not None)
    body = f"""<article>
<header class="hero"><h1>Find my miner</h1>
<p class="lede">Three quick questions. We show up to 3 best matches from today's prices.</p></header>
<form id="quiz" class="quiz" hidden>{qs}<button type="submit" class="btn">Show my top 3</button></form>
<noscript><p>The quiz needs JavaScript. Try <a href="/miners/">All miners</a> or the <a href="/best/">best-for lists</a> instead.</p></noscript>
<section id="qres" aria-live="polite"></section>
<div id="qpool" hidden>{cards}</div>
<section class="guides-line"><p>Or browse: <a href="/best/beginners/">Best for beginners</a> · <a href="/best/quiet/">Quietest</a> · <a href="/heater-miners/">Heater miners</a></p>
<p class="hint">Picks follow simple rules: your budget, the miner's type, and its stated noise or power. Prices are before shipping and tax. No miner is a sure way to earn money.</p></section>
</article>"""
    layout(path, "Find my miner: pick a home Bitcoin miner in 3 questions | Bitaxe Radar",
           "Answer 3 questions (budget, goal, where it lives) and see the 3 best home Bitcoin miners for you from today's prices and stock.",
           body, crumbs=[("Home", "/"), ("Find my miner", path)], scripts=QUIZ_JS)


def build_alerts():
    path = "/alerts/"
    form = signup_html("any") or '<p>Price alerts are paused right now. Check back soon.</p>'
    body = f"""<article>
<header class="hero"><h1>Price-drop alerts</h1>
<p class="lede">Tell us a miner and your price. We email you once when it's in stock at or under it.</p></header>
{form}
<h2>Or get a short weekly roundup</h2>
{nl_signup()}
<p class="hint">Past issues: <a href="/newsletter/">Home Mining Weekly</a> · Questions? <a href="mailto:{CONTACT}">{CONTACT}</a></p>
</article>"""
    layout(path, "Free price-drop alerts for home Bitcoin miners | Bitaxe Radar",
           "Get one email when a Bitaxe, NerdQaxe, Avalon or heater miner is in stock at or under your price. Free, no spam, one-click unsubscribe.",
           body, crumbs=[("Home", "/"), ("Alerts", path)], scripts=NL_SCRIPTS or SIGNUP_SCRIPTS)


# ---------------------------------------------------------------------------------------------
# NEWSLETTER (Home Mining Weekly): web copies of each issue, from data/newsletter/*.json (see newsletter.py)
# ---------------------------------------------------------------------------------------------
NL_NAME = "Home Mining Weekly"
NL_SCRIPTS = (SIGNUP_SCRIPTS + '\n<script src="/nl-signup.js" defer></script>') if SIGNUP_ENABLED else ""


def nl_signup():
    if not SIGNUP_ENABLED:
        return f'<section class="signup"><h2 style="margin-top:0">Get the weekly email</h2><p>Signups are paused right now. Write <a href="mailto:{CONTACT}">{CONTACT}</a> and we\'ll add you.</p></section>'
    return f"""<section class="signup" aria-labelledby="h-nl"><h2 id="h-nl" style="margin-top:0">Get the weekly email</h2>
<p>One short email a week: best prices, new miners, one plain-words explainer. Free, no spam, unsubscribe anytime.</p>
<form id="nlsignup" novalidate>
  <div class="row nl-row"><label>Email <input type="email" id="nlEmail" name="email" autocomplete="email" placeholder="you@example.com" maxlength="254" required></label></div>
  <div style="position:absolute;left:-9999px" aria-hidden="true"><label>Website <input type="text" id="nlWebsite" name="website" tabindex="-1" autocomplete="off"></label></div>
  <div class="row signup-actions"><div id="nlTurnstile" class="turnstile-slot"></div><button type="submit" id="nlBtn">Get {NL_NAME}</button></div>
  <p class="hint">You'll get one email to confirm first. Never sold. Separate from price alerts.</p>
  <p class="hint" id="nlMsg" role="status" aria-live="polite"></p>
  <noscript><p class="hint">The sign-up form needs JavaScript for its bot check. Or write <a href="mailto:{CONTACT}">{CONTACT}</a>.</p></noscript>
</form></section>"""


def build_newsletter():
    iss = NL.issues()
    for i in iss:
        path = f"/newsletter/{i['slug']}/"
        rows = "".join(f'<tr><td><a href="/models/{p["model"]}/">{esc(SHORT.get(p["model"], p["name"]))}</a><br><small class="hint">at {esc(p["seller_name"])}</small></td>'
                       f'<td class="num"><b>{esc(NL.price_label(p))}</b></td><td>{offer_link(dict(seller=p["seller"], url=p["url"]), "Shop ↗", "btn sm")}</td></tr>'
                       for p in i["prices"])
        new = "".join(f'<li><a href="/models/{n["model"]}/"><b>{esc(SHORT.get(n["model"], n["name"]))}</b>'
                      + (f' · from {money(n["from_usd"])}' if n.get("from_usd") else "") + f'</a> {esc(n["blurb"])}</li>' for n in i["new_miners"])
        ex = i["explainer"]
        body = f"""<article>
<header class="hero"><h1>{esc(i["title"])}</h1>
<p class="lede">{esc(i["intro"])}</p>
<p class="meta">Issue #{i["num"]} · <time datetime="{i["date"]}">{NL.pretty_date(i["date"])}</time> · 2-minute read</p></header>
<section aria-labelledby="h-p"><h2 id="h-p">This week's best prices</h2>
<div class="tablewrap"><table><thead><tr><th>Miner</th><th class="num">Price</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="hint">Cheapest in-stock listing we found, checked {esc(NL.et_time(i["snapshot_at"]))}. These were the prices when the issue went out; they change fast. <a href="/deals/">See today's live prices</a>.</p></section>
<section aria-labelledby="h-n"><h2 id="h-n">{plural(len(i["new_miners"]), "new miner")} on the site</h2><ul>{new}</ul><p><a href="/miners/">Browse all miners →</a></p></section>
<section aria-labelledby="h-q"><h2 id="h-q">Not sure which one fits you?</h2><p>Answer 3 quick questions and we'll suggest a miner.</p><p><a class="btn" href="/find-my-miner/">Take the Find my miner quiz</a></p></section>
<section aria-labelledby="h-e"><h2 id="h-e">{esc(ex["title"])}</h2>{"".join(f"<p>{esc(t)}</p>" for t in ex["paras"])}<p><a href="{esc(ex["link"])}">Read the 2-minute guide →</a></p></section>
<section aria-labelledby="h-a"><h2 id="h-a">Want a heads-up when a price drops?</h2><p>Pick a miner and your price. We email you once when it's in stock at or under it.</p><p><a class="btn" href="/alerts/">Set a free price alert</a></p></section>
{nl_signup()}
<p class="hint">{esc(NL.NO_PROMISE)} <a href="/newsletter/">All issues</a></p>
</article>"""
        layout(path, f"{i['title']}: best home Bitcoin miner prices | Bitaxe Radar", i["preheader"], body,
               crumbs=[("Home", "/"), ("Newsletter", "/newsletter/"), (f"Issue #{i['num']}", path)], lastmod=i["date"], og_type="article", scripts=NL_SCRIPTS)
    lis = "".join(f'<li><a href="/newsletter/{i["slug"]}/"><b>{esc(i["title"])}</b><span>{NL.pretty_date(i["date"])} · {esc(i["preheader"])}</span></a></li>' for i in iss)
    body = f"""<article>
<header class="hero"><h1>{NL_NAME}</h1>
<p class="lede">A short weekly email about home Bitcoin miners: the best prices we found, new miners, and one quick explainer. Every issue is also posted here.</p></header>
{nl_signup()}
<h2>All issues</h2><ul class="glist">{lis or "<li>The first issue is coming soon.</li>"}</ul>
<p class="hint">Rather get one email when a specific miner drops in price? <a href="/alerts/">Set a price alert</a>.</p>
</article>"""
    layout("/newsletter/", f"{NL_NAME}: a weekly home Bitcoin mining email | Bitaxe Radar",
           "A short weekly email on home Bitcoin miners: best Bitaxe, NerdQaxe, Avalon and heater miner prices, new models and plain-words explainers. Free.",
           body, crumbs=[("Home", "/"), ("Newsletter", "/newsletter/")], lastmod=iss[0]["date"] if iss else None, scripts=NL_SCRIPTS)


def tile(href, mid, title, sub):
    img = (f'<img src="/img/models/{mid}.webp" width="{MODEL_IMG[mid][0]}" height="{MODEL_IMG[mid][1]}" alt="{esc(MODEL_IMG[mid][2])}" loading="lazy" decoding="async">'
           if mid in MODEL_IMG else miner_art(mid))
    return f'<a class="btile" href="{href}"><span class="bimg">{img}</span><b>{esc(title)}</b><small>{esc(sub)}</small></a>'


def build_indexes():
    # /models/: A to Z
    rows = "".join(f'<li><a href="/models/{m}/">{esc(SHORT[m])}</a> <span>≈{MODELS[m]["hashrate_ths"]:g} TH/s · '
                   + (f'from {money(show_price(m))}' if show_price(m) is not None else "sold out") + "</span></li>"
                   for m in sorted(LIVE_TRACKED, key=lambda m: SHORT[m].lower()))
    older = " · ".join(f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' for m in TRACKED if m in NOINDEX_MODELS)
    body = f"""<article><header class="hero"><h1>Every model, A to Z</h1>
<p class="lede">Want filters and photos? Use <a href="/miners/">All miners</a>.</p></header>
<ul class="az">{rows}</ul>{f'<p class="older">Older models: {older}</p>' if older else ""}</article>"""
    layout("/models/", "All home Bitcoin miner models A to Z | Bitaxe Radar", f"An A to Z list of the {N_MODELS} home Bitcoin miners Bitaxe Radar tracks, with today's lowest price.",
           body, crumbs=[("Home", "/"), ("All miners", "/miners/"), ("Models A to Z", "/models/")])
    # /sellers/
    shops, shop_ids = [], []
    for sid, s in SELLERS.items():
        if sid not in SELLER_COPY or not any(o["seller"] == sid for o in OFFERS):
            continue
        shop_ids.append(sid)
        offs = [o for o in OFFERS if o["seller"] == sid]
        n_in = sum(1 for o in offs if in_stock(o))
        shops.append(f'<li><a class="shop" href="/sellers/{sid}/"><b>{esc(s["name"])}</b><span>{plural(len({o["model"] for o in offs}), "miner")} · {n_in} in stock · prices in {esc(s["currency"])}</span></a></li>')
    body = f"""<article><header class="hero"><h1>Shops we check</h1>
<p class="lede">{len(shops)} shops, checked every 6 hours. Tap one to see everything it sells and its shipping notes, or compare them in the table below.</p></header>
<ul class="shops">{"".join(shops)}</ul>
<section aria-labelledby="h-f"><h2 id="h-f">Compare shops</h2>{facts_table(shop_ids)}{FACTS_NOTE}</section>
<p><a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a> · <a href="/how-we-track/">How we pick shops</a></p></article>"""
    layout("/sellers/", "Shops we check for home Bitcoin miners | Bitaxe Radar", f"The {len(shops)} US, Canadian and EU shops Bitaxe Radar checks every 6 hours for home Bitcoin miner prices and stock.",
           body, crumbs=[("Home", "/"), ("Shops", "/sellers/")])
    # /best/
    tiles = "".join(tile(f"/best/{k}/", v["picks"][0][0], v["label"], v["h1"]) for k, v in BEST.items() if v["picks"])
    body = f"""<article><header class="hero"><h1>Best miners for…</h1>
<p class="lede">Short ranked lists with a one-line reason for each pick.</p></header>
<div class="btiles wide">{tiles}</div>
<p class="older">Not sure? <a href="/find-my-miner/">Find my miner</a> asks 3 questions.</p></article>"""
    layout("/best/", "Best home Bitcoin miners by need: beginners, quiet, cheap, heating | Bitaxe Radar",
           "Ranked picks of home Bitcoin miners for beginners, quiet rooms, under $100 and heating a room, from today's prices.", body, crumbs=[("Home", "/"), ("Best for", "/best/")])
    # /compare/
    pairs = [(a, b) for a, b in COMPARE_PAIRS if STATS[a]["offers"] and STATS[b]["offers"]]
    body = f"""<article><header class="hero"><h1>Compare miners</h1>
<p class="lede">Side by side: price, hashrate, power and running cost.</p></header>
<ul class="links">{"".join(f'<li><a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a></li>' for a, b in pairs)}</ul></article>"""
    layout("/compare/", "Compare home Bitcoin miners side by side | Bitaxe Radar", "Head-to-head comparisons of popular home Bitcoin miners: price, hashrate, power use and running cost.",
           body, crumbs=[("Home", "/"), ("Guides", "/guides/"), ("Compare", "/compare/")])
    # /guides/
    gl = [("/guides/is-home-mining-worth-it/", "Is home mining worth it?", "Check it at your electricity price."),
          ("/solo-odds/", "Solo odds calculator", "Your real chance of finding a block."),
          ("/solo-wins/", "Solo block wins", "Recent blocks won by solo miners."),
          ("/heat-calculator/", "Room heat calculator", "Which heater miner fits your room."),
          ("/price-per-th/", "Price per TH/s leaderboard", "Most hashrate per dollar, and is today's price good?"),
          ("/guides/solar-bitcoin-mining/", "Can solar power a miner?", "Panels needed for each miner."),
          ("/guides/bitcoin-mining-heat-your-home/", "Mining to heat your home", "Miner vs space heater vs heat pump."),
          ("/guides/solo-vs-pool-mining/", "Solo vs pool mining", "Lottery shot or small steady payouts?"),
          ("/guides/bitcoin-mining-pools/", "Which mining pool?", "Popular Bitcoin pools compared: fees and payouts."),
          ("/guides/how-heater-miners-work/", "How heater miners work", "A miner that warms the room."),
          ("/where-to-buy-bitaxe/", "Where to buy a Bitaxe", "Every shop, ranked by today's price."),
          ("/how-we-track/", "How we track prices", "Where the numbers come from.")]
    body = f"""<article><header class="hero"><h1>Guides</h1>
<p class="lede">Plain-words help for picking and running a home miner.</p></header>
<ul class="glist">{"".join(f'<li><a href="{p}"><b>{esc(t)}</b><span>{esc(d)}</span></a></li>' for p, t, d in gl)}</ul>
<h2>Best for</h2>{best_pills()}
<h2>Compare</h2><ul class="links">{"".join(f'<li><a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a></li>' for a, b in pairs[:6])}<li><a href="/compare/">All comparisons →</a></li></ul>
<h2>Shops</h2><p><a href="/sellers/">All shops we check →</a></p></article>"""
    layout("/guides/", "Home Bitcoin mining guides | Bitaxe Radar", "Guides to home Bitcoin mining: solo vs pool, how heater miners work, where to buy a Bitaxe, best-for lists and comparisons.",
           body, crumbs=[("Home", "/"), ("Guides", "/guides/")])


def main():
    BEST.update(best_defs())      # before any page that shows the best-for chips
    for mid in TRACKED:
        build_model_page(mid)
    for a, b in COMPARE_PAIRS:
        if STATS[a]["offers"] and STATS[b]["offers"]:      # only where the data supports a comparison
            build_compare_page(a, b)
    for sid in SELLERS:
        if sid in SELLER_COPY and any(o["seller"] == sid for o in OFFERS):
            build_seller_page(sid)
    build_where_to_buy()
    build_in_stock()
    build_deals()
    build_price_per_th()
    build_black_friday()
    build_redirect("/home-miners/", "/miners/", "All miners")
    build_redirect("/about/", "/how-we-track/", "About & how we track")
    build_miners()
    build_quiz()
    build_alerts()
    build_newsletter()
    for c in CATS:
        build_category(c[0])
    for k in BEST:
        build_best(k)
    build_llms()
    build_indexes()
    build_guide_heaters()
    build_guide_pool()
    build_guide_worth()
    build_guide_solar()
    build_guide_heat_home()
    build_guide_pools()
    build_solo_odds()
    build_heat_calc()
    build_solo_wins()
    build_method()
    build_advertise()
    build_404()
    build_home()
    write_sitemap()
    print(f"built {len(PAGES)} indexable pages in sitemap.xml; {len(TRACKED)} model pages ({len(NOINDEX_MODELS & set(TRACKED))} noindex)")


main()
