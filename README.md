# Bitaxe Radar (local prototype)

Price/stock tracker for small solo Bitcoin "lottery" miners (Bitaxe, Nerdaxe, NerdQaxe) across sellers.
Static site (plain HTML/CSS/JS, no framework, no build step beyond a 10-line Python copy) + a stdlib-only Python collector.

```
python3 collector/collect.py     # ~50 s; writes data/latest.json and appends data/history.json
python3 build_site.py            # writes site/data.js from data/
cd site && python3 -m http.server 8765   # open http://127.0.0.1:8765
```

* `collector/collect.py` — adapters for Bitcoin Merch (Shopify JSON), Solo Satoshi (WooCommerce Store API, variation-level stock), Bitaxe.de (JSON-LD), Power Mining (Shopify JSON + page text). Explicit product maps, no fuzzy matching. A failing seller keeps its last data flagged `stale`. History is appended only when price/stock changes or every ~20 h.
* `site/` — comparison tables (best in-stock highlighted), price-history chart (SVG), electricity-cost calculator (adjustable $/kWh, custom watts), price-drop signup (UI only — sends/stores nothing), affiliate disclosure, "solo mining is a lottery" banner, coverage/not-tracked list.
* `docs/DATA_VERIFICATION.md` — what was verified, sources, gotchas, unscrapable sellers.
* `docs/templates/collect.yml.example` — inactive GitHub Actions template for scheduled collection.

Not done on purpose: no deploy, no accounts, no emails, no real affiliate links (marked `[affiliate link placeholder]`; the "View at seller" buttons are plain, non-affiliate product URLs).
Price history only has the data points collected so far (first run 2026-10-16); nothing was back-filled or invented.
