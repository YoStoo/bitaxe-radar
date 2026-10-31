"""The chip guide: built, linked, every tracked BM-chip miner listed once under its chip, and no internal text."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/guides/bitaxe-chips/index.html"


class ChipGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt", "site/guides/bitaxe-firmware/index.html"]:
            self.assertIn("/guides/bitaxe-chips/", (ROOT / f).read_text(), f)

    def test_every_chip_miner_listed_once(self):
        groups = B.chip_groups()
        listed = [m for ms in groups.values() for m in ms]
        self.assertEqual(len(listed), len(set(listed)))
        expected = {m for m in B.TRACKED if B.chip_family(m) in B.CHIP_FAMILIES}
        self.assertEqual(set(listed), expected)
        self.assertEqual(B.chip_family("bitaxe-gamma"), "BM1370")
        self.assertEqual(B.chip_count("nerdqaxe-pp"), 4)
        self.assertEqual(B.chip_count("heatbit-bitwater"), 20)
        t = PAGE.read_text()
        for m in listed:
            self.assertIn(f'/models/{m}/', t)

    def test_newer_chips_more_efficient_in_our_data(self):
        groups = B.chip_groups()
        best = [min(B.jth(m) for m in ms) for ms in groups.values()]
        self.assertEqual(best, sorted(best, reverse=True))

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))


if __name__ == "__main__":
    unittest.main()
