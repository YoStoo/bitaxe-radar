"""Code-based grader for the deal agent. No AI grades the AI.

A case PASSES when the PUBLISHED deal:
  1. picks the right miner (the answer key, computed from the case data by facts.py), or says
     "no standout" when the key says there is no real deal;
  2. names the right shop and copies the right price, typical price and drop %;
  3. has no wrong numbers in its text: every $ and % must be one of that miner's real values
     (this check is written separately from deal_agent/guard.py on purpose, so a bug in the
     guardrail can't hide itself);
  4. makes no "lowest ever" claim the data doesn't support.
We also report, separately, how the AI did on its FIRST try (before the guardrail could step in).
"""
import re

MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
PCT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
NEGATED = re.compile(r"(?:\bnot|n't|\bno longer)\s+(?:\w+\s+){0,2}$", re.I)
LOWEST = re.compile(r"lowest[- ](?:price )?ever|all[- ]time low|record low|never been cheaper|lowest (?:price )?we(?:'ve| have)? (?:ever )?(?:seen|logged)", re.I)


def _ok_number(written, values):
    x = float(written.replace(",", ""))
    # Accept the exact value, or the value rounded to whole units / one decimal (either way on an exact half).
    return any(abs(x - v) < 0.006 or (("." not in written) and abs(x - v) <= 0.5 + 1e-9) or
               (("." in written) and abs(x - v) <= 0.05 + 1e-9) for v in (abs(v) for v in values if v is not None))


def grade_deal(deal, pd):
    """Problems with one deal object (empty list = correct)."""
    key = pd.answer_key()
    probs = []
    text = f"{deal.get('headline', '')} {deal.get('summary', '')}"
    if key is None:
        if not deal.get("no_standout"):
            probs.append(f"picked {deal.get('miner_id')!r}, but there is no real deal today")
        if MONEY.search(text):
            probs.append("quotes a price on a no-deal day")
        return probs
    if deal.get("no_standout"):
        return [f"said no standout, but {key} is a real deal"]
    if deal.get("miner_id") != key:
        return [f"picked {deal.get('miner_id')!r}, expected {key!r}"]
    f = pd.facts(key)
    if (deal.get("retailer_name") or "").lower() != f["retailer_name"].lower():
        probs.append(f"shop {deal.get('retailer_name')!r}, expected {f['retailer_name']!r}")
    for k, tol in (("price_usd", 0.011), ("typical_usd", 0.011), ("drop_pct", 0.051)):
        if deal.get(k) is None or abs(float(deal[k]) - f[k]) > tol:
            probs.append(f"{k} {deal.get(k)} != {f[k]}")
    hist = pd.history(key, 30)
    money_ok = [f["price_usd"], f["typical_usd"], f["drop_usd"], f["prior_low_usd"], f["window_low_usd"], f["window_high_usd"],
                f["price"]] + ([hist["start"]["usd"], abs(hist["change_usd"]), hist["highest_in_window"]["usd"]] if "start" in hist else [])
    pct_ok = [f["drop_pct"], 3.0] + ([abs(hist["change_pct"])] if "start" in hist and hist["change_pct"] is not None else [])
    for n in MONEY.findall(text):
        if not _ok_number(n, money_ok):
            probs.append(f"wrong number ${n}")
    for n in PCT.findall(text):
        if not _ok_number(n, pct_ok):
            probs.append(f"wrong number {n}%")
    claimed = any(not NEGATED.search(text[max(0, m.start() - 30):m.start()]) for m in LOWEST.finditer(text))
    if claimed and not f["lowest_ever"]:
        probs.append("claims lowest ever, data says no")
    return probs


def grade(case, pd, res):
    """res = the agent's result (deal, source, guard_errors...). Returns one result row."""
    final = grade_deal(res["deal"], pd) if res.get("deal") else ["nothing published"]
    first = res.get("first_deal")
    first_probs = grade_deal(first, pd) if first else None
    return dict(id=case["id"], passed=not final, problems=final, source=res.get("source"),
                first_try_ok=(first_probs == [] and not (res.get("guard_errors") or [[1]])[0]) if first is not None else None,
                first_try_problems=first_probs, guard_first=(res.get("guard_errors") or [None])[0],
                attempts=[dict(d, problems=e) for d, e in zip(res.get("submitted", []), res.get("guard_errors", []))],
                calls=res.get("calls"), tools=[t["name"] for t in res.get("tools_used", [])], cost_usd=res.get("cost_usd", 0))
