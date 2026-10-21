"""Run: python3 -m unittest discover -s tests -v   (stdlib only, no network except a local mock Resend server)."""
import json, os, sys, threading, unittest, subprocess, urllib.parse
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import send_alerts as sa

LATEST = json.loads((ROOT / "tests/fixtures/latest.json").read_text())
CONTACTS = json.loads((ROOT / "tests/fixtures/contacts.json").read_text())
NOW = sa.parse_iso("2026-10-16T16:00:00Z")
AFF = {"powermining": "ref=bitaxeradar"}

def run(contacts=CONTACTS, **kw):
    return {r["email"]: r for r in sa.run(LATEST, contacts, aff=AFF, now=NOW, dry_run=True, max_sends=90, **kw)}

class Matching(unittest.TestCase):
    def test_actions(self):
        r = run()
        send = {e for e, x in r.items() if x["action"] == "WOULD SEND"}
        self.assertEqual(send, {f"{n}@example.com" for n in "alice bob carol frank gina ivan kim".split()})
        self.assertIn("unsubscribed", r["dave@example.com"]["reason"])
        self.assertIn("dedupe", r["erin@example.com"]["reason"])
        self.assertIn("no in-stock", r["hank@example.com"]["reason"])
        self.assertIn("unrecognised", r["zed@example.com"]["reason"])
    def test_us_first_and_cheapest(self):
        r = run()
        self.assertEqual(r["alice@example.com"]["offer"], "solosatoshi:bitaxe-gamma-duo")   # cheapest in-stock US under $130
        self.assertEqual(r["bob@example.com"]["offer"], "powermining:nerdaxe-gamma")          # EU only
        self.assertEqual(r["ivan@example.com"]["offer"], "bitcoinmerch:nerdaxe-gaia")         # US wins over cheaper EU
        self.assertEqual(r["ivan@example.com"]["alt"], "powermining:nerdaxe-gamma")           # EU shown as alt
    def test_out_of_stock_ignored(self):   # solosatoshi gamma $67 is out of stock
        m = sa.find_match({"model": "bitaxe-gamma", "target_price": 100}, LATEST, NOW)
        self.assertIsNone(m)
    def test_stale_offer_ignored(self):
        self.assertIsNone(sa.find_match({"model": "bitaxe-gamma", "target_price": 125}, LATEST, NOW + timedelta(hours=49)))
    def test_dedupe_rules(self):
        p = {"last_alert_price": 100, "last_alert_at": "2026-10-15T00:00:00Z"}
        self.assertFalse(sa.should_alert(p, 100.0, NOW)[0])
        self.assertFalse(sa.should_alert(p, 105.0, NOW)[0])
        self.assertTrue(sa.should_alert(p, 99.0, NOW)[0])
        self.assertTrue(sa.should_alert(p, 105.0, NOW + timedelta(days=7))[0])
        self.assertTrue(sa.should_alert({}, 105.0, NOW)[0])
    def test_cap(self):
        res = sa.run(LATEST, CONTACTS, aff=AFF, now=NOW, dry_run=True, max_sends=3)
        self.assertEqual(sum(r["action"] == "WOULD SEND" for r in res), 3)
        self.assertEqual(sum(r["action"] == "defer" for r in res), 4)
    def test_affiliate_and_disclosure(self):
        c = next(x for x in CONTACTS if x["email"] == "bob@example.com")
        props = sa.contact_props(c); m = sa.find_match(props, LATEST, NOW)
        s, h, t = sa.build_email("bob@example.com", props, m, LATEST, AFF, "https://x/unsubscribe?t=1")
        self.assertIn("ref=bitaxeradar", t); self.assertIn("affiliate link", t)
        self.assertIn(sa.POSTAL, h); self.assertIn("Unsubscribe", h); self.assertIn("VAT", t)
    def test_affiliate_map_parsed_from_app_js(self):
        self.assertEqual(sa.load_affiliates(ROOT / "site/app.js").get("powermining"), "ref=bitaxeradar")

class Mock(BaseHTTPRequestHandler):
    log = []
    def log_message(self, *a): pass
    def _send(self, code, obj, headers=None):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/contacts":
            ids = [c["id"] for c in CONTACTS]; start = ids.index(q["after"][0]) + 1 if "after" in q else 0
            page = CONTACTS[start:start + 5]   # tiny pages to force pagination
            return self._send(200, {"object": "list", "has_more": start + 5 < len(CONTACTS),
                                    "data": [{k: v for k, v in c.items() if k != "properties"} for c in page]})
        cid = u.path.split("/")[-1]
        c = next((c for c in CONTACTS if c["id"] == cid), None)
        self._send(200 if c else 404, c or {"message": "not found"})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Mock.log.append(("POST", self.path, body, self.headers.get("Idempotency-Key")))
        self._send(200, {"id": "email-1"}, {"x-resend-daily-quota": str(len([l for l in Mock.log if l[1] == "/emails"]))})
    def do_PATCH(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Mock.log.append(("PATCH", self.path, body, None)); self._send(200, {"id": "x"})

class LiveAgainstMock(unittest.TestCase):
    def test_live_flow(self):
        srv = HTTPServer(("127.0.0.1", 0), Mock); threading.Thread(target=srv.serve_forever, daemon=True).start()
        Mock.log.clear()
        env = dict(os.environ, RESEND_API_KEY="re_test", SIGNING_SECRET="s", PUBLIC_BASE="https://w.example", POSTAL_ADDRESS="Bitaxe Radar, PO Box 1, Testville, IN 00000",
                   RESEND_API_BASE=f"http://127.0.0.1:{srv.server_port}")
        out = subprocess.run([sys.executable, str(ROOT / "scripts/send_alerts.py"), "--latest", str(ROOT / "tests/fixtures/latest.json"),
                              "--now", "2026-10-16T16:00:00Z"], env=env, capture_output=True, text=True)
        srv.shutdown()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        emails = [l for l in Mock.log if l[1] == "/emails"]; patches = [l for l in Mock.log if l[0] == "PATCH"]
        self.assertEqual(len(emails), 7); self.assertEqual(len(patches), 7)       # 12 contacts across 3 pages; 7 sent; state saved for each
        self.assertTrue(all("List-Unsubscribe" in e[2]["headers"] and e[3] for e in emails))
        self.assertEqual(patches[0][2]["properties"]["last_alert_price"], 111.69)
        self.assertNotIn("dave@example.com", json.dumps([e[2]["to"] for e in emails]))

if __name__ == "__main__":
    unittest.main()
