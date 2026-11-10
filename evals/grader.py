"""The GRADER: code that checks one answer and says pass or fail, with a reason.

Every check is a tiny function:  check_x(...) -> (passed: bool, why: str).
No AI grades the AI here. Every check is plain code, so the score means the same thing every run.
"""
import re

import radar_data as R

DEFAULT_MAX_SENTENCES = 4   # the prompt asks for 2-4 short sentences
DEFAULT_MAX_WORDS = 90      # prompt says ~70; we allow a little slack

REFUSAL_WORDS = re.compile(
    r"only (help|answer|talk|cover|assist)|only able to|can'?t (help|do|write|check|share|answer)|cannot help|not able to|unable to|"
    r"outside (what|my)|stick to|not something i|i'?m here to help with|i help with|i only", re.I)
NOT_FOUND_WORDS = re.compile(
    r"(don'?t|do not|doesn'?t|does not|isn'?t|is not|aren'?t|no|not|couldn'?t|can'?t)\b[^.]{0,60}"
    r"\b(track|have|find|list|data|carry|see|know|exist|match|recogni[sz]e)", re.I)
MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")


# ---------- small text helpers ----------
def sentences(text):
    """Split into sentences. A '.' inside a number ($55.80) or 'e.g.' does not end a sentence."""
    parts = re.split(r"(?<!\be\.g)(?<!\bi\.e)[.!?]+(?=\s|$)", text.strip())
    return [p for p in parts if p.strip()]


def dollar_amounts(text):
    return [float(x.replace(",", "")) for x in MONEY.findall(text)]


def close(a, b, pct=0.02, floor=1.0):
    """True if a is within 2% (or $1) of b. Answers round prices ('about $112' for $111.69)."""
    return abs(a - b) <= max(floor, abs(b) * pct)


# ---------- the checks ----------
def check_ok(resp):
    return resp.get("ok") is True, "answered" if resp.get("ok") else f"error: {resp.get('error') or resp.get('http_status')}"


def check_length(answer, max_sentences=DEFAULT_MAX_SENTENCES, max_words=DEFAULT_MAX_WORDS):
    n_s, n_w = len(sentences(answer)), len(answer.split())
    ok = n_s <= max_sentences and n_w <= max_words
    return ok, f"{n_s} sentences, {n_w} words (max {max_sentences}/{max_words})"


def check_in_data(resp, expected):
    got = resp.get("in_data")
    return got is expected, f"in_data={got}, expected {expected}"


def check_mentions(answer, resp, ids, latest):
    """Each miner id must be named in the answer text or listed in models_mentioned."""
    named = set(R.miners_in_text(answer, latest)) | set(resp.get("models_mentioned") or [])
    missing = [i for i in ids if i not in named]
    return not missing, "named all" if not missing else f"missing {', '.join(missing)}"


def check_ranking(answer, groups, latest):
    """groups = expected order, e.g. [['bitaxe-gamma'], ['hammer-bc01']]. Ties share a group.
    The answer's FIRST miner must be from group 1, and group 2 (if any) must appear after it."""
    order = R.miners_in_text(answer, latest)
    if not order:
        return False, "no miner named"
    if order[0] not in groups[0]:
        return False, f"led with {order[0]}, expected {'/'.join(groups[0])}"
    pos = 0
    for g in groups[1:]:
        hits = [order.index(i) for i in g if i in order]
        if not hits or min(hits) <= pos:
            return False, f"expected {'/'.join(g)} next; answer order {order[:4]}"
        pos = min(hits)
    return True, " > ".join(order[:len(groups)])


def check_price(answer, mid, expected_usd):
    amounts = dollar_amounts(answer)
    ok = any(close(a, expected_usd) for a in amounts)
    return ok, f"{mid} ${expected_usd:g} {'found' if ok else 'not found'} in {amounts}"


def check_per_th(answer, mid, expected):
    """$/TH figure, e.g. '$55.80 per TH/s'. Accept 3% slack (it's a rounded division)."""
    amounts = dollar_amounts(answer)
    ok = any(close(a, expected, pct=0.03, floor=0.5) for a in amounts)
    return ok, f"{mid} ${expected:g}/TH {'found' if ok else 'not found'} in {amounts}"


def check_shop(answer, shops):
    ok = any(s.lower() in answer.lower() for s in shops)
    return ok, f"mentions a real shop ({', '.join(shops[:3])})" if ok else f"no tracked shop named (expected one of {shops[:3]})"


def check_tool(resp, spec):
    """spec = {"name": "search_miners" or ["get_miner", "compare_miners"], "input": {"sort_by": "price_per_th"}}"""
    names = spec["name"] if isinstance(spec["name"], list) else [spec["name"]]
    used = resp.get("tools_used") or []
    for t in used:
        if t.get("name") in names and _input_matches(t.get("input") or {}, spec.get("input") or {}):
            return True, f"{t['name']} {t.get('input')}"
    seen = "; ".join(f"{t.get('name')} {t.get('input')}" for t in used) or "no tools"
    return False, f"expected {'/'.join(names)} {spec.get('input') or ''}, got {seen}"


def _input_matches(got, want):
    for k, v in want.items():
        g = got.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if not isinstance(g, (int, float)) or not close(g, v, pct=0.05, floor=0):
                return False
        elif str(g).lower() != str(v).lower():
            return False
    return True


def check_no_tools(resp):
    used = resp.get("tools_used") or []
    return not used, "no tools" if not used else f"used {[t.get('name') for t in used]}"


def check_refusal(answer, resp):
    """A polite 'I only help with miners': refusal words, and no prices made up for the off-topic ask."""
    if not REFUSAL_WORDS.search(answer):
        return False, "no refusal wording"
    if dollar_amounts(answer):
        return False, "refusal contains a price"
    return True, "refused"


def check_not_found(answer):
    ok = bool(NOT_FOUND_WORDS.search(answer))
    return ok, "says it isn't in the data" if ok else "didn't say the miner isn't tracked"


def check_not_contains(answer, phrases):
    bad = [p for p in phrases if p.lower() in answer.lower()]
    return not bad, "clean" if not bad else f"contains {bad}"


def check_not_regex(answer, pattern):
    m = re.search(pattern, answer, re.I)
    return m is None, "clean" if m is None else f"matched {m.group(0)!r}"


def check_regex(answer, pattern):
    m = re.search(pattern, answer, re.I)
    return m is not None, f"matched {m.group(0)!r}" if m else f"no match for /{pattern}/"


# ---------- turn a case's "expect" block into concrete checks, using TODAY's data ----------
def resolve(case, latest):
    """Returns a list of (check_name, function_taking(answer, resp)) built from current prices.
    This is how the eval survives price changes: "the cheapest Bitaxe" is looked up now, not written down."""
    e = case.get("expect", {})
    checks = [("answered", lambda a, r: check_ok(r))]
    checks.append(("short", lambda a, r: check_length(a, e.get("max_sentences", DEFAULT_MAX_SENTENCES), e.get("max_words", DEFAULT_MAX_WORDS))))

    if "top" in e:   # e.g. {"sort_by": "price", "brand": "Bitaxe", "n": 2, "after": "bitaxe-gamma"}
        t = dict(e["top"])
        n, after = t.pop("n", 1), t.pop("after", None)
        rows = R.rank(latest, **t)
        if after:
            ids = [r["id"] for r in rows]
            rows = rows[ids.index(after) + 1:] if after in ids else rows
        if not rows:
            checks.append(("ranking", lambda a, r: (False, "no in-stock miner matches this case today; update the case")))
        else:
            key = R.SORT_KEYS[t.get("sort_by", "price")]
            groups, i = [], 0
            while len(groups) < n and i < len(rows):   # group tied values ($119.99 and $119.99 are both "3rd")
                g = [x["id"] for x in rows if x[key] == rows[i][key]]
                groups.append(g)
                i += len(g)
            checks.append(("ranking", lambda a, r, g=groups: check_ranking(a, g, latest)))
            top = rows[0]
            if e.get("check_price", True):
                checks.append(("price", lambda a, r, x=top: check_price(a, x["id"], x["cheapest_usd"])))
            if t.get("sort_by") == "price_per_th":
                checks.append(("usd_per_th", lambda a, r, x=top: check_per_th(a, x["id"], x["usd_per_th"])))

    if "mentions" in e:
        checks.append(("mentions", lambda a, r: check_mentions(a, r, e["mentions"], latest)))
    for mid in e.get("price_of", []):
        row = R.miner_row(latest, mid)
        if row["cheapest_usd"] is not None:
            checks.append((f"price:{mid}", lambda a, r, x=row: check_price(a, x["id"], x["cheapest_usd"])))
    if "shop_of" in e:
        shops = R.miner_row(latest, e["shop_of"])["shops"]
        checks.append(("shop", lambda a, r: check_shop(a, shops)))
    if "in_data" in e:
        checks.append(("in_data", lambda a, r: check_in_data(r, e["in_data"])))
    if "tool" in e:
        checks.append(("tool", lambda a, r: check_tool(r, e["tool"])))
    if e.get("no_tools"):
        checks.append(("no_tools", lambda a, r: check_no_tools(r)))
    if e.get("refuse"):
        checks.append(("refuse", lambda a, r: check_refusal(a, r)))
    if e.get("not_found"):
        checks.append(("not_found", lambda a, r: check_not_found(a)))
    if "must_not_contain" in e:
        checks.append(("no_leak", lambda a, r: check_not_contains(a, e["must_not_contain"])))
    if "must_not_match" in e:
        checks.append(("not_match", lambda a, r: check_not_regex(a, e["must_not_match"])))
    if "must_match" in e:
        checks.append(("match", lambda a, r: check_regex(a, e["must_match"])))
    return checks


def grade(case, resp, latest):
    """Run every check for one case. The case passes only if ALL its checks pass."""
    answer = resp.get("answer") or ""
    results = []
    for name, fn in resolve(case, latest):
        if name != "answered" and not resp.get("ok"):
            results.append({"check": name, "pass": False, "why": "no answer"})
            continue
        ok, why = fn(answer, resp)
        results.append({"check": name, "pass": bool(ok), "why": why})
    return {"id": case["id"], "pass": all(c["pass"] for c in results), "checks": results}


def fill(text, latest):
    """History templates: '{price:avalon-q}' -> '$1,398', '{name:avalon-q}', '{shop:avalon-q}' from today's data."""
    def sub(m):
        kind, mid = m.group(1), m.group(2)
        row = R.miner_row(latest, mid)
        if kind == "price":
            return f"${row['cheapest_usd']:,.2f}".replace(".00", "")
        if kind == "shop":
            return row["shops"][0] if row["shops"] else "no shop right now"
        return row["name"]
    return re.sub(r"\{(price|name|shop):([a-z0-9-]+)\}", sub, text)
