import json
import tempfile
import unittest
from pathlib import Path

from bench.engine import run_tick, run_week
from bench.market import replay
from tests.test_tick import CONFIG, OPEN_BTC, market, scripted

LIVE = replay(Path(__file__).parent / "fixtures" / "live_btc")  # recorded metaAndAssetCtxs: 234 perps, 56 delisted

W1 = "2026-10-19T00:07:00Z"
W2 = "2026-10-26T00:07:00Z"
WEEK1, WEEK2 = "2026-10-19T00:00:00Z", "2026-10-26T00:00:00Z"  # Week ids: Monday 00:00 UTC
PLAN = {
    "notional": 6000,
    "watchlist": [{"symbol": "BTC", "bias": "both", "entry": "breakout", "exit": "TP +1%"},
                  {"symbol": "ETH", "bias": "long", "entry": "pullback", "exit": "TP +2%"}],
    "close_all": "Friday 20:00 UTC",
    "hostage_policy": "reopen lost Slots first",
    "rationale": "trend week",
}
DOGE = {"symbol": "DOGE", "bias": "long", "entry": "x", "exit": "y"}  # max leverage 3x


def strategist(*replies, seen=None):
    """Scripted Strategist; appends every request it gets to seen."""
    replies = iter(replies)

    def model(given):
        if seen is not None:
            seen.append(given)
        return next(replies)

    return model


class RunWeek(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())

    def week(self, at, model, source=None):
        return run_week("x", at, source or market(), model, self.data, CONFIG)

    def tick(self, at, model, source=None):
        run_tick("x", at, source or market(), model, self.data, CONFIG)
        return self.state()

    def state(self):
        return json.loads((self.data / "x" / "state.json").read_text())

    def plan_in_force(self):
        return json.loads((self.data / "x" / "plan.json").read_text())

    def events(self):
        return [json.loads(l) for l in (self.data / "x" / "events.jsonl").read_text().splitlines()]

    def test_first_week_reallocates_and_ticks_use_the_plan_notional(self):
        self.week(W1, strategist(PLAN))

        state = self.state()
        self.assertEqual(state["rp"], {"collateral": 2500, "notional": 6000})
        self.assertEqual(self.events(), [{"t": W1, "type": "plan", "plan": WEEK1, "fallback": False,
                                          "reallocated": True, "notional_used": True},
                                         {"t": W1, "type": "reallocation", "rp": state["rp"]}])

        state = self.tick("2026-10-19T00:07:00Z", scripted(OPEN_BTC))

        self.assertEqual(state["layers"][0]["notional"], 6000)
        self.assertEqual(state["free_equity"], 7500)

    def test_flat_account_at_week_boundary_reallocates_equity_over_four(self):
        self.week(W1, strategist(PLAN))
        self.tick("2026-10-19T01:07:00Z", scripted(OPEN_BTC))
        equity = self.tick("2026-10-19T02:07:00Z", scripted({"type": "close", "slot": 0}))["free_equity"]

        self.week(W2, strategist({**PLAN, "notional": 9000}))

        rp = self.state()["rp"]
        self.assertLess(equity, 10000)  # the round trip paid fees
        self.assertEqual(rp, {"collateral": equity / 4, "notional": 9000})
        self.assertEqual(self.events()[-1], {"t": W2, "type": "reallocation", "rp": rp})

    def test_open_layer_at_week_boundary_keeps_rp_and_strategist_is_told_beforehand(self):
        self.week(W1, strategist(PLAN))
        self.tick("2026-10-19T01:07:00Z", scripted(OPEN_BTC))
        seen = []

        self.week(W2, strategist({**PLAN, "notional": 9000}, seen=seen))

        self.assertEqual(seen[0]["reallocation"], {"happens": False, "collateral": 2500})
        self.assertEqual(self.state()["rp"], {"collateral": 2500, "notional": 6000})
        self.assertEqual(self.events()[-1], {"t": W2, "type": "plan", "plan": WEEK2, "fallback": False,
                                             "reallocated": False, "notional_used": False})
        self.assertNotIn("violation", [e["type"] for e in self.events()])
        archive = json.loads((self.data / "x" / "plans" / "2026-10-26.json").read_text())
        self.assertEqual((archive["plan"]["notional"], archive["notional_used"]), (9000, False))
        self.assertEqual(self.plan_in_force()["notional"], 6000)  # what the RP actually uses

    def test_without_reallocation_the_new_watchlist_is_checked_against_the_rp_in_force(self):
        self.week(W1, strategist({**PLAN, "notional": 8000}))  # 3.2x
        self.tick("2026-10-19T01:07:00Z", scripted(OPEN_BTC))

        self.week(W2, strategist({**PLAN, "notional": 7000, "watchlist": [DOGE]}, PLAN))  # 7,000 alone is 2.8x

        error = next(e for e in self.events() if e["type"] == "error")
        self.assertIn("notional 8000 / collateral 2500 = 3.20x exceeds DOGE max leverage 3x", error["error"])
        self.assertEqual(self.plan_in_force()["watchlist"], PLAN["watchlist"])

    def test_retry_request_carries_settled_events_only(self):
        self.week(W1, strategist(PLAN))
        self.tick("2026-10-19T01:07:00Z", scripted(OPEN_BTC))
        seen = []

        self.week(W2, strategist("not a plan", PLAN, seen=seen))

        self.assertEqual([r["settled"] for r in seen], [[], []])

    def test_plan_over_a_symbols_max_leverage_is_sent_back_and_the_fix_passes(self):
        greedy = {**PLAN, "notional": 10000, "watchlist": PLAN["watchlist"] + [DOGE]}  # 10,000 / 2,500 = 4x
        seen = []

        self.week(W1, strategist(greedy, {**greedy, "notional": 7000}, seen=seen))

        error = self.events()[0]
        self.assertEqual(error["type"], "error")
        self.assertIn("DOGE max leverage 3x", error["error"])
        self.assertEqual(seen[1]["retry_error"], error["error"])
        self.assertEqual(self.state()["rp"]["notional"], 7000)

    def test_invalid_plan_is_sent_back_with_its_reason(self):
        btc = PLAN["watchlist"][0]
        cases = [
            ("not on Hyperliquid", {**PLAN, "watchlist": [{**btc, "symbol": "NOPE"}]}),
            ("at most 5", {**PLAN, "watchlist": [btc] * 6}),
            ("BTC appears more than once", {**PLAN, "watchlist": [btc, {**btc, "bias": "short"}]}),
            ("minimum of 10 USD", {**PLAN, "notional": 9.99}),
            ("minimum of 10 USD", {**PLAN, "notional": float("nan")}),  # json.loads accepts NaN
            ("rationale", {k: v for k, v in PLAN.items() if k != "rationale"}),
            ("bias", {**PLAN, "watchlist": [{**btc, "bias": "up"}]}),
            ("entry", {**PLAN, "watchlist": [{"symbol": "BTC", "bias": "long"}]}),
            ("notional (number)", {**PLAN, "notional": True}),
            ("must be an object", ["BTC"]),
        ]
        for reason, plan in cases:
            with self.subTest(reason):
                self.data = Path(tempfile.mkdtemp())
                self.week(W1, strategist(plan, plan, plan))
                errors = [e for e in self.events() if e["type"] == "error"]
                self.assertEqual(len(errors), 3)  # first answer plus 2 retries
                self.assertIn(reason, errors[0]["error"])

    def test_three_failures_keep_last_weeks_plan_and_rp(self):
        self.week(W1, strategist(PLAN))

        self.week(W2, strategist(*[{"reasoning": "not a plan"}] * 3))
        self.tick("2026-10-26T01:07:00Z", scripted({"type": "hold"}))

        self.assertEqual(self.state()["rp"], {"collateral": 2500, "notional": 6000})  # flat, yet no Reallocation
        self.assertEqual([e["type"] for e in self.events()][2:], ["error", "error", "error", "plan", "decision"])
        # flat, yet not reallocated; last week's notional is the one in use
        self.assertEqual(self.events()[-2], {"t": W2, "type": "plan", "plan": WEEK1, "fallback": True,
                                             "reallocated": False, "notional_used": True})
        self.assertEqual(self.events()[-1]["plan"], WEEK1)
        self.assertFalse((self.data / "x" / "plans" / "2026-10-26.json").exists())

    def test_first_week_without_a_plan_holds_every_tick_with_one_violation(self):
        def executor(_input):
            raise AssertionError("Executor must not be called without a plan")

        self.week(W1, strategist(None, None, None))
        self.tick("2026-10-19T00:07:00Z", executor)
        state = self.tick("2026-10-19T01:07:00Z", executor)

        self.assertEqual([e["type"] for e in self.events()], ["error", "error", "error", "violation", "plan"])
        self.assertEqual(self.events()[-2], {"t": W1, "type": "violation", "rule": "no_weekly_plan"})
        self.assertEqual(self.events()[-1], {"t": W1, "type": "plan", "plan": None, "fallback": True,
                                             "reallocated": False, "notional_used": False})
        self.assertEqual((state["free_equity"], state["layers"]), (10000, [None] * 4))

    def test_strategist_sees_top_50_by_volume_and_may_pick_any_listed_symbol(self):
        tnsr = {**PLAN["watchlist"][0], "symbol": "TNSR"}  # lowest 24h volume of the listed perps
        matic = {**tnsr, "symbol": "MATIC"}  # delisted
        seen = []

        self.week(W1, strategist({**PLAN, "watchlist": [matic]}, {**PLAN, "watchlist": [tnsr]}, seen=seen), LIVE)

        universe = seen[0]["universe"]
        self.assertEqual(len(universe), 50)
        self.assertEqual(universe[0], {"symbol": "BTC", "day_volume": 1010005391.2605088949, "mark": 81959.0,
                                       "funding": -0.0000007678, "open_interest": 41576.78028, "max_leverage": 40})
        self.assertNotIn("TNSR", [u["symbol"] for u in universe])
        self.assertIn("TNSR", seen[0]["symbols"])
        self.assertNotIn("MATIC", seen[0]["symbols"])
        self.assertEqual(self.events()[0]["error"], "MATIC is not on Hyperliquid")
        self.assertEqual(self.plan_in_force()["watchlist"], [tnsr])

    def test_strategist_sees_last_weeks_plan_trades_and_violations(self):
        self.week(W1, strategist(PLAN))
        self.tick("2026-10-19T01:07:00Z", scripted(OPEN_BTC, OPEN_BTC))
        self.tick("2026-10-19T02:07:00Z", scripted({"type": "close", "slot": 0}))
        seen = []

        self.week(W2, strategist(PLAN, seen=seen))

        self.assertEqual(seen[0]["previous_plan"], {**PLAN, "week": WEEK1})
        self.assertEqual([e["type"] for e in seen[0]["last_week"]],
                         ["plan", "reallocation", "decision", "fill", "violation", "decision", "close"])
        self.assertEqual(seen[0]["last_week"][2]["reasoning"], "scripted")

        self.tick("2026-10-26T01:07:00Z", scripted({"type": "hold"}))
        self.week("2026-11-02T00:07:00Z", strategist(PLAN, seen=seen))

        self.assertEqual([e["type"] for e in seen[1]["last_week"]], ["plan", "reallocation", "decision"])  # since W2 only

    def test_every_weeks_plan_is_archived_and_each_decision_names_its_plan(self):
        runs = ((WEEK1, "2026-10-21T09:30:00Z", "2026-10-21T10:07:00Z"),  # Week 1 run by hand on Wednesday
                (WEEK2, W2, "2026-10-26T01:07:00Z"))
        for week, at, tick in runs:
            self.week(at, strategist({**PLAN, "rationale": f"why {week}"}))
            self.tick(tick, scripted({"type": "hold"}))

        self.assertEqual([e["plan"] for e in self.events() if e["type"] == "plan"], [WEEK1, WEEK2])
        self.assertEqual([e["plan"] for e in self.events() if e["type"] == "decision"], [WEEK1, WEEK2])
        for week in (WEEK1, WEEK2):
            archive = json.loads((self.data / "x" / "plans" / f"{week[:10]}.json").read_text())
            self.assertEqual((archive["plan"]["week"], archive["plan"]["rationale"]), (week, f"why {week}"))

    def test_rerunning_within_the_same_week_is_idempotent(self):
        self.week(W1, strategist(PLAN))
        files = {f: (self.data / "x" / f).read_bytes() for f in ("state.json", "events.jsonl", "plan.json")}

        self.assertFalse(self.week("2026-10-21T12:00:00Z", strategist()))  # asking again would raise StopIteration

        self.assertEqual({f: (self.data / "x" / f).read_bytes() for f in files}, files)

    def test_timestamps_with_an_offset_are_stored_as_utc(self):
        self.week("2026-10-19T07:07:00+07:00", strategist(PLAN))

        self.assertEqual(self.plan_in_force()["week"], WEEK1)
        self.assertTrue((self.data / "x" / "plans" / "2026-10-19.json").exists())

    def test_tick_before_any_week_says_to_run_the_week_first(self):
        (self.data / "x").mkdir()
        with self.assertRaisesRegex(FileNotFoundError, "run-week"):
            self.tick(W1, scripted({"type": "hold"}))


if __name__ == "__main__":
    unittest.main()
