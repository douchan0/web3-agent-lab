from dataclasses import replace
from decimal import Decimal
import json
import unittest

from src.agents import Intent
from src.analytics import candles
from src.chain import ROOT, UNIT
from src.experiment import parse_time, release_news, risk_gate, validate_config, validate_news


class ProtocolTests(unittest.TestCase):
    def test_publication_alone_does_not_release_news(self):
        rows = json.loads((ROOT / "data/fixtures/news.json").read_text())
        validate_news(rows)
        self.assertEqual(release_news(rows, parse_time("2025-01-01T00:00:00Z"), set()), [])
        self.assertEqual([row["news_id"] for row in release_news(
            rows, parse_time("2025-01-01T00:03:00Z"), {"N01"})], ["N02"])
        rows[0]["title"] = "tampered"
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_news(rows)

    def test_risk_caps_and_moved_quote(self):
        config = json.loads((ROOT / "configs/experiment.json").read_text())
        opening = {symbol: str(10_000 * UNIT) for symbol in ("RISK", "sUSD")}
        current = {"RISK": str(9_950 * UNIT), "sUSD": str(10_050 * UNIT)}
        wallet = {"RISK": str(250 * UNIT), "sUSD": str(250 * UNIT)}
        intent = Intent("buy", "sUSD", str(18 * UNIT), 30, None, "test", ())
        self.assertEqual(risk_gate(intent, config, opening, opening, wallet)[0], "accepted")
        self.assertEqual(risk_gate(intent, config, opening, current, wallet)[0], "execution_slippage")
        self.assertEqual(risk_gate(replace(intent, amount_raw=str(100 * UNIT)),
                                   config, opening, current, wallet)[0], "trade_limit")
        self.assertEqual(risk_gate(intent, config, opening, opening, dict(wallet, sUSD="0"))[0], "balance")

    def test_candles_skip_reverts_and_preserve_empty_round(self):
        refs = [dict(kind="reference", round=turn, simulated_at="test", price="1") for turn in (1, 2)]
        fills = [dict(kind="swap_receipt", round=1, success=success, price_susd_per_risk=price, id=key)
                 for success, price, key in [(True, "1", "a"), (False, "9", "b"), (True, "1.2", "c")]]
        first, second = candles(refs + fills)
        self.assertEqual(first["event_ids"], ["a", "c"])
        self.assertEqual(Decimal(first["high"]), Decimal("1.2"))
        self.assertIsNone(second["open"])

    def test_config_rejects_unrecognized_fields_before_snapshot(self):
        config = json.loads((ROOT / "configs/experiment.json").read_text())
        models = json.loads((ROOT / "configs/models.example.json").read_text())
        validate_config(config, models)
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            validate_config(dict(config, unexpected_field="example"), models)
        models["models"]["mock-v1"]["unexpected_field"] = "example"
        with self.assertRaisesRegex(ValueError, "budget"):
            validate_config(config, models)
