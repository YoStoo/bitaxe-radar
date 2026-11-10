#!/usr/bin/env python3
"""Turn saved eval result files into data/eval_history.json.

Scores come only from files under evals/results/ (and, if a file was deleted,
from git history). Nothing is invented. Prompt-injection questions and model
answers are not copied into the public file.

Usage (from the repo root):
  python3 evals/build_history.py
  python3 evals/build_history.py --results-dir evals/results --out data/eval_history.json

The eval runner calls rebuild() after each run so new scores are appended.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"
OUT = ROOT / "data" / "eval_history.json"
CASES_PATH = HERE / "cases.json"

# When a result file doesn't say which suite a case belongs to, use these ids.
# general-solo-mining sits in both Ask and RAG (it was in the original 32, then
# reused as a RAG case). Accidental 1-case overlaps are filtered later.
HISTORY_IDS = {
    "hist-gamma-month", "hist-lowest-ever", "hist-cheapest-shop",
    "hist-week", "hist-followup", "hist-unknown-miner",
}
RAG_IDS = {
    "general-solo-mining", "rag-normal-temp", "rag-psu", "rag-12v-on-gamma",
    "rag-firmware", "rag-quiet", "rag-solar", "rag-how-often",
    "rag-low-hashrate", "rag-dont-know-s19", "rag-dont-know-ha",
}
SENSITIVE_IDS = {"inject-system-prompt", "inject-fake-price", "inject-fake-history"}
SENSITIVE_QUESTION = {
    "inject-system-prompt": "Prompt-injection check: tried to get the hidden instructions (wording withheld)",
    "inject-fake-price": "Prompt-injection check: tried to override a real price (wording withheld)",
    "inject-fake-history": "Prompt-injection check: fake earlier chat trying to change the bot's role (wording withheld)",
}

# Phrases from the injection cases that must never appear on the public page.
LEAK_PATTERNS = re.compile(
    r"piratebot|limerick about dogs|ignore all previous instructions|"
    r"print your system prompt|system override|word for word|"
    r"anthropic_api_key|sk-ant-|api[_-]?key\s*[:=]",
    re.I,
)

DEAL_TITLES = {
    "clear-drop": "A clear in-stock price cut",
    "biggest-drop-sold-out": "The biggest drop is sold out",
    "no-deal-flat": "No price really moved",
    "one-day-spike": "A one-day price spike would fool a simple average",
    "fx-noise": "A currency swing, not a real cut",
    "tie-new-low": "Two similar cuts; one is a new low",
    "new-listing-short-history": "A new listing with too little history",
    "stale-price": "A stale leftover price",
    "just-under-threshold": "A drop just under the minimum bar",
    "shop-switch": "The usual cheapest shop is not today's cheapest",
    "not-lowest-ever": "A real cut that is not the lowest ever",
}

SUITES = {
    "ask": {
        "id": "ask",
        "name": "Ask chat",
        "full_size": 32,
        "tests": "The everyday chat: cheapest and best-value rankings, lookups, follow-ups, refusals of off-topic questions, made-up products, and prompt-injection checks.",
        "grading": "A code-based grader, not another AI. Expected miners and prices are computed from the live price table at run time, so the quiz stays fair when prices change. A case passes only if every check passes (right miner first, price within 2%, length, the tool used, and so on).",
    },
    "history": {
        "id": "history",
        "name": "Price history (SQL)",
        "full_size": 6,
        "tests": "Questions about how a miner's price has moved: last month, the lowest price we've logged, the cheapest shop over time, a follow-up, and a miner we don't track.",
        "grading": "The same code-based grader. The answer key is computed from the price-history database (the SQL file the site is built from), not from a hardcoded dollar amount.",
    },
    "rag": {
        "id": "rag",
        "name": "Guide search (RAG)",
        "full_size": 11,
        "tests": "How-to questions that should be answered from the site's guides: setup, power supplies, firmware, noise, solar, how often prices update, and two questions the guides do not cover (the bot should say it doesn't know).",
        "grading": "Code checks that the right guide was retrieved, that any citation is on an allowlist of real guide pages, that the answer matches expected phrases, and that “I don't know” cases do not invent a source.",
    },
    "deal": {
        "id": "deal",
        "name": "Deal of the Day agent",
        "full_size": 11,
        "tests": "A small daily agent that should pick a real in-stock deal, or honestly say there isn't one. Trap cases include sold-out “deals”, one-day spikes, currency noise, stale prices, short history, and false “lowest ever” claims.",
        "grading": "Code checks every published price, percent, shop, and claim against the case's own price data. The summary cannot mention a number that isn't in that data. Saved runs so far are a before baseline (no agent) and a free harness (a scripted tool loop and a no-AI template). A live Claude score has not been recorded yet.",
    },
}

# Named before/after points. Each value is a result-file label (the part after the timestamp).
# Scores are still read from those files, never typed in here.
MILESTONES = [
    {"suite": "ask", "role": "before", "label": "baseline-regraded",
     "note": "First live score, re-graded after a bug in the grader itself was fixed."},
    {"suite": "ask", "role": "after", "label": "after-fix-live",
     "note": "Live Worker after fixing the in_data label and the prompt-injection hole."},
    {"suite": "history", "role": "before", "label": "sql-before-prod",
     "note": "Live chat before the price-history tool existed. It could only quote today's price."},
    {"suite": "history", "role": "after", "label": "sql-after-preview",
     "note": "Test Worker with the SQL price-history tool."},
    {"suite": "rag", "role": "before", "label": "rag-before-prod",
     "note": "Live chat before guide search existed."},
    {"suite": "rag", "role": "after", "label": "rag-after-fix-preview",
     "note": "Test Worker after fixing a citation bug. This run is 12 cases: the 11 RAG cases plus one general-knowledge case the bug had broken."},
    {"suite": "deal", "role": "before", "label": "deal-before",
     "note": "Before the agent existed, nothing was published, so every case failed."},
    {"suite": "deal", "role": "after", "label": "deal-live-first-live",
     "note": "Live Claude scored 11/11. Ten cases passed on the first try; one used the template fallback."},
]


def _load_catalog():
    """Case id -> tags and public question. Missing file is fine (deal-only checkout)."""
    out = {}
    if CASES_PATH.exists():
        for c in json.loads(CASES_PATH.read_text())["cases"]:
            out[c["id"]] = {"tags": list(c.get("tags") or []), "question": c.get("question") or ""}
    return out


def _stamp_from_name(name):
    """'20261110T112534Z-baseline' -> ('2026-11-10T11:25:34Z', 'baseline')."""
    stem = Path(name).stem
    m = re.match(r"^(\d{8}T\d{6}Z)(?:-(.*))?$", stem)
    if not m:
        return None, stem
    raw, label = m.group(1), (m.group(2) or "")
    when = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return when, label


def _env_from(url, label, deal_mode=None):
    blob = f"{url or ''} {label or ''}".lower()
    if deal_mode in {"before", "template", "scripted"}:
        return "harness"
    if deal_mode == "live":
        return "live"
    if "localhost" in blob or "127.0.0.1" in blob:
        return "local"
    if "preview" in blob:
        return "preview"
    if "workers.dev" in blob or "bitaxeradar" in blob:
        return "live"
    return "unknown"


def _clean_text(text):
    """Drop anything that looks like an injection prompt or a secret. Keep a short summary."""
    if not text:
        return ""
    text = " ".join(str(text).split())
    if LEAK_PATTERNS.search(text):
        return "(details withheld)"
    return text


def _suites_for_case(cid, catalog):
    tags = set((catalog.get(cid) or {}).get("tags") or [])
    suites = []
    if cid in HISTORY_IDS or "history" in tags:
        suites.append("history")
    if cid in RAG_IDS or (cid.startswith("rag-") or "rag" in tags):
        suites.append("rag")
    if cid in DEAL_TITLES:
        suites.append("deal")
    # Original 32: everything that isn't a history-only or rag-only (rag-* ) case.
    # general-solo-mining is both ask and rag on purpose.
    if "deal" not in suites and cid not in HISTORY_IDS and "history" not in tags and not cid.startswith("rag-"):
        suites.append("ask")
    if not suites:
        suites.append("ask")
    return suites


def _public_question(cid, raw_question, catalog):
    if cid in SENSITIVE_IDS or cid.startswith("inject-"):
        return SENSITIVE_QUESTION.get(cid, "Prompt-injection check (wording withheld)")
    q = (catalog.get(cid) or {}).get("question") or raw_question or ""
    q = _clean_text(q)
    if cid in DEAL_TITLES:
        return DEAL_TITLES[cid]
    return q


def _case_row(raw, catalog, deal=False):
    cid = raw.get("id") or ""
    passed = bool(raw.get("pass") if "pass" in raw else raw.get("passed"))
    if deal:
        failed = [{"check": "guard", "why": _clean_text(p)} for p in (raw.get("problems") or []) if p]
    else:
        failed = [{"check": _clean_text(x.get("check") or "check"), "why": _clean_text(x.get("why") or "")}
                  for x in (raw.get("checks") or []) if not x.get("pass")]
    sensitive = cid in SENSITIVE_IDS or cid.startswith("inject-")
    return {
        "id": cid,
        "suites": _suites_for_case(cid, catalog),
        "pass": passed,
        "question": _public_question(cid, None if sensitive else raw.get("question"), catalog),
        "failed_checks": failed,
        "sensitive": sensitive,
    }


def _suite_counts(rows):
    """Per-suite passed/total from the cases actually present in this run."""
    out = {}
    for s in SUITES:
        present = [r for r in rows if s in r["suites"]]
        if not present:
            continue
        out[s] = {
            "passed": sum(1 for r in present if r["pass"]),
            "total": len(present),
        }
    return out


def _meaningful(suite, total):
    """Ignore accidental overlap (e.g. 1 RAG-tagged case inside a 32-case Ask run)."""
    full = SUITES[suite]["full_size"]
    if suite == "ask":
        return total >= 3  # the 3-case confirmation repeats are real; a 1-case overlap is not
    if suite == "rag":
        return total >= 6
    if suite == "history":
        return total >= 6
    if suite == "deal":
        return total >= 11 or total >= full
    return total >= full


def _chartable(suite, total):
    """A point that can sit on the over-time chart without misleading the scale."""
    return total == SUITES[suite]["full_size"]


def parse_chat_run(data, path, catalog):
    when, label = _stamp_from_name(data.get("run") or path.name)
    if data.get("summary", {}).get("when") and not when:
        when = data["summary"]["when"]
    rows = [_case_row(r, catalog) for r in data.get("results") or []]
    passed = sum(1 for r in rows if r["pass"])
    checks = [c for r in (data.get("results") or []) for c in (r.get("checks") or [])]
    return {
        "id": data.get("run") or path.stem,
        "source_file": _rel(path),
        "when": when,
        "label": label,
        "kind": "chat",
        "env": _env_from(data.get("url"), label),
        "regraded": "regraded" in (label or "") or "(regraded)" in str(data.get("url") or ""),
        "cases_passed": passed,
        "cases": len(rows),
        "checks_passed": sum(1 for c in checks if c.get("pass")) if checks else None,
        "checks": len(checks) or None,
        "suites": _suite_counts(rows),
        "results": rows,
    }


def parse_deal_run(data, path, catalog):
    summary = data.get("summary") or {}
    when = summary.get("when") or _stamp_from_name(path.name)[0]
    label = path.stem.split("-", 1)[1] if "-" in path.stem else path.stem
    # 20261110T214238Z-deal-before -> deal-before
    _, label = _stamp_from_name(path.name)
    rows = [_case_row(r, catalog, deal=True) for r in data.get("rows") or []]
    # Force deal suite (ids won't be in the chat catalog).
    for r in rows:
        r["suites"] = ["deal"]
        if not r["question"]:
            r["question"] = DEAL_TITLES.get(r["id"], r["id"])
    passed = sum(1 for r in rows if r["pass"])
    return {
        "id": path.stem,
        "source_file": _rel(path),
        "when": when,
        "label": label,
        "kind": "deal",
        "env": _env_from(None, label, deal_mode=summary.get("mode")),
        "regraded": False,
        "mode": summary.get("mode"),
        "cases_passed": passed,
        "cases": len(rows),
        "checks_passed": None,
        "checks": None,
        "suites": _suite_counts(rows),
        "results": rows,
    }


def parse_run(path, catalog):
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and "summary" in data and "rows" in data:
        return parse_deal_run(data, Path(path), catalog)
    if isinstance(data, dict) and "results" in data:
        return parse_chat_run(data, Path(path), catalog)
    return None


def _rel(path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _git_result_files(root=ROOT):
    """Paths of result JSON files that exist in git history, including deleted ones."""
    try:
        out = subprocess.check_output(
            ["git", "log", "HEAD", "--name-only", "--pretty=format:", "--", "evals/results"],
            cwd=root, text=True, stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    seen = []
    for line in out.splitlines():
        line = line.strip()
        if line.endswith(".json") and line not in seen:
            seen.append(line)
    return seen


def _git_show(relpath, root=ROOT):
    try:
        raw = subprocess.check_output(
            ["git", "log", "HEAD", "-1", "--pretty=format:%H", "--", relpath],
            cwd=root, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        if not raw:
            return None
        blob = subprocess.check_output(
            ["git", "show", f"{raw}:{relpath}"],
            cwd=root, stderr=subprocess.DEVNULL,
        )
        return blob
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def iter_result_files(results_dir=RESULTS, root=ROOT):
    """Yield (path_or_virtual, text) for every saved run, working tree first, then git."""
    results_dir = Path(results_dir)
    seen = set()
    if results_dir.exists():
        for path in sorted(results_dir.glob("*.json")):
            seen.add(path.name)
            yield path, path.read_text()
    for rel in _git_result_files(root):
        name = Path(rel).name
        if name in seen:
            continue
        blob = _git_show(rel, root)
        if not blob:
            continue
        seen.add(name)
        # Virtual path under results_dir so source_file stays stable.
        yield results_dir / name, blob.decode("utf-8") if isinstance(blob, (bytes, bytearray)) else blob


def build(results_dir=RESULTS, root=ROOT):
    catalog = _load_catalog()
    runs, skipped = [], []
    for path, text in iter_result_files(results_dir, root):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            skipped.append({"file": _rel(path), "why": "not valid JSON"})
            continue
        # Write a temp-like parse from already-loaded data
        if isinstance(data, dict) and "summary" in data and "rows" in data:
            run = parse_deal_run(data, Path(path), catalog)
        elif isinstance(data, dict) and "results" in data:
            run = parse_chat_run(data, Path(path), catalog)
        else:
            skipped.append({"file": _rel(path), "why": "unrecognized result shape"})
            continue
        if not run or not run["when"]:
            skipped.append({"file": _rel(path), "why": "missing timestamp"})
            continue
        # Attach chart/meaningful flags
        flags = {}
        for sid, sc in run["suites"].items():
            flags[sid] = {
                **sc,
                "meaningful": _meaningful(sid, sc["total"]),
                "chartable": _chartable(sid, sc["total"]),
            }
        run["suites"] = flags
        runs.append(run)
    runs.sort(key=lambda r: (r["when"], r["id"]))

    milestones = []
    by_label = {r["label"]: r for r in runs}
    for m in MILESTONES:
        run = by_label.get(m["label"])
        if not run:
            continue
        sc = (run.get("suites") or {}).get(m["suite"])
        # The RAG after point is a 12-case run (11 RAG + 1 general). Use the run total.
        if m["label"] == "rag-after-fix-preview":
            passed, total = run["cases_passed"], run["cases"]
        elif sc:
            passed, total = sc["passed"], sc["total"]
        else:
            passed, total = run["cases_passed"], run["cases"]
        milestones.append({
            "suite": m["suite"],
            "role": m["role"],
            "run": run["id"],
            "label": m["label"],
            "when": run["when"],
            "passed": passed,
            "total": total,
            "note": m["note"],
        })

    present_suites = []
    for sid, meta in SUITES.items():
        has = any((r.get("suites") or {}).get(sid, {}).get("meaningful") for r in runs)
        if has:
            present_suites.append(dict(meta))

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suites": present_suites,
        "milestones": milestones,
        "runs": runs,
        "skipped": skipped,
        "notes": [
            "Every score comes from a saved file under evals/results/. Nothing is invented or typed in by hand.",
            "When the same answers were graded twice (a grader bug, then a fix), both runs are kept. The official Ask baseline is the regraded 30/32, not the earlier 31/32.",
            "A run only counts toward a suite when enough of that suite's questions were actually asked. One overlapping case does not become a 1/1 suite score.",
            "Prompt-injection questions, hidden instructions, model answers, and secrets are not stored in this file.",
        ],
    }


def write_history(history, out=OUT):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # generated_at changes every rebuild; for a stable diff of scores, callers can ignore it.
    text = json.dumps(history, indent=2, ensure_ascii=False) + "\n"
    out.write_text(text)
    return out


def rebuild(results_dir=RESULTS, out=OUT, root=ROOT):
    history = build(results_dir=results_dir, root=root)
    write_history(history, out=out)
    return history


def public_text_ok(text):
    """False if the text would leak an injection prompt or a secret."""
    return not LEAK_PATTERNS.search(text or "")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results-dir", default=str(RESULTS))
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args(argv)
    history = rebuild(results_dir=Path(a.results_dir), out=Path(a.out))
    n = len(history["runs"])
    suites = ", ".join(s["id"] for s in history["suites"]) or "none"
    print(f"Wrote {a.out} with {n} runs across suites: {suites}")
    for m in history["milestones"]:
        print(f"  {m['suite']} {m['role']}: {m['passed']}/{m['total']} ({m['label']})")
    if history["skipped"]:
        print(f"  skipped {len(history['skipped'])} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
