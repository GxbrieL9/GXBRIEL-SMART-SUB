from pathlib import Path

from scripts.validate_hiddify import build_validation_plan


def test_validation_plan_checks_all_published_formats_and_builds_singbox(tmp_path: Path) -> None:
    plan = build_validation_plan(
        cli=Path(".bin/HiddifyCli"),
        subscription=tmp_path / "subscription.txt",
        clash=tmp_path / "clash.yaml",
        singbox=tmp_path / "singbox.json",
        output_dir=tmp_path / "hiddify-check",
    )

    assert [item[0] for item in plan] == ["parse", "parse", "parse", "build"]
    assert plan[0][1][2].endswith("subscription.txt")
    assert plan[1][1][2].endswith("clash.yaml")
    assert plan[2][1][2].endswith("singbox.json")
    assert plan[3][1][3].endswith("singbox.json")


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
