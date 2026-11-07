"""Derive price, evidence and strategy statistics from the event journal."""
from collections import Counter, defaultdict, deque
from decimal import Decimal
import json

from .chain import ROOT, UNIT
from .events import write_json
from .execution import BPS, gas_cost


def candles(events):
    rounds = {}
    for event in events:
        turn = event["round"]
        if event["kind"] == "reference":
            rounds[turn] = dict(round=turn, simulated_at=event["simulated_at"], reference=event["price"], fills=[])
        if event["kind"] == "swap_receipt" and event["success"] and turn in rounds:
            rounds[turn]["fills"].append(event)
    for row in rounds.values():
        fills = row.pop("fills")
        prices = [Decimal(fill["price_susd_per_risk"]) for fill in fills]
        values = (prices[0], max(prices), min(prices), prices[-1]) if prices else (None,) * 4
        row.update({key: str(value) if value is not None else None
                    for key, value in zip(("open", "high", "low", "close"), values)})
        row.update(trades=len(fills), event_ids=[fill["id"] for fill in fills])
    return list(rounds.values())


def summarize(events):
    stats = defaultdict(lambda: dict(orders=Counter(), risk=Counter(), fills=0, failed=0,
                                     impact_total=0, slippage_total=Decimal(0), fees=Counter(), gas=0, gas_used=0,
                                     realized=Decimal(0), positions=[]))
    costs = dict(setup_gas_wei=0, swap_gas_wei=0, calls=0, input_tokens=0, output_tokens=0, cost_usd=Decimal(0))
    refs = {}
    lots = defaultdict(deque)
    risk_quotes = {}
    for event in events:
        kind, role = event["kind"], event.get("role")
        if kind == "setup_receipt":
            costs["setup_gas_wei"] += gas_cost(event["receipt"])
        elif kind == "decision":
            stats[role]["orders"][event["intent"]["action"]] += 1
            for key in ("calls", "input_tokens", "output_tokens"):
                costs[key] += event["usage"][key]
            costs["cost_usd"] += Decimal(event["usage"]["cost_usd"])
        elif kind == "risk":
            stats[role]["risk"][event["result"]] += 1
            if event["result"] == "accepted":
                risk_quotes[event["id"]] = Decimal(event["decision_quote_out_raw"])
        elif kind == "reference":
            refs[event["round"]] = Decimal(event["price"])
        elif kind == "round_open" and event["round"] == 1:
            for actor, wallet in event["wallets"].items():
                price = Decimal(event["reserves"]["sUSD"]) / Decimal(event["reserves"]["RISK"])
                lots[actor].append((int(wallet["RISK"]), price))
                stats[actor]["initial_nav"] = str(nav(wallet, price))
        elif kind == "swap_receipt":
            costs["swap_gas_wei"] += int(event["gas_cost_wei"])
            if not role:
                continue
            entry = stats[role]
            entry["gas"] += int(event["gas_cost_wei"])
            entry["gas_used"] += event["gas_used"]
            if not event["success"]:
                entry["failed"] += 1
                continue
            entry["fills"] += 1
            entry["fees"][event["token_in"]] += int(event["fee_in_raw"])
            entry["impact_total"] += event["impact_bps"]
            baseline = risk_quotes[event["risk_id"]]
            entry["slippage_total"] += (baseline - Decimal(event["amount_out_raw"])) * BPS / baseline
            entry["realized"] += account_fill(lots[role], event)
        elif kind == "round_close":
            for actor, wallet in event["wallets"].items():
                ref = refs[event["round"]]
                cost_basis = sum((quantity * price for quantity, price in lots[actor]), Decimal(0)) / UNIT
                stats[actor]["positions"].append(dict(
                    round=event["round"], event_id=event["id"], nav=str(nav(wallet, ref)),
                    fills=stats[actor]["fills"],
                    risk_raw=wallet["RISK"], susd_raw=wallet["sUSD"],
                    unrealized_pnl=str(Decimal(wallet["RISK"]) * ref / UNIT - cost_basis),
                ))
    for entry in stats.values():
        attempts = entry["orders"]["buy"] + entry["orders"]["sell"]
        entry["fill_rate"] = entry["fills"] / attempts if attempts else None
        entry["mean_impact_bps"] = entry.pop("impact_total") / entry["fills"] if entry["fills"] else None
        slippage_total = entry.pop("slippage_total")
        entry["mean_execution_slippage_bps"] = str(slippage_total / entry["fills"]) if entry["fills"] else None
        entry["realized_pnl"] = str(entry.pop("realized"))
        entry["fee_raw"] = {token: str(amount) for token, amount in entry.pop("fees").items()}
        entry["gas_wei"] = str(entry.pop("gas"))
        if entry["positions"]:
            peak = Decimal(entry["initial_nav"])
            drawdown = Decimal(0)
            for position in entry["positions"]:
                value = Decimal(position["nav"])
                peak = max(peak, value)
                drawdown = max(drawdown, (peak - value) / peak)
                position["max_drawdown"] = str(drawdown)
            entry["max_drawdown"] = str(drawdown)
    for key in ("setup_gas_wei", "swap_gas_wei", "cost_usd"):
        costs[key] = str(costs[key])
    return dict(costs=costs, roles=dict(stats))


def nav(wallet, reference):
    return (Decimal(wallet["sUSD"]) + Decimal(wallet["RISK"]) * reference) / UNIT


def account_fill(lots, event):
    amount = int(event["amount_in_raw"])
    output = int(event["amount_out_raw"])
    price = Decimal(event["price_susd_per_risk"])
    if event["token_in"] == "sUSD":
        lots.append((output, price))
        return Decimal(0)
    cost = Decimal(0)
    while amount:
        quantity, basis = lots.popleft()
        consumed = min(quantity, amount)
        cost += consumed * basis
        amount -= consumed
        if consumed < quantity:
            lots.appendleft((quantity - consumed, basis))
    return (output - cost) / UNIT


def export_run(directory, events, *, compact=False):
    series = candles(events)
    stats = summarize(events)
    for filename, kinds in ({} if compact else {
        "news.json": {"news"},
        "orders.json": {"decision", "risk"},
        "receipts.json": {"setup_receipt", "swap_receipt", "swap_receipt_unreconciled"},
    }).items():
        write_json(directory / filename, [event for event in events if event["kind"] in kinds])
    write_json(directory / "prices.json", series)
    write_json(directory / "costs_and_stats.json", stats)
    template = ROOT / "app/report.html"
    if not compact and template.exists():
        payload = json.dumps(dict(run=directory.name, series=series, events=events, stats=stats), ensure_ascii=False)
        (directory / "index.html").write_text(
            template.read_text().replace("/* RUN_DATA */null", payload.replace("<", "\\u003c"), 1),
            encoding="utf-8",
        )


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    from .events import read_events

    parser = argparse.ArgumentParser(description="Rebuild derived files from an archived event journal")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    export_run(args.directory, read_events(args.directory), compact=args.compact)
