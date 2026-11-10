"""HTML for the public /evals/ page. Used by build_site.py. Stdlib only.

The page shows saved scores only. Prompt-injection wording, model answers,
API keys and internal prompts are never written into the HTML.
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

ENV_LABEL = {
    "live": "Live Worker",
    "preview": "Test Worker",
    "local": "Local",
    "harness": "Harness (no live model)",
    "unknown": "Saved run",
}

RUN_TITLE = {
    "baseline": "Ask baseline (first grade)",
    "baseline-pirate-check": "Prompt-injection recheck",
    "after-fix-local": "After fix, local (first grade)",
    "after-fix-local-regraded": "After fix, local (regraded)",
    "baseline-regraded": "Ask baseline (regraded)",
    "after-fix-repeat1": "After-fix confirmation (3 cases)",
    "after-fix-repeat2": "After-fix confirmation, second try",
    "after-fix-live": "After fix, live",
    "sql-before-prod": "Price history, before the tool",
    "sql-after-preview": "Price history, after (test Worker)",
    "sql-full-preview": "Full Ask + history (test Worker)",
    "rag-before-prod": "Guide search, before the tool",
    "rag-after-preview": "Guide search, first after (test Worker)",
    "rag-full-preview": "Full suite (test Worker)",
    "rag-after-fix-preview": "Guide search, after citation fix",
    "live-smoke-sql-rag": "Live smoke test (history + guides)",
    "live-fix-in-data": "Live recheck after in_data fix",
    "deal-before": "Deal agent, before",
    "deal-scripted": "Deal agent, scripted harness",
    "deal-template": "Deal agent, no-AI template",
    "deal-live-first-live": "Deal agent, live Claude",
}


def esc(s):
    return _html.escape("" if s is None else str(s), quote=True)


def fmt_time(iso):
    d = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(ET)
    return f"{d:%b} {d.day}, {d.year} {d.hour % 12 or 12}:{d:%M} {'AM' if d.hour < 12 else 'PM'} ET"


def tag_time(iso):
    return f'<time datetime="{esc(iso)}">{esc(fmt_time(iso))}</time>'


def run_title(run):
    return RUN_TITLE.get(run.get("label") or "", (run.get("label") or run.get("id") or "Run").replace("-", " "))


def score_class(passed, total):
    if total <= 0:
        return "mid"
    if passed == total:
        return "ok"
    if passed == 0:
        return "bad"
    return "mid"


def _pct(passed, total):
    if not total:
        return 0
    return round(100 * passed / total, 2)


def _latest_chartable(runs, suite):
    hits = [r for r in runs if (r.get("suites") or {}).get(suite, {}).get("chartable")]
    return _preferred(hits)[-1] if hits else None


def _latest_meaningful(runs, suite):
    hits = [r for r in runs if (r.get("suites") or {}).get(suite, {}).get("meaningful")]
    return hits[-1] if hits else None


def _preferred(runs):
    """At the same timestamp, prefer a live run, then a scripted harness, over a template."""
    def key(r):
        label = r.get("label") or ""
        env = r.get("env") or ""
        if env == "live" or "live" in label:
            bump = 3
        elif "scripted" in label:
            bump = 2
        elif "template" in label:
            bump = 0
        else:
            bump = 1
        return (r["when"], bump)
    return sorted(runs, key=key)


def _milestones_for(history, suite):
    return [m for m in history.get("milestones") or [] if m["suite"] == suite]


def _milestone_pairs(history):
    by = {}
    for m in history.get("milestones") or []:
        by.setdefault(m["suite"], {})[m["role"]] = m
    return by


def _points(runs, suite):
    out = []
    for r in runs:
        sc = (r.get("suites") or {}).get(suite) or {}
        if not sc.get("chartable"):
            continue
        out.append({
            "when": r["when"], "label": r["label"], "title": run_title(r),
            "passed": sc["passed"], "total": sc["total"], "env": r.get("env") or "unknown",
        })
    return out


def meaning_line(history):
    """One-line 'what this means' built from saved milestone scores, never typed in by hand."""
    by = _milestone_pairs(history)
    bits = []
    if "ask" in by and "before" in by["ask"] and "after" in by["ask"]:
        a, b = by["ask"]["before"], by["ask"]["after"]
        bits.append(f'the everyday chat went from <b>{a["passed"]}/{a["total"]}</b> to <b>{b["passed"]}/{b["total"]}</b> after two bugs were fixed')
    if "history" in by and "before" in by["history"] and "after" in by["history"]:
        a, b = by["history"]["before"], by["history"]["after"]
        bits.append(f'price history went from <b>{a["passed"]}/{a["total"]}</b> to <b>{b["passed"]}/{b["total"]}</b>')
    if "rag" in by and "before" in by["rag"] and "after" in by["rag"]:
        a, b = by["rag"]["before"], by["rag"]["after"]
        rag = f'guide search from <b>{a["passed"]}/{a["total"]}</b> to <b>{b["passed"]}/{b["total"]}</b>'
        if a["total"] != b["total"]:
            rag += (f' (the after-run added a {b["total"]}th general-knowledge case '
                    f'the citation bug had broken)')
        bits.append(rag + ', once those tools were added')
    if "deal" in by and "before" in by["deal"] and "after" in by["deal"]:
        a, b = by["deal"]["before"], by["deal"]["after"]
        live = "live" in (b.get("label") or "")
        how = "with live Claude" if live else "in a test harness"
        bits.append(f'a daily deal-picking agent scored <b>{b["passed"]}/{b["total"]}</b> {how}')
    if not bits:
        return ""
    # "A and B, C, and D" — first clause stands alone, then the rest.
    if len(bits) == 1:
        body = bits[0]
    elif len(bits) == 2:
        body = bits[0] + ", and " + bits[1]
    else:
        body = bits[0] + ". " + bits[1][0].upper() + bits[1][1:]
        if len(bits) > 2:
            body += ", " + ", ".join(bits[2:-1] + ([bits[-1]] if len(bits) == 3 else []))
            if len(bits) > 3:
                body += ", and " + bits[-1] if not body.endswith(bits[-1]) else ""
    # Simpler join that's easy to read:
    if len(bits) >= 3:
        body = bits[0] + ". " + bits[1][0].upper() + bits[1][1:] + ", and " + bits[2]
        if len(bits) > 3:
            body += ". " + bits[3][0].upper() + bits[3][1:]
    return "The short version: " + body + "."


def score_chart(suite_id, suite_name, points):
    """Inline SVG line chart. The path is drawn in by evals.js (stroke-dashoffset)."""
    if len(points) < 1:
        return ""
    W, H, L, R, T, B = 640, 200, 46, 16, 16, 48
    iw, ih = W - L - R, H - T - B
    n = len(points)
    xs, ys = [], []
    for i, p in enumerate(points):
        x = L + (iw * i / (n - 1) if n > 1 else iw / 2)
        y = T + ih * (1 - (p["passed"] / p["total"] if p["total"] else 0))
        xs.append(x)
        ys.append(y)
    d = " ".join(("M" if i == 0 else "L") + f" {x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    dots, labels = [], []
    for i, p in enumerate(points):
        cls = score_class(p["passed"], p["total"])
        color = {"ok": "#34d399", "mid": "#fbbf24", "bad": "#f87171"}[cls]
        dots.append(
            f'<circle class="eval-dot" style="--i:{i}" cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="5" '
            f'fill="{color}" stroke="#0b1222" stroke-width="2">'
            f'<title>{esc(p["title"])}: {p["passed"]}/{p["total"]}</title></circle>'
        )
        lx = xs[i]
        labels.append(f'<text x="{lx:.1f}" y="{H - 28}" text-anchor="middle" fill="#97a3bb" font-size="10">'
                      f'{esc(p["passed"])}/{esc(p["total"])}</text>')
        short = p["title"]
        if len(short) > 22:
            short = short[:20] + "…"
        labels.append(f'<text x="{lx:.1f}" y="{H - 14}" text-anchor="middle" fill="#6b7894" font-size="9">{esc(short)}</text>')
    grid = []
    for frac, lab in ((0, "0%"), (0.5, "50%"), (1, "100%")):
        y = T + ih * (1 - frac)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="#24324f"/>')
        grid.append(f'<text x="{L - 8}" y="{y:.1f}" text-anchor="end" dominant-baseline="middle" fill="#6b7894" font-size="11">{lab}</text>')
    title_id = f"eval-chart-{suite_id}-title"
    desc_id = f"eval-chart-{suite_id}-desc"
    desc = ", ".join(f"{p['title']} {p['passed']}/{p['total']}" for p in points)
    return f'''<div class="chart eval-chart eval-reveal">
<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="{title_id} {desc_id}" preserveAspectRatio="xMidYMid meet">
<title id="{title_id}">{esc(suite_name)} eval scores over time</title>
<desc id="{desc_id}">{esc(desc)}</desc>
{"".join(grid)}
<path class="eval-line" pathLength="1" fill="none" stroke="#f7931a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>
{"".join(dots)}
{"".join(labels)}
</svg>
</div>'''


def hero_cards(history):
    """Big after-scores for a hiring-manager glance, with the before score underneath."""
    cards = []
    by = _milestone_pairs(history)
    for suite in history.get("suites") or []:
        sid = suite["id"]
        pair = by.get(sid) or {}
        after, before = pair.get("after"), pair.get("before")
        latest = _latest_chartable(history["runs"], sid)
        if after:
            passed, total, when = after["passed"], after["total"], after["when"]
            caption = run_title({"label": after["label"]})
        elif latest:
            sc = latest["suites"][sid]
            passed, total, when = sc["passed"], sc["total"], latest["when"]
            caption = run_title(latest)
        else:
            continue
        cls = score_class(passed, total)
        from_line = ""
        if before:
            from_line = f'<div class="from-line">started at {before["passed"]}/{before["total"]}'
            if before["total"] != total:
                from_line += (
                    f' on {before["total"]} questions. The after-run added a {total}th case '
                    f'(a general-knowledge question the citation bug had broken).'
                )
            from_line += '</div>'
        latest_note = ""
        if after and latest:
            sc = latest["suites"][sid]
            if (sc["passed"], sc["total"]) != (passed, total) or latest.get("label") != after.get("label"):
                latest_note = (f'<div class="sub">Latest full run: {sc["passed"]}/{sc["total"]} '
                               f'({esc(run_title(latest))})</div>')
        cards.append(
            f'<article class="eval-score eval-reveal">'
            f'<span class="k">{esc(suite["name"])}</span>'
            f'<b class="{cls} eval-count" data-pass="{passed}" data-total="{total}">{passed}/{total}</b>'
            f'{from_line}'
            f'<div class="sub">{esc(caption)} · {tag_time(when)}</div>'
            f'{latest_note}</article>'
        )
    return f'<div class="eval-scores">{"".join(cards)}</div>' if cards else ""


def before_after(history):
    names = {s["id"]: s["name"] for s in history.get("suites") or []}
    items = []
    for sid, pair in _milestone_pairs(history).items():
        if "before" not in pair or "after" not in pair:
            continue
        a, b = pair["before"], pair["after"]
        items.append(
            f'<article class="eval-reveal" style="--from:{_pct(a["passed"], a["total"])}%;--to:{_pct(b["passed"], b["total"])}%;">'
            f'<h3>{esc(names.get(sid, sid))}</h3>'
            f'<p><span class="from">{a["passed"]}/{a["total"]}</span><span class="arrow"> → </span>'
            f'<span class="to">{b["passed"]}/{b["total"]}</span></p>'
            f'<div class="eval-meter" aria-hidden="true"><span class="eval-meter-to"></span><span class="eval-meter-from"></span></div>'
            f'<p class="hint">{esc(a["note"])} Then: {esc(b["note"])}</p></article>'
        )
    if not items:
        return ""
    return ('<section class="eval-reveal" aria-labelledby="h-ba"><h2 id="h-ba">Before and after</h2>'
            f'<div class="eval-ba">{"".join(items)}</div></section>')


def questions_block(run, suite):
    """Failures visible; the full list sits behind a smooth expand/collapse."""
    rows = [r for r in run.get("results") or [] if suite in (r.get("suites") or [])]
    if not rows:
        return ""
    failed = [r for r in rows if not r.get("pass")]
    n_pass, n_fail, n = len(rows) - len(failed), len(failed), len(rows)
    if n_fail:
        lead = (f'<p class="eval-fail-lead"><strong>{n_fail} failed</strong>, {n_pass} passed '
                f'in this run. The failures are listed first.</p>')
        visible = question_table({**run, "results": failed}, suite)
    else:
        lead = f'<p>All <strong>{n} questions</strong> in this run passed.</p>'
        visible = ""
    fold = (
        f'<details class="eval-fold">'
        f'<summary>Show all {n} questions</summary>'
        f'<div class="eval-fold-body"><div>{question_table(run, suite)}</div></div>'
        f'</details>'
    )
    return lead + visible + fold


def suite_sections(history):
    blocks = []
    for suite in history.get("suites") or []:
        sid = suite["id"]
        points = _points(history["runs"], sid)
        after = next((m for m in _milestones_for(history, sid) if m["role"] == "after"), None)
        if after and not any(p["label"] == after["label"] for p in points):
            points.append({
                "when": after["when"], "label": after["label"],
                "title": run_title({"label": after["label"]}),
                "passed": after["passed"], "total": after["total"], "env": "preview",
            })
            points.sort(key=lambda p: (p["when"], p["label"]))
        chart = score_chart(sid, suite["name"], points)
        latest = _latest_meaningful(history["runs"], sid)
        qblock = questions_block(latest, sid) if latest else "<p class=\"hint\">No saved run for this suite yet.</p>"
        latest_line = ""
        if latest:
            sc = latest["suites"][sid]
            extra = "" if sc.get("chartable") else f' This run asked {sc["total"]} of {suite["full_size"]} questions in the full set.'
            latest_line = (f'<p>Latest run: <strong>{esc(run_title(latest))}</strong> '
                           f'({sc["passed"]}/{sc["total"]} on this suite, {ENV_LABEL.get(latest.get("env"), latest.get("env"))}, '
                           f'{tag_time(latest["when"])}).{extra}</p>')
        earlier_fails = ""
        full = _latest_chartable(history["runs"], sid)
        if full and (not latest or full["id"] != latest["id"]):
            failed = [r for r in full.get("results") or []
                      if sid in (r.get("suites") or []) and not r.get("pass")]
            if failed:
                sc = full["suites"][sid]
                earlier_fails = (
                    f'<h3>Failures in the last full run</h3>'
                    f'<p class="hint">{esc(run_title(full))} scored {sc["passed"]}/{sc["total"]} on this suite '
                    f'({ENV_LABEL.get(full.get("env"), full.get("env"))}, {tag_time(full["when"])}). '
                    f'The later run above did not repeat every question, so the failures are listed here.</p>'
                    + question_table({**full, "results": failed}, sid)
                )
        blocks.append(
            f'<section class="eval-reveal" id="suite-{esc(sid)}" aria-labelledby="h-{esc(sid)}">'
            f'<h2 id="h-{esc(sid)}">{esc(suite["name"])}</h2>'
            f'<p>{esc(suite["tests"])}</p>'
            f'<p>{esc(suite["grading"])}</p>'
            f'{chart}{latest_line}{qblock}{earlier_fails}</section>'
        )
    return "".join(blocks)


def question_table(run, suite):
    rows = [r for r in run.get("results") or [] if suite in (r.get("suites") or [])]
    if not rows:
        return ""
    body = []
    for r in rows:
        if r.get("pass"):
            mark = '<span class="eval-pass">Pass</span>'
            why = ""
            cls = ""
        else:
            mark = '<span class="eval-fail">Fail</span>'
            why = "; ".join(f'{c["check"]}: {c["why"]}' for c in (r.get("failed_checks") or []) if c.get("why") or c.get("check"))
            why = f'<div class="eval-why">{esc(why)}</div>' if why else ""
            cls = " class=\"eval-fail-row\""
        body.append(f'<tr{cls}><td>{mark}</td><td><code>{esc(r["id"])}</code><br>{esc(r.get("question") or "")}{why}</td></tr>')
    return ('<div class="tablewrap"><table class="eval-q"><thead><tr><th>Result</th><th>Question</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def all_runs_table(history):
    body = []
    for r in history.get("runs") or []:
        bits = []
        for sid, sc in (r.get("suites") or {}).items():
            if not sc.get("meaningful"):
                continue
            bits.append(f'{sid} {sc["passed"]}/{sc["total"]}')
        if not bits:
            bits.append(f'{r["cases_passed"]}/{r["cases"]}')
        flags = []
        if r.get("regraded"):
            flags.append("regraded")
        if any(sc.get("meaningful") and not sc.get("chartable") for sc in (r.get("suites") or {}).values()):
            flags.append("partial set")
        flag = f'<div class="eval-why">{esc(", ".join(flags))}</div>' if flags else ""
        body.append(
            f'<tr><td>{tag_time(r["when"])}</td><td>{esc(run_title(r))}{flag}</td>'
            f'<td>{esc(ENV_LABEL.get(r.get("env"), r.get("env") or ""))}</td>'
            f'<td class="num">{esc(" · ".join(bits))}</td></tr>'
        )
    return ('<section class="eval-reveal" aria-labelledby="h-all"><h2 id="h-all">Every saved run</h2>'
            '<p class="hint">Including first grades, regrades, confirmation re-runs, and partial sets. '
            'A “partial set” asked only some of that suite’s questions, so it is not plotted as a full-suite score.</p>'
            '<details class="eval-fold"><summary>Show the full run table</summary>'
            '<div class="eval-fold-body"><div>'
            '<div class="tablewrap"><table class="eval-runs"><thead><tr>'
            '<th>When</th><th>Run</th><th>Where</th><th class="num">Score</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            '</div></div></details></section>')


def page_body(history):
    notes = "".join(f"<li>{esc(n)}</li>" for n in (history.get("notes") or []))
    meaning = meaning_line(history)
    meaning_html = f'<p class="eval-meaning">{meaning}</p>' if meaning else ""
    return f'''<article>
<header class="hero">
<h1>Checking the AI's work</h1>
<p class="lede">Automatic quizzes for Ask Bitaxe Radar. Ordinary code grades every answer against live prices and our own data. Nothing is typed in by hand.</p>
{meaning_html}
</header>
{hero_cards(history)}
{before_after(history)}
<section class="eval-reveal" aria-labelledby="h-how">
<h2 id="h-how">How grading works</h2>
<p>An eval is an automatic quiz. Each question has checks written in ordinary code — not another AI judging the AI — so a score like 32/32 means the same thing every time.</p>
<p>Prices change every few hours, so the answer key is not a hardcoded dollar amount. When a run starts, the grader looks up today's prices (and, for history questions, the price database) and computes what a right answer must include.</p>
<p>Prompt-injection questions are listed only as a short summary. The exact wording is withheld so this page cannot be used as a cheat sheet.</p>
</section>
{suite_sections(history)}
{all_runs_table(history)}
<section class="eval-reveal" aria-labelledby="h-notes">
<h2 id="h-notes">How to read these scores</h2>
<ul>{notes}
<li>Most comparisons are one run per side. Claude's wording varies a little, so a one-case difference can be noise. The Ask fixes were re-checked twice on a local Worker and passed both times.</li>
<li>The grader can be wrong too. When a case fails, we read the answer before changing the bot. One early “failure” was a bug in the grader, which is why some runs are marked regraded.</li>
</ul>
</section>
<section class="eval-reveal">
<h2>Related</h2>
<p><a href="/ask/">Ask Bitaxe Radar</a> · <a href="/how-we-track/">How we track prices</a> · <a href="/guides/">Guides</a></p>
</section>
</article>'''


TITLE = "Eval scores: how we check the AI's work | Bitaxe Radar"
DESC = ("Eval scores over time for Bitaxe Radar's Ask chat, SQL history, and guide search: "
        "which questions failed and how a code-based grader checks every answer.")
