"""Collector rules for the Oct 21 additions: strict title matching, stock (not overclock) specs, $0 placeholders skipped."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))
import collect as C  # noqa: E402


class CollectorRules(unittest.TestCase):
    def test_title_matching_is_strict(self):
        ok = [("bitforge-nano", "Bitforge Nano Solo Bitcoin Miner | Open-Source 2.6TH/s"),
              ("nerdoctaxe", "Bitcoin Merch® - NerdOCTaxe 9-12TH/s BTC Miner w/ Power Supply"),
              ("hammer-thor-p2", "Thor P2 Bitcoin Miner – 10 TH/s Dual BM1373 ASIC Miner"),
              ("futurebit-apollo-iii", "Apollo III - Standard Version - Miner Only - Ships in 4-6 Weeks"),
              ("bitaxe-gamma-hex", "Bitaxe Gamma Hex Bitcoin Solo Miner (1300 Model)")]
        bad = [("bitforge-nano", "BitForge Nano Bitcoin Solo Miner (Ghost Edition)"),
               ("nerdoctaxe", "Bitcoin Merch® - NerdOCTaxe Stand"),
               ("nerdoctaxe", "Bitcoin Merch® - NerdOCTaxe Hydro 12TH/s BTC Miner"),
               ("hammer-thor-p2", "Hammer Miner Thor X1 3.2TH/s Lottery Miner"),
               ("futurebit-apollo-iii", "Apollo III – Sovereign Bitcoin Miner & Full Node"),
               ("bitaxe-gamma-hex", "Bitaxe Hex Heatsink"),
               ("hammer-bc08", "Hammer Miner BC08 Hydro 12TH/s Bitcoin Miner"),
               ("bitaxe-naja-duo", "Naja Duo Stand Free .STL Download")]
        for m, t in ok:
            self.assertTrue(C.title_ok(m, t), (m, t))
        for m, t in bad:
            self.assertFalse(C.title_ok(m, t), (m, t))

    def test_stock_specs_not_overclock(self):
        self.assertEqual(C.MODELS["bitaxe-naja-duo"]["hashrate_ths"], 4.4)     # 8 TH/s is the ~92 W overclock
        self.assertEqual(C.MODELS["nerdoctaxe"]["hashrate_ths"], 9.6)          # 12 TH/s is an overclock
        self.assertEqual(C.MODELS["bitaxe-gamma-hex"]["hashrate_ths"], 8.4)
        self.assertNotIn("bitaxe-touch", C.MODELS)                             # sellers list different hardware under one name
        for m in ("dtv", "futurebit"):
            self.assertIn(m, C.SELLERS)
            self.assertIn(m, C.ADAPTERS)

    def test_ship_wait(self):
        self.assertEqual(C.ship_wait("Apollo III - Standard Version - Miner Only - Ships in 4-6 Weeks")[0], "backorder")
        self.assertEqual(C.ship_wait("GekkoScience KBox 22TH Quiet Bitcoin Miner Pre-order: Shipping within 6-10 weeks")[0], "preorder")
        self.assertIsNone(C.ship_wait("FutureBit Apollo 200W Power Supply - Ships in 2-3 Days"))


if __name__ == "__main__":
    unittest.main()
