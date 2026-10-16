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

I'm the owner, and I run Bitaxe Radar (https://yostoo.github.io/bitaxe-radar/), a free site that tracks prices and stock for small home Bitcoin miners like the Bitaxe and NerdQaxe across a few sellers, including you. It also has a price history chart and a running-cost calculator.

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

I'm the owner. I run Bitaxe Radar (https://yostoo.github.io/bitaxe-radar/), a free price and stock tracker for Bitaxe and NerdQaxe miners that lists Bitaxe.de alongside a few other sellers. It just launched, so I have no audience numbers yet.

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

I'm the owner. I just signed up for your affiliate program for Bitaxe Radar (https://yostoo.github.io/bitaxe-radar/), a free price and stock tracker for Bitaxe and NerdQaxe miners that includes Power Mining. The site just launched, so I don't have traffic numbers yet, and I'm not asking for a review unit. I'll be honest about that and let results speak.

A couple of questions: (1) what commission rate would I start at, and what do the higher tiers require? (2) I'm in the US, so how should I handle the invoice for payouts? Also, my tracker reads your public product pages a few times a day for price and stock. Let me know if you'd like it done differently.

Thanks,
the owner
Bitaxe Radar | https://yostoo.github.io/bitaxe-radar/
