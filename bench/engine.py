import json
from datetime import datetime
from pathlib import Path

LAYERS = 4


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
    response = model({"at": at, "plan": plan, "state": state})
    events.append({"t": at, "type": "decision", **response})
    for action in response["actions"]:
        if action["type"] == "hold":
            continue
        # ponytail: close/set_tp/cancel_tp land in ticket 03; until then they are Violations
        rule = broken_open_rule(state, plan, max_leverage, action) if action["type"] == "open" else "unsupported_action"
        if rule:
            events.append({"t": at, "type": "violation", "rule": rule, "action": action})
        else:
            events.append(open_layer(state, action, market, config, at))

    state["last_tick"] = at
    state_file.write_text(json.dumps(state, indent=2, sort_keys=True))
    with open(folder / "events.jsonl", "a") as log:
        for e in events:
            log.write(json.dumps(e, sort_keys=True) + "\n")
    return True


def broken_open_rule(state, plan, max_leverage, action):
    rp, slot, symbol = state["rp"], action["slot"], action["symbol"]
    if not 0 <= slot < LAYERS:
        return "slot_out_of_range"
    if state["layers"][slot] is not None:
        return "layer_occupied"
    if state["free_equity"] < rp["collateral"]:
        return "insufficient_free_equity"
    if symbol not in {w["symbol"] for w in plan["watchlist"]}:
        return "symbol_not_in_watchlist"
    if rp["notional"] / rp["collateral"] > max_leverage[symbol]:
        return "exceeds_max_leverage"
    return None


def open_layer(state, action, market, config, at):
    rp = state["rp"]
    book = market({"type": "l2Book", "coin": action["symbol"]})["levels"]
    entry = float(book[1][0]["px"] if action["side"] == "long" else book[0][0]["px"])
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
    }
    return {"t": at, "type": "fill", "slot": action["slot"], "symbol": action["symbol"],
            "side": action["side"], "price": entry, "notional": rp["notional"], "fee": fee}
