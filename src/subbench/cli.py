from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

from .benchmark import MihomoBenchmark, write_mihomo_config
from .countries import country_name_zh
from .models import Node
from .output import prepare_names, write_outputs
from .parsers import parse_document
from .prefilter import aliyun_tcp_prefilter, normalize_aliyun_url, tcp_prefilter
from .sources import fetch_sources, load_sources


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _filter_benchmarked_nodes(
    nodes: list[Node],
    max_latency: int,
    min_speed: float,
    require_speed: bool = True,
) -> list[Node]:
    return [
        node
        for node in nodes
        if node.error is None
        and node.latency_ms is not None
        and node.latency_ms <= max_latency
        and (
            not require_speed
            or (node.speed_mbps is not None and node.speed_mbps >= min_speed)
        )
    ]


def _country_flag(country_code: str) -> str:
    code = country_code.upper()
    if len(code) != 2 or not code.isalpha():
        return "🏳️"
    return "".join(chr(ord(character) + 127397) for character in code)


def _rename_nodes_by_country(nodes: list[Node], preferred_speed: float = 24.0) -> None:
    counters: dict[tuple[str, str], int] = {}
    for node in nodes:
        country_code = str(node.metadata.get("country_code", "UN")).upper()
        if len(country_code) != 2 or not country_code.isalpha():
            country_code = "UN"
        protocol = node.scheme.upper()
        key = (country_code, protocol)
        counters[key] = counters.get(key, 0) + 1
        speed_badge = ""
        if node.speed_mbps is not None and node.speed_mbps >= preferred_speed:
            speed_badge = f" ⚡ {node.speed_mbps:.1f}M"
        node.name = (
            f"{_country_flag(country_code)} {country_name_zh(country_code)}"
            f" | {protocol} | {counters[key]:03d}{speed_badge}"
        )
        if node.clash:
            node.clash["name"] = node.name


def run(args: argparse.Namespace) -> int:
    start_time = time.monotonic()
    max_runtime = _float_env("MAX_RUNTIME_SECONDS", 0.0)
    if max_runtime <= 0:
        max_runtime = _float_env("BENCHMARK_MAX_SECONDS", 50.0)
    runtime_deadline = start_time + max(10.0, max_runtime) if max_runtime > 0 else None
    source_specs = load_sources(args.sources)
    if not source_specs:
        raise RuntimeError("No sources configured. Add URLs to config/sources.txt or SOURCE_URLS.")

    source_results = fetch_sources(
        source_specs,
        timeout_seconds=_float_env("SOURCE_TIMEOUT_SECONDS", 60.0),
        workers=_int_env("FETCH_WORKERS", 4),
        retries=_int_env("SOURCE_RETRIES", 3),
        retry_backoff_seconds=_float_env("SOURCE_RETRY_BACKOFF_SECONDS", 2.0),
    )
    nodes: list[Node] = []
    source_errors: list[dict[str, str]] = []
    skipped_nodes: list[str] = []
    for result in source_results:
        if result.error:
            source_errors.append({"source": result.source.name, "error": result.error})
            continue
        nodes.extend(parse_document(result.text or "", result.source.name, skipped_nodes))

    print(f"Fetched {len(source_results)} sources and parsed {len(nodes)} candidate nodes.")
    if skipped_nodes:
        print(
            f"Skipped {len(skipped_nodes)} VLESS nodes with unsupported Mihomo encryption parameters.",
            flush=True,
        )

    unique: dict[str, Node] = {}
    for node in nodes:
        unique.setdefault(node.canonical_key(), node)
    nodes = list(unique.values())
    max_nodes = _int_env("MAX_NODES", 0)
    if max_nodes > 0:
        nodes = nodes[:max_nodes]
    if not nodes:
        raise RuntimeError("Sources were fetched, but no supported nodes were found.")
    for node in nodes:
        node.metadata.setdefault("original_name", node.name)

    mihomo = Path(args.mihomo)
    benchmark_performed = False
    speed_test_enabled = _bool_env("SPEED_TEST_ENABLED", False)
    if args.skip_benchmark:
        print("Benchmark skipped; publishing parsed nodes.")
    elif not mihomo.exists():
        raise RuntimeError(f"Mihomo binary not found: {mihomo}")
    else:
        benchmark_performed = True
        if _bool_env("TCP_PREFILTER_ENABLED", False):
            nodes = tcp_prefilter(
                nodes,
                timeout_seconds=_float_env("TCP_CONNECT_TIMEOUT_SECONDS", 3.0),
                workers=_int_env("TCP_PREFILTER_WORKERS", 128),
                attempts=_int_env("TCP_CONNECT_ATTEMPTS", 2),
            )
        if not nodes:
            print("No nodes passed the TCP prefilter; publishing an empty subscription.")
        else:
            prepare_names(nodes)
            workdir = Path(args.workdir)
            with MihomoBenchmark(
                binary=mihomo,
                workdir=workdir,
                nodes=nodes,
                latency_url=os.environ.get("LATENCY_TEST_URL", "https://www.google.com/generate_204"),
                speed_url=os.environ.get(
                    "SPEED_TEST_URL",
                    "https://speed.cloudflare.com/__down?bytes=1000000",
                ),
                geo_url=os.environ.get(
                    "GEOIP_TEST_URLS",
                    "https://www.cloudflare.com/cdn-cgi/trace,https://api.country.is/",
                ),
                timeout_ms=_int_env("LATENCY_TIMEOUT_MS", 8000),
                speed_bytes=_int_env("SPEED_TEST_BYTES", 1_000_000),
                speed_limit=_int_env("SPEED_TEST_LIMIT", 0),
                speed_timeout_seconds=_int_env("SPEED_TIMEOUT_SECONDS", 4),
                workers=_int_env("BENCHMARK_WORKERS", 64),
                speed_enabled=speed_test_enabled,
                geo_workers=_int_env("GEOIP_WORKERS", 64),
                latency_attempts=_int_env("LATENCY_TEST_ATTEMPTS", 2),
                deadline_monotonic=runtime_deadline,
            ) as benchmark:
                write_mihomo_config(workdir / "mihomo-nodes.yaml", nodes)
                nodes = benchmark.benchmark(nodes)

    max_latency = _int_env("MAX_LATENCY_MS", 3000)
    fast_speed = _float_env("FAST_SPEED_MBPS", 24.0)
    good_speed = _float_env("GOOD_SPEED_MBPS", 12.0)
    backup_speed = _float_env("BACKUP_SPEED_MBPS", 5.0)
    max_output_nodes = _int_env("MAX_OUTPUT_NODES", 200)

    if benchmark_performed:
        # 1. Pool of all nodes that successfully responded to Mihomo latency benchmark
        reachable_pool = [
            node
            for node in unique.values()
            if node.error is None
            and node.latency_ms is not None
            and node.latency_ms <= max_latency
        ]

        # 2. Tier 1: Verified fast nodes (>= preferred_speed Mbps / 3 MB/s)
        fast_nodes = [
            node
            for node in reachable_pool
            if node.speed_mbps is not None and node.speed_mbps >= fast_speed
        ]
        fast_nodes.sort(key=lambda n: (-float(n.speed_mbps or 0.0), n.latency_ms or 10**9, n.name))

        # 3. Tier 2: Verified reachable nodes (lowest latency) to supplement up to max_output_nodes
        fast_ids = set(id(n) for n in fast_nodes)
        backup_nodes = [
            node for node in reachable_pool
            if id(node) not in fast_ids
            and node.speed_mbps is not None
            and node.speed_mbps >= backup_speed
        ]
        backup_nodes.sort(key=lambda n: (-(n.speed_mbps or 0.0), n.latency_ms or 10**9, n.name))

        if speed_test_enabled:
            needed_backup = max(0, max_output_nodes - len(fast_nodes))
            if _bool_env("SPEED_FALLBACK_ENABLED", True):
                nodes = fast_nodes[:max_output_nodes] + backup_nodes[:needed_backup]
            else:
                nodes = fast_nodes[:max_output_nodes]
            print(
                f"Selected {len(nodes)} verified nodes: {len(fast_nodes)} fast (>= {fast_speed:g} Mbps) "
                f"+ {len(nodes) - len(fast_nodes)} speed-tested backup nodes (>= {backup_speed:g} Mbps).",
                flush=True,
            )
        else:
            nodes = reachable_pool[:max_output_nodes]

        if not _bool_env("ALIYUN_FC_ENABLED", True):
            print("Aliyun FC TCP prefilter disabled.", flush=True)
        else:
            aliyun_fc_raw = os.environ.get("ALIYUN_FC_URL", "")
            aliyun_fc_url = normalize_aliyun_url(aliyun_fc_raw)
            if aliyun_fc_raw.strip() and not aliyun_fc_url:
                print(
                    "Aliyun FC TCP prefilter skipped: ALIYUN_FC_URL must contain only the exact http:// or https:// URL.",
                    flush=True,
                )
            if aliyun_fc_url and nodes:
                nodes = aliyun_tcp_prefilter(
                    nodes,
                    url=aliyun_fc_url,
                    timeout_seconds=_float_env("ALIYUN_FC_TIMEOUT_SECONDS", 10.0),
                    interval_seconds=_float_env("ALIYUN_FC_INTERVAL_SECONDS", 0.2),
                    interval_jitter_seconds=_float_env("ALIYUN_FC_JITTER_SECONDS", 0.1),
                    max_consecutive_errors=_int_env("ALIYUN_FC_MAX_CONSECUTIVE_ERRORS", 3),
                    workers=_int_env("ALIYUN_FC_WORKERS", 10),
                )

        _rename_nodes_by_country(nodes, fast_speed)
    if not nodes:
        failures = "; ".join(node.error or "unknown error" for node in unique.values() if node.error)
        source_errors.append(
            {
                "source": "benchmark",
                "error": f"No nodes passed the configured latency/speed filters. {failures[:1000]}",
            }
        )
        print("No nodes passed the configured latency/speed filters; publishing an empty subscription.")

    duration_seconds = round(time.monotonic() - start_time, 2)
    billed_minutes = max(1, (int(duration_seconds) + 59) // 60)
    measured = [node.speed_mbps for node in unique.values() if node.speed_mbps is not None]
    execution_stats = {
        "duration_seconds": duration_seconds,
        "billed_minutes": billed_minutes,
        "monthly_projected_minutes": billed_minutes * 744,
        "github_free_limit_minutes": 2000,
        "github_free_balance_minutes": max(0, 2000 - (billed_minutes * 744)),
        "sources_total": len(source_specs),
        "sources_succeeded": len(source_specs) - len(source_errors),
        "sources_failed": len(source_errors),
        "candidates_unique": len(unique),
        "speed_test_completed": len(measured),
        "speed_test_failed": sum(1 for node in unique.values() if node.error),
        "speed_mbps": {
            "min": min(measured) if measured else None,
            "average": round(statistics.mean(measured), 3) if measured else None,
            "median": statistics.median(measured) if measured else None,
            "max": max(measured) if measured else None,
            "fast": sum(value >= fast_speed for value in measured),
            "good": sum(good_speed <= value < fast_speed for value in measured),
            "backup": sum(backup_speed <= value < good_speed for value in measured),
        },
    }
    write_outputs(Path(args.output), nodes, source_errors, execution_stats=execution_stats)
    print(
        f"Published {len(nodes)} nodes from {len(source_specs)} sources in "
        f"{duration_seconds}s (billed as {billed_minutes} GitHub Actions min)."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", nargs="?", default="run")
    parser.add_argument("--sources", type=Path, default=Path("config/sources.txt"))
    parser.add_argument("--output", type=Path, default=Path("public"))
    parser.add_argument("--workdir", type=Path, default=Path(".work"))
    parser.add_argument("--mihomo", type=Path, default=Path(".bin/mihomo"))
    parser.add_argument("--skip-benchmark", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
