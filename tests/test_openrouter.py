import json
import tempfile
import unittest
from urllib.error import HTTPError
from pathlib import Path

from bench.engine import MAX_WATCHLIST, MIN_NOTIONAL, run_tick
from bench.market import BAR_MS
from bench.openrouter import URL, client
from tests.helpers import CONFIG, FIXTURES, market

REQUEST = {"role": "executor", "at": "2026-10-19T01:07:00Z", "tsm": "rules", "plan": None}


def reply(content, usage=None):
    return {"choices": [{"message": {"content": content}}], "usage": usage or {"total_tokens": 1}}


class Client(unittest.TestCase):
    def setUp(self):
        self.artifacts = Path(tempfile.mkdtemp())
        self.posted = []

    def model(self, answer):
        """Client over a fake HTTP post: answer is the reply body, or an exception to raise."""
        def post(url, body, headers):
            self.posted.append(body)
            if isinstance(answer, Exception):
                raise answer
            return answer
        return client("key", self.artifacts, post)

    def test_failures_raise_to_the_engine_after_a_single_call(self):
        for name, answer in {"network": TimeoutError("timed out"),
                             "broken_json": reply("{not json"),
                             "not_an_object": reply("[1]"),
                             "http_status": HTTPError(URL, 502, "Bad Gateway", {}, None),
                             "no_choices": {"id": "gen-1"},
                             "openrouter_error": {"error": {"code": 429, "message": "Rate limit exceeded"}}}.items():
            with self.subTest(name):
                self.posted.clear()
                with self.assertRaises(Exception):
                    self.model(answer)("anthropic/x", REQUEST)
                self.assertEqual(len(self.posted), 1)

    def test_reply_is_parsed_with_usage_under_the_role_schema_and_the_raw_prompt_is_kept(self):
        usage = {"prompt_tokens": 900, "completion_tokens": 40, "total_tokens": 940}
        answer = self.model(reply('{"reasoning": "wait", "actions": [{"type": "hold"}]}', usage))("anthropic/x", REQUEST)

        self.assertEqual(answer, {"reasoning": "wait", "actions": [{"type": "hold"}], "_usage": usage})
        body = self.posted[0]
        self.assertEqual(body["response_format"]["json_schema"]["name"], "executor")
        self.assertNotIn("temperature", body)  # each vendor's default
        self.assertNotIn("tools", body)
        self.assertNotIn("provider", body)  # require_parameters would also demand structured_outputs, which some lack
        [kept] = [p for p in self.artifacts.rglob("*") if p.is_file()]
        self.assertNotIn(":", str(kept.relative_to(self.artifacts)))  # upload-artifact rejects colons
        self.assertEqual(json.loads(kept.read_text().splitlines()[-1])["messages"], body["messages"])

    def test_unparseable_reply_travels_whole_on_the_exception(self):
        content = "Sure! Here is my plan: " + "x" * 2000
        with self.assertRaises(ValueError) as raised:
            self.model(reply(content))("anthropic/x", REQUEST)
        self.assertEqual(raised.exception.raw, content)

    def test_strategist_is_told_the_plan_validation_up_front(self):
        self.model(reply("{}"))("anthropic/x", {**REQUEST, "role": "strategist"})

        system = self.posted[0]["messages"][0]["content"]
        for rule in (f"at most {MAX_WATCHLIST} symbols", "none repeated", "symbols", f"at least {MIN_NOTIONAL} USD",
                     "max leverage"):
            self.assertIn(rule, system)

    def test_retry_shows_the_previous_error_to_the_model(self):
        error = "watchlist has 6 symbols, at most 5"
        self.model(reply("{}"))("anthropic/x", {**REQUEST, "retry_error": error})

        system, user = self.posted[0]["messages"]
        self.assertEqual(system["role"], "system")
        self.assertIn("rules", system["content"])  # the TSM text rides in the system message, not the data dump
        self.assertNotIn('"tsm"', user["content"])
        self.assertEqual(json.loads(user["content"])["retry_error"], error)  # data, never instruction text


    def test_executor_prompt_for_a_full_watchlist_stays_near_30k_tokens(self):
        coins = ["BTC", "ETH", "SOL", "XRP", "HYPE"]
        at = "2026-10-19T05:07:00Z"
        fixtures = market()
        ctx = json.loads((FIXTURES / "metaAndAssetCtxs.json").read_text())[1][0]

        def info(body):  # five perps with every bar of ~200 present at realistic precision
            if body["type"] == "metaAndAssetCtxs":
                return [{"universe": [{"name": c, "maxLeverage": 40, "szDecimals": 5} for c in coins]}, [ctx] * 5]
            if body["type"] == "l2Book":
                return fixtures({"type": "l2Book", "coin": "BTC"})
            if body["type"] == "candleSnapshot":
                r, step = body["req"], BAR_MS[body["req"]["interval"]]
                return [{"t": t, "T": t + step - 1, "o": "112345.6", "h": "112999.1", "l": "111888.2", "c": "112456.7",
                         "v": "1234.56789"} for t in range(r["startTime"] - r["startTime"] % step, r["endTime"] + 1, step)]
            return fixtures(body)

        data = Path(tempfile.mkdtemp())
        (data / "x").mkdir()
        watchlist = [{"symbol": c, "bias": "both", "entry": "e" * 300, "exit": "x" * 300} for c in coins]
        plan = {"week": "2026-10-19T00:00:00Z", "notional": 10000, "watchlist": watchlist,
                "close_all": "c" * 300, "hostage_policy": "h" * 300, "rationale": "r" * 4000}
        (data / "x" / "plan.json").write_text(json.dumps(plan))
        (data / "x" / "state.json").write_text(json.dumps({"free_equity": 10000, "rp": {"collateral": 2500, "notional": 10000},
                                                           "layers": [None] * 4, "settled": at}))
        config = {**CONFIG, "contestants": [{"name": "x", "strategist": "s", "executor": "e"}]}
        run_tick(at, info, self.model(reply('{"reasoning": "", "actions": []}')), data, config)

        [body] = self.posted
        # ~3.5 characters per token for this JSON; the Thai TSM summary costs more per character, hence the margin
        self.assertLess(sum(len(m["content"]) for m in body["messages"]), 30_000 * 3)
        self.assertEqual(sorted(json.loads(body["messages"][1]["content"])["market"]), sorted(coins))


if __name__ == "__main__":
    unittest.main()
