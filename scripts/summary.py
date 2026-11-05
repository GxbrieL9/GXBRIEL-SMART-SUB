from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def generate_summary() -> int:
    report_path = Path("public/report.json")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")

    if not report_path.exists():
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("No report.json found.\n")
        return 0

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read report.json: {e}", file=sys.stderr)
        return 0

    node_count = report.get("node_count", 0)
    nodes = report.get("nodes", [])
    fast_nodes = sum(1 for n in nodes if (n.get("speed_mbps") or 0) >= 24.0)

    countries: dict[str, int] = {}
    protocols: dict[str, int] = {}
    for n in nodes:
        cc = str(n.get("country_code") or "UN").upper()
        proto = str(n.get("type") or n.get("scheme") or "UNKNOWN").upper()
        countries[cc] = countries.get(cc, 0) + 1
        protocols[proto] = protocols.get(proto, 0) + 1

    top_countries = ", ".join(f"{k}: {v}" for k, v in sorted(countries.items(), key=lambda x: -x[1])[:8]) or "N/A"
    proto_breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(protocols.items(), key=lambda x: -x[1])) or "N/A"

    gist_id = os.environ.get("GIST_ID", "").strip()
    sub_raw_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/subscription.txt"
    clash_raw_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/clash.yaml"
    singbox_raw_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/singbox.json"

    summary = f"""## 🚀 GXBRIEL SMART SUB — Универсальная подписка

| Показатель | Значение |
| :--- | :--- |
| **Опубликовано рабочих узлов** | **`{node_count}`** (из лимита до 200) |
| **Скоростные узлы (≥ 3 МБ/с / 24 Мбит/с)** | **`{fast_nodes}`** |
| **Поддерживаемые протоколы** | {proto_breakdown} |
| **Геолокации узлов** | {top_countries} |

---

### 🌐 Постоянные Raw-ссылки для подключения (без привязки к ревизии):

| Формат | Совместимые клиенты | Постоянный URL |
| :--- | :--- | :--- |
| **V2Ray / Base64** (`subscription.txt`) | Hiddify, Karing, v2rayN, Shadowrocket, Streisand, v2rayNG | [`subscription.txt`]({sub_raw_url}) |
| **Mihomo / Clash** (`clash.yaml`) | Mihomo Party, Clash Verge Rev, Clash Meta, Hiddify, Karing | [`clash.yaml`]({clash_raw_url}) |
| **sing-box** (`singbox.json`) | sing-box, Hiddify, Karing, Nekobox | [`singbox.json`]({singbox_raw_url}) |

```text
# V2Ray / Base64:
{sub_raw_url}

# Mihomo / Clash:
{clash_raw_url}

# sing-box:
{singbox_raw_url}
```
"""

    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as s:
            s.write(summary)

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(generate_summary())
