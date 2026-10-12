import unittest
from dataclasses import replace
from datetime import timedelta

from dealbot.parser import parse_feed
from dealbot.pipeline import run
from dealbot.storage import State
from tests.helpers import BASE_URL, NOW, fixture, make_config


def feeds():
    return {
        "computing": parse_feed(fixture("computing_feed.xml"), BASE_URL),
        "internet": parse_feed(fixture("internet_feed.xml"), BASE_URL),
    }


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.config = make_config()
        self.first = run(feeds(), [], State(), self.config, NOW)

    def ids(self, result):
        return [d["id"] for d in result.dashboard["deals"]]

    def test_keeps_only_live_deals_newest_first(self):
        # 978414 expired at 10am today, 978189 is flagged out of stock.
        self.assertEqual(self.ids(self.first), ["978661", "978561", "978464", "977686", "977478", "976888", "971220"])

    def test_first_run_marks_everything_new(self):
        self.assertTrue(all(d["is_new"] for d in self.first.dashboard["deals"]))

    def test_second_run_only_new_deals_marked_new(self):
        computing, internet = feeds()["computing"], feeds()["internet"]
        extra = replace(computing[0], id="999999", url=f"{BASE_URL}/node/999999", posted_at=NOW)
        later = NOW + timedelta(days=1)
        second = run({"computing": [extra, *computing], "internet": internet}, [], self.first.state, self.config, later)
        new_ids = [d["id"] for d in second.dashboard["deals"] if d["is_new"]]
        self.assertEqual(new_ids, ["999999"])

    def test_deal_missing_from_feed_is_kept_until_unconfirmed_limit(self):
        later = NOW + timedelta(days=3)
        second = run({"computing": [], "internet": []}, [], self.first.state, self.config, later)
        # The SSD (978464) expires 2026-10-13, so it drops; never-expiring deals remain.
        self.assertNotIn("978464", self.ids(second))
        cpu = next(d for d in second.dashboard["deals"] if d["id"] == "977686")
        self.assertFalse(cpu["confirmed_today"])

        much_later = NOW + timedelta(days=8)
        third = run({"computing": [], "internet": []}, [], second.state, self.config, much_later)
        self.assertEqual(self.ids(third), [])

    def test_failed_category_is_reported_and_its_deals_kept(self):
        later = NOW + timedelta(days=1)
        second = run({"computing": feeds()["computing"]}, ["internet"], self.first.state, self.config, later)
        self.assertEqual(second.dashboard["failed_categories"], ["Internet"])
        self.assertIn("976888", self.ids(second))

    def test_deal_that_becomes_expired_is_removed(self):
        computing = feeds()["computing"]
        expired_cpu = [replace(d, flagged_expired=True) if d.id == "977686" else d for d in computing]
        second = run({"computing": expired_cpu, "internet": feeds()["internet"]}, [], self.first.state,
                     self.config, NOW + timedelta(hours=1))
        self.assertNotIn("977686", self.ids(second))

    def test_price_history_flags_a_cheaper_repost(self):
        cpu = next(d for d in feeds()["computing"] if d.id == "977686")
        repost = replace(cpu, id="980000", url=f"{BASE_URL}/node/980000",
                         price=replace(cpu.price, amount=549.0), posted_at=NOW)
        second = run({"computing": [repost], "internet": []}, [], self.first.state,
                     self.config, NOW + timedelta(days=1))
        entry = next(d for d in second.dashboard["deals"] if d["id"] == "980000")
        self.assertEqual(entry["history"]["status"], "new_low")
        self.assertEqual(entry["history"]["previous_low"], 581.99)

    def test_cross_listed_deal_kept_if_any_category_accepts_it(self):
        config = make_config(max_price=10)  # Computing capped at $10, Internet uncapped
        cpu = next(d for d in feeds()["computing"] if d.id == "977686")  # $581.99
        for order in (("internet", "computing"), ("computing", "internet")):
            result = run({slug: [cpu] for slug in order}, [], State(), config, NOW)
            self.assertEqual(self.ids(result), ["977686"], order)

    def test_dashboard_entry_shape(self):
        entry = next(d for d in self.first.dashboard["deals"] if d["id"] == "977478")
        self.assertEqual(entry["verdict"], "positive")  # 41 up / 7 down = 14.6% negative
        self.assertEqual(entry["price"]["unit"], "month")
        self.assertEqual(entry["category_slug"], "internet")


if __name__ == "__main__":
    unittest.main()
