"""The /ask/ page: form, script wiring, noindex, and out of the sitemap. Run after `python3 build_site.py`."""
import json
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class AskPage(unittest.TestCase):
    def setUp(self):
        self.html = (SITE / "ask" / "index.html").read_text()

    def test_form_and_script(self):
        self.assertIn('id="ask-form"', self.html)
        self.assertIn('maxlength="300"', self.html)
        self.assertIn('src="/ask-api.js"', self.html)
        self.assertIn('src="/ask.js"', self.html)
        cfg = json.loads(re.search(r"window\.RADAR_ASK=(\{.*?\});", self.html).group(1))
        self.assertTrue(cfg["url"].startswith("https://") and cfg["url"].endswith("/ask"))

    def test_not_indexed_yet(self):
        self.assertIn('content="noindex', self.html)
        self.assertNotIn("/ask/", (SITE / "sitemap.xml").read_text())

    def test_answer_rendered_safely(self):
        js = (SITE / "ask.js").read_text()
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)


if __name__ == "__main__":
    unittest.main()
