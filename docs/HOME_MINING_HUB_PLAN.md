# Bitaxe Radar → Home Mining Hub: Expansion Plan (written 2026-10-21)

Owner's vision (the owner, Oct 21): grow from a Bitaxe price tracker into the place US home miners go to **pick, buy and run** a home miner, including heater miners. Mining first, nodes later.

**VERIFIED** = read on the linked page or endpoint on 2026-10-21. **ESTIMATE** = judgment, not a fact. This doc is internal. Nothing here has been sent, signed up for or published, and **any application or outreach needs the owner's yes first.**

---

## 0. Why this is worth doing (one paragraph)

Bitaxe-class miners cost $60-250, so a 3-5% commission is $2-12 per sale. Home and heater miners cost **$219-1,869**, so the same click is worth **$10-90** at 5% (ESTIMATE, based on the prices below). Same shoppers, same site, 5-10x the money per sale. Heater miners are also seasonal: **demand peaks Nov-Feb**, which lines up with Black Friday (Nov 27).

---

## 1. Home / heater miners worth tracking (US buyers)

Prices are USD from the seller page on 2026-10-21 unless marked. "Scrape" = how our collector could read price and stock.

| Model | Type | Hashrate / Watts | US price (seller) | Other US sellers | Scrape | Source |
|---|---|---|---|---|---|---|
| **Canaan Avalon Nano 3S** | Desk miner / mini heater | 6 TH/s / 140 W | **$219** Solo Satoshi (in stock); $249 Altair (sale); $299 Canaan | Canaan shop | Solo Satoshi: Woo Store API ✅. Altair: HTML + JSON-LD (Store API returns empty). Canaan: **blocks bots (403)** | shop.canaan.io/products/avalon-nano-3s-1, solosatoshi.com, altairtech.io |
| **Canaan Avalon Mini 3** | Room heater miner | 37.5 TH/s / 800 W | **$749.99** Solo Satoshi (**out of stock**); **$789** Altair; $999 Canaan (Texas warehouse) | D-Central CA$1,750 | same as above; D-Central Woo Store API ✅ | shop.canaan.io/products/avalon-mini-3 |
| **Canaan Avalon Q** | Big heater miner (~1.7 kW heat) | 90 TH/s / 1,674 W | **$1,349** Solo Satoshi (in stock); $1,499 Altair; ~$1,850 Amazon 3rd-party | — | Solo Satoshi ✅, Altair HTML | solosatoshi.com/product/canaan-avalon-q-90th-bitcoin-home-miner/ |
| **Heatbit Trio** | Space heater + purifier + miner | 10 TH/s / 400 W mining (1,500 W total heat) | **$849** preorder (RRP $1,049), Fall '26 batch | Heatbit direct only | **Shopify `.js` + `/products.json` ✅** (tested: price + `available`) | heatbit.com/products/heatbit-trio |
| **Heatbit Maxi / Maxi Pro** | Heater miner | Maxi 39 TH/s (per compare page); Maxi Pro: not listed in what we read | Maxi **$1,249**, Maxi Pro **$1,499** | Heatbit direct | Shopify ✅ | heatbit.com/pages/compare |
| **Heatbit Canvas** | Wall heater + miner | 10 TH/s | **$399** (RRP $599) | Heatbit direct | Shopify ✅ | heatbit.com/pages/compare |
| **Heatbit Bitair** | Air purifier + miner | 1.2 TH/s / 25 W (Altair listing) | **$179** Heatbit / Altair (preorder); $179.99 Solo Satoshi | Altair, Solo Satoshi | Shopify ✅ / Woo ✅ | heatbit.com/products.json, altairtech.io |
| **Braiins Mini Miner BMM 101** | Desk lottery miner | 1 TH/s / 40 W | $299 Braiins list price; $199 Punkhash (3rd-party, "while stocks last") | Altair? not seen | Braiins store moved to braiinsforge.com, not Shopify JSON (404). HTML only | braiinsforge.com/hardware/mini-miner-bmm-101, punkhash.com |
| **Hammer Miner BC04 / BC08 / Thor P2** | Desk miners | BC04 6 TH/s 96 W; BC08 12 TH/s; Thor P2 10 TH/s | $215 / $519 / $369 at Altair | — | Altair HTML | altairtech.io home-miners category |
| **GekkoScience KBox 22TH / Fluminer T3 v2** | Quiet home units | KBox 22 TH/s | $849 / $1,869 at Altair | — | Altair HTML | same |
| **D-Central Space Heater editions** (S9 / S19 / StealthMiner) | Refurb Antminers in heater cases | S19 SHE: specs on product page | **CA$235 / CA$755 / CA$849.99** (CAD; Canada-based, ships to US: ESTIMATE, verify) | — | Woo Store API ✅ | d-central.tech/product-category/bitcoin-mining-heaters/ |
| **Bitmain Antminer** | — | — | **Skip for now.** Bitmain has no current stock quiet 110 V home/heater unit (only the 2016 R4). The 110 V "Loki" and heater builds are 3rd-party mods (D-Central). | — | — | bitmain.com, d-central.tech |

**Pick for the first launch (8 models):** Nano 3S, Mini 3, Avalon Q, Heatbit Trio, Heatbit Maxi, Heatbit Canvas, Braiins BMM 101, Hammer BC04. That covers $199 → $1,499 and every seller we already have or are applying to.

### Affiliate programs for these sellers

| Seller | Program | Rate | Cookie | Payout / platform | Signup | Status |
|---|---|---|---|---|---|---|
| **Heatbit** | Yes | **5%** of final price (excl. tax/shipping), VERIFIED terms | not stated in terms | Min **$50 + 2 orders**; paid in store credit, BTC, USDC or USDT (crypto has a **90-day hold**); must click "request payout" at least once per 12 months or older commissions are zeroed. Platform: **GoAffPro** (portal at pro.heatbit.com). One directory claims impact.com: unverified | https://pro.heatbit.com/create-account (terms: https://heatbit.com/pages/affiliate-program-terms-of-use) | **Not applied. Draft for owner approval.** |
| **Solo Satoshi** | Yes | not published | not published | PayPal, monthly, 14-day delay | solosatoshi.com/affiliate-registration/ | Applied Oct 16, pending. They carry the Nano 3S, Mini 3, Q and Bitair, so **approval here monetizes most of the hub.** |
| **Altair Technology** | Yes | not published ("a fraction of the sales revenue") | not published | Register a store account, then apply | https://altairtech.io/affiliate-home/ | 3rd of the "3 signups", not yet submitted |
| **D-Central** | Yes | 3-5% (per earlier research) | — | — | — | Submitted Oct 21, no confirmation yet |
| **Canaan (official shop)** | **None found.** Only a 2024 10%-off referral promo, now expired | — | — | — | — | Link to Canaan only as a non-paying "official" reference; send buy clicks to authorized US distributors |
| **Braiins** | **No store affiliate.** Braiins OS referral needs ≥50 PH/s of new hashrate: not for us | — | — | — | braiins.com/os-firmware/referral | Skip |
| **Bitmain** | Not researched (no home product to track) | — | — | — | — | Skip |

---

## 2. Free data for a "Mining stats" section

| Stat | Source (free, no key) | Endpoint (tested 2026-10-21) |
|---|---|---|
| Network hashrate + difficulty | mempool.space | `/api/v1/mining/hashrate/3d` → current ≈ **1,050 EH/s**, difficulty ≈ 140.6 T |
| Next difficulty adjustment | mempool.space | `/api/v1/difficulty-adjustment` → **+6.57%**, block 973,728, ~8 days out |
| Fees | mempool.space | `/api/v1/fees/recommended` (all 1 sat/vB today) |
| Block reward + fees (last 144 blocks) | mempool.space | `/api/v1/mining/reward-stats/144` → 452.49 BTC/day incl. 2.49 BTC fees |
| BTC price | mempool.space | `/api/v1/prices` → $83,442 |
| **Hashprice** | **Compute it ourselves** from the above: `(24h reward BTC × price) ÷ network PH/s`. Today ≈ **$36 / PH / day** (≈ $0.036 / TH / day), ESTIMATE from those numbers. Luxor Hashrate Index's hashprice API needs a **paid Premium key**, so we don't use it. | — |

**Terms:** mempool.space's public API is free with no auth but has **undisclosed rate limits (HTTP 429, repeat abuse = ban)**; heavy or commercial use is pointed at Mempool Enterprise. Their data is provided "as is". **Plan:** fetch once per collector run (every 6 h, maybe hourly for the stats page), cache to `data/stats.json`, credit "Data: mempool.space" on the page, and never hot-link it from visitors' browsers.

**Customer-friendly framing:** show 5 tiles (Hashrate, Next adjustment, Hashprice, Fees, Block reward) plus one line: "What this means for your miner" (e.g. "A 6 TH/s Nano 3S earns about $0.22/day at today's hashprice before power"). Reuse the existing running-cost calculator.

---

## 3. Newsletter plan

**Format: "Home Mining Weekly"** (every Thursday, 3-minute read)
1. **Deals:** top 5 price drops / back-in-stock from our own data (auto-generated)
2. **Stats:** the 5 tiles above plus a one-line "what changed"
3. **One news item** with a 2-sentence "why it matters to home miners"
4. One sponsor slot (when we have one), clearly labelled

**Tooling:** we already have Resend plus a confirmed-signup flow. Add a "weekly" list. The draft is generated from data, and the owner approves each send (ESTIMATE: 10 min/week for him).

**How sponsors price this niche (real examples):**
| Who | Price | Audience | Source |
|---|---|---|---|
| Bitcoin Magazine daily newsletter | **$2,000/day premium, $1,000/day standard**, $10k minimum spend | 53,000+ subscribers | bitcoinmagazine.com/newsletter-advertising (VERIFIED) |
| Hashrate.no (mining site) | banner CPM **$4-7**, sponsored article **$400** | — | sevio.com hashrate media kit PDF (via search, not opened) |
| WeAreBitcoin.org | per-issue, rate not published | — | wearebitcoin.org/sponsors |

That works out to roughly **$20-40 per 1,000 subscribers per send** for Bitcoin-only lists (ESTIMATE from BM's $1-2k / 53k). For us: **~1,000 subscribers ≈ $25-50/send, ~5,000 ≈ $150-250/send** (ESTIMATE). Until then, the sponsor slot is our own best affiliate deal.

**Growth tactics (free):**
- Signup box on every model page: "Get the weekly deals + back-in-stock alerts" (we already capture price-alert emails, so ask for opt-in to the weekly as well)
- Post the weekly stats tile image on @BitaxeRadar every Thursday and link the archive
- Public web archive of each issue (SEO pages that compound)
- Answer "is a heater miner worth it?" threads on r/BitcoinMining and r/Bitaxe with a link to our guide (owner approves each post)
- Black Friday "Home Mining Deals" issue as the first big push

---

## 4. Phased roadmap (ranked by revenue impact ÷ effort, first dollar first)

### Phase 1: next 2 weeks (Oct 21 → Nov 4)
| # | Action | Impact | Effort | Owner needed? |
|---|---|---|---|---|
| 1 | **Draft Heatbit affiliate application** (5%, ~$42 per Trio sale) | High | 15 min | **Yes, approve signup** |
| 2 | **Finish the Altair signup** (sells Nano 3S, Mini 3, Q, Hammer, Heatbit: the broadest US home-miner catalog) | High | 15 min | Yes, approve + password |
| 3 | **Nudge Solo Satoshi** on the Oct 16 application (they carry the Avalon line + Bitair) | High | 5 min | Yes, approve email |
| 4 | Add the **8 home/heater models** to the collector (Solo Satoshi Woo API, Heatbit Shopify JSON, Altair JSON-LD, D-Central Woo API) | High | 1-2 days (me) | Review preview |
| 5 | New **"Heater miners"** page + 1 guide: "Bitcoin heater miners explained: do they really heat your room?" | Med-High (SEO, seasonal) | 1 day | Approve before live |

### Phase 2: by Black Friday (Nov 5 → Nov 27)
| # | Action | Impact | Effort |
|---|---|---|---|
| 6 | **Mining stats page** (mempool data, hashprice, "what it means for your miner") | Med (repeat visits, SEO) | 1 day |
| 7 | **"Which home miner should I buy?"** chooser (budget → noise → room size → pick) | High conversion | 1-2 days |
| 8 | Launch **Home Mining Weekly** (first issue ~Nov 12, BF issue Nov 26) | Med now, high later | 0.5 day setup + weekly |
| 9 | **Black Friday deals page** covering Bitaxe + home + heater miners, with daily price checks Nov 20-Dec 1 | **Highest single window** | 0.5 day |
| 10 | X: weekly stats card + "heater miner of the week" | Low-Med | ongoing |

### Phase 3: Dec → Jan
| # | Action | Impact |
|---|---|---|
| 11 | Heating-cost calculator: "miner vs. space heater" with your $/kWh and gas/electric heat | High (unique tool, winter searches) |
| 12 | Model comparison pages (Nano 3S vs Bitaxe Gamma, Mini 3 vs Heatbit Maxi, Avalon Q vs Heatbit Maxi Pro) | Med-High SEO |
| 13 | First newsletter / site **sponsor pitch** (once traffic + subscriber numbers exist from Cloudflare analytics) | Med |
| 14 | Guides: "Mining at home on 120 V: circuits & the 80% rule", "Pool vs solo for home miners", "Quietest miners" | Med SEO |
| 15 | Later: nodes section (owner wants this after mining) | — |

**Revenue sanity check (ESTIMATE, not a promise):** 4 heater-miner sales/month at ~$40 commission ≈ $160/mo, plus Bitaxe sales and later sponsors. That is the realistic path from "first dollar" to "low hundreds" this winter.

### Affiliate applications to draft (owner must approve each)
1. **Heatbit**: https://pro.heatbit.com/create-account: 5%, GoAffPro, $50 + 2-order minimum, crypto/store-credit payouts
2. **Altair Technology**: https://altairtech.io/affiliate-home/: rate not published, needs a store account first
3. **Solo Satoshi**: follow-up on the pending Oct 16 application
4. (Optional) Ask **Canaan** by email whether they have a partner/affiliate program: none is public

---

## 5. Site structure proposal (keeps the clean, customer-first design)

**New top nav (5 items max):**
`Bitaxe & desk miners` · `Heater & home miners` · `Deals` · `Mining stats` · `Guides`

| Page type | URL pattern | What the shopper sees |
|---|---|---|
| Category hub | `/heater-miners/`, `/home-miners/` | Photo cards: best price, in-stock badge, hashrate, watts, noise, "See prices" |
| Model page (existing template) | `/models/<slug>/` | Photo, cheapest in-stock deal, one big buy button. Specs + "heat output" + "cost to run/day" folded below |
| Stats | `/stats/` | 5 tiles + "what it means for your miner" + updated time |
| Chooser | `/which-miner/` | 3-4 taps → recommended model(s) |
| Calculator | `/calculator/` | Miner vs. heater cost, earnings at today's hashprice |
| Guides | `/guides/<slug>/` | Short, photo-led, one CTA to the relevant category |
| Newsletter archive | `/weekly/<date>/` | Each issue as a page + signup box |
| Deals | `/deals/` (existing) | Add a home/heater tab; Black Friday banner Nov 20-Dec 1 |

**Rules carried over from the redesign:**
- No internal notes on public pages ("not tracked yet", collector status, TODOs stay in `docs/` or admin-only data). Keep the existing build check that blocks them.
- Every buy button is labelled; the affiliate disclosure stays in the footer and near buy buttons (FTC; Heatbit/Altair will check).
- Non-paying sellers (e.g. Canaan direct) still get listed if they're cheapest. Trust beats commission.
- Real product photos only (same sourcing rules as `docs/IMAGE_SOURCES.md`).
