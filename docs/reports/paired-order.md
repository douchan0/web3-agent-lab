# 执行顺序的配对研究

实验因子为 fixed 对 rotate。两组使用相同配置、种子、消息与背景随机流。套利角色均最后执行。比较 trend 的期末参考价净值收益。每组 30 轮。

| 种子 | A | B | A 收益 | B 收益 | B−A（百分点） |
| --- | --- | --- | ---: | ---: | ---: |
| 7631 | [stage2-order-1-a](/?run=stage2-order-1-a#market) | [stage2-order-1-b](/?run=stage2-order-1-b#market) | 0.3263% | 0.5573% | +0.2311 |
| 7632 | [stage2-order-2-a](/?run=stage2-order-2-a#market) | [stage2-order-2-b](/?run=stage2-order-2-b#market) | 0.6405% | 0.7295% | +0.0890 |
| 7633 | [stage2-order-3-a](/?run=stage2-order-3-a#market) | [stage2-order-3-b](/?run=stage2-order-3-b#market) | 0.4483% | 0.5969% | +0.1487 |

配对样本量 n=3。差值均值 +0.1562、中位数 +0.1487 个百分点。观测范围 [+0.0890, +0.2311]。以种子对为单位的 4,000 次确定性重抽样给出 95% bootstrap 百分位区间 [+0.0890, +0.2311] 个百分点。

双侧精确符号检验剔除差为零的配对，有效 n=3，p=0.25。少量种子使区间粗糙，结论只描述当前本地设置。各轮共享池子，不是独立样本。
