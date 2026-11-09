# Ask Bitaxe Radar — build log

Shipped Nov 9, 2026. Live at https://bitaxeradar.com/ask/ and as a site-wide chat bubble (Shervin's idea) on every page.

This page is the short story of how the Claude Q&A box was built, and the mistakes we caught before it went live. Good interview material: "I didn't just call an LLM — I measured it and fixed what it got wrong."

## What it is

A question box on the site. A visitor types something like "cheapest Bitaxe in stock?" The page sends that to our Cloudflare Worker (`POST /ask`). The Worker:

1. Checks the question (max 300 characters) and rate-limits per visitor.
2. Caps questions at 200/day so a bot can't run up the Claude bill.
3. Loads the live miner table from `bitaxeradar.com/data.js`.
4. Calls Claude Haiku with that table as context plus a short system prompt.
5. Asks Claude for structured JSON (`working`, `answer`, `models_mentioned`, `confidence`, `in_data`).
6. Checks the reply, drops unknown miner ids, and never returns scratch notes or internal errors to the visitor.

Cost per question is about half a tenth of a cent. The Anthropic account also has a $10/month spend limit.

## Mistakes I caught

These all showed up when we ran the real Claude API against six test questions (not the mocked unit tests). Total cost of that live check: about one cent.

### 1. Unsorted list → wrong "next cheapest"

**Bug.** Claude was asked for the next-cheapest miner after a sold-out one and named the wrong model.

**Cause.** The miner table we sent was in whatever order `data.js` had. Claude treated "next in the list" like "next cheapest."

**Fix.** Sort the context cheapest-in-stock first before sending it. Ranking questions then match the table order.

**Lesson.** Grounding data is not enough — the *shape* of the data matters. If you care about "cheapest" or "next," put the rows in that order yourself instead of hoping the model sorts them.

### 2. Thinking out loud in the answer

**Bug.** Some replies mixed scratch reasoning into the visitor-facing answer ("let me check the list…", intermediate picks).

**Cause.** The model had nowhere private to work, so it used the answer field as a scratchpad.

**Fix.** Add a hidden `working` field to the JSON schema. Claude fills that first; the Worker keeps it server-side and only returns `answer` (plus the small metadata fields).

**Lesson.** If you want a clean answer, give the model a place to think that the user never sees.

### 3. Empty `models_mentioned`

**Bug.** The `models_mentioned` array often came back empty even when the answer named a miner.

**Cause.** The schema listed the field but did not say what belonged in it.

**Fix.** Add a short field description: put every miner id the answer talks about. After that, the array filled in reliably.

**Lesson.** Structured output follows the descriptions you write. A bare field name is not enough.

### 4. Truncated replies

**Bug.** Longer answers got cut mid-sentence and failed our JSON parse check (502).

**Cause.** `max_tokens` was too low for the scratchpad + full answer.

**Fix.** Raise `max_tokens` to 1000. That still keeps cost tiny at Haiku prices.

**Lesson.** Measure real replies. Caps that look fine on short mocks can clip real answers.

### 5. Price chart was hard to read

**Bug.** On a miner page, the price history only made sense if you hovered each dot to see which shop it was. A visitor browsing on a phone was confused.

**Cause.** Color alone, no always-visible shop labels.

**Fix.** A legend redesign (shop colors + prices) is in progress on a separate branch. Not shipped yet.

**Lesson.** If the only way to read a chart is hover, it fails on phones. Shervin caught this while watching someone use the live site.

### 6. Mobile Ask chip covered the Buy button

**Bug.** The example-question chip sat on top of the orange Buy CTA, and its × dismiss control was cut off past the right edge of the screen.

**Fix.** On phones the chip sits in one bottom row next to the Ask bubble (× stays on-screen). On model pages it stays hidden until the Buy button scrolls clear.

**Lesson.** Fixed chrome has to respect the page's primary CTA — especially on a 390px-wide screen.

### 7. Chip looked see-through

**Bug.** Page text showed through the suggestion chip, so it looked faded.

**Cause.** The chip buttons lost out to a global `button` style in places, and the wrap around chip + × had no solid fill.

**Fix.** A solid `#243a5e` tray behind chip and ×, with selectors strong enough to beat the global button rule. Fade-in runs once, then stays fully opaque.

### 8. Answer links showed raw ids

**Bug.** Under an answer the links said `bitaxe-gamma` instead of "Bitaxe Gamma".

**Fix.** `RADAR_ASK.names` ships a friendly name map on every page; both the floating widget and `/ask/` use it.

### 9. Claude typed raw `/models/…` paths

**Bug.** Some answers included paths like `/models/bitaxe-gamma/` in the prose. The site already adds the miner links separately.

**Fix.** Keep Shervin's four rules, and add a short formatting note to `SYSTEM_PROMPT`: never put URLs or page paths in the answer.

### 10. Phone cache hid the new bubble

**Bug.** After shipping the site-wide chat bubble, Shervin's phone still showed the old page for a while — no bubble.

**Cause.** Aggressive mobile cache / CDN. A private tab showed the new assets right away; the normal tab caught up in under about 10 minutes.

**Lesson.** When "it's not live" on a phone, check a private tab before assuming the deploy failed. Shervin found this by testing on his real phone.

### 11. Phone keyboard covered the chat panel

**Bug.** With the Ask panel open on a phone, the on-screen keyboard shoved the layout around, covered the input, and you could still drag/scroll the page behind the panel.

**Fix.** Size the open panel to `window.visualViewport` (with `dvh` as a CSS fallback), lock background scroll with a `body.ra-ask-lock` fixed position, pin the input above the keyboard, keep messages scrolling inside, and use a 16px input so iOS doesn't zoom.

**Lesson.** Full-screen overlays on iOS need `visualViewport`, not just `100vh`. Shervin found the keyboard issue by asking a real question on his phone.

The site-wide floating chat bubble itself was Shervin's idea (example chips that open the chat), not just an engineering add-on.

### 12. No conversation memory

**Bug.** Shervin asked "Most expensive miner" (got Avalon Q), then "Why is it so expensive?" Claude said it didn't know which miner he meant. A third follow-up ("the one you literally just told me about") still had no prior message.

**Cause.** Each `POST /ask` was stateless — the Worker only received the new question, never the earlier turns.

**Fix.** The chat widget keeps the last ~6 turns in `sessionStorage` (so the chat follows you around the site in that tab), sends them as `history` with each new question, and shows a **New chat** button to clear. The Worker validates history strictly (roles, size caps) and forwards it to Claude as prior messages. Malformed or oversized history is dropped, not trusted.

**Lesson.** "Chat" implies memory. A single-shot API call is a Q&A box, not a conversation, until you send the recent turns along.

### 13. Answers got too long on "why" follow-ups

**Bug.** After multi-turn memory shipped, a follow-up like "Why is it so expensive?" after "Most expensive miner" came back ~7 sentences. Shervin's rule was 2–4.

**Cause.** The system prompt said "2-4 sentences. No fluff." but Claude padded "why" answers with restating and extra context. The `answer` schema field had no length description either.

**Fix.** Tighten rule 4: 2–4 short sentences, ~70 words max, lead with the answer, no padding, still apply on why/follow-ups; if data doesn't explain something, one short clause then stop. Mirror that in the `answer` schema description. Keep `max_tokens` at 1000 so the hidden `working` scratchpad still has room.

**Lesson.** Length rules need to be specific (word cap, no restating) and repeated in the schema — a soft "2-4 sentences" alone isn't enough for follow-up "why" questions.

## How we checked it

- Mocked Worker tests (`cd worker && npm test`) — free, repeatable, no API key.
- Live try script (`worker/scripts/try_ask.mjs`) — six real questions against Claude, including off-topic ("write me a cat poem") which must be refused.
- Result before ship: 6/6 correct on the live set.

## Files

| Path | Role |
|------|------|
| `worker/src/ask.js` | `/ask` handler, prompt, Claude call, checks |
| `worker/src/index.js` | Routes `/ask` to the handler |
| `site/ask.js` | `/ask/` page form → Worker |
| `site/ask-api.js` | Shared Ask fetch + friendly names |
| `site/chat-widget.js` | Site-wide floating bubble + panel |
| `build_site.py` → `build_ask()` | Builds `/ask/` page |
| `worker/test/ask.test.mjs` | Mocked tests |
| `tests/test_ask_page.py` | Static page checks |
| `worker/wrangler.toml` | Worker config, daily cap, `ASK_KV` |

## What "done" means here

- Worker secret `ANTHROPIC_API_KEY` set.
- KV namespace `ASK_KV` bound for the daily cap.
- `/ask/` live on bitaxeradar.com.
- Live checks: a real price question returns a grounded answer; an off-topic question is refused; `/health` still works.
