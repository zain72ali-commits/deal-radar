import unittest
from datetime import timedelta

from dealbot.filters import DealFilter, is_live
from dealbot.models import Price
from tests.helpers import NOW, make_config, make_deal


class IsLiveTest(unittest.TestCase):
    def test_plain_deal_is_live(self):
        self.assertTrue(is_live(make_deal(), NOW))

    def test_flagged_expired_is_not_live(self):
        self.assertFalse(is_live(make_deal(flagged_expired=True), NOW))

    def test_past_expiry_is_not_live(self):
        self.assertFalse(is_live(make_deal(expires_at=NOW - timedelta(minutes=1)), NOW))

    def test_future_start_is_not_live_yet(self):
        self.assertFalse(is_live(make_deal(starts_at=NOW + timedelta(days=1)), NOW))

    def test_started_and_not_expired_is_live(self):
        self.assertTrue(is_live(make_deal(starts_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=1)), NOW))


class DealFilterTest(unittest.TestCase):
    def setUp(self):
        self.config = make_config()
        self.filter = DealFilter(self.config.filters)
        self.computing = self.config.categories[0]

    def test_excluded_category(self):
        self.assertTrue(self.filter.is_excluded(make_deal(category="Alcohol")))

    def test_excluded_category_used_as_tag(self):
        self.assertTrue(self.filter.is_excluded(make_deal(tags=("Pets",))))

    def test_keyword_whole_word_only(self):
        self.assertTrue(self.filter.is_excluded(make_deal(title="Red Wine 6-Pack $60 @ Dan")))
        self.assertTrue(self.filter.is_excluded(make_deal(title="Bulk Medicare rebate offer")))
        self.assertTrue(self.filter.is_excluded(make_deal(title="Premium Cat Food 2kg $9")))
        self.assertFalse(self.filter.is_excluded(make_deal(title="Petrol voucher $5 off")))
        self.assertFalse(self.filter.is_excluded(make_deal(title="Cat6 Ethernet Cable $5")))

    def test_keyword_in_tags(self):
        self.assertTrue(self.filter.is_excluded(make_deal(tags=("Pet Insurance",))))

    def test_price_cap(self):
        capped = make_config(max_price=100)
        deal_filter = DealFilter(capped.filters)
        category = capped.categories[0]
        self.assertTrue(deal_filter.keep(make_deal(price=Price(amount=99.0)), category, NOW))
        self.assertFalse(deal_filter.keep(make_deal(price=Price(amount=101.0)), category, NOW))
        self.assertTrue(deal_filter.keep(make_deal(price=Price()), category, NOW))

    def test_keep_combines_all_rules(self):
        self.assertTrue(self.filter.keep(make_deal(), self.computing, NOW))
        self.assertFalse(self.filter.keep(make_deal(flagged_expired=True), self.computing, NOW))
        self.assertFalse(self.filter.keep(make_deal(title="Wine $5"), self.computing, NOW))


if __name__ == "__main__":
    unittest.main()
