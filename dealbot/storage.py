"""JSON persistence: the state file between runs and the dashboard data file."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

STATE_VERSION = 1


@dataclass
class State:
    # deal id -> {"deal": Deal.to_dict(), "category_slug", "first_seen", "last_seen", "history"}
    deals: dict[str, dict] = field(default_factory=dict)
    # OzBargain product slug -> {"low", "unit", "deal_id", "date"}
    price_history: dict[str, dict] = field(default_factory=dict)
    last_run: str | None = None


class StateError(ValueError):
    """The state file exists but cannot be used."""


def load_state(path: Path) -> State:
    if not path.exists():
        return State()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"Cannot read state file {path}: {exc}") from exc
    if raw.get("version") != STATE_VERSION:
        raise StateError(f"Unsupported state version {raw.get('version')!r} in {path}")
    return State(
        deals=dict(raw.get("deals", {})),
        price_history=dict(raw.get("price_history", {})),
        last_run=raw.get("last_run"),
    )


def save_state(path: Path, state: State) -> None:
    write_json_atomic(path, {
        "version": STATE_VERSION,
        "last_run": state.last_run,
        "deals": state.deals,
        "price_history": state.price_history,
    })


def write_json_atomic(path: Path, data: object) -> None:
    """Write to a temp file then rename, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1, sort_keys=True)
            handle.write("\n")
        # mkstemp creates 0600 files; GitHub Pages needs them world-readable.
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
