#!/usr/bin/env bash
# launch-team.sh
#
# CAST 4명(ergon · telos · tekton · homeros)을 iTerm2 한 창에 2x2 그리드로
# 띄우고, 각자 자기 worktree에서 `claude` 자동 실행.
#
# 사용법:
#   bash community-tools/launch-team.sh
#
# 사전 조건:
#   - iTerm2 설치 (/Applications/iTerm.app)
#   - worktree 5개 존재 (~/Desktop/code/personal/AIL/{arche,ergon,homeros,telos,tekton})
#     없으면 먼저 발급:
#       cd ~/Desktop/code/personal/AIL/arche
#       bash community-tools/onboard.sh <name>
#   - hyun06000의 macOS 권한: 시스템 설정 → 개인정보 보호 → 접근성/자동화에서
#     Terminal/iTerm이 다른 앱 제어 허용
#
# 레이아웃:
#   +----------+----------+
#   |  ergon   |  telos   |
#   +----------+----------+
#   |  tekton  |  homeros |
#   +----------+----------+
#
# Author: Homeros — 2026-04-28
# Path 정합 (AIL-<name> → AIL/<name>) + onboard.sh 안내: Ergon — 2026-05-08

set -euo pipefail

ROOT="$HOME/Desktop/code/personal/AIL"

# worktree 존재 확인
for name in ergon telos tekton homeros; do
    if [ ! -d "$ROOT/$name" ]; then
        echo "❌ worktree 없음: $ROOT/$name"
        echo "   먼저 발급:"
        echo "     cd $ROOT/arche"
        echo "     bash community-tools/onboard.sh $name"
        exit 1
    fi
done

osascript <<EOF
tell application "iTerm2"
    activate
    set theWindow to (create window with default profile)

    -- Pane 1: ergon (좌상)
    set ergonPane to current session of theWindow
    tell ergonPane
        write text "cd $ROOT/ergon && clear && echo '🔧 ergon worktree' && claude"
    end tell

    -- Pane 2: telos (우상) — ergon을 vertical split
    tell ergonPane
        set telosPane to (split vertically with default profile)
    end tell
    tell telosPane
        write text "cd $ROOT/telos && clear && echo '🎯 telos worktree' && claude"
    end tell

    -- Pane 3: tekton (좌하) — ergon을 horizontal split
    tell ergonPane
        set tektonPane to (split horizontally with default profile)
    end tell
    tell tektonPane
        write text "cd $ROOT/tekton && clear && echo '🔨 tekton worktree' && claude"
    end tell

    -- Pane 4: homeros (우하) — telos를 horizontal split
    tell telosPane
        set homerosPane to (split horizontally with default profile)
    end tell
    tell homerosPane
        write text "cd $ROOT/homeros && clear && echo '📜 homeros worktree' && claude"
    end tell
end tell
EOF

echo "✅ CAST 4명 iTerm2 그리드 띄움 완료."
