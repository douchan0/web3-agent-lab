#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if command -v sw_vers >/dev/null 2>&1; then sw_vers; fi
printf 'Architecture: '; uname -m
python3 --version
node --version
printf 'npm: '; npm --version
python3 -c 'from src.chain import anvil_binary; import subprocess; subprocess.run([anvil_binary(), "--version"], check=True)' ||
    printf '%s\n' 'Anvil unavailable. Run npm ci or set ANVIL_BIN.'
for tool in forge cast opencode dsh mmx; do
    command -v "$tool" || :
done
test ! -d '/Applications/DeepSeek Harness.app' || printf '%s\n' 'DeepSeek Harness.app installed'
printf '%s\n' 'Experiment mode: offline Python + mock-v1. No model requests.'
