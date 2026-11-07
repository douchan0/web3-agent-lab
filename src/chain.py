"""Use only a child Anvil and its unlocked development accounts."""
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
UNIT = 10**18
MAX_UINT = 2**256 - 1
SYMBOLS = ("RISK", "sUSD")


def anvil_binary():
    packaged = ROOT / "node_modules/.bin/anvil"
    binary = os.environ.get("ANVIL_BIN") or shutil.which("anvil")
    if binary:
        return str(Path(binary).resolve())
    if packaged.exists():
        return str(packaged)
    raise FileNotFoundError("Anvil missing. Run npm ci or set ANVIL_BIN.")


def word(value):
    if isinstance(value, str):
        value = int(value, 16)
    return int(value).to_bytes(32, "big").hex()


class Anvil:
    def __init__(self, directory):
        self.directory = directory
        self.chain_id = 100_000 + secrets.randbelow(2_000_000_000)
        self.process = None
        self.connection = None
        self.counter = 0

    def __enter__(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.connection = HTTPConnection("127.0.0.1", port, timeout=5)
        args = [anvil_binary(), "--host", "127.0.0.1", "--port", str(port),
                "--chain-id", str(self.chain_id), "--hardfork", "cancun", "--silent"]
        with (self.directory / "anvil.stderr.log").open("w") as log:
            self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
        try:
            for _ in range(100):
                if self.process.poll() is not None:
                    raise RuntimeError("Anvil exited during startup; see anvil.stderr.log")
                try:
                    self.client = self.rpc("web3_clientVersion")
                except OSError:
                    time.sleep(0.05)
                    continue
                if "anvil" not in self.client.lower() or int(self.rpc("eth_chainId"), 16) != self.chain_id:
                    raise RuntimeError("Unexpected local node identity")
                self.accounts = self.rpc("eth_accounts")
                return self
            raise TimeoutError("Anvil did not become ready")
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.connection is not None:
            self.connection.close()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def rpc(self, method, *params):
        self.counter += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": self.counter}
        connection = self.connection
        try:
            connection.request("POST", "/", json.dumps(payload), {"Content-Type": "application/json"})
            with connection.getresponse() as response:
                if response.status != 200:
                    raise RuntimeError(f"{method}: unexpected HTTP status {response.status}")
                result = json.load(response)
        except Exception:
            # The outcome of a write can be uncertain. Clear the socket and surface the error.
            connection.close()
            raise
        if "error" in result:
            raise RuntimeError(f"{method}: {result['error']}")
        return result["result"]

    def call(self, address, data):
        return int(self.rpc("eth_call", {"to": address, "data": data}, "latest"), 16)

    def transact(self, sender, data, *, to=None, on_hash=lambda _: None):
        tx = {"from": sender, "data": data, "gas": hex(4_000_000)}
        if to:
            tx["to"] = to
        tx_hash = self.rpc("eth_sendTransaction", tx)
        on_hash(tx_hash)
        for _ in range(100):
            receipt = self.rpc("eth_getTransactionReceipt", tx_hash)
            if receipt is not None:
                return receipt
            time.sleep(0.05)
        raise TimeoutError(f"receipt unavailable: {tx_hash}")


class Market:
    def __init__(self, chain, record):
        self.chain = chain
        self.record = record
        self.artifacts = json.loads((ROOT / "build/contracts.json").read_text())
        self.tokens = {}
        self.pool = None

    def encode(self, contract, method, *args):
        evm = self.artifacts["contracts"][contract]["evm"]
        prefix = evm["bytecode"]["object"] if method is None else evm["methodIdentifiers"][method]
        return "0x" + prefix + "".join(map(word, args))

    def setup_tx(self, operation, sender, contract, method, *args, to=None, **details):
        payload = dict(operation=operation, account=sender, target=to, **details)
        receipt = self.chain.transact(
            sender, self.encode(contract, method, *args), to=to,
            on_hash=lambda tx_hash: self.record("setup_broadcast", tx_hash=tx_hash, **payload),
        )
        self.record("setup_receipt", receipt=receipt, tx_hash=receipt["transactionHash"], **payload)
        if receipt["status"] != "0x1":
            raise RuntimeError(f"setup reverted: {operation}")
        return receipt["contractAddress"]

    def setup(self, config, traders):
        admin = self.chain.accounts[0]
        balances = {"RISK": config["agent_risk"] * UNIT, "sUSD": config["agent_susd"] * UNIT}
        reserves = {"RISK": config["pool_risk"] * UNIT, "sUSD": config["pool_susd"] * UNIT}
        for symbol in SYMBOLS:
            supply = reserves[symbol] + len(traders) * balances[symbol]
            address = self.setup_tx("deploy_token", admin, "TestToken", None,
                                    symbol == "RISK", supply, symbol=symbol, supply_raw=str(supply))
            self.tokens[symbol] = address
        self.pool = self.setup_tx("deploy_pool", admin, "DemoPool", None, *self.tokens.values())
        for symbol, address in self.tokens.items():
            self.setup_tx("approve_seed", admin, "TestToken", "approve(address,uint256)", self.pool,
                          reserves[symbol], to=address, symbol=symbol, amount_raw=str(reserves[symbol]))
            for trader in traders:
                self.setup_tx("fund", admin, "TestToken", "transfer(address,uint256)", trader,
                              balances[symbol], to=address, symbol=symbol, recipient=trader,
                              amount_raw=str(balances[symbol]))
                self.setup_tx("approve_swap", trader, "TestToken", "approve(address,uint256)", self.pool,
                              MAX_UINT, to=address, symbol=symbol, amount_raw=str(MAX_UINT))
        self.setup_tx("seed", admin, "DemoPool", "seed(uint256,uint256)", *reserves.values(), to=self.pool)
        self.record("market_open", pool=self.pool, tokens=self.tokens, reserves=self.reserves(),
                    balances={account: self.balances(account) for account in traders})

    def balances(self, account):
        data = self.encode("TestToken", "balanceOf(address)", account)
        return {symbol: str(self.chain.call(address, data)) for symbol, address in self.tokens.items()}

    def reserves(self):
        return {
            symbol: str(self.chain.call(self.pool, self.encode("DemoPool", method)))
            for symbol, method in zip(SYMBOLS, ("reserveRisk()", "reserveSusd()"))
        }

    def quote(self, symbol, amount):
        return self.chain.call(self.pool, self.encode("DemoPool", "quote(bool,uint256)", symbol == "RISK", amount))

    def swap(self, account, symbol, amount, min_out, on_hash):
        data = self.encode("DemoPool", "swap(bool,uint256,uint256)", symbol == "RISK", amount, min_out)
        return self.chain.transact(account, data, to=self.pool, on_hash=on_hash)
