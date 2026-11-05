"""BitForge Nano vs Bitaxe GT 801 compare page: built, named, linked to both model pages."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/compare/bitforge-nano-vs-bitaxe-gt-801/index.html"
PAIR = ("bitforge-nano", "bitaxe-gt-801")


class BitforgeVsGt(unittest.TestCase):
    def test_pair_registered(self):
        self.assertIn(PAIR, B.COMPARE_PAIRS)
        self.assertIn(PAIR, B.COMPARE_COPY)
        self.assertTrue(B.COMPARE_COPY[PAIR]["angle"])
        self.assertTrue(B.COMPARE_COPY[PAIR]["a_for"])
        self.assertTrue(B.COMPARE_COPY[PAIR]["b_for"])

    def test_page_built_with_both_models(self):
        self.assertTrue(PAGE.exists(), "compare page missing; run build_site.py first")
        t = PAGE.read_text()
        self.assertIn("BitForge Nano", t)
        self.assertIn("Bitaxe GT 801", t)
        self.assertIn("/models/bitforge-nano/", t)
        self.assertIn("/models/bitaxe-gt-801/", t)
        self.assertIn("/compare/bitforge-nano-vs-bitaxe-gt-801/", (ROOT / "site/compare/index.html").read_text())
        self.assertIn("/compare/bitforge-nano-vs-bitaxe-gt-801/", (ROOT / "site/sitemap.xml").read_text())

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))


if __name__ == "__main__":
    unittest.main()
