"""Earnings math: known inputs -> expected outputs, fee and haircut applied, rounding down, stale fallback."""
import json
import math
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import earnings as E  # noqa: E402

NET = {"network_hashrate_hs": 1e21, "subsidy_btc": 3.125, "avg_fees_btc": 0.075, "btc_usd": 100_000.0,
       "difficulty": 1.4e14, "fetched_at": "2026-10-21T12:00:00Z"}


class EarningsMath(unittest.TestCase):
    def test_pool_estimate_known_inputs(self):
        # 1 PH/s on a 1,000 EH/s network = 1e-6 share; 144 blocks x 3.2 BTC = 460.8 BTC/day network-wide
        e = E.pool_estimate(1000, NET)
        raw_btc = 1e-6 * 144 * 3.2
        self.assertAlmostEqual(e["btc_day"], raw_btc * 0.98 * 0.90)          # 2% pool fee, then 10% haircut
        self.assertAlmostEqual(e["usd_day"], 46.08 * 0.882)                  # 40.64256
        self.assertAlmostEqual(e["usd_month"], 46.08 * 0.882 * 365 / 12)
        self.assertEqual(e["usd_day_shown"], 40.64)
        self.assertEqual(e["usd_month_shown"], math.floor(46.08 * 0.882 * 365 / 12))   # 1236, rounded down

    def test_haircut_and_fee_lower_the_estimate(self):
        full = E.pool_estimate(90, NET, fee=0, haircut=0)["usd_month"]
        est = E.pool_estimate(90, NET)["usd_month"]
        self.assertAlmostEqual(est / full, 0.882)
        self.assertLess(est, full)

    def test_round_down(self):
        self.assertEqual(E.round_down_money(1.159), 1.15)
        self.assertEqual(E.round_down_money(86.99), 86.0)
        self.assertEqual(E.pool_estimate(1.2, NET)["usd_month_shown"], 1.48)     # 1.2 TH/s -> $1.4835/mo -> $1.48

    def test_power_cost(self):
        self.assertAlmostEqual(E.power_cost_month(1000, 0.15), 24 * 365 / 12 * 0.15)   # 1 kW, 24/7 = 730 kWh -> $109.50
        self.assertAlmostEqual(E.power_cost_month(18), 18 / 1000 * 730 * 0.15)

    def test_solo_odds(self):
        o = E.solo_odds(1.2, NET)
        p = 1.2e12 / 1e21 * 144
        self.assertAlmostEqual(o["one_in_day"], 1 / p)
        self.assertAlmostEqual(o["one_in_year"], 1 / (1 - (1 - p) ** 365))
        self.assertAlmostEqual(o["block_usd"], 320_000)
        self.assertEqual(E.fmt_big(5_787_037), "5.8 million")
        self.assertEqual(E.fmt_big(15_855), "16,000")

    def test_fallback_and_stale(self):
        now = datetime(2026, 10, 21, 13, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "network.json"
            ok = lambda now: dict(NET, fetched_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
            def boom(now):
                raise OSError("down")
            data, fresh = E.load_network(path, fetch=ok, now=now)
            self.assertTrue(fresh)
            self.assertEqual(json.loads(path.read_text())["btc_usd"], 100_000.0)
            data, fresh = E.load_network(path, fetch=boom, now=now + timedelta(hours=30))
            self.assertTrue(fresh)                                   # cached values, still under 48h
            data, fresh = E.load_network(path, fetch=boom, now=now + timedelta(hours=49))
            self.assertFalse(fresh)                                  # too old: pages hide the estimates
            self.assertEqual(E.load_network(Path(d) / "missing.json", fetch=boom, now=now), (None, False))


if __name__ == "__main__":
    unittest.main()
