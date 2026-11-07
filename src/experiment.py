"""Run the offline experiment with a fresh chain and a single event writer."""
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from random import Random

from .agents import AGENTS, Context, Headline
from .chain import Anvil, Market, UNIT
from .execution import BPS, FEE_BPS, execute, expected_output, impact_bps, spot


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("experiment timestamps must be UTC")
    return parsed


def fixture_hash(row):
    payload = {key: value for key, value in row.items() if key != "source_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_news(rows):
    ids = set()
    for row in rows:
        if row["news_id"] in ids or fixture_hash(row) != row["source_hash"]:
            raise ValueError(f"invalid fixture identity/hash: {row['news_id']}")
        if parse_time(row["published_at"]) > parse_time(row["available_at"]):
            raise ValueError(f"published after available: {row['news_id']}")
        ids.add(row["news_id"])


def release_news(rows, at, released):
    return [row for row in rows if row["news_id"] not in released
            and parse_time(row["published_at"]) <= at and parse_time(row["available_at"]) <= at]


def validate_config(config, models):
    if config["fee_bps"] != FEE_BPS:
        raise ValueError("fee_bps must match the contract's fixed 30 bps")
    for key in ("round_seconds", "pool_risk", "pool_susd", "agent_risk", "agent_susd", "trade_size"):
        value = config[key]
        if type(value) is not int or not 0 < value <= 10**12:
            raise ValueError(f"{key} must be a positive integer up to 10^12")
    for key in ("trade_limit_bps_of_initial_input_reserve", "max_price_impact_bps", "execution_slippage_bps"):
        if type(config[key]) is not int or not 0 <= config[key] < BPS:
            raise ValueError(f"{key} must be between 0 and 9999")
    parse_time(config["start_at"])
    if models["mode"] != "mock":
        raise ValueError("only offline mock mode is implemented")


def risk_gate(intent, config, opening, current, wallet):
    if intent.action == "hold":
        return "hold", {}
    token = intent.token_in
    if (intent.action, token) not in (("buy", "sUSD"), ("sell", "RISK")):
        return "asset_or_action", {}
    amount = int(intent.amount_raw)
    initial = config["pool_risk"] if token == "RISK" else config["pool_susd"]
    cap = initial * UNIT * config["trade_limit_bps_of_initial_input_reserve"] // BPS
    if not 0 < amount <= cap:
        return "trade_limit", {"max_amount_raw": str(cap)}
    if amount > int(wallet[token]):
        return "balance", {}
    if not 0 <= intent.max_slippage_bps <= config["execution_slippage_bps"]:
        return "slippage_limit", {}
    initial_quote = expected_output(opening, token, amount)
    quote = expected_output(current, token, amount)
    minimum = max(1, (initial_quote * (BPS - intent.max_slippage_bps) + BPS - 1) // BPS)
    impact = impact_bps(current, token, amount, quote)
    fields = dict(quoted_out_raw=str(quote), decision_quote_out_raw=str(initial_quote),
                  min_out_raw=str(minimum), impact_bps=impact)
    if impact > config["max_price_impact_bps"]:
        return "price_impact", fields
    if quote < minimum:
        return "execution_slippage", fields
    return "accepted", fields


def run_market(directory, store, config, news, rounds):
    rng = Random(config["seed"])
    released = set()
    seen = []
    start = parse_time(config["start_at"])
    reference = Decimal(config["pool_susd"]) / Decimal(config["pool_risk"])
    with Anvil(directory) as chain:
        store.record("chain_started", source="anvil_rpc", client=chain.client, chain_id=chain.chain_id)
        market = Market(chain, store.record)
        traders = {agent.role: account for agent, account in zip(AGENTS, chain.accounts[1:])}
        if len(traders) != len(AGENTS):
            raise RuntimeError("insufficient Anvil development accounts")
        store.record("participants", roles=traders, models={agent.role: agent.model for agent in AGENTS})
        market.setup(config, traders.values())
        previous = spot(market.reserves())
        for turn in range(1, rounds + 1):
            at = start + timedelta(seconds=(turn - 1) * config["round_seconds"])
            store.round, store.simulated_at = turn, at.isoformat()
            fresh = release_news(news, at, released)
            for row in fresh:
                released.add(row["news_id"])
                seen.append(row)
                store.record("news", source="offline_example_fixture", **row)
            shock = sum(row["reference_shock_bps"] for row in fresh)
            reference = reference * (BPS + shock) / BPS
            store.record("reference", source="synthetic_reference_rule", price=str(reference),
                         shock_bps=shock, news_ids=[row["news_id"] for row in fresh])
            opening = market.reserves()
            initial_wallets = {role: market.balances(account) for role, account in traders.items()}
            draw = rng.choice((-5, -1, -1, 0, 0, 1, 1, 5))
            store.record("round_open", reserves=opening, wallets=initial_wallets, background_draw=draw)
            fresh_headlines = headlines(fresh)
            visible_headlines = headlines(seen)
            for agent in AGENTS:
                # Other roles decide from the same pre-order state, even though orders execute sequentially.
                decision_reserves = market.reserves() if agent.role == "arbitrage" else opening
                own = initial_wallets[agent.role]
                context = Context(turn, spot(decision_reserves), previous, reference, fresh_headlines,
                                  visible_headlines, tuple(own.items()), config["trade_size"] * UNIT,
                                  config["execution_slippage_bps"], draw if agent.role == "background" else 0)
                process_order(store, config, market, traders[agent.role], agent, context, decision_reserves)
            previous = spot(opening)
            store.record("round_close", source="anvil_rpc", reserves=market.reserves(),
                         wallets={role: market.balances(account) for role, account in traders.items()})
    store.record("run_complete", rounds=rounds)


def headlines(rows):
    return tuple(Headline(row["news_id"], row["title"], row["content_excerpt"], row["reference_shock_bps"])
                 for row in rows)


def process_order(store, config, market, account, agent, context, decision_reserves):
    intent = agent.decide(context)
    actor = dict(role=agent.role, model=agent.model, account_address=account)
    order_id = store.record(
        "decision", source="local_decision_adapter", intent=asdict(intent), **actor,
        input_snapshot=dict(spot=str(context.spot), previous_open_spot=str(context.previous_open_spot),
                            reference=str(context.reference), wallet=dict(context.own_wallet),
                            decision_reserves=decision_reserves,
                            visible_news_ids=[news.news_id for news in context.visible_news]),
        usage={"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": "0"},
    )
    current = market.reserves()
    wallet = market.balances(account)
    result, fields = risk_gate(intent, config, decision_reserves, current, wallet)
    risk_id = store.record("risk", source="local_risk_gate", order_id=order_id, result=result,
                           reserves=current, wallet=wallet, **actor, **fields)
    if result == "accepted":
        execute(market, account, intent.token_in, int(intent.amount_raw), int(fields["min_out_raw"]),
                store.record, order_id=order_id, risk_id=risk_id, **actor)
