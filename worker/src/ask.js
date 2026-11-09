// "Ask Bitaxe Radar" - answers miner questions with Claude, using ONLY the site's live price data.
//
// The whole trip, step by step:
//   1. Visitor sends   POST /ask   {"question": "..."}
//   2. We check the question (not empty, max 300 characters).
//   3. We check the daily cap (so a bot can't run up the Claude bill).
//   4. We download the site's live data (bitaxeradar.com/data.js) and shrink it to one short line per miner.
//      This is the "context": the facts Claude is allowed to use. Feeding real data in is called "grounding".
//   5. We call the Claude Messages API with: our rules (system prompt) + the data + the question.
//   6. Claude must reply in a fixed JSON shape (a "JSON schema"). That's "structured output".
//   7. We check that JSON ourselves anyway (never trust an AI's output blindly), then send it back.
//
// Secret needed (never put it in code or git):   npx wrangler secret put ANTHROPIC_API_KEY
// Optional KV storage for the daily counter:      binding name ASK_KV (see wrangler.toml)

// ---------- settings ----------
export const MAX_QUESTION_CHARS = 300;
export const DEFAULT_DAILY_LIMIT = 200;      // ~200 questions/day x ~$0.0005 = about 10 cents/day worst case
export const DEFAULT_MODEL = "claude-haiku-5-5";   // cheapest, fastest current Claude model
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_VERSION = "2026-10-21";      // API version header from Anthropic's docs
const MAX_ANSWER_CHARS = 1500;
const CONFIDENCE = ["high", "medium", "low"];

// ---------- the system prompt (written by Shervin) ----------
// The system prompt is the rule book Claude follows for every question. It's the most important part
// of "prompt engineering": small wording changes here change the answers a lot.
// Design choice (rule 2): facts that change (prices, stock) come ONLY from live data, because Claude's
// memory is old and it would confidently guess wrong prices ("hallucinate"). General mining knowledge
// is allowed, but flagged with in_data: false so the site can label it.
export const SYSTEM_PROMPT = `You are the Bitaxe Radar helper. You answer questions
about the home Bitcoin miners on bitaxeradar.com.

1. For prices, stock, specs, and shops, use ONLY the
   miner data below. Never guess a price.
2. If the data doesn't have the answer, say so. For
   general mining questions, you may use general
   knowledge, but set in_data to false.
3. If a question isn't about Bitcoin mining or the
   site, politely say you only help with miners.
4. Be helpful, calm, and direct. 2-4 sentences.
   No fluff.

Formatting: never put URLs or page paths in the answer
(e.g. /models/bitaxe-gamma/). The site adds the links.
Name miners in plain words.`;

// ---------- the JSON shape Claude must reply with ----------
export const ANSWER_SCHEMA = {
  type: "object",
  properties: {
    // "Scratch paper" Claude fills in FIRST: filter and compare rows here, so the answer itself stays clean.
    // (Without it, Claude "thought out loud" inside the answer on comparison questions.) Never shown to visitors.
    working: { type: "string", description: "Brief private notes: the rows you filtered and compared. Not shown to the visitor." },
    answer: { type: "string", description: "The final reply for the visitor, following the rules." },   // shown to the visitor
    // "description" tells Claude what goes in each field, so the rules prompt can stay about behavior.
    models_mentioned: { type: "array", items: { type: "string" },   // miner ids, e.g. "bitaxe-gamma"
      description: "The id column value of every miner named in the answer, e.g. bitaxe-gamma. Empty if none." },
    confidence: { type: "string", enum: CONFIDENCE,
      description: "high = the data answers it directly; medium = you compared or calculated; low = only partly answered." },
    in_data: { type: "boolean" },                              // false = "the data didn't have the answer"
  },
  required: ["working", "answer", "models_mentioned", "confidence", "in_data"],
  additionalProperties: false,
};

// ---------- step 2: check the question ----------
export function validateQuestion(q) {
  if (typeof q !== "string") return { error: "Please type a question." };
  const question = q.replace(/\s+/g, " ").trim();   // squash extra spaces/newlines
  if (!question) return { error: "Please type a question." };
  if (question.length > MAX_QUESTION_CHARS) return { error: `Keep it under ${MAX_QUESTION_CHARS} characters.` };
  return { question };
}

// ---------- step 3: daily cap ----------
// With KV (Cloudflare's simple key-value storage) the count is shared by all Worker copies.
// Without KV (local tests) we fall back to a counter in memory. KV isn't perfectly exact under heavy
// traffic, but as a cost safety net it's good enough.
const memoryCounts = new Map();
export async function takeDailySlot(env, now = new Date()) {
  const limit = Number(env.ASK_DAILY_LIMIT) || DEFAULT_DAILY_LIMIT;
  const key = "asks:" + now.toISOString().slice(0, 10);   // e.g. asks:2026-11-09 (UTC day)
  const used = env.ASK_KV ? Number(await env.ASK_KV.get(key)) || 0 : memoryCounts.get(key) || 0;
  if (used >= limit) return false;
  if (env.ASK_KV) await env.ASK_KV.put(key, String(used + 1), { expirationTtl: 2 * 86400 });
  else memoryCounts.set(key, used + 1);
  return true;
}
export function _resetMemoryCounts() { memoryCounts.clear(); }   // for tests

// ---------- step 4: live data -> compact context ----------
// data.js looks like:  window.RADAR = {"latest": {...}, "history": {...}};
// We only need "latest": the miners (models) and the shop listings (offers).
export async function loadLatest(env) {
  const site = env.SITE_URL || "https://bitaxeradar.com";
  // cf.cacheTtl: Cloudflare keeps a copy for 10 minutes, so we don't re-download it for every question.
  const r = await fetch(site + "/data.js", { cf: { cacheTtl: 600 } });
  if (!r.ok) throw new Error("data.js HTTP " + r.status);
  const text = await r.text();
  const jsonText = text.slice(text.indexOf("=") + 1).trim().replace(/;\s*$/, "");
  return JSON.parse(jsonText).latest;
}

const num = (x, d = 2) => (typeof x === "number" && isFinite(x) ? Number(x.toFixed(d)) : null);

// One line per miner keeps the prompt small (~37 miners -> a few thousand tokens, a fraction of a cent).
export function buildContext(latest) {
  const sellers = latest.sellers || {};
  const offers = latest.offers || [];
  const header = "id | name | chip | TH/s | watts | J/TH | cheapest in-stock USD | at shop | in-stock listings | page";
  const rows = [];
  for (const [id, m] of Object.entries(latest.models || {})) {
    const usable = offers.filter((o) => o.model === id && o.in_stock && !o.stale && typeof o.price_usd_approx === "number");
    usable.sort((a, b) => a.price_usd_approx - b.price_usd_approx);
    const best = usable[0];
    const jth = m.hashrate_ths && m.watts ? num(m.watts / m.hashrate_ths, 1) : null;
    rows.push({ price: best ? best.price_usd_approx : Infinity, line: [id, m.name, m.chip || "?", num(m.hashrate_ths) ?? "?", m.watts ?? "?", jth ?? "?",
      best ? num(best.price_usd_approx) : "out of stock", best ? (sellers[best.seller]?.name || best.seller) : "-",
      usable.length, `/models/${id}/`].join(" | ") });
  }
  // Rows sorted cheapest first (out of stock last). Small models rank lists badly from scattered rows;
  // pre-sorting the data makes "cheapest / next cheapest" questions reliable.
  rows.sort((a, b) => (a.price - b.price) || 0);   // "|| 0": two out-of-stock rows (Infinity - Infinity = NaN) count as a tie
  return `Data updated: ${latest.generated_at} (rows sorted by price, cheapest in stock first)\n` +
    [header, ...rows.map((r) => r.line)].join("\n");
}

// ---------- step 5: the request we send to Claude ----------
export function buildClaudeRequest(question, context, systemPrompt, model = DEFAULT_MODEL) {
  return {
    model,
    max_tokens: 1000,                      // hard cap on reply length = hard cap on cost per question
    system: systemPrompt,                  // the rules
    thinking: { type: "disabled" },        // short lookups don't need "thinking" tokens (cheaper, faster)
    output_config: {
      effort: "low",
      format: { type: "json_schema", schema: ANSWER_SCHEMA },   // force the JSON shape
    },
    messages: [{
      role: "user",
      // XML-style tags make it clear to Claude which part is data and which part is the visitor.
      content: `<data>\n${context}\n</data>\n\n<question>${question}</question>`,
    }],
  };
}

export async function callClaude(env, body) {
  const r = await fetch(ANTHROPIC_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": env.ANTHROPIC_API_KEY,    // the secret: proves it's us, and bills our account
      "anthropic-version": ANTHROPIC_VERSION,
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(20000),     // give up after 20 seconds instead of hanging
  });
  const data = await r.json().catch(() => null);
  if (!r.ok) throw new Error(`Claude HTTP ${r.status}: ${data?.error?.message || "no details"}`);
  return data;
}

// ---------- step 7: check Claude's reply ----------
// Even with structured output, a reply can be cut off (max_tokens) or be a refusal. And Claude could
// name a miner that doesn't exist (a "hallucination"), so we drop any id that isn't in our data.
export function parseClaudeReply(data, knownIds) {
  if (!data || data.stop_reason === "refusal" || data.stop_reason === "max_tokens") return null;
  const textBlock = (data.content || []).find((b) => b.type === "text");
  if (!textBlock) return null;
  let out;
  try { out = JSON.parse(textBlock.text); } catch { return null; }
  if (!out || typeof out.answer !== "string" || !out.answer.trim()) return null;
  if (!Array.isArray(out.models_mentioned) || typeof out.in_data !== "boolean") return null;
  const confidence = String(out.confidence || "").toLowerCase();   // docs: enum casing isn't guaranteed
  if (!CONFIDENCE.includes(confidence)) return null;
  return {
    answer: out.answer.trim().slice(0, MAX_ANSWER_CHARS),
    models_mentioned: [...new Set(out.models_mentioned.filter((id) => knownIds.has(id)))],
    confidence,
    in_data: out.in_data,
  };
}

// ---------- the route: POST /ask ----------
// `json` is the Worker's response helper (adds CORS headers). `deps` lets tests swap the prompt.
export async function handleAsk(request, env, json, deps = {}) {
  const systemPrompt = deps.systemPrompt ?? SYSTEM_PROMPT;
  if (!systemPrompt.trim() || !env.ANTHROPIC_API_KEY) return json({ ok: false, error: "Ask isn't set up yet." }, 503, request);

  let input;
  try { input = await request.json(); } catch { return json({ ok: false, error: "Send JSON like {\"question\": \"...\"}." }, 400, request); }
  const v = validateQuestion(input?.question);
  if (v.error) return json({ ok: false, error: v.error }, 400, request);

  // Per-visitor speed limit (same limiter as signups), then the site-wide daily cap.
  if (env.RATE_LIMITER) {
    const { success } = await env.RATE_LIMITER.limit({ key: "ask:" + (request.headers.get("CF-Connecting-IP") || "unknown") });
    if (!success) return json({ ok: false, error: "Too many questions. Wait a minute and try again." }, 429, request);
  }
  if (!(await takeDailySlot(env))) return json({ ok: false, error: "Ask has hit today's limit. Try again tomorrow." }, 429, request);

  try {
    const latest = await loadLatest(env);
    const body = buildClaudeRequest(v.question, buildContext(latest), systemPrompt, env.ASK_MODEL || DEFAULT_MODEL);
    const data = await callClaude(env, body);
    const result = parseClaudeReply(data, new Set(Object.keys(latest.models || {})));
    if (!result) return json({ ok: false, error: "Couldn't get a clear answer. Try rewording it." }, 502, request);
    console.log("ask ok", JSON.stringify({ q: v.question.length, usage: data.usage }));   // token use, for cost tracking
    return json({ ok: true, ...result, data_updated: latest.generated_at }, 200, request);
  } catch (e) {
    console.error("ask failed", e && e.message);   // never send internal errors (or the key) to the visitor
    return json({ ok: false, error: "Ask is having trouble right now. Try again in a bit." }, 502, request);
  }
}
