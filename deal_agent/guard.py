"""The grounding check ("guardrail"): never publish a number the data doesn't back up.

Claude writes the deal; this plain code then checks it against facts.py BEFORE anything is saved.
Two layers:
  1. The structured fields (the JSON from submit_deal): miner, shop, price, typical price, drop %, lowest-ever
     must equal what our data says, and the pick must really be an in-stock deal (drop of 3%+).
  2. The prose (headline + summary): every $ amount and % in the text must be one of the real numbers for
     that miner (rounding allowed: $229.99 may be written $230), no other miner or shop may be named,
     and "lowest ever" style claims need lowest_ever = true in the data.
verify() returns a list of plain-English problems. Empty list = safe to publish.
"""
import math
import re

MAX_HEADLINE = 90
MAX_SUMMARY_CHARS = 420
MAX_SUMMARY_WORDS = 70

MONEY_RE = re.compile(r"(?:US\$|CA\$|\$|€)\s?(\d[\d,]*(?:\.\d+)?)")
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(?:%|percent\b)", re.I)
LOWEST_RE = re.compile(r"lowest[- ](?:price )?ever|all[- ]time low|record low|never been (?:this )?cheaper|"
                       r"lowest (?:price )?(?:we(?:'ve| have)? (?:ever )?(?:seen|logged|tracked|recorded))|cheapest (?:it'?s|it has) ever", re.I)
NEW_LOW_RE = re.compile(r"\bnew (?:all[- ]time |record )?low\b", re.I)
URL_RE = re.compile(r"https?://|www\.|/models/", re.I)


def core_name(name):
    """'NerdQaxe++ (4.8 TH/s)' -> 'NerdQaxe++'. Names are matched without the bracket part."""
    return re.sub(r"\s*\(.*?\)\s*", " ", name).strip()


def close(a, b, tol=0.011):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def written_matches(text_num, value):
    """Does a number as WRITTEN in the prose match a real value? '$230' matches 229.99; '9%' matches 9.0 or 8.97."""
    if value is None:
        return False
    x = float(text_num.replace(",", ""))
    decimals = len(text_num.split(".")[1]) if "." in text_num else 0
    v, scale = abs(float(value)), 10 ** decimals
    # Nearest rounding at the precision written. An exact half (10.5%) may go either way: "about 10%" and "11%"
    # are both honest (interview story #35).
    ok = {math.floor(v * scale + 0.5 + 1e-9) / scale}
    if math.isclose((v * scale) % 1, 0.5, abs_tol=1e-6):
        ok.add(math.floor(v * scale) / scale)
    return any(math.isclose(x, o, abs_tol=1e-9) for o in ok) or close(x, v, 0.005)


def allowed_numbers(pd, f):
    """Every $ amount and % that is TRUE for this miner today (from the same functions the tools use)."""
    money = [f["price_usd"], f["typical_usd"], f["drop_usd"], f["prior_low_usd"], f["window_low_usd"], f["window_high_usd"]]
    if f["currency"] != "USD":
        money.append(f["price"])
    pct = [f["drop_pct"], 3.0]
    for days in (30, 90):
        h = pd.history(f["miner_id"], days)
        if "start" in h:
            money += [h["start"]["usd"], h["latest"]["usd"], h["change_usd"], h["lowest_in_window"]["usd"], h["highest_in_window"]["usd"]]
            pct.append(h["change_pct"])
    return [m for m in money if m is not None], [p for p in pct if p is not None]


def names_in(text, names):
    """Which of `names` appear in text. Longest first, and each match is blanked so 'Bitaxe Gamma' inside
    'Bitaxe Gamma Duo' isn't counted as a second miner."""
    found, t = [], text.lower()
    for n in sorted(set(names), key=len, reverse=True):
        nl = n.lower()
        if nl and re.search(r"(?<![\w+])" + re.escape(nl) + r"(?![\w+])", t):
            found.append(n)
            t = re.sub(r"(?<![\w+])" + re.escape(nl) + r"(?![\w+])", " ", t)
    return found, t


def verify(deal, pd):
    errs = []
    if not isinstance(deal, dict):
        return ["no deal object"]
    headline, summary = str(deal.get("headline") or "").strip(), str(deal.get("summary") or "").strip()
    prose = headline + " \n " + summary
    if not headline or not summary:
        errs.append("headline and summary are required")
    if len(headline) > MAX_HEADLINE:
        errs.append(f"headline is {len(headline)} characters (max {MAX_HEADLINE})")
    if len(summary) > MAX_SUMMARY_CHARS or len(summary.split()) > MAX_SUMMARY_WORDS:
        errs.append(f"summary is too long (max {MAX_SUMMARY_WORDS} words)")
    if URL_RE.search(prose):
        errs.append("no links or page paths in the text (the site adds links)")

    deals = pd.ranked_deals()
    miner_names = {m: core_name(pd.name(m)) for m in pd.models}
    shop_names = [s.get("name", sid) for sid, s in pd.sellers.items()]

    if deal.get("no_standout"):
        if deals:
            errs.append(f"no_standout is false: {deals[0]['miner_name']} is {deals[0]['drop_pct']}% below its typical price and in stock")
        for n in MONEY_RE.findall(prose):
            errs.append(f"${n} in the text: a no-deal day shouldn't quote prices")
        # A % on a no-deal day must still be real: the 3% bar, or some in-stock miner's actual move today (story #40).
        real_pcts = [3.0] + [abs(f["drop_pct"]) for f in pd.all_facts() if f["drop_pct"] is not None]
        for n in PCT_RE.findall(prose):
            if not any(written_matches(n, v) for v in real_pcts):
                errs.append(f"{n}% in the text doesn't match any miner's move today")
        if LOWEST_RE.search(prose) or NEW_LOW_RE.search(prose):
            errs.append("lowest-ever claim on a no-deal day")
        return errs

    mid = deal.get("miner_id") or ""
    f = pd.facts(mid) if mid in pd.models else None
    if mid not in pd.models:
        return errs + [f"unknown miner_id {mid!r}"]
    if not f:
        return errs + [f"{pd.name(mid)} is not in stock anywhere today"]
    if not f["is_deal"]:
        why = "not enough history" if f["typical_usd"] is None else f"only {f['drop_pct']}% below its typical price (needs 3%+)"
        errs.append(f"{f['miner_name']} is not a real deal today: {why}")
    # ---- layer 1: structured fields must equal the data ----
    if str(deal.get("retailer_name", "")).strip().lower() != f["retailer_name"].lower():
        errs.append(f"retailer_name {deal.get('retailer_name')!r} is wrong: cheapest in stock is at {f['retailer_name']}")
    for key in ("price_usd", "typical_usd"):
        if not close(deal.get(key), f[key]):
            errs.append(f"{key} {deal.get(key)} is wrong: data says {f[key]}")
    if not close(deal.get("drop_pct"), f["drop_pct"], 0.051):
        errs.append(f"drop_pct {deal.get('drop_pct')} is wrong: data says {f['drop_pct']}")
    if bool(deal.get("lowest_ever")) != f["lowest_ever"]:
        errs.append(f"lowest_ever {deal.get('lowest_ever')} is wrong: data says {f['lowest_ever']}")
    # ---- layer 2: the prose ----
    money_ok, pct_ok = allowed_numbers(pd, f)
    for n in MONEY_RE.findall(prose):
        if not any(written_matches(n, v) for v in money_ok):
            errs.append(f"${n} in the text doesn't match any {f['miner_name']} price in our data")
    for n in PCT_RE.findall(prose):
        if not any(written_matches(n, v) for v in pct_ok):
            errs.append(f"{n}% in the text doesn't match our data (drop is {f['drop_pct']}%)")
    found, rest = names_in(prose, miner_names.values())
    others = [n for n in found if n != miner_names[mid]]
    if others:
        errs.append(f"names another miner ({', '.join(others)}): only talk about the pick")
    shops, _ = names_in(rest, shop_names)
    wrong_shops = [s for s in shops if s.lower() != f["retailer_name"].lower()]
    if wrong_shops:
        errs.append(f"names a different shop ({', '.join(wrong_shops)}): the price is at {f['retailer_name']}")
    if LOWEST_RE.search(prose) and not f["lowest_ever"]:
        errs.append(f"says lowest ever, but we logged {f['prior_low_usd']} on {f['prior_low_day']}")
    if NEW_LOW_RE.search(prose) and not f["new_low"]:
        errs.append("says new low, but today only matches (or is above) an earlier low")
    return errs
