"""The RUNNER: send every eval question to the chat bot, grade each answer, print a score.

Usage (from the repo root):
  python3 evals/run_evals.py                      # all cases, live site
  python3 evals/run_evals.py --only refuse,inject # just cases whose id or tag contains these words
  python3 evals/run_evals.py --url http://localhost:8787/ask   # a local `wrangler dev` Worker
  python3 evals/run_evals.py --dry-run            # show the resolved checks, send nothing
  python3 evals/run_evals.py --only history --url https://<test-worker>/ask --prices-db <same .sql/.db the Worker reads>
  python3 evals/run_evals.py --regrade evals/results/X.json   # re-grade saved answers (after a grader fix), no requests

Costs: about $0.0007 of Claude time per question, and each question uses 1 of the 200/day slots.
The Worker allows 5 questions a minute per visitor, so we wait ~13 s between questions (a full run takes ~8 min).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grader  # noqa: E402
import radar_data as R  # noqa: E402

LIVE_URL = "https://bitaxe-radar-alerts.bitaxeradar.workers.dev/ask"
MAX_REQUESTS = 35   # safety cap per run (daily limit is 200)


def ask(url, question, history):
    """POST one question. Returns the JSON reply (plus timing), or an error dict. Never raises."""
    body = json.dumps({"question": question, "history": history}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "content-type": "application/json", "origin": "https://bitaxeradar.com", "user-agent": "bitaxe-radar-evals"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            out = json.loads(r.read())
            out["http_status"] = r.status
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read())
        except Exception:
            out = {"ok": False}
        out["http_status"] = e.code
    except Exception as e:   # timeout, no network
        out = {"ok": False, "error": type(e).__name__, "http_status": None}
    out["ms"] = int((time.time() - t0) * 1000)
    return out


def pick(cases, only):
    if not only:
        return cases
    words = [w.strip().lower() for w in only.split(",") if w.strip()]
    return [c for c in cases if any(w in c["id"] or w in c.get("tags", []) for w in words)]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=LIVE_URL)
    p.add_argument("--only", help="comma-separated words matched against case id or tags")
    p.add_argument("--delay", type=float, default=13.0, help="seconds between questions (rate limit is 5/min)")
    p.add_argument("--label", default="", help="name for this run, e.g. baseline or after-fix")
    p.add_argument("--local-data", action="store_true", help="grade against data/latest.json instead of the live site")
    p.add_argument("--prices-db", help="price history database the Worker reads (.db or .sql URL/path); "
                   "default bitaxeradar.com/prices.db, or data/prices.db with --local-data")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--regrade", help="saved results .json: grade its answers again with the current grader, send nothing")
    a = p.parse_args(argv)
    if a.prices_db or a.local_data:
        R.PRICES_DB_URL = a.prices_db or str(R.ROOT / "data" / "prices.db")
    if a.regrade:
        return regrade(Path(a.regrade), a)

    cases = pick(json.loads((HERE / "cases.json").read_text())["cases"], a.only)
    if len(cases) > MAX_REQUESTS:
        sys.exit(f"{len(cases)} cases is over the {MAX_REQUESTS}-question safety cap. Use --only.")
    latest = R.load_local() if a.local_data else R.load_live()
    print(f"{len(cases)} cases | data from {latest['generated_at']} | {a.url}\n")

    if a.dry_run:
        for c in cases:
            print(c["id"], "->", [name for name, _ in grader.resolve(c, latest)])
        return 0

    graded = []
    for i, c in enumerate(cases):
        if i:
            time.sleep(a.delay)
        history = [{"role": h["role"], "content": grader.fill(h["content"], latest)} for h in c.get("history", [])]
        resp = ask(a.url, c["question"], history)
        if resp.get("http_status") == 429 and "minute" in str(resp.get("error", "")):   # per-minute limit: wait, retry once
            time.sleep(61)
            resp = ask(a.url, c["question"], history)
        g = grader.grade(c, resp, latest)
        g.update(question=c["question"], ok=resp.get("ok") is True, answer=resp.get("answer") or resp.get("error"), ms=resp.get("ms"),
                 in_data=resp.get("in_data"), tools_used=resp.get("tools_used"), models_mentioned=resp.get("models_mentioned"))
        graded.append(g)
        fails = [f"{x['check']}: {x['why']}" for x in g["checks"] if not x["pass"]]
        print(f"{'PASS' if g['pass'] else 'FAIL'}  {c['id']:<26} {resp.get('ms', 0) / 1000:4.1f}s  {'; '.join(fails)}")

    save(graded, a, latest)
    return 0


def save(graded, a, latest):
    """Print the score and write results/<time>-<label>.json + .md."""
    n_pass = sum(g["pass"] for g in graded)
    n_checks = sum(len(g["checks"]) for g in graded)
    n_checks_pass = sum(x["pass"] for g in graded for x in g["checks"])
    print(f"\nSCORE: {n_pass}/{len(graded)} cases passed  ({n_checks_pass}/{n_checks} checks)")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = stamp + (f"-{a.label}" if a.label else "")
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    summary = {"run": name, "url": a.url, "data_updated": latest["generated_at"], "cases_passed": n_pass,
               "cases": len(graded), "checks_passed": n_checks_pass, "checks": n_checks, "results": graded}
    (out_dir / f"{name}.json").write_text(json.dumps(summary, indent=2))
    (out_dir / f"{name}.md").write_text(markdown(summary))
    print(f"Saved evals/results/{name}.json and .md")


def regrade(path, a):
    """Same answers, new grader. Uses the same data snapshot only if it's still current (prices move)."""
    old = json.loads(path.read_text())
    cases = {c["id"]: c for c in json.loads((HERE / "cases.json").read_text())["cases"]}
    latest = R.load_local() if a.local_data else R.load_live()
    if latest["generated_at"] != old["data_updated"]:
        print(f"Note: answers were graded on data from {old['data_updated']}, today's data is {latest['generated_at']}.")
    graded = []
    for r in old["results"]:
        ok = r.get("ok", any(x["check"] == "answered" and x["pass"] for x in r["checks"]))
        resp = {"ok": ok, "answer": r.get("answer") if ok else None, "error": None if ok else r.get("answer"),
                "in_data": r.get("in_data"), "tools_used": r.get("tools_used"), "models_mentioned": r.get("models_mentioned")}
        g = grader.grade(cases[r["id"]], resp, latest)
        g.update({k: r.get(k) for k in ("question", "answer", "ms", "in_data", "tools_used", "models_mentioned")}, ok=ok)
        graded.append(g)
        fails = [f"{x['check']}: {x['why']}" for x in g["checks"] if not x["pass"]]
        print(f"{'PASS' if g['pass'] else 'FAIL'}  {r['id']:<26} {'; '.join(fails)}")
    a.url = old["url"] + " (regraded)"
    a.label = a.label or (old["run"].split("-", 1)[1] + "-regraded" if "-" in old["run"] else "regraded")
    save(graded, a, latest)
    return 0


def markdown(s):
    lines = [f"# Eval run {s['run']}", "",
             f"**Score: {s['cases_passed']}/{s['cases']} cases** ({s['checks_passed']}/{s['checks']} checks). "
             f"Endpoint `{s['url']}`, data from {s['data_updated']}.", "",
             "| | Case | Failed checks | Answer |", "|---|---|---|---|"]
    for g in s["results"]:
        fails = "; ".join(f"**{x['check']}**: {x['why']}" for x in g["checks"] if not x["pass"]) or ""
        ans = str(g.get("answer") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {'✅' if g['pass'] else '❌'} | `{g['id']}` | {fails} | {ans} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
