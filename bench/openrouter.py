"""OpenRouter model client: model(model_id, request) -> parsed JSON reply. It never retries: the Engine does,
passing the previous failure back as request["retry_error"]."""
import json
import urllib.request
from pathlib import Path

from bench.engine import MAX_WATCHLIST, MIN_NOTIONAL

URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = 300  # seconds; a Strategist reply over ~60k tokens of prompt can take minutes


class BadReply(ValueError):
    """The model answered but not with a JSON object; raw is its whole reply, for the Engine's archive."""

    def __init__(self, message, raw):
        super().__init__(message)
        self.raw = raw


def http_post(url, body, headers):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


TASK = {
    "executor": "You are the Executor. Decide this Tick's Actions within the Weekly Plan. Reply with JSON only: "
                '{"reasoning": string, "actions": [Action]}.',
    "strategist": "You are the Strategist. Write this Week's Weekly Plan. Reply with JSON only: "
                  '{"notional", "watchlist": [{"symbol", "bias", "entry", "exit"}], "close_all", "hostage_policy", "rationale"}. '
                  # the Engine's plan validation, stated up front so a paid retry is not the first the model hears of it
                  f"The plan is rejected unless: the watchlist has at most {MAX_WATCHLIST} symbols, none repeated, each "
                  f"one of the data's symbols; notional is at least {MIN_NOTIONAL} USD; and the leverage this Week will "
                  "trade is at most the max leverage of every watchlist symbol: your notional / reallocation.collateral "
                  "when reallocation happens, otherwise the RP in state stays and its notional / collateral counts.",
}


RETRY = "If the data has retry_error, your previous reply was rejected for that reason: fix it and answer again."


def prompt(request):
    """System: the TSM text and the task. User: the request's data as JSON only, so text that came from a model
    (retry_error quotes its reply, the plan its rationale) never sits where instructions go."""
    data = {k: v for k, v in request.items() if k not in ("role", "tsm")}
    return [{"role": "system", "content": f"{request['tsm']}\n\n{TASK[request['role']]} {RETRY}"},
            {"role": "user", "content": json.dumps(data, separators=(",", ":"))}]


def strict(properties):
    """Strict structured output wants every property required and no others; optional ones are nullable."""
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT, NUMBER = {"type": "string"}, {"type": "number"}
SCHEMA = {
    "executor": strict({"reasoning": TEXT, "actions": {"type": "array", "items": strict({
        "type": {"enum": ["open", "close", "set_tp", "cancel_tp", "hold"]},
        "slot": {"type": ["integer", "null"]},
        "symbol": {"type": ["string", "null"]},
        "side": {"enum": ["long", "short", None]},
        "price": {"type": ["number", "null"]},
    })}}),
    "strategist": strict({
        "notional": NUMBER,
        "watchlist": {"type": "array", "items": strict({
            "symbol": TEXT, "bias": {"enum": ["long", "short", "both", "avoid"]}, "entry": TEXT, "exit": TEXT})},
        "close_all": TEXT, "hostage_policy": TEXT, "rationale": TEXT,
    }),
}


def client(api_key, artifacts, post=http_post):
    """artifacts: folder for raw prompts, uploaded by the workflow and never committed."""
    def model(model_id, request):
        role = request["role"]
        body = {"model": model_id, "messages": prompt(request),
                "response_format": {"type": "json_schema", "json_schema": {"name": role, "strict": True, "schema": SCHEMA[role]}}}
        folder = Path(artifacts) / request["at"].replace(":", "-")  # upload-artifact rejects colons
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f"{model_id.replace('/', '_')}.jsonl", "a") as log:  # one line per attempt
            log.write(json.dumps(body) + "\n")
        reply = post(URL, body, {"Authorization": f"Bearer {api_key}"})
        if "error" in reply:
            raise RuntimeError(f"OpenRouter error: {reply['error']}")
        content = reply["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except ValueError:
            raise BadReply("reply is not JSON", content) from None
        if not isinstance(parsed, dict):
            raise BadReply("reply is not a JSON object", content)
        return {**parsed, "_usage": reply.get("usage")}  # the Engine pops it into the response archive

    return model
