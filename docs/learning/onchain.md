# 从一笔兑换读懂本地链

以下证据来自 `first-100`。链接打开回放中的对应事件，可展开完整 JSON。金额以 18 位小数的整数写入链上。

| 概念 | 本轮实际操作 | 代码与证据 |
| --- | --- | --- |
| 钱包和账户 | 地址标识资产持有人。Anvil 预设账户被控制器用于发交易。角色分配了独立地址，持仓可以逐账户核对。 | [账户分配 E000002](../../data/experiments/first-100/index.html#E000002)、[chain.py](../../src/chain.py) |
| ERC-20 与授权 | 合约记录余额与授权额度。部署者先转测试币给角色，角色再授权池调用 `transferFrom`。授权交易本身没有把代币转入池。 | [RISK 部署 E000004](../../data/experiments/first-100/index.html#E000004)、[转账 E000012](../../data/experiments/first-100/index.html#E000012)、[授权 E000014](../../data/experiments/first-100/index.html#E000014)、[Market.sol](../../contracts/Market.sol) |
| 交易、回执和 Gas | 交易哈希定位一次广播。回执记载执行结果、区块与 Gas。Gas 用开发 ETH 结算，等于 Gas 用量乘有效 Gas 价格。回退也会耗费 Gas。 | [成功 E000067](../../data/experiments/first-100/index.html#E000067)、[集成测试回退 E000024](../../tests/chain-evidence/events.jsonl)、[execution.py](../../src/execution.py) |
| 流动性 | 部署者向池放入 10,000 RISK 和 10,000 sUSD。之后用户和合约交换，池里的代币量就是可见储备。教学池一次性注资。 | [注资 E000054](../../data/experiments/first-100/index.html#E000054)、[开盘快照 E000055](../../data/experiments/first-100/index.html#E000055)、[Market.sol](../../contracts/Market.sol) |
| AMM 与恒定乘积 | V2-style demo 按 `amountOut = floor(997 × amountIn × y / (1000 × x + 997 × amountIn))` 报价，`x` 是输入币储备，`y` 是输出币储备。实际输入全额进池，手续费留在池里，乘积随成功兑换略增。 | [储备前后 E000067](../../data/experiments/first-100/index.html#E000067)、[Market.sol](../../contracts/Market.sol) |
| 价格冲击与滑点 | 给池 18 RISK 得到约 17.913852 sUSD。与交易前边际价格相比，手续费和曲线合计约 48 bps。执行滑点另与决策时的兑换报价比较。链上最小输出提供最后一道保护。 | [成交 E000067](../../data/experiments/first-100/index.html#E000067)、[风控和回执归档](../../data/experiments/first-100/events.jsonl)、[experiment.py](../../src/experiment.py) |
| 预言机与套利 | 样例新闻 N01 在 00:00 UTC 发表，00:01 才释放。控制器以已释放消息更新合成参考价，套利角色比较它与链上储备比。这是可审计的离线输入通道。 | [新闻 E000071](../../data/experiments/first-100/index.html#E000071)、[参考价 E000072](../../data/experiments/first-100/index.html#E000072)、[experiment.py](../../src/experiment.py) |

原理参阅 [Uniswap 概念词汇](https://developers.uniswap.org/docs/get-started/concepts/glossary)。
