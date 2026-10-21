# Bitaxe Radar: Content Drafts (written 2026-10-16)

**Nothing here has been posted or sent.** Every item needs owner approval first. Brand voice only (no real name), no price predictions, no income promises.

All numbers come from `data/latest.json`, collection time **2026-10-16 17:21 UTC = 1:21 PM ET**. Prices go stale: **re-check `latest.json` and only post within ~12 hours of the collection time**, otherwise regenerate. `data/history.json` currently holds a single snapshot (12:33 UTC Oct 16), so we have **no observed price drops or back-in-stock events yet**. Posts below don't claim any. Per-TH/s math uses the listed specs in `models{}`, which are nominal. EU prices (Bitaxe.de, Power Mining) are in EUR and left out of these posts because shipping/VAT bases differ.

Links point only to bitaxeradar.com, which carries the affiliate disclosure, so the posts carry no affiliate links. If a post ever links a seller directly, add "(affiliate link)".

---

## 1. Eight X / Nostr posts

Suggested pace: max 1 per day at first, owner approves each. Suggested order: 3, 2, 4, 7, 1, 5, 8, then 6 a week later. Profile bio should say "Price tracker for Bitaxe-style miners. Some links earn us a commission."

### Post 1: Seller markdown

```
Bitaxe GT (801): Bitcoin Merch lists it at $174.99 in stock, marked down from $299.99 on their own page. Solo Satoshi has it at $195.99. Prices checked Oct 16, 1:21 PM ET. Live prices: https://bitaxeradar.com/models/bitaxe-gt-801/
```

- **Data used:** Bitaxe GT 801. Offers `bitcoinmerch:bitaxe-gt-801` (price 174.99, compare_at 299.99, in stock) and `solosatoshi:bitaxe-gt-801` (195.99, in stock).
- **Link:** https://bitaxeradar.com/models/bitaxe-gt-801/
- **Length:** 208 chars as X counts it (links count as 23); 230 chars on Nostr with the full URL.
- **Note:** Say "marked down by the seller", not "price drop". We have only one snapshot, so we have not observed a drop ourselves.

### Post 2: In stock now

```
Bitaxe Gamma Duo (650) is in stock at Solo Satoshi for $111.69 (US power supply option). Bitcoin Merch lists it at $239.99. Checked Oct 16, 1:21 PM ET. Stock changes fast. https://bitaxeradar.com/models/bitaxe-gamma-duo/
```

- **Data used:** Bitaxe Gamma Duo (650). `solosatoshi:bitaxe-gamma-duo` (111.69, 9 of 9 variants in stock) and `bitcoinmerch:bitaxe-gamma-duo` (239.99).
- **Link:** https://bitaxeradar.com/models/bitaxe-gamma-duo/
- **Length:** 195 chars as X counts it (links count as 23); 220 chars on Nostr with the full URL.
- **Note:** This is "in stock now". It is not a true "back in stock" post because we have no history yet. See the template below for those.

### Post 3: Sold out, here's the next best

```
Bitaxe Gamma: the cheapest listing we track (Solo Satoshi, $67) is sold out right now. Cheapest one in stock is Bitcoin Merch at $119.99. Checked Oct 16, 1:21 PM ET. We track stock so you don't have to refresh tabs. https://bitaxeradar.com/models/bitaxe-gamma/
```

- **Data used:** Bitaxe Gamma. `solosatoshi:bitaxe-gamma` (67.00, out of stock, 0 of 9 variants) and `bitcoinmerch:bitaxe-gamma` (119.99, in stock).
- **Link:** https://bitaxeradar.com/models/bitaxe-gamma/
- **Length:** 239 chars as X counts it (links count as 23); 260 chars on Nostr with the full URL.

### Post 4: Cheapest per TH/s

```
Lowest cost per TH/s among in-stock US listings we track: NerdQaxe++ at Bitcoin Merch, $249.99 for a listed 4.8 TH/s (about $52 per TH/s). It draws about 80 W vs about 18 W for a Gamma. Checked Oct 16. https://bitaxeradar.com/models/nerdqaxe-pp/
```

- **Data used:** NerdQaxe++ at Bitcoin Merch: 249.99 / 4.8 TH/s (listed spec in `models`) = $52.1 per TH/s, the lowest of all in-stock USD offers. Compare-at 549.99 not used in the post. Power: 80 W listed.
- **Link:** https://bitaxeradar.com/models/nerdqaxe-pp/
- **Length:** 225 chars as X counts it (links count as 23); 245 chars on Nostr with the full URL.
- **Note:** Per-TH/s uses the nominal spec, which varies by revision and tuning (see `models.nerdqaxe-pp.note`).

### Post 5: Cost per TH/s, Bitaxe line

```
Cost per TH/s, in-stock US listings (listed specs): Gamma Duo $111.69 = about $69. GT 801 $174.99 = about $81. Gamma $119.99 = about $100. Real hashrate varies with tuning. Checked Oct 16. https://bitaxeradar.com/compare/bitaxe-gamma-vs-bitaxe-gt-801/
```

- **Data used:** In-stock USD offers: Gamma Duo 111.69 / 1.63 = $68.5; GT 801 174.99 / 2.15 = $81.4; Gamma 119.99 / 1.2 = $100.0.
- **Link:** https://bitaxeradar.com/compare/bitaxe-gamma-vs-bitaxe-gt-801/
- **Length:** 212 chars as X counts it (links count as 23); 251 chars on Nostr with the full URL.
- **Note:** Nostr has no URL shortening, so this one is about 250 chars with the full link.

### Post 6: Weekly recap (TEMPLATE)

```
Bitaxe Radar, week of {range}: {n} price changes across {m} listings. Biggest drop: {model} at {seller}, ${old} to ${new}. {k} listings back in stock, {j} sold out. Full list and alerts: https://bitaxeradar.com/deals/
```

- **Data used:** Fill from `data/history.json` once it has 7 days of data. Do not post before Oct 23. History currently has one snapshot (Oct 16, 12:33 UTC).
- **Link:** https://bitaxeradar.com/deals/
- **Length:** 210 chars as X counts it (links count as 23); 217 chars on Nostr with the full URL.
- **Note:** Skip any blank. If nothing changed, say "quiet week, no price changes".

### Post 7: Beginner tip: what's in the box

```
Beginner tip: before you buy a Bitaxe, check what's in the box. Some listings include the power supply, some don't, and plug type can vary by option. We show the variant we priced, but confirm on the seller's page. https://bitaxeradar.com/how-we-track/
```

- **Data used:** No price data. Factual hook: `bitcoinmerch:bitaxe-gt-801` config says power supply "not mentioned in title (unverified)", and Solo Satoshi/Power Mining list power-supply/plug variants.
- **Link:** https://bitaxeradar.com/how-we-track/
- **Length:** 238 chars as X counts it (links count as 23); 252 chars on Nostr with the full URL.

### Post 8: Beginner tip: expectations

```
Honest note for newcomers: solo mining with a Bitaxe is a lottery ticket, not an income stream. Most people buy one to learn, tinker and back the network. We just track prices and stock. Alerts if you want them: https://bitaxeradar.com/
```

- **Data used:** No price data. Honest framing from the traffic plan (solo mining is a lottery, not income).
- **Link:** https://bitaxeradar.com/
- **Length:** 235 chars as X counts it (links count as 23); 236 chars on Nostr with the full URL.

**Template for real events (use once history exists):**

- Price drop (only if drop >= 5% vs the previous run, in stock): `{model}: {seller} dropped from ${old} to ${new} (in stock). Checked {time} ET. {url}`
- Back in stock (only if it was out for >= 24 h): `Back in stock: {model} at {seller}, ${price}. Checked {time} ET. {url}`

---

## 2. Stacker News post

### Where to post (checked 2026-10-16)

- **Recommended: `~bitcoin_Mining`.** Description: "anything related to bitcoin mining", founded by @Bell_curve, post cost **33 sats**, comment 3 sats. It's active (several posts a day, some with 30+ comments, e.g. "Tracking Your Miners" and "Solo mining is a long shot"). The March 2026 territory dashboard says about 62% of sats spent there reach posters, and it had ~369 items from ~24 users that month. [stacker.news/~bitcoin_Mining, stacker.news/items/1465373, stacker.news/items/1485883]
- **Cross-post to `~bitcoin`** (30 sats, the biggest territory, 241k sats stacked in March) only if the first post gets some zaps. SN supports cross-posting between territories. Posting the same thing in several places at once tends to read as spam.
- `~bitcoin_beginners` (21 sats) fits only a beginner-style follow-up post.
- **Rules:** SN has no formal content rules. Its guidelines say the community signals value with sats, and that "referral links and repetitive content tend to be ignored". Territories currently follow the same rule set, enforced by zapping. Our ToS read from the traffic plan allows promoting your own commercial product, but not spam. [stacker.news/guide, stacker.news/items/339533] **I could not find a territory-specific rules page for ~bitcoin_Mining** (the /rules URL 404s), so the owner should check the territory header on the site before posting.
- **Tips:** link the original source (our site), include an honest disclosure (done below), reply to every comment, never post a referral/affiliate link directly, post once and don't repost. A small amount of sats is needed (33 to post). Account name should be the brand. Best time is unverified. Early US morning is a guess.

### Draft (about 270 words)

**Title:** Bitaxe Radar: a free price and stock tracker for Bitaxe/NerdQaxe solo miners

**Body:**

Bitaxe Radar is a free tracker for Bitaxe, NerdQaxe and similar open-source solo miners. I built it because buying one meant checking several shop pages by hand, and stock and prices change quickly.

What it does:

- Lists current prices and stock for 8 models across 4 sellers (Bitcoin Merch, Solo Satoshi, Power Mining, Bitaxe.de), about 20 listings in total.
- Leads with US prices and keeps the EU shops listed, converted to USD with the date shown.
- Shows a "last checked" time on every price. Prices refresh about every 6 hours straight from the seller pages.
- Has a page per model with cost per TH/s, listed wattage and a price history chart. The history is brand new, so the charts are thin at the moment.
- Optional price alerts: pick a model and a target price, confirm by email, and you get a message when a listing reaches it. No account, double opt-in, no selling your address.

Disclosure: the site earns money through affiliate links. If you buy through one of them, I may earn a commission at no extra cost to you. Affiliate status doesn't change how offers are sorted, and the site marks which links are affiliate links. I'm not affiliated with the Bitaxe project or any seller.

Limits: a few shops (MineShop, NerdQaxe Store and others) can't be read automatically yet, so they're missing. Per-TH/s numbers use each model's listed spec, and real hashrate varies with tuning. And solo mining is a lottery, not income.

Which sellers or models should I add next? What would make you trust a price tracker more?

https://bitaxeradar.com

*(Check before posting: the counts "8 models, 4 sellers, about 20 listings" are from the 2026-10-16 collection. Update if they changed.)*

---

## 3. Plan: automating the X post queue safely

**Principle:** the script only writes drafts. A human posts or approves each one for at least the first 2 weeks. Nothing posts automatically until the owner says so.

1. **Generate candidates after each collector run.** Add `scripts/make_post_queue.py` to the existing `collect-and-deploy` workflow. It reads `data/latest.json` and `data/history.json` and writes `data/post_queue.json` (or a markdown file under `docs/queue/`). No network calls, no secrets.
2. **Rules per candidate type** (all must pass or the candidate is dropped):
   - Price drop: >= 5% below the previous run's price, in stock, not stale, and the same offer hasn't been posted in 7 days.
   - Back in stock: was out of stock for >= 24 h, now in stock, price present.
   - Cheapest per TH/s and "sold out, next best": max once a week each.
   - Weekly recap: Sundays, only if there are >= 7 days of history.
   - Skip anything with `stale: true`, a non-empty `errors` list in `latest.json`, a collection older than 12 h, or a price changed by more than ~50% in one run (likely a scraper error).
   - Use only USD offers in posts, or label currency clearly. Never any predictions, profit talk or "buy now" urgency.
3. **Fixed templates only.** Text is filled from fixed templates with real values, and the script checks length (X counts a link as 23 chars) and that the link is bitaxeradar.com.
4. **Guardrails:** max 3 queued per day and a lifetime log (`data/posted.json`) to avoid duplicates. Candidates expire after 12 h (stale prices). Include the "checked at" time in every post.
5. **Approval flow (phase 1, weeks 1-2):** the agent shows the owner the day's candidates, and the owner taps yes or no. Approved posts are posted manually from the brand X account (or sent through the X connector only after an explicit OK on each one) and mirrored to Nostr by hand.
6. **Phase 2 (after ~2 clean weeks, owner opt-in):** semi-automatic. Only price-drop and back-in-stock posts from fixed templates are posted automatically, capped at about 3 a day. This needs the X API (cost and access tier **not verified**, check before relying on it). X's rules say accounts that post automatically should be labeled "Automated" and link to the responsible account, so turn that label on first. Education posts, the weekly recap and Stacker News posts stay human-approved.
7. **Kill switch:** a `POSTING_ENABLED=false` repo variable stops everything. The queue file still gets written.
8. **Measure:** add `?utm_source=x` style tags only if analytics is on. Review in Search Console and analytics whether any X post brings clicks before scaling.

**Account safety:** one brand account, no mass mentions, no trend hijacking, no duplicate text.
