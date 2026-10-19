"""Dashboard files rebuilt from each Contestant's event log and equity snapshots, apart from Engine state."""
import json
from pathlib import Path

from bench.engine import LAYERS, read_jsonl


def export(data_dir, out_dir, config):
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, curves = [], {}
    for contestant in config["contestants"]:
        folder = data_dir / contestant["name"]
        events, snapshots = read_jsonl(folder / "events.jsonl"), read_jsonl(folder / "equity.jsonl")
        if not events:
            continue  # added to config, no Week run yet
        positions = closed_positions(events)
        who = {**contestant, "eliminated": next((e["week"] for e in events if e["type"] == "elimination"), None)}
        rows.append({**who, **metrics(events, snapshots, positions, config["initial_capital"])})
        curves[contestant["name"]] = [[s["t"], s["equity"]] for s in snapshots]
        plans = [{**a["plan"], "notional_used": a["notional_used"]}
                 for a in (json.loads(f.read_text()) for f in sorted((folder / "plans").glob("*.json")))]
        write(out_dir / f"{contestant['name']}.json", {
            **who,
            "layers": snapshots[-1]["layers"] if snapshots else [None] * LAYERS,
            "positions": positions,
            "plans": plans,
            "decisions": [strip(e) for e in events if e["type"] == "decision"],
            "violations": [strip(e) for e in events if e["type"] == "violation"],
        })
    ticks = [r for r in read_jsonl(data_dir / "runs.jsonl") if r["type"] == "tick"]
    write(out_dir / "index.json", {"last_tick": ticks[-1] if ticks else None,
                                   "leaderboard": sorted(rows, key=lambda r: -r["net_return"]), "equity": curves})


def closed_positions(events):
    """Pair each fill with the close, TP or liquidation of its slot; pnl is net of fees and funding."""
    held, closed = {}, []
    for e in events:
        if e["type"] == "fill":
            held[e["slot"]] = {"symbol": e["symbol"], "side": e["side"], "opened_at": e["t"], "entry": e["price"],
                               "fees": e["fee"], "funding": 0, "collateral": e["collateral"]}
        elif e["type"] == "funding":
            held[e["slot"]]["funding"] += e["amount"]
        elif e["type"] in ("close", "tp", "liquidation"):
            p = held.pop(e["slot"])
            collateral = p.pop("collateral")
            # a liquidation returns nothing, so its pnl is the whole collateral lost
            closed.append({**p, "closed_at": e["t"], "exit": e["price"], "fees": p["fees"] + e.get("fee", 0),
                           "pnl": e.get("returned", 0) - collateral, "reason": e["type"]})
    return closed


def metrics(events, snapshots, positions, initial):
    equity = snapshots[-1]["equity"] if snapshots else initial
    peak, drawdown = initial, 0
    for s in snapshots:
        peak = max(peak, s["equity"])
        drawdown = max(drawdown, (peak - s["equity"]) / peak)
    pnls = [p["pnl"] for p in positions]
    count = lambda kind: sum(e["type"] == kind for e in events)
    return {
        "equity": equity,
        "net_return": (equity - initial) / initial,
        "max_drawdown": drawdown,
        "closed_positions": len(pnls),
        "win_rate": sum(p > 0 for p in pnls) / len(pnls) if pnls else None,
        "avg_pnl": sum(pnls) / len(pnls) if pnls else None,
        "liquidations": count("liquidation"),
        "violations": count("violation"),
        "fees": sum(e["fee"] for e in events if e["type"] in ("fill", "close", "tp")),
        "funding": sum(e["amount"] for e in events if e["type"] == "funding"),
        "reallocation_weeks": sum(e["type"] == "plan" and e["reallocated"] for e in events),
    }


def strip(event):
    return {k: v for k, v in event.items() if k != "type"}


def write(path, content):
    path.write_text(json.dumps(content, indent=2, sort_keys=True))
