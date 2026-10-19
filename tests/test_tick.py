import json
import re
import tempfile
import unittest
from pathlib import Path

from bench.engine import run_tick
from bench.market import recording, replay
from tests.helpers import FIXTURES, HOLD, OPEN_BTC, bar, market, rate, scripted, solo

PLAN = {
    "week": "2026-10-19T00:07:00Z",
    "notional": 10000,
    "watchlist": [{"symbol": "BTC", "bias": "both"}, {"symbol": "DOGE", "bias": "both"}, {"symbol": "ETH", "bias": "both"}],
}
T0 = "2026-10-19T01:07:00Z"
T1 = "2026-10-19T02:07:00Z"
SHORT_BTC = {**OPEN_BTC, "side": "short"}


class RunTick(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())

    def tick(self, at, model, source=None, contestant="x", plan=PLAN):
        folder = self.data / contestant
        if not folder.exists():
            folder.mkdir()
            (folder / "plan.json").write_text(json.dumps(plan))
            # ponytail: Given state written by hand so plans can break rules run_week would reject (DOGE 4x, AVOID).
            # Tick-level checks like exceeds_max_leverage only fire live if max leverage drops mid-Week
            rp = {"collateral": 2500, "notional": plan["notional"]}
            given = {"free_equity": 10000, "rp": rp, "layers": [None] * 4, "settled": at}
            (folder / "state.json").write_text(json.dumps(given))
        config, client = solo(contestant, model)
        run_tick(at, source or market(), client, self.data, config)
        return json.loads((folder / "state.json").read_text())

    def events(self, contestant="x"):
        return [json.loads(l) for l in (self.data / contestant / "events.jsonl").read_text().splitlines()]

    def test_open_btc_long_fills_at_best_ask_and_locks_collateral(self):
        state = self.tick(T0, scripted(OPEN_BTC))

        self.assertEqual(state["free_equity"], 7500)
        layer = state["layers"][0]
        self.assertEqual(layer["symbol"], "BTC")
        self.assertEqual(layer["side"], "long")
        self.assertEqual(layer["notional"], 10000)
        self.assertEqual(layer["entry"], 100010.0)
        self.assertAlmostEqual(layer["collateral"], 2500 - 4.5)  # taker fee 0.045% of 10,000
        self.assertEqual(state["layers"][1:], [None, None, None])
        self.assertEqual([e["type"] for e in self.events()], ["decision", "fill"])

    def test_executor_response_is_logged(self):
        self.tick(T0, scripted(OPEN_BTC))
        decision = self.events()[0]
        self.assertEqual(decision["reasoning"], "scripted")
        self.assertEqual(decision["actions"], [OPEN_BTC])

    def test_response_cannot_forge_event_fields(self):
        forged = lambda _input: {"reasoning": "", "actions": [], "type": "violation", "rule": "forged", "t": T1}
        self.tick(T0, forged)
        self.assertEqual(self.events()[-1], {"t": T0, "type": "decision", "plan": PLAN["week"], "reasoning": "", "actions": []})

    def test_short_fills_at_best_bid(self):
        state = self.tick(T0, scripted({**OPEN_BTC, "slot": 2, "side": "short"}))
        self.assertEqual(state["layers"][2]["entry"], 99990.0)

    def test_open_side_must_match_bias(self):
        plan = {**PLAN, "watchlist": [{"symbol": "BTC", "bias": "short"}, {"symbol": "ETH", "bias": "avoid"}]}
        eth = {"type": "open", "slot": 1, "symbol": "ETH", "side": "short"}

        state = self.tick(T0, scripted(OPEN_BTC, eth, {**SHORT_BTC, "slot": 2}), plan=plan)

        self.assertEqual([(e["rule"], e["action"]) for e in self.events() if e["type"] == "violation"],
                         [("bias_mismatch", OPEN_BTC), ("bias_mismatch", eth)])
        self.assertEqual([l and l["side"] for l in state["layers"]], [None, None, "short", None])

    def test_every_rule_code_in_the_executor_summary_is_enforced(self):
        rules = (Path(__file__).parents[1] / "bench" / "tsm_executor.md").read_text().split("## 2.")[1].split("## 3.")[0]
        # Codes appear as "- `code`:" bullets or "ด้วย `code`" in prose; rephrasing either breaks this on purpose
        codes = {a or b for a, b in re.findall(r"ด้วย `(\w+)`|- `(\w+)`:", rules)}
        eth = {"type": "open", "slot": 1, "symbol": "ETH", "side": "long"}
        fill_all = [OPEN_BTC, {"type": "close", "slot": 0}, OPEN_BTC, eth, {**eth, "slot": 2}]  # the round trip cost fees
        scenarios = {  # code: Actions that apply, then the one that must be rejected
            "unsupported_action": ([], {"type": "limit", "slot": 0}),
            "slot_out_of_range": ([], {**OPEN_BTC, "slot": 4}),
            "layer_occupied": ([OPEN_BTC], OPEN_BTC),
            "insufficient_free_equity": (fill_all, {**eth, "slot": 3}),
            "symbol_not_in_watchlist": ([], {**OPEN_BTC, "symbol": "SOL"}),
            "bias_mismatch": ([], {**OPEN_BTC, "symbol": "AVOID"}),
            "opposite_side_open": ([OPEN_BTC], {**SHORT_BTC, "slot": 1}),
            "exceeds_max_leverage": ([], {**OPEN_BTC, "symbol": "DOGE"}),  # 10,000 / 2,500 = 4x > DOGE 3x
            "layer_empty": ([], {"type": "close", "slot": 1}),
            "tp_wrong_side": ([OPEN_BTC], {"type": "set_tp", "slot": 0, "price": 100010}),  # at entry is not profit
            "invalid_action": ([OPEN_BTC], {"type": "set_tp", "slot": 0}),
        }
        plan = {**PLAN, "watchlist": PLAN["watchlist"] + [{"symbol": "AVOID", "bias": "avoid"}]}
        self.assertEqual(codes, set(scenarios))
        for code, (applied, rejected) in scenarios.items():
            with self.subTest(code):
                state = self.tick(T0, scripted(*applied, rejected), contestant=code, plan=plan)
                expected = self.tick(T0, scripted(*applied), contestant=code + "_ref", plan=plan)
                self.assertEqual(self.events(code)[-1], {"t": T0, "type": "violation", "rule": code, "action": rejected})
                self.assertEqual(state, expected)

    def test_rejected_action_does_not_stop_the_ones_around_it(self):
        eth = {"type": "open", "slot": 1, "symbol": "ETH", "side": "long"}
        state = self.tick(T0, scripted(OPEN_BTC, {**OPEN_BTC, "symbol": "SOL"}, eth))
        self.assertEqual([e["type"] for e in self.events()], ["decision", "fill", "violation", "fill"])
        self.assertEqual([l and l["symbol"] for l in state["layers"]], ["BTC", "ETH", None, None])

    def test_cannot_hold_both_sides_of_a_symbol_across_layers(self):
        eth = {"type": "open", "slot": 0, "symbol": "ETH", "side": "long"}
        eth_short = {**eth, "slot": 1, "side": "short"}

        state = self.tick(T0, scripted(eth, eth_short, {**eth, "slot": 2}))

        self.assertEqual([(e["rule"], e["action"]) for e in self.events() if e["type"] == "violation"],
                         [("opposite_side_open", eth_short)])
        self.assertEqual([l and l["side"] for l in state["layers"]], ["long", None, "long", None])

    def test_slot_of_liquidated_layer_reopens_only_once_hostage_refills_free_equity(self):
        eth = [{"type": "open", "slot": n, "symbol": "ETH", "side": "long"} for n in (1, 2, 3)]
        self.tick(T0, scripted(OPEN_BTC, *eth))  # all four Layers locked, free equity 0
        crash = [bar("BTC", "2026-10-19T01:20:00Z", 80000, l=76000)]

        state = self.tick(T1, scripted(OPEN_BTC, {"type": "set_tp", "slot": 1, "price": 4100}), market(crash))

        self.assertEqual(self.events()[-1]["rule"], "insufficient_free_equity")
        self.assertIsNone(state["layers"][0])
        self.assertEqual(state["free_equity"], 0)

        rally = [bar("ETH", "2026-10-19T02:30:00Z", 4050, h=4100)]
        state = self.tick("2026-10-19T03:07:00Z", scripted(OPEN_BTC), market(rally))

        self.assertEqual([e["type"] for e in self.events()[-3:]], ["tp", "decision", "fill"])
        self.assertEqual(state["layers"][0]["symbol"], "BTC")
        # ETH TP returned 2,495.5 + 99.6 × size − maker fee; 2,500 of it re-funded slot 0, the rest is Hostage left over
        size = 10000 / 4000.4
        self.assertAlmostEqual(state["free_equity"], 2495.5 + 99.6 * size - 4100 * size * 0.00015 - 2500, places=6)

    def test_broken_response_is_retried_once_with_its_error_then_holds(self):
        def unparseable(_input):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

        def timeout(_input):
            raise TimeoutError("timed out")

        cases = {
            "unparseable": (unparseable, "ValueError: Expecting value: line 1 column 1 (char 0)"),
            "timeout": (timeout, "TimeoutError: timed out"),
            "not_an_object": (lambda _input: ["open"], "response must be an object"),
            "no_actions": (lambda _input: {"reasoning": "x"}, "response must be an object"),
            "no_reasoning": (lambda _input: {"actions": [OPEN_BTC]}, "response must be an object"),
        }
        for name, (broken, message) in cases.items():
            with self.subTest(name):
                given = []
                state = self.tick(T0, lambda i: given.append(i) or broken(i), contestant=name)
                errors = [e for e in self.events(name) if e["type"] == "error"]
                self.assertEqual([e["type"] for e in self.events(name)], ["error", "error"])
                self.assertTrue(all(e["error"].startswith(message) for e in errors))
                self.assertEqual([i.get("retry_error") for i in given], [None, errors[0]["error"]])
                self.assertEqual(state["layers"], [None] * 4)

    def test_retry_that_succeeds_applies_its_actions(self):
        replies = iter([{"reasoning": "x"}, {"reasoning": "fixed", "actions": [OPEN_BTC]}])
        state = self.tick(T0, lambda _input: next(replies))
        self.assertEqual([e["type"] for e in self.events()], ["error", "decision", "fill"])
        self.assertEqual(self.events()[0]["response"], {"reasoning": "x"})
        self.assertEqual(state["layers"][0]["symbol"], "BTC")

    def test_malformed_action_is_rejected_alone(self):
        malformed = [{**OPEN_BTC, "side": "up"}, {**OPEN_BTC, "slot": "0"}, {**OPEN_BTC, "slot": True},
                     {"type": "open", "slot": 0, "side": "long"}, {"type": "set_tp", "slot": 0, "price": "1"},
                     {"slot": 0}, "hold"]
        for n, action in enumerate(malformed):
            with self.subTest(action=action):
                state = self.tick(T0, scripted(action, OPEN_BTC), contestant=f"malformed_{n}")
                self.assertEqual([(e["type"], e.get("rule")) for e in self.events(f"malformed_{n}")[1:]],
                                 [("violation", "invalid_action"), ("fill", None)])
                self.assertEqual(state["layers"][0]["symbol"], "BTC")

    def test_hold_leaves_state_unchanged(self):
        before = self.tick(T0, scripted(OPEN_BTC))
        after = self.tick(T1, HOLD)
        clock = {"last_tick": None, "settled": None}
        self.assertEqual({**after, **clock}, {**before, **clock})
        self.assertEqual([e["type"] for e in self.events()], ["decision", "fill", "decision"])

    def test_rerunning_same_tick_is_idempotent(self):
        first = self.tick(T0, scripted(OPEN_BTC))
        log = (self.data / "x" / "events.jsonl").read_text()
        again = self.tick(T0, scripted(OPEN_BTC))
        self.assertEqual(again, first)
        self.assertEqual((self.data / "x" / "events.jsonl").read_text(), log)

    def test_funding_settles_each_full_hour_since_last_tick(self):
        self.tick(T0, scripted(OPEN_BTC))
        flat = [bar("BTC", f"2026-10-19T0{h}:00:00Z", 100010) for h in (2, 3, 4)]  # notional stays 10,000
        rates = [rate("BTC", "2026-10-19T02:00:00Z", 0.0001), rate("BTC", "2026-10-19T03:00:00Z", 0.0002),
                 rate("BTC", "2026-10-19T04:00:00Z", -0.00005)]

        state = self.tick("2026-10-19T04:07:00Z", HOLD, market(flat, rates))

        funding = [e for e in self.events() if e["type"] == "funding"]
        self.assertEqual([e["t"] for e in funding], ["2026-10-19T02:00:00Z", "2026-10-19T03:00:00Z", "2026-10-19T04:00:00Z"])
        self.assertEqual([round(e["amount"], 6) for e in funding], [-1.0, -2.0, 0.5])  # long pays positive rate
        self.assertAlmostEqual(state["layers"][0]["collateral"], 2495.5 - 1 - 2 + 0.5)

    def test_tp_fills_mid_hour_at_tp_with_maker_fee_and_frees_slot(self):
        self.tick(T0, scripted(OPEN_BTC, {"type": "set_tp", "slot": 0, "price": 101010}))
        bars = [bar("BTC", "2026-10-19T01:30:00Z", 100500, h=101000), bar("BTC", "2026-10-19T01:41:00Z", 100900, h=101200)]

        state = self.tick(T1, scripted(OPEN_BTC), market(bars))

        tp = next(e for e in self.events() if e["type"] == "tp")
        self.assertEqual(tp["t"], "2026-10-19T01:41:00Z")
        self.assertEqual(tp["price"], 101010)
        self.assertAlmostEqual(tp["pnl"], 99.990001, places=5)  # 1,000 × 10,000 / 100,010
        self.assertAlmostEqual(tp["fee"], 1.5149985, places=6)  # 0.015% of 101,010 × size
        self.assertAlmostEqual(tp["hostage"], 2495.5 + 99.990001 - 1.5149985 - 2500, places=5)
        self.assertEqual(state["layers"][0]["entry"], 100010.0)  # re-opened in the same Tick
        self.assertAlmostEqual(state["free_equity"], 7500 + 2495.5 + 99.990001 - 1.5149985 - 2500, places=5)

    def test_layer_liquidated_when_bar_low_breaches_maintenance(self):
        self.tick(T0, scripted(OPEN_BTC))
        # maintenance 10,000 / (2 × 40) = 125 → liq px = 100,010 − (2,495.5 − 125) / size ≈ 76,302.6
        bars = [bar("BTC", "2026-10-19T01:20:00Z", 80000, l=76400), bar("BTC", "2026-10-19T01:21:00Z", 77000, l=76300)]

        state = self.tick(T1, HOLD, market(bars))

        liq = next(e for e in self.events() if e["type"] == "liquidation")
        self.assertEqual((liq["t"], liq["slot"], liq["price"]), ("2026-10-19T01:21:00Z", 0, 76300))
        self.assertIsNone(state["layers"][0])
        self.assertEqual(state["free_equity"], 7500)  # collateral is gone, nothing returned

    def test_accumulated_funding_alone_can_liquidate_a_layer(self):
        self.tick(T0, scripted(OPEN_BTC))
        bars = [bar("BTC", "2026-10-19T02:00:00Z", 100010), bar("BTC", "2026-10-19T03:00:00Z", 100010)]
        # 1,200 per hour: 2,495.5 → 1,295.5 survives, → 95.5 ≤ maintenance 125 does not
        rates = [rate("BTC", "2026-10-19T02:00:00Z", 0.12), rate("BTC", "2026-10-19T03:00:00Z", 0.12)]

        state = self.tick("2026-10-19T03:07:00Z", HOLD, market(bars, rates))

        settled = self.events()[-4:-1]
        self.assertEqual([(e["t"], e["type"]) for e in settled], [("2026-10-19T02:00:00Z", "funding"),
                         ("2026-10-19T03:00:00Z", "funding"), ("2026-10-19T03:00:00Z", "liquidation")])
        self.assertAlmostEqual(settled[-1]["collateral_lost"], 95.5)
        self.assertIsNone(state["layers"][0])

    def test_funding_hour_settles_even_when_no_bar_reached_it(self):
        self.tick(T0, scripted(OPEN_BTC))
        lagging = [bar("BTC", "2026-10-19T01:30:00Z", 100010)]  # feed stops before 02:00

        state = self.tick(T1, HOLD, market(lagging, [rate("BTC", "2026-10-19T02:00:00Z", 0.0001)]))

        funding = [e for e in self.events() if e["type"] == "funding"]
        self.assertEqual([(e["t"], round(e["amount"], 6)) for e in funding], [("2026-10-19T02:00:00Z", -1.0)])
        self.assertAlmostEqual(state["layers"][0]["collateral"], 2495.5 - 1)

    def test_short_receives_positive_funding_and_tp_fills_on_bar_low(self):
        self.tick(T0, scripted(SHORT_BTC, {"type": "set_tp", "slot": 0, "price": 99000}))
        bars = [bar("BTC", "2026-10-19T02:00:00Z", 99990, h=100500, l=98900)]  # notional at 99,990 = 10,000

        state = self.tick(T1, HOLD, market(bars, [rate("BTC", "2026-10-19T02:00:00Z", 0.0001)]))

        funding, tp = self.events()[-3:-1]
        self.assertAlmostEqual(funding["amount"], 1.0)
        self.assertEqual((tp["type"], tp["price"]), ("tp", 99000))
        self.assertAlmostEqual(tp["pnl"], 990 * 10000 / 99990)
        self.assertAlmostEqual(state["free_equity"], 7500 + 2495.5 + 1 + 990 * 10000 / 99990 - 99000 * 10000 / 99990 * 0.00015)

    def test_short_liquidated_on_bar_high(self):
        self.tick(T0, scripted(SHORT_BTC))
        # liq px = 99,990 + (2,495.5 − 125) / size ≈ 123,692
        bars = [bar("BTC", "2026-10-19T01:20:00Z", 120000, h=123600), bar("BTC", "2026-10-19T01:21:00Z", 123000, h=123700)]

        state = self.tick(T1, HOLD, market(bars))

        liq = self.events()[-2]
        self.assertEqual((liq["type"], liq["t"], liq["price"]), ("liquidation", "2026-10-19T01:21:00Z", 123700))
        self.assertIsNone(state["layers"][0])

    def test_short_close_buys_back_at_best_ask(self):
        self.tick(T0, scripted(SHORT_BTC))
        self.tick(T1, scripted({"type": "close", "slot": 0}))
        close = self.events()[-1]
        self.assertEqual(close["price"], 100010.0)
        self.assertAlmostEqual(close["pnl"], -20 * 10000 / 99990)

    def test_liquidation_beats_tp_in_the_same_bar(self):
        self.tick(T0, scripted(OPEN_BTC, {"type": "set_tp", "slot": 0, "price": 101010}))
        bars = [bar("BTC", "2026-10-19T01:30:00Z", 100000, h=101200, l=76000)]

        state = self.tick(T1, HOLD, market(bars))

        self.assertEqual([e["type"] for e in self.events()[-2:]], ["liquidation", "decision"])
        self.assertEqual(state["free_equity"], 7500)

    def test_close_returns_collateral_plus_pnl_minus_taker_fee(self):
        self.tick(T0, scripted(OPEN_BTC))

        state = self.tick(T1, scripted({"type": "close", "slot": 0}))

        close = self.events()[-1]
        self.assertEqual((close["type"], close["t"], close["price"]), ("close", T1, 99990.0))  # long exits at best bid
        self.assertAlmostEqual(close["pnl"], -1.9998, places=4)  # −20 × 10,000 / 100,010
        self.assertAlmostEqual(close["fee"], 4.4991001, places=6)
        self.assertEqual(close["hostage"], 0)
        self.assertIsNone(state["layers"][0])
        self.assertAlmostEqual(state["free_equity"], 7500 + 2495.5 - 1.9998 - 4.4991001, places=4)

    def test_set_tp_replaces_and_cancel_tp_removes(self):
        self.tick(T0, scripted(OPEN_BTC, {"type": "set_tp", "slot": 0, "price": 101010},
                               {"type": "set_tp", "slot": 0, "price": 102000}))
        state = self.tick(T1, HOLD, market([bar("BTC", "2026-10-19T01:30:00Z", 101500, h=101500)]))
        self.assertEqual(state["layers"][0]["tp"], 102000)

        state = self.tick("2026-10-19T03:07:00Z", scripted({"type": "cancel_tp", "slot": 0, "price": 101010}))
        self.assertIsNone(state["layers"][0]["tp"])

    def test_tp_and_close_violations(self):
        cases = [
            ("tp_wrong_side", {"type": "set_tp", "slot": 0, "price": 99000}),  # below a long's entry
            ("layer_empty", {"type": "close", "slot": 1}),
            ("layer_empty", {"type": "set_tp", "slot": 1, "price": 101010}),
            ("layer_empty", {"type": "cancel_tp", "slot": 1}),
            ("slot_out_of_range", {"type": "cancel_tp", "slot": 7}),
        ]
        for rule, action in cases:
            name = f"{rule}_{action['type']}"
            with self.subTest(name):
                state = self.tick(T0, scripted(OPEN_BTC, action), contestant=name)
                self.assertEqual(self.events(name)[-1], {"t": T0, "type": "violation", "rule": rule, "action": action})
                self.assertIsNone(state["layers"][0]["tp"])
                self.assertIsNone(state["layers"][1])

    def test_executor_sees_events_settled_since_last_tick(self):
        self.tick(T0, scripted(OPEN_BTC))
        seen = []

        def executor(given):
            seen.append(given)
            return {"reasoning": "", "actions": [{"type": "hold"}]}

        self.tick(T1, executor, market([bar("BTC", "2026-10-19T01:20:00Z", 80000, l=76000)]))

        self.assertEqual([e["type"] for e in seen[0]["settled"]], ["liquidation"])
        self.assertIsNone(seen[0]["state"]["layers"][0])

    def test_executor_sees_violations_from_previous_tick_only(self):
        self.tick(T0, scripted(OPEN_BTC, OPEN_BTC))
        seen = []

        def executor(given):
            seen.append(given["violations"])
            return {"reasoning": "", "actions": [{"type": "hold"}]}

        self.tick(T1, executor)
        self.tick("2026-10-19T03:07:00Z", executor)

        self.assertEqual(seen, [[{"t": T0, "type": "violation", "rule": "layer_occupied", "action": OPEN_BTC}], []])

    def test_gap_beyond_1m_history_settles_on_coarser_bars(self):
        cases = {  # Hyperliquid serves at most 5,000 bars: 1m covers ~3.5 days, 15m ~52 days
            "15m": ("2026-10-23T01:07:00Z", "2026-10-21T10:15:00Z"),
            "1h": ("2026-12-20T01:07:00Z", "2026-11-30T10:00:00Z"),
        }
        for interval, (at, crash_at) in cases.items():
            with self.subTest(interval):
                self.tick(T0, scripted(OPEN_BTC), contestant=interval)
                bars = [bar("BTC", "2026-10-20T00:00:00Z", 80000, l=76000),  # 1m bar the Engine must not see
                        bar("BTC", crash_at, 80000, l=76000, i=interval)]

                self.tick(at, HOLD, market(bars), contestant=interval)

                liq = next(e for e in self.events(interval) if e["type"] == "liquidation")
                self.assertEqual((liq["t"], liq["resolution"]), (crash_at, interval))

    def test_settles_recorded_live_hyperliquid_data(self):
        """Guards the in-memory fakes above: real candle/funding shapes and time filters (recorded 2026-10-18)."""
        live = replay(Path(__file__).parent / "fixtures" / "live_btc")
        btc_only = {**PLAN, "watchlist": PLAN["watchlist"][:1]}  # only BTC's book was recorded
        self.tick("2026-10-18T08:07:00Z", scripted(OPEN_BTC), live, plan=btc_only)

        state = self.tick("2026-10-18T11:07:00Z", HOLD, live, plan=btc_only)

        funding = [e for e in self.events() if e["type"] == "funding"]
        self.assertEqual([e["t"] for e in funding], ["2026-10-18T09:00:00Z", "2026-10-18T10:00:00Z", "2026-10-18T11:00:00Z"])
        self.assertEqual([e["rate"] for e in funding], [8.817e-07, 1.4945e-06, 2.6977e-06])
        self.assertTrue(all(e["amount"] < 0 and e["resolution"] == "1m" for e in funding))
        self.assertEqual(state["layers"][0]["symbol"], "BTC")

    def test_recorded_market_replays_to_identical_state(self):
        recorded = Path(tempfile.mkdtemp())
        self.tick(T0, scripted(OPEN_BTC), source=recording(replay(FIXTURES), recorded), contestant="live")
        self.tick(T0, scripted(OPEN_BTC), source=replay(recorded), contestant="replayed")

        for f in ("state.json", "events.jsonl"):
            self.assertEqual((self.data / "replayed" / f).read_bytes(), (self.data / "live" / f).read_bytes())


if __name__ == "__main__":
    unittest.main()
