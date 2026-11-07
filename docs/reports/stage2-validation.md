# 第二阶段测试与性能

## 链上结果

环境为 macOS 15.7.7 arm64、Python 3.14.3、Node 25.6.1、Anvil 1.5.1、solc 0.8.30。以下为本机单次运行，固定种子 7631，轮换执行，均为真实本地 Anvil、mock 决策、合成参考价。

| 目标轮数 | 完成轮数 | 成交 | 有成交轮 | 链执行秒 | 含导出秒 | 原始 JSONL 字节 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 500 | 500 | 622 | 342 | 15.809 | 15.925 | 8,237,795 |
| 1,000 | 1,000 | 1,219 | 665 | 35.325 | 35.539 | 16,410,450 |
| 5,000 | 5,000 | 5,868 | 3,261 | 247.234 | 248.676 | 79,829,389 |

1000 轮归档有 5000 次决策，其中 3152 次观望、629 笔风控拒单。逐笔检查了 1219 笔的状态、前后储备连续性与执行检查字段。兑换合计 85,116,788 Gas 单位、17,880,905,034,523 wei，另有准备 Gas 1,545,649,302,514,963 wei。模型 token、模型 API 次数与费用均为 0。 [1000 轮研究报告](../../data/experiments/stage2-rotate-1000/research.md) · [完整归档](../../data/experiments/stage2-rotate-1000)

首个 1000 轮尝试在完成 253 轮后遇到回环 TCP `EADDRNOTAVAIL`。回归测试确认旧实现的 50 次连续读取创建了 50 次连接。改用已建立的直连 HTTP 后，同样 50 次读取额外创建 0 次连接，且 1000／5000 轮实测完成。广播结果不明确时会保留异常并停止，避免自动重发。 [失败状态](evidence/long-attempt-failed-status.json) · [异常事件](evidence/long-attempt-failed-event.jsonl)

停跑与重建也单独实测。随机顺序父档案在 5/12 停止，子档案用新链完成 12 轮并记录 `parent_prefix_verified=true`。另一次进程收到 SIGTERM 时在第 3 轮收盘后停止，10 件归档均通过校验。 [父状态](../../data/experiments/stage2-checkpoint-stop/status.json) · [子状态](../../data/experiments/stage2-checkpoint-rebuilt/status.json) · [SIGTERM 状态](evidence/signal-stop-status.json)

500 和 5000 轮仅作性能观察，完整档案保存在本机 `.tools/stage2-benchmarks/`，仓库提交状态与 SHA-256 清单。1000 轮和三组配对档案完整随仓库分发。 [500 状态](evidence/mock-500-status.json) · [5000 状态](evidence/mock-5000-status.json) · [5000 清单](evidence/mock-5000-manifest.json) · [配对结果](paired-order.md)

## 浏览器、正确性与耗时

Chromium 实测了 100 轮加载、单轮五角色决策、哈希和余额、两条 Transfer 与池 Swap、链上回退、新闻跳转、角色筛选、播放调速、并排对照、四个数学互动模块、1000 轮滑块及课程和故事链接。AMM 的 18 位到账量与深浅池原始回执一致。

冷缓存加载 5000 轮时，紧凑索引传输 3,927,262 字节，浏览器 Resource Timing 约 1.776 秒。热缓存同端点 curl 约 27 毫秒。切到第 2000 轮时同步画图约 3 毫秒，保持 100 轮窗口，证据请求约 2 毫秒、21,646 字节。首页仍预载紧凑的全档案行情与净值投影，原始证据逐轮读取。结果是本机单次观察，浏览器、机器和市场活跃度会影响耗时。

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_math.mjs
./scripts/check-ui.sh
python3 -m src.archive data/experiments/stage2-rotate-1000
python3 -m src.run --rounds 5000 --run-id bench-new --seed 7631 --order rotate --archive-root .tools/stage2-benchmarks
python3 -m src.lab --port 0 --archive-root .tools/stage2-benchmarks
```

已验证本地 Anvil、归档、UI 和离线替身。真实提供方调用、主网和真实资产均未参与。课堂学习效果还没有开展真人测试。同链恢复尚未实现；现有恢复方式为有谱系校验的新链重建。
