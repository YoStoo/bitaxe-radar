"""collector/solo_wins.py: parses both sources, never invents hardware, keeps the last data when a fetch fails."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collector"))
import solo_wins as S  # noqa: E402

MP = {"solock": [{"id": "00ab", "height": 960804, "timestamp": 1785723060, "extras": {"reward": 315689830}}],
      "braiinssolo": [{"id": "00cd", "height": 970904, "timestamp": 1791700000, "extras": {"reward": 312898650}}]}
CSV = ("height,date,pool,hardware,hashrate_hs,difficulty,reward_btc,reward_usd_reported,expected_seconds_per_block,chance_per_day,chance_per_day_one_in,source_label,source_url,block_url,story,note\n"
       "970904,2026-10-11,Braiins Solo,hashrate not publicly reported,,1,3.129,,,,,x,x,x,,\n"
       "957382,2026-07-10,Public Pool,Bitaxe Gamma — 995 GH/s (~1 TH/s) palm-size,995000000000.0,1,3.1382,,,,,x,x,x,,\n"
       "958527,2026-07-18,Parasite Pool,360 PH/s rented for 9h — not owned hardware,,1,3.13,,,,,x,x,x,,\n"
       "965321,2026-09-03,untagged coinbase,hashrate not publicly reported,,1,3.138,,,,,x,x,x,,\n")


def fake(fail=()):
    def f(url):
        if any(x in url for x in fail):
            raise OSError("down")
        if "sololuck" in url:
            return CSV
        slug = url.split("/pool/")[1].split("/")[0]
        return json.dumps(MP.get(slug, []))
    return f


class SoloWins(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        S.OUT = Path(self.d.name) / "solo_wins.json"

    def tearDown(self):
        self.d.cleanup()

    def test_merge_and_attribution(self):
        data = S.run(fetch=fake())
        by = {w["height"]: w for w in data["wins"]}
        self.assertEqual([w["height"] for w in data["wins"]], sorted(by, reverse=True))
        self.assertEqual(by[970904]["pool"], "Braiins Solo")
        self.assertIsNone(by[970904]["hashrate_hs"])
        self.assertIsNone(by[970904]["hardware"])
        self.assertEqual(by[957382]["hardware"], "Bitaxe Gamma")
        self.assertEqual(by[957382]["hashrate_hs"], 995e9)
        self.assertTrue(by[958527]["rented"])
        self.assertIsNone(by[958527]["hashrate_hs"])
        self.assertNotIn(965321, by)                       # inferred untagged blocks are left out
        self.assertAlmostEqual(by[960804]["reward_btc"], 3.1568983)

    def test_fetch_failure_keeps_last_data(self):
        first = S.run(fetch=fake())
        again = S.run(fetch=fake(fail=("mempool", "sololuck")))
        self.assertEqual(len(again["wins"]), len(first["wins"]))
        self.assertEqual(again["fetched_at"], first["fetched_at"])
        part = S.run(fetch=fake(fail=("mempool",)))
        self.assertEqual(len(part["wins"]), len(first["wins"]))
        self.assertIn("failed", part["status"]["mempool.space"])


if __name__ == "__main__":
    unittest.main()
