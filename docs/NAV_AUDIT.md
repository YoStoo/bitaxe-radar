# Bitaxe Radar navigation audit (Oct 21, 2026)

Read-only audit of the live site at 390px (phone) and 1280px (desktop), done as a first-time visitor.
Screenshots are in `/workspace/redesign-shots/audit-*.png`. Raw data is in `/workspace/audit/crawl.json` and `metrics.json`.

## Quick facts
- **Crawl:** 46 HTML pages and 66 URLs in total, including assets.
- **Broken internal links: 0.** Every link returns 200. The 404 page correctly returns 404.
- **Speed is fine.** Every page loads in about 0.3 s or less. The one exception was a single 2.9 s cold load of `/in-stock/` on mobile, which loaded in 0.04 s the next time.
- **No sideways scrolling** at 390px on any page.
- **The header nav is the same on all 46 pages** (one variant). Every page sits 1 tap from home, except the 8 non-Bitaxe model pages, which take 2 taps.
- **Not in the sitemap:** `/models/bitaxe-supra/` and `/models/bitaxe-ultra/`. They're linked, but they're missing from `sitemap.xml`.
- **Index URLs are 404s.** `/models/`, `/sellers/`, `/best/`, `/guides/` and `/compare/` all return 404. Someone trimming the URL hits a dead end.

## Top 10 problems (most confusing first)

1. **The site says it's about something narrower than what it now is.**
   - The home hero says "Find the cheapest Bitaxe in stock", and the logo says "Bitaxe Radar". But the menu leads with Solo / Pool / Heaters, and the Pool and Heater pages have no Bitaxes at all.
   - A newcomer who wanted a heater, or just "a home miner", reads "Bitaxe" and isn't sure they're in the right place.
   - **Fix:** change the hero to something like "Every home Bitcoin miner, price-checked. Find the cheapest one in stock, from $67 Bitaxes to space-heater miners." Add one line under it: "New? Take the 3-question quiz →". Keep the brand name.

2. **There's no single "All miners" page, and the category pages overlap heavily.**
   - All 6 heater-page miners are also on `/pool-miners/`. Pool is basically Heaters + Hammer.
   - `/home-miners/` ("Heater & home miners", 8 models) is the heater page plus three more. It's in the footer but not the menu.
   - Avalon Nano 3S and Hammer BC04 show up on both Solo and Pool.
   - The home "Bitaxe miners" link goes to an anchor on the home page (`/#miners`), not to a page.
   - So a visitor can't answer "show me everything" anywhere.
   - **Fix:**
     - Add `/miners/`, one grid of all models with filter chips: Use (Solo / Pool / Heater), Price (<$100 / $100–500 / $500+), Noise (Quiet), and In stock only.
     - Make Solo / Pool / Heaters links into that page with a filter pre-set, or keep them as SEO landing pages with an "All miners" link back.
     - 301-merge `/home-miners/` into `/miners/`, or turn it into the Heaters page, so there aren't two near-identical lists.

3. **"Deals", "In stock" and "Where to buy" cover only the 8 Bitaxe-family models, not the heaters or home miners.**
   - A visitor who taps "In stock" from the Heaters page never sees the Heatbit or Avalon units.
   - "Where to buy" goes to `/where-to-buy-bitaxe/`, and `/bitaxe-black-friday/` lists exactly the same 6 models.
   - **Fix:**
     - Make Deals and In stock cover every tracked model, grouped or filtered by category.
     - Rename "Where to buy" to "Shops" and point it at a new `/sellers/` index of every shop with its flag and what it sells.
     - Leave the Bitaxe-only pages as SEO pages that link out from the footer and guides.

4. **The mobile menu hides two of its seven items.**
   - At 390px only Solo, Pool, Heaters, Deals and Alerts show. "In stock" and "Where to buy" are hidden with `.hide-sm`, so on a phone you can't reach the shops or the full stock list from the header.
   - **Fix:** use a 5-item mobile bar: **Miners · Deals · Find my miner · Guides · Alerts**. Solo, Pool and Heaters become chips at the top of `/miners/`. Or add a "More ☰" item that opens a sheet with everything.

5. **No guide or "help me choose" path in the menu.**
   - The two guides (Solo vs pool, How heater miners work) and the 4 "Best for" pages are reachable only through the home chips and the footer.
   - `/best/under-100/` and `/best/heating-a-room/` have only 5 inbound links each.
   - Beginners, who are the target, have no obvious "start here".
   - **Fix:**
     - Add a "Find my miner" quiz (see the spec below) and a "Guides" menu item leading to a new `/guides/` index.
     - Put the "Best for" chips on every category page, not just home.

6. **Category pages repeat the menu.**
   - `/solo-miners/` (and Pool, Heaters, Best-for) shows the header pills Solo / Pool / Heaters / Deals / Alerts, then the *same five pills again* under the title.
   - That's twice the chrome before the first miner, and the first card sits about 480px down on a phone.
   - **Fix:** replace the second row with real filters (In stock only · Under $100 · Quiet · Sort: price / earnings) or remove it.

7. **The breadcrumbs are shallow and skip the category.**
   - Model pages show "Home › Bitaxe Gamma", and seller pages show "Home › Where to buy › …". Neither tells you which category you came from, and there's no "back to results".
   - **Fix:** use "Home › All miners › Solo › Bitaxe Gamma" (based on the model's main category). Add a "← Back to Solo miners" link above the photo on mobile.
   - Also add index pages for `/models/`, `/sellers/`, `/guides/`, `/best/` and `/compare/` (or redirect them to `/miners/`, `/sellers/` and `/guides/`) so trimmed URLs don't 404.

8. **Labels are confusing.**
   - "Solo" vs "Pool" mean nothing to a first-timer. A Bitaxe is labelled "Solo", but its card shows "Pool ≈ $1.16/mo".
   - Pages show times like "checked Oct 21, 2026 14:26 UTC", which US visitors have to convert.
   - "Price alerts" is an anchor (`/#alerts`) that jumps you from any page back to the home page.
   - The home card says "Solo · 9 miners", but the Solo page lists 11 models (Supra and Ultra in the small print).
   - The Solo page leads with the $299 Braiins Mini Miner rather than the $67 Gamma, its flagship.
   - **Fix:**
     - Use plain labels with a hint line: "Solo: lottery-style, tiny chance at a whole block", "Pool: small steady payouts", "Heaters: warm a room and mine".
     - Show "updated 18 min ago" everywhere (the home page already does this).
     - Make "Alerts" its own `/alerts/` page.
     - Make the counts match.
     - Sort solo by best value (cheapest in stock first).

9. **Pages are long and wordy on phones.**
   - Home is about 4,300px tall at 390px (roughly 5 screens) and about 600 words.
   - Model pages are about 5,000px and 650 words.
   - In stock is about 5,500px and 700 words.
   - Model pages put "What it could earn", the price table, price history, the alert form, "Good to know", FAQ and "Keep comparing" all in one scroll.
   - **Fix:**
     - Above the fold on a model page: photo, price, CTA and one-line earnings.
     - Collapse "Good to know", FAQ and history into `<details>` sections.
     - On home, show 3 best prices instead of 6, plus an "All miners →" button.
     - Move "How it works" and the FAQ lower or onto `/how-we-track/`.

10. **The tap targets are small.**
    - 20–60 interactive elements per page are under 32px tall. Examples:
      - footer links are 21px tall
      - breadcrumb "Home" is 37×18
      - shop names in tables are 22px
      - In-stock model labels are 17px
      - "See prices" buttons are 30px
    - The footer link wall is hard to hit with a thumb.
    - **Fix:** give links in lists and footers at least 44px of tap height (padding), and make "See prices" 40–44px. Group the footer into 3 short columns (Miners / Help / About) rather than 17 inline links.

Also noted: the 404 page is fine (menu, helpful links, correct status). It could add the quiz and an "All miners" button.

## Proposed simple site map

**Header (same on every page; phone shows all 5):**

| Menu item | Goes to | What's there |
|---|---|---|
| **All miners** | `/miners/` | Every home miner in one photo grid. Filter chips for Use (Solo · Pool · Heater), Price (<$100 · $100–500 · $500+), Quiet, and In stock only. Sort by price, value or earnings. |
| **Deals** | `/deals/` | Price drops and the cheapest in stock, across *all* categories. Absorbs `/in-stock/`, which becomes an "In stock only" view. |
| **Find my miner** | `/find/` | A 3-question quiz (below). |
| **Guides** | `/guides/` | Solo vs pool, How heater miners work, the Best-for lists, the comparisons, and Where to buy a Bitaxe. |
| **Alerts** (orange button) | `/alerts/` | Email price alerts as a standalone page. |

**Second level (one tap from the pages above):**
- **Category landings, kept for Google:** `/solo-miners/`, `/pool-miners/`, `/heater-miners/`. Each has the same grid pre-filtered, plus an "All miners" link. Merge `/home-miners/` into `/miners/` with a 301 redirect, or make it the Heaters page.
- **Best-for lists:** `/best/beginners/`, `/best/quiet/`, `/best/under-100/`, `/best/heating-a-room/` (shown as chips on `/miners/` and `/guides/`).
- **Model pages:** `/models/*`, with the breadcrumb Home › All miners › {Category} › {Model}.
- **Shops:** `/sellers/` (new index) leading to `/sellers/*`.
- **Footer only:** About & how we track, Advertise, Black Friday (seasonal), contact.

Every page is at most 2 taps from home: menu, then a filter or card.

### "Find my miner" quiz (3 questions, no sign-up)
1. **What do you want it to do?** Take a lottery shot at a whole block (solo) · Earn small, steady sats (pool) · Heat a room and mine (heater).
2. **Budget?** Under $100 · $100–$500 · $500+.
3. **Where will it live?** On my desk, so it has to be quiet · Garage or office, so noise is OK · Living room or bedroom, so it has to be quiet *and* warm.

The result is the top 3 matching models, shown as the usual photo cards. Each card has its live cheapest in-stock price, its pool earnings and power cost (the usual conservative figures), and a "Why this one" line. Under that go an "Adjust answers" link and a "Get a price alert" button.

It can all run client-side from `data.js`, with no AI needed. That keeps it fast, free and honest, and the later "AI miner picker" idea can build on the same answers.

## Suggested order of work
1. `/miners/` with filters, plus header changes 1–4. This is the biggest win.
2. The quiz at `/find/`.
3. Make Deals and In stock cover all categories, and add the `/sellers/` and `/guides/` indexes.
4. Breadcrumbs, the "back to" link, relative times, and the Supra/Ultra sitemap fix.
5. Trim mobile length, add `<details>` sections, and enlarge the tap targets.
