# Bitaxe Radar: Traffic Plan (written 2026-10-16)

Plain-language plan to get the first visitors and the first affiliate dollars.
Everything marked **VERIFIED** came from a page I read on 2026-10-16 (source in brackets). Everything marked **ESTIMATE** is my math or judgment. Anything I could not check is listed under "Could not verify".
Nothing here has been posted, emailed, or signed up for. Every outreach step below needs the owner's OK first.

---

## 0. Where we stand (VERIFIED by checking the live site and repo)

- https://bitaxeradar.com has **no robots.txt and no sitemap.xml** (both return 404) and **no structured data**.
- The site is one HTML page that fills in its tables with JavaScript from `data.js`. Google can render JS, but it is slower and less reliable. **Every model needs its own real, pre-built HTML page** (build_site.py can generate them).
- Data we already have: 8 models, 4 sellers (Bitcoin Merch, Solo Satoshi, Bitaxe.de, Power Mining), 20 offers, price history. Several sellers can't be scraped yet (MineShop, NerdQaxe Store, Plebsource, Altair, TinyChipHub), listed in `data/latest.json -> unscrapable`.
- Only 2 of the 4 sellers have affiliate programs we've actually looked into and not yet joined: Power Mining and Bitcoin Merch. **Until we're approved, clicks earn $0.** Joining is step 1 (owner approves the applications; drafts are in `docs/affiliate-drafts.md`).

### Who we're up against (VERIFIED, found by search)
| Competitor | What it does | Gap we can fill |
|---|---|---|
| bitaxe.org/buy | Official vendor list, no prices or stock | Prices, stock, history, alerts |
| cryptocodes.eu | Dated EU articles comparing 3 shops with discount codes (e.g. 14 Oct 2026) | US-first, always-fresh, more shops |
| hagglezon.com | Compares Amazon EU prices only | US + non-Amazon sellers |
| pricehistory.app | Amazon price history for some Gamma listings | Seller-direct prices, stock history |
| Mining Now / MinerCompare | Aggregators (we noted these in our own research notes) | Focus on small solo miners |

Takeaway: nobody I found does **US prices + stock history + price-drop alerts** for Bitaxe-class miners. That is our angle. I did not measure their traffic.

---

## 1. SEO (slow, but the main long-term engine)

### 1a. Search demand: what I could and couldn't verify
- **Could NOT verify real search volumes.** Google Trends only gives relative 0-100 numbers, and free volume tools weren't reachable. I will not invent numbers.
- What *is* verified: Bitaxe has a big community (OpenSats page says 100,000+ units estimated sold, [opensats.org/projects/bitaxe]); there are active price/stock articles from competitors (cryptocodes.eu), and Amazon listings with many sellers (hagglezon). That's evidence the buying question exists, not how big it is.
- Once Google Search Console is set up (step in 1c), **real impression data will replace guesses within ~2-4 weeks of pages being indexed.** Use that to decide which pages to expand.

### 1b. Target keywords (intent guesses, ranked by how close the searcher is to buying)
Highest intent (build first):
1. `bitaxe gamma price` / `bitaxe gamma for sale` / `buy bitaxe gamma`
2. `where to buy bitaxe` / `bitaxe in stock` / `bitaxe usa`
3. `nerdqaxe++ price` / `nerdqaxe++ in stock` / `where to buy nerdqaxe`
4. `bitaxe gt 801 price`, `bitaxe gamma duo price`, `nerdaxe gamma price`, `nerdaxe gaia price`
5. `bitaxe gamma vs nerdqaxe++`, `bitaxe gamma vs gt`, `bitaxe gamma vs supra`
6. `best bitaxe`, `best bitaxe deals`, `bitaxe black friday`
Medium intent (later, only if they bring impressions): `bitaxe electricity cost`, `is a bitaxe worth it`, `bitaxe profitability`.

Black Friday is **Nov 27, 2026** (day after US Thanksgiving, Nov 26). The first-30-days window ends Nov 15, so **a "Bitaxe Black Friday deals" page should be live and indexed before then.** ESTIMATE: Google needs days to weeks to index a brand-new site.

### 1c. Pages to build from our data (static HTML via build_site.py)
Rule: each page must carry something a visitor can't get by just visiting a seller. Google says it penalizes pages made "primarily for the purpose of manipulating search rankings" and "thin affiliation" with copied merchant text, and says good affiliate pages offer "additional information about price, original product reviews... product comparisons" [developers.google.com/search/docs/essentials/spam-policies]. So no keyword-swapped clones.

| Page | URL | Unique data on it |
|---|---|---|
| 1 page per model (8) | `/models/bitaxe-gamma/` etc. | Current price by seller, in-stock flag, last-checked time, price history chart, lowest/highest price we've seen, "days in stock" once we have history, cost per TH/s, J/TH, yearly electricity cost, lottery odds blurb (solo mining honesty), "alert me" form |
| Where to buy (US) | `/where-to-buy-bitaxe/` | Seller table with shipping/returns/warranty notes we verify by hand |
| Best deals / in stock now | `/deals/` and `/in-stock/` | Auto-sorted live from data; "price drop in last 7 days" list |
| Black Friday | `/bitaxe-black-friday/` | Price vs 30-day low, updates through the sale |
| Comparisons (start with 5) | `/compare/bitaxe-gamma-vs-nerdqaxe-pp/`, `gamma-vs-gt-801`, `gamma-vs-nerdaxe-gamma`, `gamma-vs-supra`, `nerdqaxe-pp-vs-nerdaxe-gaia` | Side-by-side specs, $/TH, J/TH, who it's for, current best price each |
| Sellers (4) | `/sellers/solo-satoshi/` etc. | What we know: shipping region, returns, how often they stock out (from our history) |
| Methodology | `/how-we-track/` | How prices are collected, disclosure of affiliate links (trust + required) |

Total: about 8 + 5 + 4 + 4 = **~21 pages.** Do not mass-produce more than this until Search Console shows impressions. Mark old/discontinued models (Ultra, Supra) `noindex` unless their pages have real content.

### 1d. Technical SEO checklist (agent can do all of this)
- [ ] `robots.txt` + `sitemap.xml` (regenerated each collector run, with `lastmod`).
- [ ] Pre-render all page content into the HTML (not only via JS).
- [ ] Unique `<title>` and meta description per page, e.g. `Bitaxe Gamma price: $67-$156 across 4 US/EU sellers (updated Oct 16)`. Numbers update on each build.
- [ ] `<link rel="canonical">` to the bitaxeradar.com URL.
- [ ] JSON-LD: `Product` with `AggregateOffer` (lowPrice, highPrice, offerCount) per model, `BreadcrumbList`, `Organization`. Whether Google shows rich results for aggregator pages is **unverified**; it still helps Google understand the page.
- [ ] Affiliate links must carry `rel="sponsored nofollow"` (Google's guidance for paid/affiliate links, same spam-policies page).
- [ ] Internal links: home -> model pages -> comparison pages -> seller pages, plus a "related models" block on every page.
- [ ] Show "Last checked: <time>" on every price (also builds trust).
- [ ] Don't use the Bitaxe logo; bitaxe.org says the name and logo are trademarked [bitaxe.org/buy footer]. Plain-text model names are normal usage, but keep the "unofficial" note in the footer.
- [ ] **Google Search Console**: add a *Domain* property and verify with a DNS TXT record at Porkbun (agent adds the record). Owner needs to sign in to Google once and approve. Submit the sitemap.
- [ ] **Bing Webmaster Tools**: import the site from Search Console (one click) and submit the sitemap. Optional: IndexNow ping on each deploy so Bing sees updates fast.
- [ ] Privacy-friendly analytics (e.g. Cloudflare Web Analytics, free, already have a Cloudflare account) so we can see visits without cookies. Needs owner OK to enable.

### 1e. Realistic SEO timing (ESTIMATE)
New domain, no links: first impressions in ~1-3 weeks, meaningful rankings usually take 3-6+ months. I can't verify a specific number for this niche.

---

## 2. Communities (where buyers are) and their rules

Rule for all of them: **we are a helpful member first, a link second.** The owner's real name stays off everything; use the Bitaxe Radar brand account. Disclose that it's our site and that we earn affiliate commissions whenever asked. Never fake reviews, never use multiple accounts.

| Place | What I verified (source) | What we do | Risk |
|---|---|---|---|
| **r/BitAxe** (Reddit) | Mods remove "referral links, invite codes, 'DM me for the link'", profit/ROI screenshots, "what should I mine?", marketing hype. Weekly Help & Experiments thread. Selling isn't banned but "we'd rather not have dozens of sales posts" [reddit.com/r/BitAxe start-here post; weekly-format post; "Is selling allowed" thread]. Subscriber count: **not verified** | Answer "where can I find X in stock?" questions in comments when genuinely useful, with plain info (no affiliate link). Don't link the site in posts at first. Put the site in the profile. Ask mods by modmail before ever posting a link | **High** if we drop affiliate links: the rules explicitly target them. Treat this sub as reputation-building only |
| **r/BitcoinMining** | "Promotion allowed only with moderator permission or designated threads"; referral links and URL shorteners banned; sales/ads need specific criteria and a "verified commercial vendor" tag [reddit.com/r/BitcoinMining rules posts + threadotter.com summary (a third-party summary, not the sub itself)] | Contribute answers; no site links. Optionally modmail to ask if a free price tracker may be shared in a megathread | High |
| **OSMU Discord** (Open Source Miners United) | The Discord exists (discord.gg/osmu, linked from bitaxe.org/osmu.wiki). **I could not read its server rules** | Join as owner (he must do it), read #rules, lurk. Offer the tracker only where self-promo is allowed. Also possible: ask the OSMU wiki/vendor-list maintainers whether a neutral price tracker can be linked (unverified that they'd say yes) | Unknown |
| **Telegram** | "BITAXE GERMAN" t.me/BitaxeMinerGerman, ~524 members [telekit.link, third-party]; bitaxe.de runs Telegram support @bitaxede. German-language, so it matters mainly if we lean into EU. Rules not verified | Low priority for a US-first site | Unknown |
| **Stacker News** | Terms say "reasonable commercial use... to advertise your own commercial products" isn't spam, but unwanted promo/spam and tagging random users is prohibited. Posting costs a small amount of sats. Territories set their own rules; there's no dedicated mining territory I could confirm [stacker.news ToS item 338393; FAQ] | Write 1-2 real educational posts in ~bitcoin (e.g. "What a Bitaxe actually earns solo: the lottery math"), link the tool as a resource. Owner or I fund a few thousand sats; owner approves | Low-medium. Bitcoiner audience is a very good fit |
| **X** | X allows automation but fully autonomous accounts should use the "Automated" label and link to the responsible account; avoid duplicate posts, mass mentions, trend hijacking; human-approved scheduled posts are fine [beereach.io summary + X rules mirror (secondary sources)]. API pricing/cost: **not verified** | See section 3 | Low if labeled and not spammy |
| **Nostr** | Open protocol, no central moderation. Other sellers' affiliate promos do circulate there (search results show them). No rules to check, but audience size for us is unverified | Mirror the daily posts (cheap). Use a brand key | Low |
| **YouTube comments** | Not a channel to spam | Don't | n/a |

### Honest expectations for communities
Mods in this niche are actively fighting scam and affiliate spam. Getting banned from r/BitAxe would hurt more than it helps. A realistic win is: be useful for 2-4 weeks, then occasionally answer "is X in stock?" with the tracker when asked and allowed.

---

## 3. X / Nostr content we can automate from our data

Pipeline: after each 6-hour collector run, a script writes candidate posts into a review queue file; the owner (or agent with owner approval) posts them. **First 2 weeks: human-approved only.** After that, if the owner wants fully automatic, label the account "Automated" per X's rules.

Post ideas (all derived from data we already have):
1. **Price drop:** "Bitaxe Gamma just dropped to $119.99 at Bitcoin Merch (was $139.99). In stock. Last checked 2:15 PM ET. bitaxeradar.com/models/bitaxe-gamma" (only when drop >= 5%).
2. **Back in stock:** "Back in stock: Bitaxe Gamma Duo at Solo Satoshi, $111.69." (only for models that were out for >24 h)
3. **Daily lowest price board:** one image or text list of cheapest in-stock price per model.
4. **Weekly recap (Sunday):** biggest drops, longest stockouts, price low of the week.
5. **Out-of-stock alert:** "Cheapest Gamma ($67 at Solo Satoshi) is sold out. Next cheapest in stock: $119.99." (This is the kind of info people actually search for.)
6. **Education thread (hand-written, 1/week):** solo-mining lottery odds, power cost, "should a beginner buy one?" with honest "this is a lottery ticket, not income" framing.
Rules for the bot: include "affiliate links" disclosure in the profile bio, never claim profit, post max ~3/day, skip when data is stale or in doubt.

---

## 4. Partnerships and what to offer

Our offer is **data, not money** (we have no audience to sell). Nothing below should be sent without owner approval.

| Who | Evidence | What to offer | Ask |
|---|---|---|---|
| **Sellers** (Solo Satoshi, Bitcoin Merch, Power Mining, Bitaxe.de) | Solo Satoshi has an affiliate form, PayPal payouts, 14-day delay; **rate not published** [solosatoshi.com/affiliate-registration]. Power Mining "up to 10%", 7-day cookie, EUR100 min payout, invoice required. Bitcoin Merch 3.3%, 15-day cookie, $5 min. Bitaxe.de 5%, but EU/CH/NO/IS/LI only and "no coupon sites" [docs/affiliate-drafts.md] | A neutral traffic source with correct stock info; free fix-alerts if their feed breaks | Affiliate approval, discount code for our visitors (sellers do this for other creators), maybe a feed/API so scraping isn't needed |
| **YouTubers** | Bitaxe-related sponsorships tracked by SponsorRadar: Red Panda Mining (~294K subs), Your Friend Andy (~151K, uses a Solo Satoshi affiliate link), plus Blocktrainer and others [sponsorradar.com/brands/bitaxe]. Other reviewers seen in search: Tech Hustler, Sterling, VoskCoin. **Their contact emails/rates: not verified** | Free, always-current "where to buy" link they can put in descriptions; a data page for their video's model; correction alerts when a deal they featured sells out | A link in the description. **Big channels won't care about a zero-traffic site; aim at smaller creators (1K-50K subs) first.** |
| **Newsletters / blogs** | Bitcoin Fortress (Substack) has a Bitaxe home-mining piece [bitcoinfortress.substack.com]. Other dedicated mining newsletters: **I couldn't find any I could verify** | A weekly "mining hardware price moves" box they can copy with credit | A mention or link |
| **OSMU / bitaxe.org** | Official vendor list exists with ~25 vendors [bitaxe.org/buy] | Offer to include vendor-list-only sellers so we're consistent with the official list | Link from a community resources page (long shot) |

Do **not** buy links, send free products for links, or trade link swaps for ranking (that's listed as link spam in Google's policy).

---

## 5. First 30 days (Oct 16 - Nov 15), ranked by payoff vs effort

Payoff/effort scale is my judgment (ESTIMATE).

| # | Task | Who | Effort | Payoff |
|---|---|---|---|---|
| 1 | Add robots.txt, sitemap, canonical, titles/meta, rel=sponsored | Agent | Low | High (unlocks everything) |
| 2 | Pre-render 8 model pages + where-to-buy + deals + in-stock | Agent | Med | **Highest** |
| 3 | Join Power Mining + Bitcoin Merch affiliate programs (Solo Satoshi too) and swap links in (clicks earn nothing before this) | Agent drafts/fills; **owner approves each application** and does passwords/final submit | Low | **Highest** (no approval = $0) |
| 4 | Set up Google Search Console + Bing Webmaster, submit sitemap | Agent adds DNS record; **owner signs into Google once** | Low | High |
| 5 | Comparison pages (5) + seller pages (4) + methodology page | Agent | Med | Med-High |
| 6 | Black Friday deals page live by ~Nov 10 | Agent | Low | Med-High (seasonal) |
| 7 | Create brand X account + Nostr key; build the post-queue script; post approved items | Agent builds; **owner approves account creation and the first posts** | Med | Med |
| 8 | Free analytics (Cloudflare Web Analytics) | Agent; **owner OK** | Low | Med (needed to measure) |
| 9 | Join OSMU Discord and Reddit (brand/new account), lurk + read rules; answer real questions for 2+ weeks | **Owner** (or owner OKs agent doing it) | Med, ongoing | Med (slow, risky if done wrong) |
| 10 | 1-2 Stacker News posts (lottery math / "where to find a Bitaxe in stock") | Agent drafts; **owner approves, funds sats** | Low-Med | Med |
| 11 | Outreach to 5-10 small YouTubers/newsletters (after site has 10+ pages and some data) | Agent drafts; **owner approves each send** | Med | Low-Med now, higher later |
| 12 | Fix unscrapable sellers (MineShop, NerdQaxe Store, etc.) so the tracker covers more of the market | Agent | Med-High | Med (more US coverage = better pages) |
| 13 | Weekly check: Search Console queries, clicks to sellers, signups; adjust | Agent reports; owner reads a 5-line summary | Low | High (learning) |

Suggested order by week: **Week 1:** #1, #3, #4, #8, start #2. **Week 2:** finish #2, #5, #7. **Week 3:** #6, #10, begin #9 participation. **Week 4:** #11, #12, review numbers and decide what to double down on.

---

## 6. Realistic numbers (ESTIMATES, with the math)

Formula: `monthly revenue = visitors x outbound-click rate x purchase conversion x average order x commission`.

Inputs:
- **Commission (VERIFIED where stated):** Power Mining up to 10% (starting tier unknown); Bitcoin Merch 3.3%; Bitaxe.de 5% (likely not available to us); Solo Satoshi unknown; Amazon Associates US: PC/PC components 2.5% standard [affiliate-program.amazon.com help]. I use a **blended 4% (low), 6% (mid), 8% (high).**
- **Conversion of affiliate clicks to purchases:** e-commerce typical 1-3%, hardware/electronics 1.2-2.8% [shopify.com blog; xark.io benchmarks, both generic benchmarks, not Bitaxe-specific]. I use **1.2% / 2% / 2.8%.**
- **Outbound click rate (visitors who click to a seller):** no source; my guess for a high-intent price page is **15% / 25% / 30%.** Treat this as the least reliable number.
- **Average order:** our current prices run ~$67-$410; most buyers will pick a Gamma-class unit (~$120-$160). I use **$130 / $150 / $170.**
- Also note the cookie windows (7 days Power Mining, 15 days Bitcoin Merch) and payout delays (14-30+ days, EUR100 minimum at Power Mining), so the first payment arrives well after the first sale.

| Scenario | Click | Conv | AOV | Comm | $ per visitor | $ per 1,000 visitors | Visitors/mo needed for $200 |
|---|---|---|---|---|---|---|---|
| Low | 15% | 1.2% | $130 | 4% | $0.0094 | ~$9 | ~21,000 |
| Mid | 25% | 2.0% | $150 | 6% | $0.045 | ~$45 | ~4,400 |
| High | 30% | 2.8% | $170 | 8% | $0.114 | ~$114 | ~1,750 |

What that means:
- **Month 1 (ESTIMATE):** maybe 50-500 visitors, mostly from social/community posts. At the mid case that's **$2-$23.** Realistically close to $0-$20, and payouts won't arrive in month 1.
- **Months 3-6 (ESTIMATE, if SEO works):** 1,000-3,000 visitors -> **$45-$135 at mid.**
- **$200/month** needs roughly **~4,400 visitors/month at the mid case** (range 1,750-21,000). I'd call that a **realistic month 6-12 target, not a month 1 one,** and it's a guess because I couldn't verify search demand.
- Price-drop email list helps by bringing back people at the exact moment they're ready to buy; it likely raises conversion, but I have no data. Track it.
- Risks that cut these numbers: sellers not approving us; stockouts at affiliate sellers (e.g. Power Mining Gamma is currently out of stock in our data); the market for solo miners shrinking; Google ranking us slowly.

---

## 7. Could not verify (so you know the gaps)
- Actual monthly search volume for any keyword.
- Subscriber counts for r/BitAxe and r/BitcoinMining; the OSMU Discord rules; Telegram group rules.
- Solo Satoshi's commission percentage; Power Mining's starting tier rate.
- X API cost for posting; whether Cloudflare Web Analytics or other free analytics suits us (didn't test).
- Contact details and rates for YouTubers; existence of dedicated mining newsletters beyond Bitcoin Fortress.
- Competitors' traffic.
- Whether Google shows rich results for aggregator product pages.

## Sources used (accessed 2026-10-16)
- r/BitAxe rules: reddit.com/r/BitAxe/comments/1qusz27 , /1qutl7a , /1s58yjr
- r/BitcoinMining: reddit.com/r/BitcoinMining/comments/1n6nidm , /1h0x5fo , /lq541i , /1r0e3ko ; threadotter.com/subreddit-rules/bitcoinmining
- Stacker News ToS stacker.news/items/338393 ; FAQ stacker.news/faq
- Google spam policies developers.google.com/search/docs/essentials/spam-policies
- bitaxe.org/buy ; osmu.wiki ; opensats.org/projects/bitaxe
- cryptocodes.eu/news/bitaxe-price-three-shops-14-october-2026 ; hagglezon.com/en/s/Bitaxe ; pricehistory.app
- sponsorradar.com/brands/bitaxe ; bitaxe.de/en/bitaxe-partnerprogramm ; solosatoshi.com/affiliate-registration ; powermining.io/pages/affiliate
- Amazon Associates fee table affiliate-program.amazon.com/help ; shopify.com/blog/affiliate-marketing-conversion-rates ; xark.io affiliate benchmarks
- X automation: beereach.io/blog/x-twitter-automation-rules-in-2026-post-pace-and-label-safely ; twitterapi.io/blog/twitter-bots
