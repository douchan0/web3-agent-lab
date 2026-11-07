# Web3 Agent Lab

macOS 本地 Web3 教学与多角色实验。项目使用 Anvil 开发账户、RISK 和 sUSD，以及一次性注资的 V2-style demo 教学池。新闻和参考价使用离线样例。

## 打开第二阶段教学实验室

```sh
python3 -m src.lab
```

在浏览器打开终端打印的本地地址，默认 127.0.0.1:8765。新版包含实验室地图、逐轮回放、链上证据、四个数学互动实验和八周课程。浏览已归档实验只需 Python。

- [中文用户手册](docs/user-manual.md)和[八周课程](docs/course/README.md)
- [首轮 100 轮新手故事](data/experiments/first-100/story.md)和[1000 轮研究报告](data/experiments/stage2-rotate-1000/research.md)
- [现状审计](docs/reports/stage2-audit.md)、[测试与性能](docs/reports/stage2-validation.md)和[配对种子报告](docs/reports/paired-order.md)
- [模型模式与成本](docs/model-adapters.md)和[研究路线图](docs/reports/roadmap.md)

原单页档案也可用 `open app/index.html` 打开。新版报告内的事件跳转以本地教学服务器为入口。

## 在本机复跑

需要 Python 3.10+、Node.js 22+ 和 npm。依赖安装后可断网执行。本轮使用 Python harness 与 mock-v1，模型调用和 API 费用均为零。

```sh
./scripts/doctor.sh
npm ci
npm run compile
python3 -m unittest discover -s tests -v
python3 -m src.run --rounds 10 --run-id demo-10
python3 -m src.run --rounds 100 --run-id demo-100
python3 -m src.lab
```

运行目录必须使用新名称。实验失败时保留已有事件和诊断，修复后用新 run ID 运行。默认使用本地新 Anvil 进程和临时端口，宿主环境需要允许本机回环 TCP。设置 `ANVIL_BIN` 可覆盖 Anvil 可执行文件。配置仅接受公开实验参数，请勿填入凭据。

浅池可用 `--config configs/shallow.json`。在 `configs/experiment.json` 的副本中可独立设置 `initial_reference`，缺省时使用初始储备比。基准参与者为三个固定 mock 策略、一个背景交易者和一个参考价套利者。

```sh
python3 -m src.replay data/experiments/first-10 data/experiments/first-100 --rounds 10
python3 -m src.analytics data/experiments/first-100
python3 -m src.report data/experiments/first-100
```

回放校验比较归档的市场轨迹。重新运行会创建新链，并得到该链自己的交易哈希与 Gas 记录。

- [首轮交付报告](reports/first_run.md)
- [100 轮自动教学报告](data/experiments/first-100/report.md)
- [链上概念与证据](docs/learning/onchain.md)
- [架构](docs/architecture.md)与[实验协议](docs/experiment_protocol.md)
- [进度](progress.md)
