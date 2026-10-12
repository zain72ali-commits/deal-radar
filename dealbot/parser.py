"""Parse OzBargain category RSS feeds into Deal objects.

Feed shape (verified against https://www.ozbargain.com.au/cat/computing/feed):
each <item> has title, link (/node/<id>), <category domain=".../cat|tag|brand|product/...">,
an <ozb:meta> element carrying votes, expiry and image, and optionally
<ozb:title-msg type="expired|longrunning">.

defusedxml is used because the XML comes from the network; it blocks entity
expansion and external entity attacks that the stdlib parser allows.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree.ElementTree import Element, ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

from .models import Deal
from .pricing import parse_price

log = logging.getLogger(__name__)

_OZB_NS = "{https://www.ozbargain.com.au}"
_IMAGE_HOST = "files.ozbargain.com.au"
_ID_RE = re.compile(r"^\d+$")


class FeedError(ValueError):
    """The feed could not be parsed at all."""


def parse_feed(xml_bytes: bytes, base_url: str) -> list[Deal]:
    try:
        root = fromstring(xml_bytes)
    except (ParseError, DefusedXmlException) as exc:
        raise FeedError(f"Feed is not valid or safe XML: {exc}") from exc

    channel = root.find("channel")
    if channel is None:
        raise FeedError("Feed has no <channel> element.")

    deals = []
    for item in channel.findall("item"):
        try:
            deals.append(_parse_item(item, base_url))
        except (ValueError, TypeError, AttributeError) as exc:
            log.warning("Skipping malformed feed item: %s", exc)
    return deals


def _parse_item(item: Element, base_url: str) -> Deal:
    deal_id = _text(item, "guid").split()[0]
    if not _ID_RE.match(deal_id):
        raise ValueError(f"unexpected guid {deal_id!r}")

    url = _text(item, "link")
    if not url.startswith(f"{base_url}/node/"):
        raise ValueError(f"unexpected deal link {url!r}")

    title = _text(item, "title")
    category, tags, products = _categories(item)
    meta = item.find(f"{_OZB_NS}meta")
    if meta is None:
        raise ValueError(f"deal {deal_id} has no ozb:meta")

    title_msg = item.find(f"{_OZB_NS}title-msg")
    msg_type = title_msg.get("type") if title_msg is not None else None

    return Deal(
        id=deal_id,
        title=title,
        url=url,
        image=_safe_image(meta.get("image")),
        category=category,
        tags=tags,
        products=products,
        posted_at=_aware(parsedate_to_datetime(_text(item, "pubDate"))),
        starts_at=_iso(meta.get("starting")),
        expires_at=_iso(meta.get("expiry")),
        flagged_expired=msg_type == "expired",
        long_running=msg_type == "longrunning",
        votes_pos=int(meta.get("votes-pos", "0")),
        votes_neg=int(meta.get("votes-neg", "0")),
        comments=int(meta.get("comment-count", "0")),
        price=parse_price(title),
    )


def _categories(item: Element) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    category = ""
    tags: list[str] = []
    products: list[str] = []
    for element in item.findall("category"):
        name = (element.text or "").strip()
        path = urlparse(element.get("domain", "")).path.strip("/").split("/")
        if len(path) != 2 or not name:
            continue
        kind, slug = path
        if kind == "cat" and not category:
            category = name
        elif kind in ("tag", "brand", "product"):
            tags.append(name)
            if kind == "product":
                products.append(slug)
    if not category:
        raise ValueError("item has no OzBargain category")
    return category, tuple(tags), tuple(products)


def _text(item: Element, tag: str) -> str:
    element = item.find(tag)
    if element is None or not (element.text or "").strip():
        raise ValueError(f"missing <{tag}>")
    return element.text.strip()


def _iso(value: str | None) -> datetime | None:
    return _aware(datetime.fromisoformat(value)) if value else None


def _aware(value: datetime) -> datetime:
    """Reject dates without a UTC offset; comparing them with aware dates would crash the run."""
    if value.tzinfo is None:
        raise ValueError(f"date without timezone: {value.isoformat()}")
    return value


def _safe_image(url: str | None) -> str | None:
    """Only keep https images served by OzBargain's own file host."""
    if not url:
        return None
    parsed = urlparse(url)
    return url if parsed.scheme == "https" and parsed.netloc == _IMAGE_HOST else None
