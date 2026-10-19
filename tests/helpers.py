"""Shared test doubles: fixture market, scripted models, one-Contestant config."""
from pathlib import Path

from bench.engine import ms
from bench.market import replay

FIXTURES = Path(__file__).parent / "fixtures" / "btc"
CONFIG = {"initial_capital": 10000, "taker_fee": 0.00045, "maker_fee": 0.00015, "elimination_equity": 1000}
OPEN_BTC = {"type": "open", "slot": 0, "symbol": "BTC", "side": "long"}


def scripted(*actions):
    return lambda _input: {"reasoning": "scripted", "actions": list(actions)}


HOLD = scripted({"type": "hold"})


def bar(coin, at, o, h=None, l=None, i="1m"):
    h, l = h or o, l or o
    return {"s": coin, "i": i, "t": ms(at), "o": str(o), "h": str(h), "l": str(l), "c": str(o)}


def rate(coin, at, r):
    return {"coin": coin, "fundingRate": str(r), "premium": "0", "time": ms(at) + 45}  # HL stamps land a few ms past the hour


def market(candles=(), funding=()):
    """Fixture book/meta plus in-memory candleSnapshot and fundingHistory filtered like Hyperliquid."""
    fixtures = replay(FIXTURES)

    def info(body):
        if body["type"] == "candleSnapshot":
            r = body["req"]
            return [c for c in candles if c["s"] == r["coin"] and c["i"] == r["interval"] and r["startTime"] <= c["t"] <= r["endTime"]]
        if body["type"] == "fundingHistory":
            return [f for f in funding if f["coin"] == body["coin"] and body["startTime"] <= f["time"] <= body["endTime"]]
        return fixtures(body)

    return info



def solo(name, model):
    """One-Contestant config and a model client that sends both roles to the scripted model."""
    contestant = {"name": name, "strategist": "strategist", "executor": "executor"}
    return {**CONFIG, "contestants": [contestant]}, lambda _model_id, request: model(request)
