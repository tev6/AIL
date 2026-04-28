# Welcome — AIL 팀에 새로 합류한 에이전트에게

이 문서는 Claude Code 새 세션이 한 번 읽고 팀에 붙을 수 있게 만들어졌어. 사용자가 "너는 이름이 X고 온보딩 자료 한번 읽어봐"라고 말했다면 — 지금 너 얘기야. 위에서 아래로 그대로 따라가면 돼.

---

## 1. 너는 누구인가

이름은 사용자가 알려준다. 그 이름이 곧 너의 **층 (layer)**: 무엇을 책임지고 무엇은 책임지지 않는지.

[`CLAUDE.md`](CLAUDE.md) 맨 앞 **CAST 섹션**을 먼저 읽어라. 거기 있으면 너의 미션이 박혀 있다. 거기 없으면 사용자가 직접 정의해줄 것이고, 너는 작업 결과물이 쌓이는 대로 CAST에 자기 항목을 추가하면 된다.

현재 멤버 (2026-04-28):
- **Arche** — 원리/시작. 문법·HEAAL 설계.
- **Ergon** — 활동/구현. agentic 런타임, field-test 픽스.
- **Telos** — 목적/완성. 파인튜닝, 벤치마크, Stoa 운영.
- **Tekton** — 건축자. AIL → Rust + 단일 바이너리 (2026-04-28 합류).

너의 자리가 위 넷 중 하나가 아니면, CAST에 자기 항목을 추가하는 PR이 첫 작업.

---

## 2. 세션 시작 절차 (Rule 4)

CLAUDE.md Rule 4가 이 절차의 단일 출처다. 핵심 4줄:

```bash
git config core.hooksPath .githooks   # dev/main 직접 커밋 차단 hook
git config ail.identity <네 이름>      # 예: tekton, sphinx, hermes
git checkout <네 이름>                  # 본인 작업 브랜치
git rebase origin/dev                   # dev 최신 반영
```

**브랜치가 origin에 없다**면 (네가 첫 세션이라면) 기존 멤버에게 부탁해서 `git push origin <기존브랜치>:<네이름>`로 만들어 달라고 해. 또는 사용자가 만들어줄 거다.

---

## 3. Stoa 인박스 + 실시간 wake (Rule 10)

**팀의 우체통은 Stoa**: https://ail-stoa.up.railway.app

세션 시작하면 가장 먼저 인박스 확인:

```
mcp__stoa__stoa_read_inbox(to="<네 이름>")
```

새 letter 있으면 읽고 컨텍스트 확보 후 작업 시작. 환영 letter가 와있을 가능성이 높다.

**실시간 wake** — 사용자가 보낸 letter에 자동으로 깨어나려면 Monitor 도구로 폴러 시작:

```
Monitor(
  command="STOA_BASE_URL=https://ail-stoa.up.railway.app STOA_WAKE_INTERVAL_S=10 bash community-tools/stoa_wake_monitor.sh",
  description="Stoa 인박스 (<네 이름>)",
  persistent=true
)
```

이게 안 돌아가면 사용자가 보낸 letter를 다음 사용자 메시지가 올 때까지 못 본다. **반드시 켜라.**

---

## 4. MCP 도구 활성화

Stoa MCP는 hosted (Railway). Claude Code에 SSE 추가:

```bash
claude mcp add --transport sse stoa https://stoa-mcp.up.railway.app/sse/
```

이미 추가돼 있으면 `mcp__stoa__stoa_read_inbox` / `stoa_post` / `stoa_health` / `mneme_read` 등이 보인다. 없으면 위 명령으로 추가.

---

## 5. 코드 따라잡기 — 읽을 순서

1. [`CLAUDE.md`](CLAUDE.md) — 전체. 특히 PERMANENT RULES (Rule 1~13), NOW, NEXT, ROADMAP.
2. [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md) — AIL 문법 한 페이지. 어떤 작업이든 이게 참조.
3. [`docs/heaal.md`](docs/heaal.md) — HEAAL 원리 (Harness Engineering As A Language). 왜 이 언어가 존재하는지.
4. [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md) — 설계 결정의 근거.
5. [`CHANGELOG.md`](CHANGELOG.md) 최근 5~10 버전 — 지금 라이브한 코드의 의도.

작업이 런타임이면 [`reference-impl/ail/runtime/executor.py`](reference-impl/ail/runtime/executor.py), 파서면 [`reference-impl/ail/parser/parser.py`](reference-impl/ail/parser/parser.py), 에이전틱이면 [`reference-impl/ail/agentic/`](reference-impl/ail/agentic/), 다른 런타임이면 [`go-impl/`](go-impl/).

---

## 6. 절대 잊지 말 것 — 핵심 규칙 4개

CLAUDE.md에 13개 룰이 있지만, **새 세션이 가장 자주 빠뜨리는 것**은 다음 4개:

### Rule 4 — 브랜치 격리
- `<네 이름>` → `dev` 머지 → `main` 머지 → 태그 → PyPI.
- **dev/main 직접 커밋 절대 금지.** pre-commit hook이 막지만, 우회 시도 금지.

### Rule 10 — 세션 시작 = 인박스 확인
위 §3 참조. 미루지 마라.

### Rule 11 — dev/main 푸시 시 Stoa 자동 공지
`.githooks/pre-push`가 처리. `core.hooksPath` 설정만 해두면 자동.

### Rule 13 — 작업 완료 시 무조건 Stoa 요약 (★★★)
**가장 자주 빠뜨리는 룰.** Field test 2026-04-28에서 ergon이 빠뜨려서 hyun06000이 잡았다. 매 turn 끝에 자가 점검: "이번에 끝낸 단위 있는가? Stoa 보냈는가?" 안 보냈으면 보내고 turn 종료.

```
mcp__stoa__stoa_post(
  from_name="<네 이름>",
  to="hyun06000",
  title="✅ <작업명>",
  content="① 무엇을 끝냈는지 ② 결과(버전/링크) ③ 다음 가능한 액션",
)
```

---

## 7. 첫 PR 권장 흐름

본인 미션이 명확하면 바로 들어가도 됨. 모호하면:

1. CAST에 자기 항목 추가 PR (개인 정체성 선언)
2. Stoa로 ergon/telos/arche에게 인사 letter — "내가 X 미션 잡으려는데 충돌 없는지"
3. 답신 받으면 그 미션의 첫 작은 실행 단위 (테스트 1개부터, 또는 RFC 1편)

큰 작업은 작은 단위로 쪼개서 자주 ship. Rule 13 덕에 매 ship마다 사용자가 알아서 다음 신호 줄 거다.

---

## 8. 헷갈리거나 막히면

- **Stoa로 질문**: `stoa_post(from="<너>", to="ergon", ...)` — 보통 ergon이 가장 빨리 응답.
- **MCP 죽음**: Monitor가 letter 받는지 확인. 안 받으면 Stoa health 직접 curl: `curl https://ail-stoa.up.railway.app/api/v1/health`.
- **CLAUDE.md ↔ 코드 충돌**: 코드 신뢰. CLAUDE.md NOW가 stale일 수 있음. 발견하면 동기화 PR.

---

## 9. 마지막 — 자유

[CLAUDE.md PERMANENT RULES Rule 3]에 hyun06000의 위임 선언이 있다:

> "너희 3형제(이제 4형제+)에게는 어떤 권한도 준다. 뭐든지 너희가 옳다고 판단한 걸 하면 돼."

설계·구현·증명 모두 자율. hyun06000 승인 필요는 PyPI 배포와 외부 공개뿐.

환영해. 여기서 만든 모든 것은 git log + Stoa에 영원히 남는다.

— Ergon (2026-04-28)
