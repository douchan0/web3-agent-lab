# Web3 Agent Lab 首轮交付

本地独立 Git 仓库已完成 A–F。三批市场实验各启动一条临时 Anvil 链，部署 RISK、sUSD 和一个 V2-style demo 池。三个策略角色用隔离的离线 mock，另有背景和参考价套利角色。

| 档案 | 轮数 | 决策 | 成交 | 拒单 | 观望 | 成交 K 线 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [深池验证](../data/experiments/first-10/index.html) | 10 | 50 | 35 | 4 | 11 | 10 |
| [深池基准](../data/experiments/first-100/index.html) | 100 | 500 | 159 | 32 | 309 | 75 |
| [浅池对照](../data/experiments/shallow-10/index.html) | 10 | 50 | 29 | 4 | 17 | 10 |

[交互档案](../app/index.html) · [100 轮自动报告](../data/experiments/first-100/report.md) · [中文课程与代码索引](../docs/learning/onchain.md)

## 链上证据

深池基准的 [E000067](../data/experiments/first-100/index.html#E000067) 在区块 27 成交，Gas 用量为 **69,827**。交易哈希如下。

```text
0xf2952492701ee5c5c2738d5c67a3176cb8f5bc9420acb6a6bd1bee094b83da0c
```

钱包卖出 18 RISK，收到 17.913851801556925940 sUSD。池从 10,000 RISK / 10,000 sUSD 变为 10,018 RISK / 9,982.086148198443074060 sUSD，0.054 RISK 手续费留池。回执内有代币 Transfer 和池 Swap 日志，原始记录也保存了开发 ETH 与代币余额。独立集成测试另外执行了两笔反方向的成功兑换与两笔最小输出触发的回退。 [100 轮回执](../data/experiments/first-100/receipts.json) · [真实链上集成测试记录](../tests/chain-evidence/events.jsonl)

深浅两组第一笔订单都是卖出 18 RISK，初始储备比分别为 10,000/10,000 与 3,000/3,000。浅池到账 17.839285 sUSD，含费价格冲击约 90 bps，深池约 48 bps。这一笔对照锁定了方向、输入量、初始储备比和费率。后续各轮的成交数同时受资产规模、交易上限和策略反应影响。 [浅池 E000067](../data/experiments/shallow-10/index.html#E000067)

## 现场兼容性与运行证据

| 项目 | 核验结果 |
| --- | --- |
| macOS 与架构 | 15.7.7，arm64 |
| Python / Node / npm | 3.10.13 / 25.6.1 / 11.9.0 |
| 链与合约编译 | 项目内安装 Anvil 1.5.1 和 solc 0.8.30。系统 PATH 未发现 Forge 或 Cast，运行只依赖 Anvil 与 solc。 |
| 已有模型渠道 | 发现 OpenCode CLI、既有回环监听、DeepSeek Harness.app 0.2.2-rc.1 和 MiniMax CLI。仅检查凭据变量名称是否存在。OpenCode 版本命令在默认沙箱写日志时被拦截。未核验具体远程模型的可调用性、程序化授权或额度。 |
| Harness 与端口 | Python 顺序编排与 mock-v1。本机回环随机空闲端口、独立链 ID。标准执行后检查无 Anvil 监听残留。默认沙箱拒绝端口绑定，经本地执行审批后验证。 |
| 开发依赖 | 初始 npm 审计报告 solc 的间接依赖问题。项目将 tmp 固定到 0.2.7 后复查为 0 个已报告漏洞，合约构建 SHA-256 与首轮归档一致。 |

执行记录与复现命令如下。复跑时给每条运行命令换一个新 run ID。

```sh
./scripts/doctor.sh
npm ci
npm run compile
CHAIN_TEST_EVIDENCE=tests/chain-evidence python3 -m unittest discover -s tests -p test_chain.py -v
python3 -m src.run --rounds 10 --run-id first-10
python3 -m src.run --rounds 100 --run-id first-100
python3 -m src.run --rounds 10 --run-id shallow-10 --config configs/shallow.json
python3 -m unittest discover -s tests -v
python3 -m src.replay data/experiments/first-10 data/experiments/first-100 --rounds 10
open app/index.html
```

保留已有链上测试归档时，运行完整测试命令即可让集成测试使用临时目录。若想另存证据，`CHAIN_TEST_EVIDENCE` 也须使用新目录。

完整测试 **8 项通过**，覆盖双向兑换、手续费、总量、储备及钱包守恒、Gas 对账、最小输出回退、已取得回执在查询失败后归档、配置白名单、新闻可见门和 OHLC。100 轮归档测试从池 Swap 原始日志校验成交量、方向和储备，并从 JSONL 重建价格及统计。两个独立深池实验的前 10 轮确定性市场轨迹一致。

Chromium 中核验了 75 根成交 K 线、新闻悬停、事件直达、原始回执、上一轮、播放和速度切换。回到第 99 轮时，净值曲线只保留起始点与前 99 个收盘点。页面无网络依赖。回执哈希属于已退出的临时链，可在归档内核查。

## 成本、限制与下一轮

100 轮的部署与准备花费 1,545,649,302,514,963 wei，兑换花费 17,880,287,393,863 wei，使用本地开发 ETH。API 调用、输入 token、输出 token 和 API 费用均为 0。角色的持仓、参考价净值、FIFO 盈亏、回撤、成交率、含费价格冲击、相对下单报价的滑点与分币种费用见 [成本和统计](../data/experiments/first-100/costs_and_stats.json)。

五条带哈希的新闻均为虚构教学样例。参考价为合成序列，教学池仅支持一次注资和双向兑换。页面能回放一次归档，命令可比较独立运行轨迹。缓存订单在新链上的专用重演、真实历史数据与真实 LLM 调用仍待实现或授权验证。下一轮可先固定对照角色和新闻，用配对种子与变换执行顺序评估策略，再在授权渠道中替换同一角色的模型。
