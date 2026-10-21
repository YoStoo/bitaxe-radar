"""Sanity checks for the generated static site. Run after `python3 build_site.py`:
    python3 -m unittest tests/test_site.py -v
Checks: every page parses, has one h1, unique title/description, canonical, OG tags, valid JSON-LD, internal links and
anchors resolve, sitemap matches indexable pages, affiliate links carry rel=sponsored, noindex pages stay out of the sitemap."""
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

SITE = Path(__file__).resolve().parent.parent / "site"
BASE = "https://bitaxeradar.com"


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.ids, self.h1, self.title, self.meta, self.ld, self.canon, self.robots = [], set(), 0, "", {}, [], None, None
        self._t = self._ld = False
        self.stack, self.errors = [], []
        self.hrefs_rel = []

    def handle_starttag(self, tag, a):
        a = dict(a)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._t = True
        if tag == "a" and "href" in a:
            self.links.append(a["href"]); self.hrefs_rel.append((a["href"], a.get("rel", "")))
        if tag == "link" and a.get("rel") == "canonical":
            self.canon = a["href"]
        if tag == "meta":
            k = a.get("name") or a.get("property")
            if k:
                self.meta[k] = a.get("content", "")
        if tag == "script" and a.get("type") == "application/ld+json":
            self._ld = True; self.ld.append("")
        if tag in ("link", "script") and (a.get("href") or a.get("src")):
            u = a.get("href") or a.get("src")
            if u.startswith("/"):
                self.links.append(u)
        if tag not in ("meta", "link", "br", "img", "input", "hr", "circle", "line", "polyline", "path", "source"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self._t = False
        if tag == "script":
            self._ld = False
        if tag in ("meta", "link", "br", "img", "input", "hr", "circle", "line", "polyline", "path", "source"):
            return
        if tag == "circle":
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            self.errors.append(f"unclosed before </{tag}>: {self.stack[self.stack.index(tag):]}")
            while self.stack and self.stack.pop() != tag:
                pass
        else:
            self.errors.append(f"stray </{tag}>")

    def handle_data(self, d):
        if self._t:
            self.title += d
        if self._ld:
            self.ld[-1] += d


def parse(path):
    p = P(); p.feed(path.read_text()); p.close(); return p


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {}
        for f in sorted(SITE.rglob("index.html")) + [SITE / "404.html"]:
            rel = "/" + str(f.relative_to(SITE).parent).strip(".") + "/" if f.name == "index.html" else "/404.html"
            rel = rel.replace("//", "/")
            cls.pages[rel] = parse(f)
        sm = (SITE / "sitemap.xml").read_text()
        cls.sitemap = re.findall(r"<loc>(.*?)</loc>", sm)
        cls.lastmods = re.findall(r"<lastmod>(.*?)</lastmod>", sm)

    def test_expected_pages_exist(self):
        for want in ["/", "/models/bitaxe-gamma/", "/where-to-buy-bitaxe/", "/in-stock/", "/deals/", "/how-we-track/", "/sellers/solosatoshi/", "/compare/bitaxe-gamma-vs-nerdqaxe-pp/"]:
            self.assertIn(want, self.pages)

    def test_well_formed_and_meta(self):
        titles, descs = {}, {}
        for path, p in self.pages.items():
            self.assertEqual(p.errors, [], path)
            self.assertEqual(p.stack, [], path)
            self.assertEqual(p.h1, 1, f"{path} needs exactly one h1")
            self.assertTrue(p.title.strip(), path)
            self.assertNotIn(p.title, titles, f"duplicate title {path} / {titles.get(p.title)}")
            titles[p.title] = path
            d = p.meta.get("description", "")
            self.assertFalse(p.title.endswith("…"), f"{path} title was truncated")
            if path == "/404.html":
                continue
            self.assertFalse(d.endswith("…"), f"{path} description was truncated")
            self.assertTrue(70 <= len(d) <= 165, f"{path} description length {len(d)}")
            self.assertNotIn(d, descs, f"duplicate description {path}")
            descs[d] = path
            if path != "/404.html":
                self.assertEqual(p.canon, BASE + path, path)
                self.assertEqual(p.meta.get("og:url"), BASE + path, path)
            for k in ("og:title", "og:description", "og:image", "og:type", "twitter:card"):
                self.assertIn(k, p.meta, f"{path} missing {k}")

    def test_jsonld_parses(self):
        for path, p in self.pages.items():
            for raw in p.ld:
                obj = json.loads(raw)
                nodes = obj["@graph"] if "@graph" in obj else [obj]
                for n in nodes:
                    self.assertIn("@type", n, path)
                    self.assertNotIn("aggregateRating", n, path)
                    self.assertNotIn("review", n, path)
                    if n["@type"] == "Product":
                        offers = n["offers"]
                        for o in (offers["offers"] if isinstance(offers, dict) else offers):
                            self.assertRegex(o["price"], r"^\d+\.\d{2}$")
                            self.assertIn(o["priceCurrency"], ("USD", "EUR"))
                            self.assertTrue(o["availability"].startswith("https://schema.org/"))
        gamma = json.loads(self.pages["/models/bitaxe-gamma/"].ld[0])
        self.assertEqual(gamma["@type"], "Product")

    def test_internal_links_resolve(self):
        for path, p in self.pages.items():
            for href in p.links:
                if href.startswith(("mailto:", "http://", "https://", "#")):
                    continue
                u = urlparse(href)
                target = u.path
                f = SITE / target.lstrip("/")
                if target.endswith("/"):
                    f = f / "index.html"
                self.assertTrue(f.exists(), f"{path}: broken link {href}")
                if u.fragment and f.suffix == ".html":
                    tgt = self.pages.get(target if target.endswith("/") else target)
                    if tgt is not None:
                        self.assertIn(u.fragment, tgt.ids, f"{path}: missing anchor {href}")

    def test_in_page_anchors(self):
        for path, p in self.pages.items():
            for href in p.links:
                if href.startswith("#") and len(href) > 1:
                    self.assertIn(href[1:], p.ids, f"{path}: {href}")

    def test_sitemap(self):
        self.assertEqual(len(self.sitemap), len(set(self.sitemap)))
        self.assertEqual(len(self.sitemap), len(self.lastmods))
        for u in self.sitemap:
            path = u[len(BASE):]
            self.assertIn(path, self.pages, u)
            self.assertNotIn("noindex", self.pages[path].meta.get("robots", ""), f"{u} noindex but in sitemap")
        indexable = {p for p, pg in self.pages.items() if "noindex" not in pg.meta.get("robots", "")}
        self.assertEqual({u[len(BASE):] for u in self.sitemap}, indexable)
        self.assertIn("/models/bitaxe-supra/", self.pages)
        self.assertIn("noindex", self.pages["/models/bitaxe-supra/"].meta.get("robots", ""))
        self.assertRegex((SITE / "robots.txt").read_text(), r"Sitemap: https://bitaxeradar\.com/sitemap\.xml")

    def test_affiliate_links_sponsored(self):
        app = (SITE / "app.js").read_text()
        self.assertIn("ref=bitaxeradar", app)
        seen = 0
        for path, p in self.pages.items():
            for href, rel in p.hrefs_rel:
                if "powermining.io" in href and "/products/" in href:
                    seen += 1
                    self.assertIn("ref=bitaxeradar", href, path)
                    self.assertIn("sponsored", rel, path)
                    self.assertIn("nofollow", rel, path)
                elif href.startswith("http") and "bitaxeradar.com" not in href and "/products/" in href:
                    self.assertNotIn("ref=", href, f"{path}: unexpected tracking param {href}")
        self.assertGreater(seen, 0)

    def test_model_pages_have_signup_and_prerendered_prices(self):
        for mid in ["bitaxe-gamma", "nerdqaxe-pp", "bitaxe-gt-801"]:
            p = self.pages[f"/models/{mid}/"]
            self.assertIn("signup", p.ids)
            html = (SITE / "models" / mid / "index.html").read_text()
            self.assertRegex(html, r"\$\d+\.\d{2}")
            self.assertIn("signup.js", html)
            self.assertIn("affiliate", html.lower())
        home = (SITE / "index.html").read_text()
        self.assertIn('id="signup"', home)
        self.assertIn("/models/bitaxe-gamma/", home)


    def test_black_friday_page(self):
        self.assertIn("/bitaxe-black-friday/", self.pages)
        self.assertIn(BASE + "/bitaxe-black-friday/", self.sitemap)
        html = (SITE / "bitaxe-black-friday" / "index.html").read_text()
        self.assertIn("November 27", html)
        self.assertIn('id="alerts"', html) if 'id="alerts"' in (SITE / "models" / "bitaxe-gamma" / "index.html").read_text() else None

    def test_cta_sponsor_and_advertise(self):
        self.assertIn("/advertise/", self.pages)
        self.assertIn(BASE + "/advertise/", self.sitemap)
        adv = (SITE / "advertise" / "index.html").read_text()
        self.assertIn("mailto:contact@bitaxeradar.com", adv)
        for mid in ["bitaxe-gamma", "nerdqaxe-pp"]:
            html = (SITE / "models" / mid / "index.html").read_text()
            self.assertIn('class="sponsor"', html)
            self.assertIn('href="/advertise/"', html)
            if "Cheapest in stock</small>" in html:
                self.assertIn('class="cta"', html)
        # analytics tag only when a real 32-hex token is configured
        app = (SITE / "app.js").read_text()
        tok = re.search(r'var CF_BEACON_TOKEN\s*=\s*"([^"]*)"', app).group(1)
        home = (SITE / "index.html").read_text()
        self.assertEqual("cloudflareinsights" in home, bool(re.fullmatch(r"[0-9a-f]{32}", tok)))

    def test_no_internal_notes_public(self):
        """Owner-only material (scrape limits, untracked-seller lists, traffic caveats, affiliate pipeline notes) stays off public pages."""
        banned = ["not tracked yet", "cannot track", "cannot read", "we cannot", "unscrapable", "prototype", "meaningful visitor numbers",
                  "not yet joined", "bot protection", "curl exit", "[affiliate link placeholder]"]
        for f in list(SITE.rglob("*.html")) + [SITE / "data.js", SITE / "app.js"]:
            txt = f.read_text().lower()
            for b in banned:
                self.assertNotIn(b, txt, f"{f.relative_to(SITE)} contains internal text: {b!r}")

    def test_home_cards_and_brand(self):
        home = (SITE / "index.html").read_text()
        self.assertIn('id="miners"', home)
        self.assertGreaterEqual(home.count('class="card'), 4)
        self.assertIn('class="logo-mark"', home)
        self.assertIn('id="cost"', home)
        self.assertIn("signup.js", home)
        self.assertIn("<svg", (SITE / "favicon.svg").read_text())
        # every product photo referenced anywhere exists and carries alt text and explicit dimensions
        for f in list(SITE.rglob("*.html")):
            for tag in re.findall(r"<img [^>]*>", f.read_text()):
                src = re.search(r'src="([^"]+)"', tag).group(1)
                self.assertTrue((SITE / src.lstrip("/")).exists(), f"{f}: missing image {src}")
                self.assertRegex(tag, r'alt="[^"]{8,}"')
                self.assertRegex(tag, r'width="\d+" height="\d+"')
        self.assertIn('loading="lazy"', home)
        # every card price comes from the data (no invented numbers): each shown price matches a current in-stock offer
        data = json.loads((SITE / "data.js").read_text()[len("window.RADAR = "):-2])
        live = {f"{o['price_usd_approx']:,.2f}" for o in data["latest"]["offers"] if o["in_stock"] and o.get("price_usd_approx") is not None}
        for price in re.findall(r'<div class="price">(?:≈ )?\$([\d,]+\.\d{2})', home):
            self.assertIn(price, live)


if __name__ == "__main__":
    unittest.main()
