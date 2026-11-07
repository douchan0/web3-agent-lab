# Web3 Agent Lab

macOS 本地 Web3 教学与多角色实验。项目使用 Anvil 开发账户、RISK 和 sUSD，以及一次性注资的 V2-style demo 教学池。新闻和参考价使用离线样例。

需要 Python 3.10+、Node.js 22+ 和 npm。首轮选择 Python 本地 harness 与 mock-v1，模型调用和 API 费用均为零。依赖安装后运行可断网。

```sh
npm ci
npm run compile
python3 -m src.run --rounds 10 --run-id demo
python3 -m unittest discover -s tests -v
open data/experiments/demo/index.html
```

运行目录必须是新名称。实验失败时保留已有事件和诊断，修复后用新 run ID 运行。配置位于 `configs/`。设置 `ANVIL_BIN` 可使用本机已有的 Anvil。

- [架构](docs/architecture.md)
- [实验协议](docs/experiment_protocol.md)
- [进度](progress.md)
