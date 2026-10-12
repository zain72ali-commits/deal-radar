import unittest
from unittest import mock

import requests

from dealbot import fetcher
from dealbot.fetcher import FeedFetcher, FetchError
from tests.helpers import make_config


class FakeResponse:
    def __init__(self, status=200, body=b"<rss/>", url="https://www.ozbargain.com.au/cat/computing/feed"):
        self.status_code, self._body, self.url = status, body, url

    def iter_content(self, chunk_size):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, *responses):
        self.headers, self.calls, self._responses = {}, [], list(responses)

    def get(self, url, **kwargs):
        assert kwargs.get("allow_redirects") is False, "redirects must not be followed"
        self.calls.append(url)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@mock.patch.object(fetcher.time, "sleep")
class FeedFetcherTest(unittest.TestCase):
    def make(self, *responses):
        session = FakeSession(*responses)
        return FeedFetcher(make_config().source, session=session), session

    def test_fetches_category_feed_with_user_agent(self, _sleep):
        feed, session = self.make(FakeResponse(body=b"<rss>ok</rss>"))
        self.assertEqual(feed.fetch_category("computing"), b"<rss>ok</rss>")
        self.assertEqual(session.calls, ["https://www.ozbargain.com.au/cat/computing/feed"])
        self.assertEqual(session.headers["User-Agent"], "test-agent")

    def test_retries_server_errors_then_succeeds(self, sleep):
        feed, session = self.make(FakeResponse(503), requests.ConnectionError("reset"), FakeResponse())
        self.assertEqual(feed.fetch_category("computing"), b"<rss/>")
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(sleep.call_count, 2)

    def test_gives_up_after_max_attempts(self, _sleep):
        feed, _ = self.make(FakeResponse(503), FakeResponse(503), FakeResponse(503))
        with self.assertRaises(FetchError):
            feed.fetch_category("computing")

    def test_not_found_fails_without_retry(self, sleep):
        feed, session = self.make(FakeResponse(404))
        with self.assertRaises(FetchError):
            feed.fetch_category("utilities")
        self.assertEqual(len(session.calls), 1)
        sleep.assert_not_called()

    def test_refuses_redirects_without_retry(self, _sleep):
        feed, session = self.make(FakeResponse(302))
        with self.assertRaises(FetchError):
            feed.fetch_category("computing")
        self.assertEqual(len(session.calls), 1)

    def test_rejects_oversized_feed(self, _sleep):
        feed, _ = self.make(FakeResponse(body=b"x" * (fetcher._MAX_FEED_BYTES + 1)))
        with self.assertRaises(FetchError):
            feed.fetch_category("computing")


if __name__ == "__main__":
    unittest.main()
