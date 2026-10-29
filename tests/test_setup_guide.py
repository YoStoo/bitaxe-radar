"""The first-hour setup checklist: built, linked, and the firmware defaults it quotes are on the page."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/guides/bitaxe-setup/index.html"


class SetupGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt",
                  "site/guides/is-my-bitaxe-normal/index.html", "site/guides/bitaxe-firmware/index.html"]:
            self.assertIn("/guides/bitaxe-setup/", (ROOT / f).read_text(), f)

    def test_defaults_shown(self):
        t = PAGE.read_text()
        for host, port in (B.SETUP_DEFAULT_POOL, B.SETUP_DEFAULT_FALLBACK):
            self.assertIn(f"{host}, port {port}", t)
        self.assertIn("2.4 GHz", t)
        self.assertIn('"FAQPage"', t)

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))


if __name__ == "__main__":
    unittest.main()
