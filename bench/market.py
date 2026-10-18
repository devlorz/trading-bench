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
