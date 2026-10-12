"""Decide which deals are worth showing."""

from __future__ import annotations

import re
from datetime import datetime

from .config import Category, FilterSettings
from .models import Deal


def is_live(deal: Deal, now: datetime) -> bool:
    """Live = not flagged expired/out of stock, already started, not past expiry."""
    if deal.flagged_expired:
        return False
    if deal.starts_at and deal.starts_at > now:
        return False
    return not (deal.expires_at and deal.expires_at <= now)


class DealFilter:
    def __init__(self, settings: FilterSettings):
        self._settings = settings
        self._excluded_categories = {c.casefold() for c in settings.exclude_categories}
        keywords = sorted(settings.exclude_keywords, key=len, reverse=True)
        self._keyword_re = (
            re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b", re.IGNORECASE)
            if keywords
            else None
        )

    def keep(self, deal: Deal, category: Category, now: datetime) -> bool:
        return (
            is_live(deal, now)
            and not self.is_excluded(deal)
            and self._within_price_cap(deal, category)
        )

    def is_excluded(self, deal: Deal) -> bool:
        if deal.category.casefold() in self._excluded_categories:
            return True
        if any(tag.casefold() in self._excluded_categories for tag in deal.tags):
            return True
        if self._keyword_re is None:
            return False
        haystack = " | ".join((deal.title, *deal.tags))
        return self._keyword_re.search(haystack) is not None

    def _within_price_cap(self, deal: Deal, category: Category) -> bool:
        amount = deal.price.amount
        if amount is None:
            return self._settings.include_unpriced
        return category.max_price is None or amount <= category.max_price
