"""Market sources: a callable taking a Hyperliquid /info request body and returning its JSON response."""
import json
import urllib.request
from pathlib import Path

INFO_URL = "https://api.hyperliquid.xyz/info"


def fixture_name(body):
    parts = []
    for v in body.values():
        parts.extend(v.values() if isinstance(v, dict) else [v])
    return "_".join(str(p) for p in parts) + ".json"


def live(body):
    req = urllib.request.Request(INFO_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


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
