"""Run the deal-agent eval set and record the score.

  python3 evals/deal/run_deal_evals.py --mode before     # the site BEFORE this feature: no deal is published
  python3 evals/deal/run_deal_evals.py --mode template   # code-only fallback (no AI). Correct by construction: a harness check
  python3 evals/deal/run_deal_evals.py --mode scripted   # fake Claude that follows the ideal tool path (no key, free)
  ANTHROPIC_API_KEY=... python3 evals/deal/run_deal_evals.py --mode live   # the real agent with real Claude
  ... --only fx,spike     # just some cases          --max-cost 0.10   # stop the live run at 10 cents total

Results go to evals/results/<time>-deal-<mode>.json and .md. A live run of all 11 cases costs about 1-2 cents.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import deal_grader as grader  # noqa: E402  (not "grader": evals/grader.py already owns that name, story #37)
import deal_scenarios as scenarios  # noqa: E402
from deal_agent.agent import run_agent  # noqa: E402
from deal_agent.claude import MODEL, Claude, ClaudeError  # noqa: E402
from deal_agent.template import template_deal  # noqa: E402
from deal_agent.tools import run_tool  # noqa: E402


class ScriptedClaude:
    """A fake model that does what a perfect agent would: screen, check the top pick, submit the template deal."""

    def __init__(self, pd):
        self.pd, self.n = pd, 0
        self.api_key = "scripted"

    def call(self, body):
        self.n += 1
        top = (run_tool(self.pd, "rank_price_drops", {"limit": 5})[0]["miners"] or [{}])[0].get("miner_id", "bitaxe-gamma")
        steps = {1: [("rank_price_drops", {"limit": 5})], 2: [("compare_to_average", {"miner": top}), ("get_price_history", {"miner": top, "days": 30})]}
        calls = steps.get(self.n) or [("submit_deal", template_deal(self.pd))]
        return {"stop_reason": "tool_use", "usage": {"input_tokens": 0, "output_tokens": 0},
                "content": [{"type": "tool_use", "id": f"t{self.n}{i}", "name": n, "input": a} for i, (n, a) in enumerate(calls)]}


def run_case(case, mode):
    pd = scenarios.build(case)
    if mode == "before":
        return pd, dict(deal=None, source=None)
    if mode == "template":
        return pd, dict(deal=template_deal(pd), source="template")
    client = ScriptedClaude(pd) if mode == "scripted" else Claude()
    return pd, run_agent(pd, client)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["before", "template", "scripted", "live"], required=True)
    p.add_argument("--only", default="")
    p.add_argument("--max-cost", type=float, default=0.10)
    p.add_argument("--label", default="")
    a = p.parse_args(argv)
    cases = json.loads((HERE / "cases.json").read_text())
    if a.only:
        words = [w.strip() for w in a.only.split(",") if w.strip()]
        cases = [c for c in cases if any(w in c["id"] for w in words)]
    if a.mode == "live" and not Claude().api_key:
        print("Set ANTHROPIC_API_KEY first (it is never printed).")
        return 2
    rows, spent = [], 0.0
    for c in cases:
        if spent >= a.max_cost:
            print(f"stopping: spent ${spent:.4f} (cap ${a.max_cost})")
            break
        try:
            pd, res = run_case(c, a.mode)
        except ClaudeError as e:
            rows.append(dict(id=c["id"], passed=False, problems=[f"API error: {e}"], source=None, cost_usd=0))
            continue
        row = grader.grade(c, pd, res)
        row["published"] = {k: res["deal"].get(k) for k in ("no_standout", "miner_id", "retailer_name", "price_usd", "drop_pct", "headline", "summary")} if res.get("deal") else None
        spent += row.get("cost_usd") or 0
        rows.append(row)
        print(f"{'PASS' if row['passed'] else 'FAIL'}  {c['id']:<28} source={row['source']}  {'; '.join(row['problems'])}")
    n_pass = sum(r["passed"] for r in rows)
    first = [r for r in rows if r.get("first_try_ok") is not None]
    summary = dict(mode=a.mode, model=MODEL if a.mode == "live" else None, when=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   passed=n_pass, total=len(rows), first_try_ok=sum(bool(r["first_try_ok"]) for r in first) if first else None,
                   fallbacks=sum(r.get("source") == "template" for r in rows) if a.mode in ("live", "scripted") else None,
                   cost_usd=round(spent, 5))
    print(json.dumps(summary))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-deal-{a.mode}{'-' + a.label if a.label else ''}"
    out = ROOT / "evals" / "results"
    out.mkdir(exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(dict(summary=summary, rows=rows), indent=1) + "\n")
    md = [f"# Deal agent eval: {a.mode}", "", f"**{n_pass}/{len(rows)} passed** · first-try OK: {summary['first_try_ok']} · "
          f"fallbacks: {summary['fallbacks']} · cost ${spent:.4f} · {summary['when']}", "", "| | case | source | problems | headline |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {'✅' if r['passed'] else '❌'} | `{r['id']}` | {r.get('source')} | {'; '.join(r['problems'])} | {((r.get('published') or {}).get('headline') or '').replace('|', '/')} |")
    (out / f"{name}.md").write_text("\n".join(md) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
