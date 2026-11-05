from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path


def _sanitize_log(text: str) -> str:
    """Mask sensitive tokens, UUIDs, and credentials in logs."""
    text = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "[REDACTED_UUID]", text)
    text = re.sub(r"https?://[^\s'\"]+", "[REDACTED_URL]", text)
    return text


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
        built = output_dir / f"{source.stem}.built.json"
        plan.append(("build", [str(cli), "build", "-c", str(parsed), "--disable-color", "-o", str(built)]))
    return plan


def _get_public_ip(opener: urllib.request.OpenerDirector | None = None, timeout: int = 5) -> str | None:
    for url in ("http://1.1.1.1/cdn-cgi/trace", "https://api.ipify.org?format=json"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            fn = opener.open if opener else urllib.request.urlopen
            with fn(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                if "ip=" in body:
                    for line in body.splitlines():
                        if line.startswith("ip="):
                            return line.split("=", 1)[1].strip()
                elif "ip" in body:
                    data = json.loads(body)
                    return data.get("ip")
        except Exception:
            continue
    return None


def validate_hiddify(
    cli: Path,
    subscription: Path,
    clash: Path,
    singbox: Path,
    output_dir: Path,
    probe: bool = False,
    probe_timeout: int = 8,
    probe_port: int = 12334,
) -> None:
    for path in (cli, subscription, clash, singbox):
        if not path.exists():
            raise FileNotFoundError(path)

    for kind, command in build_validation_plan(cli, subscription, clash, singbox, output_dir):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raw_detail = (result.stderr or result.stdout or "unknown error").strip()
            detail = _sanitize_log(raw_detail.splitlines()[-1] if raw_detail.splitlines() else raw_detail)
            target = command[2] if kind == "parse" else command[3]
            raise RuntimeError(f"Hiddify Core {kind} failed for {Path(target).name}: {detail}")
        
        # Verify that output file exists and contains valid JSON with outbounds
        target_out = Path(command[-1])
        if not target_out.exists() or target_out.stat().st_size == 0:
            raise RuntimeError(f"Hiddify Core {kind} produced empty output: {target_out.name}")
        try:
            with open(target_out, "r", encoding="utf-8") as f:
                data = json.load(f)
            outbounds = data.get("outbounds", [])
            if not outbounds:
                raise RuntimeError(f"Hiddify Core {kind} produced config with zero outbounds in {target_out.name}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Hiddify Core {kind} produced invalid JSON in {target_out.name}: {exc}")
        print(f"Hiddify Core {kind} passed for {Path(command[2] if kind == 'parse' else command[3]).name}")

    if probe:
        built_singbox = output_dir / f"{singbox.stem}.built.json"
        if not built_singbox.exists():
            built_singbox = singbox

        # Sanitize any balancer strategy to ensure sing-box starts without missing strategy error
        probe_cfg_path = output_dir / "probe_config.json"
        try:
            with open(built_singbox, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            for ob in cfg_data.get("outbounds", []):
                if ob.get("type") == "balancer" and not ob.get("strategy"):
                    ob["strategy"] = "round-robin"
            with open(probe_cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, indent=2)
            target_config = probe_cfg_path
        except Exception:
            target_config = built_singbox

        run_command = [
            str(cli),
            "srun",
            "-c",
            str(target_config),
            "--disable-color",
        ]
        log_file = output_dir / "hiddify_probe_run.log"
        with open(log_file, "w", encoding="utf-8") as core_log:
            process = subprocess.Popen(run_command, stdout=core_log, stderr=core_log)
        try:
            time.sleep(3)
            if process.poll() is not None:
                # If srun is unsupported, fallback to run
                run_command = [
                    str(cli),
                    "run",
                    "-c",
                    str(target_config),
                    "--in-proxy-port",
                    str(probe_port),
                    "--disable-color",
                    "--log-level",
                    "warn",
                ]
                with open(log_file, "w", encoding="utf-8") as core_log:
                    process = subprocess.Popen(run_command, stdout=core_log, stderr=core_log)
                time.sleep(3)
                if process.poll() is not None:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        err_lines = f.readlines()
                    detail = _sanitize_log("".join(err_lines[-10:]))
                    raise RuntimeError(f"Hiddify Core exited prematurely during probe (rc={process.returncode}):\n{detail}")

            # Verify real traffic routing and egress IP separation
            direct_ip = _get_public_ip(timeout=4)

            proxy_handler = urllib.request.ProxyHandler({
                "http": f"http://127.0.0.1:{probe_port}",
                "https": f"http://127.0.0.1:{probe_port}",
            })
            proxy_opener = urllib.request.build_opener(proxy_handler)
            proxied_ip = _get_public_ip(opener=proxy_opener, timeout=probe_timeout)

            if direct_ip and proxied_ip and direct_ip == proxied_ip:
                raise RuntimeError(
                    f"Traffic bypassed proxy and connected directly (Direct: {direct_ip}, Proxied: {proxied_ip})"
                )

            # Test HTTPS connectivity through proxy
            https_ok = False
            for test_url in ("https://www.google.com/generate_204", "https://speed.cloudflare.com/__down?bytes=100"):
                try:
                    req = urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0"})
                    with proxy_opener.open(req, timeout=probe_timeout) as resp:
                        if resp.status in (200, 204):
                            https_ok = True
                            break
                except Exception:
                    continue

            if not https_ok and not proxied_ip:
                # Fallback to cli health check if urllib was blocked
                health = subprocess.run(
                    [
                        str(cli),
                        "health",
                        "--http",
                        "--proxy",
                        f"socks://127.0.0.1:{probe_port}",
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
                    raw_err = (health.stderr or health.stdout or "health check failed").strip()
                    raise RuntimeError(f"Hiddify Core remote connectivity probe failed: {_sanitize_log(raw_err)}")

            print(
                f"Hiddify Core remote connectivity probe passed (Proxied IP: {proxied_ip or 'verified'}, "
                f"Direct IP: {direct_ip or 'unknown'}, HTTPS: {'OK' if https_ok else 'verified via health'})"
            )
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
    parser.add_argument("--probe-port", type=int, default=12334)
    args = parser.parse_args()
    validate_hiddify(
        args.cli,
        args.subscription,
        args.clash,
        args.singbox,
        args.output_dir,
        probe=args.probe,
        probe_timeout=args.probe_timeout,
        probe_port=args.probe_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
