// Bitaxe Radar - email signup Worker (double opt-in) for Cloudflare Workers.
// No dependencies. Secrets: RESEND_API_KEY, SIGNING_SECRET, TURNSTILE_SECRET.
// Vars: PUBLIC_BASE (this Worker's public URL, no trailing slash), SITE_URL.
//
// Routes:
//   POST /subscribe          JSON or form: email, model, target_price, cf-turnstile-response
//                            or type=newsletter + email + cf-turnstile-response (Home Mining Weekly; no miner/price)
//   GET  /nl/confirm?t=      confirms a newsletter signup (sets contact property newsletter="yes" only)
//   GET|POST /nl/unsubscribe?t=  newsletter-only unsubscribe (newsletter="no"; price alerts untouched)
//
// Newsletter state lives ONLY in the contact properties `newsletter` ("yes"/"no") and `newsletter_at`.
// It never touches `unsubscribed`, `model` or `target_price` (those belong to price alerts), so a newsletter
// signup can't create, revive or change an alert, and an alert unsubscribe doesn't drop the newsletter.
//   GET  /confirm?t=TOKEN    confirms the subscription (double opt-in link from the email)
//   GET|POST /unsubscribe?t= unsubscribes (POST = RFC 8058 one-click)
//   GET  /health

const ALLOWED_ORIGINS = ["https://bitaxeradar.com", "https://www.bitaxeradar.com", "https://yostoo.github.io"];
const FROM = "Bitaxe Radar <alerts@bitaxeradar.com>";
const CONTACT = "contact@bitaxeradar.com";
const POSTAL = "Bitaxe Radar, mailing-address-removed";
const CONFIRM_TTL_SEC = 48 * 3600;
const MODELS = ["any", "bitaxe-supra", "bitaxe-ultra", "bitaxe-gamma", "bitaxe-gamma-duo", "bitaxe-gt-801",
  "nerdaxe-gamma", "nerdaxe-gaia", "nerdqaxe-pp"];
const MODEL_FREE_TEXT = /^[A-Za-z0-9 .+_\-\/()]{1,60}$/;
const enc = new TextEncoder(), dec = new TextDecoder();

// ---------- helpers ----------
function b64u(bytes) {
  let s = ""; for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function unb64u(str) {
  str = str.replace(/-/g, "+").replace(/_/g, "/"); while (str.length % 4) str += "=";
  const bin = atob(str), out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hmacKey = (secret, usages) => crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, usages);

// Token = base64url(JSON payload) + "." + base64url(HMAC-SHA256(SIGNING_SECRET, base64url(JSON payload)))
// payload: {t: "c"|"u", e: email, m: model, p: price, x: expiry (unix sec, optional)}
// NOTE: scripts/send_alerts.py builds "u" tokens with the same format; keep both in sync.
export async function signToken(payload, secret) {
  const body = b64u(enc.encode(JSON.stringify(payload)));
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(secret, ["sign"]), enc.encode(body));
  return body + "." + b64u(new Uint8Array(sig));
}
export async function verifyToken(token, secret, type, nowSec = Math.floor(Date.now() / 1000)) {
  if (typeof token !== "string" || token.length > 2000) return null;
  const [body, sig] = token.split(".");
  if (!body || !sig) return null;
  let ok = false;
  try { ok = await crypto.subtle.verify("HMAC", await hmacKey(secret, ["verify"]), unb64u(sig), enc.encode(body)); } catch { return null; }
  if (!ok) return null;
  let p; try { p = JSON.parse(dec.decode(unb64u(body))); } catch { return null; }
  if (!p || p.t !== type || typeof p.e !== "string") return null;
  if (p.x && nowSec > p.x) return { ...p, expired: true };
  return p;
}

function corsHeaders(request) {
  const origin = request.headers.get("Origin");
  const h = { "Vary": "Origin" };
  if (origin && ALLOWED_ORIGINS.includes(origin)) {
    h["Access-Control-Allow-Origin"] = origin;
    h["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    h["Access-Control-Allow-Headers"] = "Content-Type";
    h["Access-Control-Max-Age"] = "86400";
  }
  return h;
}
const json = (obj, status, request) => new Response(JSON.stringify(obj), {
  status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...corsHeaders(request) } });

function page(title, bodyHtml, env, status = 200) {
  const site = env.SITE_URL || "https://bitaxeradar.com";
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(title)} - Bitaxe Radar</title>
<style>body{font:16px/1.5 system-ui,sans-serif;background:#0f1115;color:#e8ecf3;margin:0;display:grid;place-items:center;min-height:100vh}
main{max-width:520px;padding:28px;background:#171a21;border:1px solid #2a2f3a;border-radius:12px;margin:16px}a{color:#f7931a}h1{margin-top:0;font-size:22px}</style></head>
<body><main><h1>${esc(title)}</h1>${bodyHtml}<p><a href="${esc(site)}">&larr; Back to Bitaxe Radar</a></p><p style="font-size:13px;color:#9aa4b5">Contact: <a href="mailto:${CONTACT}">${CONTACT}</a></p></main></body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex" } });
}

export function footerHtml(unsubUrl) {
  return `<hr style="border:0;border-top:1px solid #ddd;margin:24px 0"><p style="font-size:12px;color:#666;line-height:1.5">
You are receiving this because this address was entered on bitaxeradar.com. Links to sellers may be affiliate links: if you buy through one, Bitaxe Radar may earn a commission at no extra cost to you.<br>
${esc(POSTAL)}<br>Questions? Reply to this email or write <a href="mailto:${CONTACT}">${CONTACT}</a>.<br><a href="${esc(unsubUrl)}">Unsubscribe</a></p>`;
}
export function footerText(unsubUrl) {
  return `\n--\nYou are receiving this because this address was entered on bitaxeradar.com.\nLinks to sellers may be affiliate links: if you buy through one, Bitaxe Radar may earn a commission at no extra cost to you.\n${POSTAL}\nQuestions? Reply to this email or write ${CONTACT}\nUnsubscribe: ${unsubUrl}\n`;
}

// ---------- validation ----------
export function parseSubscription(input) {
  const email = String(input.email || "").trim().toLowerCase();
  if (email.length > 254 || !/^[^\s@<>()"',;:\\]+@[^\s@<>()"',;:\\]+\.[a-z]{2,}$/i.test(email)) return { error: "Please enter a valid email address." };
  let model = String(input.model == null || input.model === "" ? "any" : input.model).trim();
  if (MODELS.includes(model.toLowerCase())) model = model.toLowerCase();
  else if (!MODEL_FREE_TEXT.test(model)) return { error: "Please pick a miner from the list." };
  const price = Number(String(input.target_price ?? input.target ?? "").replace(/[$,\s]/g, ""));
  if (!Number.isFinite(price) || price < 1 || price > 100000) return { error: "Target price must be a number between 1 and 100000 (USD)." };
  return { email, model, price: Math.round(price * 100) / 100 };
}
async function readBody(request) {
  const ct = request.headers.get("Content-Type") || "";
  if (ct.includes("application/json")) { try { return await request.json(); } catch { return null; } }
  if (ct.includes("application/x-www-form-urlencoded") || ct.includes("multipart/form-data")) {
    try { return Object.fromEntries(await request.formData()); } catch { return null; }
  }
  return null;
}

// ---------- external APIs ----------
async function resend(env, method, path, body, extraHeaders) {
  const r = await fetch("https://api.resend.com" + path, {
    method, headers: { Authorization: "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json", "User-Agent": "bitaxe-radar-worker/1.0", ...(extraHeaders || {}) },
    body: body ? JSON.stringify(body) : undefined });
  let data = null; try { data = await r.json(); } catch {}
  return { ok: r.ok, status: r.status, data };
}
const contactPath = (email) => "/contacts/" + encodeURIComponent(email);

async function verifyTurnstile(env, token, ip) {
  if (!token) return false;
  const form = new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token });
  if (ip) form.set("remoteip", ip);
  try {
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
    return !!(await r.json()).success;
  } catch { return false; }
}

// ---------- handlers ----------
async function handleSubscribe(request, env) {
  const wantsJson = (request.headers.get("Content-Type") || "").includes("json") || (request.headers.get("Accept") || "").includes("application/json");
  const fail = (msg, status) => wantsJson ? json({ ok: false, error: msg }, status, request) : page("Something went wrong", `<p>${esc(msg)}</p>`, env, status);
  const input = await readBody(request);
  if (!input) return fail("Unsupported request.", 400);
  if (input.website) return wantsJson ? json({ ok: true, message: okMessage() }, 200, request) : page("Check your inbox", `<p>${esc(okMessage())}</p>`, env); // honeypot
  const ip = request.headers.get("CF-Connecting-IP") || "";
  if (env.RATE_LIMITER) {
    const { success } = await env.RATE_LIMITER.limit({ key: ip || "unknown" });
    if (!success) return fail("Too many attempts. Please wait a minute and try again.", 429);
  }
  if (String(input.type || "") === "newsletter") return handleNewsletterSubscribe(input, request, env, wantsJson, fail);
  const v = parseSubscription(input);
  if (v.error) return fail(v.error, 400);
  if (!(await verifyTurnstile(env, input["cf-turnstile-response"], ip))) return fail("Bot check failed. Please reload and try again.", 400);

  // Never touch an existing contact here (a stranger must not be able to re-subscribe/unsubscribe/alter someone).
  // Preferences travel inside the signed token and are applied only when the owner clicks the confirm link.
  const existing = await resend(env, "GET", contactPath(v.email));
  if (existing.status === 404) {
    const created = await resend(env, "POST", "/contacts", { email: v.email, unsubscribed: true, properties: { model: v.model, target_price: v.price } });
    if (!created.ok) { console.error("create contact failed", created.status, JSON.stringify(created.data)); return fail("Could not save your signup. Please try again later.", 502); }
  } else if (!existing.ok) {
    console.error("get contact failed", existing.status, JSON.stringify(existing.data));
    return fail("Could not save your signup. Please try again later.", 502);
  }

  const exp = Math.floor(Date.now() / 1000) + CONFIRM_TTL_SEC;
  const confirmUrl = `${env.PUBLIC_BASE}/confirm?t=${encodeURIComponent(await signToken({ t: "c", e: v.email, m: v.model, p: v.price, x: exp }, env.SIGNING_SECRET))}`;
  const unsubUrl = await unsubscribeUrl(env, v.email);
  const label = v.model === "any" ? "any tracked miner" : v.model;
  const html = `<div style="font:16px/1.5 system-ui,sans-serif;max-width:560px"><p>Confirm your Bitaxe Radar price alert:</p>
<p>Miner: <strong>${esc(label)}</strong><br>Alert me at or under: <strong>$${esc(v.price)}</strong> (USD, in stock)</p>
<p><a href="${esc(confirmUrl)}" style="background:#f7931a;color:#1a1100;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700">Yes, send me alerts</a></p>
<p style="font-size:13px;color:#555">This link works for 48 hours. If you did not ask for this, ignore this email and nothing will be sent.</p>${footerHtml(unsubUrl)}</div>`;
  const text = `Confirm your Bitaxe Radar price alert:\nMiner: ${label}\nAlert me at or under: $${v.price} (USD, in stock)\n\nConfirm: ${confirmUrl}\n\nThis link works for 48 hours. If you did not ask for this, ignore this email and nothing will be sent.\n${footerText(unsubUrl)}`;
  const sent = await resend(env, "POST", "/emails", { from: FROM, reply_to: CONTACT, to: [v.email], subject: "Confirm your Bitaxe Radar price alert", html, text,
    headers: { "List-Unsubscribe": `<${unsubUrl}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" } });
  if (!sent.ok) { console.error("send confirm failed", sent.status, JSON.stringify(sent.data)); return fail("Could not send the confirmation email. Please try again later.", 502); }
  return wantsJson ? json({ ok: true, message: okMessage() }, 200, request) : page("Check your inbox", `<p>${esc(okMessage())}</p>`, env);
}
const okMessage = () => "Almost done! If that address is valid, we just sent a confirmation email. Click the link in it to start alerts (check spam if you don't see it).";

// ---------- newsletter (Home Mining Weekly) ----------
const NL_NAME = "Home Mining Weekly";
export function parseNewsletter(input) {
  const email = String(input.email || "").trim().toLowerCase();
  if (email.length > 254 || !/^[^\s@<>()"',;:\\]+@[^\s@<>()"',;:\\]+\.[a-z]{2,}$/i.test(email)) return { error: "Please enter a valid email address." };
  return { email };
}
const nlOkMessage = () => "Almost done! If that address is valid, we just sent a confirmation email. Click the link in it to get Home Mining Weekly (check spam if you don't see it).";
async function nlUnsubscribeUrl(env, email) {
  return `${env.PUBLIC_BASE}/nl/unsubscribe?t=${encodeURIComponent(await signToken({ t: "nu", e: email }, env.SIGNING_SECRET))}`;
}
export function nlFooterHtml(unsubUrl) {
  return `<hr style="border:0;border-top:1px solid #ddd;margin:24px 0"><p style="font-size:12px;color:#666;line-height:1.5">
You are receiving this because this address was entered on bitaxeradar.com. Links to sellers may be affiliate links: if you buy through one, Bitaxe Radar may earn a commission at no extra cost to you.<br>
${esc(POSTAL)}<br>Questions? Reply to this email or write <a href="mailto:${CONTACT}">${CONTACT}</a>.<br><a href="${esc(unsubUrl)}">Unsubscribe from ${NL_NAME}</a></p>`;
}
async function handleNewsletterSubscribe(input, request, env, wantsJson, fail) {
  const v = parseNewsletter(input);
  if (v.error) return fail(v.error, 400);
  const ip = request.headers.get("CF-Connecting-IP") || "";
  if (!(await verifyTurnstile(env, input["cf-turnstile-response"], ip))) return fail("Bot check failed. Please reload and try again.", 400);
  // Same rule as alerts: never change an existing contact here. New contacts are created with unsubscribed:true
  // (no alerts) and newsletter "no"; the signed confirm link is what turns the newsletter on.
  const existing = await resend(env, "GET", contactPath(v.email));
  if (existing.status === 404) {
    const created = await resend(env, "POST", "/contacts", { email: v.email, unsubscribed: true, properties: { newsletter: "no" } });
    if (!created.ok) { console.error("nl create contact failed", created.status, JSON.stringify(created.data)); return fail("Could not save your signup. Please try again later.", 502); }
  } else if (!existing.ok) {
    console.error("nl get contact failed", existing.status, JSON.stringify(existing.data));
    return fail("Could not save your signup. Please try again later.", 502);
  }
  const exp = Math.floor(Date.now() / 1000) + CONFIRM_TTL_SEC;
  const confirmUrl = `${env.PUBLIC_BASE}/nl/confirm?t=${encodeURIComponent(await signToken({ t: "nc", e: v.email, x: exp }, env.SIGNING_SECRET))}`;
  const unsubUrl = await nlUnsubscribeUrl(env, v.email);
  const html = `<div style="font:16px/1.5 system-ui,sans-serif;max-width:560px"><p>Please confirm you want <strong>${NL_NAME}</strong> from Bitaxe Radar:</p>
<p>One short email a week with the best home miner prices we found, new miners and one plain-words explainer. Free, unsubscribe anytime.</p>
<p><a href="${esc(confirmUrl)}" style="background:#f7931a;color:#1a1100;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700">Yes, sign me up</a></p>
<p style="font-size:13px;color:#555">This link works for 48 hours. If you did not ask for this, ignore this email and nothing will be sent.</p>${nlFooterHtml(unsubUrl)}</div>`;
  const text = `Please confirm you want ${NL_NAME} from Bitaxe Radar:\nOne short email a week with the best home miner prices we found, new miners and one plain-words explainer. Free, unsubscribe anytime.\n\nConfirm: ${confirmUrl}\n\nThis link works for 48 hours. If you did not ask for this, ignore this email and nothing will be sent.\n${footerText(unsubUrl)}`;
  const sent = await resend(env, "POST", "/emails", { from: FROM, reply_to: CONTACT, to: [v.email], subject: `Confirm your ${NL_NAME} signup`, html, text,
    headers: { "List-Unsubscribe": `<${unsubUrl}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" } });
  if (!sent.ok) { console.error("nl send confirm failed", sent.status, JSON.stringify(sent.data)); return fail("Could not send the confirmation email. Please try again later.", 502); }
  return wantsJson ? json({ ok: true, message: nlOkMessage() }, 200, request) : page("Check your inbox", `<p>${esc(nlOkMessage())}</p>`, env);
}
async function handleNewsletterConfirm(url, env) {
  const p = await verifyToken(url.searchParams.get("t"), env.SIGNING_SECRET, "nc");
  if (!p) return page("Invalid link", "<p>This confirmation link is not valid. Please sign up again from the site.</p>", env, 400);
  if (p.expired) return page("Link expired", "<p>This confirmation link has expired (they last 48 hours). Please sign up again from the site.</p>", env, 410);
  const props = { newsletter: "yes", newsletter_at: new Date().toISOString() };
  let r = await resend(env, "PATCH", contactPath(p.e), { properties: props });   // properties only: alerts settings are left alone
  if (r.status === 404) r = await resend(env, "POST", "/contacts", { email: p.e, unsubscribed: true, properties: props });
  if (!r.ok) { console.error("nl confirm failed", r.status, JSON.stringify(r.data)); return page("Something went wrong", "<p>We could not confirm your signup right now. Please try the link again in a few minutes.</p>", env, 502); }
  return page("You're in!", `<p>Confirmed. <strong>${esc(p.e)}</strong> will get ${NL_NAME}. Every email has a one-click unsubscribe link.</p>`, env);
}
async function handleNewsletterUnsubscribe(url, env) {
  const p = await verifyToken(url.searchParams.get("t"), env.SIGNING_SECRET, "nu");
  if (!p || p.expired) return page("Invalid link", `<p>This unsubscribe link is not valid. Email ${CONTACT} and we will remove you by hand.</p>`, env, 400);
  const r = await resend(env, "PATCH", contactPath(p.e), { properties: { newsletter: "no" } });
  if (!r.ok && r.status !== 404) { console.error("nl unsubscribe failed", r.status, JSON.stringify(r.data)); return page("Something went wrong", "<p>We could not process that right now. Please try the link again in a few minutes.</p>", env, 502); }
  return page("Unsubscribed", `<p><strong>${esc(p.e)}</strong> will not get ${NL_NAME} any more. Any price alerts you set are not affected.</p>`, env);
}

async function unsubscribeUrl(env, email) {
  return `${env.PUBLIC_BASE}/unsubscribe?t=${encodeURIComponent(await signToken({ t: "u", e: email }, env.SIGNING_SECRET))}`;
}

async function handleConfirm(url, env) {
  const p = await verifyToken(url.searchParams.get("t"), env.SIGNING_SECRET, "c");
  if (!p) return page("Invalid link", "<p>This confirmation link is not valid. Please sign up again from the site.</p>", env, 400);
  if (p.expired) return page("Link expired", "<p>This confirmation link has expired (they last 48 hours). Please sign up again from the site.</p>", env, 410);
  const cur = await resend(env, "GET", contactPath(p.e));
  if (cur.ok && cur.data && cur.data.unsubscribed === false) {
    const pr = cur.data.properties || {};
    const same = String(pr.model && pr.model.value) === String(p.m) && Number(pr.target_price && pr.target_price.value) === Number(p.p);
    if (same) return doneConfirm(p, env); // idempotent: already confirmed with identical settings
  }
  const props = { model: p.m, target_price: p.p, last_alert_price: null, last_alert_at: null }; // reset dedupe state when settings change
  let r;
  if (cur.status === 404) r = await resend(env, "POST", "/contacts", { email: p.e, unsubscribed: false, properties: { model: p.m, target_price: p.p } });
  else r = await resend(env, "PATCH", contactPath(p.e), { unsubscribed: false, properties: props });
  if (!r.ok) { console.error("confirm failed", r.status, JSON.stringify(r.data)); return page("Something went wrong", "<p>We could not confirm your signup right now. Please try the link again in a few minutes.</p>", env, 502); }
  return doneConfirm(p, env);
}
function doneConfirm(p, env) {
  const label = p.m === "any" ? "any tracked miner" : p.m;
  return page("You're in!", `<p>Confirmed. We'll email <strong>${esc(p.e)}</strong> when <strong>${esc(label)}</strong> is in stock at or under <strong>$${esc(p.p)}</strong>.</p>
<p>You can unsubscribe from any alert email with one click.</p>`, env);
}

async function handleUnsubscribe(url, env) {
  const p = await verifyToken(url.searchParams.get("t"), env.SIGNING_SECRET, "u");
  if (!p || p.expired) return page("Invalid link", `<p>This unsubscribe link is not valid. Email ${CONTACT} and we will remove you by hand.</p>`, env, 400);
  const r = await resend(env, "PATCH", contactPath(p.e), { unsubscribed: true });
  if (!r.ok && r.status !== 404) { console.error("unsubscribe failed", r.status, JSON.stringify(r.data)); return page("Something went wrong", "<p>We could not process that right now. Please try the link again in a few minutes.</p>", env, 502); }
  return page("Unsubscribed", `<p><strong>${esc(p.e)}</strong> will not get any more alerts. Sorry to see you go.</p>`, env);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(request) });
      if (url.pathname === "/health") return new Response("ok");
      if (url.pathname === "/subscribe" && request.method === "POST") {
        const origin = request.headers.get("Origin");
        if (origin && !ALLOWED_ORIGINS.includes(origin)) return json({ ok: false, error: "Origin not allowed." }, 403, request);
        return await handleSubscribe(request, env);
      }
      if (url.pathname === "/confirm" && request.method === "GET") return await handleConfirm(url, env);
      if (url.pathname === "/nl/confirm" && request.method === "GET") return await handleNewsletterConfirm(url, env);
      if (url.pathname === "/nl/unsubscribe" && (request.method === "GET" || request.method === "POST")) return await handleNewsletterUnsubscribe(url, env);
      if (url.pathname === "/unsubscribe" && (request.method === "GET" || request.method === "POST")) return await handleUnsubscribe(url, env);
      return new Response("Not found", { status: 404 });
    } catch (e) {
      console.error("unhandled", e && e.stack || e);
      return new Response("Server error", { status: 500 });
    }
  },
};
