"""Beginner narrative and research summary from one archived event stream."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from .analytics import candles, summarize
from .events import read_events
from .report import LABELS, amount


def generate(directory, events=None, stats=None):
    if events is None:
        events = read_events(directory)
    stats = stats or summarize(events)
    config = json.loads((directory / "config.json").read_text())
    status_path = directory / "status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    run = directory.name

    def evidence(event):
        return f"[{event['id']} · 第 {event['round']} 轮](/?run={run}&event={event['id']}#evidence)"

    grouped = {}
    for event in events:
        grouped.setdefault(event["kind"], []).append(event)
    initial = grouped["market_open"][0]
    last = grouped["round_close"][-1]
    fills = [e for e in grouped.get("swap_receipt", []) if e["success"]]
    failed = [e for e in grouped.get("swap_receipt", []) if not e["success"]]
    rejects = [e for e in grouped.get("risk", []) if e["result"] not in ("accepted", "hold")]
    refs = {e["round"]: e for e in grouped["reference"]}
    participants = grouped["participants"][0]
    markets = candles(events)
    first = fills[0] if fills else None
    story = [
        f"# {run} · 从市场开门讲起", "",
        "想象桌上有两个装着测试筹码的盒子。RISK 是风险资产，sUSD 是记账单位。"
        "盒子由一个智能合约管理。角色交换筹码，合约照公式给出数量，并把实际发生的事情写入本地 Anvil 链。", "",
        "## 先看第一幕：给市场和钱包装入筹码", "",
        f"池子起初存有 {amount(initial['reserves']['RISK'], 3)} RISK 和 "
        f"{amount(initial['reserves']['sUSD'], 3)} sUSD。用 sUSD 储备除以 RISK 储备可以得到起始池价。"
        f"这是一小笔交易会接近的边际价格。 [池与初始钱包](/?run={run}&event={initial['id']}#evidence)", "",
        "趋势角色看池价变化，事件角色等新消息，逆向角色在价格偏移时考虑反向操作。"
        "背景角色从固定种子抽样，套利角色比较池价和参考价。三个主角的基准行为由 mock 策略产生。"
        "每人有独立钱包，余额是两种测试币各自的数量。", "",
        "## 把重要事件按发生顺序放回桌面", "",
    ]
    index = {e["id"]: e for e in events}
    moments = list(grouped.get("news", []))
    if first:
        moments.append(first)
    if rejects:
        moments.append(rejects[0])
    for role in ("trend", "event", "contrarian", "arbitrage"):
        fill = next((e for e in fills if e["role"] == role), None)
        if fill:
            moments.append(fill)
    for event in sorted({e["id"]: e for e in moments}.values(), key=lambda e: e["id"]):
        kind = event["kind"]
        if kind == "news":
            story.extend([
                f"### 第 {event['round']} 轮 · {event['title']}", "",
                f"这条消息在 {event['published_at']} 发表，直到 {event['available_at']} 才进入角色信息集。"
                f"样例规则给参考价加入 {event['reference_shock_bps']:+d} bps，"
                f"该轮参考价变为 {Decimal(refs[event['round']]['price']):.6f} sUSD/RISK。"
                "池价还取决于随后是否真的有人兑换。 " + evidence(event), "",
            ])
        elif kind == "risk":
            reasons = {"trade_limit":"超过单笔上限", "balance":"余额不足", "execution_slippage":"报价变化超过限制",
                       "price_impact":"含费价格冲击过大"}
            decision = index[event["order_id"]]
            story.extend([
                f"### 第 {event['round']} 轮 · 一张订单被拦下", "",
                f"{LABELS[event['role']]}角色打算交出 {amount(decision['intent']['amount_raw'])} "
                f"{decision['intent']['token_in']}。风控发现{reasons.get(event['result'], event['result'])}，"
                "于是控制器没有提交这张订单，钱包和池没有因这张单发生兑换。 "
                f"{evidence(decision)} · {evidence(event)}", "",
            ])
        else:
            symbol = event["token_in"]
            other = "sUSD" if symbol == "RISK" else "RISK"
            decision = index[event["order_id"]]
            story.extend([
                f"### 第 {event['round']} 轮 · {LABELS[event['role']]}角色成交", "",
                f"公开理由是「{decision['intent']['public_rationale']}」角色交出 {amount(event['amount_in_raw'])} "
                f"{symbol}，换回 {amount(event['amount_out_raw'])} {other}。"
                f"兑换使这笔交易前后的池价从 {Decimal(event['spot_before']):.6f} 变为 "
                f"{Decimal(event['spot_after']):.6f}。合约给了这笔操作自己的回执，里面有区块 "
                f"{int(event['receipt']['blockNumber'],16)}、Gas {event['gas_used']:,} 和钱包、池子的前后状态。"
                f" 试着在回执中比较两个储备。 {evidence(decision)} · {evidence(event)}", "",
            ])
    story.extend([
        "## 收盘后，怎么比较角色的资产？", "",
        f"共看到 {last['round']} 轮、{len(fills)} 笔成交、{len(rejects)} 次风控拒单和 {len(failed)} 次链上回退。"
        f"末轮参考价是 {Decimal(refs[last['round']]['price']):.6f}。"
        "把每人手里的 RISK 乘这个同一参考价，再加手里的 sUSD，就是表中的净值。"
        "最大回撤表示净值曾从先前高点下跌的最大比例。开发 ETH 的 Gas 另记。 " + evidence(last), "",
        "| 角色 | RISK | sUSD | 参考价净值 | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for role, row in stats["roles"].items():
        end = row["positions"][-1]
        story.append(f"| {LABELS[role]} | {amount(end['risk_raw'],4)} | {amount(end['susd_raw'],4)} | "
                     f"{Decimal(end['nav']):.4f} | {Decimal(end['max_drawdown']):.2%} |")
    story.extend([
        "", "一条新闻和一次价格变化前后相接，可能与同轮几位角色的订单有关。要追问新闻的作用，"
        "可以用相同种子和参数重跑对照，改变新闻条件后再比较。"
        "先试着用 AMM 练习复算第一笔，再解释为什么深浅两池的到账不同。 [数学实验](/#labs)", "",
    ])
    (directory / "story.md").write_text("\n".join(story), encoding="utf-8")

    costs = stats["costs"]
    parameters = config["experiment"]
    close_count = sum(row["trades"] > 0 for row in markets)
    questions = "在同一初始资金与消息输入下，角色的成交率、参考价收益和回撤如何不同？"
    research = [
        f"# {run} · 研究报告", "",
        f"研究问题。{questions} 机制假设为固定输入占浅池储备比例较高时，含费价格冲击较大。"
        "策略收益差异仅作为本档案的描述性观察。", "",
        f"完成 {last['round']} / {config['rounds']} 轮。成交 {len(fills)} 笔，活跃轮 {close_count}，"
        f"拒单 {len(rejects)} 笔，链上回退 {len(failed)} 笔。种子 {parameters['seed']}，"
        f"执行顺序 {config.get('order','fixed')}，初始储备 {parameters['pool_risk']} RISK / "
        f"{parameters['pool_susd']} sUSD，费率 {parameters['fee_bps']} bps。", "",
        "角色与决策实现版本为 " + "、".join(f"{LABELS[role]} {model}" for role, model in participants["models"].items())
        + "。决策快照保留每个角色合法可见的新闻 ID、参考价、池状态和自己的资产。背景抽样与执行顺序使用独立的随机源。", "",
        f"链上执行阶段 {status.get('execution_seconds','未计时')} 秒。布置 Gas {costs['setup_gas_wei']} wei，"
        f"兑换 Gas {costs['swap_gas_wei']} wei。模型调用 {costs['calls']} 次，输入／输出 token "
        f"{costs['input_tokens']} / {costs['output_tokens']}，记录费用 {costs['cost_usd']} USD。", "",
        "| 角色 | 成交 | 成交率 | 净值收益 | 最大回撤 | 平均含费冲击 bps | 平均执行滑点 bps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for role, row in stats["roles"].items():
        end = row["positions"][-1]
        ret = Decimal(end["nav"]) / Decimal(row["initial_nav"]) - 1
        percent = "—" if row["fill_rate"] is None else f"{row['fill_rate']:.1%}"
        impact = "—" if row["mean_impact_bps"] is None else f"{row['mean_impact_bps']:.2f}"
        slip = "—" if row["mean_execution_slippage_bps"] is None else f"{Decimal(row['mean_execution_slippage_bps']):.2f}"
        research.append(f"| {LABELS[role]} | {row['fills']} | {percent} | {ret:.3%} | {Decimal(end['max_drawdown']):.3%} | {impact} | {slip} |")
    reasons = Counter(e["result"] for e in rejects)
    research.extend([
        "", "拒单分布为 " + ("、".join(f"{key} {value}" for key,value in reasons.items()) or "空") + "。",
        f"[配置与源码摘要](/artifact/{run}/config.json) · [完整事件](/artifact/{run}/events.jsonl) · " + evidence(last), "",
        "独立样本单位是种子，本档案样本量 n=1。多轮观察共享储备、持仓与消息，"
        "不能当作独立重复样本。本报告不计算跨种子置信区间或显著性。"
        "参考价由样例规则生成，单池交易、初始资金、费用及执行顺序限制了对外部市场的推断。", "",
        "复现时使用同一配置、种子、轮数和顺序，给新链分配新档案 ID。", "",
        "```sh",
        f"python3 -m src.run --rounds {config['rounds']} --run-id {run}-replay --seed {parameters['seed']} --order {config.get('order','fixed')} "
        f"--config-snapshot data/experiments/{run}/config.json",
        "```", "",
    ])
    (directory / "research.md").write_text("\n".join(research), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    generate(parser.parse_args().directory)
