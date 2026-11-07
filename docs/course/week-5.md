# 第 5 周 · Solidity、交易回执和事件

学习目标。理解 quote、swap 和日志的职责。
先修与用时。前四周，60 分钟。

## 概念与可复算示例

Solidity 中 view 函数能读取状态。quote 给报价，swap 交易才修改余额和储备。require(amountOut >= minOut) 在执行不符时回退。Event Log 有发出者、topics 和 data，可用回执追溯。

18 RISK 的报价 17.913851801556925940 sUSD。30 bps 容忍度下，minOut = ceil(报价原始整数 × 9970 ÷ 10000) ≈ 17.860110 sUSD。E000067 回执记录两条代币 Transfer 和一条池 Swap。

## 动手练习

1. 打开回执前先猜两条 Transfer 和 Swap 各是谁发出的。
2. 展开日志 JSON，比对 address 与池、代币地址。记录输入、输出、最终储备和 min_out_raw。
3. 打开集成测试回退，比较钱包、储备和 Gas，再找合约中的 quote、require 与 emit Swap。

[归档 E000067](/?run=first-100&event=E000067#evidence) · [链上证据区](/#evidence) · [Solidity](/project/contracts/Market.sol)

## 理解题与参考答案

1. 读取 quote 会发出 Swap 吗？ 答。不会，只读。
2. 回退后的日志还在吗？ 答。失败调用的状态更新及日志撤销，仍有交易回执。
3. minOut 是成交价吗？ 答。它是最少能收到的输出量。

常见误解。认为回执所有日志都由收件人合约发出。一次调用可以触发多个合约。

思考题与衔接。仅保存 Swap 日志能否知道钱包原本的余额？下周学习用快照重建资产。

外部阅读。WTF Solidity 可查中文语法与事件教程，Cyfrin Updraft 可做后续开发练习。[WTF Solidity](https://github.com/AmazingAng/WTF-Solidity) · [Cyfrin Solidity](https://updraft.cyfrin.io/courses/solidity)
