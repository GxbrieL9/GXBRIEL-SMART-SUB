from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
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
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def publish(gist_id: str, token: str, content: str) -> None:
    gist_url = f"https://api.github.com/gists/{gist_id}"
    gist = _request(gist_url, token)
    previous_file = gist.get("files", {}).get("subscription.txt", {})
    previous = str(previous_file.get("content", ""))
    if not should_publish(content.count("\n"), content):
        raise RuntimeError("Refusing to replace the Gist with an empty subscription.")
    _request(gist_url, token, "PATCH", {"files": {"subscription.txt": {"content": content}}})
    print(f"Updated subscription.txt in configured Gist ({len(content.splitlines())} nodes).")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    gist_id = os.environ.get("GIST_ID", "").strip()
    token = os.environ.get("GIST_TOKEN", "").strip()
    if not gist_id or not token:
        raise RuntimeError("GIST_ID and GIST_TOKEN must be provided by GitHub Actions.")
    publish(gist_id, token, build_subscription(args.raw))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
