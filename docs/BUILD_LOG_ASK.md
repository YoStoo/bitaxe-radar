# Ask Bitaxe Radar — build log

Shipped Nov 9, 2026. Live at https://bitaxeradar.com/ask/.

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

## How we checked it

- Mocked Worker tests (`cd worker && npm test`) — free, repeatable, no API key.
- Live try script (`worker/scripts/try_ask.mjs`) — six real questions against Claude, including off-topic ("write me a cat poem") which must be refused.
- Result before ship: 6/6 correct on the live set.

## Files

| Path | Role |
|------|------|
| `worker/src/ask.js` | `/ask` handler, prompt, Claude call, checks |
| `worker/src/index.js` | Routes `/ask` to the handler |
| `site/ask.js` | Browser form → Worker |
| `build_site.py` → `build_ask()` | Builds `/ask/` page |
| `worker/test/ask.test.mjs` | Mocked tests |
| `tests/test_ask_page.py` | Static page checks |
| `worker/wrangler.toml` | Worker config, daily cap, `ASK_KV` |

## What "done" means here

- Worker secret `ANTHROPIC_API_KEY` set.
- KV namespace `ASK_KV` bound for the daily cap.
- `/ask/` live on bitaxeradar.com.
- Live checks: a real price question returns a grounded answer; an off-topic question is refused; `/health` still works.
