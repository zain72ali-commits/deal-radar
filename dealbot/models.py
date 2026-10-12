"""Domain models, plus their JSON-friendly (de)serialisation for the state file."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class Price:
    """Price information read from a deal title. All amounts are AUD."""

    amount: float | None = None      # deal price, None when the title has none
    unit: str | None = None          # e.g. "month" for "$69/M"; None for one-off prices
    was: float | None = None         # "was"/"RRP" price stated in the title
    discount_pct: int | None = None  # from was/RRP, or an explicit "30% off"
    is_free: bool = False


@dataclass(frozen=True)
class Deal:
    id: str
    title: str
    url: str                    # the OzBargain deal page
    image: str | None
    category: str
    tags: tuple[str, ...]
    products: tuple[str, ...]   # OzBargain product slugs, used for price history
    posted_at: datetime
    starts_at: datetime | None
    expires_at: datetime | None
    flagged_expired: bool       # OzBargain marked it expired / out of stock
    long_running: bool
    votes_pos: int
    votes_neg: int
    comments: int
    price: Price

    def to_dict(self) -> dict:
        data = asdict(self)
        data["tags"] = list(self.tags)
        data["products"] = list(self.products)
        for key in ("posted_at", "starts_at", "expires_at"):
            value = getattr(self, key)
            data[key] = value.isoformat() if value else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Deal:
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            url=str(data["url"]),
            image=data.get("image"),
            category=str(data["category"]),
            tags=tuple(data.get("tags", [])),
            products=tuple(data.get("products", [])),
            posted_at=datetime.fromisoformat(data["posted_at"]),
            starts_at=_optional_datetime(data.get("starts_at")),
            expires_at=_optional_datetime(data.get("expires_at")),
            flagged_expired=bool(data.get("flagged_expired", False)),
            long_running=bool(data.get("long_running", False)),
            votes_pos=int(data.get("votes_pos", 0)),
            votes_neg=int(data.get("votes_neg", 0)),
            comments=int(data.get("comments", 0)),
            price=Price(**data.get("price", {})),
        )


def _optional_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
