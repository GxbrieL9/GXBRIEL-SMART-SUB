from pathlib import Path

from publish_gist import build_subscription, should_publish


def test_subscription_is_raw_karing_uris(tmp_path: Path) -> None:
    raw = tmp_path / "v2ray-raw.txt"
    raw.write_text("vless://example\n\n# ignored\n", encoding="utf-8")

    assert build_subscription(raw) == "vless://example\n"


def test_empty_result_keeps_previous_gist() -> None:
    assert should_publish(node_count=0, previous="# previous\n") is False
    assert should_publish(node_count=1, previous="# previous\n") is True
