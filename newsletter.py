"""Home Mining Weekly: one JSON file per issue in data/newsletter/, frozen price snapshot inside it.

  python3 newsletter.py snapshot data/newsletter/issue-001.json   # (re)fill "prices" from data/latest.json
  python3 newsletter.py render   data/newsletter/issue-001.json   # write docs/newsletter/<slug>.html + .txt

build_site.py imports this module to publish /newsletter/ and /newsletter/<slug>/ from the same files.
Nothing here sends email. A future issue = copy the JSON, edit the words and model lists, snapshot, render.
"""
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DIR = ROOT / "data" / "newsletter"
BASE = "https://bitaxeradar.com"
CONTACT = "contact@bitaxeradar.com"
ET = ZoneInfo("America/New_York")
UNSUB = "{{NL_UNSUBSCRIBE_URL}}"   # the sender fills a per-recipient Worker /nl/unsubscribe link (newsletter-only; NOT Resend's global unsubscribe, which would also stop price alerts)
POSTAL = "[mailing address goes here before sending]"   # required by law in sent email; never shown on the web page
DISCLOSURE = ("Some shop links are affiliate links. If you buy through one, Bitaxe Radar may earn a commission "
              "at no extra cost to you. It never changes how prices are ranked.")
NO_PROMISE = "Mining earnings are never guaranteed. Prices change fast, so check the shop's page before buying. Not financial advice."


def esc(s):
    return html.escape(str(s), quote=True)


def _affiliates():
    app = (ROOT / "site" / "app.js").read_text()
    m = re.search(r"var AFFILIATE\s*=\s*\{(.*?)\};", app, re.S)
    return dict(re.findall(r'(\w+)\s*:\s*"([^"]+)"', m.group(1))) if m else {}


AFFILIATE = _affiliates()


def with_aff(url, code):
    """Add a shop's affiliate code to a URL. Codes ending in "/" are path style (Solo Satoshi: .../product/x/aff/8840/),
    appended to the path with exactly one slash, keeping any query string; anything else is a query param (?ref=...)."""
    if not code:
        return url
    if code.endswith("/"):
        base, sep, rest = url.partition("?")
        frag = ""
        if not sep:
            base, sep2, f = base.partition("#")
            frag = sep2 + f
        code = code.strip("/") + "/"
        if not base.rstrip("/").endswith("/" + code.rstrip("/")):
            base = base.rstrip("/") + "/" + code
        return base + (sep + rest if sep else "") + frag
    return url + ("&" if "?" in url else "?") + code


def href(p):
    return with_aff(p["url"], AFFILIATE.get(p["seller"]))


def money(v, cur="USD"):
    return {"USD": "$", "EUR": "€", "CAD": "CA$"}.get(cur, cur + " ") + f"{v:,.2f}"


def et_time(iso):
    d = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(ET)
    return f"{d:%b} {d.day}, {d.year}, {d.strftime('%I:%M %p').lstrip('0')} ET"


def pretty_date(day):
    d = datetime.strptime(day, "%Y-%m-%d")
    return f"{d:%B} {d.day}, {d.year}"


def load(path):
    return json.loads(Path(path).read_text())


def issues():
    """All issues that have a price snapshot, newest first."""
    out = [load(p) for p in sorted(DIR.glob("issue-*.json"))]
    return sorted([i for i in out if i.get("prices")], key=lambda i: i["num"], reverse=True)


def snapshot(path):
    issue, latest = load(path), json.loads((ROOT / "data" / "latest.json").read_text())
    models, sellers = latest["models"], latest["sellers"]

    def best(mid):
        ins = [o for o in latest["offers"] if o["model"] == mid and o["stock_status"] == "in_stock" and o.get("price_usd_approx")]
        if not ins:
            return None
        o = min(ins, key=lambda o: o["price_usd_approx"])
        return dict(model=mid, name=models[mid]["name"], hashrate_ths=models[mid]["hashrate_ths"], watts=models[mid]["watts"],
                    seller=o["seller"], seller_name=sellers[o["seller"]]["name"], price=o["price"], currency=o["currency"],
                    price_usd=o["price_usd_approx"], url=o["url"], checked_at=o["checked_at"])
    issue["prices"] = sorted([p for p in (best(m) for m in issue["price_models"]) if p], key=lambda p: p["price_usd"])
    for n in issue["new_miners"]:
        n["name"] = models[n["model"]]["name"]
        b = best(n["model"])
        n["from_usd"] = b["price_usd"] if b else None
    issue["snapshot_at"] = latest["generated_at"]
    Path(path).write_text(json.dumps(issue, indent=2, ensure_ascii=False) + "\n")
    return issue


def price_label(p):
    s = money(p["price"], p["currency"])
    return s + (f" (≈{money(p['price_usd'])})" if p["currency"] != "USD" else "")


def web_url(issue):
    return f"{BASE}/newsletter/{issue['slug']}/"


# ---------------------------------------------------------------- email (inline styles, table layout, light theme)
NAVY, ORANGE, INK, MUTED, LINE = "#0b1222", "#f7931a", "#1b2333", "#5b6475", "#e3e7ee"


def email_html(issue):
    btn = (f'display:inline-block;background:{ORANGE};color:#1a1100;font-weight:700;text-decoration:none;'
           'padding:12px 18px;border-radius:8px;font-size:16px')
    h2 = f'margin:28px 0 10px;font-size:19px;line-height:1.3;color:{INK}'
    rows = "".join(
        f'<tr><td style="padding:10px 0;border-top:1px solid {LINE}"><a href="{BASE}/models/{p["model"]}/" style="color:{INK};font-weight:700;text-decoration:none">{esc(p["name"])}</a>'
        f'<br><span style="color:{MUTED};font-size:13px">at {esc(p["seller_name"])} · in stock</span></td>'
        f'<td align="right" style="padding:10px 0;border-top:1px solid {LINE};white-space:nowrap"><a href="{esc(href(p))}" style="color:{INK};font-weight:800;font-size:17px;text-decoration:none">{esc(price_label(p))}</a></td></tr>'
        for p in issue["prices"])
    new = "".join(
        f'<li style="margin:0 0 10px"><a href="{BASE}/models/{n["model"]}/" style="color:{INK};font-weight:700">{esc(n["name"])}</a>'
        + (f' <span style="color:{MUTED}">· from {money(n["from_usd"])}</span>' if n.get("from_usd") else "")
        + f'<br><span style="color:{MUTED}">{esc(n["blurb"])}</span></li>' for n in issue["new_miners"])
    ex = issue["explainer"]
    paras = "".join(f'<p style="margin:0 0 12px">{esc(t)}</p>' for t in ex["paras"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{esc(issue["subject"])}</title></head>
<body style="margin:0;padding:0;background:#f3f5f9">
<div style="display:none;max-height:0;overflow:hidden">{esc(issue["preheader"])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f5f9"><tr><td align="center" style="padding:16px 10px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;font:16px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{INK}">
<tr><td style="background:{NAVY};padding:18px 22px">
  <a href="{BASE}/" style="color:#ffffff;text-decoration:none;font-size:18px;font-weight:800">Bitaxe <span style="color:{ORANGE}">Radar</span></a>
  <div style="color:#aab6cf;font-size:13px;margin-top:2px">Home Mining Weekly · Issue #{issue["num"]} · {pretty_date(issue["date"])}</div>
</td></tr>
<tr><td style="padding:22px">
<p style="margin:0 0 6px">{esc(issue["intro"])}</p>

<h2 style="{h2}">This week's best prices</h2>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:15px">{rows}</table>
<p style="margin:8px 0 0;color:{MUTED};font-size:13px">Cheapest in-stock listing we found, checked {esc(et_time(issue["snapshot_at"]))}. Prices change fast. <a href="{BASE}/deals/" style="color:{MUTED}">See today's live prices</a>.</p>

<h2 style="{h2}">3 new miners on the site</h2>
<ul style="margin:0;padding-left:20px">{new}</ul>
<p style="margin:4px 0 0"><a href="{BASE}/miners/" style="color:{INK}">Browse all miners →</a></p>

<h2 style="{h2}">Not sure which one fits you?</h2>
<p style="margin:0 0 14px">Answer 3 quick questions and we'll suggest a miner.</p>
<p style="margin:0"><a href="{BASE}/find-my-miner/" style="{btn}">Take the Find my miner quiz</a></p>

<h2 style="{h2}">{esc(ex["title"])}</h2>
{paras}<p style="margin:0"><a href="{BASE}{ex["link"]}" style="color:{INK}">Read the 2-minute guide →</a></p>

<h2 style="{h2}">Want a heads-up when a price drops?</h2>
<p style="margin:0 0 14px">Pick a miner and your price. We email you once when it's in stock at or under it.</p>
<p style="margin:0"><a href="{BASE}/alerts/" style="{btn}">Set a free price alert</a></p>
</td></tr>
<tr><td style="padding:18px 22px;border-top:1px solid {LINE};color:{MUTED};font-size:12.5px;line-height:1.5">
<p style="margin:0 0 8px">{esc(DISCLOSURE)}</p>
<p style="margin:0 0 8px">{esc(NO_PROMISE)}</p>
<p style="margin:0 0 8px">You're getting this because you signed up for Home Mining Weekly on bitaxeradar.com. Questions? Reply or write <a href="mailto:{CONTACT}" style="color:{MUTED}">{CONTACT}</a>.</p>
<p style="margin:0 0 8px">Bitaxe Radar · {esc(POSTAL)}</p>
<p style="margin:0"><a href="{UNSUB}" style="color:{MUTED}">Unsubscribe</a> · <a href="{web_url(issue)}" style="color:{MUTED}">View on the web</a></p>
</td></tr>
</table></td></tr></table>
</body></html>
"""


def email_text(issue):
    L = [f"HOME MINING WEEKLY #{issue['num']} · {pretty_date(issue['date'])}", "Bitaxe Radar", "", issue["intro"], "",
         "THIS WEEK'S BEST PRICES", f"(cheapest in-stock listing, checked {et_time(issue['snapshot_at'])})"]
    L += [f"- {p['name']}: {price_label(p)} at {p['seller_name']}\n  {href(p)}" for p in issue["prices"]]
    L += [f"Live prices: {BASE}/deals/", "", "3 NEW MINERS ON THE SITE"]
    L += [f"- {n['name']}" + (f" (from {money(n['from_usd'])})" if n.get("from_usd") else "") + f": {n['blurb']}\n  {BASE}/models/{n['model']}/"
          for n in issue["new_miners"]]
    ex = issue["explainer"]
    L += ["", "NOT SURE WHICH ONE FITS YOU?", f"Take the 3-question Find my miner quiz: {BASE}/find-my-miner/", "",
          ex["title"].upper()] + ex["paras"] + [f"Guide: {BASE}{ex['link']}", "",
          "PRICE-DROP ALERTS", f"Get one email when a miner hits your price: {BASE}/alerts/", "", "--", DISCLOSURE, NO_PROMISE,
          f"You're getting this because you signed up for Home Mining Weekly on bitaxeradar.com. Questions? Reply or write {CONTACT}.",
          f"Bitaxe Radar · {POSTAL}", f"Unsubscribe: {UNSUB}", f"View on the web: {web_url(issue)}", ""]
    return "\n".join(L)


def render(path):
    issue = load(path)
    out = ROOT / "docs" / "newsletter"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{issue['slug']}.html").write_text(email_html(issue))
    (out / f"{issue['slug']}.txt").write_text(email_text(issue))
    return out / f"{issue['slug']}.html", out / f"{issue['slug']}.txt"


if __name__ == "__main__":
    cmd, p = sys.argv[1], sys.argv[2]
    print(snapshot(p)["snapshot_at"] if cmd == "snapshot" else render(p))
