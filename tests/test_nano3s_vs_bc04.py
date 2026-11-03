"""Avalon Nano 3S vs Hammer BC04 compare page: built, named, linked to both model pages."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/compare/avalon-nano-3s-vs-hammer-bc04/index.html"
PAIR = ("avalon-nano-3s", "hammer-bc04")


class Nano3sVsBc04(unittest.TestCase):
    def test_pair_registered(self):
        self.assertIn(PAIR, B.COMPARE_PAIRS)
        self.assertIn(PAIR, B.COMPARE_COPY)
        self.assertTrue(B.COMPARE_COPY[PAIR]["angle"])
        self.assertTrue(B.COMPARE_COPY[PAIR]["a_for"])
        self.assertTrue(B.COMPARE_COPY[PAIR]["b_for"])

    def test_page_built_with_both_models(self):
        self.assertTrue(PAGE.exists(), "compare page missing; run build_site.py first")
        t = PAGE.read_text()
        self.assertIn("Avalon Nano 3S", t)
        self.assertIn("Hammer BC04", t)
        self.assertIn('/models/avalon-nano-3s/', t)
        self.assertIn('/models/hammer-bc04/', t)
        self.assertIn("/compare/avalon-nano-3s-vs-hammer-bc04/", (ROOT / "site/compare/index.html").read_text())
        self.assertIn("/compare/avalon-nano-3s-vs-hammer-bc04/", (ROOT / "site/sitemap.xml").read_text())

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))


if __name__ == "__main__":
    unittest.main()
