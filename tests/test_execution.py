from unittest import TestCase
from unittest.mock import Mock

from src.execution import execute


class ExecutionFailureTests(TestCase):
    def test_mined_receipt_survives_unavailable_state(self):
        receipt = {"transactionHash": "test-hash", "status": "0x1"}
        market = Mock()
        market.reserves.side_effect = [{"RISK": "100", "sUSD": "100"}, TimeoutError()]
        market.balances.return_value = {"RISK": "20", "sUSD": "20"}
        market.chain.rpc.return_value = "0x100"

        def swap(*args):
            args[-1](receipt["transactionHash"])
            return receipt

        market.swap.side_effect = swap
        record = Mock()
        with self.assertRaises(TimeoutError):
            execute(market, "dev-account", "RISK", 10, 1, record)
        broadcast, archived = record.call_args_list
        self.assertEqual(broadcast.args[0], "swap_broadcast")
        self.assertEqual(archived.args[0], "swap_receipt_unreconciled")
        self.assertEqual(archived.kwargs["receipt"], receipt)
