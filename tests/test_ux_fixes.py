"""The 9 buyer-UX fixes from the Nov 27 fresh-eyes review. Run after `python3 build_site.py`."""
import json
import re
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
LATEST = json.loads((ROOT / "data" / "latest.json").read_text())
AFF = dict(re.findall(r'(\w+):\s*"([^"]+)"', re.search(r"var AFFILIATE = \{(.*?)\}", (SITE / "app.js").read_text(), re.S).group(1)))


def read(path):
    return (SITE / path.strip("/") / "index.html").read_text() if path != "/" else (SITE / "index.html").read_text()


def shop_links(html):
    return re.findall(r'<a class="btn[^"]*" href="([^"]+)" target="_blank" rel="([^"]+)">', html)


class AskButton(unittest.TestCase):
    def test_ask_steps_aside_for_buttons_and_pages_have_room_at_the_bottom(self):
        js, css = (SITE / "chat-widget.js").read_text(), (SITE / "style.css").read_text()
        self.assertIn('classList.toggle("ra-dodge"', js)
        self.assertIn("#radar-ask-root.ra-dodge{opacity:0", css)
        self.assertIn("body:not(.ask-app){padding-bottom:76px}", css)


class Homepage(unittest.TestCase):
    def test_tiles_explain_solo_pool_heaters_in_quiz_words(self):
        home = read("/")
        for word in ("A lottery shot at a whole block", "Small, steady payouts", "Heats a room while it mines"):
            self.assertIn(f'<small class="tsub">{word}</small>', home)

    def test_phone_first_screen_has_a_real_price_and_shop_button(self):
        pick = read("/").split('class="hero-pick"')[1].split("</div></div>")[0]
        name = re.search(r'class="hp-name" href="/models/([^/]+)/"', pick).group(1)
        offers = [o for o in LATEST["offers"] if o["model"] == name and o["stock_status"] == "in_stock"]
        self.assertTrue(offers)
        href, rel = re.search(r'<a class="btn sm" href="([^"]+)" target="_blank" rel="([^"]+)">', pick).groups()
        self.assertIn("nofollow", rel)


class AllMinersAndInStock(unittest.TestCase):
    def test_in_stock_only_is_on_by_default_and_filters_fold_on_phones(self):
        h = read("/miners/")
        self.assertIn('name="stock" value="1" checked', h)
        self.assertIn('id="mftoggle"', h)
        self.assertIn('href="/compare/#pick"', h)

    def test_in_stock_list_is_cheapest_first(self):
        sec = read("/in-stock/").split('id="h-i"')[1].split("</section>")[0]
        prices = []
        for row in re.findall(r"<tr>(.*?)</tr>", sec, re.S):
            m = re.search(r'class="num price-cell">(?:[^<]*?)([$€]|CA\$)([\d,.]+)(?:<div class="cfg">≈ \$([\d,.]+))?', row)
            if m:
                prices.append(float((m.group(3) or m.group(2)).replace(",", "")))
        self.assertGreater(len(prices), 5)
        self.assertEqual(prices, sorted(prices))


class Counts(unittest.TestCase):
    def test_one_listing_count_everywhere(self):
        home = read("/")
        n_in = re.search(r'<strong data-count="(\d+)">\d+</strong> listings in stock', home).group(1)
        m = re.search(r"(\d+) of (\d+) listings in stock", read("/miners/"))
        self.assertEqual(m.group(1), n_in)
        self.assertIn(f"{n_in} of {m.group(2)} tracked listings are in stock", read("/in-stock/"))
        shops = sum(int(x) for x in re.findall(r"(\d+) in stock · prices in", read("/sellers/")))
        self.assertEqual(str(shops), n_in)

    def test_pages_that_come_and_go_redirect_instead_of_404(self):
        sitemap = (SITE / "sitemap.xml").read_text()
        for mid in LATEST["models"]:
            f = SITE / "models" / mid / "index.html"
            self.assertTrue(f.exists(), mid)
            if not any(o["model"] == mid for o in LATEST["offers"]):
                self.assertIn('http-equiv="refresh" content="0; url=/miners/"', f.read_text(), mid)
                self.assertNotIn(f"/models/{mid}/", sitemap)
        for sid in LATEST["sellers"]:
            self.assertTrue((SITE / "sellers" / sid / "index.html").exists(), sid)
        self.assertTrue((SITE / "compare" / "bitaxe-gamma-vs-nerdaxe-gamma" / "index.html").exists())


class BuyButtons(unittest.TestCase):
    def test_quiz_and_best_cards_go_straight_to_the_cheapest_shop(self):
        for path in ("/find-my-miner/", "/best/beginners/", "/"):
            h = read(path)
            buys = re.findall(r'<a class="btn buy" href="([^"]+)" target="_blank" rel="([^"]+)">View at ([^<]+), \$[\d,.]+ ↗</a>', h)
            self.assertTrue(buys, path)
            for href, rel, shop in buys:
                self.assertIn("nofollow", rel)
                sid = next(k for k, s in LATEST["sellers"].items() if s["name"] == unescape(shop))
                if sid in AFF:
                    self.assertIn("sponsored", rel)
                    self.assertIn(AFF[sid].strip("/"), href)
            self.assertIn("See all prices</a>", h)


class Chart(unittest.TestCase):
    def test_chart_has_a_stats_strip_and_is_never_drawn_hidden(self):
        h = read("/models/bitaxe-gamma/")
        self.assertIn('<dl class="pc-stats">', h)
        self.assertIn("<dt>Cheapest now</dt>", h)
        self.assertIn("<dt>Lowest in stock</dt>", h)
        self.assertIn('class="ln lead"', h)
        self.assertNotIn("scaleX(0)", (SITE / "style.css").read_text())


class Compare(unittest.TestCase):
    def test_pick_any_two(self):
        h = read("/compare/")
        data = json.loads(re.search(r'<script type="application/json" id="pickdata">(.*?)</script>', h, re.S).group(1))
        ids = set(data["m"])
        self.assertEqual(len(ids), int(re.search(r"<strong[^>]*>(\d+)</strong> miners tracked", read("/")).group(1)))
        self.assertEqual(h.count('<select name="a">'), 1)
        for mid, d in data["m"].items():
            if "p" in d:
                o = min((o for o in LATEST["offers"] if o["model"] == mid and o["stock_status"] == "in_stock" and o.get("price_usd_approx") is not None),
                        key=lambda o: o["price_usd_approx"], default=None)
                if o and d["stock"] == "in":
                    self.assertAlmostEqual(d["p"], o["price_usd_approx"], places=2)
        self.assertIn('href="/compare/?a=bitaxe-gamma#pick"', read("/models/bitaxe-gamma/"))
        self.assertNotIn("/compare/?", (SITE / "sitemap.xml").read_text())


class DealOfTheDay(unittest.TestCase):
    def test_card_has_photo_and_no_template_note(self):
        for p in ("/", "/deals/"):
            h = read(p)
            if 'class="dotd"' not in h:
                continue
            card = h.split('class="dotd"')[1].split("</section>")[0]
            self.assertIn('class="dotd-img"', card)
            self.assertNotIn("fixed template", card)
            self.assertIn('class="dotd-line"', card)


if __name__ == "__main__":
    unittest.main()
