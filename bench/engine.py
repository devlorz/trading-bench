import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

LAYERS = 4
HOUR = 3_600_000
BAR_MS = {"1m": 60_000, "15m": 900_000, "1h": HOUR}
MAX_BARS = 5000  # Hyperliquid candleSnapshot serves only the most recent 5,000 bars per interval
SIGN = {"long": 1, "short": -1}
ACTIONS = ("open", "close", "set_tp", "cancel_tp")  # plus hold, which needs no checks
BIASES = ("long", "short", "both", "avoid")
MAX_WATCHLIST = 5
MIN_NOTIONAL = 10  # USD, Hyperliquid's minimum order value
TOP_PERPS = 50  # Strategist universe, by 24h notional volume


def run_tick(contestant, at, market, model, data_dir, config):
    at = iso(ms(at))
    folder = Path(data_dir) / contestant
    state_file = folder / "state.json"
    if not state_file.exists():
        raise FileNotFoundError(f"{state_file} does not exist: run run-week for {contestant} first")
    state = json.loads(state_file.read_text())
    if "last_tick" in state and datetime.fromisoformat(state["last_tick"]) >= datetime.fromisoformat(at):
        return False  # already ran this Tick
    plan_file = folder / "plan.json"
    plan = json.loads(plan_file.read_text()) if plan_file.exists() else None
    events = []

    max_leverage = {a["name"]: a["maxLeverage"] for a in market({"type": "metaAndAssetCtxs"})[0]["universe"]}
    settled = settle(state, state["settled"], at, market, config, max_leverage)
    violations = []
    if "last_tick" in state:
        violations = [e for e in read_events(folder) if e["type"] == "violation" and e["t"] == state["last_tick"]]
    events.extend(settled)
    request = {"at": at, "plan": plan, "state": state, "settled": settled, "violations": violations}
    # spec: no passing plan in Week 1 forces hold without asking the Executor
    response = ask(model, request, schema_error, 1, at, events) if plan else None
    actions = []  # spec: a response still broken after the retry holds the whole Tick and is not a Violation
    if response is not None:
        events.append({"t": at, "type": "decision", "plan": plan["week"],
                       "reasoning": response["reasoning"], "actions": response["actions"]})
        actions = response["actions"]
    for action in actions:
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

    state["last_tick"] = state["settled"] = at
    save(folder, state, events)
    return True


def run_week(contestant, at, market, model, data_dir, config):
    at = iso(ms(at))
    day = datetime.fromisoformat(at).replace(hour=0, minute=0, second=0)
    week_start = (day - timedelta(days=day.weekday())).strftime("%Y-%m-%dT%H:%M:%SZ")  # Monday 00:00 UTC
    folder = Path(data_dir) / contestant
    (folder / "plans").mkdir(parents=True, exist_ok=True)
    state_file = folder / "state.json"
    meta, ctxs = market({"type": "metaAndAssetCtxs"})
    settled = []
    if state_file.exists():
        state = json.loads(state_file.read_text())
        if state["last_week"] >= week_start:
            return False  # this Week already has its plan
        settled = settle(state, state["settled"], at, market, config, {a["name"]: a["maxLeverage"] for a in meta["universe"]})
    else:
        state = {"free_equity": config["initial_capital"], "rp": None, "layers": [None] * LAYERS}
    events = list(settled)

    reallocate = all(l is None for l in state["layers"])  # equity is all free equity then
    collateral = state["free_equity"] / LAYERS if reallocate else state["rp"]["collateral"]
    in_force = None if reallocate else state["rp"]["notional"]  # without Reallocation the new notional is not used
    plan_file = folder / "plan.json"
    previous = json.loads(plan_file.read_text()) if plan_file.exists() else None
    # ponytail: rescans the whole append-only log each Week; keep a cursor if it grows
    last_week = [e for e in read_events(folder) if e["t"] >= state["last_week"]] if "last_week" in state else []
    listed_leverage = {a["name"]: a["maxLeverage"] for a in meta["universe"] if not a.get("isDelisted")}
    perps = [{"symbol": a["name"], "day_volume": float(c["dayNtlVlm"]), "mark": float(c["markPx"]),
              "funding": float(c["funding"]), "open_interest": float(c["openInterest"]), "max_leverage": a["maxLeverage"]}
             for a, c in zip(meta["universe"], ctxs) if a["name"] in listed_leverage]
    # ponytail: candles, Indicator Pack, %change, VWAP and 7d average funding are added when ticket 07 builds the prompt
    request = {
        "at": at,
        "state": state,
        "reallocation": {"happens": reallocate, "collateral": collateral},
        "settled": settled,
        "previous_plan": previous,
        "last_week": last_week,
        "universe": sorted(perps, key=lambda p: -p["day_volume"])[:TOP_PERPS],
        "symbols": sorted(listed_leverage),
    }
    check = lambda plan: plan_error(plan, listed_leverage, collateral, in_force)
    plan = ask(model, request, check, 2, at, events)
    if plan is None:  # last week's plan and RP stay in force
        if previous is None:
            events.append({"t": at, "type": "violation", "rule": "no_weekly_plan"})
        # plan.json always carries the RP notional, so a fallback plan's notional is the one in use
        events.append({"t": at, "type": "plan", "plan": previous and previous["week"], "fallback": True,
                       "reallocated": False, "notional_used": previous is not None})
    else:
        plan = {**plan, "week": week_start}  # one id for plan.json, the archive name and every decision event
        events.append({"t": at, "type": "plan", "plan": week_start, "fallback": False,
                       "reallocated": reallocate, "notional_used": reallocate})
        if reallocate:
            state["rp"] = {"collateral": collateral, "notional": plan["notional"]}
            events.append({"t": at, "type": "reallocation", "rp": state["rp"]})
        (folder / "plans" / f"{week_start[:10]}.json").write_text(
            json.dumps({"plan": plan, "notional_used": reallocate}, indent=2, sort_keys=True))
        plan_file.write_text(json.dumps({**plan, "notional": state["rp"]["notional"]}, indent=2, sort_keys=True))

    state["last_week"], state["settled"] = week_start, at
    save(folder, state, events)
    return True


def read_events(folder):
    with open(folder / "events.jsonl") as log:
        return [json.loads(line) for line in log]


def save(folder, state, events):
    (folder / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True))
    with open(folder / "events.jsonl", "a") as log:
        for e in events:
            log.write(json.dumps(e, sort_keys=True) + "\n")


def ask(model, request, check, retries, at, events):
    """Call the model, re-asking with the previous error attached; every failed attempt is an error event."""
    for _ in range(retries + 1):
        try:
            response = model(request)
            error = check(response)
        except Exception as e:  # any failed model call (network, unparseable reply) counts as a broken response
            response, error = None, f"{type(e).__name__}: {e}"
        if not error:
            return response
        events.append({"t": at, "type": "error", "error": error, "response": response})
        request = {**request, "retry_error": error}
    return None


def schema_error(response):
    """Response shape only; each Action's own shape is a per-item Violation in broken_rule."""
    if not (isinstance(response, dict) and isinstance(response.get("reasoning"), str)
            and isinstance(response.get("actions"), list)):
        return "response must be an object with reasoning (string) and actions (list)"
    return None


def plan_error(plan, max_leverage, collateral, in_force=None):
    """Weekly Plan validation; the message goes back to the Strategist as retry_error.

    Leverage uses the notional the RP will actually trade: in_force when there is no Reallocation."""
    texts = ("close_all", "hostage_policy", "rationale")
    if not (isinstance(plan, dict) and type(plan.get("notional")) in (int, float)
            and isinstance(plan.get("watchlist"), list) and all(isinstance(plan.get(k), str) for k in texts)):
        return "plan must be an object with notional (number), watchlist (list), close_all, hostage_policy and rationale (strings)"
    watchlist = plan["watchlist"]
    if len(watchlist) > MAX_WATCHLIST:
        return f"watchlist has {len(watchlist)} symbols, at most {MAX_WATCHLIST}"
    if not plan["notional"] >= MIN_NOTIONAL:  # also rejects NaN
        return f"notional {plan['notional']} is below Hyperliquid's minimum of {MIN_NOTIONAL} USD"
    notional = in_force or plan["notional"]
    seen = set()
    for item in watchlist:
        if not (isinstance(item, dict) and isinstance(item.get("symbol"), str) and item.get("bias") in BIASES
                and isinstance(item.get("entry"), str) and isinstance(item.get("exit"), str)):
            return "each watchlist item needs symbol, bias (long/short/both/avoid), entry and exit (strings)"
        symbol = item["symbol"]
        if symbol in seen:
            return f"{symbol} appears more than once in the watchlist"
        seen.add(symbol)
        if symbol not in max_leverage:
            return f"{symbol} is not on Hyperliquid"
        if notional / collateral > max_leverage[symbol]:
            return (f"notional {notional} / collateral {collateral:g} = {notional / collateral:.2f}x "
                    f"exceeds {symbol} max leverage {max_leverage[symbol]}x")
    return None


def broken_rule(state, plan, max_leverage, action):
    if not (isinstance(action, dict) and isinstance(action.get("type"), str)):
        return "invalid_action"
    if action["type"] == "hold":
        return None
    if action["type"] not in ACTIONS:
        return "unsupported_action"
    # type() rather than isinstance(): JSON true/false would pass as int
    if type(action.get("slot")) is not int:
        return "invalid_action"
    if action["type"] == "open" and not (isinstance(action.get("symbol"), str) and action.get("side") in SIGN):
        return "invalid_action"
    if action["type"] == "set_tp" and type(action.get("price")) not in (int, float):
        return "invalid_action"
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
    bias_of = {w["symbol"]: w["bias"] for w in plan["watchlist"]}
    if symbol not in bias_of:
        return "symbol_not_in_watchlist"
    if bias_of[symbol] not in ("both", action["side"]):
        return "bias_mismatch"
    if any(l and l["symbol"] == symbol and l["side"] != action["side"] for l in state["layers"]):
        return "opposite_side_open"
    # ponytail: plan validation checked the symbol is listed; one removed from Hyperliquid mid-Week raises KeyError
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
