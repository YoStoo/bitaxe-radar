"""Floating Ask chat widget: every built page loads it; /ask/ still builds. Run after `python3 build_site.py`."""
import json
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
SKIP_DIRS = {"img"}  # binary assets only


def html_pages():
    pages = []
    for p in SITE.rglob("*.html"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        pages.append(p)
    return pages


class ChatWidget(unittest.TestCase):
    def test_widget_assets_exist(self):
        self.assertTrue((SITE / "ask-api.js").is_file())
        self.assertTrue((SITE / "chat-widget.js").is_file())
        self.assertTrue((SITE / "ask.js").is_file())
        css = (SITE / "style.css").read_text()
        self.assertIn("#radar-ask-bubble", css)
        self.assertIn("prefers-reduced-motion", css)

    def test_every_page_includes_widget_script(self):
        pages = html_pages()
        self.assertGreater(len(pages), 50)
        missing = []
        for p in pages:
            # Tiny redirect stubs don't need the chat bubble.
            html = p.read_text()
            if "This page moved" in html or '<meta http-equiv="refresh"' in html.lower():
                continue
            if 'src="/chat-widget.js"' not in html or 'src="/ask-api.js"' not in html:
                missing.append(str(p.relative_to(SITE)))
            elif "window.RADAR_ASK=" not in html:
                missing.append(str(p.relative_to(SITE)) + " (no RADAR_ASK)")
        self.assertEqual(missing, [], "pages missing chat widget:\n" + "\n".join(missing[:20]))

    def test_ask_page_still_builds(self):
        html = (SITE / "ask" / "index.html").read_text()
        self.assertIn('id="ask-form"', html)
        self.assertIn('src="/ask.js"', html)
        self.assertIn('src="/ask-api.js"', html)
        self.assertIn('src="/chat-widget.js"', html)
        self.assertIn('maxlength="300"', html)
        cfg = json.loads(re.search(r"window\.RADAR_ASK=(\{.*?\});", html).group(1))
        self.assertTrue(cfg["url"].startswith("https://") and cfg["url"].endswith("/ask"))
        self.assertIn('content="noindex', html)

    def test_home_and_model_have_widget(self):
        home = (SITE / "index.html").read_text()
        self.assertIn('src="/chat-widget.js"', home)
        gamma = (SITE / "models" / "bitaxe-gamma" / "index.html").read_text()
        self.assertIn('src="/chat-widget.js"', gamma)

    def test_no_innerhtml_for_answers(self):
        # User/AI text must go through textContent, not innerHTML.
        api = (SITE / "ask-api.js").read_text()
        ask = (SITE / "ask.js").read_text()
        widget = (SITE / "chat-widget.js").read_text()
        self.assertIn("textContent", ask)
        self.assertNotIn("innerHTML", ask)
        self.assertIn("RadarAsk", api)
        # Widget may use innerHTML for its own static chrome; answers use textContent via el(..., text).
        self.assertIn("textContent", widget)
        self.assertIn("models_mentioned", widget)
        self.assertIn("radarAskChipsDismissed", widget)
        self.assertIn("prefers-reduced-motion", widget)


if __name__ == "__main__":
    unittest.main()
