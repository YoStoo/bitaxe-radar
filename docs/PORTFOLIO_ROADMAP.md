# Bitaxe Radar — portfolio roadmap (internal)

Internal notes only. Do **not** publish, link from the site, or mention on public pages.

Updated: Nov 10, 2026 (afternoon)

## Goal

Use Bitaxe Radar as the AI practice ground and portfolio proof for AI Engineer / applied AI-ML roles (and junior SWE where tests/CI matter).

## Ordered items

| # | Item | Role tag | Status |
|---|------|----------|--------|
| (a) | Automated tests + CI (GitHub Actions) | Rokt Residency, junior SWE | **Done / largely done** — 128+ tests, GHA on collect-and-deploy |
| (b) | Clear README + 1–2 page "how I built it with AI agents and caught their mistakes" post (written by the owner) | GovAI writing sample (due **Nov 22, 2026**); AI engineer roles | **Next focus** |
| (c) | Claude-powered natural-language Q&A over price / profitability data | Claude Corps, AI engineer roles | **Done, live**: Ask chat with tool calling + 48 code-graded evals |
| (c2) | SQL price history (SQLite schema, idempotent daily upserts, `get_price_history` tool) | Gen AI Enable "SQL and relational databases" | **Done, live Nov 10**: docs/SQL.md |
| (d) | Ask-the-site RAG over site data (grown from the Q&A feature) | AI Engineer / applied AI; RAG is top skill in postings | **Done, live Nov 10**: hybrid embeddings + BM25, citations, RAG evals; docs/RAG.md |
| (e) | Price-drop agent emailing subscribers about deals | AI Engineer | Planned |
| (f) | Daily AI summary (site / market / inbox digest) | AI Engineer | Planned |
| (g) | Photo checker (computer vision) for miner listing images | Applied AI / CV | Planned |
| (h) | Price-trend chart + simple prediction | Applied AI-ML | Planned |

## Current next step

**(b)** — README + how-I-built-it post the owner writes himself. Target: GovAI writing sample due Nov 22, 2026.

Do not invent fake portfolio "ships." Keep this file in `docs/` only.
