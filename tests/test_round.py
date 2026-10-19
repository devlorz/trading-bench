import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bench.engine import run_tick, run_week
from bench.export import export
from tests.helpers import CONFIG, OPEN_BTC, bar, market, rate

W1, T0, T1, T2 = "2026-10-19T00:07:00Z", "2026-10-19T01:07:00Z", "2026-10-19T02:07:00Z", "2026-10-19T03:07:00Z"
W2, W3 = "2026-10-26T00:07:00Z", "2026-11-02T00:07:00Z"
PLAN = {"notional": 5000, "watchlist": [{"symbol": "BTC", "bias": "both", "entry": "x", "exit": "y"}],
        "close_all": "never", "hostage_policy": "reopen", "rationale": "r"}
PAIRS = {**CONFIG, "contestants": [{"name": "a", "strategist": "a-big", "executor": "a-small"},
                                   {"name": "b", "strategist": "b-big", "executor": "b-small"}]}
HOLD = {"reasoning": "wait", "actions": [{"type": "hold"}]}


def client(replies, calls):
    """Model client keyed by model id; logs every model id it is called with."""
    def model(model_id, request):
        calls.append(model_id)
        return replies[model_id]
    return model


class RunRound(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())
        self.calls = []
        self.replies = {"a-big": {**PLAN, "notional": 6000}, "b-big": PLAN,
                        "a-small": {"reasoning": "go", "actions": [OPEN_BTC]}, "b-small": HOLD}

    def run_both(self, run, at, source=None):
        return run(at, source or market(), client(self.replies, self.calls), self.data, PAIRS)

    def state(self, name):
        return json.loads((self.data / name / "state.json").read_text())

    def export(self):
        export(self.data, self.data / "site", PAIRS)
        return lambda name: json.loads((self.data / "site" / f"{name}.json").read_text())

    def test_every_contestant_runs_in_config_order_with_its_own_models_and_account(self):
        self.run_both(run_week, W1)
        self.run_both(run_tick, T0)

        self.assertEqual(self.calls, ["a-big", "b-big", "a-small", "b-small"])
        a, b = self.state("a"), self.state("b")
        self.assertEqual((a["rp"]["notional"], a["layers"][0]["notional"]), (6000, 6000))
        self.assertEqual((b["rp"]["notional"], b["layers"]), (5000, [None] * 4))
        layer = self.export()("a")["layers"][0]
        self.assertEqual(sorted(layer), ["entry", "liq", "mark", "notional", "side", "symbol", "tp", "unrealized"])
        size = 6000 / 100010
        self.assertEqual((layer["symbol"], layer["mark"]), ("BTC", 100000.0))  # mark from metaAndAssetCtxs
        self.assertAlmostEqual(layer["unrealized"], size * (100000 - 100010))
        self.assertAlmostEqual(layer["liq"], 100010 - (2500 - 2.7 - 6000 / 80) / size)  # maintenance = notional / (2 x 40)

        self.run_both(run_week, W2)  # a still holds BTC, so only b reallocates
        rows = {r["name"]: r for r in self.export()("index")["leaderboard"]}
        self.assertEqual((rows["a"]["reallocation_weeks"], rows["b"]["reallocation_weeks"]), (1, 2))

    def test_market_failure_mid_round_skips_the_tick_for_every_contestant(self):
        self.replies["a-small"], self.replies["b-small"] = HOLD, self.replies["a-small"]
        self.run_both(run_week, W1)
        before = {n: (self.data / n / "events.jsonl").read_text() for n in "ab"}
        del self.calls[:]

        def no_book(body):  # a has finished its Tick; b's open then fails at the L2 book
            if body["type"] == "l2Book":
                raise TimeoutError("l2Book timed out")
            return market()(body)

        self.assertFalse(self.run_both(run_tick, T0, no_book))

        self.assertEqual(self.calls, [])  # every book is fetched before the first paid model call

        for n in "ab":
            self.assertEqual((self.data / n / "events.jsonl").read_text(), before[n])
            self.assertNotIn("last_tick", self.state(n))
        runs = [json.loads(l) for l in (self.data / "runs.jsonl").read_text().splitlines()]
        self.assertEqual(runs, [{"t": W1, "type": "week", "status": "ok"},
                                {"t": T0, "type": "tick", "status": "skipped", "reason": "TimeoutError: l2Book timed out"}])
        self.assertEqual(self.export()("index")["last_run"], runs[-1])
        self.run_both(run_tick, "2026-10-19T02:07:00Z")  # the next Tick runs normally
        self.assertEqual(self.state("b")["layers"][0]["symbol"], "BTC")

    def test_contestant_below_1000_after_settle_is_eliminated_and_never_called_again(self):
        self.replies["a-big"] = {**PLAN, "notional": 100000}  # 40x, BTC's max
        self.replies["a-small"] = {"reasoning": "all in", "actions": [{**OPEN_BTC, "slot": s} for s in range(4)]}
        crash = market([bar("BTC", "2026-10-19T01:30:00Z", 100000, l=98000)])  # liquidates every Layer
        self.run_both(run_week, W1)
        self.run_both(run_tick, T0)
        del self.calls[:]

        self.run_both(run_tick, T1, crash)
        frozen = (self.data / "a" / "events.jsonl").read_text()
        self.run_both(run_tick, T2, crash)
        self.run_both(run_week, W2, crash)

        self.assertEqual(self.calls, ["b-small", "b-small", "b-big"])
        self.assertEqual(self.state("a")["eliminated"], "2026-10-19T00:00:00Z")
        last = json.loads(frozen.splitlines()[-1])
        self.assertEqual((last["t"], last["type"], last["week"], last["equity"]),
                         (T1, "elimination", "2026-10-19T00:00:00Z", 0))
        self.assertEqual((self.data / "a" / "events.jsonl").read_text(), frozen)
        index = self.export()("index")
        self.assertEqual([(r["name"], r["eliminated"], r["equity"]) for r in index["leaderboard"]],
                         [("b", None, 10000), ("a", "2026-10-19T00:00:00Z", 0)])
        self.assertEqual([t for t, _ in index["equity"]["a"]], [T0, T1])  # stops at the score

    def test_week_that_settles_the_crash_eliminates_before_asking_the_strategist(self):
        self.replies["a-big"] = {**PLAN, "notional": 100000}
        self.replies["a-small"] = {"reasoning": "all in", "actions": [{**OPEN_BTC, "slot": s} for s in range(4)]}
        self.run_both(run_week, W1)
        self.run_both(run_tick, T0)
        del self.calls[:]

        self.run_both(run_week, W2, market([bar("BTC", "2026-10-25T12:00:00Z", 100000, l=98000, i="15m")]))

        self.assertEqual(self.calls, ["b-big"])
        self.assertEqual(self.state("a")["eliminated"], "2026-10-26T00:00:00Z")

    def test_export_ranks_by_net_return_with_metrics_rebuilt_from_the_logs(self):
        eth_short = {"type": "open", "slot": 0, "symbol": "ETH", "side": "short"}
        self.replies.update({
            "a-big": {**PLAN, "notional": 10000},
            "a-small": {"reasoning": "go", "actions": [OPEN_BTC, OPEN_BTC]},  # the second is layer_occupied
            "b-big": {**PLAN, "notional": 62500, "watchlist": [{"symbol": "ETH", "bias": "short", "entry": "x", "exit": "y"}]},
            "b-small": {"reasoning": "fade", "actions": [eth_short]},
        })
        self.run_both(run_week, W1)
        self.run_both(run_tick, T0)
        self.replies.update({"a-small": {"reasoning": "out", "actions": [{"type": "close", "slot": 0}]}, "b-small": HOLD})
        spike = market([bar("ETH", "2026-10-19T01:30:00Z", 4000, h=4200)],  # liquidates b's 25x short
                       [rate("BTC", "2026-10-19T02:00:00Z", 0.0001)])  # a's long pays 10,000 x 0.01% at entry price
        self.run_both(run_tick, T1, spike)

        read = self.export()
        index = read("index")
        size = 10000 / 100010  # a's BTC, bought at the ask
        exit_fee = size * 99990 * 0.00045
        a_net = -4.5 - 1.0 + size * (99990 - 100010) - exit_fee  # entry fee, funding, price, exit fee
        self.assertEqual((index["last_run"], index["initial_capital"]), ({"t": T1, "type": "tick", "status": "ok"}, 10000))
        a, b = index["leaderboard"]
        self.assertEqual((a["name"], b["name"]), ("a", "b"))
        expected = {
            "a": {"equity": 10000 + a_net, "net_return": a_net / 10000, "max_drawdown": -a_net / 10000,
                  "closed_positions": 1, "win_rate": 0, "avg_pnl": a_net, "liquidations": 0, "violations": 1,
                  "fees": 4.5 + exit_fee, "funding": -1.0, "reallocation_weeks": 1},
            "b": {"equity": 7500, "net_return": -0.25, "max_drawdown": 0.25, "closed_positions": 1, "win_rate": 0,
                  "avg_pnl": -2500, "liquidations": 1, "violations": 0, "fees": 62500 * 0.00045, "funding": 0,
                  "reallocation_weeks": 1},
        }
        for row in (a, b):
            for key, value in expected[row["name"]].items():
                self.assertAlmostEqual(row[key], value, msg=f"{row['name']} {key}")
        self.assertEqual([t for t, _ in index["equity"]["a"]], [T0, T1])

        a_page, b_page = read("a"), read("b")
        closed = a_page["positions"][0]
        self.assertEqual(sorted(closed), ["closed_at", "entry", "exit", "fees", "funding", "opened_at", "pnl", "reason",
                                          "side", "symbol"])
        self.assertEqual({k: closed[k] for k in ("symbol", "side", "opened_at", "closed_at", "entry", "exit", "reason")},
                         {"symbol": "BTC", "side": "long", "opened_at": T0, "closed_at": T1,
                          "entry": 100010.0, "exit": 99990.0, "reason": "close"})
        self.assertAlmostEqual(closed["pnl"], a_net)
        self.assertAlmostEqual(closed["fees"], 4.5 + exit_fee)
        self.assertAlmostEqual(closed["funding"], -1.0)
        self.assertEqual((b_page["positions"][0]["reason"], b_page["positions"][0]["closed_at"]),
                         ("liquidation", "2026-10-19T01:30:00Z"))
        self.assertEqual([(d["t"], d["reasoning"]) for d in a_page["decisions"]], [(T0, "go"), (T1, "out")])
        self.assertEqual([(v["t"], v["rule"]) for v in a_page["violations"]], [(T0, "layer_occupied")])
        self.assertEqual([(p["week"], p["rationale"], p["notional_used"]) for p in a_page["plans"]],
                         [("2026-10-19T00:00:00Z", "r", True)])
        self.assertEqual(a_page["layers"], [None] * 4)

    def test_contestant_added_mid_benchmark_waits_for_its_first_week_while_the_others_tick(self):
        self.run_both(run_week, W1)
        joined = {**PAIRS, "contestants": PAIRS["contestants"] + [{"name": "c", "strategist": "c-big", "executor": "c-small"}]}

        run_tick(T0, market(), client(self.replies, self.calls), self.data, joined)

        self.assertEqual(self.calls[-2:], ["a-small", "b-small"])
        runs = [json.loads(l) for l in (self.data / "runs.jsonl").read_text().splitlines()]
        self.assertEqual(runs[-1], {"t": T0, "type": "tick", "status": "ok", "waiting_for_week": ["c"]})
        export(self.data, self.data / "site", joined)
        index = json.loads((self.data / "site" / "index.json").read_text())
        self.assertEqual(sorted(r["name"] for r in index["leaderboard"]), ["a", "b"])

        self.replies["c-big"] = PLAN
        run_week(W2, market(), client(self.replies, self.calls), self.data, joined)
        export(self.data, self.data / "site", joined)
        index = json.loads((self.data / "site" / "index.json").read_text())
        self.assertEqual({r["name"]: r["started_week"] for r in index["leaderboard"]},
                         {"a": "2026-10-19T00:00:00Z", "b": "2026-10-19T00:00:00Z", "c": "2026-10-26T00:00:00Z"})

    def test_skipped_week_round_is_the_last_run(self):
        self.run_both(run_week, W1)
        self.run_both(run_tick, T0)

        def down(body):
            raise TimeoutError("metaAndAssetCtxs timed out")

        self.run_both(run_week, W2, down)
        self.assertEqual(self.export()("index")["last_run"],
                         {"t": W2, "type": "week", "status": "skipped", "reason": "TimeoutError: metaAndAssetCtxs timed out"})

    def test_weekly_plans_list_every_week_with_the_plan_in_force_or_none(self):
        broken = {"rationale": "no watchlist"}
        self.replies["a-big"] = broken
        self.run_both(run_week, W1)  # no plan yet: the Executor holds all Week
        self.replies["a-big"] = PLAN
        self.run_both(run_week, W2)
        self.replies["a-big"] = broken
        self.run_both(run_week, W3)  # last week's plan stays in force

        plans = self.export()("a")["plans"]
        self.assertEqual([(p["week"], p["in_force"], p["fallback"], p["reallocated"], p["notional_used"], p.get("rationale"))
                          for p in plans],
                         [("2026-10-19T00:00:00Z", None, True, False, False, None),
                          ("2026-10-26T00:00:00Z", "2026-10-26T00:00:00Z", False, True, True, "r"),
                          ("2026-11-02T00:00:00Z", "2026-10-26T00:00:00Z", True, False, True, "r")])

    def test_book_of_a_layer_held_from_last_weeks_watchlist_is_fetched_before_any_model(self):
        self.run_both(run_week, W1)
        self.run_both(run_tick, T0)  # a holds BTC
        eth_only = {**PLAN, "watchlist": [{"symbol": "ETH", "bias": "both", "entry": "x", "exit": "y"}]}
        self.replies.update({"a-big": eth_only, "b-big": eth_only, "a-small": {"reasoning": "", "actions": [{"type": "close", "slot": 0}]}})
        self.run_both(run_week, W2)
        del self.calls[:]

        def no_btc_book(body):
            if body == {"type": "l2Book", "coin": "BTC"}:
                raise TimeoutError("l2Book timed out")
            return market()(body)

        self.assertFalse(self.run_both(run_tick, "2026-10-26T01:07:00Z", no_btc_book))
        self.assertEqual(self.calls, [])


class Reset(unittest.TestCase):
    def reset(self, cwd, *args):
        """CLI reset run from a scratch working directory, so a broken guard can only delete scratch files."""
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
        return subprocess.run([sys.executable, "-m", "bench", "reset", *args], cwd=cwd, env=env, capture_output=True, text=True)

    def test_reset_removes_state_and_export_for_a_fresh_week_1(self):
        cwd = Path(tempfile.mkdtemp())
        for folder in ("data/a", "site/data"):
            (cwd / folder).mkdir(parents=True)

        result = self.reset(cwd)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(p.name for p in cwd.iterdir()), ["site"])

    def test_reset_refuses_the_working_directory_or_anything_outside_it(self):
        cwd, outside = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (cwd / "data").mkdir()
        for args in (["--data", "."], ["--out", str(outside)], ["--data", "../" + outside.name]):
            with self.subTest(args=args):
                result = self.reset(cwd, *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing", result.stderr)
                self.assertTrue((cwd / "data").exists() and outside.exists())
