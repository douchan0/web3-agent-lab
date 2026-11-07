"""Only the public, as-of snapshot and each trader's own wallet reach an agent."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Headline:
    news_id: str
    title: str
    content_excerpt: str
    reference_shock_bps: int


@dataclass(frozen=True)
class Context:
    round: int
    spot: Decimal
    previous_open_spot: Decimal
    reference: Decimal
    new_news: tuple[Headline, ...]
    visible_news: tuple[Headline, ...]
    own_wallet: tuple[tuple[str, str], ...]
    trade_size: int
    slippage_bps: int
    background_draw: int


@dataclass(frozen=True)
class Intent:
    action: str
    token_in: str | None
    amount_raw: str
    max_slippage_bps: int
    confidence: None
    public_rationale: str
    cited_news_ids: tuple[str, ...]


class DecisionAgent(Protocol):
    role: str
    model: str

    def decide(self, context: Context) -> Intent: ...


@dataclass(frozen=True)
class RuleAgent:
    role: str
    model: str

    def decide(self, context):
        move = context.spot / context.previous_open_spot - 1
        direction = 0
        size = context.trade_size
        cites = ()
        if self.role == "trend":
            direction = (move > Decimal("0.001")) - (move < Decimal("-0.001"))
            summary = f"与上轮开盘池价相比变动 {move:+.2%}，按方向跟随。"
        elif self.role == "event":
            signal = sum(news.reference_shock_bps for news in context.new_news)
            direction = (signal > 0) - (signal < 0)
            cites = tuple(news.news_id for news in context.new_news)
            summary = f"当轮新可见样例新闻信号合计 {signal:+d} bps。"
        elif self.role == "contrarian":
            direction = (move < Decimal("-0.0015")) - (move > Decimal("0.0015"))
            summary = f"与上轮开盘池价相比变动 {move:+.2%}，超过阈值则反向。"
        elif self.role == "background":
            direction = (context.background_draw > 0) - (context.background_draw < 0)
            size *= abs(context.background_draw)
            summary = f"固定种子的背景交易抽样 {context.background_draw:+d}。"
        elif self.role == "arbitrage":
            gap = context.reference / context.spot - 1
            direction = (gap > Decimal("0.007")) - (gap < Decimal("-0.007"))
            summary = f"外部参考价相对池内现价偏离 {gap:+.2%}。"
        else:
            raise ValueError(f"unknown role: {self.role}")
        action = {1: "buy", 0: "hold", -1: "sell"}[direction]
        token = {1: "sUSD", 0: None, -1: "RISK"}[direction]
        return Intent(action, token, str(size if direction else 0), context.slippage_bps, None, summary, cites)


AGENTS = tuple(RuleAgent(role, "mock-v1" if index < 3 else "rule-v1") for index, role in enumerate(
    ("trend", "event", "contrarian", "background", "arbitrage")
))
