from pathlib import Path

from publish_gist import (
    build_subscription,
    get_permanent_raw_url,
    prepare_gist_files,
    should_publish,
)


def test_subscription_is_raw_karing_uris(tmp_path: Path) -> None:
    raw = tmp_path / "v2ray-raw.txt"
    raw.write_text("vless://example\n\n# ignored\n", encoding="utf-8")

    assert build_subscription(raw) == "vless://example\n"


def test_empty_result_keeps_previous_gist() -> None:
    assert should_publish(node_count=0, previous="# previous\n") is False
    assert should_publish(node_count=1, previous="# previous\n") is True


def test_should_publish_validates_files_payload() -> None:
    valid_files = {
        "subscription.txt": "dm1lc3M6Ly9leGFtcGxl",
        "clash.yaml": "proxies:\n  - name: test",
        "singbox.json": '{"outbounds": []}',
    }
    assert should_publish(node_count=5, files=valid_files) is True
    assert should_publish(node_count=0, files=valid_files) is False
    assert should_publish(node_count=5, files={"subscription.txt": ""}) is False


def test_get_permanent_raw_url() -> None:
    url = get_permanent_raw_url(owner="GxbrieL9", gist_id="abc123gist", filename="clash.yaml")
    assert url == "https://gist.githubusercontent.com/GxbrieL9/abc123gist/raw/clash.yaml"
    # Ensure no commit hash is in the URL
    assert "/raw/clash.yaml" in url
    assert url.count("/") == 6


def test_prepare_gist_files_reads_all_formats(tmp_path: Path) -> None:
    sub = tmp_path / "subscription.txt"
    sub.write_text("base64data\n", encoding="utf-8")
    clash = tmp_path / "clash.yaml"
    clash.write_text("proxies:\n", encoding="utf-8")
    sb = tmp_path / "singbox.json"
    sb.write_text('{"outbounds":[]}\n', encoding="utf-8")

    files = prepare_gist_files(
        subscription_path=sub,
        clash_path=clash,
        singbox_path=sb,
    )
    assert "subscription.txt" in files
    assert "clash.yaml" in files
    assert "singbox.json" in files
    assert files["subscription.txt"]["content"] == "base64data\n"
    assert files["clash.yaml"]["content"] == "proxies:\n"
    assert files["singbox.json"]["content"] == '{"outbounds":[]}\n'

