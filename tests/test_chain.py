import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.chain import Anvil, Market, ROOT, UNIT
from src.events import EventStore
from src.execution import execute, expected_output, opposite


class ChainIntegration(unittest.TestCase):
    def test_bidirectional_swap_and_min_out(self):
        evidence = os.environ.get("CHAIN_TEST_EVIDENCE")
        if evidence:
            directory = Path(evidence)
            directory.mkdir()
            self.exercise(directory)
        else:
            with TemporaryDirectory() as directory:
                self.exercise(Path(directory))

    def exercise(self, directory):
        config = json.loads((ROOT / "configs/experiment.json").read_text())
        with EventStore(directory) as store:
            try:
                with Anvil(directory) as chain:
                    store.record("chain_started", client=chain.client, chain_id=chain.chain_id)
                    market = Market(chain, store.record)
                    admin, trader = chain.accounts[:2]
                    market.setup(config, [trader])
                    for symbol in ("sUSD", "RISK"):
                        amount = 25 * UNIT
                        reserves = market.reserves()
                        quote = market.quote(symbol, amount)
                        self.assertEqual(quote, expected_output(reserves, symbol, amount))
                        no_fee = amount * int(reserves[opposite(symbol)]) // (int(reserves[symbol]) + amount)
                        self.assertLess(quote, no_fee)
                        receipt = execute(market, trader, symbol, amount, quote + 1, store.record)
                        self.assertEqual(receipt["status"], "0x0")
                        receipt = execute(market, trader, symbol, amount, quote, store.record)
                        self.assertEqual(receipt["status"], "0x1")
                    for symbol, token in market.tokens.items():
                        supply = chain.call(token, market.encode("TestToken", "totalSupply()"))
                        self.assertEqual(supply, sum(int(market.balances(account)[symbol])
                                                     for account in (admin, trader, market.pool)))
                    store.record("test_passed", case=self.id())
            except Exception as exc:
                store.record("error", error=repr(exc))
                raise
