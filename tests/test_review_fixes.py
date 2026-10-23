"""Checks for the fixes from the fresh-eyes site review. Run after `python3 build_site.py`."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def read(path):
    return (SITE / path.strip("/") / "index.html").read_text() if path != "/" else (SITE / "index.html").read_text()


def home_cards():
    return read("/").split('id="miners"')[1].split("</section>")[0]


class ReviewFixes(unittest.TestCase):
    def test_cards_have_neutral_cost_line_not_red_verdict(self):
        for p in ["/", "/miners/", "/solo-miners/", "/heater-miners/", "/find-my-miner/"]:
            h = read(p)
            for card in re.findall(r'<article class="card[^"]*".*?</article>', h, re.S):
                self.assertNotIn("Costs about", card, p)
                self.assertNotIn('data-calc="net"', card, p)
        self.assertRegex(home_cards(), r'class="cardline"[^>]*>≈<span data-calc="power"[^>]*>\$[\d.,]+</span>/mo power · 1 in [\d,]+/yr block odds')

    def test_pool_comparison_only_on_model_pages_and_labelled(self):
        g = read("/models/bitaxe-gamma/")
        if 'id="h-earn"' not in g:
            self.skipTest("network inputs stale; estimates hidden by design")
        self.assertIn("<small>If you pool mine:</small>", g)
        self.assertIn("If you pool mine", g.split('id="h-earn"')[1].split("</section>")[0])

    def test_heater_economics_use_mining_watts(self):
        t = read("/models/heatbit-trio/")
        if 'id="h-earn"' not in t:
            self.skipTest("network inputs stale; estimates hidden by design")
        self.assertNotIn('data-w="1500', t)                      # heater-mode draw never feeds the math
        self.assertIn('data-w="400.0"', t)
        rate = float(re.search(r"Break-even power price: <b>about \$([\d.]+)/kWh", t).group(1))
        self.assertGreater(rate, 0.02)                            # was a nonsensical $0.008 when 1,500 W was used
        self.assertIn("net ≈", t)
        self.assertIn("isn't counted here", t)
        self.assertIn("(up to 5,118 with heater on)", read("/heater-miners/"))

    def test_home_picks_unique_spec_and_bitaxe_class(self):
        latest = json.loads((ROOT / "data" / "latest.json").read_text())
        mids = re.findall(r'<h3><a href="/models/([^/]+)/', home_cards())
        self.assertGreaterEqual(len(mids), 3)
        specs = [(latest["models"][m]["hashrate_ths"], latest["models"][m]["watts"]) for m in mids]
        self.assertEqual(len(specs), len(set(specs)), f"same-spec duplicates on home: {mids}")
        self.assertNotIn("nerdaxe-gamma", mids)                    # same spec as the cheaper Bitaxe Gamma
        self.assertEqual(home_cards().count('class="ribbon"'), 1)

    def test_hero_counts_come_from_data(self):
        latest = json.loads((ROOT / "data" / "latest.json").read_text())
        home = read("/")
        n_shops = len(latest["sellers"])
        self.assertIn(f"price-checked</span> across {n_shops} shops.</h1>", home)
        self.assertNotIn("Every home Bitcoin miner", home)
        n = re.search(r"<strong>(\d+)</strong> miners tracked", home).group(1)
        self.assertIn(f"{n} home Bitcoin miners", read("/models/"))
        self.assertIn(f"on our {n} miner pages", read("/advertise/"))
        self.assertIn(f"All {n} home Bitcoin miners we track", read("/miners/"))

    def test_times_are_us_eastern(self):
        for f in SITE.rglob("*.html"):
            self.assertNotRegex(f.read_text(), r"\d\d:\d\d UTC", str(f))
        self.assertRegex(read("/"), r'id="freshness"[^>]*>\w{3} \d{1,2}, \d{4} \d{1,2}:\d\d [AP]M ET<')

    def test_about_redirects_to_how_we_track(self):
        a = read("/about/")
        self.assertIn("url=/how-we-track/", a)
        self.assertIn('name="robots" content="noindex', a)
        self.assertNotIn("/about/<", (SITE / "sitemap.xml").read_text())

    def test_black_friday_wording_is_modest(self):
        bf = read("/bitaxe-black-friday/")
        self.assertNotIn("lowest logged", bf)
        self.assertIn("We started tracking on", bf)

    def test_shop_store_link_carries_affiliate_code(self):
        aff = dict(re.findall(r'(\w+):\s*"([^"]+)"', re.search(r"var AFFILIATE = \{(.*?)\}", (SITE / "app.js").read_text(), re.S).group(1)))
        self.assertIn("powermining", aff)
        for sid, code in aff.items():
            h = read(f"/sellers/{sid}/")
            m = re.search(r'Store: <a href="([^"]+)" rel="([^"]+)"', h)
            self.assertIn(code, m.group(1), sid)
            self.assertIn("sponsored", m.group(2), sid)
        other = next(p for p in (SITE / "sellers").iterdir() if p.is_dir() and p.name not in aff)
        self.assertRegex((other / "index.html").read_text(), r'Store: <a href="https://[^"?]+" rel="nofollow noopener"')


@unittest.skipUnless(shutil.which("node"), "node not installed")
class FinderLogic(unittest.TestCase):
    """Runs the real Find-my-miner script against the real cards in a tiny fake DOM."""

    def run_quiz(self, budget, goal, place):
        h = read("/find-my-miner/")
        js = re.search(r"<script>\s*(\(function\(\)\{\s*var f=document.getElementById\('quiz'\).*?)</script>", h, re.S).group(1)
        pool = h.split('id="qpool"')[1]
        cards = [dict(re.findall(r'data-(\w+)="([^"]*)"', a)) for a in re.findall(r"<article ([^>]*)>", pool)]
        harness = """
const cards=%s, answers=%s;
function el(d){return {dataset:d,textContent:'',hidden:true,className:'',innerHTML:'',children:[],
  appendChild(c){this.children.push(c)},cloneNode(){return el(this.dataset)},querySelector(){return el({})},scrollIntoView(){}};}
const pool=cards.map(el); const out=el({}); let submit;
const form={hidden:true,querySelector(sel){const k=sel.match(/name="(\\w+)"/)[1];return {value:answers[k]};},addEventListener(t,f){submit=f}};
global.document={getElementById:id=>id==='quiz'?form:out,querySelectorAll:()=>pool,createElement:()=>el({})};
%s
submit({preventDefault(){}});
const grid=out.children.find(c=>c.className==='cards');
console.log(JSON.stringify({picks:grid.children.map(c=>c.dataset),note:(out.children.find(c=>c.className==='hint')||{}).textContent||''}));
""" % (json.dumps(cards), json.dumps(dict(budget=budget, goal=goal, place=place)), js)
        r = subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)

    def test_big_budget_heater_search_respects_budget(self):
        res = self.run_quiz("500up", "heat", "garage")
        self.assertTrue(res["picks"])
        for d in res["picks"]:
            self.assertGreaterEqual(float(d["price"]), 500, d)

    def test_no_same_spec_padding(self):
        for b in ("100", "500", "500up"):
            for g in ("solo", "pool", "heat"):
                for p in ("desk", "room", "garage"):
                    picks = self.run_quiz(b, g, p)["picks"]
                    specs = [(d["th"], d["w"]) for d in picks]
                    self.assertEqual(len(specs), len(set(specs)), (b, g, p, picks))
                    self.assertLessEqual(len(picks), 3)


if __name__ == "__main__":
    unittest.main()
