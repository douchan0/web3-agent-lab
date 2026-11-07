from decimal import Decimal
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import unittest

from src.agents import AGENTS
from src.archive import seal, verify
from src.experiment import ordered_agents
from src.paired import paired_summary


class ResearchTests(unittest.TestCase):
    def test_seal_detects_altered_data(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            for name in ("config.json","events.jsonl","status.json"):
                (path / name).write_text("{}\n")
            seal(path)
            self.assertEqual(verify(path),3)
            (path / "events.jsonl").write_text('[]\n')
            with self.assertRaisesRegex(ValueError,"integrity"):
                verify(path)

    def test_rotations_and_seeded_shuffle_keep_arbitrage_last(self):
        fixed = ordered_agents(AGENTS,"fixed",2,Random(42))
        rotated = ordered_agents(AGENTS,"rotate",2,Random(42))
        self.assertNotEqual(fixed[0],rotated[0])
        self.assertEqual(fixed[-1],rotated[-1])
        self.assertEqual(ordered_agents(AGENTS,"random",2,Random(42)),
                         ordered_agents(AGENTS,"random",2,Random(42)))

    def test_exact_sign_test_uses_paired_nonzero_samples(self):
        result = paired_summary(list(map(Decimal,[1,1,1,1,0])))
        self.assertEqual(result["n"],5)
        self.assertEqual(result["nonzero"],4)
        self.assertEqual(result["sign_test_p"],.125)
        self.assertEqual(result["mean"],Decimal(".8"))

    def test_mark_to_same_reference_and_ignore_undefined_slippage(self):
        from src.analytics import summarize
        from src.chain import UNIT

        wallet = {"RISK":str(UNIT),"sUSD":str(UNIT)}
        events = [
            {"kind":"reference","round":1,"price":"2"},
            {"kind":"round_open","round":1,"wallets":{"trend":wallet},"reserves":wallet},
            {"kind":"risk","role":"trend","result":"accepted","id":"E1","decision_quote_out_raw":"0"},
            {"kind":"swap_receipt","role":"trend","success":True,"risk_id":"E1","gas_cost_wei":"0",
             "gas_used":0,"token_in":"sUSD","fee_in_raw":"0","impact_bps":1,"price_susd_per_risk":"2",
             "amount_in_raw":"2","amount_out_raw":"1"},
            {"kind":"round_close","round":1,"id":"E2","wallets":{"trend":wallet}},
        ]
        row = summarize(events)["roles"]["trend"]
        self.assertEqual(row["initial_nav"],"3")
        self.assertEqual(row["positions"][0]["nav"],"3")
        self.assertIsNone(row["mean_execution_slippage_bps"])
