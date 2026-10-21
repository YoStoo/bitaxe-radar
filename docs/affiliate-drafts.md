# Bitaxe Radar: affiliate application drafts

Status: DRAFTS ONLY. Nothing has been sent or submitted. Researched 2026-10-16.
Site: https://yostoo.github.io/bitaxe-radar/ (free price/stock tracker, 4 sellers, just launched, no audience yet)

Before applying: add a short affiliate disclosure to the site (e.g. footer + near buy buttons: "Some links are affiliate links. We may earn a commission at no extra cost to you."). Bitaxe.de explicitly requires labelling; the FTC expects it in the US.

---

## 1. Bitcoin Merch  -> EMAIL (no web form needed)

- Apply page: https://bitcoinmerch.com/pages/affiliate -> "Ready to start? Email us - influencers@bitcoinmerch.com"
- Terms (stated on that page): "3.3% commission rate", "15-day cookie duration", "$5 minimum payout". Tracking via Affiliatly.com. Payout method/schedule: not stated.
- Rules: no disclosure/comparison-site/scraper rules stated on the affiliate page. agents.md (https://bitcoinmerch.com/agents.md) is about AI shopping agents: "Agents must identify their requests as agent-initiated. Server-to-server requests and hosted or remote browsers must use Web Bot Auth"; back off on 429 and respect Retry-After; reading public HTML pages is allowed "provided your requests follow the agent-identification guidance". robots.txt disallows /cart.js and /recommendations/products. (Our price checker should send an identifying User-Agent and respect these.)

**To:** influencers@bitcoinmerch.com
**Subject:** Affiliate application: Bitaxe Radar (Bitaxe/NerdQaxe price tracker)

Hi Bitcoin Merch team,

I run Bitaxe Radar (https://yostoo.github.io/bitaxe-radar/), a free site that tracks prices and stock for small home Bitcoin miners like the Bitaxe and NerdQaxe across a few sellers, including you. It also has a price history chart and a running-cost calculator.

I'd like to join your affiliate program. I'll be upfront: the site just launched, so I don't have traffic numbers or an audience to show yet. I'm building it for people who ask "where can I buy a Bitaxe right now, and who has it in stock?", and I'm a Bitcoin enthusiast who wants to send them to sellers they can trust. Affiliate links would be clearly disclosed on the site.

Two quick things I wanted you to know: my site checks your public product pages a few times a day to read price and stock, and I'm happy to identify that traffic however you prefer (it uses a named user agent and respects your robots.txt). If you'd rather I use a different method, just tell me.

Could you send me the affiliate sign-up link (or approve me through Affiliatly) and any rules for price-comparison sites I should follow?

Thanks,
the owner
Bitaxe Radar | https://yostoo.github.io/bitaxe-radar/

---

## 2. Bitaxe.de  -> WEB FORM (browser), and probably NOT a fit

- Apply page: https://bitaxe.de/en/affiliate (German: https://bitaxe.de/affiliate). Form fields per their guide: name, email, password, country, link to channel/community/blog, a few sentences on audience and plans; accept program rules + privacy policy; then confirm email within 48 hours. Reviewed by hand "usually within a few days".
- Terms (quote): "5 % commission on net order value", "30 days attribution after the click" (only if the visitor accepts cookies; otherwise current visit only; last click wins), "€50.00 minimum payout". Goods value after discount, excluding shipping, PayPal surcharge, VAT. Held until 30 days after delivery; monthly payouts in the first week, by SEPA or Bitcoin. Optional 5% community discount code. Source: https://bitaxe.de/en/bitaxe-partnerprogramm
- Rules (quote): "Referral links are advertising. Label them as required for your platform and your country." No paid ads on brand/product names; no spam/hidden redirects/coupon sites; no self-purchases. Refunds reverse commission.
- **Eligibility problems:**
  1. Countries: "You can join from every country we deliver to: the EU plus Switzerland, Norway, Iceland and Liechtenstein." The US is not listed, and the owner is in the US.
  2. Audience: "It is not meant for coupon sites, for ads on our brand names..." and "Anyone who just wants to post a link, without content or a community behind it, gets a friendly no." A brand-new price tracker with no audience will likely be declined.
- Bot policy: robots.txt welcomes crawlers (only /admin is disallowed); no scraper rules. Contact: info@bitaxe.de (Nanohash OÜ, Tallinn), plus a Telegram chat mentioned on the site.
- Recommendation: don't submit the form with a false country. Either skip for now, or send a short email first (below) asking whether non-EU/price-comparison sites are accepted. Revisit once the site has real traffic or an X/Reddit presence.

**To:** info@bitaxe.de
**Subject:** Question about your affiliate program (Bitaxe Radar, US-based)

Hi,

I run Bitaxe Radar (https://yostoo.github.io/bitaxe-radar/), a free price and stock tracker for Bitaxe and NerdQaxe miners that lists Bitaxe.de alongside a few other sellers. It just launched, so I have no audience numbers yet.

I read your affiliate program page and saw it's open to the EU plus CH/NO/IS/LI, and that you don't want coupon sites. I'm based in the US and the site is a price-comparison tracker, so I'm probably outside what you had in mind. Before applying, I wanted to ask if there's any way for a site like mine to take part (for example, with a US address, or once the site has built an audience). If not, no worries at all.

Also, my tracker reads your public product pages a few times a day for price and stock. Please tell me if you'd like that done differently.

Thanks for your time,
the owner
Bitaxe Radar | https://yostoo.github.io/bitaxe-radar/

(If the form is used anyway, "channel/community" field = site URL; "audience and plans" text: "Bitaxe Radar is a free, newly launched price and stock tracker for home Bitcoin miners. No audience yet. I plan to share it in solo-mining communities and link to Bitaxe.de with clear affiliate disclosure. I'm US-based.")

---

## 3. Power Mining (powermining.io)  -> WEB FORM (GoAffPro; needs browser), plus optional email

- Apply page: https://powermining.io/pages/affiliate (same at https://shop.powermining.io/pages/affiliate). Step 1 is "Create Account: Join our Affiliate Program in under 2 minutes. Get your referral link instantly after signup." Registration is hosted on GoAffPro; a search result gave the sign-up URL https://c5010df4-31f1-404b-be1a-44db81090603.goaffpro.com/create-account (JavaScript app, could not read its fields; verify the link from the Power Mining page button in the browser). Support: support@powermining.io.
- Terms (quote): "Earn up to 10% commission" / "Up to 10% per sale" (exact tier/rate for a new affiliate: not stated). "We use a 7-day tracking cookie." Sales also tracked via unique discount code.
- Payouts (quote): "Commissions are paid on a Net 15 basis (15 days after the end of the month in which the sale was made)." "The minimum payout amount is €100." "Commissions are not paid automatically": you send an invoice ("affiliate payout") to the partner manager, Rolands, rolands@powermining.io, addressed to Power Mining SIA (Latvia, VAT LV40203109378). Invoice requirement is a small hassle for a US individual; ask how they handle that.
- Rules: no disclosure, comparison-site or scraper rules stated on the page. GoAffPro's affiliate operating agreement (https://goaffpro.com/terms) applies: complete and accurate application, must identify your site, and they "may reject your application in our sole discretion including if we determine that your site is unsuitable". robots.txt (https://powermining.io/robots.txt) allows /products/ and disallows /cart, /checkout, /account, /orders, /admin; nothing about bots.
- Perks: "Stocked in US & EU warehouses", free review units "for qualifying partners" (requests based on audience relevance; not requested in the draft below since the site is new). Affiliate manager: rolands@powermining.io.
- Best fit of the three: accepts sign-up directly, ships to the US.

**Web form text** (use in any "website / how will you promote" field):

Bitaxe Radar (https://yostoo.github.io/bitaxe-radar/) is a free price and stock tracker for home Bitcoin miners like the Bitaxe Gamma and NerdQaxe++, comparing a few sellers including Power Mining, with price history and a running-cost calculator. It just launched, so I don't have traffic numbers yet. I'll link to Power Mining with clear affiliate disclosure, and I'm building it for people deciding where to buy.

**Optional follow-up email (send after the sign-up, once approved or if no response)**
**To:** rolands@powermining.io
**Subject:** New affiliate: Bitaxe Radar (price tracker)

Hi Rolands,

I just signed up for your affiliate program for Bitaxe Radar (https://yostoo.github.io/bitaxe-radar/), a free price and stock tracker for Bitaxe and NerdQaxe miners that includes Power Mining. The site just launched, so I don't have traffic numbers yet, and I'm not asking for a review unit. I'll be honest about that and let results speak.

A couple of questions: (1) what commission rate would I start at, and what do the higher tiers require? (2) I'm in the US, so how should I handle the invoice for payouts? Also, my tracker reads your public product pages a few times a day for price and stock. Let me know if you'd like it done differently.

Thanks,
the owner
Bitaxe Radar | https://yostoo.github.io/bitaxe-radar/


---

# Addendum (2026-10-16, web research only; nothing submitted or sent)

Site: https://bitaxeradar.com | Brand: Bitaxe Radar | Contact: contact@bitaxeradar.com (use these in anything public; no owner real name in public things)

## 4. Solo Satoshi (solosatoshi.com, US) -> WEB FORM, open program, apply first

- **Program exists.** Apply page: https://www.solosatoshi.com/affiliate-registration/ (WordPress + SliceWP plugin, self-serve; account is created on submit).
- **Commission rate: NOT STATED anywhere public.** Page, ToS (https://www.solosatoshi.com/terms-of-service-and-sale-agreement/, section 10) and search results give no percentage. Ask by email or see it in the dashboard after signup. Do not quote a number.
- **Cookie: 30 days, first-click credit** (read from the page's live SliceWP config: `cookie_duration":30,"affiliate_credit":"first","affiliate_keyword":"aff"`). Link format: https://www.solosatoshi.com/aff/<ID>/ (seen in public affiliate posts, e.g. /aff/1096/). Affiliate links reportedly also give shoppers a 5% discount on the Bitaxe Gamma (affiliate's own tweet, https://damus.io/nevent1qqstp098fx5080xa77080ddd5r2h7jqqy0jn7aq52qmq0z8du6fxxhclw4mva; not from Solo Satoshi). Unverified as a standing program feature.
- **Payout:** PayPal only, to the "Payment Email" given at signup; paid on the last day of each month; 14-day hold for warranties/replacements/cancellations. Minimum payout: not stated.
- **Approval:** Page says "reserves the right to reject applicants we deem unfit". Solo Satoshi's own post (2025-06-02, https://njump.me/nevent1qqsqf7edz5lvzamp4yur640t5rl462xq59n5wf6y2nyrdkk6n6sm07cpqqq2dr57) says "All applications are approved once received" and that they paid over $1,000 to affiliates the previous month. So likely near-automatic. No audience or traffic requirement stated.
- **Form fields (all from the page HTML), 9 visible + terms box:**
  1. Username *
  2. First Name *
  3. Last Name *
  4. Email *
  5. Password * and Password Confirmation * (only the owner types these)
  6. Payment Email * (must be a PayPal email; **needs the owner's PayPal address; I did not check whether he has PayPal**)
  7. Website * (https://bitaxeradar.com)
  8. How will you promote us? * (free text)
  9. Checkbox: accept the terms (14-day delay, PayPal, right to reject/ban, "act in Solo Satoshi's best interest")
  Hidden: honeypot + token. Page mentions reCAPTCHA scripts; could not confirm whether a captcha shows on this form.
- **Public-facing name issue:** First/Last Name are required but are not shown publicly. Username is probably only a login; pick a brand one like `bitaxeradar`. Use contact@bitaxeradar.com as Email if he wants to keep his Gmail out of it (then verification/login mail goes to contact@, which forwards to his Gmail).
- Bot rules: robots.txt (https://www.solosatoshi.com/robots.txt) only blocks add-to-cart URLs, /wp-admin/ and log folders. Nothing stated about price-comparison sites or scraping. No ToS clause restricts comparison sites, but ToS section 10 says affiliate relationships must be disclosed (FTC).
- Support contact: not captured. Look up in the footer/contact page before emailing. I did not find an affiliate-specific email.

**Suggested "How will you promote us?" text (no real name):**

Bitaxe Radar (https://bitaxeradar.com) is a free price and stock tracker for home Bitcoin miners like the Bitaxe Gamma, GT and NerdQaxe, with price history, price-drop email alerts and a running-cost calculator. Solo Satoshi is one of the US sellers we list. We send people to the product pages with clear affiliate disclosure. The site is new, so there is no traffic to report yet. We'll promote it through SEO pages for each miner model, price-drop alerts, and posts in solo-mining communities, without spam.

Suggested signup values: Username `bitaxeradar`; Email contact@bitaxeradar.com; Website https://bitaxeradar.com; Payment Email = owner's PayPal email (ask him; this is only used for payouts).

## 5. Other sellers: checked for affiliate programs

In /workspace/bitaxe-radar/data/latest.json the only sellers are Bitcoin Merch, Solo Satoshi, Bitaxe.de and Power Mining, all now covered (sections 1-4). Sellers in its `unscrapable` list, checked for affiliate programs:

### Altair Technology (altairtech.io, St. Louis MO, US) -> WEB FORM (SliceWP, needs a store account first)
- **Program exists.** Info: https://altairtech.io/affiliate-home/. Apply: https://altairtech.io/affiliate-registration/. The home page says you "must first be a registered user" (create a store account, then apply). Audience: "social media influencers, content creators, hosting companies, and others".
- Cookie: **30 days, LAST-click credit** (from page config `cookie_duration":30,"affiliate_credit":"last"`). Link format `?aff=<ID>` (affiliate_keyword "aff").
- Payout: **PayPal** ("We use PayPal for payouts. Please enter your PayPal email ID in the Payment Email field"). Search result summary says paid on the 1st of each month (single secondary source, https://altairtech.io/affiliate-home/ indexed text; I could not see it on the page I fetched, so unverified).
- **Commission rate: NOT STATED.** The pages show a banner "Fee % of revenue 0.52 %" with an "Estimated Adjustment Date": that looks like a site-wide widget, not the affiliate rate. Do not treat it as the commission.
- Form fields (same SliceWP form as Solo Satoshi): Username *, First Name *, Last Name *, Email *, Password *, Password Confirmation *, Payment Email *, Website (optional), How will you promote us? *, I agree to terms & conditions checkbox. (Signing up for a store account first requires a normal WooCommerce registration; exact fields not captured.)
- Do they stock Bitaxe/NerdQaxe? Their site and HashHawks' partner listing say they carry GekkoScience, Canaan, NerdQaxe and more (https://hashhawks.com/en/partners). I did not confirm Bitaxe stock or prices. The collector is blocked by a bot challenge (see `unscrapable` in latest.json), so tracking Altair needs a manual entry or a browser scraper, and a link without price data is less useful.
- Note: **not on the site yet**, so low priority until we track their prices.

### MineShop (mineshop.eu, Dublin, Ireland: EU seller, not US) -> WEB FORM, open, fast
- **Program exists.** Apply: https://mineshop.eu/affiliate/apply. Reviewed manually in 24-48 hours.
- **Commission: 3%** of net price (after discounts, before tax and shipping). Referral link `?wpam_id=` plus a unique customer coupon code you choose.
- **Cookie length: NOT STATED** (page says tracked via link or coupon, no duration).
- Payout: monthly, manual transfer **against an invoice the affiliate sends**; minimum payout not stated. Invoicing is a hassle for a US individual, same as Power Mining.
- Rules: no self-referrals, no spam, no misleading claims.
- Form fields: Name / channel name *, Email *, Desired coupon code * (3-32 letters/numbers, hyphen/underscore allowed), Website, Social / video channel, Audience size *, Country *, How will you promote Mineshop.eu? * (plus a honeypot "Company fax" field to leave empty). Page lists top affiliates at EUR 1M+ referred sales, so it is an active program.
- Audience size is required (the owner can honestly say "new site, starting from 0").
- It is on our `unscrapable` list (HTTP 403 for the collector), so it is not tracked yet either. EU shop; does it ship to US buyers? Not verified.

### NerdQaxe Store (nerdqaxestore.com, ships from Houston TX)
- No affiliate or partner page found, and the site did not load from the box (TLS failure) so I could only read search snippets (https://nerdqaxestore.com/). Search found nothing on an affiliate program.
- **Caution:** Scamadviser rates it low (https://www.scamadviser.com/check-website/nerdqaxestore.com, "domain recently registered") and one Trustpilot review reports a payment with no response (https://ca.trustpilot.com/review/nerdqaxestore.com, a single review). I would not list or promote it until vetted.

### Plebsource (plebsource.com)
- Store was in "invite only / password" mode when search indexed it (https://plebsource.com/). Site did not load from the box. No affiliate program found. Skip for now.

### TinyChipHub (tinychiphub.com), IxTech (ixtech.xyz)
- Homepages loaded, but no affiliate/partner/referral link on the front page HTML. Not investigated further. IxTech is listed as a "partner" on HashHawks (https://hashhawks.com/en/partners), which is a different aggregator site.

### Corrections / notes on existing sections
- Power Mining minimum payout: the live page (https://shop.powermining.io/pages/affiliate) says "The minimum payout amount is €100", matching section 3. One search snippet said €10, which looks like a truncated version of that. Cookie 7 days and "up to 10%" are confirmed again. Page also says "Select the option during signup" for free test units (a product-request option in the GoAffPro form).
- HashHawks (https://hashhawks.com/en/partners) is a competitor/aggregator that lists Solo Satoshi, PlebSource, IxTech, Altair, Bitaxe.de, Power Mining and The Solo Mining Co (UK) as partners. It confirms those shops work with affiliates, and it is a model for how a comparison site pitches sellers.

## What I could not verify
- Solo Satoshi's commission rate, minimum payout, and a support/affiliate contact email.
- Solo Satoshi / Altair: whether a CAPTCHA appears and whether approval is instant or manual.
- Altair: commission rate, payout schedule (only one secondary source), whether Bitaxe is stocked.
- MineShop: cookie length, minimum payout, US shipping.
- Whether the owner has a PayPal account (needed for both Solo Satoshi and Altair payouts).
- Nothing was submitted, signed up for, or emailed.

## Recommended order
1. Solo Satoshi (US seller, in our feed, open program, 30-day cookie). Needs PayPal email from the owner, plus his OK on the form values and a quick look before submit. Add the site affiliate disclosure first.
2. Power Mining (already drafted above).
3. Bitcoin Merch email (already drafted above; update the draft to use bitaxeradar.com and contact@bitaxeradar.com and drop the real name).
4. MineShop and Altair after we start tracking them. Skip Bitaxe.de until non-EU is confirmed. Skip NerdQaxe Store and Plebsource.
