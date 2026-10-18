import argparse
import json
from pathlib import Path

from bench import market
from bench.engine import run_tick

parser = argparse.ArgumentParser(prog="bench")
sub = parser.add_subparsers(dest="command", required=True)
tick = sub.add_parser("run-tick")
tick.add_argument("--contestant", required=True)
tick.add_argument("--at", required=True, help="ISO timestamp, e.g. 2026-10-19T01:07:00Z")
tick.add_argument("--fixtures", help="replay market from this folder instead of live Hyperliquid")
tick.add_argument("--record", help="save live Hyperliquid responses into this folder")
tick.add_argument("--response", help="scripted Executor response JSON (default: hold)")
tick.add_argument("--data", default="data")
tick.add_argument("--config", default="config.json")
args = parser.parse_args()

source = market.replay(args.fixtures) if args.fixtures else market.live
if args.record:
    source = market.recording(source, args.record)
# ponytail: scripted Executor only; OpenRouter client lands in ticket 07
response = json.loads(Path(args.response).read_text()) if args.response else {"reasoning": "", "actions": [{"type": "hold"}]}
config = json.loads(Path(args.config).read_text())
if not run_tick(args.contestant, args.at, source, lambda _input: response, args.data, config):
    print(f"skipped: {args.contestant} already ran a Tick at or after {args.at}")
