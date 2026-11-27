"""HTML for the deal of the day (homepage card, /deals/ box, /deals/daily/ archive). Used by build_site.py.

Pure functions: build_site.py passes in the live listing and the link HTML (made by its own offer_link(), so
affiliate codes work exactly like every other shop link on the site). Every bit of AI text is HTML-escaped.
"""
import html
from datetime import date

HOME_MAX_AGE_DAYS = 2        # an old deal (agent not running) quietly drops off the homepage; the archive keeps it
EMPTY_ARCHIVE = "No deal of the day yet. A deal shows up here on days when a miner is at least 3% under its typical price."


def is_real(rec):
    """Only real deal days are public. No-deal days stay in data/deals_history.json for our records, never on the site."""
    return bool(rec) and not rec.get("no_standout") and bool(rec.get("miner_id"))


def real_deals(history):
    return [r for r in history if is_real(r)]


def esc(s):
    return html.escape(str(s), quote=True)


def money(v):
    return f"${v:,.2f}"


def nice_date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def is_fresh(rec, today):
    return is_real(rec) and (date.fromisoformat(today) - date.fromisoformat(rec["date"])).days <= HOME_MAX_AGE_DAYS


def price_line(rec):
    """One short sentence under the price, e.g. "26.6% under its typical $293, the lowest we've logged." """
    typ = rec["typical_usd"]
    typ_txt = f"${typ:,.0f}" if abs(typ - round(typ)) < 0.005 else money(typ)
    low = ", the lowest we've logged" if rec.get("lowest_ever") else ""
    return f'{rec["drop_pct"]:g}% under its typical {typ_txt}{low}.'


def deal_box(rec, live=None, link_html="", *, compact=False, img_html=""):
    """The card. live = today's listing for the picked offer (or None if it's gone), link_html = the shop button,
    img_html = the miner's photo. Short on purpose: photo, name, price, one sentence, button.
    Empty on a no-deal day: we show nothing rather than "no deal today"."""
    if not is_real(rec):
        return ""
    head = f'<small>Deal of the day · {esc(nice_date(rec["date"]))}</small>'
    now = ""
    if live is None or live.get("stock_status") != "in_stock":
        now = '<p class="hint dotd-now">Sold out since we picked it. <a href="/models/{0}/">See other shops →</a></p>'.format(esc(rec["miner_id"]))
        link_html = ""
    elif abs((live.get("price_usd_approx") or 0) - rec["price_usd"]) > 0.005:
        now = f'<p class="hint dotd-now">Price has changed since we picked it: now {money(live["price_usd_approx"])}.</p>'
    img = f'<a class="dotd-img" href="/models/{esc(rec["miner_id"])}/" tabindex="-1" aria-hidden="true">{img_html}</a>' if img_html else ""
    body = (f'{img}<h3><a href="/models/{esc(rec["miner_id"])}/">{esc(rec["miner_name"])}</a></h3>'
            f'<p class="dotd-price"><b>{money(rec["price_usd"])}</b> <span class="dotd-at">at {esc(rec["retailer_name"])}</span></p>'
            f'<p class="dotd-line">{esc(price_line(rec))}</p>'
            + now + link_html)
    more = '<p class="hint"><a href="/deals/daily/">Past deals of the day →</a></p>' if compact else ""
    return f'<section class="dotd" aria-label="Deal of the day">{head}{body}{more}</section>'


def archive_rows(history):
    rows = []
    for r in real_deals(history):
        pick = f'<a href="/models/{esc(r["miner_id"])}/">{esc(r["miner_name"])}</a> at {esc(r["retailer_name"])}'
        price = f'{money(r["price_usd"])} ({r["drop_pct"]:g}% under {money(r["typical_usd"])})'
        src = "AI, checked" if r.get("source") == "ai" else "Template"
        rows.append(f'<tr><td>{esc(nice_date(r["date"]))}</td><td>{pick}<div class="hint">{esc(r["headline"])}</div></td>'
                    f'<td class="num">{price}</td><td>{src}</td></tr>')
    return "".join(rows)


HOW_IT_WORKS = """<section id="how" aria-labelledby="h-how"><h2 id="h-how">How the deal of the day works</h2>
<ol>
<li>Every day, after we check the shops, an AI agent looks through our price data with a few tools: today's prices,
each miner's price history from our database, and a comparison with its typical price.</li>
<li>It picks the in-stock miner that is furthest below its <b>typical price</b> (the middle price of the last 14 days),
if anything is at least 3% lower. On days when nothing is, there's simply no deal of the day, which is normal.</li>
<li>It writes a two-line summary. Then our code checks every price, percentage and shop name against the data
before anything is published. If a number doesn't match, the AI gets one chance to fix it; after that we publish a plain
template version instead. So the page never shows a made-up number.</li>
</ol>
<p class="hint">Prices change fast. The price shown is the one at our check; the shop's page has the current price.
Shop links may be affiliate links, labelled "affiliate link".</p></section>"""
