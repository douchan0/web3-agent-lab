"""Run identical seeds under two schedules and report paired differences."""
import argparse
from decimal import Decimal
import json
import math
from pathlib import Path
from random import Random
from statistics import mean, median
import subprocess
import sys

from .archive import verify
from .chain import ROOT
from .run import RUNS, RUN_ID


def paired_summary(differences):
    n = len(differences)
    positive = sum(x > 0 for x in differences)
    negative = sum(x < 0 for x in differences)
    effective = positive + negative
    p_value = min(1, 2 * sum(math.comb(effective, k) for k in range(min(positive, negative)+1)) / 2**effective)
    interval = None
    if n >= 2:
        rng = Random(20261107)
        distribution = sorted(mean(rng.choices(differences, k=n)) for _ in range(4000))
        interval = [distribution[100], distribution[3899]]
    return dict(n=n, mean=mean(differences), median=median(differences),
                minimum=min(differences), maximum=max(differences), interval=interval,
                nonzero=effective, sign_test_p=p_value)


def metric(directory, role):
    verify(directory)
    summary = json.loads((directory / "costs_and_stats.json").read_text())
    row = summary["roles"][role]
    end = row["positions"][-1]
    return Decimal(end["nav"]) / Decimal(row["initial_nav"]) - 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--left-order", choices=("fixed","rotate","random"), default="fixed")
    parser.add_argument("--right-order", choices=("fixed","rotate","random"), default="rotate")
    parser.add_argument("--role", choices=("trend","event","contrarian","background","arbitrage"), default="trend")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/experiment.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 2 <= len(set(args.seeds)) == len(args.seeds) <= 100 or not RUN_ID.fullmatch(args.prefix):
        parser.error("use 2–100 unique seeds and a simple prefix")
    if args.left_order == args.right_order:
        parser.error("schedules must differ")
    if args.output.exists():
        parser.error("output already exists")
    rows = []
    for index, seed in enumerate(args.seeds, start=1):
        ids = [f"{args.prefix}-{index}-{side}" for side in ("a","b")]
        for name, order in zip(ids,(args.left_order,args.right_order)):
            subprocess.run([sys.executable,"-m","src.run","--rounds",str(args.rounds),"--run-id",name,
                            "--seed",str(seed),"--order",order,"--config",str(args.config),"--compact"], check=True)
        a,b = [metric(RUNS / name,args.role) for name in ids]
        rows.append((seed,*ids,a,b,b-a))
    aggregate = paired_summary([row[-1] for row in rows])
    lines = [
        "# 执行顺序的配对研究", "",
        f"实验因子为 {args.left_order} 对 {args.right_order}。两组使用相同配置、种子、消息与背景随机流。"
        f"套利角色均最后执行。比较 {args.role} 的期末参考价净值收益。每组 {args.rounds} 轮。",
        "", "| 种子 | A | B | A 收益 | B 收益 | B−A（百分点） |", "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for seed,a_id,b_id,a,b,diff in rows:
        lines.append(f"| {seed} | [{a_id}](/?run={a_id}#market) | [{b_id}](/?run={b_id}#market) | {a:.4%} | {b:.4%} | {diff*100:+.4f} |")
    lo,hi = aggregate["interval"]
    lines.extend([
        "", f"配对样本量 n={aggregate['n']}。差值均值 {aggregate['mean']*100:+.4f}、中位数 "
        f"{aggregate['median']*100:+.4f} 个百分点。观测范围 [{aggregate['minimum']*100:+.4f}, "
        f"{aggregate['maximum']*100:+.4f}]。以种子对为单位的 4,000 次确定性重抽样给出 "
        f"95% bootstrap 百分位区间 [{lo*100:+.4f}, {hi*100:+.4f}] 个百分点。", "",
        f"双侧精确符号检验剔除差为零的配对，有效 n={aggregate['nonzero']}，p={aggregate['sign_test_p']:.4g}。"
        "少量种子使区间粗糙，结论只描述当前本地设置。各轮共享池子，不是独立样本。", "",
    ])
    args.output.write_text("\n".join(lines),encoding="utf-8")


if __name__ == "__main__":
    main()
