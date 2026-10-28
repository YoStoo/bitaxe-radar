"""with_aff: query-style codes (?ref=) vs path-style codes (Solo Satoshi .../aff/8840/). Same helper in all three link builders."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(rel):
    src = (ROOT / rel).read_text()
    ns = {}
    start = src.index("def with_aff(")
    end = src.index("\ndef ", start + 1)
    exec(src[start:end], ns)
    return ns["with_aff"]


class WithAff(unittest.TestCase):
    CASES = [
        ("https://www.solosatoshi.com/product/bitaxe-gamma/", "aff/8840/", "https://www.solosatoshi.com/product/bitaxe-gamma/aff/8840/"),
        ("https://www.solosatoshi.com/product/bitaxe-gamma", "aff/8840/", "https://www.solosatoshi.com/product/bitaxe-gamma/aff/8840/"),
        ("https://www.solosatoshi.com/product/bitaxe-gamma/?attribute_color=black", "aff/8840/",
         "https://www.solosatoshi.com/product/bitaxe-gamma/aff/8840/?attribute_color=black"),
        ("https://www.solosatoshi.com/", "aff/8840/", "https://www.solosatoshi.com/aff/8840/"),
        ("https://www.solosatoshi.com/product/x/aff/8840/", "aff/8840/", "https://www.solosatoshi.com/product/x/aff/8840/"),
        ("https://powermining.shop/products/a", "ref=bitaxeradar", "https://powermining.shop/products/a?ref=bitaxeradar"),
        ("https://powermining.shop/products/a?v=1", "ref=bitaxeradar", "https://powermining.shop/products/a?v=1&ref=bitaxeradar"),
        ("https://x.com/p", None, "https://x.com/p"),
    ]

    def test_all_copies(self):
        for rel in ["build_site.py", "newsletter.py", "scripts/send_alerts.py"]:
            f = load(rel)
            for url, code, want in self.CASES:
                self.assertEqual(f(url, code), want, (rel, url))


if __name__ == "__main__":
    unittest.main()
