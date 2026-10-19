"""Sample dashboard: Contestants run through the Engine seam for a Week and a bit, for checking site/ by eye.

python3 -m tests.sample_site [out]   (default .sample, gitignored), then python3 -m http.server -d .sample
Covers TP, close, liquidation, Elimination with a Layer still open, Violations, a broken reply, Week 1 with no
plan, a fallback plan, a Contestant joining in Week 2, one still waiting for its Week, and a skipped last Tick.
"""
import math
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bench.engine import run_tick, run_week
from bench.export import export
from tests.helpers import CONFIG as FEES, bar, market, rate

START = datetime(2026, 10, 19, 0, 7, tzinfo=timezone.utc)
HOURS = 176  # Week 1 plus the first 8 Ticks of Week 2
NAMES = ["anthropic", "openai", "google", "qwen", "zai", "deepseek", "mistral", "xai"]
JOINS = {"mistral": 100, "xai": 172}  # hour each is added to the config; everyone else is there from the start
CONFIG = {**FEES, "contestants": [{"name": n, "strategist": f"{n}-big", "executor": f"{n}-small"} for n in NAMES]}


def iso(h):
    return (START + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")


def watch(symbol, bias):
    return {"symbol": symbol, "bias": bias, "entry": f"{symbol} pulls back to the 20-hour mean", "exit": "TP at +3%"}


PLANS = {
    "anthropic": (10000, [watch("BTC", "both"), watch("ETH", "long")]),
    "openai": (20000, [watch("BTC", "long")]),
    "google": (10000, [watch("ETH", "short"), watch("BTC", "both")]),
    "qwen": (5000, [watch("DOGE", "long"), watch("BTC", "both")]),
    "zai": (62500, [watch("ETH", "short"), watch("BTC", "long")]),
    "deepseek": (15000, [watch("BTC", "both"), watch("ETH", "both")]),
    "mistral": (10000, [watch("BTC", "both")]),
}


def opening(slot, symbol, side):
    return {"type": "open", "slot": slot, "symbol": symbol, "side": side}


def close(slot):
    return {"type": "close", "slot": slot}


# Executor actions per Contestant by hour since Week 1 starts; every other hour holds
SCRIPTS = {
    "anthropic": {1: [opening(0, "BTC", "long"), {"type": "set_tp", "slot": 0, "price": 103000}],
                  3: [opening(1, "ETH", "long")], 40: [close(1)], 60: [opening(1, "ETH", "long")]},
    "openai": {1: [opening(0, "BTC", "long"), opening(0, "BTC", "long")], 2: [opening(1, "ETH", "long")],
               30: [close(0)], 31: [opening(0, "BTC", "long")]},
    "google": {2: [opening(0, "ETH", "short")], 50: [close(0)], 51: [opening(1, "BTC", "short")]},
    "qwen": {169: [opening(0, "DOGE", "long")]},
    "zai": {1: [opening(s, "ETH", "short") for s in range(3)], 14: [opening(3, "BTC", "long")]},  # BTC is frozen open
    "deepseek": {1: [opening(0, "BTC", "long")], 10: [opening(1, "BTC", "short")], 80: [close(0)]},
    "mistral": {169: [opening(0, "BTC", "short")]},
}
# unparseable replies: qwen has no plan in Week 1, deepseek's Week 2 falls back to Week 1's plan, one Tick holds
BROKEN = {("qwen", 0), ("deepseek", 168), ("deepseek", 5)}


def drift(h):
    return {"BTC": 1 + 0.02 * math.sin(h / 9) + 0.0002 * h, "ETH": 1 - 0.03 * math.sin(h / 14), "DOGE": 1 + 0.05 * math.sin(h / 20)}


CANDLES = [bar("BTC", "2026-10-19T15:30:00Z", 102000, h=103500),  # anthropic's TP fills
           bar("ETH", "2026-10-19T20:30:00Z", 4100, h=4400)]  # liquidates zai's 25x shorts, not google's 4x
SKIPPED = HOURS  # Hyperliquid is down for the last Tick
FUNDING = [rate(c, iso(h)[:14] + "00:00Z", r) for h in range(HOURS + 1) for c, r in (("BTC", 0.00001), ("ETH", -0.00002))]


def priced(h):
    """Fixture market with BTC/ETH/DOGE marks and books moved by the hour's drift."""
    base, f = market(CANDLES, FUNDING), drift(h)

    def info(body):
        if h == SKIPPED and body["type"] == "l2Book":
            raise TimeoutError("l2Book timed out")
        data = base(body)
        if body["type"] == "metaAndAssetCtxs":
            meta, ctxs = data
            return [meta, [{**c, "markPx": str(float(c["markPx"]) * f[a["name"]])} for a, c in zip(meta["universe"], ctxs)]]
        if body["type"] == "l2Book":
            k = f[body["coin"]]
            return {**data, "levels": [[{**l, "px": str(float(l["px"]) * k)} for l in side] for side in data["levels"]]}
        return data

    return info


def model(h):
    def reply(model_id, _request):
        name, role = model_id.rsplit("-", 1)
        if (name, h) in BROKEN:
            return {"actions": "hold"}
        if role == "big":
            notional, watchlist = PLANS[name]
            return {"notional": notional, "watchlist": watchlist, "close_all": "Friday 20:00 UTC if the week is red",
                    "hostage_policy": "reopen the lost slot at the next pullback",
                    "rationale": f"Week {1 + h // 168}: trend on 4h is up, funding is mild, so {name} leans on {watchlist[0]['symbol']}."}
        actions = SCRIPTS[name].get(h)
        reasoning = f"Hour {h}: " + ("acting on the plan's entry rule." if actions else "no setup, holding.")
        return {"reasoning": reasoning, "actions": actions or [{"type": "hold"}]}
    return reply


def main(out):
    data, out = Path(tempfile.mkdtemp()), Path(out)
    for h in range(HOURS + 1):
        config = {**CONFIG, "contestants": [c for c in CONFIG["contestants"] if JOINS.get(c["name"], 0) <= h]}
        run = run_week if h % 168 == 0 else run_tick
        run(iso(h), priced(h), model(h), data, config)
    export(data, out / "data", CONFIG)
    shutil.copy(Path(__file__).parents[1] / "site" / "index.html", out)
    print(f"wrote {out} from {data}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".sample")
