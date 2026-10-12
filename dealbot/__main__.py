"""Entry point: python -m dealbot [--config config.toml] [--state ...] [--output ...]"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, load_config
from .fetcher import FeedFetcher, FetchError
from .models import Deal
from .parser import FeedError, parse_feed
from .pipeline import run
from .storage import StateError, load_state, save_state, write_json_atomic

log = logging.getLogger("dealbot")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        config = load_config(args.config)
        state = load_state(args.state)
    except (ConfigError, StateError) as exc:
        log.error("%s", exc)
        return 2

    fetcher = FeedFetcher(config.source)
    feeds: dict[str, list[Deal]] = {}
    failed: list[str] = []
    for index, category in enumerate(config.categories):
        if index:
            time.sleep(config.source.delay_between_requests_seconds)
        try:
            feeds[category.slug] = parse_feed(fetcher.fetch_category(category.slug), config.source.base_url)
            log.info("%s: %d deals in feed", category.name, len(feeds[category.slug]))
        except (FetchError, FeedError) as exc:
            log.error("%s: skipped (%s)", category.name, exc)
            failed.append(category.slug)

    if not feeds:
        log.error("Every category failed; leaving state and dashboard unchanged.")
        return 1

    result = run(feeds, failed, state, config, datetime.now(timezone.utc))
    save_state(args.state, result.state)
    write_json_atomic(args.output, result.dashboard)

    deals = result.dashboard["deals"]
    log.info("Dashboard: %d live deals, %d new this run.", len(deals), sum(d["is_new"] for d in deals))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dealbot", description="Daily OzBargain category deal check.")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--state", type=Path, default=Path("data/state.json"))
    parser.add_argument("--output", type=Path, default=Path("site/data/deals.json"))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
