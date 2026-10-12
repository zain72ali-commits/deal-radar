import unittest

from dealbot.models import Price
from dealbot.scoring import EARLY, MIXED, POSITIVE, STRONG, compare_to_history, record_price, verdict
from tests.helpers import make_config, make_deal


class VerdictTest(unittest.TestCase):
    def setUp(self):
        self.settings = make_config().scoring

    def test_verdicts(self):
        self.assertEqual(verdict(make_deal(votes_pos=5, votes_neg=1), self.settings), EARLY)
        self.assertEqual(verdict(make_deal(votes_pos=30, votes_neg=10), self.settings), MIXED)
        self.assertEqual(verdict(make_deal(votes_pos=85, votes_neg=15), self.settings), MIXED)  # exactly 15%
        self.assertEqual(verdict(make_deal(votes_pos=41, votes_neg=7), self.settings), POSITIVE)  # 14.6%
        self.assertEqual(verdict(make_deal(votes_pos=83, votes_neg=0), self.settings), STRONG)
        self.assertEqual(verdict(make_deal(votes_pos=36, votes_neg=0), self.settings), POSITIVE)


class PriceHistoryTest(unittest.TestCase):
    def test_new_low_then_above_low(self):
        history = {}
        first = make_deal(id="1", products=("kingston-nv2",), price=Price(amount=159.0))
        self.assertIsNone(compare_to_history(first, history))
        record_price(first, history, "2026-10-01T00:00:00+00:00")

        cheaper = make_deal(id="2", products=("kingston-nv2",), price=Price(amount=149.0))
        self.assertEqual(compare_to_history(cheaper, history)["status"], "new_low")
        record_price(cheaper, history, "2026-10-05T00:00:00+00:00")

        dearer = make_deal(id="3", products=("kingston-nv2",), price=Price(amount=170.0))
        result = compare_to_history(dearer, history)
        self.assertEqual(result, {
            "status": "above_low",
            "previous_low": 149.0,
            "previous_low_date": "2026-10-05T00:00:00+00:00",
        })

    def test_bundles_and_unpriced_are_ignored(self):
        history = {}
        record_price(make_deal(products=("a", "b")), history, "t")
        record_price(make_deal(products=("a",), price=Price()), history, "t")
        self.assertEqual(history, {})

    def test_different_units_are_not_compared(self):
        history = {}
        record_price(make_deal(id="1", products=("plan",), price=Price(amount=60.0, unit="month")), history, "t")
        one_off = make_deal(id="2", products=("plan",), price=Price(amount=500.0))
        self.assertIsNone(compare_to_history(one_off, history))


if __name__ == "__main__":
    unittest.main()
