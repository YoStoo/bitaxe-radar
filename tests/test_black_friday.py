"""Black Friday promo is gone: the old URL redirects to /deals/, and no banners, tabs, or leftover links remain."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://bitaxeradar.com"


class BlackFridayRemoved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = SITE / "bitaxe-black-friday" / "index.html"
        if not p.exists() or not (SITE / "sitemap.xml").exists():
            raise unittest.SkipTest("run build_site.py first")
        cls.html = p.read_text()
        cls.sitemap = (SITE / "sitemap.xml").read_text()

    def test_old_url_redirects_to_deals_and_stays_out_of_sitemap(self):
        self.assertIn("url=/deals/", self.html)
        self.assertIn('name="robots" content="noindex', self.html)
        self.assertIn(f'rel="canonical" href="{BASE}/deals/"', self.html)
        self.assertNotIn(BASE + "/bitaxe-black-friday/", self.sitemap)
        self.assertNotIn("bitaxe-black-friday", self.sitemap)

    def test_no_promo_links_banners_or_styles(self):
        css = (SITE / "style.css").read_text()
        self.assertNotIn("bf-banner", css)
        self.assertNotIn("bf-table", css)
        self.assertNotIn("Black Friday", css)
        # The redirect stub itself may mention the old path only as its file location, not as a promo link.
        for f in SITE.rglob("*.html"):
            if f.parent.name == "bitaxe-black-friday":
                continue
            txt = f.read_text()
            self.assertNotIn("/bitaxe-black-friday/", txt, f)
            self.assertNotIn("bf-banner", txt, f)
        src = (ROOT / "build_site.py").read_text()
        self.assertNotIn("def build_black_friday", src)
        self.assertNotIn("def bf_banner", src)
        self.assertNotIn("BF_BANNER", src)
        self.assertIn('build_redirect("/bitaxe-black-friday/", "/deals/"', src)


if __name__ == "__main__":
    unittest.main()
