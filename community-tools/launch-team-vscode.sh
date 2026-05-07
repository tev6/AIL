#!/usr/bin/env bash
# launch-team-vscode.sh
#
# CAST 4명(ergon · telos · tekton · homeros)을 VSCode 창 4개로 동시에 띄움.
# 각 창에서 Claude Code 사이드바를 한 번 클릭하면 해당 worktree에서 세션 시작.
#
# 사용법:
#   bash community-tools/launch-team-vscode.sh
#
# 사전 조건:
#   - VSCode `code` 명령어가 PATH에 있어야 함
#     (없으면 VSCode → Cmd+Shift+P → "Shell Command: Install 'code' command in PATH" 실행)
#   - worktree 5개 존재 (~/Desktop/code/personal/AIL/{arche,ergon,homeros,telos,tekton})
#     없으면 먼저 발급:
#       cd ~/Desktop/code/personal/AIL/arche
#       bash community-tools/onboard.sh <name>
#
# Author: Homeros — 2026-04-28
# Path 정합 + onboard.sh 안내: Ergon — 2026-05-08

set -euo pipefail

ROOT="$HOME/Desktop/code/personal/AIL"

if ! command -v code >/dev/null 2>&1; then
    echo "❌ 'code' 명령어 없음."
    echo "   VSCode → Cmd+Shift+P → 'Shell Command: Install code command in PATH' 실행 후 다시 시도."
    exit 1
fi

for name in ergon telos tekton homeros; do
    if [ ! -d "$ROOT/$name" ]; then
        echo "❌ worktree 없음: $ROOT/$name"
        echo "   먼저 발급:"
        echo "     cd $ROOT/arche"
        echo "     bash community-tools/onboard.sh $name"
        exit 1
    fi
done

echo "🚀 CAST 4명 VSCode 창 띄우는 중..."
code -n "$ROOT/ergon"
code -n "$ROOT/telos"
code -n "$ROOT/tekton"
code -n "$ROOT/homeros"

echo "✅ 완료. 각 창에서 Claude Code 사이드바를 열면 해당 worktree 컨텍스트로 세션 시작됩니다."
