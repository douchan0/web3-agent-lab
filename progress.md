# 首轮进度

- A 环境已盘点。macOS 15.7.7 / arm64，Python 3.10.13，Node 25.6.1。发现 OpenCode CLI 和本地监听进程、DeepSeek Harness.app 以及 MiniMax CLI／环境变量名称。模型可调用性与额度均未验证。选择 Python harness 和 mock-v1。
- B 架构、协议、预算与深浅池配置已落盘。C 等待安装 Anvil 与 Solidity 编译工具并验证。
- C 已验证。Anvil 1.5.1 与 solc 0.8.30 安装在项目目录。两种 ERC-20 和 V2-style demo 部署后，真实双向兑换、两笔最小输出保护回退、ERC-20 总量、手续费、Gas 以及储备／钱包对账均通过。原始证据见 `tests/chain-evidence/events.jsonl`。默认沙箱拒绝回环端口绑定，链上命令经本地执行审批。
- D 已验证。独立链上依次完成 `first-10` 和 `first-100`，归档全部决策、风控、回执、价序列、角色统计和模型用量。五条新闻均为带哈希的本地教学样例。三个 mock 角色与两类规则角色使用独立开发账户。新闻时间门、风险约束与 OHLC 单元测试通过。
- E 已验证。Chromium 从本地 `app/index.html` 打开 100 轮档案，显示 75 根成交 K 线。悬停第 2 轮新闻能看到摘要，点击可看来源与可见时间；点击第 1 轮 K 线可定位 `E000067`，展开完整回执和前后状态。轮次回放及速度切换通过，未报告 JavaScript 错误。10 轮与 100 轮的前十轮确定性市场轨迹匹配。
