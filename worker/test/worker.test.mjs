// Run: node test/worker.test.mjs   (Node >= 20, no deps; mocks Resend + Turnstile fetch calls)
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const SCRIPTS = fileURLToPath(new URL("../../scripts", import.meta.url));
import worker, { signToken, verifyToken, parseSubscription } from "../src/index.js";

const env = { RESEND_API_KEY: "re_x", SIGNING_SECRET: "test-secret", TURNSTILE_SECRET: "ts", PUBLIC_BASE: "https://w.example", SITE_URL: "https://bitaxeradar.com" };
const contacts = new Map(); const sent = []; let turnstileOk = true;
globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url), m = init.method || "GET";
  const res = (code, obj) => new Response(JSON.stringify(obj), { status: code });
  if (u.host === "challenges.cloudflare.com") return res(200, { success: turnstileOk });
  const body = init.body ? JSON.parse(init.body) : null;
  if (u.pathname === "/emails") { sent.push(body); return res(200, { id: "e1" }); }
  if (u.pathname === "/contacts" && m === "POST") {
    if (contacts.has(body.email)) return res(409, { message: "exists" });
    contacts.set(body.email, { email: body.email, unsubscribed: body.unsubscribed, properties: Object.fromEntries(Object.entries(body.properties || {}).map(([k, v]) => [k, { value: v }])) });
    return res(201, { id: "c1" });
  }
  const email = decodeURIComponent(u.pathname.split("/")[2] || "");
  if (m === "GET") return contacts.has(email) ? res(200, contacts.get(email)) : res(404, { message: "nf" });
  if (m === "PATCH") {
    if (!contacts.has(email)) return res(404, {}); const c = contacts.get(email);
    if ("unsubscribed" in body) c.unsubscribed = body.unsubscribed;
    for (const [k, v] of Object.entries(body.properties || {})) c.properties[k] = { value: v };
    return res(200, { id: "c1" });
  }
  throw new Error("unexpected " + m + " " + url);
};
const post = (obj, extra = {}) => worker.fetch(new Request("https://w.example/subscribe", { method: "POST", headers: { "Content-Type": "application/json", Origin: "https://bitaxeradar.com", ...extra }, body: JSON.stringify({ "cf-turnstile-response": "tok", ...obj }) }), env);
const tokenFrom = (html, path) => new URL(html.match(new RegExp(`https://w\\.example/${path}\\?t=[^"\\s<]+`))[0].replace(/&amp;/g, "&")).searchParams.get("t");

// validation
assert.equal(parseSubscription({ email: "a@b.co", model: "bitaxe-gamma", target_price: "$120" }).price, 120);
assert.ok(parseSubscription({ email: "nope", target_price: 5 }).error);
assert.ok(parseSubscription({ email: "a@b.co", target_price: 0 }).error);
assert.ok(parseSubscription({ email: "a@b.co", target_price: 100001 }).error);
assert.ok(parseSubscription({ email: "a@b.co", model: "<script>", target_price: 5 }).error);
assert.equal(parseSubscription({ email: "A@B.co", model: "", target_price: 5 }).model, "any");

// subscribe -> pending contact + confirmation email
let r = await post({ email: "Alice@Example.com", model: "bitaxe-gamma", target_price: 120 });
assert.equal(r.status, 200); assert.equal(r.headers.get("Access-Control-Allow-Origin"), "https://bitaxeradar.com");
assert.equal(contacts.get("alice@example.com").unsubscribed, true);
assert.equal(sent.length, 1); assert.equal(sent[0].from, "Bitaxe Radar <alerts@bitaxeradar.com>");
assert.match(sent[0].html, //); assert.match(sent[0].html, /affiliate/); assert.match(sent[0].headers["List-Unsubscribe"], /unsubscribe\?t=/);
// rejects: bad origin, failed turnstile, bad email
assert.equal((await post({ email: "x@y.co", target_price: 5 }, { Origin: "https://evil.example" })).status, 403);
turnstileOk = false; assert.equal((await post({ email: "x@y.co", target_price: 5 })).status, 400); turnstileOk = true;
assert.equal((await post({ email: "bad", target_price: 5 })).status, 400);
assert.equal(sent.length, 1);
// CORS preflight
r = await worker.fetch(new Request("https://w.example/subscribe", { method: "OPTIONS", headers: { Origin: "https://yostoo.github.io" } }), env);
assert.equal(r.status, 204); assert.equal(r.headers.get("Access-Control-Allow-Origin"), "https://yostoo.github.io");
// form-encoded
r = await worker.fetch(new Request("https://w.example/subscribe", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" }, body: "email=bob%40example.com&model=any&target_price=99&cf-turnstile-response=t" }), env);
assert.equal(r.status, 200); assert.equal(sent.length, 2);

// confirm (idempotent), then settings
const ct = tokenFrom(sent[0].html, "confirm");
const confirm = (t) => worker.fetch(new Request("https://w.example/confirm?t=" + encodeURIComponent(t)), env);
r = await confirm(ct); assert.equal(r.status, 200); assert.match(await r.text(), /Confirmed\./);
assert.equal(contacts.get("alice@example.com").unsubscribed, false);
assert.equal(contacts.get("alice@example.com").properties.model.value, "bitaxe-gamma");
contacts.get("alice@example.com").properties.last_alert_price = { value: 119.99 };
r = await confirm(ct); assert.equal(r.status, 200);
assert.equal(contacts.get("alice@example.com").properties.last_alert_price.value, 119.99, "second click must not reset dedupe state");
// re-subscribing an existing confirmed contact must NOT unsubscribe or alter them until the link is clicked
await post({ email: "alice@example.com", model: "any", target_price: 50 });
assert.equal(contacts.get("alice@example.com").unsubscribed, false);
assert.equal(contacts.get("alice@example.com").properties.target_price.value, 120);
await confirm(tokenFrom(sent[sent.length - 1].html, "confirm"));
assert.equal(contacts.get("alice@example.com").properties.target_price.value, 50);
assert.equal(contacts.get("alice@example.com").properties.last_alert_price.value, null, "changed settings reset dedupe state");
// tampered / expired / wrong-type tokens
assert.equal((await confirm(ct.slice(0, -2) + "xx")).status, 400);
const expired = await signToken({ t: "c", e: "a@b.co", m: "any", p: 5, x: 1 }, env.SIGNING_SECRET);
assert.equal((await confirm(expired)).status, 410);
assert.equal((await confirm(await signToken({ t: "u", e: "a@b.co" }, env.SIGNING_SECRET))).status, 400);
assert.equal((await confirm(await signToken({ t: "c", e: "a@b.co", m: "any", p: 5, x: 9e9 }, "other-secret"))).status, 400);

// unsubscribe: GET link from email, POST one-click, and a token minted by the Python script
const ut = tokenFrom(sent[0].html, "unsubscribe");
r = await worker.fetch(new Request("https://w.example/unsubscribe?t=" + encodeURIComponent(ut)), env); assert.equal(r.status, 200);
assert.equal(contacts.get("alice@example.com").unsubscribed, true);
contacts.get("bob@example.com").unsubscribed = false;
const pyTok = execFileSync("python3", ["-c", `import sys;sys.path.insert(0,${JSON.stringify(SCRIPTS)});import send_alerts as s;print(s.sign_token({"t":"u","e":"bob@example.com"},"test-secret"))`]).toString().trim();
assert.ok(await verifyToken(pyTok, env.SIGNING_SECRET, "u"), "python-signed token must verify in the worker");
r = await worker.fetch(new Request("https://w.example/unsubscribe?t=" + encodeURIComponent(pyTok), { method: "POST", body: "List-Unsubscribe=One-Click" }), env);
assert.equal(r.status, 200); assert.equal(contacts.get("bob@example.com").unsubscribed, true);
console.log("worker tests: all passed");

// ---------- newsletter ----------
{
  const before = sent.length;
  // existing confirmed alert contact: newsletter signup + confirm must not touch alerts
  contacts.set("carol@example.com", { email: "carol@example.com", unsubscribed: false, properties: { model: { value: "bitaxe-gamma" }, target_price: { value: 80 } } });
  let r = await post({ type: "newsletter", email: "Carol@Example.com" });
  assert.equal(r.status, 200);
  const c0 = contacts.get("carol@example.com");
  assert.equal(c0.unsubscribed, false); assert.equal(c0.properties.target_price.value, 80); assert.equal(c0.properties.newsletter, undefined);
  const m = sent[sent.length - 1]; assert.equal(sent.length, before + 1);
  assert.equal(m.subject, "Confirm your Home Mining Weekly signup"); assert.match(m.html, //); assert.match(m.headers["List-Unsubscribe"], /nl\/unsubscribe\?t=/);
  const t = tokenFrom(m.html, "nl/confirm");
  assert.equal((await worker.fetch(new Request("https://w.example/confirm?t=" + encodeURIComponent(t)), env)).status, 400); // nc token can't confirm an alert
  r = await worker.fetch(new Request("https://w.example/nl/confirm?t=" + encodeURIComponent(t)), env); assert.equal(r.status, 200);
  const c1 = contacts.get("carol@example.com");
  assert.equal(c1.properties.newsletter.value, "yes"); assert.equal(c1.unsubscribed, false); assert.equal(c1.properties.model.value, "bitaxe-gamma"); assert.equal(c1.properties.target_price.value, 80);
  // newsletter unsubscribe leaves alerts on
  const u = tokenFrom(m.html, "nl/unsubscribe");
  r = await worker.fetch(new Request("https://w.example/nl/unsubscribe?t=" + encodeURIComponent(u), { method: "POST" }), env); assert.equal(r.status, 200);
  assert.equal(contacts.get("carol@example.com").properties.newsletter.value, "no"); assert.equal(contacts.get("carol@example.com").unsubscribed, false);
  // brand new address: created with alerts off and no miner/price
  r = await post({ type: "newsletter", email: "dan@example.com" }); assert.equal(r.status, 200);
  const d = contacts.get("dan@example.com"); assert.equal(d.unsubscribed, true); assert.equal(d.properties.newsletter.value, "no"); assert.equal(d.properties.target_price, undefined);
  await worker.fetch(new Request("https://w.example/nl/confirm?t=" + encodeURIComponent(tokenFrom(sent[sent.length - 1].html, "nl/confirm"))), env);
  assert.equal(contacts.get("dan@example.com").properties.newsletter.value, "yes"); assert.equal(contacts.get("dan@example.com").unsubscribed, true);
  // turnstile + email checks apply
  turnstileOk = false; assert.equal((await post({ type: "newsletter", email: "e@example.com" })).status, 400); turnstileOk = true;
  assert.equal((await post({ type: "newsletter", email: "nope" })).status, 400);
  console.log("newsletter tests ok");
}
