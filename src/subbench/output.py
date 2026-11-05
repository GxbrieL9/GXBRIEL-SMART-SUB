from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from .models import Node


def node_to_singbox(node: Node) -> dict[str, Any] | None:
    if not node.clash or not isinstance(node.clash, dict):
        return None
    clash = node.clash
    scheme = str(node.scheme).lower()
    name = node.name

    if scheme == "vless":
        outbound: dict[str, Any] = {
            "type": "vless",
            "tag": name,
            "server": str(clash["server"]),
            "server_port": int(clash["port"]),
            "uuid": str(clash["uuid"]),
            "packet_encoding": "xudp",
        }
        if clash.get("flow"):
            outbound["flow"] = str(clash["flow"])
        tls_config: dict[str, Any] = {}
        if clash.get("tls") or clash.get("reality-opts"):
            tls_config["enabled"] = True
            if clash.get("servername"):
                tls_config["server_name"] = str(clash["servername"])
            if clash.get("skip-cert-verify"):
                tls_config["insecure"] = True
            if clash.get("alpn"):
                tls_config["alpn"] = (
                    clash["alpn"] if isinstance(clash["alpn"], list) else [str(clash["alpn"])]
                )
            if clash.get("client-fingerprint"):
                tls_config["utls"] = {
                    "enabled": True,
                    "fingerprint": str(clash["client-fingerprint"]),
                }
            reality = clash.get("reality-opts")
            if reality and reality.get("public-key"):
                tls_config["reality"] = {
                    "enabled": True,
                    "public_key": str(reality["public-key"]),
                    "short_id": str(reality.get("short-id", "")),
                }
        if tls_config:
            outbound["tls"] = tls_config

        network = str(clash.get("network", "tcp")).lower()
        if network in {"raw", "none", ""}:
            network = "tcp"
        if network == "ws":
            ws_opts = clash.get("ws-opts") or {}
            transport: dict[str, Any] = {"type": "ws", "path": str(ws_opts.get("path", "/"))}
            headers = ws_opts.get("headers") or {}
            if headers.get("Host"):
                transport["headers"] = {"Host": str(headers["Host"])}
            outbound["transport"] = transport
        elif network == "grpc":
            grpc_opts = clash.get("grpc-opts") or {}
            outbound["transport"] = {
                "type": "grpc",
                "service_name": str(grpc_opts.get("grpc-service-name", "")),
            }
        elif network == "httpupgrade":
            opts = clash.get("http-upgrade-opts") or {}
            transport = {"type": "httpupgrade", "path": str(opts.get("path", "/"))}
            headers = opts.get("headers") or {}
            if headers.get("Host"):
                transport["host"] = str(headers["Host"])
            outbound["transport"] = transport
        return outbound

    if scheme == "vmess":
        outbound = {
            "type": "vmess",
            "tag": name,
            "server": str(clash["server"]),
            "server_port": int(clash["port"]),
            "uuid": str(clash["uuid"]),
            "security": str(clash.get("cipher", "auto") or "auto"),
            "alter_id": int(clash.get("alterId", 0) or 0),
            "packet_encoding": "xudp",
        }
        tls_config = {}
        if clash.get("tls"):
            tls_config["enabled"] = True
            if clash.get("servername"):
                tls_config["server_name"] = str(clash["servername"])
            if clash.get("skip-cert-verify"):
                tls_config["insecure"] = True
            if clash.get("alpn"):
                tls_config["alpn"] = (
                    clash["alpn"] if isinstance(clash["alpn"], list) else [str(clash["alpn"])]
                )
            if clash.get("client-fingerprint"):
                tls_config["utls"] = {
                    "enabled": True,
                    "fingerprint": str(clash["client-fingerprint"]),
                }
        if tls_config:
            outbound["tls"] = tls_config

        network = str(clash.get("network", "tcp")).lower()
        if network in {"raw", "none", ""}:
            network = "tcp"
        if network == "ws":
            ws_opts = clash.get("ws-opts") or {}
            transport = {"type": "ws", "path": str(ws_opts.get("path", "/"))}
            headers = ws_opts.get("headers") or {}
            if headers.get("Host"):
                transport["headers"] = {"Host": str(headers["Host"])}
            outbound["transport"] = transport
        elif network == "grpc":
            grpc_opts = clash.get("grpc-opts") or {}
            outbound["transport"] = {
                "type": "grpc",
                "service_name": str(grpc_opts.get("grpc-service-name", "")),
            }
        return outbound

    if scheme == "trojan":
        outbound = {
            "type": "trojan",
            "tag": name,
            "server": str(clash["server"]),
            "server_port": int(clash["port"]),
            "password": str(clash["password"]),
        }
        tls_config = {"enabled": True}
        sni = clash.get("sni") or clash.get("servername")
        if sni:
            tls_config["server_name"] = str(sni)
        if clash.get("skip-cert-verify"):
            tls_config["insecure"] = True
        if clash.get("alpn"):
            tls_config["alpn"] = (
                clash["alpn"] if isinstance(clash["alpn"], list) else [str(clash["alpn"])]
            )
        outbound["tls"] = tls_config

        network = str(clash.get("network", "tcp")).lower()
        if network in {"raw", "none", ""}:
            network = "tcp"
        if network == "ws":
            ws_opts = clash.get("ws-opts") or {}
            transport = {"type": "ws", "path": str(ws_opts.get("path", "/"))}
            headers = ws_opts.get("headers") or {}
            if headers.get("Host"):
                transport["headers"] = {"Host": str(headers["Host"])}
            outbound["transport"] = transport
        elif network == "grpc":
            grpc_opts = clash.get("grpc-opts") or {}
            outbound["transport"] = {
                "type": "grpc",
                "service_name": str(grpc_opts.get("grpc-service-name", "")),
            }
        return outbound

    if scheme == "ss":
        outbound = {
            "type": "shadowsocks",
            "tag": name,
            "server": str(clash["server"]),
            "server_port": int(clash["port"]),
            "method": str(clash["cipher"]),
            "password": str(clash["password"]),
        }
        if clash.get("plugin"):
            outbound["plugin"] = str(clash["plugin"])
            if clash.get("plugin-opts"):
                outbound["plugin_opts"] = str(clash["plugin-opts"])
        return outbound

    if scheme == "hysteria2":
        outbound = {
            "type": "hysteria2",
            "tag": name,
            "server": str(clash["server"]),
            "server_port": int(clash["port"]),
            "password": str(clash["password"]),
        }
        tls_config = {"enabled": True}
        sni = clash.get("sni") or clash.get("servername")
        if sni:
            tls_config["server_name"] = str(sni)
        if clash.get("skip-cert-verify"):
            tls_config["insecure"] = True
        if clash.get("alpn"):
            tls_config["alpn"] = (
                clash["alpn"] if isinstance(clash["alpn"], list) else [str(clash["alpn"])]
            )
        outbound["tls"] = tls_config
        if clash.get("obfs"):
            outbound["obfs"] = {
                "type": str(clash["obfs"]),
                "password": str(clash.get("obfs-password", "")),
            }
        return outbound

    if scheme == "tuic":
        outbound = {
            "type": "tuic",
            "tag": name,
            "server": str(clash["server"]),
            "server_port": int(clash["port"]),
            "uuid": str(clash["uuid"]),
            "password": str(clash["password"]),
            "congestion_control": str(clash.get("congestion-controller", "bbr")),
            "udp_relay_mode": str(clash.get("udp-relay-mode", "native")),
        }
        tls_config = {"enabled": True}
        sni = clash.get("sni") or clash.get("servername")
        if sni:
            tls_config["server_name"] = str(sni)
        if clash.get("skip-cert-verify"):
            tls_config["insecure"] = True
        if clash.get("alpn"):
            tls_config["alpn"] = (
                clash["alpn"] if isinstance(clash["alpn"], list) else [str(clash["alpn"])]
            )
        outbound["tls"] = tls_config
        return outbound

    return None


def build_singbox_config(nodes: list[Node]) -> dict[str, Any]:
    singbox_outbounds: list[dict[str, Any]] = []
    for node in nodes:
        try:
            outbound = node_to_singbox(node)
            if outbound:
                singbox_outbounds.append(outbound)
        except Exception:
            continue

    tags = [ob["tag"] for ob in singbox_outbounds]

    groups: list[dict[str, Any]] = []
    if tags:
        groups.append({
            "type": "selector",
            "tag": "PROXY",
            "outbounds": ["AUTO", "direct", *tags],
            "default": "AUTO",
        })
        groups.append({
            "type": "urltest",
            "tag": "AUTO",
            "outbounds": tags,
            "url": "https://www.google.com/generate_204",
            "interval": "5m",
            "tolerance": 50,
        })
    else:
        groups.append({
            "type": "selector",
            "tag": "PROXY",
            "outbounds": ["direct"],
            "default": "direct",
        })

    return {
        "log": {"level": "warn"},
        "dns": {
            "servers": [
                {"tag": "dns-remote", "type": "tls", "server": "8.8.8.8"},
                {"tag": "dns-direct", "type": "local", "detour": "direct"},
            ]
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 2080,
            }
        ],
        "outbounds": [
            *groups,
            *singbox_outbounds,
            {"type": "direct", "tag": "direct"},
        ],
        "route": {
            "default_domain_resolver": "dns-direct",
            "final": "PROXY",
            "auto_detect_interface": True,
        },
    }


def _safe_name(name: str, index: int, used: set[str]) -> str:
    clean = " ".join(name.split()).strip() or f"node-{index:03d}"
    candidate = clean[:80]
    suffix = 2
    while candidate in used:
        candidate = f"{clean[:70]}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def prepare_names(nodes: list[Node]) -> None:
    used: set[str] = {"AUTO", "PROXY", "BENCHMARK", "DIRECT"}
    for index, node in enumerate(nodes, start=1):
        node.name = _safe_name(node.name, index, used)
        if node.clash:
            node.clash["name"] = node.name


def _rename_uri(uri: str, scheme: str, name: str) -> str:
    if scheme == "vmess" and uri.startswith("vmess://"):
        try:
            encoded = uri.split("://", 1)[1].split("#", 1)[0]
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            payload["ps"] = name
            rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return "vmess://" + base64.urlsafe_b64encode(rendered).decode("ascii").rstrip("=")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
            return uri

    main = uri.split("#", 1)[0]
    main = main.replace("type=raw", "type=tcp")

    import re
    import urllib.parse

    parsed = urllib.parse.urlsplit(main)
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    changed = False

    if "type" in qs and qs["type"][0].lower() in {"raw", "none", ""}:
        qs["type"] = ["tcp"]
        changed = True

    if "alpn" in qs:
        cleaned = [
            item.strip()
            for item in qs["alpn"][0].split(",")
            if item.strip() and re.match(r"^[a-zA-Z0-9_\.\-\+]+$", item.strip())
        ]
        if cleaned:
            qs["alpn"] = [",".join(cleaned)]
        else:
            del qs["alpn"]
        changed = True

    if "fm" in qs:
        del qs["fm"]
        changed = True

    if changed:
        clean_query = urllib.parse.urlencode(qs, doseq=True)
        main = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, clean_query, ""))

    return f"{main}#{quote(name, safe='')}"


def write_outputs(
    output_dir: Path,
    nodes: list[Node],
    source_errors: list[dict[str, str]],
    execution_stats: dict[str, Any] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    prepare_names(nodes)

    uris = [_rename_uri(node.uri, node.scheme, node.name) for node in nodes if node.uri]
    raw = "\n".join(uris) + ("\n" if uris else "")
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    (output_dir / "v2ray.txt").write_text(encoded + "\n", encoding="ascii")
    (output_dir / "v2ray-raw.txt").write_text(raw, encoding="utf-8")
    (output_dir / "subscription.txt").write_text(encoded + "\n", encoding="ascii")
    (output_dir / "subscription-raw.txt").write_text(raw, encoding="utf-8")

    proxies = [node.clash for node in nodes if node.clash]
    names = [proxy["name"] for proxy in proxies]
    if names:
        proxy_groups = [
            {
                "name": "AUTO",
                "type": "url-test",
                "url": "https://www.google.com/generate_204",
                "interval": 300,
                "tolerance": 100,
                "proxies": names,
            },
            {"name": "PROXY", "type": "select", "proxies": ["AUTO", "DIRECT", *names]},
        ]
    else:
        proxy_groups = [{"name": "PROXY", "type": "select", "proxies": ["DIRECT"]}]

    clash_config = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "ipv6": False,
        "proxies": proxies,
        "proxy-groups": proxy_groups,
        "rules": ["MATCH,PROXY"],
    }
    (output_dir / "clash.yaml").write_text(
        yaml.safe_dump(clash_config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    singbox_config = build_singbox_config(nodes)
    (output_dir / "singbox.json").write_text(
        json.dumps(singbox_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node_count": len(nodes),
        "source_errors": source_errors,
        "nodes": [node.report_dict() for node in nodes],
    }
    if execution_stats:
        report["execution_stats"] = execution_stats
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rows = "".join(
        f"<tr><td>{index}</td><td>{node.name}</td><td>{node.scheme}</td>"
        f"<td>{node.latency_ms or '-'} ms</td><td>{node.speed_mbps or '-'} Mbps</td></tr>"
        for index, node in enumerate(nodes, start=1)
    )
    page = f"""<!doctype html>
<meta charset="utf-8">
<title>Node subscriptions</title>
<style>body{{font:16px system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:8px;text-align:left}}code{{background:#f3f3f3;padding:2px 4px}}</style>
<h1>Node subscriptions</h1>
<p>Generated {report['generated_at']} with {len(nodes)} usable nodes.</p>
<ul><li><a href="subscription.txt">V2Ray Base64 subscription</a></li><li><a href="clash.yaml">Clash/Mihomo config</a></li><li><a href="singbox.json">sing-box config</a></li><li><a href="subscription-raw.txt">Raw links</a></li><li><a href="report.json">JSON report</a></li></ul>
<table><thead><tr><th>#</th><th>Name</th><th>Type</th><th>Latency</th><th>Speed</th></tr></thead><tbody>{rows}</tbody></table>
"""
    (output_dir / "index.html").write_text(page, encoding="utf-8")
