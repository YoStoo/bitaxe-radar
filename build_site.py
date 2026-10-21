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
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
AVAIL = {"in_stock": "https://schema.org/InStock", "out_of_stock": "https://schema.org/OutOfStock",
         "preorder": "https://schema.org/PreOrder", "backorder": "https://schema.org/BackOrder"}


def esc(s):
    return _html.escape(str(s), quote=True)


def parse_t(iso):
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def money(v, cur="USD"):
    return {"USD": "$", "EUR": "€"}.get(cur, cur + " ") + f"{v:,.2f}"


def fmt_time(iso):
    d = parse_t(iso)
    return f"{d:%b} {d.day}, {d.year} {d:%H:%M} UTC"


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


SPONSOR_SLOT = ('<aside class="sponsor" aria-label="Sponsor spot"><small>Sponsor</small> '
                '<span>Sell miners or accessories? <a href="/advertise/">Your shop could be featured here</a>.</span></aside>')


def badge(status):
    return f'<span class="badge b-{esc(status)}">{esc(STATUS.get(status, status))}</span>'


# ---------------------------------------------------------------------------------------------
# model & seller metadata (hand-written; numbers are computed, not typed)
# ---------------------------------------------------------------------------------------------
SHORT = {"bitaxe-supra": "Bitaxe Supra", "bitaxe-ultra": "Bitaxe Ultra", "bitaxe-gamma": "Bitaxe Gamma",
         "bitaxe-gamma-duo": "Bitaxe Gamma Duo", "bitaxe-gt-801": "Bitaxe GT 801", "nerdaxe-gamma": "Nerdaxe Gamma",
         "nerdaxe-gaia": "Nerdaxe Gaia", "nerdqaxe-pp": "NerdQaxe++"}
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
        region="EUR prices (US variant listed)",
        about="A European shop that lists a US variant for some miners and says it ships to the US and Canada. Prices are in euros; the dollar figures are estimates.",
        notes=["Pre-orders are labelled as such, with the seller's own ship-date wording when it gives one.",
               "Its FAQ says it ships to the US and Canada (express 2–4 days, standard 4–6 days; customs can add time).",
               "Shipping and import duties are not included, so the real US price will be higher than the figure shown."]),
    "bitaxede": dict(
        region="EUR prices incl. VAT",
        about="A European shop. Prices are in euros and include VAT; shipping is extra.",
        notes=["It delivers to the EU plus Switzerland, Norway, Iceland and Liechtenstein, so it's mainly useful for European buyers.",
               "Because VAT is included and shipping isn't, its dollar estimates aren't directly comparable to a US shop's pre-tax prices."]),
}

NAV = [("/#miners", "Miners"), ("/deals/", "Deals"), ("/in-stock/", "In stock"), ("/where-to-buy-bitaxe/", "Where to buy")]

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
         "nerdaxe-gamma": 1, "nerdaxe-gaia": 1, "nerdqaxe-pp": 4}
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


STATS = {mid: stats(mid) for mid in MODELS}
TRACKED = [mid for mid in MODELS if STATS[mid]["offers"]]
EFF_RANK = {mid: i + 1 for i, mid in enumerate(sorted(TRACKED, key=jth))}
_pth = sorted([m for m in TRACKED if STATS[m]["per_th"] is not None], key=lambda m: STATS[m]["per_th"])
PTH_RANK = {mid: i + 1 for i, mid in enumerate(_pth)}


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


def header_html():
    nav = "".join(f'<a href="{p}"{" class=\"hide-sm\"" if p == "/where-to-buy-bitaxe/" else ""}>{esc(n)}</a>' for p, n in NAV) + '<a class="nav-cta" href="/#alerts"><span class="hide-sm">Price alerts</span><span class="show-sm">Alerts</span></a>'
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
  <a class="brand" href="/" aria-label="Bitaxe Radar home">{WORDMARK}</a>
  <nav aria-label="Main">{nav}</nav>
</div></header>"""


def footer_html(extra=""):
    links = [("/#miners", "All miners"), ("/deals/", "Deals"), ("/bitaxe-black-friday/", "Black Friday 2026"), ("/in-stock/", "In stock"), ("/where-to-buy-bitaxe/", "Where to buy"),
             ("/how-we-track/", "About & how we track"), ("/advertise/", "Advertise")]
    return f"""<footer class="foot"><div class="wrap">
  <a class="brand" href="/">{WORDMARK}</a>
  <p>The cheapest in-stock Bitaxe, NerdQaxe and Nerdaxe miners from US and EU shops, checked every 6 hours.</p>
  <nav class="foot-links" aria-label="Footer">{"".join(f'<a href="{p}">{esc(n)}</a>' for p, n in links)}<a href="mailto:{CONTACT}">{CONTACT}</a></nav>
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
{header_html()}
<main class="wrap" id="main">
{crumbs_html(crumbs) if crumbs else ""}
{body}
</main>
{footer_html()}
{scripts}{ANALYTICS}
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
    if p["currency"] == "EUR":
        return p["price"] * FX["EUR_USD"] if FX.get("EUR_USD") else None
    return p["price"]


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
    path = f"/models/{mid}/"
    best, low = st["best"], st["low_any"]
    n_in = len(st["in_stock"])
    day = fmt_day(GEN)
    trail = [("Home", "/"), (short, path)]

    if best:
        head = (f'In stock at {n_in} of {plural(st["sellers"], "shop")}. Cheapest right now: <strong>{money(usd(best))}</strong> at {esc(sname(best["seller"]))}.')
        title = f"{short} price: {money(usd(best))} in stock ({day}) | Bitaxe Radar"
        desc = (f"{short} prices at {plural(st['sellers'], 'seller')}: cheapest in stock {money(usd(best))} at {sname(best['seller'])}, "
                f"listed {money(usd(low))}–{money(usd(st['high_any']))}. Stock, price log, running cost. Updated {day}.")
    else:
        head = (f'<strong>Sold out everywhere we check right now.</strong> Lowest listed price: {money(usd(low))} at {esc(sname(low["seller"]))} ({esc(STATUS[low["stock_status"]].lower())}). Set an alert below and we\'ll tell you when it\'s back.')
        title = f"{short} price: sold out or pre-order only ({day}) | Bitaxe Radar"
        desc = (f"{short} at {plural(st['sellers'], 'seller')}: none has it in stock at the last check ({day}). "
                f"Lowest listed {money(usd(low))} at {sname(low['seller'])}. Stock status, price log and price alerts.")

    avail_note = ""
    if best and low and low["id"] != best["id"] and not in_stock(low):
        avail_note = (f'<p class="avail">Listed cheaper at {esc(sname(low["seller"]))} ({money(usd(low))}), but it\'s {esc(STATUS[low["stock_status"]].lower())}.</p>')

    offers_html = offers_table(sort_offers(st["offers"]), best_id=best["id"] if best else None)

    per_th = st["per_th"]
    rows = [("Hashrate", f"≈ {m['hashrate_ths']:g} TH/s (seller-stated)"),
            ("Power", f"≈ {m['watts']:g} W (seller-stated)"),
            ("Efficiency", f"≈ {jth(mid):.1f} J/TH · {ordinal(EFF_RANK[mid])} best of {len(TRACKED)}"),
            ("Chip", m["chip"]),
            ("Price per TH/s", (f"{money(per_th)} · {ordinal(PTH_RANK[mid])} cheapest of {len(PTH_RANK)}") if per_th else "n/a, none in stock"),
            ("Energy", f"≈ {kwh_year(mid):,.0f} kWh a year if run 24/7")]
    spec_tbl = '<div class="tablewrap"><table><tbody>' + "".join(f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in rows) + "</tbody></table></div>"
    kwh = kwh_year(mid)
    elec_tbl = ('<div class="tablewrap"><table><thead><tr><th>Power price</th>' + "".join(f'<th class="num">${r:.2f}/kWh</th>' for r in ELEC_RATES) + "</tr></thead>"
                f'<tbody><tr><th scope="row">Cost per year, 24/7</th>{"".join(f"<td class=num>${kwh * r:,.0f}</td>" for r in ELEC_RATES)}</tr></tbody></table></div>')
    spec_note = f'<p class="hint">{esc(m["note"])}. Want your own rate? Use the <a href="/#cost">power-cost calculator</a>.</p>'

    yrs = lottery_years(mid)
    rel_c = related_compare(mid)
    rel_links = "".join(f'<li><a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a></li>' for a, b in rel_c)
    others = [x for x in TRACKED if x != mid and x not in NOINDEX_MODELS][:6]
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
    faq.append((f"Can a {short} make money?",
                f"Almost certainly not. It's a solo \"lottery\" miner: it either finds a whole Bitcoin block (a huge reward) or nothing. As a rough illustration, on a {NETWORK_EH_ILLUSTRATION:,} EH/s network it would find a block about once every {sig2(yrs)} years on average, while electricity costs money every year. Buy it as a hobby, not an investment.", False))
    faq.append((f"How do I get told when the {short} price drops?",
                "Use the alert form on this page: pick your price and we email you once it's in stock at or under it. Free, and you can unsubscribe in one click.", False))
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{a if raw else esc(a)}</p></details>" for q, a, raw in faq)

    check_html = "".join(f"<li>{esc(c)}</li>" for c in cp["check"])
    body = f"""<article>
<header class="hero"><h1>{esc(short)}</h1>
<p class="lede">{head}</p>
<p class="meta">≈{m['hashrate_ths']:g} TH/s · ≈{m['watts']:g} W · {esc(m['chip'])} · checked {tag_time(st['checked'])}</p></header>
<div class="model-top"><figure class="model-photo{"" if mid in MODEL_IMG else " placeholder"}">{model_img(mid, lazy=False)}</figure>
<div class="model-deal">{best_cta(st) or '<div class="cta"><div><small>Sold out right now</small><p class="hint">Set a price alert below and we\'ll email you when it\'s back.</p></div></div>'}
{avail_note}</div></div>
<section aria-labelledby="h-offers"><h2 id="h-offers">Prices by shop</h2>
{offers_html}
<p class="hint">Before shipping and tax. Euro prices are converted to dollars as an estimate. Updated every 6 hours.</p></section>
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
<ul class="links">{other_links}</ul></section>
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
    trail = [("Home", "/"), ("Where to buy", "/where-to-buy-bitaxe/"), (s["name"], path)]
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
    unverified = '<p class="hint">Check the shop\'s own shipping, warranty and return pages before you pay.</p>'
    title = f"{s['name']} Bitaxe prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"{s['name']}: {len(offs)} Bitaxe-family miners tracked, {n_in} in stock now ({cp['region']}). Prices, stock, price log and buying notes."
    body = f"""<article>
<header class="hero"><h1>{esc(s['name'])}: prices and stock</h1><p class="lede">{esc(cp['about'])}</p>
<p class="meta">{summary}</p></header>
<section aria-labelledby="h-p"><h2 id="h-p">What {esc(s['name'])} has right now</h2>{tbl}
<p class="hint">Store: <a href="{esc(s['url'])}" rel="nofollow noopener" target="_blank">{esc(s['url'].replace('https://', ''))}</a>. Prices are before shipping and tax.</p></section>
<section aria-labelledby="h-n"><h2 id="h-n">Good to know</h2><ul>{notes}</ul>{unverified}{aff_txt}</section>
<section aria-labelledby="h-l"><h2 id="h-l">Price log</h2><details class="more"><summary>Show price log</summary>{log}</details></section>
<section><h2>See also</h2><ul class="links"><li><a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a></li><li><a href="/in-stock/">Everything in stock</a></li><li><a href="/deals/">Best deals</a></li></ul></section>
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


CURRENT_MODELS = [m for m in TRACKED if m not in NOINDEX_MODELS]


def build_where_to_buy():
    path = "/where-to-buy-bitaxe/"
    trail = [("Home", "/"), ("Where to buy a Bitaxe", path)]
    usd_sellers = [sid for sid in SELLERS if SELLERS[sid]["currency"] == "USD"]
    eur_sellers = [sid for sid in SELLERS if SELLERS[sid]["currency"] != "USD"]
    qa = []
    g = STATS["bitaxe-gamma"]
    if g["best_usd"]:
        qa.append(f"Cheapest <strong>Bitaxe Gamma</strong> in stock at a USD-priced seller: <strong>{money(g['best_usd']['price'])}</strong> at {esc(sname(g['best_usd']['seller']))}.")
    gl = g["low_any"]
    if gl and not in_stock(gl):
        qa.append(f"The cheapest listed Gamma, {money(usd(gl))} at {esc(sname(gl['seller']))}, is {esc(STATUS[gl['stock_status']].lower())} at the last check.")
    ins_usd = [o for o in OFFERS if in_stock(o) and o["currency"] == "USD"]
    qa.append(f"Right now {len(ins_usd)} of our {sum(1 for o in OFFERS if o['currency'] == 'USD')} USD-priced listings are in stock, across {len({o['seller'] for o in ins_usd})} sellers.")
    qa_html = "".join(f"<li>{x}</li>" for x in qa)

    def seller_row(sid):
        s, cp = SELLERS[sid], SELLER_COPY[sid]
        offs = [o for o in OFFERS if o["seller"] == sid]
        n_in = sum(1 for o in offs if in_stock(o))
        return (f'<tr><td><a href="/sellers/{sid}/">{esc(s["name"])}</a></td><td>{esc(cp["region"])}</td><td class="num">{len(offs)}</td><td class="num">{n_in}</td>'
                f'<td class="cfg">{tag_time(max(o["checked_at"] for o in offs))}</td></tr>')
    sellers_tbl = ('<div class="tablewrap"><table><thead><tr><th>Shop</th><th>Pricing</th><th class="num">Models</th><th class="num">In stock</th><th>Last checked</th></tr></thead>'
                   f'<tbody>{"".join(seller_row(s) for s in usd_sellers + eur_sellers)}</tbody></table></div>')
    title = f"Where to buy a Bitaxe in the US: prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = (f"Where to buy a Bitaxe or NerdQaxe: {len(SELLERS)} sellers tracked, {len(ins_usd)} USD-priced listings in stock. "
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
    items = [(SHORT[m], f"/models/{m}/") for m in CURRENT_MODELS]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Bitaxe-class miners tracked by Bitaxe Radar", items)])


def build_in_stock():
    path = "/in-stock/"
    trail = [("Home", "/"), ("In stock now", path)]
    order = {m: i for i, m in enumerate(MODELS)}

    def srt(lst):
        return sorted(lst, key=lambda o: (order[o["model"]], usd(o) if usd(o) is not None else 1e9))
    ins = srt([o for o in OFFERS if in_stock(o)])
    pre = srt([o for o in OFFERS if o["stock_status"] in ("preorder", "backorder")])
    oos = srt([o for o in OFFERS if o["stock_status"] in ("out_of_stock", "unknown")])
    none = [m for m in TRACKED if not STATS[m]["in_stock"]]
    notes = []
    for mid in TRACKED:
        st = STATS[mid]
        if st["best"] and st["low_any"]["id"] != st["best"]["id"] and not in_stock(st["low_any"]):
            notes.append(f"The cheapest listed {esc(SHORT[mid])}, {money(usd(st['low_any']))} at {esc(sname(st['low_any']['seller']))}, is {esc(STATUS[st['low_any']['stock_status']].lower())}. Cheapest in stock: {money(usd(st['best']))} at {esc(sname(st['best']['seller']))}.")
    if none:
        notes.append("Sold out everywhere we check: " + ", ".join(f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' for m in none) + ".")
    n_sellers = len({o["seller"] for o in ins})
    title = f"Bitaxe in stock now: {len(ins)} listings at {plural(n_sellers, 'seller')} ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"What is in stock right now: {len(ins)} of {len(OFFERS)} tracked Bitaxe, Nerdaxe and NerdQaxe listings, plus {len(pre)} pre-order or backorder. Updated {fmt_day(GEN)}."
    body = f"""<article>
<header class="hero"><h1>Bitaxe and NerdQaxe in stock now</h1>
<p class="lede">{len(ins)} of {len(OFFERS)} tracked listings are in stock at the last check. Another {len(pre)} are pre-order or backorder (not in stock yet) and {len(oos)} are sold out.</p>
<p class="meta">Checked {tag_time(latest['generated_at'])} · updated every 6 hours</p></header>
<section aria-labelledby="h-n"><h2 id="h-n">What the stock picture means today</h2><ul>{"".join(f"<li>{x}</li>" for x in notes) or "<li>Nothing unusual at the last check.</li>"}</ul></section>
<section aria-labelledby="h-i"><h2 id="h-i">In stock ({len(ins)})</h2>{offers_table(ins, show_model=True) if ins else "<p>Nothing is in stock at the tracked sellers at the last check.</p>"}</section>
<section aria-labelledby="h-p"><h2 id="h-p">Pre-order and backorder ({len(pre)})</h2><p class="hint">Not in stock. Read the seller's shipping note before ordering.</p>{offers_table(pre, show_model=True) if pre else "<p>None right now.</p>"}</section>
<section aria-labelledby="h-o"><h2 id="h-o">Sold out ({len(oos)})</h2>{offers_table(oos, show_model=True) if oos else "<p>None right now.</p>"}</section>
<section><h2>Related</h2><p><a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a> · <a href="/deals/">Best deals</a> · <a href="/how-we-track/">How we track</a></p></section>
</article>"""
    items = [(f"{SHORT[o['model']]} at {sname(o['seller'])}", f"/models/{o['model']}/") for o in ins]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Bitaxe-class miners in stock now", items)])


def build_deals():
    path = "/deals/"
    trail = [("Home", "/"), ("Best deals", path)]
    cand = [m for m in TRACKED if STATS[m]["best"]]
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
    gaps = [(mid, STATS[mid]) for mid in TRACKED if STATS[mid]["best"] and STATS[mid]["low_any"]["id"] != STATS[mid]["best"]["id"] and not in_stock(STATS[mid]["low_any"])]
    gap_rows = "".join(f'<tr><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td><td>{esc(sname(st["low_any"]["seller"]))}</td><td class="num">{money(usd(st["low_any"]))}</td><td>{badge(st["low_any"]["stock_status"])}</td>'
                       f'<td class="num">{money(usd(st["best"]))}</td><td class="num">{money(usd(st["best"]) - usd(st["low_any"]))}</td></tr>' for mid, st in gaps)
    gap_html = (('<div class="tablewrap"><table><thead><tr><th>Model</th><th>Cheapest listing</th><th class="num">Price</th><th>Status</th><th class="num">Cheapest in stock</th><th class="num">Premium</th></tr></thead>'
                 f"<tbody>{gap_rows}</tbody></table></div>") if gaps else "<p>At the last check the cheapest listing for every model was also in stock.</p>")
    spread = []
    for mid in TRACKED:
        ins = sorted(STATS[mid]["in_stock"], key=usd)
        if len(ins) >= 2:
            spread.append((mid, ins[0], ins[-1]))
    spread_rows = "".join(f'<tr><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td><td class="num">{money(usd(lo))}</td><td>{esc(sname(lo["seller"]))}</td><td class="num">{money(usd(hi))}</td><td>{esc(sname(hi["seller"]))}</td>'
                          f'<td class="num">{money(usd(hi) - usd(lo))}</td></tr>' for mid, lo, hi in spread)
    spread_html = (('<div class="tablewrap"><table><thead><tr><th>Model</th><th class="num">Lowest</th><th>Seller</th><th class="num">Highest</th><th>Seller</th><th class="num">Spread</th></tr></thead>'
                    f'<tbody>{spread_rows}</tbody></table></div><p class="hint">Configurations differ (power supply, stand, region), so part of any spread is the bundle, not the seller.</p>')
                   if spread else "<p>No model has two or more in-stock sellers at the last check.</p>")
    top = ranked[0] if ranked else None
    title = (f"Best Bitaxe deals today: {SHORT[top]} cheapest per TH/s ({fmt_day(GEN)}) | Bitaxe Radar" if top else f"Best Bitaxe deals today ({fmt_day(GEN)}) | Bitaxe Radar")
    desc = f"Best Bitaxe deals right now: cheapest in-stock price per model ranked by cost per TH/s, seller discounts, price drops and seller price spread. Updated {fmt_day(GEN)}."
    body = f"""<article>
<header class="hero"><h1>Best Bitaxe deals right now</h1>
<p class="lede">The cheapest in-stock price for each miner, ranked by how much hashrate you get per dollar.</p>
<p class="meta">Data collected {tag_time(latest['generated_at'])}</p></header>
<section aria-labelledby="h-r"><h2 id="h-r">Cheapest in stock, ranked by price per TH/s</h2>{rank_tbl}
<p class="hint">Uses seller-stated hashrate and ignores power cost, shipping and bundle differences.</p></section>
<section aria-labelledby="h-d"><h2 id="h-d">Seller-listed discounts</h2>{disc_html}</section>
<section aria-labelledby="h-c"><h2 id="h-c">Price changes in the last 7 days</h2>{ch_html}</section>
<section aria-labelledby="h-g"><h2 id="h-g">Cheaper listings that are not in stock</h2><p>Some of the lowest prices we see are on sold-out, backorder or pre-order listings. This shows how much more the cheapest in-stock listing costs.</p>{gap_html}</section>
<section aria-labelledby="h-s"><h2 id="h-s">Price spread between sellers (in stock)</h2>{spread_html}</section>
<section><h2>Want a heads-up?</h2><p>Pick a model and a target price on its page and we email you once when it is in stock at or under that price: <a href="/models/bitaxe-gamma/#alerts">set an alert</a>.</p>
<p><a href="/in-stock/">Everything in stock now</a> · <a href="/where-to-buy-bitaxe/">Where to buy</a> · <a href="/bitaxe-black-friday/">Black Friday 2026 tracker</a></p></section>
</article>"""
    items = [(f"{SHORT[m]} {money(usd(STATS[m]['best']))}", f"/models/{m}/") for m in ranked]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Cheapest in-stock Bitaxe-class miners by price per TH/s", items)])


BF_DATES = dict(bf="2026-11-27", cm="2026-11-30")   # Black Friday / Cyber Monday 2026


def build_black_friday():
    path = "/bitaxe-black-friday/"
    trail = [("Home", "/"), ("Black Friday 2026", path)]
    rows, n_at_low = [], 0
    for mid in [m for m in CURRENT_MODELS if m in TRACKED]:
        st, b = STATS[mid], STATS[mid]["best"]
        logged = [to_usd(dict(price=pt["price"], currency=o["currency"])) for o in st["offers"] for pt in hist_pts(o["id"]) if pt.get("in_stock")]
        logged = [x for x in logged if x is not None]
        lo = min(logged) if logged else None
        now = usd(b) if b else None
        if now is not None and lo is not None and now <= lo + 0.005:
            verdict, n_at_low = '<span class="badge in">At our lowest logged price</span>', n_at_low + 1
        elif now is not None and lo is not None:
            verdict = f"{money(now - lo)} above our lowest logged"
        else:
            verdict = "Sold out everywhere we check"
        alert_a = f'<a href="/models/{mid}/#alerts">Get alert</a>'
        rows.append(f'<tr><td><a href="/models/{mid}/">{esc(SHORT[mid])}</a></td><td class="num">{money(now) if now is not None else "&ndash;"}</td>'
                    f'<td>{esc(sname(b["seller"])) if b else "&ndash;"}</td><td class="num">{money(lo) if lo is not None else "&ndash;"}</td><td>{verdict}</td>'
                    f'<td>{offer_link(b, "View ↗") if b else alert_a}</td></tr>')
    tbl = ('<div class="tablewrap"><table><thead><tr><th>Miner</th><th class="num">Cheapest in stock now</th><th>Shop</th><th class="num">Lowest in-stock price we have logged</th><th>Today vs our low</th><th>Buy</th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table></div>')
    first = min((pts[0]["t"] for pts in history.values() if pts), default=latest["generated_at"])
    title = "Bitaxe Black Friday 2026 deals: live prices vs our lowest logged | Bitaxe Radar"
    desc = "Bitaxe and NerdQaxe Black Friday 2026 deals: live in-stock prices from US and EU shops vs the lowest price we have logged."
    body = f"""<article>
<header class="hero"><h1>Bitaxe Black Friday 2026 deals</h1>
<p class="lede">Black Friday is November 27 and Cyber Monday is November 30. We check every shop every 6 hours, so this page shows whether today's price is actually a deal compared with what we've seen.</p>
<p class="meta">Prices checked {tag_time(latest['generated_at'])} · tracking since {esc(fmt_day(first))}</p></header>
<section aria-labelledby="h-t"><h2 id="h-t">Today's price vs our lowest logged</h2>{tbl}
<p class="hint">{n_at_low} of {len(rows)} miners are at the lowest in-stock price we've logged. Prices are before shipping and tax; euro prices are converted to dollars as an estimate.</p></section>
<section aria-labelledby="h-a"><h2 id="h-a">Get a Black Friday price alert</h2><p>Pick a miner and your target price. We email you once when it's in stock at or under that price, so you don't have to refresh shop pages all week.</p>{signup_html("any")}</section>
<section aria-labelledby="h-h"><h2 id="h-h">How to spot a real Black Friday deal</h2><ul>
<li>Compare against the price history on each miner's page, not the shop's "was" price.</li>
<li>Check what's in the box: some bundles include a power supply or stand, some don't.</li>
<li>Stock moves fast on popular models. Sold-out listings drop off the "cheapest in stock" column.</li>
<li>A small miner is a lottery ticket, not an investment. Buy one because you want to run it.</li></ul></section>
<section><h2>More</h2><p><a href="/deals/">Best deals right now</a> · <a href="/in-stock/">Everything in stock</a> · <a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a></p></section>
</article>"""
    layout(path, title, desc, body, crumbs=trail, scripts=SIGNUP_SCRIPTS)


def build_method():
    path = "/how-we-track/"
    trail = [("Home", "/"), ("About & how we track", path)]
    src_rows = "".join(f'<tr><td><a href="/sellers/{sid}/">{esc(s["name"])}</a></td><td>{esc(s["currency"])}</td><td>{esc(SELLER_COPY.get(sid, {}).get("region", ""))}</td></tr>' for sid, s in SELLERS.items())
    title = "How Bitaxe Radar tracks prices and stock (methodology) | Bitaxe Radar"
    desc = "How Bitaxe Radar collects Bitaxe and NerdQaxe prices and stock: sources, schedule, currency conversion, history, which sellers we list and affiliate income."
    body = f"""<article>
<header class="hero"><h1>About Bitaxe Radar</h1>
<p class="lede">We check the shops that sell Bitaxe-style home miners every 6 hours and show you who has each one in stock, and for how much.</p></header>
<section><h2>Where the prices come from</h2>
<p>Straight from each shop's own product pages. We show the price and stock status the shop itself reports, and link you to that page so you can check it. Last check: {tag_time(latest['generated_at'])}.</p>
<div class="tablewrap"><table><thead><tr><th>Shop</th><th>Currency</th><th>Pricing</th></tr></thead><tbody>{src_rows}</tbody></table></div></section>
<section><h2>What a price means</h2><ul>
<li>The shop's listed price for the bundle shown, <strong>before</strong> shipping, import duties and (unless noted) tax.</li>
<li>Euro prices are converted to dollars at the ECB reference rate ({esc(FX.get('EUR_USD', 'n/a'))} on {esc(FX.get('date', ''))}), so treat them as estimates.</li>
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
    n_models = len([m for m in TRACKED if m not in NOINDEX_MODELS])
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
def home_card(mid, best_value):
    st, m = STATS[mid], MODELS[mid]
    b = st["best"]
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
            f'<div class="price">{price}</div><div class="where">{where}</div>'
            f'<div class="row">{status}<a class="btn sm" href="/models/{mid}/" aria-label="See {esc(SHORT[mid])} prices">See prices</a></div>'
            "</div></article>")


def build_home():
    tpl = (ROOT / "templates" / "home.html").read_text()
    t = re.search(r"<title>(.*?)</title>", tpl, re.S).group(1)
    d = re.search(r'<meta name="description" content="(.*?)">', tpl, re.S).group(1)
    items = [(SHORT[m], f"/models/{m}/") for m in CURRENT_MODELS]
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
             f'<li><strong>{len(SELLERS)}</strong> shops checked</li>'
             f'<li>Updated <time id="freshness" datetime="{esc(latest["generated_at"])}">{esc(fmt_time(latest["generated_at"]))}</time></li></ul>')
    best_value = min((m for m in CURRENT_MODELS if STATS[m]["per_th"]), key=lambda m: STATS[m]["per_th"], default=None)
    older = [m for m in TRACKED if m in NOINDEX_MODELS]
    older_html = ('<p class="older">Older models: ' + " · ".join(
        f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' + (f' from {money(usd(STATS[m]["best"]))}' if STATS[m]["best"] else " (sold out)") for m in older) + "</p>") if older else ""
    cards = f"""<section id="miners" aria-labelledby="h-miners">
    <div class="sec-head"><h2 id="h-miners">Today's best prices</h2><a href="/in-stock/">Everything in stock →</a></div>
    <div class="cards">{"".join(home_card(m, best_value) for m in CURRENT_MODELS)}</div>
    {older_html}
  </section>"""
    compare_links = '<ul class="links">' + "".join(f'<li><a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a></li>' for a, b in COMPARE_PAIRS) + "</ul>"
    sellers_line = ('<p>Shops we check: ' + " · ".join(f'<a href="/sellers/{sid}/">{esc(s["name"])}</a>' for sid, s in SELLERS.items() if sid in SELLER_COPY) + "</p>\n  ")
    out = (tpl.replace("<!--HEAD-->", head).replace("<!--HEADER-->", header_html()).replace("<!--RADAR-BG-->", RADAR_BG)
           .replace("<!--HERO-CHIPS-->", chips).replace("<!--CARDS-->", cards).replace("<!--SIGNUP-->", signup_html("any"))
           .replace("<!--COMPARE-LINKS-->", compare_links).replace("<!--FOOTER-->", footer_html(sellers_line))
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
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")


def main():
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
    build_black_friday()
    build_method()
    build_advertise()
    build_404()
    build_home()
    write_sitemap()
    print(f"built {len(PAGES)} indexable pages in sitemap.xml; {len(TRACKED)} model pages ({len(NOINDEX_MODELS & set(TRACKED))} noindex)")


main()
