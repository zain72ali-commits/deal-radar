"""Polite HTTP fetching of OzBargain category feeds.

Only /cat/<slug>/feed is requested; OzBargain's robots.txt allows it
(it disallows /api/, /search/, /goto/ and similar, which this bot never touches).
"""

from __future__ import annotations

import logging
import time

import requests

from .config import SourceSettings

log = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 5
_MAX_FEED_BYTES = 5 * 1024 * 1024
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """A feed could not be downloaded."""


class FeedFetcher:
    def __init__(self, settings: SourceSettings, session: requests.Session | None = None):
        self._settings = settings
        self._session = session or requests.Session()
        self._session.headers.update({
            "User-Agent": settings.user_agent,
            "Accept": "application/rss+xml, application/xml;q=0.9",
        })

    def fetch_category(self, slug: str) -> bytes:
        url = f"{self._settings.base_url}/cat/{slug}/feed"
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return self._get(url)
            except _Retryable as exc:
                if attempt == _MAX_ATTEMPTS:
                    raise FetchError(f"{url}: {exc}") from exc
                wait = _BACKOFF_SECONDS * attempt
                log.warning("%s failed (%s); retrying in %ss", url, exc, wait)
                time.sleep(wait)
        raise AssertionError("unreachable")

    def _get(self, url: str) -> bytes:
        try:
            # Redirects are not followed: the feed URL is fixed, so any redirect is unexpected.
            with self._session.get(
                url,
                timeout=self._settings.request_timeout_seconds,
                stream=True,
                allow_redirects=False,
            ) as resp:
                if resp.status_code in _RETRYABLE_STATUS:
                    raise _Retryable(f"HTTP {resp.status_code}")
                if resp.status_code != 200:
                    raise FetchError(f"{url}: HTTP {resp.status_code}")
                return _read_capped(resp)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise _Retryable(str(exc)) from exc


class _Retryable(Exception):
    pass


def _read_capped(resp: requests.Response) -> bytes:
    chunks, size = [], 0
    for chunk in resp.iter_content(chunk_size=64 * 1024):
        size += len(chunk)
        if size > _MAX_FEED_BYTES:
            raise FetchError(f"{resp.url}: feed larger than {_MAX_FEED_BYTES} bytes")
        chunks.append(chunk)
    return b"".join(chunks)
