import json
import tempfile
import unittest
from pathlib import Path

from bench.engine import run_tick
from bench.market import recording, replay

FIXTURES = Path(__file__).parent / "fixtures" / "btc"
CONFIG = {"initial_capital": 10000, "taker_fee": 0.00045}
PLAN = {
    "notional": 10000,
    "watchlist": [{"symbol": "BTC", "bias": "both"}, {"symbol": "DOGE", "bias": "both"}],
}
T0 = "2026-10-19T01:07:00Z"
T1 = "2026-10-19T02:07:00Z"
OPEN_BTC = {"type": "open", "slot": 0, "symbol": "BTC", "side": "long"}


def scripted(*actions):
    return lambda _input: {"reasoning": "scripted", "actions": list(actions)}


HOLD = scripted({"type": "hold"})


class RunTick(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())

    def tick(self, at, model, market=None, contestant="x"):
        folder = self.data / contestant
        if not folder.exists():
            folder.mkdir()
            (folder / "plan.json").write_text(json.dumps(PLAN))
        run_tick(contestant, at, market or replay(FIXTURES), model, self.data, CONFIG)
        return json.loads((folder / "state.json").read_text())

    def events(self, contestant="x"):
        return [json.loads(l) for l in (self.data / contestant / "events.jsonl").read_text().splitlines()]

    def test_first_tick_reallocates_and_opens_btc_long_at_best_ask(self):
        state = self.tick(T0, scripted(OPEN_BTC))

        self.assertEqual(state["rp"], {"collateral": 2500, "notional": 10000})
        self.assertEqual(state["free_equity"], 7500)
        layer = state["layers"][0]
        self.assertEqual(layer["symbol"], "BTC")
        self.assertEqual(layer["side"], "long")
        self.assertEqual(layer["notional"], 10000)
        self.assertEqual(layer["entry"], 100010.0)
        self.assertAlmostEqual(layer["collateral"], 2500 - 4.5)  # taker fee 0.045% of 10,000
        self.assertEqual(state["layers"][1:], [None, None, None])
        self.assertEqual([e["type"] for e in self.events()], ["reallocation", "decision", "fill"])

    def test_executor_response_is_logged(self):
        self.tick(T0, scripted(OPEN_BTC))
        decision = self.events()[1]
        self.assertEqual(decision["reasoning"], "scripted")
        self.assertEqual(decision["actions"], [OPEN_BTC])

    def test_short_fills_at_best_bid(self):
        state = self.tick(T0, scripted({**OPEN_BTC, "slot": 2, "side": "short"}))
        self.assertEqual(state["layers"][2]["entry"], 99990.0)

    def test_open_violations_are_rejected_and_logged(self):
        cases = {
            "layer_occupied": [OPEN_BTC, OPEN_BTC],
            "slot_out_of_range": [{**OPEN_BTC, "slot": 4}],
            "symbol_not_in_watchlist": [{**OPEN_BTC, "symbol": "ETH"}],
            "exceeds_max_leverage": [{**OPEN_BTC, "symbol": "DOGE"}],  # 10,000 / 2,500 = 4x > DOGE 3x
        }
        for rule, actions in cases.items():
            with self.subTest(rule):
                state = self.tick(T0, scripted(*actions), contestant=rule)
                violation = self.events(rule)[-1]
                self.assertEqual(violation["type"], "violation")
                self.assertEqual(violation["rule"], rule)
                self.assertEqual(violation["action"], actions[-1])
                self.assertEqual(state["free_equity"], 10000 - 2500 * (len(actions) - 1))

    def test_open_rejected_when_free_equity_below_collateral(self):
        self.tick(T0, HOLD)
        # Temporary: writes state directly because no Tick can drain free equity yet.
        # Move onto the seam (liquidate a Layer) once ticket 03 lands.
        state_file = self.data / "x" / "state.json"
        state_file.write_text(json.dumps({**json.loads(state_file.read_text()), "free_equity": 2000}))

        state = self.tick(T1, scripted(OPEN_BTC))

        self.assertEqual(self.events()[-1]["rule"], "insufficient_free_equity")
        self.assertEqual(state["free_equity"], 2000)
        self.assertIsNone(state["layers"][0])

    def test_unsupported_action_is_a_violation(self):
        close = {"type": "close", "slot": 0}
        state = self.tick(T0, scripted(close, OPEN_BTC))
        types = [e["type"] for e in self.events()]
        self.assertEqual(types, ["reallocation", "decision", "violation", "fill"])
        self.assertEqual(self.events()[2]["rule"], "unsupported_action")
        self.assertEqual(state["layers"][0]["symbol"], "BTC")

    def test_hold_leaves_state_unchanged(self):
        before = self.tick(T0, scripted(OPEN_BTC))
        after = self.tick(T1, HOLD)
        self.assertEqual({**after, "last_tick": None}, {**before, "last_tick": None})
        self.assertEqual([e["type"] for e in self.events()], ["reallocation", "decision", "fill", "decision"])

    def test_rerunning_same_tick_is_idempotent(self):
        first = self.tick(T0, scripted(OPEN_BTC))
        log = (self.data / "x" / "events.jsonl").read_text()
        again = self.tick(T0, scripted(OPEN_BTC))
        self.assertEqual(again, first)
        self.assertEqual((self.data / "x" / "events.jsonl").read_text(), log)

    def test_recorded_market_replays_to_identical_state(self):
        recorded = Path(tempfile.mkdtemp())
        self.tick(T0, scripted(OPEN_BTC), market=recording(replay(FIXTURES), recorded), contestant="live")
        self.tick(T0, scripted(OPEN_BTC), market=replay(recorded), contestant="replayed")

        for f in ("state.json", "events.jsonl"):
            self.assertEqual((self.data / "replayed" / f).read_bytes(), (self.data / "live" / f).read_bytes())


if __name__ == "__main__":
    unittest.main()
