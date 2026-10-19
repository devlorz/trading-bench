"""Indicator Pack (ADR-0003): pure functions over closed Hyperliquid candles, oldest first. Stdlib only.

Frozen before Week 1: changing any definition or parameter here means a new benchmark and a new version.
"""
import operator

INDICATOR_PACK_VERSION = 1
POINTS = (1, 2, 6)  # now, 1 bar ago, 5 bars ago, as negative indexes
EMA_FAST, EMA_SLOW = 20, 50
RSI_LEN = ATR_LEN = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
FRACTAL = 3  # bars each side of a swing


def seeded(xs, n, alpha, start=0):
    """EMA/Wilder smoothing whose first value is the SMA of xs[start:start+n]; None before that.
    xs before `start` is never read, so it may hold None."""
    out = [None] * len(xs)
    if len(xs) < start + n:
        return out
    out[start + n - 1] = prev = sum(xs[start:start + n]) / n
    for i in range(start + n, len(xs)):
        out[i] = prev = prev + alpha * (xs[i] - prev)
    return out


def ema(xs, n, start=0):
    return seeded(xs, n, 2 / (n + 1), start)


def wilder(xs, n, start=0):
    return seeded(xs, n, 1 / n, start)


def points(xs):
    return [xs[-i] if len(xs) >= i else None for i in POINTS]


def combine(f, *series):
    return [None if None in vals else f(*vals) for vals in zip(*series)]


def col(series, key):
    return [float(c[key]) for c in series]


def rsi(gain, loss):
    if loss == 0:
        return 100.0 if gain else 50.0  # a flat series is neutral, not overbought
    return 100 - 100 / (1 + gain / loss)


def swing(values, better):
    """Last confirmed fractal: strictly better than the FRACTAL bars on each side."""
    for i in range(len(values) - 1 - FRACTAL, FRACTAL - 1, -1):
        if all(better(values[i], values[j]) for j in range(i - FRACTAL, i + FRACTAL + 1) if j != i):
            return {"price": values[i], "bars_ago": len(values) - 1 - i}
    return None


def pack(series):
    """Series must hold closed bars only (market.candles); a bar still forming would make the pack unreplayable."""
    close, high, low = col(series, "c"), col(series, "h"), col(series, "l")
    # index 0 has no previous bar, so gains and true ranges start at 1 and Wilder seeds over [1, 14]
    deltas = [0.0] + [b - a for a, b in zip(close, close[1:])]
    gain = wilder([max(d, 0) for d in deltas], RSI_LEN, start=1)
    loss = wilder([max(-d, 0) for d in deltas], RSI_LEN, start=1)
    tr = [0.0] + [max(h - l, abs(h - pc), abs(l - pc)) for h, l, pc in zip(high[1:], low[1:], close)]
    atr = wilder(tr, ATR_LEN, start=1)
    line = combine(operator.sub, ema(close, MACD_FAST), ema(close, MACD_SLOW))
    signal = ema(line, MACD_SIGNAL, start=MACD_SLOW - 1)  # the line's first value is at the slow EMA's seed
    hi, lo = swing(high, operator.gt), swing(low, operator.lt)
    position = None
    if hi and lo:
        position = "above" if close[-1] > hi["price"] else "below" if close[-1] < lo["price"] else "between"
    return {
        "version": INDICATOR_PACK_VERSION,
        "ema20": points(ema(close, EMA_FAST)),
        "ema50": points(ema(close, EMA_SLOW)),
        "rsi14": points(combine(rsi, gain, loss)),
        "atr14": points(atr),
        "atr14_pct": points(combine(lambda a, c: a / c * 100, atr, close)),
        "macd": {"line": points(line), "signal": points(signal), "hist": points(combine(operator.sub, line, signal))},
        "swing_high": hi,
        "swing_low": lo,
        "swing_position": position,
    }


def pct_change(series, bars):
    """% change of the last close against the close `bars` bars earlier; 24h is 24 on 1h, 7d is 7 on 1d."""
    if len(series) <= bars:
        return None
    close = col(series, "c")
    return (close[-1] / close[-1 - bars] - 1) * 100


def vwap(series, anchor):
    """VWAP of typical price (H+L+C)/3 over bars opening at or after `anchor` (ms), with the last close's % distance."""
    bars = [c for c in series if c["t"] >= anchor]
    volume = sum(col(bars, "v"))
    value = distance = None
    if volume:
        typical = combine(lambda h, l, c: (h + l + c) / 3, col(bars, "h"), col(bars, "l"), col(bars, "c"))
        value = sum(t * v for t, v in zip(typical, col(bars, "v"))) / volume
        distance = (float(bars[-1]["c"]) / value - 1) * 100
    return {"vwap": value, "distance_pct": distance, "bars": len(bars), "version": INDICATOR_PACK_VERSION}
