# 第 2 周 · ERC-20 和智能合约

学习目标。区分余额、授权和开发 ETH。
先修与用时。第 1 周，45 分钟。

## 概念与可复算示例

智能合约（Smart Contract）在链上按代码更新状态。ERC-20 定义可互换代币的常用接口。balanceOf 查余额，transfer 转账，approve 设置代扣额度，transferFrom 使用额度。Transfer 和 Approval 日志帮助核对两种不同操作。

这里 decimals = 18。展示量 = 原始整数 ÷ 10^18。250000000000000000000 代表 250 RISK。深池 RISK 的初始发行量 = 10,000 + 5 × 250 = 11,250。

## 动手练习

1. 先预测给池发 Approval 时钱包余额是否变化。
2. 打开「部署与注资」，查看 RISK 部署、给钱包转币和授权，分别记下日志名。
3. 打开首笔兑换，找两个代币合约发出的 Transfer。核对钱包和池余额的相反方向。

[归档 E000012](/?run=first-100&event=E000012#evidence) · [归档 E000014](/?run=first-100&event=E000014#evidence) · [合约](/project/contracts/Market.sol)

## 理解题与参考答案

1. ERC-20 余额和 ETH 是一张账吗？ 答。代币余额由各合约维护，ETH 是链的原生余额。
2. 授权额度是已到账的金额吗？ 答。额度是可代扣的上限，Transfer 才移动代币。
3. 为何同一地址的 RISK 和 sUSD 不同？ 答。两种代币由独立合约记账。

常见误解。看到 sUSD 就认为它有美元担保。它是实验记账币。

思考题与衔接。若给不可信的 spender 无限额度，有什么风险？下周追踪池如何用授权执行兑换。

外部阅读。Ethereum.org 中文的 ERC-20 章节解释标准接口。实验合约只覆盖本实验需要的行为。[ERC-20](https://ethereum.org/zh/developers/docs/standards/tokens/erc-20/)
