"""Daily command (run by .github/workflows/collect.yml right after the price collector):

  python3 -m deal_agent            # write today's deal if there isn't one for today yet (US Eastern date)
  python3 -m deal_agent --force    # write it again even if today's exists
  python3 -m deal_agent --dry-run  # print the result, write nothing
  python3 -m deal_agent --template # no AI: write the code-only template version (labelled as such on the site)

Writes data/deal_of_the_day.json and adds the same entry to data/deals_history.json (one per day).
Never breaks the deploy: with no API key, or if Claude is down, it keeps the previous deal and exits 0.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import guard
from .agent import run_agent
from .claude import Claude, ClaudeError
from .facts import ROOT, PriceData
from .template import template_deal

HISTORY_MAX = 365
ET = ZoneInfo("America/New_York")


def deal_date(generated_at):
    """The day a visitor sees: US Eastern date of the collector run (same zone the site shows)."""
    t = datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return t.astimezone(ET).date().isoformat()


def make_record(pd, res, now=None):
    d = res["deal"]
    rec = dict(date=deal_date(pd.generated_at), data_checked_at=pd.generated_at,
               written_at=(now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
               source=res["source"], model=res["model"] if res["source"] == "ai" else None,
               no_standout=bool(d.get("no_standout")), headline=d["headline"].strip(), summary=d["summary"].strip())
    if not rec["no_standout"]:
        f = pd.facts(d["miner_id"])
        rec.update(miner_id=f["miner_id"], miner_name=f["miner_name"], offer_id=f["offer_id"], retailer_id=f["retailer_id"],
                   retailer_name=f["retailer_name"], price_usd=f["price_usd"], price=f["price"], currency=f["currency"],
                   typical_usd=f["typical_usd"], drop_usd=f["drop_usd"], drop_pct=f["drop_pct"],
                   lowest_ever=f["lowest_ever"], new_low=f["new_low"], history_days=f["history_days"], window_days=f["window_days"])
    rec["check"] = dict(passed=True, attempts=res.get("attempts", 0), first_try_problems=(res.get("guard_errors") or [[]])[0])
    rec["run"] = dict(calls=res.get("calls", 0), tools=[t["name"] for t in res.get("tools_used", [])],
                      input_tokens=res["usage"]["input_tokens"], output_tokens=res["usage"]["output_tokens"], cost_usd=res["cost_usd"])
    return rec


def save(rec, data_dir):
    (data_dir / "deal_of_the_day.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    hp = data_dir / "deals_history.json"
    hist = json.loads(hp.read_text()) if hp.exists() else []
    hist = [rec] + [h for h in hist if h.get("date") != rec["date"]]       # one entry per day; re-runs replace it
    hist.sort(key=lambda h: h["date"], reverse=True)
    hp.write_text(json.dumps(hist[:HISTORY_MAX], indent=1, ensure_ascii=False) + "\n")


def main(argv=None, client=None, root=ROOT):
    p = argparse.ArgumentParser(description="Write the Bitaxe Radar deal of the day.")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--template", action="store_true", help="skip the AI; write the template version")
    a = p.parse_args(argv)
    data_dir = root / "data"
    pd = PriceData.load(root)
    today = deal_date(pd.generated_at)
    cur = data_dir / "deal_of_the_day.json"
    if not a.force and cur.exists() and json.loads(cur.read_text()).get("date") == today:
        print(f"deal agent: today's deal ({today}) already written; nothing to do")
        return 0
    if a.template:
        res = dict(deal=template_deal(pd), source="template", model=None, usage={"input_tokens": 0, "output_tokens": 0},
                   cost_usd=0, tools_used=[], attempts=0, guard_errors=[], calls=0)
        return finish(pd, res, today, data_dir, a.dry_run)
    client = client or Claude()
    if not getattr(client, "api_key", True):
        print("deal agent: ANTHROPIC_API_KEY not set; keeping the previous deal")
        return 0
    try:
        res = run_agent(pd, client)
    except ClaudeError as e:
        print(f"deal agent: Claude unavailable ({e}); keeping the previous deal")
        return 0
    return finish(pd, res, today, data_dir, a.dry_run)


def finish(pd, res, today, data_dir, dry_run):
    errs = guard.verify(res["deal"], pd)          # belt and braces: nothing unchecked is ever written
    if errs:
        print(f"deal agent: final check failed, keeping the previous deal: {errs}")
        return 0
    rec = make_record(pd, res)
    pick = "no standout deal" if rec["no_standout"] else f"{rec['miner_name']} {rec['drop_pct']}% below typical at {rec['retailer_name']}"
    print(f"deal agent: {today}: {pick} (source {rec['source']}, {rec['run']['calls']} calls, tools {rec['run']['tools']}, "
          f"${rec['run']['cost_usd']:.4f})")
    if dry_run:
        print(json.dumps(rec, indent=1, ensure_ascii=False))
        return 0
    save(rec, data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
