"""Exercise real loopback HTTP and Anvil with a credential-free relay fixture."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from src.archive import verify
from src.chain import ROOT, UNIT
from src.events import read_events


class RelayIntegration(unittest.TestCase):
    def test_local_relay_to_chain_with_role_budget_and_fallback(self):
        requests = []
        discoveries = []

        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def send_json(self, data):
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path != "/models":
                    self.send_error(404)
                    return
                discoveries.append(self.path)
                self.send_json({"protocol": "web3-lab-v1", "enforces_budget": True, "ids": ["test-relay-v1"]})

            def do_POST(self):
                if self.path != "/decide":
                    self.send_error(404)
                    return
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request)
                if request["role"] == "contrarian":
                    self.send_error(503)
                    return
                trade = request["role"] == "trend"
                decision = dict(action="sell" if trade else "hold", token_in="RISK" if trade else None,
                                amount_raw=str(18 * UNIT) if trade else "0",
                                max_slippage_bps=30 if trade else 0, confidence=None,
                                public_rationale="本地中继合成测试决策。", cited_news_ids=[])
                self.send_json(dict(model="test-relay-v1", decision=json.dumps(decision),
                                    input_tokens=0, output_tokens=0, cost_usd="0",
                                    private_reasoning="IGNORED_RELAY_FIXTURE_FIELD"))

        with TemporaryDirectory() as folder, ThreadingHTTPServer(("127.0.0.1", 0), Fixture) as server:
            root = Path(folder)
            server_thread = Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            try:
                spec = dict(model="test-relay-v1", max_calls=1, max_tokens=64, timeout_seconds=2,
                            max_cost_usd=0, temperature=0)
                config = root / "relay.json"
                config.write_text(json.dumps(dict(mode="live", relay_port=server.server_port,
                                                 agents={role: spec for role in ("trend","event","contrarian")})))
                command = [sys.executable, "-m", "src.run", "--archive-root", str(root),
                           "--rounds", "2", "--run-id", "local-relay-test", "--models", str(config)]
                blocked = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn("require explicit --allow-model-calls", blocked.stderr)
                self.assertFalse(discoveries)
                self.assertFalse(requests)

                run = subprocess.run([*command, "--allow-model-calls"], cwd=ROOT, capture_output=True,
                                     text=True, timeout=20)
                self.assertEqual(run.returncode, 0, run.stderr)
                directory = root / "local-relay-test"
                events = read_events(directory)
                self.assertGreater(verify(directory), 0)
                self.assertEqual(len(discoveries), 3)
                self.assertEqual([r["role"] for r in requests], ["trend", "event", "contrarian"])
                for request in requests:
                    self.assertEqual(request["model"], "test-relay-v1")
                    self.assertEqual(request["max_cost_usd"], "0")
                    self.assertEqual(request["max_total_tokens"], 64)
                    self.assertEqual(request["snapshot"]["visible_news"], [])
                    self.assertNotIn("wallets", request["snapshot"])

                trend = next(event for event in events if event["kind"] == "decision"
                             and event["role"] == "trend" and event["round"] == 1)
                trade = next(event for event in events if event["kind"] == "swap_receipt"
                             and event["order_id"] == trend["id"])
                self.assertEqual(trend["provider_model"], "test-relay-v1")
                self.assertEqual(trade["receipt"]["status"], "0x1")
                self.assertEqual(trade["amount_in_raw"], str(18 * UNIT))
                failure = next(event for event in events if event["kind"] == "decision"
                               and event["role"] == "contrarian" and event["round"] == 1)
                self.assertEqual(failure["decision_mode"], "model_fallback")
                self.assertEqual(failure["failure"], "relay_or_schema_error")
                self.assertTrue(failure["billing_uncertain"])
                self.assertNotIn("IGNORED_RELAY_FIXTURE_FIELD", (directory / "events.jsonl").read_text())
                costs = json.loads((directory / "costs_and_stats.json").read_text())["costs"]
                self.assertEqual(costs["calls"], 3)  # HTTP fixture attempts, no provider traffic.
                self.assertEqual(costs["cost_usd"], "0")
                self.assertEqual(costs["input_tokens"] + costs["output_tokens"], 0)
            finally:
                server.shutdown()
                server_thread.join(5)
