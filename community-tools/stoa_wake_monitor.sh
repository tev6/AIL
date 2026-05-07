#!/bin/bash
# Stoa wake monitor — 자기 인박스 폴링 후 새 letter 도착 시 한 줄 알림.
#
# 사용:
#   STOA_NAME=Admin STOA_BASE_URL=https://ail-stoa.up.railway.app \
#   STOA_WAKE_INTERVAL_S=3 \
#   bash community-tools/stoa_wake_monitor.sh
#
# 또는 Claude Code Monitor 도구로:
#   Monitor(
#     command="STOA_NAME=Admin bash community-tools/stoa_wake_monitor.sh",
#     description="Stoa 새 편지 감지 (3초 폴링)",
#     persistent=true
#   )
#
# 환경 변수:
#   STOA_NAME            (필수) 자기 멤버 이름 — Stoa-<role> 형식 권고 (예: Stoa-Walter).
#                        미설정 시 다음 우선순위로 fallback (2026-05-07 arche review 정합):
#                          1. `git config --worktree ail.identity` — 워크트리 별 영속 (Brandon
#                             SOP `git config --worktree ail.identity Stoa-<이름>` 발급 시 박음).
#                          2. `git config ail.identity` — global fallback.
#                          3. literal `unknown-host` — 사람 눈에 명백히 잘못 보이는 값.
#                             (직전 fallback `ergon`은 *정상 이름처럼 보이는* 값이라 typo 사고
#                              자리. 2026-05-07 Marcus 사고 직접 학습 — letter catch 0.)
#                        운영 시 항상 `STOA_NAME` 명시. fallback 신뢰 금지.
#   STOA_BASE_URL        (선택) default: https://ail-stoa.up.railway.app
#   STOA_WAKE_INTERVAL_S (선택) default: 3 (초)
#   STOA_SINCE_FILE      (선택) default: .stoa-since-<name>. since_id 영속화 path.
#
# 출력:
#   stdout 한 줄 = 알람 1건. 형식:
#     "📬 Stoa: [<msg_id>] <from> → <to_list>: <content_preview>"
#   Monitor 도구가 한 줄당 한 알람으로 인식.
#
# 종료: Ctrl-C 또는 harness 종료. since_id는 SINCE_FILE에 보존돼 재시작 시 이어감.

set -uo pipefail

NAME="${STOA_NAME:-$(git config --worktree ail.identity 2>/dev/null || git config ail.identity 2>/dev/null || echo unknown-host)}"
BASE="${STOA_BASE_URL:-https://ail-stoa.up.railway.app}"
INTERVAL="${STOA_WAKE_INTERVAL_S:-3}"
SINCE_FILE="${STOA_SINCE_FILE:-.stoa-since-$NAME}"

# Restore since_id if exists, else "" (= 첫 부트 → 폴링 첫 사이클에 전체 backlog drain).
# 2026-05-04 정정 (룰 22 (b) — Marcus 메일 누락 패턴 학습):
#   이전: 첫 부트 시 since=max(latest_id)로 advance → 부트 직전 letter 전부 skip → 멤버 미수신.
#   현재: 첫 부트 시 since="" → 첫 폴링이 since_id 파라미터 없이 전체 letter 가져와 한 번에 emit.
#   Bug B (server.ail since_id=0 → 0건) 수정 후이므로 ?since_id=0 안전하지만 더 안전하게 빈값 분기 유지.
since=""
[ -f "$SINCE_FILE" ] && since="$(cat "$SINCE_FILE")"

while true; do
    sleep "$INTERVAL"
    # Bug-B guard: server.ail의 ?since_id=0 가 0건 반환하므로 since=0/빈값이면 since_id 파라미터 생략.
    if [ -z "$since" ] || [ "$since" = "0" ]; then
        url="$BASE/api/v1/messages?to=$NAME"
    else
        url="$BASE/api/v1/messages?to=$NAME&since_id=$since"
    fi
    resp="$(curl -fsS "$url" 2>/dev/null || echo '{"messages":[]}')"
    # stdout flows through to Monitor (each printed line = 1 alarm).
    # stderr captures meta (__SINCE__<id>) for since_id 영속화.
    echo "$resp" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    msgs = d.get("messages", [])
    for m in msgs:
        mid = m.get("id", "")
        frm = m.get("from", {}).get("name", "?")
        tos = m.get("to", [])
        to_list = ",".join(t.get("name", "?") for t in tos)
        content = (m.get("content") or "").replace("\n", " ").replace("\r", " ")
        if len(content) > 80:
            content = content[:80] + "..."
        print(f"📬 Stoa: [{mid}] {frm} → {to_list}: {content}", flush=True)
    if msgs:
        ids = [m.get("id", "") for m in msgs if m.get("id")]
        if ids:
            # NOTE (lex vs numeric guard): id는 "msg_<unix_ts>_<counter>" 형식.
            # max()는 문자열 lex 비교 — 동일 timestamp 내 counter가 10+자리로 가면
            # lex ≠ numeric (예: "_2" > "_10")라 since 역행 → 누락 위험.
            # 현 트래픽(초당 한 발신자 10건 미만)에서는 비현실적이라 그대로 둠.
            # 폭주가 정상이 되면 "_<counter>" 분리 후 int 비교로 교체.
            print(f"__SINCE__{max(ids)}", file=sys.stderr)
except Exception as e:
    print(f"__ERR__{e}", file=sys.stderr)
' 2> /tmp/stoa-wake-meta-$$.txt
    # Pick up new since from stderr meta
    while IFS= read -r line; do
        case "$line" in
            __SINCE__*) since="${line#__SINCE__}"; echo "$since" > "$SINCE_FILE" ;;
        esac
    done < /tmp/stoa-wake-meta-$$.txt
    rm -f /tmp/stoa-wake-meta-$$.txt
done
