import base64
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote

import yaml

from subbench.models import Node
from subbench.output import _rename_uri, build_singbox_config, node_to_singbox, write_outputs


class OutputTests(unittest.TestCase):
    def test_vless_fragment_is_replaced(self):
        rendered = _rename_uri("vless://id@example.com:443?security=tls#old", "vless", "🇺🇸 美国 | VLESS | 001")
        self.assertEqual(unquote(rendered.split("#", 1)[1]), "🇺🇸 美国 | VLESS | 001")

    def test_vmess_display_name_is_replaced(self):
        payload = base64.urlsafe_b64encode(json.dumps({"ps": "old", "add": "example.com"}).encode()).decode().rstrip("=")
        rendered = _rename_uri(f"vmess://{payload}", "vmess", "🇯🇵 日本 | VMESS | 001")
        encoded = rendered.split("://", 1)[1]
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        self.assertEqual(json.loads(decoded)["ps"], "🇯🇵 日本 | VMESS | 001")

    def test_empty_subscription_uses_direct_only_group(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            stats = {"duration_seconds": 45.2, "billed_minutes": 1, "monthly_projected_minutes": 744}
            write_outputs(output, [], [{"source": "benchmark", "error": "no usable nodes"}], execution_stats=stats)
            clash = yaml.safe_load((output / "clash.yaml").read_text(encoding="utf-8"))
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            singbox = json.loads((output / "singbox.json").read_text(encoding="utf-8"))
            self.assertEqual(clash["proxy-groups"], [{"name": "PROXY", "type": "select", "proxies": ["DIRECT"]}])
            self.assertEqual(report["node_count"], 0)
            self.assertEqual(report["execution_stats"]["duration_seconds"], 45.2)
            self.assertEqual(report["execution_stats"]["billed_minutes"], 1)
            self.assertTrue((output / "singbox.json").exists())
            self.assertEqual(singbox["outbounds"][0]["tag"], "PROXY")
            self.assertEqual(singbox["outbounds"][0]["outbounds"], ["direct"])

    def test_singbox_outbound_generation_all_protocols(self):
        vless_node = Node(
            uri="vless://00000000-0000-4000-8000-000000000001@example.com:443?security=reality&pbk=abc&sid=12",
            scheme="vless",
            name="Node-VLESS",
            clash={
                "name": "Node-VLESS",
                "type": "vless",
                "server": "example.com",
                "port": 443,
                "uuid": "00000000-0000-4000-8000-000000000001",
                "reality-opts": {"public-key": "abc", "short-id": "12"},
                "network": "ws",
                "ws-opts": {"path": "/ws", "headers": {"Host": "cdn.example.com"}},
            },
            source="test",
        )
        ob_vless = node_to_singbox(vless_node)
        self.assertIsNotNone(ob_vless)
        self.assertEqual(ob_vless["type"], "vless")
        self.assertEqual(ob_vless["tag"], "Node-VLESS")
        self.assertTrue(ob_vless["tls"]["reality"]["enabled"])
        self.assertEqual(ob_vless["transport"]["type"], "ws")

        vmess_node = Node(
            uri="vmess://example",
            scheme="vmess",
            name="Node-VMESS",
            clash={
                "name": "Node-VMESS",
                "type": "vmess",
                "server": "example.com",
                "port": 443,
                "uuid": "00000000-0000-4000-8000-000000000001",
                "cipher": "auto",
                "alterId": 0,
                "tls": True,
                "servername": "example.com",
            },
            source="test",
        )
        ob_vmess = node_to_singbox(vmess_node)
        self.assertIsNotNone(ob_vmess)
        self.assertEqual(ob_vmess["type"], "vmess")
        self.assertTrue(ob_vmess["tls"]["enabled"])

        trojan_node = Node(
            uri="trojan://pass@example.com:443",
            scheme="trojan",
            name="Node-Trojan",
            clash={
                "name": "Node-Trojan",
                "type": "trojan",
                "server": "example.com",
                "port": 443,
                "password": "pass",
                "sni": "example.com",
            },
            source="test",
        )
        ob_trojan = node_to_singbox(trojan_node)
        self.assertIsNotNone(ob_trojan)
        self.assertEqual(ob_trojan["type"], "trojan")

        ss_node = Node(
            uri="ss://example",
            scheme="ss",
            name="Node-SS",
            clash={
                "name": "Node-SS",
                "type": "ss",
                "server": "example.com",
                "port": 8388,
                "cipher": "aes-256-gcm",
                "password": "secret",
            },
            source="test",
        )
        ob_ss = node_to_singbox(ss_node)
        self.assertIsNotNone(ob_ss)
        self.assertEqual(ob_ss["type"], "shadowsocks")
        self.assertEqual(ob_ss["method"], "aes-256-gcm")

        hy2_node = Node(
            uri="hysteria2://pass@example.com:443",
            scheme="hysteria2",
            name="Node-HY2",
            clash={
                "name": "Node-HY2",
                "type": "hysteria2",
                "server": "example.com",
                "port": 443,
                "password": "pass",
                "sni": "example.com",
                "obfs": "salamander",
                "obfs-password": "opass",
            },
            source="test",
        )
        ob_hy2 = node_to_singbox(hy2_node)
        self.assertIsNotNone(ob_hy2)
        self.assertEqual(ob_hy2["type"], "hysteria2")
        self.assertEqual(ob_hy2["obfs"]["type"], "salamander")

        tuic_node = Node(
            uri="tuic://uuid:pass@example.com:8443",
            scheme="tuic",
            name="Node-TUIC",
            clash={
                "name": "Node-TUIC",
                "type": "tuic",
                "server": "example.com",
                "port": 8443,
                "uuid": "00000000-0000-4000-8000-000000000001",
                "password": "pass",
                "sni": "example.com",
            },
            source="test",
        )
        ob_tuic = node_to_singbox(tuic_node)
        self.assertIsNotNone(ob_tuic)
        self.assertEqual(ob_tuic["type"], "tuic")

    def test_incompatible_node_excluded_from_singbox_only(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            good_node = Node(
                uri="trojan://pass@example.com:443#Good",
                scheme="trojan",
                name="Good-Node",
                clash={
                    "name": "Good-Node",
                    "type": "trojan",
                    "server": "example.com",
                    "port": 443,
                    "password": "pass",
                },
                source="test",
            )
            # Incompatible node has invalid/missing data for sing-box but valid clash/uri
            bad_for_sb = Node(
                uri="custom://example#Custom",
                scheme="custom",
                name="Custom-Node",
                clash={
                    "name": "Custom-Node",
                    "type": "trojan",
                    "server": "example2.com",
                    "port": 443,
                    "password": "pass",
                },
                source="test",
            )
            write_outputs(output, [good_node, bad_for_sb], [])
            singbox = json.loads((output / "singbox.json").read_text(encoding="utf-8"))
            clash = yaml.safe_load((output / "clash.yaml").read_text(encoding="utf-8"))
            subscription = (output / "subscription.txt").read_text(encoding="ascii")
            
            # singbox should only contain Good-Node
            sb_tags = [ob["tag"] for ob in singbox["outbounds"] if ob.get("tag") not in {"PROXY", "AUTO", "direct"}]
            self.assertEqual(sb_tags, ["Good-Node"])
            # clash should contain both
            clash_names = [p["name"] for p in clash["proxies"]]
            self.assertEqual(len(clash_names), 2)
            # subscription should contain both URIs
            decoded = base64.b64decode(subscription).decode("utf-8")
            self.assertIn("Good", decoded)
            self.assertIn("Custom", decoded)


if __name__ == "__main__":
    unittest.main()
