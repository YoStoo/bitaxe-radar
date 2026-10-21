"""site/calc.js must give the same numbers and words as earnings.py for every tracked miner across a range of power prices."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import earnings as E  # noqa: E402

SITE = ROOT / "site"
RATES = [0, 0.01, 0.02, 0.03, 0.045, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.2, 0.22,
         0.25, 0.3, 0.33, 0.4, 0.5, 0.75, 1, 1.5, 2, 0.0625, 0.123, 0.0999]
NETS = [json.loads((ROOT / "data" / "network.json").read_text()),
        {"network_hashrate_hs": 8.0e20, "subsidy_btc": 3.125, "avg_fees_btc": 0.2, "btc_usd": 150000.0},
        {"network_hashrate_hs": 2.0e21, "subsidy_btc": 3.125, "avg_fees_btc": 0.0, "btc_usd": 30000.0}]


def miners():
    latest = json.loads((ROOT / "data" / "latest.json").read_text())
    out = []
    for m in latest["models"].values():
        out.append((float(m["hashrate_ths"]), float(m.get("heat_watts", m["watts"]))))
    return out + [(0.5, 5.0), (1000.0, 3000.0), (0.0001, 1.0)]


def py_rows(net):
    rows = []
    for th, w in miners():
        for r in RATES:
            rows.append([E.net_words(th, w, net, r), E.net_short(th, w, net, r), E.fmt_usd(E.power_shown(w, r)),
                         E.fmt_usd(E.heat_value_month(w, r)), f"{E.breakeven_rate(th, w, net):.3f}", E.fmt_rate(r),
                         E.fmt_usd(E.pool_estimate(th, net)["usd_month_shown"])])
    return rows


JS = """
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
global.window = {RADAR_NET: Object.assign({pool_fee: %s, haircut: %s, default_rate: %s}, input.net)};
eval(fs.readFileSync(%s, 'utf8'));
const C = window.RadarCalc, out = [];
for (const [th, w] of input.miners) for (const r of input.rates)
  out.push([C.netWords(th, w, r), C.netShort(th, w, r), C.fmtUsd(C.roundUp(C.power(w, r))), C.fmtUsd(C.heat(w, r)),
            C.breakeven(th, w).toFixed(3), C.fmtRate(r), C.fmtUsd(C.roundDown(C.poolMonth(th)))]);
process.stdout.write(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed")
class CalcParity(unittest.TestCase):
    def test_js_matches_python(self):
        js = JS % (E.POOL_FEE, E.HAIRCUT, E.POWER_RATE, json.dumps(str(SITE / "calc.js")))
        for net in NETS:
            got = json.loads(subprocess.run(["node", "-e", js], input=json.dumps({"net": net, "miners": miners(), "rates": RATES}),
                                            capture_output=True, text=True, check=True).stdout)
            want = py_rows(net)
            self.assertEqual(len(got), len(want))
            for g, w in zip(got, want):
                self.assertEqual(g, w)

    def test_words_and_breakeven_sense(self):
        net = NETS[0]
        th, w = 1.2, 18.0
        be = E.breakeven_rate(th, w, net)
        self.assertIn("Earns about", E.net_words(th, w, net, max(be - 0.02, 0)))
        self.assertIn("Costs about", E.net_words(th, w, net, be + 0.02))
        self.assertTrue(E.net_words(th, w, net, 0.15).endswith("at $0.15"))
        self.assertEqual(E.fmt_rate(0.1), "$0.10")
        self.assertEqual(E.fmt_rate(0.065), "$0.065")
        # conservative: shown pool is rounded down, shown power and loss rounded up
        self.assertLessEqual(E.pool_estimate(th, net)["usd_month_shown"], E.pool_estimate(th, net)["usd_month"])
        self.assertGreaterEqual(E.power_shown(w, 0.15), E.power_cost_month(w, 0.15))
        self.assertLessEqual(be, E.pool_estimate(th, net)["usd_month"] / (w / 1000 * 24 * E.DAYS_PER_MONTH))


class CalcPages(unittest.TestCase):
    def read(self, p):
        return (SITE / p.strip("/") / "index.html").read_text()

    def test_calculator_on_pages(self):
        g = self.read("/models/bitaxe-gamma/")
        if 'id="h-earn"' not in g:
            self.skipTest("network inputs stale; estimates hidden by design")
        for p in ["/miners/", "/solo-miners/", "/pool-miners/", "/heater-miners/", "/best/quiet/", "/models/bitaxe-gamma/", "/models/avalon-q/",
                  "/guides/is-home-mining-worth-it/"]:
            h = self.read(p)
            self.assertIn('<form class="ratebox"', h, p)
            self.assertIn(" hidden>", h.split('<form class="ratebox"')[1][:30], p)     # hidden until JS runs
            self.assertIn('src="/calc.js"', h, p)
            self.assertIn("window.RADAR_NET=", h, p)
            self.assertRegex(h, r'data-calc="net(num)?"[^>]*>(Costs about|Earns about|About breaks even|[+−$])', p)
        self.assertIn("Break-even power price: <b>about $", g)
        self.assertNotIn("Heat you'd pay for anyway", g)
        q = self.read("/models/avalon-q/")
        self.assertIn("Heat you'd pay for anyway", q)
        self.assertIn("space heater", q)
        heat = self.read("/heater-miners/")
        self.assertIn("Heat you'd pay for anyway", heat)
        # the no-JS default matches the Python math
        net = json.loads((ROOT / "data" / "network.json").read_text())
        self.assertIn(E.net_words(1.2, 18.0, net, 0.15), g)

    def test_worth_it_guide(self):
        h = self.read("/guides/is-home-mining-worth-it/")
        self.assertIn("/miners/#rate", h)
        self.assertIn('id="rate"', self.read("/miners/"))
        self.assertIn('"FAQPage"', h)
        for bad in ["guaranteed income", "passive income", "pays for itself", "profit of $", "you will earn", "risk-free"]:
            self.assertNotIn(bad, h.lower())
        self.assertIn("/guides/is-home-mining-worth-it/", self.read("/guides/"))
        self.assertIn("is-home-mining-worth-it", (SITE / "sitemap.xml").read_text())


SOLO_JS = """
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
global.window = {RADAR_SOLO: {network_hashrate_hs: input.net.network_hashrate_hs}};
eval(fs.readFileSync(%s, 'utf8'));
process.stdout.write(JSON.stringify(input.ths.map(th => window.RadarSolo.rows(th))));
"""
SOLO_THS = sorted({float(m["hashrate_ths"]) for m in json.loads((ROOT / "data" / "latest.json").read_text())["models"].values()}
                  | {0.0001, 0.001, 0.05, 0.48, 0.995, 1, 2.5, 6, 37.2, 100, 230, 1000, 1e4, 1e5, 1e6, 5e6, 1e7})


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SoloParity(unittest.TestCase):
    def test_js_matches_python(self):
        js = SOLO_JS % json.dumps(str(SITE / "solo.js"))
        for net in NETS:
            got = json.loads(subprocess.run(["node", "-e", js], input=json.dumps({"net": net, "ths": SOLO_THS}),
                                            capture_output=True, text=True, check=True).stdout)
            want = [list(E.solo_rows(th, net)) for th in SOLO_THS]
            self.assertEqual(got, json.loads(json.dumps(want)))

    def test_solo_sense(self):
        net = NETS[0]
        self.assertLess(E.solo_chance(1.2, net, 1), E.solo_chance(1.2, net, 365))
        self.assertLess(E.solo_chance(1.2, net, 365), E.solo_chance(1.2, net, 365 * 5))
        self.assertAlmostEqual(E.solo_rate(1.2, net), 1.2e12 / net["network_hashrate_hs"] * 144)
        self.assertEqual(E.solo_rows(1e7, net)[0][0][2], "better than even")


class SoloPages(unittest.TestCase):
    def read(self, p):
        return (SITE / p.strip("/") / "index.html").read_text()

    def test_solo_odds_page(self):
        h = self.read("/solo-odds/")
        self.assertIn('<form class="solobox" id="solo-form" hidden>', h)
        self.assertIn('src="/solo.js"', h)
        self.assertIn("window.RADAR_SOLO=", h)
        self.assertIn('"FAQPage"', h)
        self.assertIn("lottery", h)
        net = json.loads((ROOT / "data" / "network.json").read_text())
        rows, wait = E.solo_rows(1.2, net)
        self.assertIn(f'data-solo="year-in">{rows[1][2]}<', h)      # no-JS default = Python math for a 1.2 TH/s Bitaxe Gamma
        for bad in ["guaranteed", "passive income", "you will win", "get rich"]:
            self.assertNotIn(bad, h.lower())
        for p in ["/solo-miners/", "/guides/", "/models/bitaxe-gamma/"]:
            self.assertIn("/solo-odds/", self.read(p), p)
        self.assertIn("/solo-odds/", (SITE / "llms.txt").read_text())
        self.assertIn("/solo-odds/", (SITE / "sitemap.xml").read_text())

    def test_solo_wins_page_and_model_line(self):
        wins = json.loads((ROOT / "data" / "solo_wins.json").read_text())["wins"]
        if not wins:
            self.skipTest("no solo wins data")
        h = self.read("/solo-wins/")
        self.assertIn("since the last solo win", h)
        self.assertIn("mempool.space/block/", h)
        self.assertIn("CC BY 4.0", h)
        self.assertIn("Pool = the service the winner mined through. Device = the machine they used, if they shared it.", h)
        self.assertNotIn("not publicly reported", h)
        unknown = [w for w in wins if not w.get("hashrate_hs") and not w.get("rented")]
        if unknown:
            self.assertIn('<span class="dev unk">Device: unknown</span>', h)
        named = next((w for w in wins if w.get("hardware") and w.get("hashrate_hs")), None)
        if named:
            self.assertIn(f'Device: {named["hardware"]} (≈', h)
            self.assertIn(", reported by winner)", h)
        self.assertIn(f'Pool: {wins[0]["pool"]}', h)
        self.assertIn("/solo-wins/", (SITE / "sitemap.xml").read_text())
        g = self.read("/models/bitaxe-gamma/")
        self.assertIn("Last solo block win:", g)
        self.assertIn("Pool: ", g.split("Last solo block win:")[1][:300])
        self.assertIn("Device: ", g.split("Last solo block win:")[1][:400])
        self.assertNotIn("Last solo block win:", self.read("/models/heatbit-maxi/"))     # not a solo model
        # "this size" only from a publicly reported hashrate within half to double the model's
        th = json.loads((ROOT / "data" / "latest.json").read_text())["models"]["bitaxe-gamma"]["hashrate_ths"]
        known = [w for w in wins if w.get("hashrate_hs") and not w.get("rented") and 0.5 <= w["hashrate_hs"] / 1e12 / th <= 2]
        self.assertEqual("Last win by a miner this size" in g, bool(known))


if __name__ == "__main__":
    unittest.main()
