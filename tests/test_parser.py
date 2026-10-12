import unittest
from datetime import datetime

from dealbot.parser import FeedError, parse_feed
from tests.helpers import AEDT, BASE_URL, fixture


class ParseFeedTest(unittest.TestCase):
    def setUp(self):
        self.deals = {d.id: d for d in parse_feed(fixture("computing_feed.xml"), BASE_URL)}

    def test_parses_every_item(self):
        self.assertEqual(set(self.deals), {"978561", "978464", "978414", "978189", "977686"})

    def test_fields_from_meta_and_categories(self):
        cpu = self.deals["977686"]
        self.assertEqual(cpu.url, f"{BASE_URL}/node/977686")
        self.assertEqual(cpu.category, "Computing")
        self.assertEqual(cpu.tags, ("AMD", "AMD Ryzen 7 9800X3D", "CPU"))
        self.assertEqual(cpu.products, ("amd-ryzen-7-9800x3d",))
        self.assertEqual((cpu.votes_pos, cpu.votes_neg, cpu.comments), (36, 0, 35))
        self.assertEqual(cpu.price.amount, 581.99)
        self.assertEqual(cpu.posted_at, datetime(2026, 10, 4, 18, 21, 6, tzinfo=AEDT))
        self.assertIsNone(cpu.expires_at)

    def test_expired_flag_and_dates(self):
        dock = self.deals["978189"]
        self.assertTrue(dock.flagged_expired)
        self.assertEqual(dock.starts_at, datetime(2026, 10, 8, tzinfo=AEDT))
        self.assertFalse(self.deals["978464"].flagged_expired)

    def test_long_running_flag(self):
        deals = {d.id: d for d in parse_feed(fixture("internet_feed.xml"), BASE_URL)}
        self.assertTrue(deals["971220"].long_running)
        self.assertFalse(deals["971220"].flagged_expired)

    def test_xml_entities_are_decoded(self):
        self.assertIn("($0 C&C)", self.deals["978464"].title)

    def test_rejects_non_xml(self):
        with self.assertRaises(FeedError):
            parse_feed(b"<html>not a feed", BASE_URL)

    def test_rejects_entity_expansion_attack(self):
        bomb = b"""<?xml version="1.0"?>
        <!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>
        <rss><channel><title>&lol2;</title></channel></rss>"""
        with self.assertRaises(FeedError):
            parse_feed(bomb, BASE_URL)

    def test_skips_items_with_off_site_links(self):
        xml = fixture("computing_feed.xml").replace(
            b"<link>https://www.ozbargain.com.au/node/978561</link>",
            b"<link>https://evil.example/node/978561</link>",
        )
        ids = {d.id for d in parse_feed(xml, BASE_URL)}
        self.assertNotIn("978561", ids)
        self.assertEqual(len(ids), 4)

    def test_skips_items_with_dates_lacking_a_timezone(self):
        xml = fixture("computing_feed.xml").replace(
            b'expiry="2026-10-13T00:00:00+11:00"', b'expiry="2026-10-13T00:00:00"'
        )
        ids = {d.id for d in parse_feed(xml, BASE_URL)}
        self.assertNotIn("978464", ids)
        self.assertEqual(len(ids), 4)

    def test_drops_images_from_other_hosts(self):
        xml = fixture("computing_feed.xml").replace(
            b'image="https://files.ozbargain.com.au/n/86/977686l.jpg?h=fe7c36f4"',
            b'image="javascript:alert(1)"',
        )
        deals = {d.id: d for d in parse_feed(xml, BASE_URL)}
        self.assertIsNone(deals["977686"].image)


if __name__ == "__main__":
    unittest.main()
