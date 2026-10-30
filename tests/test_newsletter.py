import json
import unittest
from pathlib import Path

import build_site  # noqa: F401  (builds the site on import)
import newsletter as NL

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


class NewsletterTest(unittest.TestCase):
    def test_every_issue_has_a_web_page_listed_on_the_index(self):
        idx = (SITE / "newsletter" / "index.html").read_text()
        for i in NL.issues():
            page = SITE / "newsletter" / i["slug"] / "index.html"
            self.assertTrue(page.exists(), i["slug"])
            self.assertIn(f'href="/newsletter/{i["slug"]}/"', idx)
            self.assertIn(f"https://bitaxeradar.com/newsletter/{i['slug']}/", (SITE / "sitemap.xml").read_text())

    def test_feature_block_and_new_miner_count(self):
        for path in sorted(NL.DIR.glob("issue-*.json")):
            i = json.loads(path.read_text())
            html = (SITE / "newsletter" / i["slug"] / "index.html").read_text()
            email = NL.email_html(i)
            n = len(i["new_miners"])
            self.assertIn(f"{n} new miner", email)
            self.assertIn(f"{n} new miner", html)
            if i.get("feature"):
                self.assertIn(f'href="{i["feature"]["link"]}"', html)
                self.assertIn(f'href="https://bitaxeradar.com{i["feature"]["link"]}"', email)
                self.assertIn(i["feature"]["title"].upper(), NL.email_text(i))

    def test_web_copy_hides_email_only_bits(self):
        for i in NL.issues():
            html = (SITE / "newsletter" / i["slug"] / "index.html").read_text()
            self.assertNotIn("mailing address goes here", html)
            self.assertNotIn("NL_UNSUBSCRIBE_URL", html)
            for bad in ["guaranteed income", "passive income", "pays for itself"]:
                self.assertNotIn(bad, html.lower())


if __name__ == "__main__":
    unittest.main()
