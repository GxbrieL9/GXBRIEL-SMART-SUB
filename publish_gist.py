from __future__ import annotations

import argparse
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


def should_publish(node_count: int, previous: str) -> bool:
    return node_count > 0 and bool(previous.strip())


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


def publish(gist_id: str, token: str, content: str, report_path: Path | None = None, raw_content: str = "") -> None:
    gist_url = f"https://api.github.com/gists/{gist_id}"
    gist = _request(gist_url, token)
    previous_file = gist.get("files", {}).get("subscription.txt", {})
    previous = str(previous_file.get("content", ""))

    node_lines = [line for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    node_count = len(node_lines)

    if not should_publish(node_count, previous):
        print("Notice: No nodes to publish or empty content. Preserving existing Gist content.")
        return

    fast_count = 0
    if report_path and report_path.exists():
        try:
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            nodes = report_data.get("nodes", [])
            fast_count = sum(1 for n in nodes if (n.get("speed_mbps") or 0) >= 24.0)
        except Exception:
            pass

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    description = f"GXBRIEL SMART SUB — Updated {now_iso} | {node_count} nodes ({fast_count} >= 24 Mbps)"

    import base64
    b64_content = base64.b64encode(content.encode("utf-8")).decode("ascii") + "\n"

    files_payload: dict[str, dict[str, str]] = {
        "subscription.txt": {"content": content},
        "subscription-b64.txt": {"content": b64_content},
    }
    if raw_content and raw_content != content:
        files_payload["subscription-raw.txt"] = {"content": raw_content}

    _request(gist_url, token, "PATCH", {
        "description": description,
        "files": files_payload,
    })

    owner = gist.get("owner", {}).get("login", "GxbrieL9")
    raw_url = f"https://gist.githubusercontent.com/{owner}/{gist_id}/raw/subscription.txt"

    print("=" * 60)
    print("✓ GIST SUCCESSFULLY UPDATED!")
    print(f"  Description: {description}")
    print(f"  Total nodes: {node_count}")
    print(f"  Fast nodes (>= 24 Mbps / 3 MB/s): {fast_count}")
    print(f"  PERMANENT KARING URL: {raw_url}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish subscription to GitHub Gist")
    parser.add_argument("--raw", type=Path, help="Path to raw subscription file")
    parser.add_argument("--subscription", type=Path, help="Path to subscription file")
    parser.add_argument("--report", type=Path, default=Path("public/report.json"), help="Path to report.json")
    args = parser.parse_args()

    gist_id = os.environ.get("GIST_ID", "").strip()
    token = os.environ.get("GIST_TOKEN", "").strip()
    if not gist_id or not token:
        raise RuntimeError("GIST_ID and GIST_TOKEN must be provided by GitHub Actions.")

    content = ""
    raw_content = ""
    if args.raw and args.raw.exists():
        content = build_subscription(args.raw)
        raw_content = content
    elif args.subscription and args.subscription.exists():
        content = args.subscription.read_text(encoding="utf-8").strip() + "\n"

    publish(gist_id, token, content, report_path=args.report, raw_content=raw_content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
