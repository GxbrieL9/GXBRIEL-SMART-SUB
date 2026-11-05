from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path


def build_validation_plan(
    cli: Path,
    subscription: Path,
    clash: Path,
    singbox: Path,
    output_dir: Path,
) -> list[tuple[str, list[str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = (subscription, clash, singbox)
    plan: list[tuple[str, list[str]]] = []
    for source in files:
        parsed = output_dir / f"{source.stem}.parsed.json"
        plan.append(("parse", [str(cli), "parse", str(source), "--disable-color", "-o", str(parsed)]))
    built = output_dir / "singbox.built.json"
    plan.append(
        (
            "build",
            [str(cli), "build", "-c", str(singbox), "--disable-color", "-o", str(built)],
        )
    )
    return plan


def validate_hiddify(
    cli: Path,
    subscription: Path,
    clash: Path,
    singbox: Path,
    output_dir: Path,
    probe: bool = False,
    probe_timeout: int = 8,
) -> None:
    for path in (cli, subscription, clash, singbox):
        if not path.exists():
            raise FileNotFoundError(path)

    for kind, command in build_validation_plan(cli, subscription, clash, singbox, output_dir):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()[-1:]
            raise RuntimeError(f"Hiddify Core {kind} failed: {' '.join(detail) or 'unknown error'}")
        print(f"Hiddify Core {kind} passed")

    if probe:
        run_command = [
            str(cli),
            "run",
            "-c",
            str(singbox),
            "--in-proxy-port",
            "12334",
            "--disable-color",
            "--log-level",
            "error",
        ]
        process = subprocess.Popen(run_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(5)
            health = subprocess.run(
                [
                    str(cli),
                    "health",
                    "--http",
                    "--proxy",
                    "socks://127.0.0.1:12334",
                    "--timeout",
                    f"{probe_timeout}s",
                    "--disable-color",
                ],
                capture_output=True,
                text=True,
                timeout=probe_timeout + 5,
                check=False,
            )
            if health.returncode != 0:
                raise RuntimeError("Hiddify Core remote connectivity probe failed")
            print("Hiddify Core remote connectivity probe passed")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated files with official Hiddify Core")
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--subscription", type=Path, required=True)
    parser.add_argument("--clash", type=Path, required=True)
    parser.add_argument("--singbox", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--probe-timeout", type=int, default=8)
    args = parser.parse_args()
    validate_hiddify(
        args.cli,
        args.subscription,
        args.clash,
        args.singbox,
        args.output_dir,
        probe=args.probe,
        probe_timeout=args.probe_timeout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
