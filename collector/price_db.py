"""Price history in a real SQL database (SQLite).

Plain-English version: docs/SQL.md.

What this file does, every collector run:
  1. Load the database from data/prices.sql (a text copy of the database, kept in git).
  2. Make sure the 4 tables exist (CREATE TABLE IF NOT EXISTS).
  3. Upsert every miner, retailer and listing, and one price row per listing per day.
  4. Write the text copy back (data/prices.sql) and a ready-to-query file (data/prices.db, not in git).

Why a text copy in git and not the .db file? A .db file is binary: every change would add a whole new
copy to git history (hundreds of KB, 4 times a day). The text copy is one INSERT line per row, so git
only stores the few new lines each day.

Idempotent ("safe to run twice"): every write is INSERT ... ON CONFLICT DO UPDATE keyed on a UNIQUE
column, so running the same data in twice gives exactly the same database.

Usage:
  python3 collector/price_db.py                  # normal run: add today's prices from data/latest.json
  python3 collector/price_db.py --backfill-git   # one-off: also add a row per day from every old
                                                 #   data/latest.json version in git history
"""
import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SQL_DUMP = DATA / "prices.sql"
DB_FILE = DATA / "prices.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS retailers (
  id        TEXT PRIMARY KEY,            -- e.g. 'solosatoshi'
  name      TEXT NOT NULL,               -- e.g. 'Solo Satoshi'
  url       TEXT,
  currency  TEXT                         -- the currency the shop prices in (USD, EUR, CAD)
);
CREATE TABLE IF NOT EXISTS miners (
  id            TEXT PRIMARY KEY,        -- e.g. 'bitaxe-gamma'
  name          TEXT NOT NULL,
  maker         TEXT,
  chip          TEXT,
  hashrate_ths  REAL,
  watts         REAL
);
CREATE TABLE IF NOT EXISTS offers (      -- one product page: this miner, at this shop
  id           TEXT PRIMARY KEY,         -- e.g. 'solosatoshi:bitaxe-gamma'
  miner_id     TEXT NOT NULL REFERENCES miners(id),
  retailer_id  TEXT NOT NULL REFERENCES retailers(id),
  title        TEXT,
  url          TEXT
);
CREATE TABLE IF NOT EXISTS price_snapshots (   -- one row per offer per day
  id          INTEGER PRIMARY KEY,
  offer_id    TEXT NOT NULL REFERENCES offers(id),
  day         TEXT NOT NULL,             -- 'YYYY-MM-DD' (UTC)
  checked_at  TEXT NOT NULL,             -- exact time we read the price (ISO, UTC)
  price       REAL,                      -- in the shop's own currency
  currency    TEXT,
  price_usd   REAL,                      -- approximate USD (exchange rate of that day)
  in_stock    INTEGER NOT NULL,          -- 1 = in stock, 0 = not
  UNIQUE (offer_id, day)                 -- the rule that makes re-runs safe: max one row per offer per day
);
CREATE INDEX IF NOT EXISTS idx_offers_miner ON offers(miner_id);
CREATE INDEX IF NOT EXISTS idx_snap_day ON price_snapshots(day);
"""


def connect(dump=SQL_DUMP):
    """In-memory database loaded from the text copy (or empty), with the schema in place."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    if dump.exists() and dump.stat().st_size:
        con.executescript(dump.read_text())
    con.executescript(SCHEMA)
    return con


def usd(price, currency, fx):
    if price is None:
        return None
    if currency == "USD":
        return round(float(price), 2)
    rate = (fx or {}).get(f"{currency}_USD")
    return round(float(price) * rate, 2) if rate else None


def upsert_catalog(con, latest):
    """Miners, retailers and offers. Newer data wins (names and specs get fixed sometimes)."""
    for sid, s in (latest.get("sellers") or {}).items():
        con.execute("""INSERT INTO retailers (id, name, url, currency) VALUES (?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET name=excluded.name, url=excluded.url, currency=excluded.currency""",
                    (sid, s.get("name") or sid, s.get("url"), s.get("currency")))
    for mid, m in (latest.get("models") or {}).items():
        con.execute("""INSERT INTO miners (id, name, maker, chip, hashrate_ths, watts) VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET name=excluded.name, maker=excluded.maker, chip=excluded.chip,
                         hashrate_ths=excluded.hashrate_ths, watts=excluded.watts""",
                    (mid, m.get("name") or mid, m.get("maker") or (m.get("name") or mid).split(" ")[0],
                     m.get("chip"), m.get("hashrate_ths"), m.get("watts")))
    for o in latest.get("offers") or []:
        ensure_offer(con, o["id"], o.get("model"), o.get("seller"), o.get("title"), o.get("url"))


def ensure_offer(con, oid, miner_id=None, retailer_id=None, title=None, url=None):
    """Make sure an offer row exists (old history can mention offers the catalog no longer has).
    Returns False if we can't tie it to a known miner and retailer (row skipped, never a broken key)."""
    if not miner_id or not retailer_id:
        retailer_id, _, miner_id = oid.partition(":")
    known_m = con.execute("SELECT 1 FROM miners WHERE id = ?", (miner_id,)).fetchone()
    known_r = con.execute("SELECT 1 FROM retailers WHERE id = ?", (retailer_id,)).fetchone()
    if not (known_m and known_r):
        return False
    con.execute("""INSERT INTO offers (id, miner_id, retailer_id, title, url) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET title=COALESCE(excluded.title, offers.title), url=COALESCE(excluded.url, offers.url)""",
                (oid, miner_id, retailer_id, title, url))
    return True


def add_snapshot(con, offer_id, checked_at, price, currency, in_stock, fx, fill_only=False):
    """One row per offer per day. A later reading on the same day replaces an earlier one;
    an older reading never overwrites a newer one (so the order you feed data in doesn't matter).
    fill_only=True: only add days that have no row yet (used for history.json, which has no
    exchange rate of its own, so it must never overwrite a row that has the real rate of that day)."""
    day = checked_at[:10]
    if fill_only:
        con.execute("""INSERT INTO price_snapshots (offer_id, day, checked_at, price, currency, price_usd, in_stock)
                       VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(offer_id, day) DO NOTHING""",
                    (offer_id, day, checked_at, price, currency, usd(price, currency, fx), 1 if in_stock else 0))
        return
    con.execute("""INSERT INTO price_snapshots (offer_id, day, checked_at, price, currency, price_usd, in_stock)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(offer_id, day) DO UPDATE SET checked_at=excluded.checked_at, price=excluded.price,
                     currency=excluded.currency, price_usd=excluded.price_usd, in_stock=excluded.in_stock
                   WHERE excluded.checked_at > price_snapshots.checked_at""",
                (offer_id, day, checked_at, price, currency, usd(price, currency, fx), 1 if in_stock else 0))


def add_latest(con, latest):
    """Today's prices. Stale offers (shop failed to load, old price carried forward) are skipped:
    we only store prices we actually read."""
    upsert_catalog(con, latest)
    n = 0
    for o in latest.get("offers") or []:
        if o.get("stale") or not o.get("checked_at"):
            continue
        add_snapshot(con, o["id"], o["checked_at"], o.get("price"), o.get("currency"), o.get("in_stock"), latest.get("fx"))
        n += 1
    return n


def add_history(con, history, fx):
    """Backfill from data/history.json (points recorded when a price changed, or about daily)."""
    n = 0
    for oid, pts in history.items():
        if not ensure_offer(con, oid):
            continue
        for p in pts:
            add_snapshot(con, oid, p["t"], p.get("price"), p.get("currency"), p.get("in_stock"), fx, fill_only=True)
            n += 1
    return n


def git_versions(path="data/latest.json"):
    """Every committed version of a file, oldest first: (commit, text)."""
    revs = subprocess.run(["git", "-C", str(ROOT), "log", "--reverse", "--format=%H", "--", path],
                          capture_output=True, text=True, check=True).stdout.split()
    for rev in revs:
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{path}"], capture_output=True, text=True)
        if r.returncode == 0:
            yield rev, r.stdout


def add_git_backfill(con):
    n = 0
    for _, text in git_versions():
        try:
            old = json.loads(text)
        except ValueError:
            continue
        upsert_catalog_known_only(con, old)
        for o in old.get("offers") or []:
            if o.get("stale") or not o.get("checked_at") or not ensure_offer(con, o["id"], o.get("model"), o.get("seller")):
                continue
            add_snapshot(con, o["id"], o["checked_at"], o.get("price"), o.get("currency"), o.get("in_stock"), old.get("fx"))
            n += 1
    return n


def upsert_catalog_known_only(con, old):
    """Old versions may list miners/shops we've since renamed; only ADD missing ones, never overwrite."""
    for sid, s in (old.get("sellers") or {}).items():
        con.execute("INSERT OR IGNORE INTO retailers (id, name, url, currency) VALUES (?, ?, ?, ?)",
                    (sid, s.get("name") or sid, s.get("url"), s.get("currency")))
    for mid, m in (old.get("models") or {}).items():
        con.execute("INSERT OR IGNORE INTO miners (id, name, maker, chip, hashrate_ths, watts) VALUES (?, ?, ?, ?, ?, ?)",
                    (mid, m.get("name") or mid, m.get("maker") or (m.get("name") or mid).split(" ")[0],
                     m.get("chip"), m.get("hashrate_ths"), m.get("watts")))


def dump_text(con):
    """Deterministic text copy: schema, then rows sorted by primary key. Same data -> same bytes."""
    out = ["PRAGMA foreign_keys=OFF;", "BEGIN TRANSACTION;"]
    for table, order in (("retailers", "id"), ("miners", "id"), ("offers", "id"), ("price_snapshots", "id")):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        for row in con.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY {order}"):
            vals = ", ".join(sql_literal(v) for v in row)
            out.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({vals});")
    out.append("COMMIT;")
    # Schema goes FIRST so loading the text builds the tables before the rows.
    return SCHEMA.strip() + "\n" + "\n".join(out) + "\n"


def sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def save(con, dump=SQL_DUMP, db_file=DB_FILE):
    con.commit()
    dump.write_text(dump_text(con))
    if db_file:
        db_file.unlink(missing_ok=True)
        disk = sqlite3.connect(db_file)
        con.backup(disk)                 # copy the in-memory database into a real .db file
        disk.execute("VACUUM")
        disk.close()


def counts(con):
    """Rows per table (printed after each run)."""
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("miners", "retailers", "offers", "price_snapshots")}


def main(argv=None):
    p = argparse.ArgumentParser(description="Update the SQL price history (data/prices.sql + data/prices.db).")
    p.add_argument("--backfill-git", action="store_true", help="also add rows from every old data/latest.json in git")
    p.add_argument("--no-history", action="store_true", help="skip data/history.json backfill")
    a = p.parse_args(argv)
    latest = json.loads((DATA / "latest.json").read_text())
    con = connect()
    upsert_catalog(con, latest)
    if a.backfill_git:
        print(f"git backfill: {add_git_backfill(con)} readings")
    if not a.no_history and (DATA / "history.json").exists():
        add_history(con, json.loads((DATA / "history.json").read_text()), latest.get("fx"))
    n = add_latest(con, latest)
    save(con)
    print(f"price db: {n} readings today -> {counts(con)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
