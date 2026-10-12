"""Shared test helpers."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dealbot.config import Config, parse_config
from dealbot.models import Deal, Price

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://www.ozbargain.com.au"
AEDT = timezone(timedelta(hours=11))
NOW = datetime(2026, 10, 12, 17, 0, tzinfo=AEDT)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def make_config(**category_overrides) -> Config:
    computing = {"name": "Computing", "slug": "computing", **category_overrides}
    return parse_config({
        "source": {
            "base_url": BASE_URL,
            "user_agent": "test-agent",
            "request_timeout_seconds": 5,
            "delay_between_requests_seconds": 0,
        },
        "categories": [computing, {"name": "Internet", "slug": "internet"}],
        "filters": {
            "include_unpriced": True,
            "exclude_categories": ["Alcohol", "Pets"],
            "exclude_keywords": ["wine", "pet", "medicare", "cat food"],
            "keep_unconfirmed_days": 7,
        },
        "scoring": {"min_votes_for_verdict": 10, "strong_min_votes": 50, "mixed_negative_ratio": 0.15},
    })


def make_deal(**overrides) -> Deal:
    deal = Deal(
        id="1",
        title="Widget $10 @ Store",
        url=f"{BASE_URL}/node/1",
        image=None,
        category="Computing",
        tags=(),
        products=(),
        posted_at=NOW - timedelta(hours=1),
        starts_at=None,
        expires_at=None,
        flagged_expired=False,
        long_running=False,
        votes_pos=20,
        votes_neg=0,
        comments=3,
        price=Price(amount=10.0),
    )
    return replace(deal, **overrides)
