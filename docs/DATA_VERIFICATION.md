# Data verification log — 2026-10-16 (checked ~08:20-08:35 ET)

"Verified" = fetched directly from the seller's own page/feed by the collector (or by hand with curl) on the date above.
Anything from a search-result snippet or third-party article is listed separately and is NOT in data/latest.json.

## Verified and collected (data/latest.json) — 20 offers, 4 sellers, 8 models
| Seller | How read | Models with data |
|---|---|---|
| Bitcoin Merch (USD) | https://bitcoinmerch.com/products.json (public Shopify feed) | Supra, Ultra, Gamma, Gamma Duo 650, GT 801, Nerdaxe Gaia, NerdQaxe++ 4.8 |
| Solo Satoshi (USD) | https://www.solosatoshi.com/wp-json/wc/store/v1/products?slug=… + per-variation calls | Supra (OOS), Gamma 602 (OOS), Gamma Duo 650, GT 801, NerdQaxe++ Rev 7 (OOS) |
| Bitaxe.de (EUR) | schema.org JSON-LD on https://bitaxe.de/produkt/<slug> | Gamma 601, GT, Nerdaxe Gamma, Nerdaxe Gaia, NerdQaxe++ 4.8 |
| Power Mining (EUR) | https://powermining.io/products.json + product-page text | Gamma (pre-order, "shipping end of October, 2026" on page), Nerdaxe Gamma, NerdQaxe++ 4.8 |

### Gotchas found (important for scraper correctness)
* **Solo Satoshi:** for variable products the product-level `is_in_stock` is wrong (True while *all* variations were out of stock for Gamma 602 and NerdQaxe++ Rev 7). The collector checks each variation and compares the North-America-power-supply, no-stand/no-fan configuration.
* **Power Mining:** Shopify `available` is true for pre-order items. The collector reads the page text for "pre-order". NerdQaxe++ has a variant literally named `NONE` priced lower (€338.80, apparently no PSU) — skipped; US variant used (€363.00).
* **Bitcoin Merch:** product titles say "w/ Power Supply" for most items but NOT for the Bitaxe 801 GT listing — flagged "unverified" in the Config column. Its robots.txt/agents.md ask agent traffic to identify itself and respect 429/Retry-After; collector sends a descriptive User-Agent and ~1 request/page. Revisit (Web Bot Auth / ask for a feed) before running at scale.
* **Currencies/tax:** Bitaxe.de prices are EUR incl. VAT; Power Mining's tax basis isn't stated; shipping/duties aren't included anywhere. EUR→USD uses the ECB reference rate via frankfurter.dev (1.1208 on 2026-10-15) and is labelled approximate.
* Bitaxe.de's homepage card labelled the Gamma "Nachbestellung" (backorder) but its product page says "Auf Lager · in 24 h verschickt" and JSON-LD says InStock; the product page was used.
* Revisions/hashrates differ between sellers for the "same" model (e.g. NerdQaxe++ Rev 7 vs 4.8 TH/s standard vs Rev 6.1). The table shows the config; prices aren't strictly apples-to-apples.

## Identified but NOT scrapable / not collected
* MineShop (mineshop.eu): HTTP 403 to our collector. (A 14 Oct 2026 article on cryptocodes.eu reported Gamma 601 sold out there — secondary source, not used.)
* NerdQaxe Store (nerdqaxestore.com): TLS/connection failure (curl exit 35) from the box; WebFetch got HTTP 500. Search snippet claimed Rev 6.1 $249 — not verified, not used.
* Plebsource (plebsource.com): TLS/connection failure from the box.
* Altair Technology (altairtech.io): Woo Store API empty, search returns HTTP 202 (bot challenge).
* TinyChipHub (tinychiphub.com): JS-rendered Shopline storefront; no usable feed.
* Aggregators (MinerCompare, Mining Now): competitors — research only, not scraped.
* Deliberately excluded as unvetted: CryptoMinerBros (HK-based, wire/crypto payment, $69 Gamma 601 listing — far below every vetted seller), MillionMiner ($149 Gamma text, no price in structured data), bitaxehardware.com ($79 "MSRP $119" Gamma). Vet before ever listing; a price site that lists a scam shop damages trust.

## Spec figures used for the electricity estimate (vendor-stated, approximate)
Gamma ~1.1–1.3 TH/s, 15–18 W (Solo Satoshi, Bitaxe.de, Power Mining pages) · Gamma Duo 1.63 TH/s ~25.8 W (Solo Satoshi article) · GT 2.15 TH/s ~43 W (Solo Satoshi, Bitaxe.de) · Nerdaxe Gaia ~2.6 TH/s 25 W (Bitaxe.de) · NerdQaxe++ 4.8 TH/s 80 W (Power Mining page) · Supra ~0.7 TH/s 15 W and Ultra ~0.5 TH/s 12 W (MinerLottery spec pages, third-party, via search snippet — not fetched). Watts are editable in the "My own wattage" row.

## Affiliate programs (facts seen, none joined)
* Power Mining: "up to 10%" via GoAffPro, join page https://powermining.io/pages/affiliate (their page; contact rolands@powermining.io for review units/promos).
* Bitcoin Merch 3.3% and Bitaxe.de: reported in the earlier research / third-party article; not confirmed on the sellers' own pages in this pass.
