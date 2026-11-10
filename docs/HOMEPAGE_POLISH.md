# Homepage polish, explained simply

Branch `feature/homepage-polish` (Nov 10, 2026). Not live until Shervin says yes.

## What changed

- **Price chart (every miner page).** One stepped line per shop. A price holds until the next check, so the line steps instead of sloping. Solid means in stock and dashed means sold out. The cheapest shop right now gets a soft orange fill, a pulsing "Now $X" dot and its shop name. If today's price is above the lowest in-stock price in the window, a green "Low $X" marker sits on the line and a note says when it was last seen. Tap or hover anywhere for every shop's price on that day. The lines draw in left to right the first time the chart scrolls into view. The labels are HTML on top of the SVG, so text stays readable on a phone. At most 5 shops are drawn, and every shop is still in the price log.
- **Today's best prices: 3 cards.** The best price per TH/s in each size band, then the 3 best of those. The grid is even: three across on desktop and stacked on a phone.
- **Photos** for NerdOCTAXE Gamma, StealthMiner, NerdQX, GekkoScience KBeast 50 and Bitaxe Ultra. Every miner with a page now has a real photo. Sources are in `docs/IMAGE_SOURCES.md`.
- **Questions moved to `/faq/`**, with FAQPage schema and the power-cost calculator. The FAQ is linked from the footer. The homepage ends at the price-alert form, and the Ask chat covers the rest. Model pages link to `/faq/#cost`.
- **The "how it works" bubbles are gone**, along with their CSS.
- **Invisible bot check.** Cloudflare Turnstile now runs with `appearance: "interaction-only"`, so nothing shows unless Cloudflare needs a click. The Worker gets the same `cf-turnstile-response` token, so the Worker needed no change. If the check hasn't finished when someone presses the button, the form waits for it and then sends.
- **Motion.** The cards and tiles fade and slide in, the hero numbers count up, the radar sweeps, and the live dot pings. The cards lift on hover and their photos zoom a little. All motion is vanilla CSS/JS and turns off with reduced motion. The hidden starting states only exist after `motion.js` adds a class, so the page is complete with JavaScript off (story #46).

## Bug stories

**#47. A comparison page linked to a page that no longer exists.**
Problem: on main, `/compare/avalon-nano-3s-vs-hammer-bc04/` linked to `/compare/bitaxe-gamma-vs-nerdaxe-gamma/`, a 404, and the internal-links test failed.
Cause: the builder skips a comparison when one of its miners has no listings today, but the "other comparisons" links were drawn from the full hand-written list.
Fix: one list, `BUILT_PAIRS`, decides which comparison pages get built, and every comparison link reads from it. Shop links work the same way: `BUILT_SELLERS` and `seller_a()` print a plain name when the shop has no page today.

**#48. A test expected a shop page that the data no longer builds.**
Problem: the affiliate-link test read `/sellers/bitaxede/`, which wasn't built.
Cause: Bitaxe.de had no listings in today's data, so by design it gets no page. The test assumed every affiliate shop always has one.
Fix: the test checks the shops whose pages exist. Nothing links to a missing page, because of #47.

**#49. An old newsletter issue linked to a miner with no page.**
Problem: once #47 was fixed, the same test found `/newsletter/issue-002/` linking to `/models/nerdaxe-gaia-copper-pro/`.
Cause: the test stops at its first failure, so the second broken link was hiding behind the first. Old issues name miners that may have no listings today.
Fix: `model_a()` links a miner only when its page is built. Lesson: after fixing one failure from a "stop at first" test, run it again.

**#50. The easiest product photos were the wrong ones.**
Problem: the first NerdQX image at Bitcoin Merch is named `ChatGPTImage…`, so it is AI-generated. D-Central's StealthMiner photo has a "D-Central × Structur3" logo printed over the product.
Cause: a shop's first image isn't always a real photo of the exact model.
Fix: I checked every candidate by eye. NerdQX uses the shop's second image, a real photo. StealthMiner uses the enclosure maker Structur3's own photo of the same case. Bitaxe Ultra uses the maker's open-source repo photo.

**#51. Cards stopped lifting on hover after the entrance animation.**
Problem: after a card faded in, hovering did nothing.
Cause: the entrance animation ends with `animation-fill-mode: forwards` holding `transform: none`, and a held animation beats the `:hover` transform.
Fix: the entrance animates the separate `translate` property and hover uses `transform`, so the two stack.

**#52. The chart gave the wrong date for the lowest price.**
Problem: the Avalon Q note said the $1,349 low was on Oct 23. The line clearly stayed at $1,349, in stock, until Nov 2.
Cause: to keep the page small, the chart keeps only the checks where price or stock changed. The low date was read from that shortened list, which gave the first day at the price instead of the last.
Fix: the low and its date come from every check. The note now reads "last seen Nov 2".

**#53. The chart drew empty path pieces.**
Problem: lines that never changed price were split into extra zero-length `<path>` elements.
Cause: in the step builder, "same stock status, same price" fell into the "stock status changed" branch.
Fix: the run only splits when stock status really flips.

**#54. My test harness nearly posted to the real Worker.**
Problem: the browser test of the invisible bot check was meant to fake the Worker reply, but it showed "Network error".
Cause: the fake was set for `**/workers.dev/subscribe`, which doesn't match `bitaxe-radar-alerts.bitaxeradar.workers.dev`, so the request went to the real Worker. CORS blocked it, and Cloudflare's test token would have failed verification anyway, so no signup was created.
Fix: the fake now matches the real host. A second run returned the fake "check your inbox" reply, and the posted body carried the Turnstile token.

**#55. A markup tweak broke an unrelated test.**
Problem: adding `data-count` for the count-up broke a test that read `<strong>32</strong> miners tracked`.
Cause: the test matched the exact tag, not the number.
Fix: the test accepts attributes on the tag. The visible number is unchanged, and with JavaScript off it's the real number from the start.
