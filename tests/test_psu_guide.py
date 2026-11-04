"""The power supply guide: built, linked, voltage facts consistent, only 'in the box' listings in the buy table, no internal text."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/guides/bitaxe-power-supply/index.html"


class PsuGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt", "site/guides/bitaxe-setup/index.html", "site/guides/bitaxe-chips/index.html"]:
            self.assertIn("/guides/bitaxe-power-supply/", (ROOT / f).read_text(), f)

    def test_voltages(self):
        for m in ("bitaxe-gamma", "bitaxe-gamma-duo", "nerdaxe-gamma"):
            self.assertEqual(B.PSU_SPECS[m][0], "5V DC")
        for m in ("bitaxe-gt-801", "bitaxe-naja-duo", "nerdqaxe-pp", "bitaxe-gamma-hex"):
            self.assertEqual(B.PSU_SPECS[m][0], "12V DC")

    def test_psu_detection(self):
        self.assertTrue(B.psu_included({"seller": "x", "model": "y", "config": "Stand: None, Power Supply: North America"}))
        self.assertTrue(B.psu_included({"seller": "x", "model": "y", "config": "power supply included per product title"}))
        self.assertFalse(B.psu_included({"seller": "x", "model": "y", "config": "power supply not mentioned in title (unverified)"}))
        self.assertFalse(B.psu_included({"seller": "x", "model": "y", "config": "Base price incl. VAT"}))
        for m in B.psu_models():
            b = B.psu_best(m)
            if b:
                self.assertTrue(B.in_stock(b) and B.psu_included(b))

    def test_every_model_on_page(self):
        t = PAGE.read_text()
        for m in B.psu_models():
            self.assertIn(f'/models/{m}/', t)

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))

    def test_several_miners_section(self):
        t = PAGE.read_text()
        self.assertIn('id="h-4"', t)
        self.assertIn("Several miners on one power supply", t)
        self.assertIn("80%", t)
        self.assertRegex(t, r"same voltage|Same voltage", re.I)
        self.assertIn("Never feed a 5V", t)
        self.assertIn("Wall watts vs dashboard watts", t)
        self.assertIn("power strip", t.lower())
        # Worked example uses live model watts
        self.assertIn(f"{B.MODELS['nerdoctaxe']['watts']:g} W", t)
        self.assertIn(f"{B.MODELS['nerdqaxe-pp']['watts']:g} W", t)
        self.assertIn("Can several miners share one power supply?", t)


if __name__ == "__main__":
    unittest.main()
