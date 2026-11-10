"""Homepage polish (Nov 2026): top-3 cards, FAQ moved to /faq/, no 'how it works' bubbles, a photo for every miner,
the redesigned price chart, and the invisible bot check. Run after `python3 build_site.py`."""
import json
import re
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def read(path):
    return (SITE / "index.html").read_text() if path == "/" else (SITE / path.strip("/") / "index.html").read_text()


def home_cards():
    return read("/").split('id="miners"')[1].split("</section>")[0]


class TopThree(unittest.TestCase):
    def test_home_shows_at_most_three_cards(self):
        cards = re.findall(r'<article class="card', home_cards())
        self.assertEqual(len(cards), 3)
        self.assertIn('class="cards cards-top"', home_cards())

    def test_three_are_the_best_price_per_th(self):
        latest = json.loads((ROOT / "data" / "latest.json").read_text())
        mids = re.findall(r'<h3><a href="/models/([^/]+)/', home_cards())
        prices = [float(p.replace(",", "")) for p in re.findall(r'<div class="price">≈? ?\$([\d,.]+)', home_cards())]
        per_th = [p / latest["models"][m]["hashrate_ths"] for m, p in zip(mids, prices)]
        ribbon = re.search(r'<h3><a href="/models/([^/]+)/', home_cards().split('class="ribbon"')[1]).group(1)
        self.assertEqual(ribbon, mids[per_th.index(min(per_th))])      # "Best value" goes to the lowest $/TH card
        # shown smallest to biggest
        hs = [latest["models"][m]["hashrate_ths"] for m in mids]
        self.assertEqual(hs, sorted(hs))

    def test_hero_numbers_count_up_from_the_real_value(self):
        for n, txt in re.findall(r'<strong data-count="(\d+)">(\d+)</strong>', read("/")):
            self.assertEqual(n, txt)   # with JS off the real number is already there


class Removed(unittest.TestCase):
    def test_questions_section_gone_from_home(self):
        home = read("/")
        self.assertNotIn('id="faq"', home)
        self.assertNotIn('id="h-faq"', home)
        self.assertNotIn("<summary>What is a Bitaxe?</summary>", home)

    def test_faq_page_keeps_the_answers_schema_and_calculator(self):
        faq = read("/faq/")
        self.assertIn("<summary>What is a Bitaxe?</summary>", faq)
        self.assertIn('id="cost"', faq)
        self.assertIn('id="costTable"', faq)
        self.assertIn('/app.js', faq)
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', faq, re.S)]
        self.assertTrue(any(x.get("@type") == "FAQPage" and len(x["mainEntity"]) >= 5 for x in ld))
        self.assertIn('href="/faq/"', read("/"))                   # footer link
        self.assertIn("<loc>https://bitaxeradar.com/faq/</loc>", (SITE / "sitemap.xml").read_text())
        self.assertIn('href="/faq/#cost"', read("/models/bitaxe-gamma/"))
        self.assertNotIn('href="/#cost"', read("/models/bitaxe-gamma/"))

    def test_how_it_works_bubbles_gone(self):
        home = read("/")
        self.assertNotIn('class="steps"', home)
        self.assertNotIn("We check the shops</b>", home)
        self.assertNotIn("Buy direct</b>", home)
        self.assertNotIn(".steps{", (SITE / "style.css").read_text())


class Photos(unittest.TestCase):
    def test_every_built_model_page_has_a_photo(self):
        missing = []
        for page in sorted((SITE / "models").glob("*/index.html")):
            mid = page.parent.name
            if not (SITE / "img" / "models" / f"{mid}.webp").exists() or f'src="/img/models/{mid}.webp"' not in page.read_text():
                missing.append(mid)
        self.assertEqual(missing, [])

    def test_photos_are_sized_like_the_rest(self):
        for f in (SITE / "img" / "models").glob("*.webp"):
            head = f.read_bytes()[:40]
            self.assertEqual(head[:4], b"RIFF", f.name)
            self.assertLess(f.stat().st_size, 200_000, f.name)

    def test_home_cards_use_photos_not_drawings(self):
        self.assertNotIn("<svg", home_cards().split("</div></article>")[0].split('class="art')[1].split("</div>")[0])

    def test_new_photos_have_sources_listed(self):
        doc = (ROOT / "docs" / "IMAGE_SOURCES.md").read_text()
        for f in ("nerdoctaxe.webp", "dcentral-stealthminer.webp", "nerdqx.webp", "gekko-kbeast-50.webp", "bitaxe-ultra.webp"):
            self.assertIn(f"| {f} |", doc)


class Chart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = read("/models/bitaxe-gamma/")
        cls.hist = cls.page.split('id="h-hist"')[1].split("</section>")[0]
        cls.data = json.loads(unescape(re.search(r'<figure class="pchart" data-chart="([^"]+)"', cls.hist).group(1)))

    def test_one_line_and_legend_item_per_shop(self):
        n = len(self.data["s"])
        self.assertGreaterEqual(n, 2)
        self.assertLessEqual(n, 5)
        self.assertEqual(len(re.findall(r'<li data-i="\d+">', self.hist)), n)
        self.assertEqual({int(i) for i in re.findall(r'class="ln[^"]*" data-i="(\d+)"', self.hist)}, set(range(n)))

    def test_current_price_is_called_out_from_the_data(self):
        cheapest_now = min(s["p"][-1][1] for s in self.data["s"] if s["p"][-1][2])
        self.assertRegex(self.hist, r'class="ctag now"[^>]*>Now \$')
        self.assertIn(f"Now ${cheapest_now:,.0f}", self.hist)

    def test_chart_is_accessible_and_labeled(self):
        self.assertRegex(self.hist, r'<svg [^>]*role="img" aria-label="Price history for Bitaxe Gamma in US dollars over \d+ days')
        self.assertIn("<figcaption", self.hist)
        self.assertIn("dashed = sold out", self.hist)

    def test_low_marker_or_note_matches_history(self):
        for mid in ("avalon-q", "bitaxe-gamma", "nerdqaxe-pp"):
            h = read(f"/models/{mid}/").split('id="h-hist"')[1].split("</section>")[0]
            self.assertIn('class="chart-note"', h, mid)
            m = re.search(r"Lowest in-stock price in the last \d+ days: <b>\$([\d,.]+)</b>", h)
            if m:                                                   # not at the low now: the low gets a marker on the line too
                self.assertIn('class="cdot low"', h, mid)
                self.assertIn(f'Low ${m.group(1)}', h, mid)

    def test_motion_is_opt_in_and_never_hides_content_without_js(self):
        css = (SITE / "style.css").read_text()
        block = css.split("@media (prefers-reduced-motion: no-preference){", 1)[1]
        self.assertIn(".pchart.anim .chart-reveal", block)
        self.assertIn(".rv .card", block)
        # the classes that start hidden are only ever added by motion.js, never in the HTML
        for f in SITE.rglob("*.html"):
            t = f.read_text()
            self.assertNotRegex(t, r'class="[^"]*\b(rv|anim|is-in|is-inview)\b', f.name)
        self.assertIn("/motion.js", self.page)
        self.assertIn("/motion.js", read("/"))
        js = (SITE / "motion.js").read_text()
        self.assertIn("prefers-reduced-motion: reduce", js)


class BotCheck(unittest.TestCase):
    def test_turnstile_is_invisible_unless_needed(self):
        js = (SITE / "signup.js").read_text()
        self.assertIn('appearance: "interaction-only"', js)
        self.assertIn('"cf-turnstile-response": tok', js)       # the Worker still gets the same token field
        self.assertIn("radarBotCheck", (SITE / "nl-signup.js").read_text())
        self.assertNotIn("min-height:65px", (SITE / "style.css").read_text())


if __name__ == "__main__":
    unittest.main()
