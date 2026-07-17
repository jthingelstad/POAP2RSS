import os
import unittest
from xml.etree.ElementTree import fromstring

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

from src.poap2rss_lambda import CacheManager, RSSFeedGenerator, lambda_handler


class FakePOAPClient:
    def get_event_details(self, event_id):
        return {
            "id": event_id,
            "name": "Test Event",
            "description": "A test POAP event",
            "image_url": "https://example.com/poap.png",
            "start_date": "2026-07-01T12:00:00Z",
        }

    def get_event_poaps(self, _event_id):
        return [
            {
                "id": "42",
                "created": "2026-07-02T12:00:00Z",
                "owner": {"id": "0x1234567890", "ens": "collector.eth"},
            }
        ]


class POAP2RSSTests(unittest.TestCase):
    def test_cache_key_is_stable(self):
        self.assertEqual(CacheManager.get_cache_key("event", "123"), "event:123")

    def test_invalid_path_returns_client_error(self):
        response = lambda_handler({"path": "/event", "headers": {}}, None)

        self.assertEqual(response["statusCode"], 400)

    def test_event_feed_is_valid_rss(self):
        xml = RSSFeedGenerator(FakePOAPClient()).generate_event_feed(
            123, suppress_inactivity_alert=True
        )
        root = fromstring(xml)

        self.assertEqual(root.tag, "rss")
        self.assertEqual(root.findtext("channel/title"), "POAP: Test Event")
        self.assertEqual(len(root.findall("channel/item")), 2)


if __name__ == "__main__":
    unittest.main()
