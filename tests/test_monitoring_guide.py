"""The monitoring apps roundup: built, linked from guides, every app listed with an outbound link, no internal text."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/guides/bitaxe-monitoring-apps/index.html"


class MonitoringGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt", "site/guides/bitaxe-setup/index.html", "site/guides/is-my-bitaxe-normal/index.html"]:
            self.assertIn("/guides/bitaxe-monitoring-apps/", (ROOT / f).read_text(), f)

    def test_every_app_listed(self):
        t = PAGE.read_text()
        self.assertEqual(len(B.MON_APPS), 5)
        for app in B.MON_APPS:
            self.assertIn(app[0], t)
            self.assertTrue(app[1].startswith("https://"))
            self.assertIn(app[1], t)

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
