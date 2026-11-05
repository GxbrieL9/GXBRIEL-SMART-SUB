import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from subbench.sources import (
    SourceSpec,
    _extract_v2nodes_subscription_url,
    fetch_sources,
    load_sources,
)


class DummyResponse:
    def __init__(self, text: str):
        self.content = text.encode("utf-8")
        self.encoding = "utf-8"

    def raise_for_status(self) -> None:
        return None

    def close(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.content


class SourceTests(unittest.TestCase):
    def test_priority_sources_file_is_loaded_first(self):
        tmp_dir = Path("scratch/test_priority_sources_tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        pri_file = tmp_dir / "priority_sources.txt"
        pri_file.write_text("Eternity | https://example.com/eternity\nResilience | https://example.com/resilience\n", encoding="utf-8")
        src_file = tmp_dir / "sources.txt"
        src_file.write_text("https://example.com/other\n", encoding="utf-8")

        with patch.dict("os.environ", {"SOURCE_URLS": "https://example.com/secret1"}, clear=True):
            specs = load_sources(src_file)

        self.assertEqual(len(specs), 3)
        self.assertEqual(specs[0].name, "Eternity")
        self.assertEqual(specs[0].url, "https://example.com/eternity")
        self.assertEqual(specs[1].name, "Resilience")
        self.assertEqual(specs[1].url, "https://example.com/resilience")
        self.assertEqual(specs[2].url, "https://example.com/secret1")

    def test_priority_sources_are_loaded_before_secret_sources(self):
        with patch.dict(
            "os.environ",
            {
                "PRIORITY_SOURCE_URLS": "priority-a | https://example.com/a\nhttps://example.com/b",
                "SOURCE_URLS": "https://example.com/secret-a\nhttps://example.com/a",
            },
            clear=True,
        ):
            specs = load_sources(__import__("pathlib").Path("missing-sources.txt"))

        self.assertEqual([spec.url for spec in specs], [
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/secret-a",
        ])
        self.assertEqual([spec.name for spec in specs[:2]], ["priority-a", "priority-02"])

    def test_extracts_v2nodes_subscription_from_landing_page(self):
        url = "https://www.v2nodes.com/subscriptions/country/all/?key=ABC123"
        document = f'<input data-config="{url}" value="{url}">'
        self.assertEqual(_extract_v2nodes_subscription_url(document), url)

    def test_v2nodes_landing_page_resolves_current_key_before_download(self):
        subscription_url = (
            "https://www.v2nodes.com/subscriptions/country/all/?key=ABC123"
        )
        responses = [
            DummyResponse(f'<input value="{subscription_url}">'),
            DummyResponse("vless://example"),
        ]
        with patch("subbench.sources.requests.get", side_effect=responses) as requester:
            results = fetch_sources(
                [SourceSpec(name="V2Nodes", url="https://www.v2nodes.com/")],
                workers=1,
            )

        self.assertEqual(results[0].text, "vless://example")
        self.assertIsNone(results[0].error)
        self.assertEqual(requester.call_count, 2)
        self.assertEqual(requester.call_args_list[1].args[0], subscription_url)

    def test_v2nodes_missing_subscription_link_is_reported(self):
        with patch(
            "subbench.sources.requests.get",
            return_value=DummyResponse("<html>No subscription here</html>"),
        ) as requester:
            results = fetch_sources(
                [SourceSpec(name="V2Nodes", url="https://www.v2nodes.com/")],
                workers=1,
            )

        self.assertIsNone(results[0].text)
        self.assertIn("did not contain a subscription link", results[0].error or "")
        self.assertEqual(requester.call_count, 1)

    def test_retries_transient_source_failures(self):
        responses = [requests.Timeout("temporary timeout"), DummyResponse("vless://example")]
        with patch("subbench.sources.requests.get", side_effect=responses) as requester:
            results = fetch_sources(
                [SourceSpec(name="retry-source", url="https://example.com/source")],
                workers=1,
                retries=1,
                retry_backoff_seconds=0,
            )

        self.assertEqual(results[0].text, "vless://example")
        self.assertIsNone(results[0].error)
        self.assertEqual(requester.call_count, 2)

    def test_fetch_sources_redacts_urls_in_error_messages(self):
        with patch("subbench.sources.requests.get", side_effect=requests.RequestException("Failed connecting to https://secret-token.com/sub?key=12345")):
            results = fetch_sources(
                [SourceSpec(name="source-01", url="https://secret-token.com/sub?key=12345")],
                workers=1,
                retries=0,
            )
        self.assertNotIn("https://secret-token.com", results[0].error or "")
        self.assertIn("[REDACTED_URL]", results[0].error or "")


if __name__ == "__main__":
    unittest.main()
