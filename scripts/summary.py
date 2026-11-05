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
        proto = str(n.get("scheme") or "UNKNOWN").upper()
        countries[cc] = countries.get(cc, 0) + 1
        protocols[proto] = protocols.get(proto, 0) + 1

    top_countries = ", ".join(f"{k}: {v}" for k, v in sorted(countries.items(), key=lambda x: -x[1])[:8])
    proto_breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(protocols.items(), key=lambda x: -x[1]))

    gist_id = os.environ.get("GIST_ID", "").strip()
    raw_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/subscription.txt"
    raw_b64_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/subscription-b64.txt"

    summary = f"""## 🚀 GXBRIEL SMART SUB — Сводка обновления

| Показатель | Значение |
| :--- | :--- |
| **Опубликовано серверов** | **`{node_count}`** (из лимита 200) |
| **Скоростные узлы (≥ 24 Мбит/с / 3 МБ/с)** | **`{fast_nodes}`** |
| **Протоколы** | {proto_breakdown} |
| **Геолокации узлов** | {top_countries} |
| **Прямая ссылка для Karing (Raw)** | [`subscription.txt`]({raw_url}) |
| **Base64-ссылка (для v2rayN/Xray)** | [`subscription-b64.txt`]({raw_b64_url}) |

### 📲 Инструкция по добавлению в Karing:
1. Скопируйте постоянную прямую ссылку:
   ```text
   {raw_url}
   ```
2. Откройте **Karing** → перейдите в раздел **Профили (Profiles)** → **Добавить подписку (Add Subscription)**.
3. Вставьте ссылку, назовите профиль `GXBRIEL SMART SUB` и сохраните.
4. Включите автоматическое обновление подписки в приложении.
"""

    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as s:
            s.write(summary)

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(generate_summary())
