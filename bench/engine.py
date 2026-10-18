import json
from datetime import datetime, timezone
from pathlib import Path

LAYERS = 4
HOUR = 3_600_000
BAR_MS = {"1m": 60_000, "15m": 900_000, "1h": HOUR}
MAX_BARS = 5000  # Hyperliquid candleSnapshot serves only the most recent 5,000 bars per interval
SIGN = {"long": 1, "short": -1}


def run_tick(contestant, at, market, model, data_dir, config):
    folder = Path(data_dir) / contestant
    state_file = folder / "state.json"
    plan = json.loads((folder / "plan.json").read_text())
    events = []

    if state_file.exists():
        state = json.loads(state_file.read_text())
        if datetime.fromisoformat(state["last_tick"]) >= datetime.fromisoformat(at):
            return False  # already ran this Tick
    else:
        equity = config["initial_capital"]
        state = {
            "free_equity": equity,
            "rp": {"collateral": equity / LAYERS, "notional": plan["notional"]},
            "layers": [None] * LAYERS,
        }
        events.append({"t": at, "type": "reallocation", "rp": state["rp"]})

    max_leverage = {a["name"]: a["maxLeverage"] for a in market({"type": "metaAndAssetCtxs"})[0]["universe"]}
    settled = settle(state, state["last_tick"], at, market, config, max_leverage) if "last_tick" in state else []
    events.extend(settled)
    response = model({"at": at, "plan": plan, "state": state, "settled": settled})
    events.append({"t": at, "type": "decision", **response})
    for action in response["actions"]:
        if action["type"] == "hold":
            continue
        rule = broken_rule(state, plan, max_leverage, action)
        if rule:
            events.append({"t": at, "type": "violation", "rule": rule, "action": action})
        elif action["type"] == "open":
            events.append(open_layer(state, action, market, config, at))
        elif action["type"] == "close":
            layer = state["layers"][action["slot"]]
            px = best_price(market, layer["symbol"], buy=layer["side"] == "short")
            events.append(close_layer(state, action["slot"], px, config["taker_fee"], at, "close"))
        elif action["type"] == "set_tp":
            state["layers"][action["slot"]]["tp"] = action["price"]  # replaces any earlier TP
        elif action["type"] == "cancel_tp":
            state["layers"][action["slot"]]["tp"] = None

    state["last_tick"] = at
    state_file.write_text(json.dumps(state, indent=2, sort_keys=True))
    with open(folder / "events.jsonl", "a") as log:
        for e in events:
            log.write(json.dumps(e, sort_keys=True) + "\n")
    return True


def broken_rule(state, plan, max_leverage, action):
    if action["type"] not in ("open", "close", "set_tp", "cancel_tp"):
        return "unsupported_action"
    rp, slot = state["rp"], action["slot"]
    if not 0 <= slot < LAYERS:
        return "slot_out_of_range"
    layer = state["layers"][slot]
    if action["type"] != "open":
        if layer is None:
            return "layer_empty"
        if action["type"] == "set_tp" and SIGN[layer["side"]] * (action["price"] - layer["entry"]) <= 0:
            return "tp_wrong_side"
        return None
    symbol = action["symbol"]
    if layer is not None:
        return "layer_occupied"
    if state["free_equity"] < rp["collateral"]:
        return "insufficient_free_equity"
    if symbol not in {w["symbol"] for w in plan["watchlist"]}:
        return "symbol_not_in_watchlist"
    if rp["notional"] / rp["collateral"] > max_leverage[symbol]:
        return "exceeds_max_leverage"
    return None


def best_price(market, symbol, buy):
    """Market fill: a buy lifts the best ask, a sell hits the best bid."""
    book = market({"type": "l2Book", "coin": symbol})["levels"]
    return float(book[1][0]["px"] if buy else book[0][0]["px"])


def open_layer(state, action, market, config, at):
    rp = state["rp"]
    entry = best_price(market, action["symbol"], buy=action["side"] == "long")
    fee = rp["notional"] * config["taker_fee"]
    state["free_equity"] -= rp["collateral"]
    state["layers"][action["slot"]] = {
        "symbol": action["symbol"],
        "side": action["side"],
        "notional": rp["notional"],
        "size": rp["notional"] / entry,
        "entry": entry,
        "collateral": rp["collateral"] - fee,
        "opened_at": at,
        "tp": None,
    }
    return {"t": at, "type": "fill", "slot": action["slot"], "symbol": action["symbol"],
            "side": action["side"], "price": entry, "notional": rp["notional"], "fee": fee}


def ms(at):
    return int(datetime.fromisoformat(at).timestamp() * 1000)


def iso(t):
    return datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def settle(state, since, at, market, config, max_leverage):
    """Replay everything between the last Tick and this one, bar by bar, against each open Layer."""
    start, end = ms(since), ms(at)
    # ponytail: one interval for the whole gap, sized from its length. A coarse bar straddling the last Tick counts
    # in full, so its high/low from before the Layer opened can liquidate or fill TP falsely. Upgrade: settle the
    # last ~3.5 days on 1m and only the older head on 15m/1h, clipping the first coarse bar with 1m.
    interval = next(i for i, step in BAR_MS.items() if (end - start) / step <= MAX_BARS)
    first_bar = start - start % BAR_MS[interval]
    events = []
    for slot, layer in enumerate(state["layers"]):
        if layer is None:
            continue
        coin = layer["symbol"]
        req = {"coin": coin, "interval": interval, "startTime": first_bar, "endTime": end}
        candles = [c for c in market({"type": "candleSnapshot", "req": req}) if first_bar <= c["t"] < end]
        rates = market({"type": "fundingHistory", "coin": coin, "startTime": start, "endTime": end})
        hours = sorted((f["time"] // HOUR * HOUR, float(f["fundingRate"])) for f in rates)
        hours = [(h, r) for h, r in hours if start <= h < end]
        sign = SIGN[layer["side"]]
        maintenance = layer["notional"] / (2 * max_leverage[coin])  # ADR-0001
        bars = sorted(candles, key=lambda c: c["t"])
        last = bars[-1]["c"] if bars else layer["entry"]
        # Flat bar at the Tick: funding hours no bar reached (feed lag) still settle, at the last known price
        bars.append({"t": end, "o": last, "h": last, "l": last})
        for c in bars:
            while hours and hours[0][0] <= c["t"]:
                h, r = hours.pop(0)
                amount = -sign * layer["size"] * float(c["o"]) * r
                layer["collateral"] += amount
                events.append({"t": iso(h), "type": "funding", "slot": slot, "symbol": coin, "rate": r, "amount": amount})
            worst = float(c["l"] if sign > 0 else c["h"])  # bar extreme as worst-case mark (ADR-0001)
            if layer["collateral"] + sign * layer["size"] * (worst - layer["entry"]) <= maintenance:
                state["layers"][slot] = None
                events.append({"t": iso(c["t"]), "type": "liquidation", "slot": slot, "symbol": coin,
                               "side": layer["side"], "price": worst, "collateral_lost": layer["collateral"]})
                break
            tp = layer["tp"]
            if tp is not None and (float(c["h"]) >= tp if sign > 0 else float(c["l"]) <= tp):
                events.append(close_layer(state, slot, tp, config["maker_fee"], iso(c["t"]), "tp"))
                break
    return sorted(({**e, "resolution": interval} for e in events), key=lambda e: e["t"])


def close_layer(state, slot, price, fee_rate, t, kind):
    """Release collateral ± PnL − fee to free equity; anything above the RP collateral is Hostage."""
    layer = state["layers"][slot]
    pnl = SIGN[layer["side"]] * layer["size"] * (price - layer["entry"])
    fee = layer["size"] * price * fee_rate
    returned = layer["collateral"] + pnl - fee
    state["free_equity"] += returned
    state["layers"][slot] = None
    return {"t": t, "type": kind, "slot": slot, "symbol": layer["symbol"], "side": layer["side"], "price": price,
            "pnl": pnl, "fee": fee, "returned": returned, "hostage": max(0, returned - state["rp"]["collateral"])}
