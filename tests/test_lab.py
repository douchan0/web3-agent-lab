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

    def test_unclosed_round_has_evidence_without_market_marks_or_wallet_reset(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        archive = Journal(ROOT / "data/experiments/first-100/events.jsonl")
        setup_and_round = archive.round_events(0) + archive.round_events(1)
        next_round = [e for e in archive.round_events(2) if e["kind"] == "reference"]
        with TemporaryDirectory() as folder:
            path = Path(folder) / "events.jsonl"
            path.write_text("".join(json.dumps(e) + "\n" for e in setup_and_round + next_round))
            journal = Journal(path)
            self.assertEqual(journal.series()["incomplete_round"],2)
            self.assertEqual(len(journal.series()["rows"]),1)
            self.assertEqual(len(journal.series()["roles"]["trend"]),1)
            self.assertEqual(journal.round_events(2)[0]["id"],next_round[0]["id"])
