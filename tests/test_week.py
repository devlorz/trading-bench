import hashlib
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bench.engine import ms, run_tick, run_week
from bench.market import BAR_MS, PROMPT_ENCODING_VERSION
from bench.indicators import INDICATOR_PACK_VERSION
from tests.helpers import FAKE_TSM, OPEN_BTC, bar, market, rate, recorded, scripted, solo

LIVE = recorded(Path(__file__).parent / "fixtures" / "live_btc")  # recorded metaAndAssetCtxs: 234 perps, 56 delisted

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
UNIVERSE_MAX_CHARS = 130_000  # ADR-0003 encoding; the live recording of 2026-10-19 measured 126k
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
        config, client = solo("x", model)
        return run_week(at, source or market(), client, self.data, config)

    def tick(self, at, model, source=None):
        config, client = solo("x", model)
        run_tick(at, source or market(), client, self.data, config)
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

    def test_strategist_reads_the_full_tsm_from_the_path_in_the_env_var(self):
        seen = []
        self.week(W1, strategist(PLAN, seen=seen))

        self.assertEqual(seen[0]["role"], "strategist")
        self.assertEqual(seen[0]["tsm"], FAKE_TSM.read_text())
        [record] = [json.loads(l) for l in (self.data / "x" / "responses.jsonl").read_text().splitlines()]
        self.assertEqual((record["role"], record["model"]), ("strategist", "strategist"))
        self.assertEqual(record["tsm_sha256"], hashlib.sha256(FAKE_TSM.read_bytes()).hexdigest())
        self.assertEqual(record["prompt_encoding_version"], PROMPT_ENCODING_VERSION)

    def test_week_fails_naming_the_env_var_when_the_full_tsm_cannot_be_read(self):
        unreadable = self.data / "locked.md"
        unreadable.write_text("TSM")
        unreadable.chmod(0)
        for path in (None, "", str(self.data / "nowhere.md"), str(self.data), str(unreadable)):
            with self.subTest(path), patch.dict(os.environ):
                os.environ.pop("TSM_FULL_PATH")
                if path is not None:
                    os.environ["TSM_FULL_PATH"] = path
                with self.assertRaises(RuntimeError) as raised:
                    self.week(W1, strategist(PLAN))
                self.assertIn("TSM_FULL_PATH", str(raised.exception))
                self.assertIn(repr(path), str(raised.exception))  # the path as given, even an empty one
                self.assertFalse((self.data / "x").exists())

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

    def test_strategist_sees_candles_packs_and_last_weeks_vwap_and_funding_per_universe_symbol(self):
        candles = [bar("BTC", "2026-10-11T23:45:00Z", 999, i="15m"),  # before last Monday: outside the VWAP
                   bar("BTC", "2026-10-12T00:00:00Z", 100, h=103, l=97, i="15m"),  # typical 100
                   bar("BTC", "2026-10-18T23:45:00Z", 200, i="15m"),
                   bar("BTC", "2026-10-19T00:00:00Z", 999, i="15m"),  # still forming at W1
                   *[bar("BTC", f"2026-09-{d:02}T00:00:00Z", 100 + d, i="1d") for d in range(1, 31)],
                   *[bar("BTC", f"2026-10-{d:02}T00:00:00Z", 130 + d, i="1d") for d in range(1, 19)],
                   bar("BTC", "2026-10-12T00:00:00Z", 140, i="1w")]
        funding = [rate("BTC", "2026-10-12T00:00:00Z", 0.0001), rate("BTC", "2026-10-18T23:00:00Z", 0.0003),
                   rate("BTC", "2026-10-11T23:00:00Z", 0.01),  # before last Monday
                   rate("BTC", "2026-10-19T00:00:00Z", 0.01)]  # this Week's first hour, like the VWAP's forming bar
        seen = []
        self.week(W1, strategist(PLAN, seen=seen), market(candles, funding))

        universe = {u["symbol"]: u for u in seen[0]["universe"]}
        btc = universe["BTC"]
        self.assertEqual((btc["vwap_last_week"]["vwap"], btc["vwap_last_week"]["bars"]), (150, 2))
        self.assertAlmostEqual(btc["funding_last_week"], 0.0002)
        self.assertEqual(len(btc["candles"]["1d"]["bars"]), 30)
        self.assertEqual(btc["candles"]["1d"]["bars"][-1][3], 148)  # Oct 18 close, the last closed day
        self.assertEqual(btc["candles"]["1d"]["pack"]["version"], INDICATOR_PACK_VERSION)
        self.assertEqual(btc["candles"]["1w"], {"start": ms("2026-10-12T00:00:00Z"), "interval": "1w",
                                                "bars": [[140, 140, 140, 140, 1]]})
        # every float sent is cut to 5 significant figures, after it is computed at full precision
        self.assertEqual((btc["change_24h"], btc["change_7d"], btc["change_30d"]), (0.68027, 4.9645, 25.424))
        for symbol in ("ETH", "DOGE"):  # no candles: the pack is still attached
            self.assertEqual(universe[symbol]["candles"]["1d"]["pack"]["version"], INDICATOR_PACK_VERSION)

    def test_universe_candles_are_compact_and_decode_back_to_the_bars_sent(self):
        meta, ctxs = LIVE({"type": "metaAndAssetCtxs"})
        decimals = {a["name"]: a["szDecimals"] for a in meta["universe"]}
        marks = {a["name"]: float(c["markPx"]) for a, c in zip(meta["universe"], ctxs)}
        coins_a_day = {a["name"]: float(c["dayNtlVlm"]) / float(c["markPx"]) for a, c in zip(meta["universe"], ctxs)}

        def exchange_price(symbol, px):
            """How Hyperliquid quotes: at most 5 significant figures and 6 - szDecimals decimals; integers always."""
            places = max(0, min(6 - decimals[symbol], 4 - math.floor(math.log10(px))))
            return f"{round(px, places):.{places}f}"

        made = {}

        def info(body):  # every symbol gets full history at the exchange's own precision
            if body["type"] != "candleSnapshot":
                return LIVE(body)
            r, step = body["req"], BAR_MS[body["req"]["interval"]]
            first = r["startTime"] - r["startTime"] % step + (step if r["startTime"] % step else 0)
            bars = []
            for t in range(first, r["endTime"] + 1, step):
                k = t // step
                o, h, l, c = (marks[r["coin"]] * (1 + 0.03 * math.sin(k + d)) for d in (0, 0.3, 0.6, 0.9))
                px = [exchange_price(r["coin"], p) for p in (o, max(o, h, l, c), min(o, h, l, c), c)]
                bars.append({"t": t, "T": t + step - 1, "o": px[0], "h": px[1], "l": px[2], "c": px[3],
                             # volume in coins, as Hyperliquid reports it: billions for cheap perps
                             "v": f"{coins_a_day[r['coin']] * step / BAR_MS['1d'] * (0.7 + 0.1 * (k % 7)):.5f}",
                             "n": 100 + k % 50})
            made[r["coin"], r["interval"]] = bars
            return bars

        seen = []
        self.week(W1, strategist(PLAN, seen=seen), info)

        universe = seen[0]["universe"]
        self.assertEqual(len(universe), 50)
        self.assertLessEqual(len(json.dumps(universe, separators=(",", ":"))), UNIVERSE_MAX_CHARS)  # as the prompt sends it
        for u in universe:
            for interval, series in u["candles"].items():
                closed = [b for b in made[u["symbol"], interval] if b["T"] < ms(W1)]
                sent = closed[-len(series["bars"]):]
                self.assertEqual(len(series["bars"]), {"1d": 30, "1w": 12}[interval])
                for i, (bar_, original) in enumerate(zip(series["bars"], sent)):
                    self.assertEqual(series["start"] + i * BAR_MS[series["interval"]], original["t"])
                    self.assertEqual(bar_[:4], [float(original[k]) for k in "ohlc"])  # prices are already on tick
                    self.assertLessEqual(abs(bar_[4] - float(original["v"])), 0.5)

    def test_strategist_sees_top_50_by_volume_and_may_pick_any_listed_symbol(self):
        tnsr = {**PLAN["watchlist"][0], "symbol": "TNSR"}  # lowest 24h volume of the listed perps
        matic = {**tnsr, "symbol": "MATIC"}  # delisted
        seen = []

        self.week(W1, strategist({**PLAN, "watchlist": [matic]}, {**PLAN, "watchlist": [tnsr]}, seen=seen), LIVE)

        universe = seen[0]["universe"]
        self.assertEqual(len(universe), 50)
        self.assertLessEqual({"symbol": "BTC", "day_volume": 1.0100e9, "mark": 81959.0,
                              "funding": -0.0000007678, "open_interest": 41577.0, "max_leverage": 40}.items(),
                             universe[0].items())
        self.assertNotIn("TNSR", [u["symbol"] for u in universe])
        self.assertIn("TNSR", seen[0]["symbols"])
        self.assertNotIn("MATIC", seen[0]["symbols"])
        self.assertEqual(self.events()[0]["error"], "MATIC is not on Hyperliquid")
        self.assertEqual(self.plan_in_force()["watchlist"], [tnsr])

    def test_strategist_sees_last_weeks_plan_trades_and_violations(self):
        self.week(W1, strategist(PLAN))
        self.tick("2026-10-19T01:07:00Z", scripted(OPEN_BTC, OPEN_BTC))
        self.tick("2026-10-19T02:07:00Z", scripted({"type": "close", "slot": 0}),
                  market(funding=[rate("BTC", "2026-10-19T02:00:00Z", 0.0001)]))
        seen = []

        self.week(W2, strategist(PLAN, seen=seen))

        # funding shows in collateral and holds carry no trade: neither comes back (spec: trades and reasoning)
        self.assertIn("funding", [e["type"] for e in self.events()])

        self.assertEqual(seen[0]["previous_plan"], {**PLAN, "week": WEEK1})
        self.assertEqual([e["type"] for e in seen[0]["last_week"]],
                         ["plan", "reallocation", "decision", "fill", "violation", "decision", "close"])
        self.assertEqual(seen[0]["last_week"][2]["reasoning"], "scripted")

        self.tick("2026-10-26T01:07:00Z", scripted({"type": "hold"}))
        self.week("2026-11-02T00:07:00Z", strategist(PLAN, seen=seen))

        self.assertEqual([e["type"] for e in seen[1]["last_week"]], ["plan", "reallocation"])  # since W2 only

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

    def test_rerun_within_the_week_asks_hyperliquid_nothing_and_logs_nothing(self):
        # the hourly workflow runs run-week before every Tick, so a Week that has its plan must cost nothing
        self.week(W1, strategist(PLAN))
        runs = (self.data / "runs.jsonl").read_bytes()

        def down(_body):
            raise OSError("Hyperliquid down")

        self.assertFalse(self.week("2026-10-21T12:07:00Z", strategist(), down))

        self.assertEqual((self.data / "runs.jsonl").read_bytes(), runs)

    def test_timestamps_with_an_offset_are_stored_as_utc(self):
        self.week("2026-10-19T07:07:00+07:00", strategist(PLAN))

        self.assertEqual(self.plan_in_force()["week"], WEEK1)
        self.assertTrue((self.data / "x" / "plans" / "2026-10-19.json").exists())

    def test_tick_before_any_week_waits_for_it(self):
        config, client = solo("x", scripted({"type": "hold"}))
        self.assertFalse(run_tick(W1, market(), client, self.data, config))
        self.assertFalse((self.data / "x").exists())


if __name__ == "__main__":
    unittest.main()
