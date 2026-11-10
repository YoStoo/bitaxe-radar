"""The /ask/ page: form, script wiring, noindex, and out of the sitemap. Run after `python3 build_site.py`."""
import json
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class AskPage(unittest.TestCase):
    def setUp(self):
        self.html = (SITE / "ask" / "index.html").read_text()
        self.css = (SITE / "style.css").read_text()
        self.js = (SITE / "ask.js").read_text()

    def test_form_and_script(self):
        self.assertIn('id="ask-form"', self.html)
        self.assertIn('maxlength="300"', self.html)
        self.assertIn('src="/ask-api.js"', self.html)
        self.assertIn('src="/ask.js"', self.html)
        i = self.html.index("window.RADAR_ASK=") + len("window.RADAR_ASK=")
        cfg, _ = json.JSONDecoder().raw_decode(self.html[i:])
        self.assertTrue(cfg["url"].startswith("https://") and cfg["url"].endswith("/ask"))

    def test_not_indexed_yet(self):
        self.assertIn('content="noindex', self.html)
        self.assertNotIn("/ask/", (SITE / "sitemap.xml").read_text())

    def test_answer_rendered_safely(self):
        self.assertIn("textContent", self.js)
        self.assertNotIn("innerHTML", self.js)
        self.assertIn("modelName", self.js)

    def test_dark_themed_composer_not_signup_form(self):
        # The old page used class="signup" and an unstyled (white) textarea.
        form = re.search(r"<form[^>]*id=\"ask-form\"[^>]*>", self.html).group(0)
        self.assertNotIn("signup", form)
        self.assertIn('class="ask-page"', self.html)
        self.assertIn("ask-composer", self.html)
        self.assertIn('id="ask-q"', self.html)
        self.assertIn("placeholder=", self.html)
        # Scoped dark styles for the page textarea, plus a global textarea rule.
        self.assertIn(".ask-page #ask-form textarea", self.css)
        self.assertRegex(self.css, r"input,select,textarea\{[^}]*background:var\(--bg\)")
        self.assertIn("prefers-reduced-motion", self.css)

    def test_example_chips_and_how_it_works(self):
        self.assertIn("ask-chip", self.html)
        self.assertIn("data-q=", self.html)
        self.assertIn("1 TH/s", self.html)
        self.assertIn("gotten cheaper this month", self.html)
        self.assertIn("power supply", self.html.lower())
        self.assertIn("bedroom", self.html.lower())
        self.assertIn("How it works", self.html)
        self.assertIn('href="/evals/"', self.html)
        self.assertIn("Checked by evals", self.html)
        self.assertIn("Anthropic", self.html)
        self.assertIn("don't type personal info", self.html)
        self.assertIn("ask-disclaimer", self.html)

    def test_motion_and_widget_styles_untouched(self):
        self.assertIn("ask-reveal", self.html)
        self.assertIn("prefers-reduced-motion", self.js)
        self.assertIn("IntersectionObserver", self.js)
        # Floating widget chrome must still be in the stylesheet.
        self.assertIn("#radar-ask-bubble", self.css)
        self.assertIn(".ra-form textarea", self.css)
        self.assertIn("background:var(--bg2)", self.css)
        # The standalone page hides the bubble, but only when .ask-page is present.
        self.assertIn("body:has(.ask-page) #radar-ask-root", self.css)

    def test_js_wires_chips_loading_and_badges(self):
        self.assertIn("ask-chip", self.js)
        self.assertIn("Asking…", self.js)
        self.assertIn("Looking up today's prices", self.js)
        self.assertIn("From our data", self.js)
        self.assertIn("From our guides", self.js)
        self.assertIn("ask-badge", self.js)


    def test_enter_submits_question(self):
        # Enter sends; Shift+Enter keeps a newline. IME composition is ignored.
        self.assertIn('enterkeyhint="send"', self.html)
        self.assertIn("isComposing", self.js)
        self.assertIn("keyCode === 229", self.js)
        self.assertIn('e.key !== "Enter" || e.shiftKey', self.js)
        self.assertIn("requestSubmit", self.js)
        self.assertIn('!(box.value || "").trim()', self.js)
        self.assertIn("btn.disabled", self.js)

if __name__ == "__main__":
    unittest.main()
