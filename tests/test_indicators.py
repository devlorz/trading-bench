import json
import unittest
from pathlib import Path

from bench.engine import ms
from bench.indicators import INDICATOR_PACK_VERSION, pack, pct_change, vwap
from bench.market import bars_between, candles, replay

FIXTURES = Path(__file__).parent / "fixtures" / "indicators"
AT = "2026-10-19T09:07:00Z"
REFERENCE = json.loads((FIXTURES / "reference.json").read_text())  # from make_reference.py (pandas), not bench code


def series(interval):
    return candles(replay(FIXTURES), "BTC", interval, ms(AT))


class Candles(unittest.TestCase):
    def test_fetches_200_closed_bars_in_one_call(self):
        calls = []
        source = replay(FIXTURES)
        bars = candles(lambda body: calls.append(body) or source(body), "BTC", "1h", ms(AT))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(bars), 200)
        self.assertTrue(all(b["T"] < ms(AT) for b in bars))  # the bar still forming at AT is dropped
        self.assertEqual(bars[-1]["t"], ms("2026-10-19T08:00:00Z"))
        self.assertEqual([b["t"] for b in bars], sorted(b["t"] for b in bars))

    def test_bars_between_drops_the_bar_opening_at_end_which_hyperliquid_returns(self):
        served = [{"t": t} for t in (0, 60_000, 120_000)]  # endTime is inclusive on Hyperliquid
        self.assertEqual(bars_between(lambda _body: served, "BTC", "1m", 60_000, 120_000), [{"t": 60_000}])


class Pack(unittest.TestCase):
    def assertClose(self, actual, expected, path="pack"):
        if isinstance(expected, dict):
            self.assertEqual(set(actual), set(expected), path)
            for k in expected:
                self.assertClose(actual[k], expected[k], f"{path}.{k}")
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected), path)
            for i, (a, e) in enumerate(zip(actual, expected)):
                self.assertClose(a, e, f"{path}[{i}]")
        elif isinstance(expected, float):
            self.assertAlmostEqual(actual / expected, 1, delta=1e-6, msg=path)
        else:
            self.assertEqual(actual, expected, path)

    def test_matches_reference_on_200_bars_of_btc(self):
        result = pack(series("1h"))
        self.assertEqual(result.pop("version"), INDICATOR_PACK_VERSION)
        self.assertClose(result, REFERENCE["pack_1h"])

    def test_matches_reference_on_40_bars_where_the_seeds_still_show(self):
        result = pack(series("1h")[:40])
        self.assertEqual(result.pop("version"), INDICATOR_PACK_VERSION)
        self.assertClose(result, REFERENCE["pack_1h_first40"])

    def test_swing_must_beat_every_bar_three_each_side(self):
        bars = [{"t": i, "h": h, "l": h - 1, "c": h - 0.5} for i, h in enumerate([1, 2, 3, 5, 4, 3, 2, 9, 9, 3, 2, 1, 0])]
        # the tied 9s are no fractal; 5 is, 9 bars back; the last 3 bars cannot confirm anything yet
        self.assertEqual(pack(bars)["swing_high"], {"price": 5, "bars_ago": 9})

    def test_rsi_of_a_flat_series_is_neutral(self):
        flat = [{"t": i, "h": 1, "l": 1, "c": 1} for i in range(20)]
        rising = [{"t": i, "h": i, "l": i, "c": i} for i in range(20)]
        self.assertEqual((pack(flat)["rsi14"], pack(rising)["rsi14"]), ([50.0] * 3, [100.0] * 3))

    def test_values_the_series_is_too_short_for_are_null(self):
        short = pack(series("1h")[:20])
        self.assertIsNotNone(short["ema20"][0])
        self.assertEqual(short["ema20"][1:], [None, None])  # EMA 20 starts at bar 20
        self.assertEqual(short["ema50"], [None] * 3)
        self.assertEqual(short["macd"], {"line": [None] * 3, "signal": [None] * 3, "hist": [None] * 3})
        self.assertIsNotNone(short["rsi14"][2])  # RSI 14 needs 15 bars, bar 15 is 5 ago
        empty = pack([])
        self.assertEqual((empty["rsi14"], empty["atr14_pct"], empty["swing_high"], empty["swing_position"]),
                         ([None] * 3, [None] * 3, None, None))


class PerSymbol(unittest.TestCase):
    def test_pct_change_against_close_n_bars_ago(self):
        hours = series("1h")
        for bars, expected in REFERENCE["pct_change_1h"].items():
            self.assertAlmostEqual(pct_change(hours, int(bars)) / expected, 1, delta=1e-6)
        self.assertIsNone(pct_change(hours, 200))  # needs 201 bars

    def test_vwap_anchored_mid_series(self):
        result = vwap(series("15m"), ms("2026-10-19T00:00:00Z"))
        self.assertEqual(result.pop("version"), INDICATOR_PACK_VERSION)
        expected = REFERENCE["vwap_15m_from_2026-10-19T00:00:00Z"]
        self.assertEqual(result.pop("bars"), expected.pop("bars"))
        for k, v in expected.items():
            self.assertAlmostEqual(result[k] / v, 1, delta=1e-6, msg=k)

    def test_vwap_with_no_bar_after_the_anchor(self):
        self.assertEqual(vwap(series("15m"), ms(AT)),
                         {"vwap": None, "distance_pct": None, "bars": 0, "version": INDICATOR_PACK_VERSION})


if __name__ == "__main__":
    unittest.main()
