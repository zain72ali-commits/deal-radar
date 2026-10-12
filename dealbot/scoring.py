"""Signals for how competitive a deal is versus the market.

Two signals the data honestly supports:
1. Community verdict - OzBargain members vote on whether a deal beats the
   market, so the up/down split is a crowd-sourced market comparison.
2. Price history - the bot remembers the lowest price it has seen for each
   OzBargain product (e.g. /product/kingston-nv2), so it can tell you whether
   today's price is a new low. This history starts empty and grows daily.
"""

from __future__ import annotations

from .config import ScoringSettings
from .models import Deal

STRONG, POSITIVE, MIXED, EARLY = "strong", "positive", "mixed", "early"


def verdict(deal: Deal, settings: ScoringSettings) -> str:
    total = deal.votes_pos + deal.votes_neg
    if total < settings.min_votes_for_verdict:
        return EARLY
    if deal.votes_neg / total >= settings.mixed_negative_ratio:
        return MIXED
    if deal.votes_pos >= settings.strong_min_votes:
        return STRONG
    return POSITIVE


def compare_to_history(deal: Deal, history: dict) -> dict | None:
    """Compare a deal's price with the lowest price previously seen for its product."""
    key = _history_key(deal)
    record = history.get(key) if key else None
    if not record or record["deal_id"] == deal.id or record["unit"] != deal.price.unit:
        return None
    amount, low = deal.price.amount, record["low"]
    status = "new_low" if amount < low else "matches_low" if amount == low else "above_low"
    return {"status": status, "previous_low": low, "previous_low_date": record["date"]}


def record_price(deal: Deal, history: dict, seen_at: str) -> None:
    """Update `history` in place if this deal sets a new low for its product."""
    key = _history_key(deal)
    if not key:
        return
    record = history.get(key)
    if record and record["unit"] != deal.price.unit:
        return
    if record is None or deal.price.amount < record["low"]:
        history[key] = {
            "low": deal.price.amount,
            "unit": deal.price.unit,
            "deal_id": deal.id,
            "date": seen_at,
        }


def _history_key(deal: Deal) -> str | None:
    # Only single-product deals: a bundle's headline price can't be pinned to one product.
    if len(deal.products) != 1 or deal.price.amount is None:
        return None
    return deal.products[0]
