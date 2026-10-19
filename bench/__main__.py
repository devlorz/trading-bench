import argparse
import json
import os
import shutil
from pathlib import Path

from bench import market, openrouter
from bench.engine import run_tick, run_week
from bench.export import export

parser = argparse.ArgumentParser(prog="bench")
sub = parser.add_subparsers(dest="command", required=True)
tick, week, reset = sub.add_parser("run-tick"), sub.add_parser("run-week"), sub.add_parser("reset")
for cmd in (tick, week):
    cmd.add_argument("--at", required=True, help="ISO timestamp, e.g. 2026-10-19T01:07:00Z")
    cmd.add_argument("--fixtures", help="replay market from this folder instead of live Hyperliquid")
    cmd.add_argument("--record", help="save live Hyperliquid responses into this folder")
    cmd.add_argument("--config", default="config.json")
    cmd.add_argument("--response", help="scripted reply JSON for every Contestant instead of OpenRouter")
    cmd.add_argument("--artifacts", default="artifacts/prompts", help="raw prompts for the workflow artifact, never committed")
for cmd in (tick, week, reset):
    cmd.add_argument("--data", default="data")
    cmd.add_argument("--out", default="site/data", help="dashboard export folder")
args = parser.parse_args()

if args.command == "reset":
    cwd = Path.cwd()
    for folder in (args.data, args.out):
        path = Path(folder).resolve()
        if path == cwd or not path.is_relative_to(cwd):
            raise SystemExit(f"refusing to delete {path}: reset only removes folders inside {cwd}")
    for folder in (args.data, args.out):
        if Path(folder).exists():
            shutil.rmtree(folder)
    print(f"removed {args.data} and {args.out}: run run-week to start Week 1")
    raise SystemExit

source = market.replay(args.fixtures) if args.fixtures else market.live
if args.record:
    source = market.recording(source, args.record)
if args.response:
    response = json.loads(Path(args.response).read_text())
    model = lambda _model_id, _request: response
elif os.environ.get("OPENROUTER_API_KEY"):
    model = openrouter.client(os.environ["OPENROUTER_API_KEY"], args.artifacts)
else:
    raise SystemExit("set OPENROUTER_API_KEY to call the models, or pass --response for a scripted reply")
config = json.loads(Path(args.config).read_text())
run = run_tick if args.command == "run-tick" else run_week
if not run(args.at, source, model, args.data, config):
    print(f"nothing ran at {args.at}: already ran, eliminated, waiting for its first Week, or skipped (see {args.data}/runs.jsonl)")
export(args.data, args.out, config)  # also after a skip, so the dashboard shows the skipped Tick
