from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def build_subscription(raw_path: Path) -> str:
    lines = [line.strip() for line in raw_path.read_text(encoding="utf-8").splitlines()]
    return "".join(f"{line}\n" for line in lines if line and not line.startswith("#"))


def get_permanent_raw_url(owner: str, gist_id: str, filename: str) -> str:
    """Return permanent GitHub Gist raw URL without commit hash."""
    return f"https://gist.githubusercontent.com/{owner}/{gist_id}/raw/{filename}"


def should_publish(
    node_count: int,
    previous: str = "",
    files: dict[str, str] | None = None,
) -> bool:
    if node_count <= 0:
        return False
    if previous and not bool(previous.strip()):
        return False
    if files is not None:
        if not files:
            return False
        for filename, content in files.items():
            if not content or not content.strip():
                return False
    return True


def prepare_gist_files(
    subscription_path: Path | None = None,
    clash_path: Path | None = None,
    singbox_path: Path | None = None,
    raw_path: Path | None = None,
) -> dict[str, dict[str, str]]:
    files_payload: dict[str, dict[str, str]] = {}

    if subscription_path and subscription_path.exists():
        content = subscription_path.read_text(encoding="utf-8").strip()
        if content:
            files_payload["subscription.txt"] = {"content": content + "\n"}

    if clash_path and clash_path.exists():
        clash_content = clash_path.read_text(encoding="utf-8").strip()
        if clash_content:
            files_payload["clash.yaml"] = {"content": clash_content + "\n"}

    if singbox_path and singbox_path.exists():
        singbox_content = singbox_path.read_text(encoding="utf-8").strip()
        if singbox_content:
            files_payload["singbox.json"] = {"content": singbox_content + "\n"}

    if raw_path and raw_path.exists():
        raw_content = raw_path.read_text(encoding="utf-8").strip()
        if raw_content:
            files_payload["subscription-raw.txt"] = {"content": raw_content + "\n"}

    return files_payload


def _request(url: str, token: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("User-Agent", "GXBRIEL-SMART-SUB")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")

    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"Request to {url} attempt {attempt}/{max_attempts} failed: HTTP {e.code} - {error_body}")
            if e.code in (401, 403, 404):
                raise
        except Exception as e:
            print(f"Request to {url} attempt {attempt}/{max_attempts} failed: {e}")
        if attempt < max_attempts:
            time.sleep(attempt * 2)

    raise RuntimeError(f"Request to {url} failed after {max_attempts} attempts.")


def publish(
    gist_id: str,
    token: str,
    files_payload: dict[str, dict[str, str]],
    report_path: Path | None = None,
    node_count: int | None = None,
) -> None:
    gist_url = f"https://api.github.com/gists/{gist_id}"
    gist = _request(gist_url, token)
    owner = gist.get("owner", {}).get("login", "GxbrieL9")

    # Read stats from report if available
    fast_count = 0
    actual_node_count = node_count or 0
    if report_path and report_path.exists():
        try:
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            actual_node_count = actual_node_count or report_data.get("node_count", 0)
            nodes = report_data.get("nodes", [])
            fast_count = sum(1 for n in nodes if (n.get("speed_mbps") or 0) >= 24.0)
        except Exception:
            pass

    if actual_node_count == 0 and "subscription.txt" in files_payload:
        sub_content = files_payload["subscription.txt"]["content"]
        # Try decoding base64 if needed
        try:
            decoded = base64.b64decode(sub_content).decode("utf-8", errors="ignore")
            actual_node_count = len([line for line in decoded.splitlines() if line.strip() and not line.strip().startswith("#")])
        except Exception:
            actual_node_count = len([line for line in sub_content.splitlines() if line.strip() and not line.strip().startswith("#")])

    files_content_map = {k: v["content"] for k, v in files_payload.items()}
    if not should_publish(actual_node_count, files=files_content_map):
        print("Notice: No nodes to publish or files are empty. Preserving existing Gist content.")
        return

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    description = (
        f"GXBRIEL SMART SUB — Universal Multi-Format | "
        f"Updated {now_iso} | {actual_node_count} nodes ({fast_count} >= 3 MB/s)"
    )

    _request(gist_url, token, "PATCH", {
        "description": description,
        "files": files_payload,
    })

    sub_raw_url = get_permanent_raw_url(owner, gist_id, "subscription.txt")
    clash_raw_url = get_permanent_raw_url(owner, gist_id, "clash.yaml")
    singbox_raw_url = get_permanent_raw_url(owner, gist_id, "singbox.json")

    print("=" * 68)
    print("✓ GIST SUCCESSFULLY UPDATED WITH UNIVERSAL SUBSCRIPTION FORMATS!")
    print(f"  Description: {description}")
    print(f"  Total nodes: {actual_node_count}")
    print(f"  Fast nodes (>= 3 MB/s / 24 Mbps): {fast_count}")
    print()
    print("  PERMANENT RAW LINKS (NO REVISION PINNING):")
    print(f"  1. V2Ray / Base64 : {sub_raw_url}")
    print(f"  2. Mihomo / Clash : {clash_raw_url}")
    print(f"  3. sing-box       : {singbox_raw_url}")
    print("=" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish universal subscription formats to GitHub Gist")
    parser.add_argument("--subscription", type=Path, default=Path("public/subscription.txt"), help="Path to subscription.txt")
    parser.add_argument("--clash", type=Path, default=Path("public/clash.yaml"), help="Path to clash.yaml")
    parser.add_argument("--singbox", type=Path, default=Path("public/singbox.json"), help="Path to singbox.json")
    parser.add_argument("--raw-subscription", type=Path, default=Path("public/subscription-raw.txt"), help="Path to raw subscription")
    parser.add_argument("--raw", type=Path, help="Legacy: path to raw subscription")
    parser.add_argument("--report", type=Path, default=Path("public/report.json"), help="Path to report.json")
    args = parser.parse_args()

    gist_id = os.environ.get("GIST_ID", "").strip()
    token = os.environ.get("GIST_TOKEN", "").strip()
    if not gist_id or not token:
        raise RuntimeError("GIST_ID and GIST_TOKEN must be provided by GitHub Actions.")

    raw_path = args.raw if args.raw and args.raw.exists() else args.raw_subscription

    files_payload = prepare_gist_files(
        subscription_path=args.subscription,
        clash_path=args.clash,
        singbox_path=args.singbox,
        raw_path=raw_path,
    )

    if not files_payload and args.raw and args.raw.exists():
        raw_sub = build_subscription(args.raw)
        b64_sub = base64.b64encode(raw_sub.encode("utf-8")).decode("ascii") + "\n"
        files_payload["subscription.txt"] = {"content": b64_sub}
        files_payload["subscription-raw.txt"] = {"content": raw_sub}

    publish(gist_id, token, files_payload, report_path=args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
