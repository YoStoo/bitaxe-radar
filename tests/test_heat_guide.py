"""The heat-your-home guide: built, linked, and its "beats a heat pump below" column matches the stated rule."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import earnings as E  # noqa: E402

PAGE = ROOT / "site/guides/bitcoin-mining-heat-your-home/index.html"


class HeatGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt", "site/guides/how-heater-miners-work/index.html"]:
            self.assertIn("/guides/bitcoin-mining-heat-your-home/", (ROOT / f).read_text(), f)

    def test_heat_pump_rule(self):
        # At a power price p, the miner's net heat cost is power - pool, a heat pump's is power / 2.
        # The miner wins exactly when pool > power / 2, i.e. below twice its break-even price.
        net = dict(network_hashrate_hs=1e21, subsidy_btc=3.125, avg_fees_btc=0.02, btc_usd=100000)
        th, w = 37.5, 800
        be = E.breakeven_rate(th, w, net)
        beat = be / 0.5
        pool = E.pool_estimate(th, net)["usd_month"]
        below = E.power_cost_month(w, beat * 0.95) / 2
        above = E.power_cost_month(w, beat * 1.05) / 2
        self.assertLess(E.power_cost_month(w, beat * 0.95) - pool, below)
        self.assertGreater(E.power_cost_month(w, beat * 1.05) - pool, above)

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem", t, re.I))
        self.assertIn("energy.gov", t)


if __name__ == "__main__":
    unittest.main()
