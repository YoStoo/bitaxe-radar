"""New-low detection (newlows.py) on small hand-made data, plus the box on /price-per-th/ (run after build_site.py)."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import newlows  # noqa: E402

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
MODELS = {"m": {"hashrate_ths": 1.2, "watts": 18}}


def offer(oid, price, stock="in_stock", seller="s1"):
    return dict(id=oid, model="m", seller=seller, price=price, price_usd_approx=price, currency="USD", stock_status=stock)


def pt(day, price, ins=True):
    return dict(t=f"2026-10-{day:02d}T12:00:00Z", price=price, in_stock=ins)


class NewLows(unittest.TestCase):
    def test_price_drop_below_old_low_is_a_new_low(self):
        h = {"a": [pt(16, 120), pt(18, 120), pt(22, 99)]}
        [d] = newlows.new_lows(MODELS, [offer("a", 99)], h, NOW)
        self.assertEqual((d["kind"], round(d["old_low"], 2), round(d["new_low"], 2)), ("drop", 120, 99))

    def test_drop_that_is_not_below_old_low_is_ignored(self):
        h = {"a": [pt(16, 90), pt(18, 120), pt(22, 100)]}
        self.assertEqual(newlows.new_lows(MODELS, [offer("a", 100)], h, NOW), [])

    def test_restock_at_lower_price_counts_as_restock(self):
        h = {"a": [pt(16, 120), pt(20, 120)], "b": [pt(16, 70, False), pt(21, 70, True)]}
        [d] = newlows.new_lows(MODELS, [offer("a", 120), offer("b", 70, seller="s2")], h, NOW)
        self.assertEqual((d["kind"], d["seller"]), ("restock", "s2"))

    def test_new_listing_first_point_is_not_an_event(self):
        h = {"a": [pt(16, 120), pt(20, 120)], "b": [pt(21, 60)]}
        self.assertEqual(newlows.new_lows(MODELS, [offer("a", 120), offer("b", 60, seller="s2")], h, NOW), [])

    def test_hidden_once_price_goes_back_up_or_old(self):
        h = {"a": [pt(16, 120), pt(18, 120), pt(22, 99), pt(23, 110)]}
        self.assertEqual(newlows.new_lows(MODELS, [offer("a", 110)], h, NOW), [])
        h = {"a": [pt(1, 120), pt(4, 120), pt(10, 99)]}
        self.assertEqual(newlows.new_lows(MODELS, [offer("a", 99)], h, NOW, days=7), [])

    def test_too_little_history_is_not_a_low(self):
        h = {"a": [pt(22, 120), pt(23, 99)]}
        self.assertEqual(newlows.new_lows(MODELS, [offer("a", 99)], h, datetime(2026, 10, 23, 13, tzinfo=timezone.utc)), [])

    def test_box_on_leaderboard(self):
        page = ROOT / "site" / "price-per-th" / "index.html"
        if not page.exists():
            self.skipTest("run build_site.py first")
        self.assertIn('id="h-lows">New lows this week</h2>', page.read_text())


if __name__ == "__main__":
    unittest.main()
