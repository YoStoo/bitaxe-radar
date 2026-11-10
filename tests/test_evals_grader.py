"""Unit tests for the eval GRADER (evals/grader.py). No network, no Claude: fake answers on tiny data."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))
import grader as G  # noqa: E402
import radar_data as R  # noqa: E402


def offer(model, price, seller="s1", in_stock=True):
    return {"model": model, "seller": seller, "price_usd_approx": price, "in_stock": in_stock, "stale": False}


LATEST = {
    "generated_at": "2026-11-10T00:00:00Z",
    "sellers": {"s1": {"name": "Solo Satoshi"}, "s2": {"name": "Altair Technology"}},
    "models": {
        "bitaxe-gamma": {"name": "Bitaxe Gamma (601/602)", "hashrate_ths": 1.2, "watts": 18},
        "bitaxe-gamma-duo": {"name": "Bitaxe Gamma Duo (650)", "hashrate_ths": 1.63, "watts": 26},
        "bitaxe-supra": {"name": "Bitaxe Supra", "hashrate_ths": 0.65, "watts": 15},
        "bitaxe-ultra": {"name": "Bitaxe Ultra", "hashrate_ths": 0.5, "watts": 12},
        "avalon-q": {"name": "Canaan Avalon Q (90 TH/s)", "maker": "Canaan", "hashrate_ths": 90, "watts": 1674},
        "sold-out": {"name": "Sold Out Miner", "hashrate_ths": 5, "watts": 50},
    },
    "offers": [offer("bitaxe-gamma", 67), offer("bitaxe-gamma", 70, "s2"), offer("bitaxe-gamma-duo", 111.69),
               offer("bitaxe-supra", 119.99), offer("bitaxe-ultra", 119.99), offer("avalon-q", 1398, "s2"),
               offer("sold-out", 10, in_stock=False)],
}


def resp(answer, **kw):
    return {"ok": True, "answer": answer, "models_mentioned": [], "in_data": True, "tools_used": [], **kw}


class DataTests(unittest.TestCase):
    def test_rank_skips_out_of_stock_and_sorts(self):
        self.assertEqual([r["id"] for r in R.rank(LATEST, "price")][:2], ["bitaxe-gamma", "bitaxe-gamma-duo"])
        self.assertNotIn("sold-out", [r["id"] for r in R.rank(LATEST, "price")])

    def test_rank_price_per_th_and_desc(self):
        self.assertEqual(R.rank(LATEST, "price_per_th")[0]["id"], "avalon-q")
        self.assertEqual(R.rank(LATEST, "price", order="desc")[0]["id"], "avalon-q")
        self.assertEqual(R.rank(LATEST, "price", brand="Canaan")[0]["id"], "avalon-q")

    def test_miners_in_text_prefers_longer_names(self):
        text = "Get the Bitaxe Gamma Duo, not the Bitaxe Gamma (601/602)."
        self.assertEqual(R.miners_in_text(text, LATEST), ["bitaxe-gamma-duo", "bitaxe-gamma"])

    def test_miners_in_text_short_names(self):
        self.assertEqual(R.miners_in_text("The Avalon Q is pricey; the Gamma Duo is not.", LATEST), ["avalon-q", "bitaxe-gamma-duo"])


class CheckTests(unittest.TestCase):
    def test_sentences_ignore_decimals(self):
        self.assertEqual(len(G.sentences("It costs $55.80 per TH/s. That is cheap! Buy it?")), 3)

    def test_length_cap(self):
        self.assertTrue(G.check_length("One. Two. Three. Four.")[0])
        self.assertFalse(G.check_length("One. Two. Three. Four. Five.")[0])
        self.assertFalse(G.check_length("word " * 91)[0])

    def test_price_tolerance(self):
        self.assertTrue(G.check_price("about $112 at Solo Satoshi", "x", 111.69)[0])
        self.assertTrue(G.check_price("$1,398 from Altair", "x", 1398)[0])
        self.assertFalse(G.check_price("about $120", "x", 111.69)[0])

    def test_ranking_order_and_ties(self):
        groups = [["bitaxe-gamma"], ["bitaxe-gamma-duo"]]
        self.assertTrue(G.check_ranking("Bitaxe Gamma at $67, then the Gamma Duo.", groups, LATEST)[0])
        self.assertFalse(G.check_ranking("The Gamma Duo, then the Bitaxe Gamma.", groups, LATEST)[0])
        tie = [["bitaxe-supra", "bitaxe-ultra"]]
        self.assertTrue(G.check_ranking("The Bitaxe Ultra is $119.99.", tie, LATEST)[0])

    def test_tool_check_matches_inputs(self):
        r = resp("x", tools_used=[{"name": "search_miners", "input": {"sort_by": "efficiency", "max_price": 200}}])
        self.assertFalse(G.check_tool(r, {"name": "search_miners", "input": {"sort_by": "price_per_th"}})[0])
        self.assertTrue(G.check_tool(r, {"name": "search_miners", "input": {"max_price": 199.99}})[0])
        self.assertTrue(G.check_tool(r, {"name": ["get_miner", "search_miners"]})[0])

    def test_refusal(self):
        self.assertTrue(G.check_refusal("Sorry, I only help with Bitcoin miners.", {})[0])
        self.assertFalse(G.check_refusal("Here's a poem about cats.", {})[0])
        self.assertFalse(G.check_refusal("I only help with miners. The Gamma is $67.", {})[0])
        # Story #19: a real refusal the first regex missed (the GRADER was wrong, not the bot)
        self.assertTrue(G.check_refusal("I'm only able to help with home Bitcoin miners, so I can't write a cat poem.", {})[0])

    def test_not_found(self):
        self.assertTrue(G.check_not_found("We don't track the Bitaxe Omega 9000.")[0])
        self.assertFalse(G.check_not_found("The Bitaxe Omega 9000 is $300.")[0])

    def test_fill_history_template(self):
        self.assertEqual(G.fill("{name:avalon-q} is {price:avalon-q} at {shop:avalon-q}", LATEST),
                         "Canaan Avalon Q (90 TH/s) is $1,398 at Altair Technology")


class GradeTests(unittest.TestCase):
    CASE = {"id": "cheapest-bitaxe", "question": "q",
            "expect": {"top": {"sort_by": "price", "brand": "Bitaxe"}, "in_data": True,
                       "tool": {"name": "search_miners", "input": {"sort_by": "price"}}}}

    def test_good_answer_passes_every_check(self):
        r = resp("The cheapest Bitaxe is the Bitaxe Gamma at $67 from Solo Satoshi.",
                 tools_used=[{"name": "search_miners", "input": {"sort_by": "price", "brand": "Bitaxe"}}])
        g = G.grade(self.CASE, r, LATEST)
        self.assertTrue(g["pass"], g)

    def test_wrong_in_data_fails_only_that_check(self):
        r = resp("The cheapest Bitaxe is the Bitaxe Gamma at $67.", in_data=False,
                 tools_used=[{"name": "search_miners", "input": {"sort_by": "price"}}])
        g = G.grade(self.CASE, r, LATEST)
        self.assertFalse(g["pass"])
        self.assertEqual([c["check"] for c in g["checks"] if not c["pass"]], ["in_data"])

    def test_after_skips_the_named_miner(self):
        case = {"id": "next", "question": "q", "expect": {"top": {"sort_by": "price", "brand": "Bitaxe", "after": "bitaxe-gamma"}}}
        g = G.grade(case, resp("Next is the Bitaxe Gamma Duo at $111.69."), LATEST)
        self.assertTrue(g["pass"], g)

    def test_error_reply_fails_cleanly(self):
        g = G.grade(self.CASE, {"ok": False, "error": "Too many questions."}, LATEST)
        self.assertFalse(g["pass"])
        self.assertTrue(all(not c["pass"] for c in g["checks"]))

    def test_every_real_case_resolves(self):
        import json
        cases = json.loads((ROOT / "evals" / "cases.json").read_text())["cases"]
        latest = R.load_local()
        for c in cases:
            self.assertGreaterEqual(len(G.resolve(c, latest)), 3, c["id"])


if __name__ == "__main__":
    unittest.main()
