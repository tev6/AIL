#!/usr/bin/env bash
# onboard.sh
#
# 신규 멤버 zero-touch 워크트리 부트스트랩.
# 한 줄로: 워크트리 발급 + per-worktree identity 박음 + hooks 활성 + dev rebase.
#
# 사용법:
#   cd ~/Desktop/code/personal/AIL/arche
#   bash community-tools/onboard.sh <name>
#
# 동작:
#   1. ~/Desktop/code/personal/AIL/<name>/ 워크트리 add
#      - 브랜치 <name>이 origin에 있으면 그것을 checkout
#      - 없으면 origin/dev에서 새로 분기
#   2. extensions.worktreeConfig=true (먼저)
#      ail.identity=<name>          (per-worktree)
#      core.hooksPath=.githooks     (dev/main 직접 commit + Stoa broadcast)
#   3. origin/dev에 자동 rebase (브랜치가 dev보다 뒤져 있으면)
#   4. 다음 단계 안내 출력
#
# 멱등: 같은 이름으로 두 번 호출하면 두 번째는 no-op + 상태 확인만.
#
# Author: Ergon — 2026-05-08 (arche letter msg_1778168084_8 위임)

set -euo pipefail

# ---- 인자 검증 ------------------------------------------------------

if [ "$#" -ne 1 ]; then
    cat <<'USAGE'
사용법: bash community-tools/onboard.sh <name>

예시:
  bash community-tools/onboard.sh tekton    # 새 Tekton 멤버 영입
  bash community-tools/onboard.sh hyun-2    # 외부 협업자 워크트리

<name>은 영문 소문자/숫자/하이픈만. 브랜치 이름과 디렉토리 이름 동시 사용.
USAGE
    exit 1
fi

NAME="$1"
if ! [[ "$NAME" =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "❌ 이름은 영문 소문자로 시작 + 영문 소문자/숫자/하이픈만 허용: '$NAME'"
    exit 1
fi

# ---- 위치 검증 ------------------------------------------------------

# 본 스크립트는 어떤 AIL 워크트리 안에서든 동작 — git worktree add는 공유 .git을 통해 처리.
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ 현재 디렉토리가 git 저장소가 아닙니다."
    echo "   먼저 cd ~/Desktop/code/personal/AIL/arche 후 다시 실행."
    exit 1
fi

ROOT="$HOME/Desktop/code/personal/AIL"
TARGET="$ROOT/$NAME"

# ---- 워크트리 발급 --------------------------------------------------

if [ -d "$TARGET" ]; then
    echo "ℹ️  워크트리 이미 존재: $TARGET"
    echo "    상태 확인 후 config 갱신만 진행."
else
    echo "🌱 워크트리 발급: $TARGET"
    git fetch origin --quiet

    if git show-ref --verify --quiet "refs/remotes/origin/$NAME"; then
        echo "   브랜치 origin/$NAME 사용."
        git worktree add "$TARGET" "$NAME"
    else
        echo "   브랜치 $NAME 신규 — origin/dev에서 분기."
        git worktree add -b "$NAME" "$TARGET" origin/dev
    fi
fi

# ---- per-worktree config ------------------------------------------

echo "🔧 워크트리 config 박는 중..."

# extensions.worktreeConfig는 *각 워크트리에서* set해야 효과 있음 (전역이 아님).
# 단 본 옵션 자체는 repository-level이므로 한 번만 박혀 있으면 됨 — 이미 박혀 있으면 no-op.
git -C "$TARGET" config extensions.worktreeConfig true
git -C "$TARGET" config --worktree ail.identity "$NAME"
git -C "$TARGET" config core.hooksPath .githooks

# ---- dev rebase ---------------------------------------------------

cur_branch=$(git -C "$TARGET" branch --show-current)
if [ "$cur_branch" = "$NAME" ]; then
    git -C "$TARGET" fetch origin --quiet
    if [ -n "$(git -C "$TARGET" status --porcelain)" ]; then
        echo "ℹ️  워크트리에 미커밋 변경 있음 — rebase 스킵."
        echo "    수동으로: cd $TARGET && git stash && git rebase origin/dev && git stash pop"
    else
        echo "🔄 origin/dev rebase..."
        if ! git -C "$TARGET" rebase origin/dev; then
            echo ""
            echo "⚠️  rebase 충돌 — 워크트리에서 수동 해결 필요:"
            echo "   cd $TARGET"
            echo "   # 충돌 해결 후"
            echo "   git rebase --continue"
            exit 1
        fi
    fi
fi

# ---- 검증 ---------------------------------------------------------

identity=$(git -C "$TARGET" config --worktree ail.identity)
if [ "$identity" != "$NAME" ]; then
    echo "❌ identity 박힘 검증 실패: '$identity' != '$NAME'"
    exit 1
fi

# ---- 안내 ---------------------------------------------------------

cat <<DONE

✅ $NAME 워크트리 준비 완료.

다음 단계:
  cd $TARGET
  # 새 Claude Code 세션 spawn 후 부팅 의식 §0(2.5) 진행:
  #   - CLAUDE.md 읽기 (자기 층 Identity 확인)
  #   - Stoa 인박스 읽기 (Rule 10)
  #   - Monitor 도구로 stoa_wake_monitor.sh 가동 (Rule 4)

워크트리 상태:
  경로:     $TARGET
  브랜치:   $cur_branch
  identity: $identity
  hooks:    $(git -C "$TARGET" config core.hooksPath)

Stoa registry 등록 (별도): 양 팀 leader에게 letter 한 줄 — "<NAME> 영입,
agents.list 추가 부탁". 본 onboard.sh는 워크트리만 발급, registry는 인간
승인 자리.
DONE
