"""Generate a Chinese teaching report from the archived Anvil event journal."""
import argparse
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .analytics import candles, summarize
from .chain import UNIT
from .events import read_events

LABELS = {"trend": "趋势", "event": "事件", "contrarian": "逆向", "background": "背景", "arbitrage": "套利"}


def amount(raw, digits=6):
    return f"{Decimal(raw) / UNIT:.{digits}f}"


def report(directory: Path):
    events = read_events(directory)
    complete = next(e for e in events if e["kind"] == "run_complete")
    first = next((e for e in events if e["kind"] == "swap_receipt" and e["success"]), None)
    setup = [e for e in events if e["kind"] == "setup_receipt"]
    seed = next(e for e in setup if e["operation"] == "seed")
    funding = next(e for e in setup if e["operation"] == "fund")
    deployed = [e for e in setup if e["operation"] in ("deploy_token", "deploy_pool")]
    chain = next(e for e in events if e["kind"] == "chain_started")
    participants = next(e for e in events if e["kind"] == "participants")
    result = summarize(events)
    prices = candles(events)
    decisions = [e for e in events if e["kind"] == "decision"]
    news = [e for e in events if e["kind"] == "news"]
    fills = [e for e in events if e["kind"] == "swap_receipt" and e["success"]]
    reverts = [e for e in events if e["kind"] == "swap_receipt" and not e["success"]]
    rejected = [e for e in events if e["kind"] == "risk" and e["result"] not in ("accepted", "hold")]
    reasons = Counter(e["result"] for e in rejected)
    costs = result["costs"]
    lines = [
        f"# {directory.name} 中文实验报告", "",
        f"本轮完成 {complete['rounds']} 轮，归档 {len(decisions)} 次决策、{len(fills)} 笔成功兑换、"
        f"{len(rejected)} 笔风控拒单和 {len(reverts)} 笔链上回退。K 线有 "
        f"{sum(row['trades'] > 0 for row in prices)} 个成交轮。链 ID 为 `{chain['chain_id']}`，"
        "模型为离线 mock，新闻及参考价为样例，合约执行来自本地 Anvil。", "",
        "[交互图与事件选择器](index.html) · [原始事件](events.jsonl) · [配置快照](config.json)"
        " · [原始回执](receipts.json) · [OHLC](prices.json) · [成本与统计](costs_and_stats.json)", "",
        "## 账户、测试币和流动性", "",
        f"账户在链上用地址标识。控制器用 Anvil 解锁的开发账户提交交易。参与者映射见 "
        f"[{participants['id']}](index.html#{participants['id']})。事件 "
        f"[{funding['id']}](index.html#{funding['id']}) 的 ERC-20 Transfer 日志记录 "
        f"`{funding['recipient']}` 收到 {amount(funding['amount_raw'])} {funding['symbol']}。"
        "代币余额与用于 Gas 的开发 ETH 余额分别存储。", "",
    ]
    for event in deployed:
        name = event.get("symbol", "V2-style demo 池")
        lines.append(f"- {name} 部署于 `{event['receipt']['contractAddress']}`。"
                     f"[{event['id']}](index.html#{event['id']})")
    lines.extend(["", f"池由部署者一次性授权并注资。种子交易 "
                  f"[{seed['id']}](index.html#{seed['id']}) 的合约日志和后续池开盘快照记录了流动性。"
                  "合约入口见 [Market.sol](../../../contracts/Market.sol)。", ""])
    if first:
        lines.extend(explain_swap(first))
    else:
        lines.extend(["## 交易", "", "本轮无成功兑换，所有轮次的 OHLC 留空。", ""])
    lines.extend(["## 新闻与参考价", "",
                  "参考输入在控制器中作为可审计的预言机通道。样例没有外部新闻机构来源。"
                  "控制器校验内容 SHA-256，再同时检查发表时间与可见时间。"
                  "样例信号按规则调整合成参考价；成交价和池内即期价分别由兑换金额和链上储备计算。"
                  "历史模式需要保存外部来源、实际发表时间和抓取快照。", "",
                  "| 样例 | 发表 UTC | 可见 UTC | 来源与事件 |", "| --- | --- | --- | --- |"])
    for event in news:
        lines.append(f"| {event['news_id']} {event['title']} | {event['published_at']} | {event['available_at']} "
                     f"| `{event['source_url']}` · [{event['id']}](index.html#{event['id']}) |")
    lines.extend(["", "## 策略行为与成本", "",
                  "| 角色 | 买意图 | 卖意图 | 观望 | 成交 | 期末参考价净值 | 已实现 / 未实现盈亏 | 最大回撤 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for role, row in result["roles"].items():
        end = row["positions"][-1]
        orders = row["orders"]
        lines.append(f"| {LABELS[role]} | {orders['buy']} | {orders['sell']} | {orders['hold']} | {row['fills']} | "
                     f"{Decimal(end['nav']):.3f} | {Decimal(row['realized_pnl']):.3f} / "
                     f"{Decimal(end['unrealized_pnl']):.3f} | {Decimal(row['max_drawdown']):.2%} |")
    lines.extend(["", "三种 mock 策略共用公开开盘快照。趋势跟随前一轮到本轮的开盘池价变化，逆向在变动达到"
                  "自己的阈值时反向操作，事件策略只响应当轮首次可见的样例信号。"
                  "买入 RISK 会降低池内 RISK 储备并提高即期价格，卖出反之。套利角色根据参考价偏差下单，"
                  "其成交也会改变下一轮看到的储备。下列案例展示了各策略对应的真实交易。", ""])
    for role in ("trend", "event", "contrarian", "arbitrage"):
        fill = next((e for e in fills if e["role"] == role), None)
        if fill:
            lines.append(f"- {LABELS[role]}在第 {fill['round']} 轮兑换 {amount(fill['amount_in_raw'])} "
                         f"{fill['token_in']}，池价 {Decimal(fill['spot_before']):.6f} → "
                         f"{Decimal(fill['spot_after']):.6f} sUSD/RISK。"
                         f"[决策 {fill['order_id']}](index.html#{fill['order_id']}) · "
                         f"[回执 {fill['id']}](index.html#{fill['id']})")
    if rejected:
        e = rejected[0]
        counts = "、".join(f"`{key}` {value} 笔" for key, value in reasons.items())
        lines.extend(["", f"拒单原因包括 {counts}。首笔拒单见 [{e['id']}](index.html#{e['id']})。"])
    lines.extend(["", f"布置与注资共消耗 {costs['setup_gas_wei']} wei，兑换共消耗 "
                  f"{costs['swap_gas_wei']} wei，均为开发 ETH。模型调用 {costs['calls']} 次，"
                  f"输入／输出 token 为 {costs['input_tokens']} / {costs['output_tokens']}，"
                  f"记录的 API 费用为 {costs['cost_usd']} USD。池费分代币计量。"
                  "净值以统一参考价计量，已实现盈亏按 FIFO，起始 RISK 按初始储备比计成本。"
                  "净值与盈亏未折入开发 ETH Gas。", "",
                  "固定先后顺序、单池和单一随机种子限制了归因。后续可用相同新闻和种子配对运行深浅池，"
                  "再随机化执行顺序，最后在取得授权的渠道上替换同一角色的模型。", ""])
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")


def explain_swap(event):
    receipt = event["receipt"]
    direction = "sUSD" if event["token_in"] == "RISK" else "RISK"
    before = event["reserves_before"]
    after = event["reserves_after"]
    pre_k = int(before["RISK"]) * int(before["sUSD"])
    post_k = int(after["RISK"]) * int(after["sUSD"])
    return [
        "## 一笔链上兑换", "",
        f"[{event['id']}](index.html#{event['id']}) 在区块 {int(receipt['blockNumber'], 16)} 成功。"
        f"交易哈希为 `{event['tx_hash']}`，消耗 {event['gas_used']} Gas，"
        f"按有效 Gas 价格共扣除 {event['gas_cost_wei']} wei。"
        "交易回执包含状态、区块号及 ERC-20 Transfer 与池 Swap 日志。", "",
        f"钱包交出 {amount(event['amount_in_raw'])} {event['token_in']} 并收到 "
        f"{amount(event['amount_out_raw'])} {direction}。池储备从 "
        f"{amount(before['RISK'])} RISK / {amount(before['sUSD'])} sUSD 变成 "
        f"{amount(after['RISK'])} RISK / {amount(after['sUSD'])} sUSD。"
        f"0.30% 输入留费为 {amount(event['fee_in_raw'])} {event['token_in']}。"
        f"由整数储备计算的乘积 `k` 从 `{pre_k}` 增至 `{post_k}`。", "",
        "报价先从输入扣去计算用的手续费，再沿恒定乘积曲线计算输出，实际输入全额留在池中。"
        f"本笔相对交易前的池内边际价，含手续费的执行损失向上取整为 {event['impact_bps']} bps。"
        f"合约校验的最小输出为 {amount(event['min_out_raw'])} {direction}。"
        "前者衡量曲线与费用造成的损失，后者限制决策快照到执行的报价变动。"
        "对账可见 [execution.py](../../../src/execution.py)，"
        "最小输出回退可查 [独立链集成测试](../../../tests/chain-evidence/events.jsonl)。", "",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    report(parser.parse_args().directory)


if __name__ == "__main__":
    main()
