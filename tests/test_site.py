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
            if path in ("/404.html", "/home-miners/", "/about/"):     # 404 and the redirect stub (canonical points at /miners/)
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
                            self.assertIn(o["priceCurrency"], ("USD", "EUR", "CAD"))
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

    def test_solosatoshi_affiliate_links(self):
        """Solo Satoshi approved us Oct 26, 2026 (affiliate 8840): product links use their path style .../aff/8840/ (from their
        dashboard's link generator), exactly one slash, with rel sponsored and the 'affiliate link' label."""
        seen = 0
        for path, p in self.pages.items():
            for href, rel in p.hrefs_rel:
                if "solosatoshi.com/product/" in href:
                    seen += 1
                    url = href.split("?")[0].split("#")[0]
                    self.assertRegex(url, r"^https://www\.solosatoshi\.com/product/[^?#]*[^/]/aff/8840/$", path)
                    self.assertNotIn("aff=", href, path)
                    self.assertIn("sponsored", rel, path)
                    self.assertIn("nofollow", rel, path)
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


    def test_home_miners_hub_and_guides(self):
        data = json.loads((SITE / "data.js").read_text()[len("window.RADAR = "):-2])
        models = data["latest"]["models"]
        home_ids = [m for m, v in models.items() if v.get("category") == "home" and any(o["model"] == m for o in data["latest"]["offers"])]
        self.assertGreaterEqual(len(home_ids), 5)
        for path in ["/miners/", "/guides/solo-vs-pool-mining/", "/guides/how-heater-miners-work/"]:
            self.assertIn(path, self.pages)
            self.assertIn(BASE + path, self.sitemap)
        hub = (SITE / "miners" / "index.html").read_text()
        for mid in home_ids:
            self.assertIn(f'href="/models/{mid}/"', hub, mid)
            self.assertIn(BASE + f"/models/{mid}/", self.sitemap)
            if (SITE / "img" / "models" / f"{mid}.webp").exists():      # models without a reliable seller photo keep the drawn placeholder
                self.assertIn(f"/img/models/{mid}.webp", hub, f"{mid} has no product photo on /miners/")
        # old hub URL redirects to /miners/ and stays out of the sitemap
        old = (SITE / "home-miners" / "index.html").read_text()
        self.assertIn('url=/miners/', old)
        self.assertIn(f'rel="canonical" href="{BASE}/miners/"', old)
        self.assertNotIn(BASE + "/home-miners/", self.sitemap)
        # one menu on every page: All miners · Deals · Find my miner · Guides + Alerts, no sideways scroller
        want = ["/miners/", "/deals/", "/find-my-miner/", "/guides/", "/alerts/"]
        for f in list(SITE.rglob("*.html")):
            if f.parent.name in ("home-miners", "about"):
                continue
            nav = re.search(r'<nav aria-label="Main">(.*?)</nav>', f.read_text(), re.S)
            self.assertIsNotNone(nav, str(f))
            self.assertEqual(re.findall(r'<a[^>]*href="([^"]+)"', nav.group(1)), want, str(f))
        css = (SITE / "style.css").read_text()
        self.assertNotRegex(re.search(r"\.top nav\{[^}]*\}", css).group(0), "overflow-x")
        # Bitaxe-only home sections still exclude home miners (Deals and In stock now cover everything)
        for page in ["where-to-buy-bitaxe/index.html"]:   # (the Black Friday tracker covers every miner type since Oct 25)
            txt = (SITE / page).read_text()
            for mid in home_ids:
                self.assertNotIn(f'href="/models/{mid}/"', txt.split('<footer')[0].split('id="alerts"')[0], f"{page} lists {mid}")
        cards = (SITE / "index.html").read_text().split('id="miners"')[1].split("</section>")[0]
        for mid in home_ids:
            self.assertNotIn(f'href="/models/{mid}/"', cards, f"home Bitaxe cards list {mid}")
        deals = (SITE / "deals" / "index.html").read_text()
        self.assertTrue(any(f'href="/models/{m}/"' in deals for m in home_ids), "deals should cover all miners")
        # no earnings promises on the explainers
        for g in ["guides/solo-vs-pool-mining/index.html", "guides/how-heater-miners-work/index.html", "miners/index.html"]:
            txt = (SITE / g).read_text().lower()
            for bad in ["guaranteed income", "passive income", "pays for itself", "per day profit", "profit of $"]:
                self.assertNotIn(bad, txt, g)

    def test_unapproved_sellers_plain_links(self):
        """Only Power Mining carries an affiliate param; links to shops we are not approved with stay plain."""
        for path, p in self.pages.items():
            for href, rel in p.hrefs_rel:
                if any(d in href for d in ("altairtech.io", "heatbit.com", "d-central.tech", "braiinsforge.com", "bitcoinmerch.com")):
                    self.assertNotRegex(href, r"[?&](ref|aff|affiliate|sca_ref|wpam_id)=", f"{path}: {href}")
                    self.assertNotIn("sponsored", rel, f"{path}: {href}")

    def test_browse_category_pages(self):
        data = json.loads((SITE / "data.js").read_text()[len("window.RADAR = "):-2])
        tracked = {o["model"] for o in data["latest"]["offers"]}
        expect = {"/solo-miners/": (["bitaxe-gamma", "nerdqaxe-pp", "braiins-bmm-101"], ["avalon-q", "heatbit-maxi"], "Best for solo mining"),
                  "/pool-miners/": (["avalon-q", "avalon-mini-3", "heatbit-maxi"], ["bitaxe-gamma"], "Best for pool mining"),
                  "/heater-miners/": (["heatbit-trio", "heatbit-maxi", "heatbit-canvas", "avalon-mini-3"], ["bitaxe-gamma", "braiins-bmm-101"], "Heater miners")}
        for path, (yes, no, h1) in expect.items():
            self.assertIn(path, self.pages)
            self.assertIn(BASE + path, self.sitemap)
            html = (SITE / path.strip("/") / "index.html").read_text()
            self.assertIn(f"<h1>{h1}</h1>", html)
            self.assertIn('aria-current="page"', html.split("</header>", 2)[1])   # browse pill marks the current page
            self.assertIn("/guides/solo-vs-pool-mining/", html)
            for m in yes:
                if m in tracked:
                    self.assertIn(f'<h3><a href="/models/{m}/">', html, f"{path} should list {m}")
                    self.assertIn(f"/img/models/{m}.webp", html)
            for m in no:
                self.assertNotIn(f'href="/models/{m}/"', html.split("<footer")[0], f"{path} should not list {m}")
            for bad in ["guaranteed", "passive income", "pays for itself", "profit of $"]:
                self.assertNotIn(bad, html.lower(), path)
        solo = (SITE / "solo-miners" / "index.html").read_text()
        self.assertNotIn('<h3><a href="/models/bitaxe-supra/">', solo)          # older noindex models only in the small "Older models" line
        home = (SITE / "index.html").read_text()
        for cat in ("/solo-miners/", "/pool-miners/", "/heater-miners/"):
            self.assertIn(f'class="btile" href="{cat}"', home)
        self.assertIn('class="tag" href="/solo-miners/"', (SITE / "models" / "bitaxe-gamma" / "index.html").read_text())
        q = (SITE / "models" / "avalon-q" / "index.html").read_text()
        self.assertIn('class="tag" href="/pool-miners/"', q)
        self.assertIn('class="tag" href="/heater-miners/"', q)
        self.assertIn("/home-miners/", self.pages)    # old hub URL keeps working

    def test_earnings_estimates_on_pages(self):
        net = json.loads((SITE.parent / "data" / "network.json").read_text())
        for k in ("network_hashrate_hs", "btc_usd", "avg_fees_btc", "subsidy_btc", "fetched_at"):
            self.assertIn(k, net)
        g = (SITE / "models" / "bitaxe-gamma" / "index.html").read_text()
        if 'id="h-earn"' not in g:
            self.skipTest("network inputs stale; estimates hidden by design")
        self.assertIn("Solo block chance", g)
        self.assertIn("Estimate. Changes with Bitcoin price and network difficulty.", g)
        self.assertIn("$0.15/kWh", g)
        q = (SITE / "models" / "avalon-q" / "index.html").read_text()
        self.assertIn("heat offsets this", q)
        self.assertNotIn("Solo block chance", q)
        self.assertIn('class="cardline"', (SITE / "index.html").read_text())

    def test_best_for_pages_and_llms(self):
        best = sorted(p for p in self.pages if p.startswith("/best/") and p != "/best/")
        self.assertTrue({"/best/beginners/", "/best/quiet/", "/best/heating-a-room/"} <= set(best), best)
        home = (SITE / "index.html").read_text()
        for path in best:
            self.assertIn(BASE + path, self.sitemap)
            self.assertIn(f'href="{path}"', home)                       # "Best for" row on the home page
            p = self.pages[path]
            faqs = [json.loads(x) for x in p.ld if '"FAQPage"' in x]
            self.assertEqual(len(faqs), 1, path)
            qs = faqs[0]["mainEntity"]
            self.assertGreaterEqual(len(qs), 2)
            html = (SITE / path.strip("/") / "index.html").read_text()
            for q in qs:                                                 # FAQ markup must match visible questions
                self.assertIn(q["acceptedAnswer"]["text"].replace("'", "&#x27;").replace("&", "&amp;").replace("&amp;#x27;", "&#x27;"), html)
            self.assertIn('class="ribbon rank">#1<', html)
            self.assertIn('class="why"', html)
            for bad in ["guaranteed income", "passive income", "pays for itself", "profit of $"]:
                self.assertNotIn(bad, html.lower(), path)
        quiet = (SITE / "best" / "quiet" / "index.html").read_text()
        self.assertNotIn('href="/models/avalon-q/"', quiet.split("<footer")[0])     # loud at full power, not a quiet pick
        self.assertNotIn('<h3><a href="/models/bitaxe-gamma/">', quiet)             # no published dB figure
        if "/best/under-100/" in self.pages:
            u = (SITE / "best" / "under-100" / "index.html").read_text().split('id="h-more"')[0]
            for price in re.findall(r'<div class="price">(?:≈ )?\$([\d,]+\.\d{2})', u):
                self.assertLess(float(price.replace(",", "")), 100)
        heat = (SITE / "best" / "heating-a-room" / "index.html").read_text()
        self.assertIn('<h3><a href="/models/avalon-mini-3/">', heat)
        llms = (SITE / "llms.txt").read_text()
        self.assertTrue(llms.startswith("# Bitaxe Radar\n\n> "))
        for need in ("/solo-miners/", "/best/beginners/", "/models/bitaxe-gamma/", "/guides/solo-vs-pool-mining/", "llms-full.txt"):
            self.assertIn(need, llms)
        full = (SITE / "llms-full.txt").read_text()
        self.assertIn("### Bitaxe Gamma", full)
        self.assertIn("llms.txt", (SITE / "robots.txt").read_text())
        for t in (llms, full):
            for b in ["not tracked yet", "unscrapable", "bot protection", "passive income"]:
                self.assertNotIn(b, t.lower())


if __name__ == "__main__":
    unittest.main()


class NavBuildTests(unittest.TestCase):
    """docs/NAV_AUDIT.md: /miners/ filters, quiz, alerts page, index pages, breadcrumbs, quick fixes."""

    def read(self, path):
        return (SITE / path.strip("/") / "index.html").read_text() if path != "/" else (SITE / "index.html").read_text()

    def test_index_pages_and_quiz(self):
        for path in ["/miners/", "/find-my-miner/", "/alerts/", "/models/", "/sellers/", "/best/", "/guides/", "/compare/"]:
            self.assertTrue((SITE / path.strip("/") / "index.html").exists(), path)
        q = self.read("/find-my-miner/")
        self.assertEqual(q.count('<fieldset class="q">'), 3)
        for name in ("budget", "goal", "place"):
            self.assertIn(f'name="{name}"', q)
        self.assertIn("<noscript>", q)
        m = self.read("/miners/")
        self.assertIn('id="mf"', m)                       # filters, hidden until JS runs; every card is in the HTML
        for k in ("type", "price", "power", "stock", "sort"):
            self.assertIn(f'name="{k}"', m)
        self.assertGreaterEqual(m.count("data-price="), 20)
        self.assertIn('id="signup"', self.read("/alerts/"))
        home = self.read("/")
        self.assertRegex(home, r"<h1>Home Bitcoin miners, <span class=\"hl\">price-checked</span> across \d+ shops\.</h1>")
        self.assertIn('href="/find-my-miner/"', home.split("</section>")[0])

    def test_seller_facts_table(self):
        idx = self.read("/sellers/")
        self.assertIn('<table class="facts">', idx)
        self.assertIn("Ships from", idx)
        self.assertIn("St. Louis, Missouri", idx)
        self.assertRegex(idx, r"\d+%<br><span class=\"cfg\">of \d+ checks")
        page = self.read("/sellers/altair/")
        self.assertIn("Shop facts", page)
        self.assertIn("14 days against defects", page)

    def test_breadcrumbs(self):
        crumbs = lambda h: re.findall(r'<a href="([^"]+)">', re.search(r'<nav class="crumbs"[^>]*>(.*?)</nav>', h, re.S).group(1))
        self.assertEqual(crumbs(self.read("/models/bitaxe-gamma/")), ["/", "/miners/", "/solo-miners/"])
        self.assertEqual(crumbs(self.read("/models/avalon-q/")), ["/", "/miners/", "/heater-miners/"])
        self.assertEqual(crumbs(self.read("/solo-miners/")), ["/", "/miners/"])
        self.assertEqual(crumbs(self.read("/sellers/altair/")), ["/", "/sellers/"])
        self.assertEqual(crumbs(self.read("/best/quiet/")), ["/", "/best/"])

    def test_quick_fixes(self):
        solo = self.read("/solo-miners/")
        head = solo.split("<h1>")[1].split("</header>")[0]
        self.assertEqual(head.count('class="browse"'), 1)                     # one type row (plus the best-for row)
        cards = re.findall(r'<h3><a href="/models/([^/]+)/">', solo)
        home = self.read("/")
        n = int(re.search(r'class="btile" href="/solo-miners/">.*?<small>(\d+) miners</small>', home, re.S).group(1))
        self.assertEqual(n, len(cards))                                       # tile count matches the page
        prices = []
        for art in re.findall(r'<article class="card">(.*?)</article>', solo, re.S):
            if 'b-in_stock' in art:
                prices.append(float(re.search(r'<div class="price">(?:≈ )?\$([\d,.]+)', art).group(1).replace(",", "")))
        self.assertEqual(prices, sorted(prices))                              # cheapest first
        foot = home.split('<footer')[1]
        for p in ("/how-we-track/", "/advertise/", "/bitaxe-black-friday/"):
            self.assertIn(f'href="{p}"', foot)
        nav = re.search(r'<nav aria-label="Main">(.*?)</nav>', home, re.S).group(1)
        for p in ("/how-we-track/", "/advertise/", "/bitaxe-black-friday/"):
            self.assertNotIn(p, nav)
        css = (SITE / "style.css").read_text()
        self.assertIn(".btn.sm{padding:7px 12px;font-size:13.5px;min-height:40px}", css)
        self.assertRegex(css, r"\.foot \.foot-cols a\{[^}]*min-height:40px")
