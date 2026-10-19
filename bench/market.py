"""Market sources (a callable taking a Hyperliquid /info request body and returning its JSON response), candles,
and the market data the models are given."""
import json
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


EXECUTOR_BARS = {"4h": 30, "1h": 24, "15m": 16}  # ADR-0003: candles sent per watchlist symbol, the tail of ~200
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


def bars(series):
    """Compact candles for the prompt: [open time ms, o, h, l, c, v]."""
    return [[c["t"], *(float(c[k]) for k in "ohlcv")] for c in series]


def watch_data(market, symbol, at, asset, ctx, venues):
    """One watchlist symbol for the Executor (ADR-0003); at in ms."""
    series = {i: candles(market, symbol, i, at) for i in EXECUTOR_BARS}
    hl = venues.get("HlPerp")
    return {**basics(asset, ctx), "predicted_funding": hl and float(hl["fundingRate"]),
            "change_24h": pct_change(series["1h"], 24), "change_7d": pct_change(series["1h"], 7 * 24),
            "vwap_today": vwap(series["15m"], at - at % BAR_MS["1d"]),
            "candles": {i: {"bars": bars(s[-EXECUTOR_BARS[i]:]), "pack": pack(s)} for i, s in series.items()}}


def universe_data(market, symbol, at, anchor):
    """One top-50 symbol for the Strategist (ADR-0003); at and anchor in ms. VWAP and average funding cover the Week
    that just ended, [anchor, anchor + 1w): the new Week has no closed bar yet when run-week runs."""
    end = anchor + BAR_MS["1w"]
    daily = candles(market, symbol, "1d", at)
    quarters = [c for c in candles(market, symbol, "15m", at, bars=(at - anchor) // BAR_MS["15m"]) if c["t"] < end]
    rates = [float(f["fundingRate"]) for f in market({"type": "fundingHistory", "coin": symbol, "startTime": anchor, "endTime": end})
             if anchor <= f["time"] < end]
    return {"change_24h": pct_change(daily, 1), "change_7d": pct_change(daily, 7), "change_30d": pct_change(daily, 30),
            "vwap_last_week": vwap(quarters, anchor), "funding_last_week": sum(rates) / len(rates) if rates else None,
            "candles": {"1d": {"bars": bars(daily[-30:]), "pack": pack(daily)},
                        "1w": {"bars": bars(candles(market, symbol, "1w", at, bars=26))}}}
