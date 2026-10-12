import unittest

from dealbot.pricing import parse_price


class ParsePriceTest(unittest.TestCase):
    """Titles are real OzBargain deal titles seen on 2026-10-12."""

    def check(self, title, amount, unit=None, was=None, discount=None, free=False):
        price = parse_price(title)
        self.assertEqual(
            (price.amount, price.unit, price.was, price.discount_pct, price.is_free),
            (amount, unit, was, discount, free),
            title,
        )

    def test_simple_price_ignores_delivery_add_on(self):
        self.check("BIWIN NV3500 1TB SSD $159, BIWIN M350 $89 + Delivery ($0 C&C) @ Centre Com", 159.0)

    def test_rrp_gives_was_price_and_discount(self):
        self.check("AMD Ryzen 7 9800X3D $581.99 (RRP $821) Delivered @ Amazon DE via AU",
                   581.99, was=821.0, discount=29)

    def test_was_price_in_brackets(self):
        self.check("Collapsible Pop Up Laundry Airer $15 (Was $39) + $10 Delivery ($0 C&C/ In Store) @ Kmart",
                   15.0, was=39.0, discount=62)

    def test_thousands_separator(self):
        self.check("Samsung Galaxy S25 Ultra (256GB) $1,499 (+20% TCB) @ Samsung via Woolworths", 1499.0)

    def test_monthly_plan_unit(self):
        self.check("nbn FTTP or HFC 500/50 $82/M Carbon Network, $84/M ABB @ Carbon Comms", 82.0, unit="month")
        self.check("nbn 25/10 $30/Month for 6 Months @ amaysim", 30.0, unit="month")

    def test_foreign_currency_skipped_in_favour_of_aud(self):
        self.check("Adguard Family Plan (Lifetime) US$11 (~A$16) + 10% GST @ StackSocial", 16.0)

    def test_free_titles(self):
        self.check("[PC] Free - Pony Island @ Steam", 0.0, free=True)
        self.check("[Free] Office Application Softwares", 0.0, free=True)

    def test_free_delivery_is_not_a_free_deal(self):
        self.check("Dash Cam $524 + Free Express Post @ Dash Cams Australia", 524.0)

    def test_discount_amount_is_not_a_price(self):
        self.check("Get $120 off over 12 months On Telstra Upfront Basic Mobile Plan.", None)
        self.check("[Perks] $10 Voucher on Your Birthday Month @ JB Hi-Fi", None)

    def test_spend_threshold_is_not_a_price(self):
        self.check("Everyday Market: 20% Cashback on $150.01+ Spend (Uncapped) @ TopCashback AU", None)

    def test_percent_off_without_price(self):
        self.check("15% off TCN Cinema Gift Cards (Digital or Physical) + $2.95 Physical Delivery @ Card.Gift",
                   None, discount=15)

    def test_half_price(self):
        self.check("[PC, Steam] Arc Raiders Free-To-Play on Steam, 1/2 Price $28.99 until 16 Oct @ Steam",
                   28.99, discount=50)

    def test_real_price_beats_the_word_free(self):
        self.check("Free Upgrade to 1TB SSD with Laptop $1,299 @ Dell", 1299.0)

    def test_free_postage_is_not_a_free_deal(self):
        self.check("Free Shipping Sitewide @ Store", None)
        self.check("Free Delivery on $50+ Orders @ Store", None)

    def test_skip_words_need_a_word_boundary(self):
        self.check("Microsoft 365 Family $99 Office Bundle @ Store", 99.0)
        self.check("Kindle $99 Offer Ends Sunday @ Amazon AU", 99.0)
        self.check("Osprey $49 Backpack, Osprey $89 Daypack @ Store", 49.0)

    def test_au_dollar_prefix(self):
        self.check("Game AU$29 (RRP AU$59) @ Store", 29.0, was=59.0, discount=51)

    def test_price_range_takes_lowest(self):
        self.check("Bacon Deluxe, Whopper or Jack's Fried Chicken Burger $4-$6 @ Hungry Jack's via App", 4.0)


if __name__ == "__main__":
    unittest.main()
