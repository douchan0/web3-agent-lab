# 模型适配器与预算

本机发现 OpenCode CLI 安装标记 2.0.27、OpenCode JS SDK 1.17.18、DeepSeek Harness 0.2.2-rc.1、MiniMax CLI 1.0.28。这些是本机组件版本。DeepSeek、GLM、MiniMax 的可调用模型 ID、程序化授权、定价与额度尚未核验。验收覆盖内存替身及无凭据回环 HTTP 替身。回环联调验证了模型发现、每角色一次请求、503 回退和一笔真实 Anvil 成交。测试中的请求数是本地替身尝试数，提供方用量和费用为零。 [OpenCode CLI](https://opencode.ai/docs/cli/) · [OpenCode SDK](https://opencode.ai/docs/sdk/)

| 模式 | 运行行为 | 成本 |
| --- | --- | --- |
| mock | 三个主角色为 mock-v1，背景和套利为 rule-v1 | 0 调用与 0 USD |
| fixture | fixture-v1 检查隔离、结构化输出和预算耗尽回退 | 0 提供方调用与 0 USD |
| live | 使用显式配置的 loopback relay，需 `--allow-model-calls` | 以中继核算为准。未知费用另标。供应商联调未验证。 |

## 中继协议

应用不接收凭据。用户提供的单独服务应绑定 127.0.0.1，使用它自己的授权方式，并证明能在调用前实施每次的 token 与 USD 硬上限。候选 OpenCode、DSH、MiniMax 路径若无法可靠报告或约束计费，应保持离线。项目没有附带具体供应商中继。请求只发往回环地址，HTTP 不跟随重定向。

- `GET /models` 返回对象 `{"protocol":"web3-lab-v1","enforces_budget":true,"ids":["提供方运行时发现的模型 ID"]}`。
- `POST /decide` 接收 role、model、system、snapshot、schema、temperature、max_total_tokens、max_output_tokens、max_cost_usd。
- 返回对象包含 model、decision（JSON 字符串）、input_tokens、output_tokens、cost_usd。费用使用十进制字符串；上游回复中的隐藏推理、会话和工具信息不应进入 decision。
- `configs/models.fixture.json` 提供角色预算字段示例。将 mode 改为 live、增加 relay_port 并为每个角色填入发现到的确切 ID，才构成 live 配置。默认拒绝从配置启动 live 调用，必须额外指定 CLI 开关。

每个角色有独立的调用、合计 token、USD 和超时预算，顺序并发为 1。超时、无效响应和未知计费会回退到对应 mock，之后停用该角色的模型路径。报告区分调用尝试、已知费用和费用不确定的请求。公开理由限 280 字，新闻引用只能来自可见信息集。请求仅包含当前角色快照和无状态指令。中继须禁用共享会话、工具和持久记忆。框架无法独立担保供应商中继遵守声明，首次真实测试前需在授权环境验明。

公平比较时固定角色、执行顺序、初始资产、种子、新闻时间和请求预算，只替换该角色的模型。归档的模型参数、输入快照和实际模型 ID 可用于检查配对是否成立。包含回退的结果应单独报告。
