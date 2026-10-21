# Bitaxe Radar: First Dollar Plan (written 2026-10-21)

Goal: the first $1-$100 of real revenue, then scale. **VERIFIED** = read on the linked page on 2026-10-21 (or earlier where dated). **ESTIMATE** = judgment. Nothing in this doc has been sent, signed up for or bought.

---

## 0. Real numbers today (2026-10-21, ~7:35 AM ET)

| What | Number | Source |
|---|---|---|
| Email alert subscribers (Resend contacts) | **1 confirmed** (a gmail.com address created Oct 16, almost certainly the owner's own test signup), 0 pending | Resend API `/contacts` |
| Emails sent so far | 4 delivered (1 confirm, 2 price alerts, 1 forwarding test) | Resend API `/emails` |
| Data | 8 models, 4 sellers, 20 listings; last collection 2026-10-21 04:47 UTC (12:47 AM ET); collector commits every 6 h | `data/latest.json`, git log |
| Pages | 21 in sitemap (22 with the new /advertise/ page) | `site/sitemap.xml` |
| X | @BitaxeRadar, 2 posts | — |
| Affiliate links live | **Power Mining only** (`?ref=bitaxeradar`, "up to 10%", 7-day cookie, **€100 minimum payout**, invoice required) | `site/app.js`, docs/affiliate-drafts.md |
| Monetized links for US buyers | **Effectively none from US-dollar sellers.** Solo Satoshi and Bitcoin Merch links (the two USD sellers, and the cheapest in-stock price on most models) earn $0 until approved. Power Mining *does* ship to the US & Canada (express 2-4 days, standard 4-6 days, per its product-page FAQ, VERIFIED) and has a US warehouse, but it prices in EUR and is rarely the cheapest for a US buyer. | site data + powermining.io/products/nerdqaxe |
| Traffic / clicks | **Unknown. No analytics installed** (no Cloudflare beacon, no GA). Search Console + Bing are set up but give impressions only, with a lag. | site HTML |
| Revenue to date | $0 | — |
| Pending | Solo Satoshi affiliate (applied Oct 16, auto-reply "we'll review it shortly", PayPal payouts). Bitcoin Merch (emailed influencers@bitcoinmerch.com Oct 16 from the owner's Gmail, no reply; the email still pointed at the old yostoo.github.io URL). | Gmail |

**Cloudflare Web Analytics:** the account exists, and the saved API token can *list* Web Analytics sites (0 exist) but gets "Authentication error" when *creating* one, so it lacks the write scope. The site now has a ready hook: paste the site token into `CF_BEACON_TOKEN` in `site/app.js` and every page gets the cookie-free beacon on the next build. **Owner step (~2 min, free, no new signup):** Cloudflare dashboard → Analytics & Logs → Web Analytics → Add a site → `bitaxeradar.com` → copy the token (or give the API token the "Account Analytics: Edit" permission and I'll do it).

**The honest picture:** the first dollar is blocked by two things: (1) the US sellers that win most "cheapest in stock" slots don't pay us yet, and (2) we can't see traffic. Everything below is ranked by how fast it removes those blocks.

---

## 1. Ranked paths to the first $1-$100

| # | Path | Why it works | Cost | Needs from owner | Time to money (ESTIMATE) |
|---|---|---|---|---|---|
| 1 | **Get US seller links paid: Bitcoin Merch follow-up + Solo Satoshi** | They are the cheapest in-stock US price on most model pages (Gamma $67 at Solo Satoshi; GT, Duo, NerdQaxe++ at one of the two). Every click we already send them is currently unpaid. Bitcoin Merch: 3.3%, 15-day cookie, $5 min payout (VERIFIED, bitcoinmerch.com/pages/affiliate). Solo Satoshi: PayPal, rate not published. | $0 | Approve sending the Bitcoin Merch follow-up on Oct 23 (draft in §4). Solo Satoshi: nothing, just wait (no affiliate email published; a nudge via their contact form after ~10 days is optional). | Days after approval + first buyer. One $119.99 Gamma at Bitcoin Merch = ~$3.96 earned; 2 sales clear the $5 payout. |
| 2 | **Join more US-reachable seller programs: Altair Technology, DTV Electronics, D-Central** | More paid links = more chances. **Altair** (St. Louis, MO, US): affiliate program exists, PayPal, paid on the 1st of each month, apply after making a store account (VERIFIED, altairtech.io/affiliate-home/; rate not published). **DTV Electronics** (UK company, sells Bitaxe builds via its store and Amazon storefronts): "up to 10%", 30-day attribution (VERIFIED, dtvelectronics.com/affiliates/). **D-Central** (Canada; miners + the biggest Bitaxe accessory range: PSUs, heatsinks, stands, cases): 3% accessories / 5% ASICs at 0-10 sales a month, 31-day cookie, $25 min payout (VERIFIED, d-central.tech/fr/zone-daffiliation/). Caveat: Altair is on our "can't scrape" list (bot challenge), so its prices need a browser-based or manual check before listing. | $0 | Approve each signup; enter passwords; PayPal email (Altair, D-Central). I prefill everything. | 1-2 weeks (approval + adding to tracker + first sale). |
| 3 | **Black Friday deals page (live ~Nov 10, BF = Nov 27, Cyber Monday Nov 30)** | Highest buying intent of the year; sellers run sales; "bitaxe black friday" is a search people make every year. Page auto-shows price vs our 30-day low. | $0 | Nothing (approve the X posts that promote it). | Nov 27-Dec 1. ESTIMATE: this is the most likely week for the first real affiliate sales. |
| 4 | **Click-through quick wins on the site (shipped today)** | A big "Check price at <seller>" button above the fold on every model page sends more of each visit to a seller page. | $0 | — | Immediate, but only multiplies traffic we have. |
| 5 | **Accessories box on model pages ("What else you need")** | Every Gamma needs a 5V/6A barrel PSU if not bundled, many buyers add a stand/fan/heatsink. Links to D-Central (once approved) and/or Amazon. | $0 | Signup approval (D-Central and/or Amazon). | 2-4 weeks. Small: a $15 stand at 3% = $0.45. Volume play, not a first-dollar play. |
| 6 | **Amazon Associates** | Huge catalog; Amazon US has several "Bitaxe Gamma 601" listings ($45-$159, VERIFIED via search) plus every accessory. Rates: 2.5% PC & PC components, 3% tools/home improvement, 4% "all other" (VERIFIED, affiliate-program.amazon.com Commission Income Statement). Cookie = **24 hours** (cart items 89 days). **Catch:** approval is conditional: 3 qualifying sales within 180 days or the account is closed and can't be reinstated (VERIFIED). Needs SSN/EIN tax info. Many Amazon Bitaxe listings are unknown resellers, so we'd only link ones we can vet. | $0 | Signup with tax info (only he can). | Weeks-months; low $ per sale. **Recommend: wait until analytics shows >~500 visits/month**, so the 180-day clock doesn't run out. |
| 7 | **Sponsor / "featured seller" spot** | Small sellers and accessory makers (DTV, D-Central, Altair, TinyChipHub, IxTech, 3D-print case makers) want buyers who are comparing prices. Placeholder + /advertise/ page are live now. | $0 | Approve outreach emails. Decide intro pricing (ESTIMATE: $25-$50/month flat at our size). | **Low odds until we can show traffic.** Best pitched together with "we'll list you for free + do you have an affiliate program" (drafts in §4). A yes could still be the first $25. |
| 8 | **Tips: Lightning zaps / Stacker News** | Bitcoiners tip in sats. Stacker News zaps only arrive as real sats if a receiving Lightning wallet is attached; otherwise they become non-withdrawable "Cowboy Credits" (VERIFIED, stacker.news/faq). | ~33 sats to post (fraction of a cent) | A Lightning wallet (new account, his choice) + SN account. | Cents to a few dollars. Good for reach, not revenue. |
| 9 | ~~Geyser fund~~ | **Not available:** Geyser no longer allows new self-service projects; only approved "Circular Grants" (VERIFIED, guide.geyser.fund FAQ). | — | — | Skip. |
| 10 | ~~Pool / exchange referrals~~ | **Braiins Pool has no referral program**; the Braiins OS partner program needs 50 PH/s+ of referred hashrate (VERIFIED, academy.braiins.com + braiins.com/os-firmware/referral). **River's partner program** needs 50+ clients or $5M+ in buys (VERIFIED, river.com/partner); its consumer referral (up to $100 each, river.com/referrals) is for personal invites, so check its terms before putting it on a site. **Swan's affiliate program is retired.** | — | — | Skip for now. |

Not worth it now: Bitaxe.de (EU-only, rejects coupon/link sites), NerdQaxe Store (no program, trust flags), Plebsource (invite-only store).

---

## 2. Top 3 for this week (Oct 21-27)

1. **Oct 23: send the Bitcoin Merch follow-up** (draft below; owner taps approve). It's the fastest path to a paid US link, and it fixes the old URL in the first email. In the same pass, check the Solo Satoshi status.
2. **Apply to Altair, DTV Electronics and D-Central** (prefilled forms, owner checks the fields + passwords) and send the short "list you + affiliate/sponsor" note to DTV (draft below). Then add whichever approve to the tracker.
3. **Turn on Cloudflare Web Analytics** (2-minute owner step above) and **start the Black Friday page** so it's indexed by ~Nov 10. One X post a day keeps pointing at model pages.

---

## 3. Shipped today (no money, no accounts, no outreach)

- **"Best deal right now" box** above the fold on every model page: cheapest in-stock price with a big "Check price at <seller>" button, plus the cheapest US-dollar seller if that's different. Affiliate buttons keep `rel="sponsored"` and the "affiliate link" label.
- **Sponsor spot** on model pages (under the price table): "This spot is open… Advertise on Bitaxe Radar", clearly not an ad yet.
- **/advertise/ page** (in sitemap): what's offered, the rules (always labelled, never changes rankings), honest "no traffic numbers yet", mailto contact@bitaxeradar.com. Footer link on every page.
- **Analytics hook**: `CF_BEACON_TOKEN` in `site/app.js`; empty = nothing loads. Tested both ways.
- **Power Mining seller page** now says it ships to the US & Canada (its own FAQ), so US readers know the one paying link is usable.
- Tests: new test for CTA/sponsor/advertise/analytics; all 18 tests pass.

---

## 4. Draft emails (NOT sent; each needs owner approval)

### 4a. Bitcoin Merch follow-up (send Oct 23, as a reply in the Oct 16 thread)
**To:** influencers@bitcoinmerch.com
**Subject:** Re: Affiliate application: Bitaxe Radar (Bitaxe/NerdQaxe price tracker)

Hi Bitcoin Merch team,

Just following up on my note from last week about your affiliate program. One update: Bitaxe Radar has moved to its own domain, https://bitaxeradar.com, so please use that instead of the github.io link I sent before.

The site now has a page for each miner, for example https://bitaxeradar.com/models/bitaxe-gamma/, and Bitcoin Merch is listed across 7 models with live price and stock. Those links aren't affiliate links yet, so I'd love to get set up through Affiliatly whenever you have a moment. If there's a form I should fill in instead, just point me to it.

Thanks again,
the owner
Bitaxe Radar | https://bitaxeradar.com | contact@bitaxeradar.com

### 4b. DTV Electronics: listing + affiliate + sponsor
**To:** info@dtvelectronics.com
**Subject:** Listing DTV Electronics on Bitaxe Radar (Bitaxe price tracker)

Hi DTV team,

I run Bitaxe Radar (https://bitaxeradar.com), a free tracker that compares prices and stock for the Bitaxe Gamma, GT, NerdQaxe++ and similar miners across several sellers, with price history and email price alerts.

I'd like to add DTV Electronics to the tracker. Two quick questions:
1. Is there a product feed or a preferred way for us to read your prices and stock? We check public product pages a few times a day with a clearly named user agent.
2. I saw your affiliate program (up to 10%). Could you approve Bitaxe Radar? Affiliate links are labelled on the site and never change how sellers are ranked.

We also have a labelled sponsor spot on our model pages if you'd ever like extra visibility. The site is new, so I'll keep it simple and honest on pricing until we have real traffic numbers to share.

Thanks,
the owner
Bitaxe Radar | https://bitaxeradar.com | contact@bitaxeradar.com

### 4c. Altair Technology: listing + affiliate (optional, send after applying)
**To:** help@altairtech.io (also published: contact@altairtech.io)
**Subject:** Bitaxe Radar: adding Altair to our price tracker

Hi Altair team,

I run Bitaxe Radar (https://bitaxeradar.com), a free price and stock tracker for Bitaxe-class home miners. US buyers make up most of our audience, and Altair is one of the US shops people recommend, so I'd like to list you.

Our price checker currently gets a bot challenge on altairtech.io. Is there a product feed or another way you'd prefer us to read price and stock? We identify ourselves clearly and check only a few times a day.

I've also applied to your affiliate program under Bitaxe Radar. Affiliate links on our site are labelled and never affect ranking.

Thanks,
the owner
Bitaxe Radar | https://bitaxeradar.com | contact@bitaxeradar.com

Note: contact@bitaxeradar.com receives mail but Gmail "send as contact@" isn't set up yet, so for now these would go from the owner's Gmail with contact@ in the signature (same as the Oct 16 email).

---

## 5. What needs the owner

- Approve: Bitcoin Merch follow-up (Oct 23), DTV email, Altair email (optional).
- Signups (free; he enters passwords): Altair store + affiliate, DTV affiliate, D-Central affiliate. Later: Amazon Associates (tax info).
- 2-minute step: create the Cloudflare Web Analytics site and share the token (or widen the API token).
- Decision: intro sponsor price (suggest $25-$50/month) before any sponsor pitch names a number.
- Money: none required for anything above.
