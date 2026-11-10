"""RAG index builder (scripts/build_rag_index.py): cleaning, chunking, citations metadata."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_rag_index as B  # noqa: E402

PAGE = """<html><body><nav>Menu Home Guides</nav><main><article>
<header><h1>How loud are home miners?</h1><p class="lede">Noise is the top question.</p>
<p class="meta">Updated Nov 10, 2026 7:17 AM ET · 3-minute read</p></header>
<section><h2>1. The short answer</h2><ul><li><strong>Want silent:</strong> fanless heaters.</li>
<li>Quiet desk miners are near 30&ndash;40 dB.</li></ul></section>
<section><h2>2. Noise table</h2><table><tr><th>Miner</th><th>Stated noise</th><th>Today's price</th></tr>
<tr><td><a href="/m/">BitForge Nano</a></td><td>29 dB</td><td>$169.99</td></tr></table></section>
<section><h2>3. Long part</h2><p>""" + " ".join(f"Sentence number {i} says something useful about fans." for i in range(40)) + """</p></section>
<section><h2>Keep reading</h2><ul><li><a href="/guides/x/">Another guide</a></li></ul></section>
<script>var x = "do not index";</script></article></main></body></html>"""


class RagIndexTest(unittest.TestCase):
    def chunks(self):
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "guides" / "bitaxe-noise"
            page.mkdir(parents=True)
            (page / "index.html").write_text(PAGE)
            old = B.SITE
            B.SITE = Path(d)
            try:
                return B.page_chunks(page)
            finally:
                B.SITE = old

    def test_metadata_for_citations(self):
        c = self.chunks()
        self.assertEqual({x["guide"] for x in c}, {"bitaxe-noise"})
        self.assertEqual({x["url"] for x in c}, {"/guides/bitaxe-noise/"})
        self.assertEqual(c[0]["title"], "How loud are home miners?")
        self.assertEqual([x["id"] for x in c], [f"bitaxe-noise#{i}" for i in range(len(c))])

    def test_cleaning(self):
        text = " ".join(x["text"] for x in self.chunks())
        self.assertIn("Quiet desk miners are near 30–40 dB.", text)
        self.assertIn("Miner: BitForge Nano; Stated noise: 29 dB.", text)    # table kept as readable rows
        for gone in ("$169.99", "Today's price", "Updated Nov 10", "Menu", "do not index", "Another guide"):
            self.assertNotIn(gone, text)

    def test_sections_short_ones_merged_long_ones_split_with_overlap(self):
        c = self.chunks()
        sections = [x["section"] for x in c]
        self.assertNotIn("Keep reading", sections)
        self.assertEqual(sections[0], "Intro")       # the lede is under MIN_CHARS so it merges forward
        self.assertIn("Want silent", c[0]["text"])
        long = [x for x in c if x["section"] == "Long part"]
        self.assertGreater(len(long), 1)
        self.assertTrue(all(len(x["text"]) <= B.MAX_CHARS + 80 for x in long))
        last_sentence = B.split_sentences(long[0]["text"])[-1]
        self.assertTrue(long[1]["text"].startswith(last_sentence), "one-sentence overlap between pieces")

    def test_committed_index_shape_and_coverage(self):
        idx = json.loads((ROOT / "worker" / "src" / "rag_chunks.json").read_text())
        self.assertEqual(set(idx), {"version", "guides", "chunks"})
        self.assertGreaterEqual(len(idx["chunks"]), 50)
        for c in idx["chunks"]:
            self.assertIn(c["guide"], idx["guides"])
            self.assertEqual(set(c), {"id", "guide", "section", "text"})
        # Every guide page the site builds is in the index (rebuild it after adding a guide).
        built = {p.parent.name for p in (ROOT / "site" / "guides").glob("*/index.html")}
        self.assertTrue(built <= set(idx["guides"]), f"missing from RAG index: {built - set(idx['guides'])}; "
                        "run python3 scripts/build_rag_index.py")


if __name__ == "__main__":
    unittest.main()
