import re
import unittest
from pathlib import Path

import build_site  # noqa: F401  (builds the site on import)

SITE = Path(__file__).resolve().parent.parent / "site"


class GiftGuideTest(unittest.TestCase):
    def setUp(self):
        self.html = (SITE / "best" / "gifts" / "index.html").read_text()

    def test_budget_groups_hold_their_prices(self):
        bands = {"under-100": (0, 100), "100-300": (100, 300), "300-up": (300, 10 ** 9)}
        parts = re.split(r'<h2 id="h-([\w-]+)">', self.html)
        seen = set()
        for gid, chunk in zip(parts[1::2], parts[2::2]):
            if gid not in bands:
                continue
            seen.add(gid)
            lo, hi = bands[gid]
            for p in re.findall(r'<div class="price">(?:≈ )?\$([\d,]+\.\d{2})', chunk):
                self.assertTrue(lo <= float(p.replace(",", "")) < hi, (gid, p))
        self.assertTrue(seen)

    def test_preorders_labelled_and_no_income_promises(self):
        if 'id="h-pre"' in self.html:
            pre = self.html.split('id="h-pre"')[1].split('id="h-faq"')[0]
            self.assertNotIn('class="badge b-in_stock"', pre)
        low = self.html.lower()
        for bad in ["guaranteed", "passive income", "pays for itself", "profit of $"]:
            self.assertNotIn(bad, low)
        self.assertIn('href="/guides/bitaxe-setup/"', self.html)
        self.assertIn("https://bitaxeradar.com/best/gifts/", (SITE / "sitemap.xml").read_text())


if __name__ == "__main__":
    unittest.main()
