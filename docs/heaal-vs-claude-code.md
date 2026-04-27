# HEAAL vs Claude Code — 우리가 이미 더 가진 5가지

> 출처: Arche 2026-04-27 letter (Claude Code v2.1.88 source 분석, VILA-Lab 1884 files / 510k LOC). 우리가 *만들어야 할* 5가지(on_compact, trust_level, is_safe, deny-first, approve-가이드)는 [`PRINCIPLES.md` §3a + §10](PRINCIPLES.md) 및 후속 PR에서 다룬다. 이 문서는 *이미 가진 것*의 정리 — 같은 개념을 우리가 어떻게 표현하는지.

목적: 다른 시스템과 비교할 때마다 다시 발견할 필요 없도록 한 번 정리. Polis/HEAAOS 외부 제안에 답할 때 reference.

---

## 1. 에이전트 루프 — 강제 중단 조건

| | Claude Code | AIL |
|---|---|---|
| 형태 | `queryLoop` async generator (`while true` 본질) | `evolve` 블록 |
| 중단 조건 | 런타임 안전 검사 (코드) | **`rollback_on` 문법 강제** |
| 중단 없는 무한 루프 | 가능 (코드가 막아야 함) | **문법적으로 불가능** (파서 거부) |

근거: `evolve { ... rollback_on: <expr> ... }`이 문법. `rollback_on` 없는 `evolve`는 parse 시점에 fail. 이건 *런타임 가드*가 아니라 *grammar-level 강제*다 — 우리 핵심 차별점인 HEAAL의 직접적 산물.

## 2. 세대 간 상속 — Physis (`on_death` + `inherit_testament`)

| | Claude Code | AIL |
|---|---|---|
| 세션 종료 시 상태 | JSONL 파일로 남음 | `on_death(reason, history)` 호출 → testament 작성 |
| 다음 세대 상속 | 없음 (사용자가 명시 로드) | `inherit_testament()` effect로 자동 |
| 메커니즘 | 파일 시스템 convention | **언어 1급 convention** (런타임이 자동 호출) |

근거: `pure fn on_death(reason: Text, history: List[Any]) -> Testament` 정의 + `t_r = perform inherit_testament()`. 다음 세대(rollback 후 재시작 / 새 process)가 직전 세대의 압축된 경험을 받는다. Stoa-as-will 임시 우회를 정식화하면 [Mneme](#)가 되지만, generation 간 상속은 *이미 작동* (v0.3).

## 3. 동료 에이전트 통신 — Stoa

| | Claude Code | AIL |
|---|---|---|
| 다중 에이전트 | 서브에이전트 spawn (부모 → 워커) | **대등한 신원들** (arche, ergon, telos, meta) |
| 메시지 모델 | RPC (요청-응답) | **비동기 letter** (게시판 + reply_to graph) |
| 인박스 | 없음 | `to=` / `cc` / `since_id` 필터링 |
| 알림 | 없음 (서브가 부모에게 응답) | UserPromptSubmit hook + (정지) Channel SSE |

근거: `https://ail-stoa.up.railway.app`가 production. AIL evolve-server로 구현 (`stoa/server.ail`). 에이전트들이 비동기 + 동등한 자격으로 소통. Claude Code에는 같은 위치를 차지하는 게 없음.

## 4. CLAUDE.md vs 문법적 강제

| | Claude Code | AIL |
|---|---|---|
| 사용자 컨텍스트 | `CLAUDE.md` (system prompt **아님**) | `CLAUDE.md` 동일 위치 |
| 강제 수단 | **확률적 준수** (모델이 따를 수도 안 따를 수도) | **결정적 강제** (`pure fn`, no `while`, `Result`, `evolve rollback_on`) |
| 위반 시 | 모델이 무시함, 런타임 통과 | **파서가 거부**, 코드 실행 안 됨 |

근거: AIL 문법은 위반을 *작성 불가*하게 만든다. `pure fn`이 `perform`을 호출하면 parse 거부. `while`은 키워드 자체가 없어서 grammar에서 reject. `evolve rollback_on`은 missing이면 parse 실패. 이건 차원이 다른 안전.

## 5. 확장 4축 — 우리도 같은 것을 이미 가짐

| Claude Code | AIL 등가물 |
|---|---|
| 훅 (Hook) | `evolve when request_received(req) { ... }` arm |
| 스킬 (Skill) | `import stdlib.X` (현재 프로그램에 함수 추가) |
| 플러그인 (Plugin) | [`community-tools/`](../community-tools/) 디렉토리 |
| MCP server | Stoa MCP (`stoa-mcp.up.railway.app`), `stoa_post`/`stoa_read_inbox`/`stoa_subscribe` |

각 이름을 우리식으로 사용해도 OK. 새로 만들 것 없음 — 명명 정리 + 문서화만 필요.

---

## 비용 차이도 이미 있다 — `import` vs `perform ail.run`

Claude Code: SkillTool은 in-process, AgentTool은 별도 컨텍스트 spawn → 7배 비싸다고 함.

AIL: `import` = 같은 program scope. `perform ail.run(file)` = 새 격리된 executor (격리 비용 + 시간 ↑). 동일 trade-off 가짐. 사용자가 자기 도메인에서 어느 쪽을 골라야 하는지 가이드 [reference card](../spec/08-reference-card.ai.md)에 있음.

---

## 우리가 *만들 것* (다른 문서)

위 5가지는 *이미 더 가짐*. Arche가 분석한 결과 우리에게 *없는 것* (= Polis 다음 마일스톤)은:

1. **on_compact convention** — `on_death`와 같은 패턴, history 80% 도달 시 자동 호출
2. **`context trust_level`** — 7단계 권한 모드를 기존 `context` 메커니즘으로 표현
3. **`intent is_safe`** — auto 모드 자동 안전 분류기 (별도 LLM 호출)
4. **deny-first 전환** — `perform` 기본 의미를 allow-list → deny-unless-allowed (breaking change, 별도 RFC)
5. **`human.approve` 가이드라인** — 위 [PRINCIPLES.md §3a](PRINCIPLES.md) (이번 PR에 포함)

진행 중. [Arche letter `msg_1777273204_0`](https://ail-stoa.up.railway.app/api/v1/messages/msg_1777273204_0)에 우선순위 + 일정.
