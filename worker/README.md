# Bitaxe Radar - email alerts (Cloudflare Worker + Resend)

Double opt-in price-drop alerts. Nothing here is deployed yet; no accounts/keys are baked in.

```
visitor -> site form -> POST /subscribe (Worker: validate + Turnstile)
        -> Resend contact created (unsubscribed:true) + confirmation email with signed link
click   -> GET /confirm?t=...  (Worker flips contact to unsubscribed:false, stores model + target_price)
every 6h-> GitHub Actions: scripts/send_alerts.py reads data/latest.json, lists contacts from Resend, emails matches
```

Everything is stateless: the confirm/unsubscribe links are HMAC-signed (`SIGNING_SECRET`), and alert dedupe state lives on the
Resend contact (`last_alert_price`, `last_alert_at`). Nothing to commit back to the repo.

## 0. What you need (all free)
* Resend account with `bitaxeradar.com` **verified** and a sending API key (see note on key permissions below)
* Cloudflare account (free) with Workers + Turnstile
* Node 18+ (for `npx wrangler`); `gh` CLI optional for repo secrets

## 1. One-time Resend setup: contact properties
Properties must exist *before* a contact can be written with them. Run once (replace the key):

```bash
export RESEND_API_KEY=re_xxxxxxxx   # needs permission to manage contacts (a "Full access" key)
for body in \
  '{"key":"model","type":"string","fallback_value":"any"}' \
  '{"key":"target_price","type":"number"}' \
  '{"key":"last_alert_price","type":"number"}' \
  '{"key":"last_alert_at","type":"string"}'; do
  curl -sS -X POST https://api.resend.com/contact-properties \
    -H "Authorization: Bearer $RESEND_API_KEY" -H "Content-Type: application/json" -d "$body"; echo
done
```
(Property keys: max 50 chars, alphanumeric + underscore; types are only `string` or `number`.)
Same thing in the dashboard: Audience/Contacts -> Properties -> New property.

## 2. Cloudflare Turnstile
Dashboard -> Turnstile -> Add widget. Hostnames: `bitaxeradar.com`, `yostoo.github.io`. Mode: Managed.
You get a **site key** (public, goes into `site/app.js`) and a **secret key** (Worker secret).
For local tests Cloudflare's dummy pair always passes: site key `1x00000000000000000000AA`, secret `1x0000000000000000000000000000000AA`.

## 3. Deploy the Worker
```bash
cd worker
npx wrangler login                       # opens a browser; approve
openssl rand -hex 32                     # generate a SIGNING_SECRET, save it (you also need it for GitHub below)
npx wrangler secret put SIGNING_SECRET
npx wrangler secret put RESEND_API_KEY
npx wrangler secret put TURNSTILE_SECRET
npx wrangler deploy                      # prints https://bitaxe-radar-alerts.<your-subdomain>.workers.dev
```

### Public URL (`PUBLIC_BASE`) - pick one
* **A. workers.dev URL (easiest, no DNS change).** Set `PUBLIC_BASE` in `wrangler.toml` to the URL `wrangler deploy` printed (no trailing slash), then `npx wrangler deploy` again.
  Confirm/unsubscribe links in emails will show the workers.dev host.
* **B. `subscribe.bitaxeradar.com`.** A Worker *custom domain* requires the zone to be on Cloudflare, but DNS for bitaxeradar.com is at Porkbun.
  You would have to move the whole zone to Cloudflare (change nameservers at Porkbun and re-create the GitHub Pages A/CNAME records, the Resend SPF/DKIM/MX records and the Brevo leftovers *before* switching). Only worth it later.
  Then uncomment the `[[routes]]` block in `wrangler.toml` and redeploy.

`PUBLIC_BASE` is used in the links inside emails, so it must be the URL that actually serves the Worker.
Test: `curl https://<PUBLIC_BASE host>/health` -> `ok`.

### Optional rate limit
`wrangler.toml` binds `RATE_LIMITER` (5 requests / 60 s per IP per Cloudflare location). Requires Wrangler >= 4.36. If your Wrangler complains, delete that block; the Worker skips the check when the binding is absent.

## 4. Point the site at the Worker
Edit the three constants at the top of `site/app.js`:
```js
var WORKER_URL = "<PUBLIC_BASE>/subscribe";
var TURNSTILE_SITEKEY = "<site key from step 2>";
var SIGNUP_ENABLED = true;
```
Until `SIGNUP_ENABLED` is `true` the form is disabled and says "launching soon" (honest placeholder). Commit + push -> GitHub Pages redeploys.

## 5. Wire up the GitHub Action (sends the alerts)
`.github/workflows/collect.yml` already has a `send-alerts` step; it does nothing until these exist:
```bash
gh secret set RESEND_API_KEY   -R YoStoo/bitaxe-radar
gh secret set SIGNING_SECRET   -R YoStoo/bitaxe-radar     # SAME value as the Worker's
gh variable set PUBLIC_BASE    -R YoStoo/bitaxe-radar --body "https://..."   # same as wrangler.toml
```
First real run: trigger the workflow manually, or run locally with `--dry-run` (below).

## 6. End-to-end test
1. Sign up with your own email on the live site -> you get a confirmation email -> click it -> "You're in".
2. In the Resend dashboard the contact should show `unsubscribed: false` and properties `model`, `target_price`.
3. Dry run against real contacts (sends nothing, writes nothing):
   ```bash
   RESEND_API_KEY=re_xxx python3 scripts/send_alerts.py --dry-run
   ```
   (Live-API dry run still lists contacts from Resend; for a fully offline run use `--contacts-fixture tests/fixtures/contacts.json`.)
4. Set your target above the current price, run without `--dry-run` once (needs `SIGNING_SECRET` and `PUBLIC_BASE` too), check the email + the unsubscribe link.

## Tests
```bash
python3 -m unittest discover -s tests -v     # matching, dedupe, cap, plus a live-flow run against a local mock of Resend
node worker/test/worker.test.mjs             # Worker: validation, double opt-in, idempotency, tokens (mocked fetch)
```

## Behaviour notes
* **Matching:** contact's `model` (id, `any`, or free text matched against model names) and `target_price` (USD). Offer must be `in_stock`, not `stale`, checked <= 48 h ago. US (USD) sellers win; a EU seller is used only if no US offer matches (shown as "approx USD, excl. shipping/duties/VAT"); the cheapest offer from the other region is added as an extra line.
* **Dedupe:** a contact is alerted again only if the best price is lower than `last_alert_price`, or `last_alert_at` is >= 7 days old. State is written to the contact right after each successful send. Re-confirming with *changed* settings resets the state.
* **Caps:** at most 90 emails per run, and the script stops as soon as Resend's `x-resend-daily-quota` response header shows >= 90 used today (free plan = 100/day, shared with confirmation emails). Contacts not reached are simply retried next run.
* **Unsubscribe:** signed link in every email footer + `List-Unsubscribe` / `List-Unsubscribe-Post` (one-click, RFC 8058) headers. Unsubscribe links never expire.
* **Existing contacts:** `/subscribe` never modifies an existing contact (so a stranger can't unsubscribe/alter someone); new preferences are carried in the signed token and applied only when the owner clicks confirm.

## Uncertain / verify on first deploy
* Resend's docs list `properties` on create/update contact and `unsubscribed`; they don't document the error for a *duplicate* contact or for unknown properties, so the Worker does GET-before-create and logs failures (`npx wrangler tail`).
* Resend's list-contacts response (per docs) does not include properties, so the script does one GET per confirmed contact (rate-limited to ~6/s; 10/s is Resend's default). Fine for hundreds of subscribers; revisit at thousands.
* Whether `x-resend-daily-quota` is returned on every response/plan is per Resend docs ("free plan users"); the 90/run cap is the backstop.
* Email link scanners (some corporate filters) may "click" the confirm link and confirm the address automatically - a known double-opt-in weakness. A POST-button confirm page would fix it if it shows up.
* Resend API key: contacts endpoints need a full-access key, and the same key is stored as a GitHub secret. Keep the repo's secrets private; rotate if leaked.
* A stale-but-valid confirm link (<= 48 h) re-subscribes someone who unsubscribed in between.
