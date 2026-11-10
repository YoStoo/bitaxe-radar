"""The tools Claude may call. Each one is a small, read-only view of facts.py.

A "tool" is a function we describe to Claude with a name, a description and a JSON schema for its inputs.
Claude can't run code: it replies "please call rank_price_drops with {...}", WE run it, and send the result back.
That's what makes it an agent: it decides which data to look at next, based on what it has seen so far.

Why several small tools and not one big data dump?
  - Each result is small, so a run costs a fraction of a cent.
  - Claude has to investigate (screen, then check history), which is what we grade.
  - Every number it can quote came out of one of these functions, so guard.py can check them.
"""
import json

MAX_LIMIT = 10

LIST_OFFERS = {
    "name": "list_current_offers",
    "description": "Today's cheapest IN-STOCK listing for each miner we track: miner id and name, shop, price in USD "
                   "(and the shop's own currency), and how many shops have it in stock. No history. Sorted by miner name.",
    "strict": True,
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}
RANK_DROPS = {
    "name": "rank_price_drops",
    "description": "Screener: miners whose cheapest in-stock price today is furthest BELOW their typical price "
                   "(median of the cheapest in-stock price on each of the previous 14 days). Biggest drop first. "
                   "Only miners with at least 3 days of history. is_deal = drop of 3% or more.",
    "strict": True,
    "input_schema": {"type": "object", "properties": {
        "limit": {"type": "integer", "description": f"How many to return, 1-{MAX_LIMIT}. Default 5."}},
        "additionalProperties": False},
}
COMPARE = {
    "name": "compare_to_average",
    "description": "For ONE miner: today's cheapest in-stock price vs its typical (14-day median) price, the drop in $ and %, "
                   "the lowest price we logged BEFORE today, and whether today is the lowest ever (ties count) or a new low.",
    "strict": True,
    "input_schema": {"type": "object", "properties": {
        "miner": {"type": "string", "description": "Miner id (e.g. bitaxe-gamma) or name."}},
        "required": ["miner"], "additionalProperties": False},
}
HISTORY = {
    "name": "get_price_history",
    "description": "Price HISTORY for ONE miner from our SQL price database: cheapest in-stock USD price at the start and end "
                   "of the window, the change, the lowest and highest day, and a few dated points. Use it to sanity-check a drop "
                   "(was the old price real for days, or a one-day blip?).",
    "strict": True,
    "input_schema": {"type": "object", "properties": {
        "miner": {"type": "string", "description": "Miner id (e.g. bitaxe-gamma) or name."},
        "days": {"type": "integer", "description": "Days back, 1-90. Default 30."}},
        "required": ["miner"], "additionalProperties": False},
}

# The final answer is a tool too ("structured output"): strict: true makes the API enforce this exact JSON shape.
DEAL_SCHEMA = {
    "type": "object",
    "properties": {
        "working": {"type": "string", "description": "Brief private notes: which candidates you compared and why. Not shown."},
        "no_standout": {"type": "boolean", "description": "true if NO miner is a real deal today (no in-stock drop of 3%+). Then leave miner_id empty."},
        "miner_id": {"type": "string", "description": "The picked miner's id, e.g. bitaxe-gamma. Empty string if no_standout."},
        "retailer_name": {"type": "string", "description": "The shop with today's cheapest in-stock price for it, exactly as the tools wrote it. Empty if no_standout."},
        "price_usd": {"type": "number", "description": "Today's cheapest in-stock price in USD, copied from the tool result. 0 if no_standout."},
        "typical_usd": {"type": "number", "description": "Its typical (14-day median) price from compare_to_average. 0 if no_standout."},
        "drop_pct": {"type": "number", "description": "The drop % from compare_to_average, copied exactly. 0 if no_standout."},
        "lowest_ever": {"type": "boolean", "description": "lowest_ever from compare_to_average. false if no_standout."},
        "headline": {"type": "string", "description": "Max 70 characters. Plain words."},
        "summary": {"type": "string", "description": "2-3 short sentences, max 60 words. Only numbers that appear in your tool results."},
    },
    "required": ["working", "no_standout", "miner_id", "retailer_name", "price_usd", "typical_usd", "drop_pct", "lowest_ever", "headline", "summary"],
    "additionalProperties": False,
}
SUBMIT = {
    "name": "submit_deal",
    "description": "Submit today's deal of the day (or no_standout). Call once, after checking the data. Our code checks every number.",
    "strict": True,
    "input_schema": DEAL_SCHEMA,
}
DATA_TOOLS = [LIST_OFFERS, RANK_DROPS, COMPARE, HISTORY]
ALL_TOOLS = DATA_TOOLS + [SUBMIT]


def _offer_row(pd, f):
    row = dict(miner_id=f["miner_id"], miner_name=f["miner_name"], shop=f["retailer_name"], price_usd=f["price_usd"],
               shops_in_stock=f["shops_in_stock"])
    if f["currency"] != "USD":
        row.update(shop_price=f["price"], shop_currency=f["currency"], note="USD price is converted; small moves can be exchange-rate noise")
    return row


def _compare_row(f):
    keys = ("miner_id", "miner_name", "price_usd", "typical_usd", "drop_usd", "drop_pct", "history_days",
            "prior_low_usd", "prior_low_day", "lowest_ever", "new_low", "is_deal")
    row = {k: f[k] for k in keys} | {"shop": f["retailer_name"]}
    if f["currency"] != "USD":
        row["shop_price"], row["shop_currency"] = f["price"], f["currency"]
    # Say the low-price claim in words, right next to the numbers. The first live eval wrote "lowest we've logged"
    # while copying lowest_ever = false into the JSON (interview story #39).
    if f["new_low"]:
        row["low_claim"] = "New low: lower than any price we logged before today. You may say 'new low' or 'lowest we've logged'."
    elif f["lowest_ever"]:
        row["low_claim"] = "Ties the lowest price we've logged (not a new low). You may say 'lowest we've logged', not 'new low'."
    elif f["prior_low_usd"] is not None:
        row["low_claim"] = (f"NOT the lowest: it was ${f['prior_low_usd']:,.2f} on {f['prior_low_day']}. Do not say lowest, record, "
                            f"all-time or new low. You may say it was cheaper on {f['prior_low_day']}.")
    if f["fx_only"]:
        row["note"] = "The USD drop is exchange-rate movement only: the shop's own price did not go down. Not a deal."
    return row


def run_tool(pd, name, args):
    """Run one tool call. Returns (result_dict, is_error). Never raises: bad input becomes an error Claude can read."""
    args = args if isinstance(args, dict) else {}
    try:
        if name == "list_current_offers":
            rows = [_offer_row(pd, f) for f in sorted(pd.all_facts(), key=lambda f: f["miner_name"])]
            return {"day": pd.today, "offers": rows}, False
        if name == "rank_price_drops":
            limit = args.get("limit", 5)
            if not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
                return {"error": f"limit must be a whole number 1-{MAX_LIMIT}"}, True
            ranked = sorted((f for f in pd.all_facts() if f["typical_usd"] is not None),
                            key=lambda f: (-f["drop_pct"], not f["new_low"], f["price_usd"], f["miner_id"]))
            return {"day": pd.today, "rule": "typical = 14-day median of the daily cheapest in-stock price; a deal = drop of 3%+",
                    "any_deal_today": any(f["is_deal"] for f in ranked), "miners": [_compare_row(f) for f in ranked[:limit]]}, False
        if name in ("compare_to_average", "get_price_history"):
            mid = pd.resolve(args.get("miner", ""))
            if not mid:
                return {"error": f"No single miner matches {args.get('miner')!r}. Use an id from list_current_offers."}, True
            if name == "get_price_history":
                days = args.get("days", 30)
                if not isinstance(days, int) or not 1 <= days <= 90:
                    return {"error": "days must be a whole number 1-90"}, True
                return pd.history(mid, days), False
            f = pd.facts(mid)
            if not f:
                return {"miner_id": mid, "note": "Not in stock anywhere today, so it can't be the deal of the day."}, False
            return _compare_row(f), False
        return {"error": f"Unknown tool {name!r}."}, True
    except Exception as e:  # a tool bug must not crash the run; Claude sees an error and we log it
        return {"error": f"tool failed: {type(e).__name__}"}, True


def as_text(result):
    return json.dumps(result, separators=(",", ":"))
