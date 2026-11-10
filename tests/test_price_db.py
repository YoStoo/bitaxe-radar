"""SQL price history (collector/price_db.py): schema, idempotent upserts, daily rule, text dump."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collector"))
import price_db as P  # noqa: E402

LATEST = {
    "generated_at": "2026-11-10T12:00:00Z", "fx": {"EUR_USD": 1.1},
    "models": {"bitaxe-gamma": {"name": "Bitaxe Gamma", "chip": "BM1370", "hashrate_ths": 1.2, "watts": 18}},
    "sellers": {"shopa": {"name": "Shop A", "currency": "USD"}, "shopb": {"name": "Shop B", "currency": "EUR"}},
    "offers": [
        {"id": "shopa:bitaxe-gamma", "model": "bitaxe-gamma", "seller": "shopa", "price": 99, "currency": "USD",
         "in_stock": True, "stale": False, "checked_at": "2026-11-10T12:00:00Z"},
        {"id": "shopb:bitaxe-gamma", "model": "bitaxe-gamma", "seller": "shopb", "price": 100, "currency": "EUR",
         "in_stock": True, "stale": True, "checked_at": "2026-11-09T12:00:00Z"},   # stale: carried forward, not re-read
    ],
}


def fresh():
    return P.connect(Path("/nonexistent/prices.sql"))


def rows(con, sql="SELECT offer_id, day, checked_at, price, price_usd, in_stock FROM price_snapshots ORDER BY offer_id, day"):
    return con.execute(sql).fetchall()


class PriceDbTest(unittest.TestCase):
    def test_schema_has_keys_and_indexes(self):
        con = fresh()
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {"miners", "retailers", "offers", "price_snapshots"})
        idx = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertTrue({"idx_offers_miner", "idx_snap_day"} <= idx)
        fks = {(r[2], r[3]) for r in con.execute("PRAGMA foreign_key_list(offers)")}
        self.assertEqual(fks, {("miners", "miner_id"), ("retailers", "retailer_id")})

    def test_add_latest_skips_stale_and_converts_currency(self):
        con = fresh()
        self.assertEqual(P.add_latest(con, LATEST), 1)
        self.assertEqual(rows(con), [("shopa:bitaxe-gamma", "2026-11-10", "2026-11-10T12:00:00Z", 99, 99.0, 1)])
        self.assertEqual(P.usd(100, "EUR", LATEST["fx"]), 110.0)
        self.assertIsNone(P.usd(100, "GBP", LATEST["fx"]))

    def test_running_twice_changes_nothing(self):
        con = fresh()
        P.add_latest(con, LATEST)
        first = P.dump_text(con)
        P.add_latest(con, LATEST)
        P.add_history(con, {"shopa:bitaxe-gamma": [{"t": "2026-11-10T01:00:00Z", "price": 1, "currency": "USD", "in_stock": True}]}, None)
        self.assertEqual(P.dump_text(con), first)

    def test_one_row_per_day_newest_reading_wins_in_any_order(self):
        con = fresh()
        P.upsert_catalog(con, LATEST)
        for t, price in (("2026-11-10T18:00:00Z", 90), ("2026-11-10T06:00:00Z", 80)):   # newer first, then older
            P.add_snapshot(con, "shopa:bitaxe-gamma", t, price, "USD", True, None)
        self.assertEqual(rows(con), [("shopa:bitaxe-gamma", "2026-11-10", "2026-11-10T18:00:00Z", 90, 90.0, 1)])

    def test_history_only_fills_missing_days(self):
        con = fresh()
        P.add_latest(con, LATEST)
        n = P.add_history(con, {
            "shopa:bitaxe-gamma": [{"t": "2026-11-01T10:00:00Z", "price": 120, "currency": "USD", "in_stock": True},
                                   {"t": "2026-11-10T13:00:00Z", "price": 5, "currency": "USD", "in_stock": True}],
            "ghost:nope": [{"t": "2026-11-01T10:00:00Z", "price": 1, "currency": "USD", "in_stock": True}]}, None)
        self.assertEqual(n, 2)   # ghost offer (unknown shop and miner) skipped
        self.assertEqual([r[1:4] for r in rows(con)], [("2026-11-01", "2026-11-01T10:00:00Z", 120),
                                                       ("2026-11-10", "2026-11-10T12:00:00Z", 99)])

    def test_dump_round_trips_and_is_valid_sql(self):
        con = fresh()
        P.add_latest(con, LATEST)
        con.execute("UPDATE offers SET title = ? WHERE id = ?", ("It's a \"Gamma\"", "shopa:bitaxe-gamma"))
        text = P.dump_text(con)
        with tempfile.TemporaryDirectory() as d:
            dump = Path(d) / "prices.sql"
            dump.write_text(text)
            again = P.connect(dump)
            self.assertEqual(P.dump_text(again), text)
            self.assertEqual(again.execute("SELECT title FROM offers").fetchone()[0], "It's a \"Gamma\"")
            P.save(again, dump, Path(d) / "prices.db")
            disk = sqlite3.connect(Path(d) / "prices.db")
            self.assertEqual(disk.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0], 1)
            self.assertEqual(disk.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_repo_database_is_consistent(self):
        """The committed text copy loads, has no broken keys, and never two rows for one offer on one day."""
        con = P.connect()
        self.assertGreater(con.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0], 0)
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
        dup = con.execute("SELECT offer_id, day, COUNT(*) FROM price_snapshots GROUP BY 1, 2 HAVING COUNT(*) > 1").fetchall()
        self.assertEqual(dup, [])


if __name__ == "__main__":
    unittest.main()
