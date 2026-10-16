#!/usr/bin/env python3
"""Send price-drop alert emails to confirmed Bitaxe Radar subscribers via Resend. Stdlib only.

Flow: read data/latest.json -> list Resend contacts (paginated) -> for every confirmed
(unsubscribed == false) contact find in-stock offers at/below the contact's target price ->
send ONE email with the best offer -> record last_alert_price / last_alert_at on the contact.

Env (live mode): RESEND_API_KEY, SIGNING_SECRET (same value as the Worker; used for unsubscribe links),
                 PUBLIC_BASE (the Worker URL, e.g. https://subscribe.bitaxeradar.com)
Optional env:    ALERT_FROM (default "Bitaxe Radar <alerts@bitaxeradar.com>")

Examples:
  python3 scripts/send_alerts.py --dry-run --contacts-fixture tests/fixtures/contacts.json   # offline, sends nothing
  RESEND_API_KEY=... SIGNING_SECRET=... PUBLIC_BASE=... python3 scripts/send_alerts.py        # live
"""
import argparse, base64, hashlib, hmac, html, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTACT = "contact@bitaxeradar.com"
FROM = os.environ.get("ALERT_FROM", "Bitaxe Radar <alerts@bitaxeradar.com>")
POSTAL = "Bitaxe Radar, mailing-address-removed"
SITE_URL = "https://bitaxeradar.com"
RESEND = os.environ.get("RESEND_API_BASE", "https://api.resend.com")  # override only for local tests
REALERT_AFTER = timedelta(days=7)
MAX_OFFER_AGE = timedelta(hours=48)   # ignore offers whose last check is older than this
DAILY_STOP = 90                       # Resend free plan = 100 emails/day; stop at 90 (leave headroom for confirmation emails)


# ---------- small utils ----------
def parse_iso(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def iso(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None

def b64u(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def sign_token(payload, secret):
    """Same format as worker/src/index.js signToken(): b64u(json) + '.' + b64u(HMAC-SHA256(secret, b64u(json)))."""
    body = b64u(json.dumps(payload, separators=(",", ":")).encode())
    return body + "." + b64u(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())

def money(v, cur):
    sym = {"USD": "$", "EUR": "€"}.get(cur)
    return f"{sym}{v:,.2f}" if sym else f"{cur} {v:,.2f}"


# ---------- data ----------
def load_affiliates(app_js):
    """Parse `var AFFILIATE = { powermining: "ref=bitaxeradar" };` from site/app.js (single source of truth)."""
    try:
        src = Path(app_js).read_text()
    except OSError:
        return {}
    m = re.search(r"var\s+AFFILIATE\s*=\s*\{(.*?)\}\s*;", src, re.S)
    return dict(re.findall(r'["\']?([\w-]+)["\']?\s*:\s*"([^"]*)"', m.group(1))) if m else {}

def offer_link(o, aff):
    p = aff.get(o["seller"])
    if not p:
        return o["url"], False
    return o["url"] + ("&" if "?" in o["url"] else "?") + p, True

def contact_props(c):
    """Return flat {key: value} from either Resend's {key: {value, type}} shape or a flat dict."""
    out = {}
    for k, v in (c.get("properties") or {}).items():
        out[k] = v.get("value") if isinstance(v, dict) and "value" in v else v
    return out

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

def resolve_models(wanted, models):
    """Map the contact's model property (id, 'any', or free text) to a set of model ids. Empty set = unrecognised."""
    w = (wanted or "any").strip()
    if w.lower() == "any":
        return set(models)
    if w in models:
        return {w}
    nw = norm(w)
    if not nw:
        return set()
    exact = {mid for mid, m in models.items() if norm(m["name"]) == nw or norm(mid) == nw}
    if exact:
        return exact
    return {mid for mid, m in models.items() if nw in norm(m["name"]) or nw in norm(mid)}


# ---------- matching / dedupe ----------
def eligible(o, now):
    if not o.get("in_stock") or o.get("stale") or o.get("price_usd_approx") is None:
        return False
    t = parse_iso(o.get("checked_at"))
    return t is not None and now - t <= MAX_OFFER_AGE

def find_match(props, latest, now):
    """Return {'best', 'alt', 'model_ids'} or None. US-first: cheapest USD-seller offer wins; EU (converted) only if no US match.
    `alt` = cheapest match from the other region (shown as an extra line)."""
    target = num(props.get("target_price"))
    if target is None:
        return None
    ids = resolve_models(props.get("model"), latest["models"])
    hits = [o for o in latest["offers"] if o["model"] in ids and eligible(o, now) and o["price_usd_approx"] <= target + 1e-9]
    if not hits:
        return None
    us = sorted((o for o in hits if o["currency"] == "USD"), key=lambda o: o["price_usd_approx"])
    eu = sorted((o for o in hits if o["currency"] != "USD"), key=lambda o: o["price_usd_approx"])
    best = (us or eu)[0]
    alt = (eu[0] if us and eu else None)
    return {"best": best, "alt": alt, "model_ids": ids}

def should_alert(props, price, now):
    """Dedupe: alert if never alerted, or the price is lower than the last alerted price, or the last alert was >= 7 days ago."""
    lp, la = num(props.get("last_alert_price")), parse_iso(props.get("last_alert_at"))
    if lp is None or la is None:
        return True, "first alert"
    if price < lp - 0.005:
        return True, f"price dropped further (${lp:.2f} -> ${price:.2f})"
    if now - la >= REALERT_AFTER:
        return True, "7+ days since last alert"
    return False, f"already alerted at ${lp:.2f} on {la:%Y-%m-%d}"


# ---------- email ----------
def build_email(email, props, match, latest, aff, unsub_url):
    best, alt = match["best"], match["alt"]
    models = latest["models"]
    mname = models[best["model"]]["name"]
    seller = latest["sellers"].get(best["seller"], {}).get("name", best["seller"])
    price = best["price_usd_approx"]
    target = num(props.get("target_price"))
    link, is_aff = offer_link(best, aff)
    is_eu = best["currency"] != "USD"
    price_line = money(best["price"], best["currency"]) if not is_eu else f'{money(best["price"], best["currency"])} (≈ {money(price, "USD")})'
    checked = parse_iso(best.get("checked_at"))
    checked_s = f"{checked:%b %d, %H:%M} UTC" if checked else "recently"
    notes = []
    if is_eu:
        notes.append("This is a EU seller: the USD figure is only an approximate conversion, and shipping, import duties and VAT/tax are not included.")
    notes.append("Prices are the seller's listed price before shipping and taxes, and stock can change within minutes.")

    subject = f"Price alert: {mname} at {money(price, 'USD')} (your target: {money(target, 'USD')})"
    alt_html = alt_text = ""
    if alt:
        alink, _ = offer_link(alt, aff)
        aseller = latest["sellers"].get(alt["seller"], {}).get("name", alt["seller"])
        aprice = f'{money(alt["price"], alt["currency"])} (≈ {money(alt["price_usd_approx"], "USD")})' if alt["currency"] != "USD" else money(alt["price"], "USD")
        alt_html = f'<p style="font-size:14px">Also in stock at {html.escape(aseller)} ({html.escape(models[alt["model"]]["name"])}): <a href="{html.escape(alink)}">{html.escape(aprice)}</a> (not including shipping/duties/VAT).</p>'
        alt_text = f'\nAlso in stock at {aseller} ({models[alt["model"]]["name"]}): {aprice} - {alink} (not including shipping/duties/VAT).\n'
    disclosure = "Links to sellers may be affiliate links: if you buy through one, Bitaxe Radar may earn a commission at no extra cost to you."
    if is_aff:
        disclosure = f"The {seller} link above is an affiliate link: if you buy through it, Bitaxe Radar may earn a commission at no extra cost to you."

    html_body = f"""<div style="font:16px/1.5 system-ui,sans-serif;max-width:560px">
<p><strong>{html.escape(mname)}</strong> is in stock at or under your target.</p>
<table style="border-collapse:collapse;font-size:15px">
<tr><td style="padding:2px 12px 2px 0;color:#666">Seller</td><td>{html.escape(seller)}</td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#666">Price</td><td><strong>{html.escape(price_line)}</strong></td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#666">Your target</td><td>{html.escape(money(target, "USD"))}</td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#666">Config</td><td>{html.escape(best.get("config") or "see seller page")}</td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#666">Checked</td><td>{html.escape(checked_s)}</td></tr></table>
<p><a href="{html.escape(link)}" style="background:#f7931a;color:#1a1100;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700;display:inline-block">View at {html.escape(seller)}</a></p>
{alt_html}<p style="font-size:13px;color:#555">{html.escape(" ".join(notes))} Solo mining is a lottery, not income.</p>
<p style="font-size:13px"><a href="{SITE_URL}">See all prices on Bitaxe Radar</a></p>
<hr style="border:0;border-top:1px solid #ddd;margin:24px 0"><p style="font-size:12px;color:#666;line-height:1.5">{html.escape(disclosure)}<br>
You get this because you signed up for price alerts on bitaxeradar.com.<br>{html.escape(POSTAL)}<br>Questions? Reply to this email or write <a href="mailto:{CONTACT}">{CONTACT}</a>.<br><a href="{html.escape(unsub_url)}">Unsubscribe</a></p></div>"""
    text_body = (f"{mname} is in stock at or under your target.\n\nSeller: {seller}\nPrice: {price_line}\nYour target: {money(target, 'USD')}\n"
                 f"Config: {best.get('config') or 'see seller page'}\nChecked: {checked_s}\n\nView at {seller}: {link}\n{alt_text}\n"
                 f"{' '.join(notes)} Solo mining is a lottery, not income.\nAll prices: {SITE_URL}\n\n--\n{disclosure}\n"
                 f"You get this because you signed up for price alerts on bitaxeradar.com.\n{POSTAL}\nQuestions? Reply to this email or write {CONTACT}\nUnsubscribe: {unsub_url}\n")
    return subject, html_body, text_body


# ---------- Resend client ----------
class Resend:
    def __init__(self, key):
        self.key, self.last_gap = key, 0.0
    def call(self, method, path, body=None, headers=None, retries=3):
        for attempt in range(retries + 1):
            gap = time.time() - self.last_gap          # stay under Resend's 10 req/s default
            if gap < 0.15:
                time.sleep(0.15 - gap)
            self.last_gap = time.time()
            req = urllib.request.Request(RESEND + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json", "User-Agent": "bitaxe-radar-alerts/1.0", **(headers or {})})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.status, json.loads(r.read() or b"null"), dict(r.headers)
            except urllib.error.HTTPError as e:
                raw = e.read()
                try: data = json.loads(raw)
                except ValueError: data = {"raw": raw[:300].decode("utf-8", "replace")}
                if e.code == 429 and attempt < retries:
                    time.sleep(float(e.headers.get("retry-after", "1")) + 0.5); continue
                return e.code, data, dict(e.headers)
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < retries:
                    time.sleep(2); continue
                return 0, {"error": str(e)}, {}
    def list_contacts(self):
        after = None
        while True:
            q = "limit=100" + (f"&after={after}" if after else "")
            st, d, _ = self.call("GET", "/contacts?" + q)
            if st != 200:
                raise RuntimeError(f"list contacts failed: {st} {d}")
            for c in d.get("data", []):
                yield c
            if not d.get("has_more") or not d.get("data"):
                return
            after = d["data"][-1]["id"]
    def get_contact(self, id_or_email):
        st, d, _ = self.call("GET", "/contacts/" + urllib.parse.quote(id_or_email, safe=""))
        return d if st == 200 else None


def quota_used(headers):
    for k, v in (headers or {}).items():
        if k.lower() == "x-resend-daily-quota":
            try: return int(v)
            except ValueError: return None
    return None


# ---------- main ----------
def run(latest, contacts, *, aff, now, dry_run, max_sends, sender=None, updater=None, signing_secret="", public_base="", log=print):
    """Core loop (no I/O besides sender/updater callbacks). Returns list of result dicts."""
    results, sent = [], 0
    for c in contacts:
        email = (c.get("email") or "").lower()
        props = c.get("_props") if "_props" in c else contact_props(c)
        row = {"email": email, "model": props.get("model"), "target": props.get("target_price")}
        if c.get("unsubscribed") is not False:
            row.update(action="skip", reason="not confirmed / unsubscribed"); results.append(row); continue
        match = find_match(props, latest, now)
        if not match:
            ids = resolve_models(props.get("model"), latest["models"])
            row.update(action="skip", reason="unrecognised model" if not ids else "no in-stock offer at/below target"); results.append(row); continue
        best = match["best"]; price = best["price_usd_approx"]
        ok, why = should_alert(props, price, now)
        if not ok:
            row.update(action="skip", reason="dedupe: " + why, price=price); results.append(row); continue
        if sent >= max_sends:
            row.update(action="defer", reason=f"send cap reached ({max_sends}); will retry next run", price=price); results.append(row); continue
        secret, base = signing_secret or "dry-run-secret", public_base or "https://subscribe.bitaxeradar.com"
        unsub = f"{base}/unsubscribe?t={urllib.parse.quote(sign_token({'t': 'u', 'e': email}, secret))}"
        subject, html_body, text_body = build_email(email, props, match, latest, aff, unsub)
        row.update(price=price, seller=best["seller"], offer=best["id"], subject=subject, reason=why,
                   link=offer_link(best, aff)[0], alt=(match["alt"] or {}).get("id"))
        if dry_run:
            row["action"] = "WOULD SEND"; sent += 1; results.append(row); continue
        status, data, headers = sender(email, subject, html_body, text_body, unsub, c, price, now)
        if status in (200, 201):
            row["action"] = "sent"; sent += 1
            updater(c, {"last_alert_price": price, "last_alert_at": iso(now)})
            used = quota_used(headers)
            if used is not None and used >= DAILY_STOP:
                row["note"] = f"daily quota {used} >= {DAILY_STOP}; stopping"; results.append(row)
                log(f"STOP: Resend daily quota used = {used}"); max_sends = 0; continue
        else:
            row.update(action="error", reason=f"send failed: {status} {data}")
        results.append(row)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent; send and write nothing")
    ap.add_argument("--latest", default=str(ROOT / "data" / "latest.json"))
    ap.add_argument("--app-js", default=str(ROOT / "site" / "app.js"), help="where to read the AFFILIATE map from")
    ap.add_argument("--contacts-fixture", help="JSON list of contacts (Resend shape); skips the Resend API entirely (dry-run only)")
    ap.add_argument("--max-sends", type=int, default=DAILY_STOP, help="max emails this run (default 90; Resend free plan is 100/day)")
    ap.add_argument("--now", help="override current time (ISO 8601) - for tests")
    ap.add_argument("--show-email", action="store_true", help="in dry-run, print the first email's text body")
    a = ap.parse_args()

    latest = json.loads(Path(a.latest).read_text())
    now = parse_iso(a.now) or datetime.now(timezone.utc)
    aff = load_affiliates(a.app_js)
    key, secret, base = os.environ.get("RESEND_API_KEY", ""), os.environ.get("SIGNING_SECRET", ""), os.environ.get("PUBLIC_BASE", "").rstrip("/")

    if a.contacts_fixture:
        if not a.dry_run:
            sys.exit("--contacts-fixture is only allowed with --dry-run")
        contacts = json.loads(Path(a.contacts_fixture).read_text())
        client = None
    else:
        if not key:
            sys.exit("RESEND_API_KEY is not set")
        if not a.dry_run and not (secret and base):
            sys.exit("SIGNING_SECRET and PUBLIC_BASE are required to build unsubscribe links")
        client = Resend(key)
        contacts = []
        for c in client.list_contacts():
            if c.get("unsubscribed") is not False:
                continue
            if "properties" in c:            # some API versions include them in the list response
                contacts.append(c)
            else:
                full = client.get_contact(c["id"])
                if full:
                    contacts.append(full)
        print(f"loaded {len(contacts)} confirmed contacts from Resend")

    def sender(email, subject, html_body, text_body, unsub, c, price, now_):
        return client.call("POST", "/emails", {
            "from": FROM, "reply_to": CONTACT, "to": [email], "subject": subject, "html": html_body, "text": text_body,
            "headers": {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            "tags": [{"name": "type", "value": "price_alert"}]},
            headers={"Idempotency-Key": f"alert-{c.get('id', email)}-{price:.2f}-{now_:%Y%m%d}"[:256]})

    def updater(c, props):
        st, d, _ = client.call("PATCH", "/contacts/" + urllib.parse.quote(c.get("id") or c["email"], safe=""), {"properties": props})
        if st != 200:
            print(f"WARNING: could not store dedupe state for {c['email']}: {st} {d}  (may re-alert next run)")

    print(f"{'DRY RUN - ' if a.dry_run else ''}offers collected {latest['generated_at']}; affiliate map: {aff or '{}'}; now={iso(now)}")
    res = run(latest, contacts, aff=aff, now=now, dry_run=a.dry_run, max_sends=a.max_sends,
              sender=sender if client else None, updater=updater if client else None, signing_secret=secret, public_base=base)
    for r in res:
        extra = f" -> {r['offer']} @ ${r['price']:.2f}" if r.get("offer") else ""
        print(f"  {r['action']:<10} {r['email']:<24} model={r.get('model')!s:<18} target={r.get('target')!s:<6}{extra}  [{r['reason']}]")
    n = sum(1 for r in res if r["action"] in ("sent", "WOULD SEND"))
    print(f"summary: contacts={len(res)} {'would_send' if a.dry_run else 'sent'}={n} "
          f"deferred={sum(r['action']=='defer' for r in res)} errors={sum(r['action']=='error' for r in res)}")
    if a.dry_run and a.show_email:
        first = next((r for r in res if r["action"] == "WOULD SEND"), None)
        if first:
            c = next(x for x in contacts if (x.get("email") or "").lower() == first["email"])
            props = c.get("_props") if "_props" in c else contact_props(c)
            m = find_match(props, latest, now)
            s, _, t = build_email(first["email"], props, m, latest, aff, "https://subscribe.bitaxeradar.com/unsubscribe?t=EXAMPLE")
            print("\n--- first email ---\nSubject:", s, "\n" + t)
    if any(r["action"] == "error" for r in res):
        sys.exit(1)

if __name__ == "__main__":
    main()
