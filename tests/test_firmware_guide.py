"""The firmware roundup guide: built, linked, and every row names an open-source repo."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_site as B  # noqa: E402

PAGE = ROOT / "site/guides/bitaxe-firmware/index.html"


class FirmwareGuide(unittest.TestCase):
    def test_page_built_and_linked(self):
        self.assertTrue(PAGE.exists())
        for f in ["site/guides/index.html", "site/sitemap.xml", "site/llms.txt", "site/guides/is-my-bitaxe-normal/index.html"]:
            self.assertIn("/guides/bitaxe-firmware/", (ROOT / f).read_text(), f)

    def test_rows_sourced(self):
        t = PAGE.read_text()
        for name, _, repo, lic, ver, *_ in B.FIRMWARE:
            self.assertTrue(repo.startswith("https://github.com/"), name)
            self.assertIn(repo, t)
            self.assertIn(ver, t)
            for m in B.FIRMWARE[0][7]:
                self.assertIn(m, B.MODELS)

    def test_no_internal_text(self):
        t = PAGE.read_text()
        self.assertIsNone(re.search(r"TODO|placeholder|lorem|Shervin|Wilkinson", t, re.I))


if __name__ == "__main__":
    unittest.main()
