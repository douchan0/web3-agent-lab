"""Integer arithmetic and post-receipt reconciliation for the teaching AMM."""
from decimal import Decimal

from .chain import SYMBOLS

BPS = 10_000
FEE_BPS = 30


def opposite(symbol):
    return SYMBOLS[1 - SYMBOLS.index(symbol)]


def expected_output(reserves, symbol, amount):
    weighted = amount * (BPS - FEE_BPS)
    return weighted * int(reserves[opposite(symbol)]) // (int(reserves[symbol]) * BPS + weighted)


def spot(reserves):
    return Decimal(reserves["sUSD"]) / Decimal(reserves["RISK"])


def impact_bps(reserves, symbol, amount, out):
    # Loss vs pre-trade marginal price, including pool fee.
    fair_numerator = amount * int(reserves[opposite(symbol)])
    loss = fair_numerator - out * int(reserves[symbol])
    return (loss * BPS + fair_numerator - 1) // fair_numerator


def gas_cost(receipt):
    return int(receipt["gasUsed"], 16) * int(receipt["effectiveGasPrice"], 16)


def execute(market, account, symbol, amount, min_out, record, **context):
    before = market.reserves()
    wallet_before = market.balances(account)
    chain = market.chain
    eth_before = int(chain.rpc("eth_getBalance", account, "latest"), 16)
    details = dict(context, source="anvil_rpc", account=account, pool=market.pool, token_in=symbol,
                   amount_in_raw=str(amount), min_out_raw=str(min_out), reserves_before=before,
                   wallet_before=wallet_before, eth_before_wei=str(eth_before))
    receipt = market.swap(account, symbol, amount, min_out,
                          lambda tx_hash: record("swap_broadcast", tx_hash=tx_hash, **details))
    try:
        after = market.reserves()
        wallet_after = market.balances(account)
        pool_balances = market.balances(market.pool)
        eth_after = int(chain.rpc("eth_getBalance", account, "latest"), 16)
    except BaseException:
        record("swap_receipt_unreconciled", tx_hash=receipt["transactionHash"], receipt=receipt, **details)
        raise
    success = receipt["status"] == "0x1"
    other = opposite(symbol)
    output = int(wallet_after[other]) - int(wallet_before[other])
    checks = {
        "gas": eth_before - eth_after == gas_cost(receipt),
        "pool_balance_equals_reserves": pool_balances == after,
    }
    if success:
        checks.update(
            swap_log=any(log["address"].lower() == market.pool.lower() for log in receipt["logs"]),
            amount_matches_formula=output > 0 and output == expected_output(before, symbol, amount),
            input_conserved=int(wallet_before[symbol]) - int(wallet_after[symbol]) == amount
            and int(after[symbol]) - int(before[symbol]) == amount,
            output_conserved=int(before[other]) - int(after[other]) == output,
            k_non_decreasing=int(after["RISK"]) * int(after["sUSD"])
            >= int(before["RISK"]) * int(before["sUSD"]),
            min_out=output >= min_out,
        )
    else:
        checks["revert_atomic"] = before == after and wallet_before == wallet_after
    price = None
    if success and output > 0:
        price = Decimal(output) / amount if symbol == "RISK" else Decimal(amount) / output
    event_id = record(
        "swap_receipt", tx_hash=receipt["transactionHash"], receipt=receipt, success=success,
        reserves_after=after, wallet_after=wallet_after, eth_after_wei=str(eth_after),
        amount_out_raw=str(output), price_susd_per_risk=str(price) if price is not None else None,
        spot_before=str(spot(before)), spot_after=str(spot(after)),
        fee_in_raw=str(amount * FEE_BPS // BPS) if success else "0",
        gas_used=int(receipt["gasUsed"], 16), gas_cost_wei=str(gas_cost(receipt)),
        impact_bps=impact_bps(before, symbol, amount, output) if success else None,
        checks=checks, **details,
    )
    if not all(checks.values()):
        raise RuntimeError(f"chain reconciliation failed for {event_id}")
    return receipt
