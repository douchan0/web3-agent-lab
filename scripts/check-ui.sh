#!/bin/sh
# Isolated Chromium regression. Requires the optional agent-browser CLI.
set -eu
cd "$(dirname "$0")/.."
scratch=$(mktemp -d)
python3 -m src.lab --port 0 >"$scratch/server" 2>&1 &
pid=$!
session="ui-$$"
ab() { agent-browser --namespace web3-stage2 --session "$session" "$@"; }
trap 'ab close >/dev/null 2>&1 || :; kill "$pid" 2>/dev/null || :; wait "$pid" 2>/dev/null || :; rm -f "$scratch/server"; rmdir "$scratch"' EXIT
for i in 1 2 3 4 5 6 7 8 9 10; do test -s "$scratch/server" && break; sleep .2; done
url=$(head -1 "$scratch/server")
ab open "$url"
ab set viewport 1366 900
ab wait '#results:not([hidden])'
ab get text '#metric-rounds' | rg '^1,000$'
ab get text '#metric-fills' | rg '^1,219$'
ab get text '#metric-rejects' | rg '^629$'
ab get text '#metric-cost' | rg '^\$0$'
ab get text '#receipt-amount' | rg '18 RISK.*17.913852 sUSD'
ab click '#receipt-link'
ab wait --text '267.91385180155692594'
ab open "$url/lab?run=first-100#market"
ab wait '#chart [data-round="100"]'
test "$(ab get count '#chart [data-round]')" = 100
ab click '#chart [data-round="1"]'
ab wait '#event-list [data-event-id="E000067"]'
test "$(ab get count '#event-list [data-event-id]')" = 14
ab click '#event-list [data-event-id="E000067"]'
ab get text '#event-body' | rg '69827.*wei'
ab get text '#event-body' | rg '267.91385180155692594'
ab get text '#event-body' | rg 'Swap'
ab select '#lab-amm select' less
ab click '#lab-amm button'
ab get text '#lab-amm output' | rg '17.91385180155692594'
ab select '#lab-depth select' deep
ab click '#lab-depth button'
ab get text '#lab-depth output' | rg '48 bps.*90 bps'
ab select '#lab-info select[name=prediction]' buy
ab click '#lab-info button'
ab get text '#lab-info output' | rg '160 bps'
ab select '#lab-risk select' rejected
ab click '#lab-risk button'
ab get text '#lab-risk output' | rg '超过单笔上限'
ab click '#revert-example'
ab wait --text '独立链集成测试 · Revert'
ab get text '#event-body' | rg '链上回退'
ab open "$url/?run=first-100&event=E000071#evidence"
ab wait --text '模拟支付试点新增商户'
ab get text '#clock-label' | rg '^2 / 100'
ab select '#role' arbitrage
test "$(ab get count '#chart polygon:not([data-role="arbitrage"])')" = 0
ab select '#speed' 100
ab click '#play'
ab wait 480
ab click '#play'
ab get text '#clock-label' | rg '^[3-9][0-9]? / 100'
ab click 'details:has(#compare) summary'
ab select '#compare' shallow-10
ab wait '#comparison > div:nth-child(2)'
test "$(ab get count '#comparison > div')" = 2
ab select '#run' stage2-rotate-1000
ab wait '#chart [data-round="1000"]'
test "$(ab get count '#chart [data-round]')" = 100
ab eval 'const s=document.getElementById("clock");s.value="500";s.dispatchEvent(new Event("input"));'
ab wait '#chart [data-round="500"]'
ab get text '#clock-label' | rg '^500 / 1000'
ab open "$url/artifact/first-100/story.md"
ab wait --text '从市场开门讲起'
ab open "$url/project/docs/course/week-8.md"
ab wait --text '科学实验设计与综合研究报告'
errors=$(ab errors)
test -z "$errors" || { printf '%s\n' "$errors"; exit 1; }
printf '%s\n' 'Chromium interaction checks passed'
