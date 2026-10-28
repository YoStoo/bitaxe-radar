"""The "Is my Bitaxe normal?" guide: built, linked, and its stock numbers follow AxeOS's own formula."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/guides/is-my-bitaxe-normal/index.html"


class NormalGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt", "site/guides/bitcoin-mining-pools/index.html", "site/models/bitaxe-gamma/index.html"]:
            self.assertIn("/guides/is-my-bitaxe-normal/", (ROOT / f).read_text(), f)

    def test_axeos_formula(self):
        # ESP-Miner: expected GH/s = frequency MHz x small cores x chips / 1000
        self.assertAlmostEqual(B.axeos_expected_ghs(525, 2040, 1), 1071.0)
        self.assertAlmostEqual(B.axeos_expected_ghs(690, 2040, 6), 8445.6)
        # Each board's stock figure stays close to the hashrate the site uses for that model (within 25%)
        for m, _, _, mhz, _, cores, chips, _, _ in B.AXEOS_BOARDS:
            exp = B.axeos_expected_ghs(mhz, cores, chips) / 1000
            self.assertLess(abs(exp / B.MODELS[m]["hashrate_ths"] - 1), 0.25, m)
        t = PAGE.read_text()
        self.assertIn("≈1.07 TH/s", t)
        self.assertIn("75°C", t)

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))
        self.assertIn("github.com/bitaxeorg/ESP-Miner", t)


if __name__ == "__main__":
    unittest.main()
