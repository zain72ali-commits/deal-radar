"""One daily run: merge freshly fetched deals into state and build dashboard data.

This module does no I/O, so the whole run can be tested with fixture feeds.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from .config import Category, Config
from .filters import DealFilter
from .models import Deal
from .scoring import compare_to_history, record_price, verdict
from .storage import State

log = logging.getLogger(__name__)
_MAX_TAGS_SHOWN = 8


@dataclass(frozen=True)
class RunResult:
    state: State
    dashboard: dict


def run(
    feeds: dict[str, list[Deal]],
    failed_slugs: list[str],
    state: State,
    config: Config,
    now: datetime,
) -> RunResult:
    """`feeds` maps category slug -> deals for every category fetched successfully."""
    run_ts = now.isoformat(timespec="seconds")
    deal_filter = DealFilter(config.filters)
    categories = {c.slug: c for c in config.categories}
    records = {deal_id: dict(record) for deal_id, record in state.deals.items()}
    history = {slug: dict(record) for slug, record in state.price_history.items()}

    accepted_this_run: set[str] = set()
    for slug, deals in feeds.items():
        for deal in deals:
            if not deal_filter.keep(deal, categories[slug], now):
                # A cross-listed deal accepted via another category this run stays.
                if deal.id not in accepted_this_run:
                    records.pop(deal.id, None)
                continue
            accepted_this_run.add(deal.id)
            previous = records.get(deal.id) or {
                "first_seen": run_ts,
                "history": compare_to_history(deal, history),
            }
            record_price(deal, history, run_ts)
            records[deal.id] = {
                "deal": deal.to_dict(),
                "category_slug": slug,
                "first_seen": previous["first_seen"],
                "history": previous["history"],
                "last_seen": run_ts,
            }

    kept = _prune(records, categories, deal_filter, config, now)
    dashboard = {
        "generated_at": run_ts,
        "categories": [{"name": c.name, "slug": c.slug} for c in config.categories],
        "failed_categories": [categories[s].name for s in failed_slugs if s in categories],
        "deals": [
            _dashboard_entry(record, deal, run_ts, config)
            for record, deal in sorted(kept.values(), key=lambda pair: pair[1].posted_at, reverse=True)
        ],
    }
    new_state = State(
        deals={deal_id: record for deal_id, (record, _) in kept.items()},
        price_history=history,
        last_run=run_ts,
    )
    return RunResult(state=new_state, dashboard=dashboard)


def _prune(
    records: dict[str, dict],
    categories: dict[str, Category],
    deal_filter: DealFilter,
    config: Config,
    now: datetime,
) -> dict[str, tuple[dict, Deal]]:
    """Drop deals that expired, were excluded by a config change, or went unconfirmed too long."""
    cutoff = now - timedelta(days=config.filters.keep_unconfirmed_days)
    kept = {}
    for deal_id, record in records.items():
        category = categories.get(record.get("category_slug", ""))
        if category is None:
            continue  # category removed from config
        try:
            deal = Deal.from_dict(record["deal"])
            last_seen = datetime.fromisoformat(record["last_seen"])
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("Dropping unreadable state record %s: %s", deal_id, exc)
            continue
        if last_seen >= cutoff and deal_filter.keep(deal, category, now):
            kept[deal_id] = (record, deal)
    return kept


def _dashboard_entry(record: dict, deal: Deal, run_ts: str, config: Config) -> dict:
    return {
        "id": deal.id,
        "title": deal.title,
        "url": deal.url,
        "image": deal.image,
        "category": deal.category,
        "category_slug": record["category_slug"],
        "tags": list(deal.tags[:_MAX_TAGS_SHOWN]),
        "posted_at": deal.posted_at.isoformat(),
        "starts_at": deal.starts_at.isoformat() if deal.starts_at else None,
        "expires_at": deal.expires_at.isoformat() if deal.expires_at else None,
        "long_running": deal.long_running,
        "votes_pos": deal.votes_pos,
        "votes_neg": deal.votes_neg,
        "comments": deal.comments,
        "price": asdict(deal.price),
        "verdict": verdict(deal, config.scoring),
        "history": record["history"],
        "is_new": record["first_seen"] == run_ts,
        "last_confirmed": record["last_seen"],
        "confirmed_today": record["last_seen"] == run_ts,
    }
