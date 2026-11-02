"""The 'Buying on AliExpress or from an unknown shop' box on /where-to-buy-bitaxe/: present, links the guides,
shows today's cheapest in-stock Gamma from data with an affiliate link, names no unknown shop, no internal text."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/where-to-buy-bitaxe/index.html"


def box():
    t = PAGE.read_text()
    m = re.search(r'<section class="buybox".*?</section>', t, re.S)
    assert m, "unknown-shop box missing"
    return m.group(0)


class UnknownShopBox(unittest.TestCase):
    def test_box_content(self):
        b = box()
        self.assertIn("AliExpress", b)
        self.assertIn("official", b)
        for want in ("/guides/bitaxe-power-supply/", "/guides/bitaxe-chips/", "5V", "12V", "XT30", "Return terms", "import", "buyer protection"):
            self.assertIn(want, b)

    def test_cheapest_gamma_from_data(self):
        b = box()
        g = B.STATS["bitaxe-gamma"]
        pick = g["best_usd"] or g["best"]
        if pick:
            self.assertTrue(B.in_stock(pick))
            self.assertIn(B.money(pick["price"], pick["currency"]), b)
            if B.psu_included(pick):
                self.assertIn("with a power supply", b)
            self.assertIn(B.esc(B.sname(pick["seller"])), b)
            if B.aff_param(pick["seller"]):
                self.assertIn('rel="sponsored nofollow noopener"', b)
        # Solo Satoshi links use the path-style affiliate code
        if "/solosatoshi" in b or "solosatoshi.com" in b:
            self.assertIn("aff/8840/", b)

    def test_tracked_sellers_linked(self):
        b = box()
        for sid in B.TRUSTED_AFF_SELLERS:
            if sid in B.SELLERS:
                self.assertIn(B.esc(B.sname(sid)), b)

    def test_no_accusations_or_internal_text(self):
        b = box()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson|Oneminers|Stellapex|scam|reddit", b, re.I))


if __name__ == "__main__":
    unittest.main()
