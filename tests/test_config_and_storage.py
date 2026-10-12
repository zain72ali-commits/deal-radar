import json
import tempfile
import unittest
from pathlib import Path

from dealbot.config import ConfigError, load_config, parse_config
from dealbot.storage import State, StateError, load_state, save_state, write_json_atomic

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def raw_config(**source_overrides):
    return {
        "source": {
            "base_url": "https://www.ozbargain.com.au",
            "user_agent": "ua",
            "request_timeout_seconds": 5,
            "delay_between_requests_seconds": 0,
            **source_overrides,
        },
        "categories": [{"name": "Computing", "slug": "computing"}],
        "filters": {"include_unpriced": True, "keep_unconfirmed_days": 7},
        "scoring": {"min_votes_for_verdict": 10, "strong_min_votes": 50, "mixed_negative_ratio": 0.15},
    }


class ConfigTest(unittest.TestCase):
    def test_shipped_config_is_valid(self):
        config = load_config(PROJECT_ROOT / "config.toml")
        self.assertIn("internet", [c.slug for c in config.categories])

    def test_rejects_unsafe_slug(self):
        raw = raw_config()
        raw["categories"] = [{"name": "Bad", "slug": "../api"}]
        with self.assertRaises(ConfigError):
            parse_config(raw)

    def test_rejects_plain_http(self):
        with self.assertRaises(ConfigError):
            parse_config(raw_config(base_url="http://www.ozbargain.com.au"))

    def test_rejects_duplicate_slugs(self):
        raw = raw_config()
        raw["categories"] *= 2
        with self.assertRaises(ConfigError):
            parse_config(raw)


class StorageTest(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "state.json"
            state = State(deals={"1": {"x": 1}}, price_history={"p": {"low": 1}}, last_run="t")
            save_state(path, state)
            self.assertEqual(load_state(path), state)

    def test_written_files_are_world_readable_for_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deals.json"
            write_json_atomic(path, {"ok": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_missing_file_gives_empty_state(self):
        self.assertEqual(load_state(Path("/nonexistent/state.json")), State())

    def test_rejects_unknown_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({"version": 99}))
            with self.assertRaises(StateError):
                load_state(path)


if __name__ == "__main__":
    unittest.main()
