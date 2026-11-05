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

    fast_nodes = sum(1 for n in nodes if (n.get("speed_mbps") or 0.0) >= 24.0)
    good_nodes = sum(1 for n in nodes if 12.0 <= (n.get("speed_mbps") or 0.0) < 24.0)
    backup_nodes = sum(1 for n in nodes if 5.0 <= (n.get("speed_mbps") or 0.0) < 12.0)
    excluded_slow = speed_stats.get("excluded_slow", 0)
    speed_tested_total = stats.get("speed_test_completed", 0)

    duration_s = stats.get("duration_seconds", 0.0)
    duration_str = (
        f"{int(duration_s // 60)}м {int(duration_s % 60):02d}с ({duration_s:.1f}с)"
        if duration_s > 0
        else "N/A"
    )

    countries: dict[str, int] = {}
    protocols: dict[str, int] = {}
    for n in nodes:
        cc = str(n.get("country_code") or "UN").upper()
        proto = str(n.get("type") or n.get("scheme") or "UNKNOWN").upper()
        countries[cc] = countries.get(cc, 0) + 1
        protocols[proto] = protocols.get(proto, 0) + 1

    top_countries = (
        ", ".join(f"{k}: {v}" for k, v in sorted(countries.items(), key=lambda x: -x[1])[:8])
        or "N/A"
    )
    proto_breakdown = (
        ", ".join(f"{k}: {v}" for k, v in sorted(protocols.items(), key=lambda x: -x[1]))
        or "N/A"
    )

    gist_id = os.environ.get("GIST_ID", "").strip()
    sub_raw_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/subscription.txt"
    clash_raw_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/clash.yaml"
    singbox_raw_url = f"https://gist.githubusercontent.com/GxbrieL9/{gist_id}/raw/singbox.json"

    spd_min = f"{speed_stats.get('min'):.1f}" if speed_stats.get("min") is not None else "N/A"
    spd_med = f"{speed_stats.get('median'):.1f}" if speed_stats.get("median") is not None else "N/A"
    spd_avg = f"{speed_stats.get('average'):.1f}" if speed_stats.get("average") is not None else "N/A"
    spd_max = f"{speed_stats.get('max'):.1f}" if speed_stats.get("max") is not None else "N/A"

    summary = f"""## 🚀 GXBRIEL SMART SUB — Универсальная подписка (Public)

| Показатель | Значение | Описание |
| :--- | :--- | :--- |
| **Опубликовано серверов** | **`{node_count}`** (из лимита до 200) | Прошли полный цикл проверки реальным трафиком |
| ⚡ **FAST (≥ 24 Мбит/с / 3 МБ/с)** | **`{fast_nodes}`** | Премиум-узлы для 4K/стриминга (Tier 1) |
| 🚀 **GOOD (12–24 Мбит/с)** | **`{good_nodes}`** | Высокоскоростные узлы (Tier 2) |
| 🛡️ **BACKUP (5–12 Мбит/с)** | **`{backup_nodes}`** | Стабильный резерв (Tier 3) |
| ❌ **Исключено медленных (< 5 Мбит/с)** | **`{excluded_slow}`** | Отклонены алгоритмом качества (не публикуются) |
| 📊 **Скорость min / median / avg / max** | `{spd_min} / {spd_med} / {spd_avg} / {spd_max} Мбит/с` | Измеренная скорость реального скачивания |
| 📡 **Полноценных Speedtest выполнено** | **`{speed_tested_total}`** узлов | Измерение скорости скачивания через Mihomo |
| **Поддерживаемые протоколы** | {proto_breakdown} | VLESS, VMess, Trojan, TUIC |
| **Геолокации узлов** | {top_countries} | Страны по проверенному egress IP |

---

### ⏱️ Метрики выполнения и GitHub Actions Public:

| Метрика | Значение | Описание |
| :--- | :--- | :--- |
| **Фактическая длительность** | **`{duration_str}`** | Внутренний watchdog с лимитом `timeout-minutes: 5` |
| **Стоимость runner'ов** | **0.00 $ (0 руб.)** | Неограниченные минуты для Public GitHub репозитория |
| **Параллелизм тестирования** | **64 latency / 24 speed** | Многопоточный бенчмарк без перегрузки сокетов |
| **Расписание обновления** | **Каждые 30 мин (`17,47 * * * *`)** | Свежие и рабочие конфиги круглые сутки |

> [!NOTE]
> ⚠️ **Важно для пользователей из РФ**: Измеренная скорость отражает пропускную способность узлов из облачной среды GitHub Actions. Проходимость конкретных узлов внутри РФ зависит от блокировок вашего интернет-провайдера и ТСПУ. Протоколы **VLESS Reality** и **Trojan** обеспечивают максимальную устойчивость.

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
