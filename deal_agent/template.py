"""The no-AI fallback: a deal written from a fixed template, straight from facts.py.

Used when Claude's output fails the grounding check twice. Boring on purpose: every number is
copied from the data, so it always passes guard.verify() (a test proves it on every eval case).
"""


def money(v):
    return f"${v:,.2f}"


def pct(v):
    return f"{v:g}%"


def template_deal(pd):
    deals = pd.ranked_deals()
    if not deals:
        return dict(working="template", no_standout=True, miner_id="", retailer_name="", price_usd=0, typical_usd=0, drop_pct=0,
                    lowest_ever=False, headline="No standout deal today",
                    summary="No miner we track is at least 3% below its typical price of the last 14 days. "
                            "Prices are steady, so there's no rush today.")
    f = deals[0]
    low = " That's the lowest price we've logged for it." if f["lowest_ever"] else ""
    return dict(working="template", no_standout=False, miner_id=f["miner_id"], retailer_name=f["retailer_name"],
                price_usd=f["price_usd"], typical_usd=f["typical_usd"], drop_pct=f["drop_pct"], lowest_ever=f["lowest_ever"],
                headline=f"{pct(f['drop_pct'])} off its typical price at {f['retailer_name']}"[:90],
                summary=f"It's {money(f['price_usd'])} today, in stock at {f['retailer_name']}. Its typical price over the last 14 days "
                        f"was {money(f['typical_usd'])}, so that's {money(f['drop_usd'])} ({pct(f['drop_pct'])}) less.{low}")
