"""Black Friday push: the tracker covers every miner type in groups, and the site-wide banner shows only Nov 20-Dec 1.
Page checks run after `python3 build_site.py`; the banner date logic is loaded straight from build_site.py."""
import ast
import html as H
import json
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
NAMES = {"BF_DATES", "BF_BANNER", "BF_PATH", "bf_today", "bf_banner", "esc"}


def bf_funcs():
    """Load just the banner helpers (importing build_site.py would build the whole site)."""
    tree = ast.parse((ROOT / "build_site.py").read_text())
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in NAMES)
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in NAMES for t in n.targets))]
    ns = {"datetime": datetime, "timedelta": timedelta, "_html": H, "GEN": datetime(2026, 10, 25, tzinfo=timezone.utc)}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "build_site_bf", "exec"), ns)
    return ns


def utc(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


class Banner(unittest.TestCase):
    def setUp(self):
        self.b = bf_funcs()["bf_banner"]

    def test_hidden_outside_window(self):
        for t in [utc(2026, 10, 25), utc(2026, 11, 10), utc(2026, 11, 19, 23), utc(2026, 11, 20, 4),  # Nov 20 04:00 UTC is still Nov 19 in the US
                  utc(2026, 12, 2, 6), utc(2026, 12, 25), utc(2027, 11, 25)]:
            self.assertEqual(self.b(t), "", t)

    def test_shown_inside_window_and_links_tracker(self):
        d = utc(2026, 11, 20, 6)
        while d <= utc(2026, 12, 2, 4):
            out = self.b(d)
            self.assertIn('class="bf-banner"', out, d)
            self.assertIn('href="/bitaxe-black-friday/"', out, d)
            self.assertIn("lowest price we've logged so far", H.unescape(out), d)
            self.assertNotIn("all-time", out.lower())
            d += timedelta(hours=6)

    def test_message_follows_the_calendar(self):
        self.assertIn("in 7 days", self.b(utc(2026, 11, 20)))
        self.assertIn("tomorrow", self.b(utc(2026, 11, 26)))
        self.assertIn("Black Friday weekend is on", self.b(utc(2026, 11, 27)))
        self.assertIn("Black Friday weekend is on", self.b(utc(2026, 11, 29)))
        self.assertIn("Cyber Monday", self.b(utc(2026, 11, 30)))
        self.assertIn("run through today", self.b(utc(2026, 12, 1)))


class TrackerPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = SITE / "bitaxe-black-friday" / "index.html"
        if not p.exists():
            raise unittest.SkipTest("run build_site.py first")
        cls.html = p.read_text()
        cls.latest = json.loads((ROOT / "data" / "latest.json").read_text())

    def test_three_groups_cover_every_live_miner(self):
        for g in ("bf-bitaxe", "bf-home", "bf-heater"):
            self.assertIn(f'id="{g}"', self.html)
        tracked = {o["model"] for o in self.latest["offers"]} - {"bitaxe-supra", "bitaxe-ultra"}
        main = self.html.split('id="h-a"')[0]
        for mid in tracked:
            self.assertIn(f'href="/models/{mid}/"', main, mid)

    def test_groups_are_right(self):
        def group(gid):
            return self.html.split(f'id="bf-{gid}"')[1].split("</section>")[0]
        for mid in ("bitaxe-gamma", "nerdqaxe-pp"):
            self.assertIn(f'/models/{mid}/', group("bitaxe"))
        for mid in ("avalon-mini-3", "avalon-q", "heatbit-maxi", "heatbit-bitwater"):
            self.assertIn(f'/models/{mid}/', group("heater"))
            self.assertNotIn(f'/models/{mid}/', group("bitaxe"))
        self.assertIn("/models/avalon-nano-3s/", group("home"))

    def test_low_column_matches_logged_history(self):
        """Every 'lowest we've logged' value must be an in-stock price that is actually in data/history.json (USD rows)."""
        hist = json.loads((ROOT / "data" / "history.json").read_text())
        offers = self.latest["offers"]
        for mid in ("bitaxe-gamma", "nerdqaxe-pp", "avalon-q"):
            row = re.search(rf'<tr><td[^>]*><a href="/models/{mid}/">.*?</tr>', self.html).group(0)
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row)
            m = re.match(r"\$([\d,]+\.\d\d)", cells[3])
            if not m:
                continue
            lo = float(m.group(1).replace(",", ""))
            logged = [pt["price"] for o in offers if o["model"] == mid and o["currency"] == "USD" for pt in hist.get(o["id"], []) if pt.get("in_stock")]
            if logged:
                self.assertAlmostEqual(lo, min(logged), places=2, msg=mid)

    def test_wording_and_links(self):
        self.assertIn("lowest in-stock price we&#x27;ve logged so far".replace("&#x27;", "'"), H.unescape(self.html))
        self.assertNotIn("all-time", self.html.lower())
        self.assertIn('href="/heater-miners/"', self.html)
        for page in ("deals", "in-stock", "price-per-th"):   # Black Friday tab on every deals page
            self.assertIn('href="/bitaxe-black-friday/"', re.search(r'aria-label="Deals filter">(.*?)</nav>', (SITE / page / "index.html").read_text()).group(1), page)

    def test_phone_cards_and_desktop_columns(self):
        """Phones get one stacked card per miner (no sideways scroll to reach Buy); desktop gets a short low-price header."""
        css = (SITE / "style.css").read_text()
        m = re.search(r"@media \(max-width:640px\)\{(.*?)\n\}", css, re.S)
        self.assertIsNotNone(m, "missing the <=640px Black Friday card block")
        phone = m.group(1)
        for rule in (".bf-table thead{display:none}", ".bf-table tr{display:grid", "content:attr(data-label)",
                     ".bf-wrap{overflow-x:visible}", ".bf-table td.bf-buy .btn{display:block;width:100%"):
            self.assertIn(rule, phone, rule)
        self.assertIn(".bf-table td.bf-miner,.bf-table td.bf-shop{white-space:nowrap}", css)
        self.assertEqual(self.html.count('<table class="bf-table">'), self.html.count('class="bf-group"'))
        rows = re.findall(r'<tr><td class="bf-miner">.*?</tr>', self.html)
        self.assertGreaterEqual(len(rows), 20)
        for row in rows:
            for cls, label in (("bf-now", "Cheapest in stock"), ("bf-shop", "Shop"), ("bf-low", "Lowest we&#x27;ve logged"), ("bf-vs", "Today vs that low")):
                self.assertRegex(H.unescape(row), rf'class="[^"]*{cls}" data-label="{H.unescape(label)}"')
            self.assertIn('class="bf-buy"', row)
        self.assertIn("Lowest we've logged</th>", H.unescape(self.html))
        self.assertNotIn("all-time", css.lower())

    def test_banner_matches_build_date(self):
        """The built pages carry the banner exactly when the data date is in the window (today, before Nov 20, they don't)."""
        gen = datetime.strptime(self.latest["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        want = bf_funcs()["bf_banner"](gen) != ""
        for page in ("index.html", "deals/index.html", "in-stock/index.html", "price-per-th/index.html"):
            self.assertEqual('class="bf-banner"' in (SITE / page).read_text(), want, page)


if __name__ == "__main__":
    unittest.main()
