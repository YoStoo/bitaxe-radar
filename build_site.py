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
METHODOLOGY_UPDATED = "2026-10-16"      # bump when the hand-written methodology text changes
NETWORK_EH_ILLUSTRATION = 1000          # EH/s, round number for the lottery illustration only (labelled as such on pages)
BLOCKS_PER_YEAR = 52560                 # 144 blocks/day * 365
ELEC_RATES = (0.10, 0.15, 0.25)         # $/kWh scenarios (assumptions, labelled as such)

latest = json.loads((ROOT / "data" / "latest.json").read_text())
history = json.loads((ROOT / "data" / "history.json").read_text())
latest = dict(latest, unscrapable=[u for u in latest["unscrapable"] if not u.get("internal")])

# ---------------------------------------------------------------------------------------------
# 1) data.js for the interactive home page (unchanged behaviour)
# ---------------------------------------------------------------------------------------------
payload = {"latest": latest, "history": history}
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


def offer_link(o, text=None):
    aff = aff_param(o["seller"])
    rel = "sponsored nofollow noopener" if aff else "nofollow noopener"
    t = text or f"View at {sname(o['seller'])} ↗"
    a = f'<a class="btn" href="{esc(offer_href(o))}" target="_blank" rel="{rel}">{esc(t)}</a>'
    return a + ('<div class="ph">affiliate link</div>' if aff else "")


def best_cta(st):
    """Above-the-fold 'go to the best deal' box: cheapest in-stock listing, plus the cheapest USD-priced one if different."""
    best, usd_best = st["best"], st["best_usd"]
    if not best:
        return ""
    picks = [("Cheapest in stock", best)]
    if usd_best and usd_best["id"] != best["id"]:
        picks.append(("Cheapest in stock at a US-dollar seller", usd_best))
    items = "".join(
        f'<div><small>{esc(lbl)}</small><b>{money(o["price"], o["currency"])}</b>'
        + (f' <span class="hint">≈ {money(usd(o))}</span>' if o["currency"] != "USD" and usd(o) is not None else "")
        + f' <span class="hint">at {esc(sname(o["seller"]))}</span><br>{offer_link(o, "Check price at " + sname(o["seller"]) + " ↗")}</div>'
        for lbl, o in picks)
    return f'<div class="cta" role="region" aria-label="Best deal right now">{items}</div>'


SPONSOR_SLOT = ('<aside class="sponsor" aria-label="Sponsor spot"><small>Sponsor spot</small> '
                '<span>Sell Bitaxe-class miners or accessories? This spot is open. Sponsored placements are always labelled and never change our price rankings. '
                '<a href="/advertise/">Advertise on Bitaxe Radar</a></span></aside>')


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
        check=["Whether a power supply is included: Bitcoin Merch's listing title does not say, so we flag it as unverified.",
               "Cooling: look for the fan and heatsink setup the seller ships.",
               "Seller-quoted hashrate ranges are optimistic ranges, not guarantees."]),
    "nerdaxe-gamma": dict(
        intro="The Nerdaxe Gamma is a Gamma-class board (one BM1370 chip) with a color display, from the Nerdaxe line rather than the Bitaxe line. Sellers state the same ballpark hashrate and power as the Bitaxe Gamma, about 1.2 TH/s at 18 W, so the question is mainly whether the display and enclosure are worth the price difference.",
        who="Buyers who like the Gamma's numbers but want a built-in screen to see status at a glance.",
        check=["Compare against the Bitaxe Gamma's price: the silicon is the same class, so you are paying for display and case.",
               "Region variant: Power Mining lists a US version; Bitaxe.de prices include VAT.",
               "Stock changes quickly, so check the status column before planning around it."]),
    "nerdaxe-gaia": dict(
        intro="The Nerdaxe Gaia uses a newer BM1373 chip. Sellers state 2.4–2.6 TH/s at about 25 W, which is the best hashrate-per-watt of the miners we track on paper. It is also one of the pricier small miners, and as a newer design it has fewer long-term user reports than the Gamma family.",
        who="Buyers who care most about efficiency and are willing to pay a premium for a newer chip.",
        check=["Efficiency figures are vendor-stated; treat them as targets rather than measurements.",
               "Pre-order listings may ship weeks later: read the shipping note on the seller's page.",
               "Prices can differ a lot between sellers, so compare the config column."]),
    "nerdqaxe-pp": dict(
        intro="The NerdQaxe++ combines four BM1370 chips on one board. The standard version is stated at about 4.8 TH/s and 80 W; some sellers also list newer revisions (Rev 6.1 at roughly 6 TH/s and about 100 W, and Rev 7) that are not the same product at the same price. It is the highest-hashrate miner on this site, and it is closer to a small space heater than the single-chip boards.",
        who="Hobbyists who want the most hashrate from a compact open-source miner and have somewhere to put the heat and fan noise.",
        check=["Revision: 4.8 TH/s standard, Rev 6.1 and Rev 7 are different configurations, so read the config column before comparing prices.",
               "Fan and stand options change the price (Solo Satoshi lists them as separate choices).",
               "Power: at around 80 W or more it needs a proper supply rated for it."]),
    "bitaxe-supra": dict(
        intro="The Bitaxe Supra uses the older BM1368 chip at about 0.6–0.7 TH/s and 15 W. It has largely been superseded by the Gamma, which our data shows is available for similar money, so this page exists mostly for people who find an old listing and want to know what it is.",
        who="Mostly people who already own one. A new buyer will usually get more hashrate per dollar from a Gamma.",
        check=["Compare against a current Gamma listing before buying an older board.",
               "Make sure a power supply is included."]),
    "bitaxe-ultra": dict(
        intro="The Bitaxe Ultra uses the older BM1366 chip at about 0.4–0.5 TH/s and 12 W. We track one listing for it. It is slower than the current Gamma at a similar price, so this page is for reference.",
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
        about="Bitcoin Merch lists most of the Bitaxe-family miners we track, priced in US dollars, and most of its listing titles say a power supply is included.",
        notes=["We read prices and stock from the store's public Shopify product feed.",
               "Most titles say 'w/ Power Supply'. The Bitaxe GT 801 title does not, so our config column marks it unverified.",
               "Prices are before shipping and sales tax. We have not verified its shipping regions or return terms, so check at checkout."]),
    "solosatoshi": dict(
        region="USD prices",
        about="Solo Satoshi sells Bitaxe-family miners priced in US dollars, with a North America power-supply option.",
        notes=["Stock is read per option (variation) from the store's public API, because the product-level 'in stock' flag can be wrong for variable products: we saw it report in stock while every option was sold out.",
               "The price we show is for the North America power supply with no stand or extra fan, since that is the closest to apples-to-apples with other sellers' bundles.",
               "We have not verified its shipping regions or return terms, so check at checkout."]),
    "powermining": dict(
        region="EUR prices (US variant listed)",
        about="Power Mining prices in euros and lists a US variant for some miners. We convert to dollars only to compare, so the dollar figures are approximate.",
        notes=["Prices and stock come from the store's public Shopify feed. The feed's 'available' flag is true even for pre-orders, so we also read the product page and mark pre-orders as such.",
               "Its page quotes a ship date for pre-orders; we show the seller's own wording in the config column when we have it.",
               "The tax basis of its prices is not stated on the page and shipping and import duties are not included, so the real US price will be higher than the figure shown.",
               "Its product-page FAQ says it ships to the US and Canada (express 2-4 days, standard 4-6 days, customs delays possible), and its affiliate page says it stocks US and EU warehouses."]),
    "bitaxede": dict(
        region="EUR prices incl. VAT",
        about="Bitaxe.de is a European shop. Its prices are in euros and include VAT, and shipping is extra.",
        notes=["We read prices and stock from the schema.org data on each product page. Its home page and product pages sometimes disagree about stock, so we use the product page.",
               "Its own partner-program page describes delivery to the EU plus Switzerland, Norway, Iceland and Liechtenstein; we have not verified delivery to the US.",
               "Because VAT is included and shipping is not, its dollar-approximate prices are not directly comparable to a US shop's pre-tax prices."]),
}

NAV = [("/", "Home"), ("/where-to-buy-bitaxe/", "Where to buy"), ("/in-stock/", "In stock"), ("/deals/", "Deals"), ("/how-we-track/", "How we track")]


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


FOOT_DISCLOSURE = ('<strong>Affiliate disclosure:</strong> some seller links on Bitaxe Radar are affiliate links (labelled "affiliate link", with rel="sponsored"). '
                   "If you buy through one we may earn a commission at no extra cost to you. Affiliate status never changes how offers are ranked or sorted. "
                   'See <a href="/how-we-track/">how we track prices</a>.')


def layout(path, title, desc, body, *, crumbs=None, jsonld=(), noindex=False, lastmod=None, scripts="", og_type="website", index_in_sitemap=True):
    url = BASE + (path if path != "/404.html" else "/")
    desc = shorten(desc, 158)
    title = shorten(title, 90)
    ld = list(jsonld)
    if crumbs:
        ld.append(breadcrumb_ld(crumbs))
    nav = "".join(f'<a href="{p}">{esc(n)}</a>' for p, n in NAV)
    robots = '<meta name="robots" content="noindex,follow">\n' if noindex else ""
    canon = f'<link rel="canonical" href="{esc(url)}">\n' if path != "/404.html" else ""
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
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
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
  <a class="brand" href="/"><span class="dot" aria-hidden="true"></span> Bitaxe Radar</a>
  <nav aria-label="Main">{nav}</nav>
</div></header>
<div class="notice lottery" role="note"><div class="wrap"><strong>Solo mining is a lottery, not income.</strong> A Bitaxe-class miner has a tiny chance of ever finding a block. Treat any purchase as a hobby expense. Nothing here is financial advice.</div></div>
<main class="wrap" id="main">
{crumbs_html(crumbs) if crumbs else ""}
{body}
</main>
<footer class="foot"><div class="wrap">
  <p>{FOOT_DISCLOSURE}</p>
  <p>Prices and stock are collected automatically from public seller pages and can be wrong or out of date: check the seller's page before buying. Bitaxe Radar is an independent project, not affiliated with the Bitaxe project, Open Source Miners United or any seller listed.</p>
  <p><a href="/how-we-track/">How we track</a> · <a href="/where-to-buy-bitaxe/">Where to buy</a> · <a href="/deals/">Deals</a> · <a href="/advertise/">Advertise</a> · <a href="mailto:{CONTACT}">{CONTACT}</a></p>
</div></footer>
{scripts}{ANALYTICS}
</body>
</html>
"""
    out = SITE / "404.html" if path == "/404.html" else SITE / path.strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    if index_in_sitemap and not noindex:
        PAGES.append(dict(path=path, lastmod=lastmod or latest["generated_at"]))


def offers_table(offers, *, show_model=False, best_id=None):
    rows = []
    for o in offers:
        cur = money(o["price"], o["currency"])
        approx = f'<div class="cfg">≈ {money(usd(o))}</div>' if o["currency"] != "USD" and usd(o) is not None else ""
        cmp_at = f'<div class="cfg">seller-listed was {money(o["compare_at"], o["currency"])}</div>' if o.get("compare_at") and o["compare_at"] > o["price"] else ""
        cfg = esc(o["config"]) + (f" · {esc(o['ship_note'])}" if o.get("ship_note") else "") + (
            f" · {o['variants_in_stock']}/{o['variants_total']} options in stock" if o.get("variants_total") else "")
        best = ' class="best"' if best_id and o["id"] == best_id else ""
        tagb = '<span class="tag-best">Best in-stock</span>' if best_id and o["id"] == best_id else ""
        stale = '<div class="stale">stale data</div>' if o.get("stale") else ""
        first = (f'<td><a href="/models/{o["model"]}/">{esc(SHORT[o["model"]])}</a></td>' if show_model else "")
        rows.append(f'<tr{best}>{first}<td><a href="/sellers/{esc(o["seller"])}/">{esc(sname(o["seller"]))}</a>{tagb}{stale}</td>'
                    f'<td class="num">{cur}{approx}{cmp_at}</td><td>{badge(o["stock_status"])}</td><td class="cfg">{cfg}</td>'
                    f'<td class="cfg">{tag_time(o["checked_at"])}</td><td>{offer_link(o)}</td></tr>')
    head = ("<th>Model</th>" if show_model else "") + '<th>Seller</th><th class="num">Price</th><th>Stock</th><th>Config</th><th>Checked</th><th>Buy</th>'
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
    W, Hh, ml, mr, mt, mb = 900, 300, 56, 16, 14, 34
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
        g.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#2a2f3a"/><text x="{ml - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="#9aa3b2" font-size="12">${v:.0f}</text>')
    g.append(f'<text x="{ml}" y="{Hh - 10}" fill="#9aa3b2" font-size="12">{fmt_day(tmin)}</text><text x="{W - mr}" y="{Hh - 10}" text-anchor="end" fill="#9aa3b2" font-size="12">{fmt_day(tmax)}</text>')
    legend = []
    for o, col, pts in series:
        if len(pts) > 1:
            g.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{" ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v, _ in pts)}"/>')
        for t, v, p in pts:
            fill = col if p.get("in_stock") else "#0f1115"
            g.append(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="4" fill="{fill}" stroke="{col}" stroke-width="2"><title>{esc(sname(o["seller"]))}: {esc(money(p["price"], p["currency"]))} ({esc(STATUS.get(p["status"], p["status"]))}) {esc(fmt_time(p["t"]))}</title></circle>')
        legend.append(f'<span><i style="background:{col}"></i>{esc(sname(o["seller"]))}</span>')
    legend.append("<span>● filled = in stock, ○ hollow = not in stock at that point</span>")
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


HIST_NOTE = ('<p class="hint">A data point is logged when a seller\'s price or stock changes, and at least about once a day otherwise, so points are not evenly spaced. '
             "Nothing is back-filled: the log only covers the time we have been tracking. EUR prices are converted at the latest ECB reference rate, so exchange-rate moves show up as small changes on those lines.</p>")


# ---- signup form ---------------------------------------------------------------------------
def signup_html(default_model="any"):
    if not SIGNUP_ENABLED:
        return ""
    opts = '<option value="any">Any tracked miner</option>' + "".join(
        f'<option value="{esc(m)}"{" selected" if m == default_model else ""}>{esc(MODELS[m]["name"])}</option>' for m in TRACKED)
    return f"""<section id="alerts" aria-labelledby="h-alerts">
<h2 id="h-alerts">Get an email when the price drops</h2>
<form id="signup" class="signup" novalidate>
  <p id="signupIntro"><strong>Get one email when a miner drops to your price.</strong> Pick a miner and a target price (USD). We email you only when it is <em>in stock</em> at or under that price. Free; unsubscribe with one click.</p>
  <div class="row">
    <label>Email <input type="email" id="email" name="email" autocomplete="email" placeholder="you@example.com" maxlength="254" required></label>
    <label>Miner <select id="alertModel" name="model">{opts}</select></label>
    <label>Alert me at or under (USD) <input type="number" min="1" max="100000" step="1" id="alertPrice" name="target_price" placeholder="e.g. 120" inputmode="numeric" required></label>
  </div>
  <div style="position:absolute;left:-9999px" aria-hidden="true"><label>Website <input type="text" id="website" name="website" tabindex="-1" autocomplete="off"></label></div>
  <div class="row signup-actions"><div id="turnstile" class="turnstile-slot"></div><button type="submit" id="signupBtn">Notify me</button></div>
  <p class="hint">Double opt-in: we send one confirmation email, and you only start getting alerts after you click the link in it. At most about one alert per price per week. Your email is only used for these alerts and is never sold.</p>
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
        head = (f'cheapest in stock right now: <strong>{money(usd(best))}</strong> at {esc(sname(best["seller"]))}'
                + (f' ({esc(money(best["price"], best["currency"]))}, converted)' if best["currency"] != "USD" else "") + f'. In stock at {n_in} of {plural(st["sellers"], "tracked seller")}.')
        title = f"{short} price: {money(usd(best))} in stock ({day}) | Bitaxe Radar"
        desc = (f"{short} prices at {plural(st['sellers'], 'seller')}: cheapest in stock {money(usd(best))} at {sname(best['seller'])}, "
                f"listed {money(usd(low))}–{money(usd(st['high_any']))}. Stock, price log, running cost. Updated {day}.")
    else:
        head = (f'<strong>not in stock at any tracked seller at the last check.</strong> Lowest listed price: {money(usd(low))} at {esc(sname(low["seller"]))} ({esc(STATUS[low["stock_status"]].lower())}).')
        title = f"{short} price: sold out or pre-order only ({day}) | Bitaxe Radar"
        desc = (f"{short} at {plural(st['sellers'], 'seller')}: none has it in stock at the last check ({day}). "
                f"Lowest listed {money(usd(low))} at {sname(low['seller'])}. Stock status, price log and price alerts.")

    kp = [("Cheapest in stock", money(usd(best)) if best else "none in stock"),
          ("Lowest listed (any status)", money(usd(low))),
          ("In stock at", f"{n_in} of {st['sellers']} sellers"),
          ("Last checked", None)]
    kpis = '<div class="kpis">' + "".join(
        f'<div><small>{esc(k)}</small><b>{tag_time(st["checked"]) if v is None else esc(v)}</b></div>' for k, v in kp) + "</div>"

    usd_best = st["best_usd"]
    if usd_best and best and usd_best["id"] != best["id"]:
        us_note = f'<p>Cheapest in stock at a USD-priced seller: <strong>{money(usd_best["price"])}</strong> at {esc(sname(usd_best["seller"]))}.</p>'
    elif not usd_best:
        us_note = "<p>No USD-priced seller has it in stock at the last check. Prices from euro sellers are converted for comparison and will not include shipping, VAT differences or import duties.</p>"
    else:
        us_note = ""
    avail_note = ""
    if best and low and low["id"] != best["id"] and not in_stock(low):
        avail_note = (f'<p class="hint">The lowest listed price, {money(usd(low))} at {esc(sname(low["seller"]))}, is <strong>{esc(STATUS[low["stock_status"]].lower())}</strong>, '
                      f'so the cheapest in-stock price is {money(usd(best))}, which is {money(usd(best) - usd(low))} higher.</p>')

    offers_html = offers_table(sort_offers(st["offers"]), best_id=best["id"] if best else None)

    per_th = st["per_th"]
    rows = [("Stated hashrate", f"≈ {m['hashrate_ths']:g} TH/s (vendor-stated)"),
            ("Stated power", f"≈ {m['watts']:g} W (vendor-stated)"),
            ("Efficiency", f"≈ {jth(mid):.1f} J/TH, {ordinal(EFF_RANK[mid])} best of {len(TRACKED)} tracked models"),
            ("Chip", m["chip"]),
            ("Price per TH/s at cheapest in-stock price", (f"{money(per_th)} per TH/s, {ordinal(PTH_RANK[mid])} cheapest of {len(PTH_RANK)} models with stock") if per_th else "n/a, none in stock"),
            ("Energy used", f"≈ {kwh_year(mid):,.0f} kWh per year if run 24/7")]
    spec_tbl = '<div class="tablewrap"><table><tbody>' + "".join(f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in rows) + "</tbody></table></div>"
    kwh = kwh_year(mid)
    elec_tbl = ('<div class="tablewrap"><table><thead><tr><th>Electricity price (assumption)</th>' + "".join(f'<th class="num">${r:.2f}/kWh</th>' for r in ELEC_RATES) + "</tr></thead>"
                f'<tbody><tr><th scope="row">Yearly cost, 24/7</th>{"".join(f"<td class=num>${kwh * r:,.0f}</td>" for r in ELEC_RATES)}</tr></tbody></table></div>')
    spec_note = f'<p class="hint">{esc(m["note"])}. Watts are approximate vendor-stated typical figures and move with firmware overclocking, fans and power-supply efficiency. The <a href="/#cost">home page calculator</a> lets you enter your own electricity rate and wattage.</p>'

    yrs = lottery_years(mid)
    lottery = (f'<p>A solo miner does not earn a steady income: it either finds a whole block (a very large reward) or nothing. As a rough illustration only, if the whole network were {NETWORK_EH_ILLUSTRATION:,} EH/s (a round number we chose, not today\'s figure: look up the current one), '
               f'a miner at {m["hashrate_ths"]:g} TH/s would be expected to find a block about once every <strong>{sig2(yrs)} years</strong> on average, and most years it finds nothing. '
               f'Electricity is a real cost every year either way. If you want one, buy it as a hobby and for learning, not as an investment.</p>')

    rel_c = related_compare(mid)
    rel_links = "".join(f'<li><a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a></li>' for a, b in rel_c)
    others = [x for x in TRACKED if x != mid and x not in NOINDEX_MODELS][:6]
    other_links = "".join(f'<li><a href="/models/{x}/">{esc(SHORT[x])}</a>' + (f' <span class="hint">from {money(usd(STATS[x]["best"]))} in stock</span>' if STATS[x]["best"] else ' <span class="hint">none in stock</span>') + "</li>" for x in others)

    chart = chart_svg(mid)
    log = history_log_table(mid)
    hist_html = chart + log + HIST_NOTE if (chart or log) else "<p>No history logged yet for this model.</p>"
    firsts = [h["first"] for o in st["offers"] for h in [hist_summary(o)] if h]
    first_day = min(firsts) if firsts else None
    hist_intro = (f"<p>We have been tracking since {esc(fmt_day(first_day))}. " + (
        "There are not enough data points yet to draw a trend line, so the table below is the honest summary." if not chart else "Lines appear once a seller has more than one logged point.") + "</p>") if first_day else ""

    faq = []
    if best:
        a1 = (f"At our last check ({fmt_time(st['checked'])}) the cheapest in-stock listing was {money(usd(best))} at {sname(best['seller'])}"
              + (f", from {money(best['price'], best['currency'])}" if best["currency"] != "USD" else "") + ". Prices exclude shipping and tax; configs differ, so read the config column.")
    else:
        a1 = f"Nothing is in stock at the tracked sellers right now. The lowest listed price is {money(usd(low))} at {sname(low['seller'])}, which is {STATUS[low['stock_status']].lower()}."
    faq.append((f"What is the cheapest {short} right now?", a1, False))
    stock_lines = "; ".join(f"{sname(o['seller'])}: {STATUS[o['stock_status']].lower()}" for o in sort_offers(st["offers"]))
    faq.append((f"Is the {short} in stock?", f"At the last check: {stock_lines}. Stock changes within minutes, so confirm on the seller's page.", False))
    faq.append((f"How much electricity does the {short} use?",
                f"Sellers state about {m['watts']:g} W, which is roughly {kwh:,.0f} kWh a year if it runs 24/7. At $0.10, $0.15 and $0.25 per kWh that is about ${kwh * 0.10:,.0f}, ${kwh * 0.15:,.0f} and ${kwh * 0.25:,.0f} a year.", False))
    faq.append((f"Can a {short} make money?",
                f"Almost certainly not. It is a solo lottery miner: at an illustrative {NETWORK_EH_ILLUSTRATION:,} EH/s network the expected time to a block is about {sig2(yrs)} years, while electricity costs money every year. Buy it as a hobby.", False))
    faq.append((f"How do I get notified when the {short} price drops?",
                "Use the alert form on this page: pick a target price and we email you once when it is in stock at or under it. It is free, needs an email confirmation, and unsubscribes in one click.", False))
    if rel_c:
        a, b = rel_c[0]
        faq.append((f"How does the {short} compare with other miners?", f'See our side-by-side page: <a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a>.', True))
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{a if raw else esc(a)}</p></details>" for q, a, raw in faq)

    check_html = "".join(f"<li>{esc(c)}</li>" for c in cp["check"])
    body = f"""<article>
<header class="hero"><h1>{esc(short)} price and stock</h1>
<p class="lede">{esc(m['name'])}: {head}</p></header>
{kpis}
{best_cta(st)}
{us_note}{avail_note}
<section aria-labelledby="h-offers"><h2 id="h-offers">Prices by seller</h2>
<p class="hint">Listed price for the configuration shown, before shipping, import duties and (where noted) tax. Euro prices are converted to USD only as an approximation (EUR→USD ≈ {FX.get('EUR_USD', 'n/a')}, {esc(FX.get('date', ''))}). Updated about every 6 hours.</p>
{offers_html}
<p class="hint">Not listed here: sellers we cannot read yet. See <a href="/where-to-buy-bitaxe/#not-tracked">sellers not tracked yet</a>.</p></section>
{SPONSOR_SLOT}
<section aria-labelledby="h-hist"><h2 id="h-hist">Price and stock history</h2>{hist_intro}{hist_html}</section>
<section aria-labelledby="h-nums"><h2 id="h-nums">Numbers that matter</h2>{spec_tbl}{elec_tbl}{spec_note}</section>
<section aria-labelledby="h-about"><h2 id="h-about">About the {esc(short)}</h2>
<p>{esc(cp['intro'])}</p>
<p><strong>Who it suits:</strong> {esc(cp['who'])}</p>
<h3>Check before you buy</h3><ul>{check_html}</ul></section>
<section aria-labelledby="h-lot"><h2 id="h-lot">Is it worth it? The lottery maths</h2>{lottery}</section>
{signup_html(mid)}
<section aria-labelledby="h-faq"><h2 id="h-faq">Frequently asked questions</h2>{faq_html}</section>
<section aria-labelledby="h-more"><h2 id="h-more">Keep comparing</h2>
{"<h3>Side by side</h3><ul>" + rel_links + "</ul>" if rel_links else ""}
<h3>Other miners we track</h3><ul>{other_links}</ul>
<p><a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a> · <a href="/in-stock/">Everything in stock now</a> · <a href="/deals/">Best deals</a></p></section>
</article>"""

    offer_ld = []
    for o in sort_offers(st["offers"]):
        offer_ld.append({"@type": "Offer", "url": o["url"], "price": f'{o["price"]:.2f}', "priceCurrency": o["currency"],
                         "availability": AVAIL.get(o["stock_status"], "https://schema.org/OutOfStock"),
                         "seller": {"@type": "Organization", "name": sname(o["seller"]), "url": SELLERS[o["seller"]]["url"]}})
    product = {"@context": "https://schema.org", "@type": "Product", "name": m["name"],
               "description": shorten(cp["intro"], 300), "url": BASE + path}
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
<p class="hint">Hashrate and power are vendor-stated approximations. Higher hashrate raises your lottery odds in proportion, but the odds stay tiny either way.</p></section>
<section aria-labelledby="h-t"><h2 id="h-t">Side by side</h2>{tbl}</section>
<section aria-labelledby="h-w"><h2 id="h-w">Which one fits you?</h2>
<p><strong>Pick the {esc(sa)} if</strong> {esc(cc['a_for'])}</p>
<p><strong>Pick the {esc(sb)} if</strong> {esc(cc['b_for'])}</p>
<p>Neither is an income source. See the lottery maths on each model page.</p></section>
<section aria-labelledby="h-a"><h2 id="h-a">Where to buy the {esc(sa)}</h2>{best_block(a, ta)}</section>
<section aria-labelledby="h-b"><h2 id="h-b">Where to buy the {esc(sb)}</h2>{best_block(b, tb)}</section>
<section aria-labelledby="h-al"><h2 id="h-al">Price alerts</h2><p>Want a nudge when one of them drops? Use the form on the <a href="/models/{a}/#alerts">{esc(sa)} page</a> or the <a href="/models/{b}/#alerts">{esc(sb)} page</a>.</p></section>
<section><h2>More comparisons</h2><ul>{olinks}</ul></section>
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
    tbl = ('<div class="tablewrap"><table><thead><tr><th>Model</th><th class="num">Price</th><th>Stock</th><th>Versus other sellers</th><th>Checked</th><th>Buy</th></tr></thead>'
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
    aff_txt = (f"Links to {esc(s['name'])} on this site are <strong>affiliate links</strong>: if you buy after clicking, we may earn a commission at no extra cost to you. It does not change how we rank or sort offers."
               if aff else f"We have no affiliate arrangement with {esc(s['name'])} right now, so our links to it are plain links and we earn nothing if you buy.")
    notes = "".join(f"<li>{esc(n)}</li>" for n in cp["notes"])
    unverified = '<p class="hint">Shipping regions, delivery times, warranty and return terms are <strong>not</strong> verified by us for any seller yet. Read the seller\'s own policy pages before you pay.</p>'
    title = f"{s['name']} Bitaxe prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"{s['name']}: {len(offs)} Bitaxe-family miners tracked, {n_in} in stock now ({cp['region']}). Prices, stock log, affiliate status."
    body = f"""<article>
<header class="hero"><h1>{esc(s['name'])}: prices and stock</h1><p class="lede">{esc(cp['about'])}</p>
<p class="meta">{summary}</p></header>
<section aria-labelledby="h-p"><h2 id="h-p">What {esc(s['name'])} has right now</h2>{tbl}
<p class="hint">Store: <a href="{esc(s['url'])}" rel="nofollow noopener" target="_blank">{esc(s['url'].replace('https://', ''))}</a>. Prices are before shipping and tax.</p></section>
<section aria-labelledby="h-l"><h2 id="h-l">Stock and price log</h2>{log}</section>
<section aria-labelledby="h-n"><h2 id="h-n">How we read this seller</h2><ul>{notes}</ul>{unverified}</section>
<section aria-labelledby="h-a"><h2 id="h-a">Affiliate status</h2><p>{aff_txt}</p></section>
<section><h2>See also</h2><p><a href="/where-to-buy-bitaxe/">Where to buy a Bitaxe</a> · <a href="/in-stock/">Everything in stock now</a> · <a href="/how-we-track/">How we track prices</a></p></section>
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
        aff = "yes, affiliate links" if aff_param(sid) else "none, plain links"
        return (f'<tr><td><a href="/sellers/{sid}/">{esc(s["name"])}</a></td><td>{esc(cp["region"])}</td><td class="num">{len(offs)}</td><td class="num">{n_in}</td>'
                f'<td>{esc(aff)}</td><td class="cfg">{tag_time(max(o["checked_at"] for o in offs))}</td></tr>')
    sellers_tbl = ('<div class="tablewrap"><table><thead><tr><th>Seller</th><th>Pricing</th><th class="num">Models tracked</th><th class="num">In stock now</th><th>Affiliate?</th><th>Last checked</th></tr></thead>'
                   f'<tbody>{"".join(seller_row(s) for s in usd_sellers + eur_sellers)}</tbody></table></div>')
    unt = "".join(f"<li><strong>{esc(u['seller'])}:</strong> {esc(u['reason'])}</li>" for u in latest["unscrapable"])
    title = f"Where to buy a Bitaxe in the US: prices and stock ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = (f"Where to buy a Bitaxe or NerdQaxe: {len(SELLERS)} sellers tracked, {len(ins_usd)} USD-priced listings in stock. "
            f"Cheapest in-stock Gamma {money(g['best_usd']['price']) if g['best_usd'] else 'n/a'}. Updated {fmt_day(GEN)}.")
    body = f"""<article>
<header class="hero"><h1>Where to buy a Bitaxe (US-first)</h1>
<p class="lede">Which tracked sellers have each miner in stock, and at what price. We lead with sellers that price in US dollars, and keep the European shops listed below them for comparison.</p>
<p class="meta">Data collected {tag_time(latest['generated_at'])}</p></header>
<section aria-labelledby="h-q"><h2 id="h-q">The short answer today</h2><ul>{qa_html}</ul></section>
<section aria-labelledby="h-m"><h2 id="h-m">Cheapest in stock at a USD-priced seller</h2>
{model_summary_table(CURRENT_MODELS, usd_only=True)}
<p class="hint">"None in stock" means no USD-priced seller we track has it available at the last check. Euro-priced shops may still have it: open the model page. Prices exclude shipping and sales tax. Whether a seller ships to your address is for you to confirm at checkout.</p></section>
<section aria-labelledby="h-s"><h2 id="h-s">Sellers we track</h2>{sellers_tbl}
<p class="hint">USD-priced sellers come first. "Plain links" means we earn nothing if you buy there. Euro-priced sellers are converted to dollars for comparison only, and real US cost will differ with shipping, VAT and import duties.</p></section>
<section aria-labelledby="h-c"><h2 id="h-c">Before you buy: a checklist</h2><ul>
<li><strong>What is in the box.</strong> Power supply, stand and fan are included by some sellers and sold separately by others. A cheap listing without a power supply is not cheaper.</li>
<li><strong>Which revision.</strong> Gamma 601 vs 602, NerdQaxe++ 4.8 TH/s vs Rev 6.1 vs Rev 7: they are different products at different prices.</li>
<li><strong>Pre-order or in stock.</strong> Pre-order and backorder items can take weeks. We label these separately.</li>
<li><strong>Total cost.</strong> Add shipping, sales tax or import duty, and the electricity to run it.</li>
<li><strong>Payment safety.</strong> Be wary of a price far below every other seller, or a shop that only takes wire or crypto. We only list sellers we have looked at.</li>
<li><strong>Look-alikes.</strong> Prefer sellers that name the exact board and revision in the title.</li></ul></section>
<section id="not-tracked" aria-labelledby="h-n"><h2 id="h-n">Sellers we cannot track yet</h2>
<p>These shops exist but we cannot read their stock automatically yet, so they are not in our tables. Check them yourself if you want a wider search.</p><ul class="plain">{unt}</ul></section>
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
        notes.append("No tracked seller has these in stock: " + ", ".join(f'<a href="/models/{m}/">{esc(SHORT[m])}</a>' for m in none) + ".")
    n_sellers = len({o["seller"] for o in ins})
    title = f"Bitaxe in stock now: {len(ins)} listings at {plural(n_sellers, 'seller')} ({fmt_day(GEN)}) | Bitaxe Radar"
    desc = f"What is in stock right now: {len(ins)} of {len(OFFERS)} tracked Bitaxe, Nerdaxe and NerdQaxe listings, plus {len(pre)} pre-order or backorder. Updated {fmt_day(GEN)}."
    body = f"""<article>
<header class="hero"><h1>Bitaxe and NerdQaxe in stock now</h1>
<p class="lede">{len(ins)} of {len(OFFERS)} tracked listings are in stock at the last check. Another {len(pre)} are pre-order or backorder (not in stock yet) and {len(oos)} are sold out.</p>
<p class="meta">Data collected {tag_time(latest['generated_at'])}. Refreshed about every 6 hours.</p></header>
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
    first_t = min(parse_t(p[0]["t"]) for p in history.values() if p)
    ch_rows = "".join(f'<tr><td><a href="/models/{o["model"]}/">{esc(SHORT[o["model"]])}</a></td><td>{esc(sname(o["seller"]))}</td><td class="num">{money(old, o["currency"])}</td><td class="num">{money(new, o["currency"])}</td>'
                      f'<td class="num">{(new / old - 1) * 100:+.1f}%</td><td>{esc(fmt_day(t))}</td></tr>' for o, old, new, t in ch)
    ch_html = (f'<div class="tablewrap"><table><thead><tr><th>Model</th><th>Seller</th><th class="num">Was</th><th class="num">Now</th><th class="num">Change</th><th>When</th></tr></thead><tbody>{ch_rows}</tbody></table></div>'
               if ch else f"<p>No price changes logged in the last 7 days. We started tracking on {esc(fmt_day(first_t))}, so there is not much history yet; this list fills in as prices move.</p>")
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
<p class="lede">A "deal" here is the cheapest in-stock price for each miner, ranked by dollars per stated TH/s, so you can compare a cheap small miner with an expensive big one. Everything on this page is recalculated from live seller data.</p>
<p class="meta">Data collected {tag_time(latest['generated_at'])}</p></header>
<section aria-labelledby="h-r"><h2 id="h-r">Cheapest in stock, ranked by price per TH/s</h2>{rank_tbl}
<p class="hint">Hashrate is the vendor-stated figure, and "price per TH/s" ignores power cost, shipping and bundle differences. Lowest is not automatically best: see the model page for configs.</p></section>
<section aria-labelledby="h-d"><h2 id="h-d">Seller-listed discounts</h2>{disc_html}</section>
<section aria-labelledby="h-c"><h2 id="h-c">Price changes in the last 7 days</h2>{ch_html}</section>
<section aria-labelledby="h-g"><h2 id="h-g">Cheaper listings that are not in stock</h2><p>Some of the lowest prices we see are on sold-out, backorder or pre-order listings. This shows how much more the cheapest in-stock listing costs.</p>{gap_html}</section>
<section aria-labelledby="h-s"><h2 id="h-s">Price spread between sellers (in stock)</h2>{spread_html}</section>
<section><h2>Want a heads-up?</h2><p>Pick a model and a target price on its page and we email you once when it is in stock at or under that price: <a href="/models/bitaxe-gamma/#alerts">set an alert</a>.</p>
<p><a href="/in-stock/">Everything in stock now</a> · <a href="/where-to-buy-bitaxe/">Where to buy</a></p></section>
</article>"""
    items = [(f"{SHORT[m]} {money(usd(STATS[m]['best']))}", f"/models/{m}/") for m in ranked]
    layout(path, title, desc, body, crumbs=trail, jsonld=[itemlist("Cheapest in-stock Bitaxe-class miners by price per TH/s", items)])


def build_method():
    path = "/how-we-track/"
    trail = [("Home", "/"), ("How we track prices", path)]
    src_rows = "".join(f'<tr><td><a href="/sellers/{sid}/">{esc(s["name"])}</a></td><td>{esc(s["currency"])}</td><td>{esc(s["method"])}</td></tr>' for sid, s in SELLERS.items())
    unt = "".join(f"<li><strong>{esc(u['seller'])}:</strong> {esc(u['reason'])}</li>" for u in latest["unscrapable"])
    title = "How Bitaxe Radar tracks prices and stock (methodology) | Bitaxe Radar"
    desc = "How Bitaxe Radar collects Bitaxe and NerdQaxe prices and stock: sources, schedule, currency conversion, history, excluded sellers and affiliate income."
    body = f"""<article>
<header class="hero"><h1>How we track prices and stock</h1>
<p class="lede">Bitaxe Radar is a price and stock tracker for small solo Bitcoin miners. This page explains where the numbers come from, what they leave out, and how the site earns money.</p></header>
<section><h2>Where the data comes from</h2>
<p>An automated job reads each seller's own public product pages or product feeds about every 6 hours. We read the price and the stock status the seller itself reports, and we link to the seller's product page so you can check it. Last collection: {tag_time(latest['generated_at'])}.</p>
<div class="tablewrap"><table><thead><tr><th>Seller</th><th>Currency</th><th>How we read it</th></tr></thead><tbody>{src_rows}</tbody></table></div>
<p>The job identifies itself with a descriptive user agent, makes about one request per product page, and backs off when a site asks it to.</p></section>
<section><h2>What a price means</h2><ul>
<li>It is the seller's listed price for the configuration shown in the Config column, <strong>before</strong> shipping, import duties and (unless noted) tax.</li>
<li>Euro prices are converted to US dollars only so sellers can be compared. We use the ECB reference rate from Frankfurter (latest: {esc(FX.get('EUR_USD', 'n/a'))} on {esc(FX.get('date', ''))}). Treat converted figures as approximate.</li>
<li>Bundles differ (power supply, stand, fan, region, revision). We say what we could verify and mark what we could not.</li>
<li>"Stated" hashrate and power are vendor-stated approximations, not our measurements. We have not benchmarked any miner.</li></ul></section>
<section><h2>What "in stock" means</h2><p>We call a listing in stock only when the seller reports it available now. Pre-order and backorder are shown separately because they usually ship later. Some shops report stock unreliably (for example a product-level flag that says in stock while every option is sold out), so we read stock per option where we can. Stock can change within minutes, so always confirm on the seller's page.</p></section>
<section><h2>How the history works</h2><p>We log a data point whenever a seller's price or stock status changes, and at least about once a day otherwise. We do not back-fill and we do not invent history: charts only cover the time we have been tracking, and several models have only a few points so far.</p></section>
<section><h2>Which sellers we list</h2><p>We list sellers whose public data we can read and whose pricing looks consistent with the rest of the market. We deliberately leave out shops we have not been able to vet, for example those with prices far below every other seller or only wire/crypto payment, because listing a bad shop would hurt readers. We have not verified shipping regions, warranty or return terms for any seller yet.</p>
<h3>Sellers we cannot read yet</h3><ul class="plain">{unt}</ul></section>
<section><h2>How Bitaxe Radar earns money</h2>
<p>Some seller links are affiliate links: if you buy through one, we may earn a commission at no extra cost to you. Those links are labelled "affiliate link" and carry rel="sponsored". We never change prices, rankings or sort order because of affiliate status: offers are ordered by stock and price. If we ever take a seller sponsorship, it will be labelled (see <a href="/advertise/">advertise</a>). Right now only Power Mining links are affiliate links.</p>
<p>We do not publish ratings or reviews, because we have not tested the hardware. We do not give financial advice. Solo mining with a small miner is a lottery: the expected return is negative once electricity is counted.</p></section>
<section><h2>Spotted a mistake?</h2><p>Prices and stock are collected by software and can be wrong. If you see an error or are a seller who wants a listing corrected, write to <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>
<p><a href="/where-to-buy-bitaxe/">Where to buy</a> · <a href="/in-stock/">In stock now</a> · <a href="/deals/">Deals</a></p></section>
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
<p class="lede">Bitaxe Radar tracks prices and stock for Bitaxe-class solo miners across {plural(len(SELLERS), 'seller')} and {plural(len(OFFERS), 'listing')}. People land here when they are deciding where to buy, which is the moment a seller wants to be seen.</p></header>
<section><h2>What is available</h2><ul>
<li><strong>Featured seller spot</strong> on our {n_models} model pages, right under the price table, labelled "Sponsored".</li>
<li><strong>Accessory spot</strong> for stands, cases, heatsinks, fans and power supplies.</li>
<li><strong>Get listed in the tracker</strong>: if you sell Bitaxe-class miners and we don't track you yet, write to us. Being listed in the price table is free and never paid for.</li></ul></section>
<section><h2>The rules</h2><ul>
<li>Every sponsored placement is clearly labelled and uses rel="sponsored" links.</li>
<li>Sponsors never change price rankings, sort order or stock data. The cheapest in-stock listing is always shown first.</li>
<li>We only take sponsors we would be comfortable sending readers to (real stock, consistent prices, normal payment methods).</li></ul></section>
<section><h2>Honest numbers</h2><p>The site launched in October 2026, so we do not have meaningful visitor numbers yet and will not make any up. Early sponsors get introductory pricing, and we'll share real traffic figures as soon as we have them.</p>
<p><a class="btn" href="{esc(mail)}">Email {CONTACT}</a></p></section>
<p><a href="/how-we-track/">How we track prices and earn money</a> · <a href="/where-to-buy-bitaxe/">Where to buy</a></p>
</article>"""
    layout(path, title, desc, body, crumbs=trail, lastmod=METHODOLOGY_UPDATED)


def build_404():
    body = '<article><header class="hero"><h1>Page not found</h1><p class="lede">That page does not exist. Try the <a href="/">home page</a>, <a href="/in-stock/">what is in stock now</a> or <a href="/where-to-buy-bitaxe/">where to buy</a>.</p></header></article>'
    layout("/404.html", "Page not found | Bitaxe Radar", "This page does not exist on Bitaxe Radar.", body, noindex=True, index_in_sitemap=False)


# ---------------------------------------------------------------------------------------------
# HOME PAGE (template + pre-rendered summary)
# ---------------------------------------------------------------------------------------------
def build_home():
    tpl = (ROOT / "templates" / "home.html").read_text()
    t = re.search(r"<title>(.*?)</title>", tpl, re.S).group(1)
    d = re.search(r'<meta name="description" content="(.*?)">', tpl, re.S).group(1)
    head = f"""<link rel="canonical" href="{BASE}/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta property="og:site_name" content="Bitaxe Radar"><meta property="og:type" content="website">
<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">
<meta property="og:url" content="{BASE}/"><meta property="og:image" content="{BASE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
{jsonld_tag({"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "@id": BASE + "/#org", "name": "Bitaxe Radar", "url": BASE + "/", "email": CONTACT},
    {"@type": "WebSite", "@id": BASE + "/#site", "name": "Bitaxe Radar", "url": BASE + "/", "publisher": {"@id": BASE + "/#org"}}]})}"""
    ins = [o for o in OFFERS if in_stock(o)]
    summary = f"""<section id="summary" aria-labelledby="h-sum">
    <h2 id="h-sum">Cheapest in stock right now</h2>
    <p class="hint">{len(ins)} of {len(OFFERS)} tracked listings are in stock · data collected {tag_time(latest['generated_at'])}. Each model has its own page with every seller, history and an alert form.</p>
    {model_summary_table(TRACKED)}
    <p class="hint"><a href="/where-to-buy-bitaxe/">Where to buy (US-first)</a> · <a href="/in-stock/">Everything in stock</a> · <a href="/deals/">Best deals</a> · <a href="/how-we-track/">How we track</a></p>
  </section>"""
    foot = ('<p><a href="/where-to-buy-bitaxe/">Where to buy</a> · <a href="/in-stock/">In stock now</a> · <a href="/deals/">Deals</a> · <a href="/how-we-track/">How we track</a> · <a href="/advertise/">Advertise</a> · '
            + " · ".join(f'<a href="{compare_url(a, b)}">{esc(compare_label(a, b))}</a>' for a, b in COMPARE_PAIRS) + "</p>\n  <p>Sellers: "
            + " · ".join(f'<a href="/sellers/{sid}/">{esc(s["name"])}</a>' for sid, s in SELLERS.items()) + "</p>")
    out = tpl.replace("<!--HEAD-->", head).replace("<!--SEO-SUMMARY-->", summary).replace("<!--FOOT-LINKS-->", foot).replace("</body>", ANALYTICS + "</body>")
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
    build_method()
    build_advertise()
    build_404()
    build_home()
    write_sitemap()
    print(f"built {len(PAGES)} indexable pages in sitemap.xml; {len(TRACKED)} model pages ({len(NOINDEX_MODELS & set(TRACKED))} noindex)")


main()
