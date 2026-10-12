"""Read prices out of OzBargain deal titles.

OzBargain feeds have no structured price field, so the price comes from the
title, e.g. "SSD $159 (RRP $199) + Delivery ($0 C&C) @ Store". The rules are
deliberately simple heuristics; anything ambiguous is left as "no price"
rather than guessed.
"""

from __future__ import annotations

import re

from .models import Price

_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?"

# "$159", "$1,499", "A$16", "AU$29", "$69/M". The look-behind rejects "US$" and "NZ$".
_MONEY_RE = re.compile(
    rf"(?<![A-Za-z])(?:AU?)?\$\s?(?P<num>{_NUMBER})"
    r"(?:\s*/\s*(?P<unit>month|mth|mo|m|night|nt|year|yr|week|wk)\b)?",
    re.IGNORECASE,
)
_WAS_RE = re.compile(rf"\b(?:was|rrp)\b\s*:?\s*(?:AU?)?\$\s?(?P<num>{_NUMBER})", re.IGNORECASE)
_PERCENT_OFF_RE = re.compile(r"(?<![\d.])(\d{1,2}(?:\.\d+)?)\s*%\s*off\b", re.IGNORECASE)
_HALF_PRICE_RE = re.compile(r"(?:\b1/2|\bhalf)\s+price\b", re.IGNORECASE)
_LEADING_TAGS_RE = re.compile(r"^(?:\[([^\]]*)\]\s*)+")

# A dollar amount right after one of these is a threshold, add-on or old price.
_SKIP_IF_PRECEDED_BY = ("was", "rrp", "spend", "save", "+", "(")
# A dollar amount right before one of these words is a discount or bonus, not a price.
_SKIP_IF_FOLLOWED_BY_RE = re.compile(r"(?:off|cashback|voucher|credit|back|gift card|bonus|spend)\b")
# "Free Delivery/Shipping" titles are about postage, not a free product.
_FREE_POSTAGE_RE = re.compile(r"free\s+(?:delivery|shipping|postage|express|returns)\b", re.IGNORECASE)

_UNITS = {
    "m": "month", "mo": "month", "mth": "month", "month": "month",
    "nt": "night", "night": "night",
    "yr": "year", "year": "year",
    "wk": "week", "week": "week",
}


def parse_price(title: str) -> Price:
    amount, unit = _deal_amount(title)
    # A real price wins over the word "Free" ("Free Upgrade to 1TB with Laptop $1,299").
    is_free = amount == 0 or (amount is None and _is_free(title))
    if is_free:
        amount = 0.0

    was = _first_number(_WAS_RE, title)
    return Price(
        amount=amount,
        unit=unit,
        was=was,
        discount_pct=_discount(amount, was, title),
        is_free=is_free,
    )


def _deal_amount(title: str) -> tuple[float | None, str | None]:
    for match in _MONEY_RE.finditer(title):
        before = title[: match.start()].rstrip().lower()
        raw_after = title[match.end():]
        after = raw_after.lstrip(" +").lower()
        is_threshold = raw_after.startswith("+")  # "$50+ orders" is a minimum spend
        if is_threshold or before.endswith(_SKIP_IF_PRECEDED_BY) or _SKIP_IF_FOLLOWED_BY_RE.match(after):
            continue
        unit = match.group("unit")
        return _to_float(match.group("num")), _UNITS[unit.lower()] if unit else None
    return None, None


def _is_free(title: str) -> bool:
    """True for titles like "[PC] Free - Game" or "[Free] Software"."""
    leading = _LEADING_TAGS_RE.match(title)
    rest = title
    if leading:
        tags = re.findall(r"\[([^\]]*)\]", leading.group(0))
        if any(tag.strip().lower() == "free" for tag in tags):
            return True
        rest = title[leading.end():]
    rest = rest.strip()
    return re.match(r"free\b", rest, re.IGNORECASE) is not None and not _FREE_POSTAGE_RE.match(rest)


def _discount(amount: float | None, was: float | None, title: str) -> int | None:
    if amount is not None and was and was > amount:
        return round((was - amount) / was * 100)
    percent = _first_number(_PERCENT_OFF_RE, title)
    if percent is not None:
        return round(percent)
    if _HALF_PRICE_RE.search(title):
        return 50
    return None


def _first_number(pattern: re.Pattern, text: str) -> float | None:
    match = pattern.search(text)
    return _to_float(match.group(1)) if match else None


def _to_float(number: str) -> float:
    return float(number.replace(",", ""))
