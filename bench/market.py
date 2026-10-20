"""Market sources (a callable taking a Hyperliquid /info request body and returning its JSON response), candles,
and the market data the models are given."""
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

from bench.indicators import pack, pct_change, vwap

INFO_URL = "https://api.hyperliquid.xyz/info"


def fixture_name(body):
    parts = []
    for v in body.values():
        parts.extend(v.values() if isinstance(v, dict) else [v])
    return "_".join(str(p) for p in parts) + ".json"


def live(body, waits=(10, 20, 30, 60), urlopen=urllib.request.urlopen, sleep=time.sleep):
    """A Week's universe is ~200 requests, past Hyperliquid's 1,200 weight a minute, so a 429 waits (Retry-After when
    given) and tries again; any other failure, or a 429 after the last wait, raises and the round is skipped."""
    # ponytail: blocking sleep, up to 2 minutes per request; pace requests up front if runs get close to the job timeout
    req = urllib.request.Request(INFO_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for wait in (*waits, None):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                raise
            told = e.headers.get("Retry-After", "")
            sleep(int(told) if told.isdigit() else wait)


def recording(source, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    def info(body):
        data = source(body)
        (folder / fixture_name(body)).write_text(json.dumps(data))
        return data

    return info


def replay(folder):
    return lambda body: json.loads((Path(folder) / fixture_name(body)).read_text())


PROMPT_ENCODING_VERSION = 1  # compact() is frozen with the Indicator Pack: changing it means a new benchmark
EXECUTOR_BARS = {"4h": 30, "1h": 24, "15m": 16}  # ADR-0003: candles sent per watchlist symbol, the tail of ~200
STRATEGIST_BARS = {"1d": 30, "1w": 12}  # per universe symbol; weekly is raw, with no Indicator Pack
PRICE_SIG_FIGS = 5  # Hyperliquid perp prices carry at most this many significant figures; every float sent too
PERP_MAX_DECIMALS = 6  # a perp price has at most this many decimals minus the asset's szDecimals
BAR_MS = {"1m": 60_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000, "1w": 604_800_000}


def bars_between(market, coin, interval, start, end):
    """Candles opening in [start, end) ms, oldest first; the last one may still be forming."""
    req = {"coin": coin, "interval": interval, "startTime": start, "endTime": end}
    bars = [c for c in market({"type": "candleSnapshot", "req": req}) if start <= c["t"] < end]
    return sorted(bars, key=lambda c: c["t"])


def candles(market, coin, interval, at, bars=200):
    """The last `bars` closed candles before `at` (ms) in one candleSnapshot call: the bar still forming is
    dropped, since its values depend on the second it was fetched and would not replay."""
    # ponytail: sized as if no bar is missing, so exchange downtime in the window silently returns fewer than
    # `bars`; widen the window or loop if a short series ever shows up
    start = at - (bars + 1) * BAR_MS[interval]
    return [c for c in bars_between(market, coin, interval, start, at) if c["T"] < at][-bars:]


# What the models are given of the market (ADR-0003)

def basics(asset, ctx):
    return {"mark": float(ctx["markPx"]), "funding": float(ctx["funding"]),
            "open_interest": float(ctx["openInterest"]), "max_leverage": asset["maxLeverage"]}


def on_tick(px, sz_decimals):
    """A price as Hyperliquid quotes it: at most PRICE_SIG_FIGS significant figures and PERP_MAX_DECIMALS - szDecimals
    decimals, whole numbers always allowed; an integer when it has no decimals, which also saves the ".0"."""
    whole_digits = math.floor(math.log10(px)) + 1 if px > 0 else 1
    places = max(0, min(PERP_MAX_DECIMALS - sz_decimals, PRICE_SIG_FIGS - whole_digits))
    px = round(px, places)
    return int(px) if px == int(px) else px


def compact(series, interval, count, sz_decimals):
    """The last `count` intervals of a series as ADR-0003 sends them: the first bar's open time and the interval once,
    then [o, h, l, c, v] per bar oldest first, prices on tick and volume whole. A bar the exchange never printed is
    null, so bar i always opens at start + i * interval; a symbol listed more recently gets fewer bars. The Indicator Pack is computed before this rounding."""
    if not series:
        return {"start": None, "interval": interval, "bars": []}
    step = BAR_MS[interval]
    start = max(series[0]["t"], series[-1]["t"] - (count - 1) * step)  # no padding before a young listing's first bar
    out = [None] * ((series[-1]["t"] - start) // step + 1)
    for c in series:
        if c["t"] >= start:
            # Hyperliquid opens every bar on its interval grid, so (t - start) is a whole number of steps
            out[(c["t"] - start) // step] = [*(on_tick(float(c[k]), sz_decimals) for k in "ohlc"), round(float(c["v"]))]
    return {"start": start, "interval": interval, "bars": out}


def rounded(x):
    """Every float sent cut to PRICE_SIG_FIGS significant figures, after it is computed at full precision (ADR-0003).
    A no-op on compact bars, whose prices are already on tick and volumes whole."""
    if isinstance(x, float):
        return float(f"{x:.{PRICE_SIG_FIGS}g}")
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v) for v in x]
    return x


def watch_data(market, symbol, at, asset, ctx, venues):
    """One watchlist symbol for the Executor (ADR-0003); at in ms."""
    series = {i: candles(market, symbol, i, at) for i in EXECUTOR_BARS}
    hl = venues.get("HlPerp")
    return {**basics(asset, ctx), "predicted_funding": hl and float(hl["fundingRate"]),
            "change_24h": pct_change(series["1h"], 24), "change_7d": pct_change(series["1h"], 7 * 24),
            "vwap_today": vwap(series["15m"], at - at % BAR_MS["1d"]),
            "candles": {i: {**compact(s, i, EXECUTOR_BARS[i], asset["szDecimals"]), "pack": pack(s)} for i, s in series.items()}}


def universe_data(market, symbol, sz_decimals, at, anchor):
    """One top-50 symbol for the Strategist (ADR-0003); at and anchor in ms. VWAP and average funding cover the Week
    that just ended, [anchor, anchor + 1w): the new Week has no closed bar yet when run-week runs."""
    end = anchor + BAR_MS["1w"]
    daily = candles(market, symbol, "1d", at)
    quarters = [c for c in candles(market, symbol, "15m", at, bars=(at - anchor) // BAR_MS["15m"]) if c["t"] < end]
    rates = [float(f["fundingRate"]) for f in market({"type": "fundingHistory", "coin": symbol, "startTime": anchor, "endTime": end})
             if anchor <= f["time"] < end]
    return {"change_24h": pct_change(daily, 1), "change_7d": pct_change(daily, 7), "change_30d": pct_change(daily, 30),
            "vwap_last_week": vwap(quarters, anchor), "funding_last_week": sum(rates) / len(rates) if rates else None,
            "candles": {"1d": {**compact(daily, "1d", STRATEGIST_BARS["1d"], sz_decimals), "pack": pack(daily)},
                        "1w": compact(candles(market, symbol, "1w", at, bars=STRATEGIST_BARS["1w"]), "1w",
                                      STRATEGIST_BARS["1w"], sz_decimals)}}
