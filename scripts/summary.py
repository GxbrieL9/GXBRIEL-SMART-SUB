from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def generate_summary() -> int:
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
    stats = report.get("execution_stats", {})
    speed_stats = stats.get("speed_mbps", {})
    fast_nodes = speed_stats.get("fast", sum(1 for n in nodes if (n.get("speed_mbps") or 0) >= 24.0))
    good_nodes = speed_stats.get("good", 0)
    backup_nodes = speed_stats.get("backup", 0)
    duration_s = stats.get("duration_seconds", 0.0)
    billed_m = stats.get("billed_minutes", max(1, (int(duration_s) + 59) // 60) if duration_s > 0 else 1)
    projected_m = stats.get("monthly_projected_minutes", billed_m * 744)
    balance_m = stats.get("github_free_balance_minutes", max(0, 2000 - projected_m))

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

    duration_str = f"{int(duration_s // 60)}м {int(duration_s % 60):02d}с ({duration_s:.1f}с)" if duration_s > 0 else "N/A"

    schedule_note = ""
    if duration_s >= 95:
        schedule_note = (
            "\n> [!TIP]\n"
            "> Длительность выполнения приблизилась к лимиту тайм-аута. "
            "Рекомендуется переключиться на интервал раз в 2 часа (`cron: '17 */2 * * *'`) "
            "с `timeout-minutes: 4` (расход останется в рамках 1 488 мин/мес).\n"
        )

    summary = f"""## 🚀 GXBRIEL SMART SUB — Универсальная подписка

| Показатель | Значение |
| :--- | :--- |
| **Опубликовано рабочих узлов** | **`{node_count}`** (из лимита до 200) |
| **Скоростные узлы (≥ 3 МБ/с / 24 Мбит/с)** | **`{fast_nodes}`** |
| **GOOD (12–24 Мбит/с)** | **`{good_nodes}`** |
| **BACKUP (5–12 Мбит/с)** | **`{backup_nodes}`** |
| **Speed min / median / average / max** | `{speed_stats.get("min", "N/A")} / {speed_stats.get("median", "N/A")} / {speed_stats.get("average", "N/A")} / {speed_stats.get("max", "N/A")} Mbps` |
| **Поддерживаемые протоколы** | {proto_breakdown} |
| **Геолокации узлов** | {top_countries} |

---

### ⏱️ Фактическая длительность и лимит GitHub Actions Free (0.00 $):

| Метрика выполнения | Значение | Описание |
| :--- | :--- | :--- |
| **Фактическая длительность сборки** | **`{duration_str}`** | Жёсткий лимит `timeout-minutes: 2` |
| **Списано включённых минут GitHub** | **`{billed_m} мин`** | Посекундное округление runner |
| **Прогноз расхода в месяц** | **`~{projected_m} мин`** | Расчёт для 744 запусков (24/день * 31) |
| **Остаток бесплатного лимита Free** | **`~{balance_m} мин`** | Из 2 000 включённых минут аккаунта |
| **Финансовые расходы** | **0.00 $ (0 руб.)** | Гарантия нулевых расходов |
{schedule_note}
---

### 🌐 Постоянные Raw-ссылки для подключения:

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
