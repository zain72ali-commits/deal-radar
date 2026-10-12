"""Load config.toml and validate it into typed, immutable settings."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ConfigError(ValueError):
    """Raised when config.toml is missing or holds invalid values."""


@dataclass(frozen=True)
class Category:
    name: str
    slug: str
    max_price: float | None = None


@dataclass(frozen=True)
class SourceSettings:
    base_url: str
    user_agent: str
    request_timeout_seconds: float
    delay_between_requests_seconds: float


@dataclass(frozen=True)
class FilterSettings:
    include_unpriced: bool
    exclude_categories: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    keep_unconfirmed_days: int


@dataclass(frozen=True)
class ScoringSettings:
    min_votes_for_verdict: int
    strong_min_votes: int
    mixed_negative_ratio: float


@dataclass(frozen=True)
class Config:
    source: SourceSettings
    categories: tuple[Category, ...]
    filters: FilterSettings
    scoring: ScoringSettings


def load_config(path: Path) -> Config:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Cannot read {path}: {exc}") from exc
    try:
        return parse_config(raw)
    except (KeyError, TypeError) as exc:
        raise ConfigError(f"Missing or malformed setting in {path}: {exc!r}") from exc


def parse_config(raw: dict) -> Config:
    source = _parse_source(raw["source"])
    categories = tuple(_parse_category(c) for c in raw["categories"])
    if not categories:
        raise ConfigError("At least one [[categories]] entry is required.")
    slugs = [c.slug for c in categories]
    if len(slugs) != len(set(slugs)):
        raise ConfigError("Category slugs must be unique.")

    f = raw["filters"]
    filters = FilterSettings(
        include_unpriced=_bool(f["include_unpriced"], "include_unpriced"),
        exclude_categories=tuple(str(c) for c in f.get("exclude_categories", [])),
        exclude_keywords=tuple(str(k).strip() for k in f.get("exclude_keywords", []) if str(k).strip()),
        keep_unconfirmed_days=_positive_int(f["keep_unconfirmed_days"], "keep_unconfirmed_days"),
    )

    s = raw["scoring"]
    ratio = float(s["mixed_negative_ratio"])
    if not 0 < ratio < 1:
        raise ConfigError("mixed_negative_ratio must be between 0 and 1.")
    scoring = ScoringSettings(
        min_votes_for_verdict=_positive_int(s["min_votes_for_verdict"], "min_votes_for_verdict"),
        strong_min_votes=_positive_int(s["strong_min_votes"], "strong_min_votes"),
        mixed_negative_ratio=ratio,
    )
    return Config(source=source, categories=categories, filters=filters, scoring=scoring)


def _parse_source(s: dict) -> SourceSettings:
    base_url = str(s["base_url"]).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise ConfigError("base_url must be an https origin, e.g. https://www.ozbargain.com.au")
    user_agent = str(s["user_agent"]).strip()
    if not user_agent:
        raise ConfigError("user_agent must not be empty.")
    timeout = float(s["request_timeout_seconds"])
    delay = float(s["delay_between_requests_seconds"])
    if timeout <= 0 or delay < 0:
        raise ConfigError("request_timeout_seconds must be > 0 and delay must be >= 0.")
    return SourceSettings(base_url, user_agent, timeout, delay)


def _parse_category(c: dict) -> Category:
    name = str(c["name"]).strip()
    slug = str(c["slug"]).strip()
    if not name:
        raise ConfigError("Every category needs a name.")
    if not _SLUG_RE.match(slug):
        raise ConfigError(f"Invalid category slug {slug!r}: use lowercase letters, digits and hyphens.")
    max_price = c.get("max_price")
    if max_price is not None:
        max_price = float(max_price)
        if max_price <= 0:
            raise ConfigError(f"max_price for {name} must be positive.")
    return Category(name=name, slug=slug, max_price=max_price)


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{name} must be a positive whole number.")
    return value


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be true or false.")
    return value
