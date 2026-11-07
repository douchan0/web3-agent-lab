from collections import Counter
import json
import unittest

from src.analytics import candles, summarize
from src.chain import ROOT
from src.events import read_events
from src.execution import expected_output, opposite
from src.experiment import fixture_hash, parse_time
from src.replay import compare

ARCHIVES = ROOT / "data/experiments"


class ArchiveTests(unittest.TestCase):
    def test_export_and_reconciliation(self):
        directory = ARCHIVES / "first-100"
        events = read_events(directory)
        self.assertEqual([e["id"] for e in events], [f"E{i:06d}" for i in range(1, len(events) + 1)])
        self.assertEqual(Counter(e["kind"] for e in events)["decision"], 500)
        index = {e["id"]: e for e in events}
        broadcast = {e["tx_hash"]: e for e in events if e["kind"] == "swap_broadcast"}
        visible = set()
        last_reserves = next(e["reserves"] for e in events if e["kind"] == "market_open")
        for event in events:
            if event["kind"] == "news":
                at = parse_time(event["simulated_at"])
                self.assertLessEqual(parse_time(event["published_at"]), parse_time(event["available_at"]))
                self.assertLessEqual(parse_time(event["available_at"]), at)
                fields = {key: event[key] for key in (
                    "news_id", "source_type", "source_url", "title", "published_at", "available_at",
                    "content_excerpt", "asset_tags", "reference_shock_bps", "source_hash",
                )}
                self.assertEqual(fixture_hash(fields), event["source_hash"])
                visible.add(event["news_id"])
            if event["kind"] == "decision":
                self.assertEqual(set(event["input_snapshot"]["visible_news_ids"]), visible)
                self.assertLessEqual(set(event["intent"]["cited_news_ids"]), visible)
            if event["kind"] == "swap_receipt":
                self.check_swap(event, index, broadcast, last_reserves)
                last_reserves = event["reserves_after"]
        self.assertEqual(len(visible), 5)
        self.assertEqual(candles(events), json.loads((directory / "prices.json").read_text()))
        self.assertEqual(summarize(events), json.loads((directory / "costs_and_stats.json").read_text()))

    def check_swap(self, event, index, broadcast, last_reserves):
        receipt = event["receipt"]
        tx_hash = event["tx_hash"]
        self.assertEqual(receipt["transactionHash"], tx_hash)
        self.assertEqual(receipt["from"], event["account"])
        self.assertEqual(receipt["to"], event["pool"])
        self.assertEqual(receipt["status"], "0x1")
        self.assertTrue(all(event["checks"].values()))
        self.assertEqual(broadcast[tx_hash]["order_id"], event["order_id"])
        self.assertEqual(index[event["risk_id"]]["result"], "accepted")
        self.assertEqual(index[event["risk_id"]]["order_id"], event["order_id"])
        self.assertEqual(event["reserves_before"], last_reserves)
        pool_logs = [log for log in receipt["logs"] if log["address"] == event["pool"]]
        self.assertEqual(len(pool_logs), 1)
        data = pool_logs[0]["data"][2:]
        values = [int(data[offset:offset + 64], 16) for offset in range(0, len(data), 64)]
        symbol = event["token_in"]
        amount = int(event["amount_in_raw"])
        output = int(event["amount_out_raw"])
        self.assertEqual(values, [int(symbol == "RISK"), amount, output,
                                  int(event["reserves_after"]["RISK"]), int(event["reserves_after"]["sUSD"])])
        self.assertEqual(expected_output(last_reserves, symbol, amount), output)
        self.assertEqual(int(last_reserves[opposite(symbol)]) - int(event["reserves_after"][opposite(symbol)]),
                         output)
        self.assertEqual(int(last_reserves[symbol]) + amount, int(event["reserves_after"][symbol]))

    def test_independent_runs_have_matching_prefix(self):
        small = read_events(ARCHIVES / "first-10")
        large = read_events(ARCHIVES / "first-100")
        self.assertTrue(compare(small, large, 10))
        self.assertNotEqual(next(e["tx_hash"] for e in small if e["kind"] == "swap_receipt"),
                            next(e["tx_hash"] for e in large if e["kind"] == "swap_receipt"))


    def test_long_run_every_receipt_reconciles_from_raw_logs(self):
        from src.archive import verify

        directory = ARCHIVES / "stage2-rotate-1000"
        verify(directory)
        events = read_events(directory)
        index = {e["id"]: e for e in events}
        broadcast = {e["tx_hash"]: e for e in events if e["kind"] == "swap_broadcast"}
        reserves = next(e["reserves"] for e in events if e["kind"] == "market_open")
        receipts = [e for e in events if e["kind"] == "swap_receipt"]
        self.assertEqual(len(receipts), 1219)
        for event in receipts:
            self.check_swap(event, index, broadcast, reserves)
            reserves = event["reserves_after"]
        self.assertEqual(candles(events), json.loads((directory / "prices.json").read_text()))
        self.assertEqual(summarize(events), json.loads((directory / "costs_and_stats.json").read_text()))
