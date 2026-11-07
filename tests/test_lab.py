import unittest

from src.chain import ROOT
from src.lab import Journal
from src.reading import document


class TeachingArchiveTests(unittest.TestCase):
    def test_lookup_swap_and_confirm_wallet_and_logs(self):
        j = Journal(ROOT / "data/experiments/first-100/events.jsonl")
        event_id = j.hashes["0xf2952492701ee5c5c2738d5c67a3176cb8f5bc9420acb6a6bd1bee094b83da0c"]
        turn = j.lookup[event_id]
        events = j.round_events(turn)
        swap = next(event for event in events if event["id"] == event_id)
        self.assertEqual(len([e for e in events if e["kind"] == "decision"]), 5)
        self.assertEqual(swap["wallet_after"]["sUSD"], "267913851801556925940")
        self.assertEqual([log["name"] for log in swap["decoded_logs"]], ["Transfer", "Transfer", "Swap"])
        self.assertEqual(j.series()["rows"][0][6], "18000000000000000000")

    def test_content_escapes_injected_html_and_protocols(self):
        text = document("# 练习\n\n<script>x</script> [坏](javascript:alert) [证据](/?run=a&event=b)").decode()
        self.assertNotIn("<script>", text)
        self.assertNotIn("javascript:", text)
        self.assertIn("/?run=a&amp;event=b", text)
