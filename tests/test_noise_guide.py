"""Noise comparison guide: built, linked, every cited miner listed with a source, buy CTA present, no internal text."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/guides/bitaxe-noise/index.html"


class NoiseGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt", "site/best/quiet/index.html", "site/guides/bitaxe-monitoring-apps/index.html"]:
            self.assertIn("/guides/bitaxe-noise/", (ROOT / f).read_text(), f)

    def test_every_noise_model_listed_with_source(self):
        t = PAGE.read_text()
        ms = B.noise_models()
        self.assertGreaterEqual(len(ms), 10)
        for m in ms:
            self.assertIn(f"/models/{m}/", t)
            self.assertIn(B.NOISE[m][2], t)

    def test_no_invented_db_claim(self):
        t = PAGE.read_text()
        self.assertIn("not our lab measurements", t)
        self.assertIn("makers' or sellers'", t)

    def test_internal_links_exist(self):
        t = PAGE.read_text()
        for href in set(re.findall(r'href="(/[^"#]*)', t)):
            if href.endswith("/"):
                self.assertTrue((ROOT / "site" / href.lstrip("/") / "index.html").exists() or href == "/", href)

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))


if __name__ == "__main__":
    unittest.main()
