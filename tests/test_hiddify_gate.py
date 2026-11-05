import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from scripts.validate_hiddify import build_validation_plan, _sanitize_log, validate_hiddify


def test_validation_plan_checks_all_published_formats_and_builds_singbox(tmp_path: Path) -> None:
    plan = build_validation_plan(
        cli=Path(".bin/HiddifyCli"),
        subscription=tmp_path / "subscription.txt",
        clash=tmp_path / "clash.yaml",
        singbox=tmp_path / "singbox.json",
        output_dir=tmp_path / "hiddify-check",
    )

    # 3 formats, each has its own parse and its own build
    assert [item[0] for item in plan] == ["parse", "build", "parse", "build", "parse", "build"]
    
    # subscription: parse source -> build parsed output
    assert plan[0][1][2].endswith("subscription.txt")
    assert plan[0][1][-1].endswith("subscription.parsed.json")
    assert plan[1][1][3].endswith("subscription.parsed.json")
    assert plan[1][1][-1].endswith("subscription.built.json")

    # clash: parse source -> build parsed output
    assert plan[2][1][2].endswith("clash.yaml")
    assert plan[2][1][-1].endswith("clash.parsed.json")
    assert plan[3][1][3].endswith("clash.parsed.json")
    assert plan[3][1][-1].endswith("clash.built.json")

    # singbox: parse source -> build parsed output
    assert plan[4][1][2].endswith("singbox.json")
    assert plan[4][1][-1].endswith("singbox.parsed.json")
    assert plan[5][1][3].endswith("singbox.parsed.json")
    assert plan[5][1][-1].endswith("singbox.built.json")


def test_validation_plan_never_prints_file_contents(tmp_path: Path) -> None:
    plan = build_validation_plan(
        cli=Path(".bin/HiddifyCli"),
        subscription=tmp_path / "subscription.txt",
        clash=tmp_path / "clash.yaml",
        singbox=tmp_path / "singbox.json",
        output_dir=tmp_path / "hiddify-check",
    )

    for _, command in plan:
        assert "--disable-color" in command
        assert "--log-level" not in command


def test_sanitize_log_redacts_sensitive_values() -> None:
    sample = "Failed to parse vless://b8a2c4e6-1234-5678-90ab-cdef12345678@example.com:443 from https://secret.link/sub"
    sanitized = _sanitize_log(sample)
    assert "[REDACTED_UUID]" in sanitized
    assert "b8a2c4e6-1234-5678-90ab-cdef12345678" not in sanitized
    assert "[REDACTED_URL]" in sanitized
    assert "https://secret.link/sub" not in sanitized


def test_validate_hiddify_catches_empty_outbounds(tmp_path: Path) -> None:
    cli = tmp_path / "HiddifyCli"
    cli.touch()
    sub = tmp_path / "subscription.txt"
    sub.touch()
    clash = tmp_path / "clash.yaml"
    clash.touch()
    singbox = tmp_path / "singbox.json"
    singbox.touch()
    out_dir = tmp_path / "out"

    # Mock subprocess.run to succeed, but write empty outbounds
    def fake_run(cmd, **kwargs):
        out_file = Path(cmd[-1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({"outbounds": []}, f)
        mock = MagicMock()
        mock.returncode = 0
        return mock

    with patch("subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="zero outbounds"):
            validate_hiddify(cli, sub, clash, singbox, out_dir, probe=False)
