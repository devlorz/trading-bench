import io
import json
import unittest
from urllib.error import HTTPError

from bench.market import INFO_URL, live


def busy(retry_after=None):
    return HTTPError(INFO_URL, 429, "Too Many Requests", {"Retry-After": retry_after} if retry_after else {}, None)


class Live(unittest.TestCase):
    def call(self, *answers):
        """live() over a fake urlopen that raises or answers in turn; returns the result and the sleeps taken."""
        answers, slept = iter(answers), []

        def urlopen(_req, timeout):
            answer = next(answers)
            if isinstance(answer, Exception):
                raise answer
            return io.BytesIO(json.dumps(answer).encode())

        return live({"type": "meta"}, urlopen=urlopen, sleep=slept.append), slept

    def test_rate_limited_request_waits_as_told_then_succeeds(self):
        self.assertEqual(self.call(busy("3"), busy(), {"ok": 1}), ({"ok": 1}, [3, 20]))

    def test_other_errors_and_a_429_past_the_last_wait_raise(self):
        down = HTTPError(INFO_URL, 500, "Internal Server Error", {}, None)
        for name, answers in {"server_error": [down], "still_busy": [busy()] * 5}.items():
            with self.subTest(name), self.assertRaises(HTTPError):
                self.call(*answers)


if __name__ == "__main__":
    unittest.main()
