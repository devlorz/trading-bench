"""Rebuilds reference.json from the recorded candles with pandas, independently of bench/indicators.py.

Run from the repo root after re-recording the fixture: PYTHONPATH=. python3 tests/fixtures/indicators/make_reference.py
Needs pandas; the tests themselves stay stdlib-only and only read the JSON.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from bench.engine import ms

F = Path(__file__).parent
AT = "2026-10-19T09:07:00Z"


def load(interval):
    df = pd.DataFrame(json.loads(next(F.glob(f"candleSnapshot_BTC_{interval}_*.json")).read_text()))
    df = df[df["T"] < ms(AT)].sort_values("t").tail(200).reset_index(drop=True)
    for k in "ohlcv":
        df[k] = df[k].astype(float)
    return df


def seeded(x, n, alpha, start):
    """EMA/Wilder whose first value is the SMA of x[start:start+n]: pandas ewm alone seeds with x[start]."""
    y = x.copy() * np.nan
    if len(x) < start + n:
        return y
    y.iloc[start + n - 1] = x.iloc[start:start + n].mean()
    y.iloc[start + n:] = x.iloc[start + n:]
    return y.ewm(alpha=alpha, adjust=False, ignore_na=True).mean().where(y.index >= start + n - 1)


def pts(s):
    return [None if pd.isna(s.iloc[i]) else float(s.iloc[i]) for i in (-1, -2, -6)]


def swing(s, better):
    for i in range(len(s) - 4, 2, -1):
        if all(better(s[i], s[j]) for j in range(i - 3, i + 4) if j != i):
            return {"price": float(s[i]), "bars_ago": len(s) - 1 - i}


def pack_of(h):
    c = h["c"]
    ema = lambda n: seeded(c, n, 2 / (n + 1), 0)
    d = c.diff()
    rsi = 100 - 100 / (1 + seeded(d.clip(lower=0), 14, 1 / 14, 1) / seeded((-d).clip(lower=0), 14, 1 / 14, 1))
    tr = pd.concat([h["h"] - h["l"], (h["h"] - c.shift()).abs(), (h["l"] - c.shift()).abs()], axis=1).max(axis=1)
    tr.iloc[0] = np.nan
    atr = seeded(tr, 14, 1 / 14, 1)
    line = ema(12) - ema(26)
    signal = seeded(line, 9, 2 / 10, 25)
    hi, lo = swing(h["h"], lambda a, b: a > b), swing(h["l"], lambda a, b: a < b)
    last = float(c.iloc[-1])
    pos = None if not (hi and lo) else "above" if last > hi["price"] else "below" if last < lo["price"] else "between"
    return {"ema20": pts(ema(20)), "ema50": pts(ema(50)), "rsi14": pts(rsi), "atr14": pts(atr),
            "atr14_pct": pts(atr / c * 100),
            "macd": {"line": pts(line), "signal": pts(signal), "hist": pts(line - signal)},
            "swing_high": hi, "swing_low": lo, "swing_position": pos}


def vwap(q, anchor):
    b = q[q["t"] >= ms(anchor)]
    v = float(((b["h"] + b["l"] + b["c"]) / 3 * b["v"]).sum() / b["v"].sum())
    return {"vwap": v, "distance_pct": (float(b["c"].iloc[-1]) / v - 1) * 100, "bars": len(b)}


h = load("1h")
c = h["c"]
last = float(c.iloc[-1])
ref = {
    "pack_1h": pack_of(h),
    "pack_1h_first40": pack_of(h.head(40).copy()),
    "pct_change_1h": {"24": (last / c.iloc[-25] - 1) * 100, "168": (last / c.iloc[-169] - 1) * 100},
    "vwap_15m_from_2026-10-19T00:00:00Z": vwap(load("15m"), "2026-10-19T00:00:00Z"),
}
(F / "reference.json").write_text(json.dumps(ref, indent=1))
