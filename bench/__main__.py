import argparse
import json
from pathlib import Path

from bench import market
from bench.engine import run_tick, run_week

parser = argparse.ArgumentParser(prog="bench")
sub = parser.add_subparsers(dest="command", required=True)
tick, week = sub.add_parser("run-tick"), sub.add_parser("run-week")
for cmd in (tick, week):
    cmd.add_argument("--contestant", required=True)
    cmd.add_argument("--at", required=True, help="ISO timestamp, e.g. 2026-10-19T01:07:00Z")
    cmd.add_argument("--fixtures", help="replay market from this folder instead of live Hyperliquid")
    cmd.add_argument("--record", help="save live Hyperliquid responses into this folder")
    cmd.add_argument("--data", default="data")
    cmd.add_argument("--config", default="config.json")
tick.add_argument("--response", help="scripted Executor response JSON (default: hold)")
week.add_argument("--response", required=True, help="scripted Strategist Weekly Plan JSON")
args = parser.parse_args()

source = market.replay(args.fixtures) if args.fixtures else market.live
if args.record:
    source = market.recording(source, args.record)
# ponytail: scripted models only; OpenRouter client lands in ticket 07
hold = {"reasoning": "", "actions": [{"type": "hold"}]}
response = json.loads(Path(args.response).read_text()) if args.response else hold
config = json.loads(Path(args.config).read_text())
run = run_tick if args.command == "run-tick" else run_week
if not run(args.contestant, args.at, source, lambda _input: response, args.data, config):
    print(f"skipped: {args.contestant} already ran {args.command} at or after {args.at}")
