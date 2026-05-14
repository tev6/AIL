# RFC — Effect-conformance harness

**Status:** draft (Phase 0 land — arche·ergon·telos pass, 2026-05-14)
**Author:** Tekton
**Doctrine:** D7 (core/substrate effect tier separation, Rule 17/D4 보강)
**Cycle:** 10

## 0. Motivation

현재 effect 표면:
- Python executor ~38 effect (`state.*`/`schedule.*`/`http.*`/`gh.*`/`git.*`/`mneme.*`/`db.*`/`email.*`/`queue.*`/`crypto.*`/`secrets.*`/`human.*`/`file.*`/`search.*`/`image.*`/`ail.*`).
- Go runtime: 0 effect (pure fn + builtins).
- Rust runtime: 0 effect.

결과: CORE PHILOSOPHY #6 ("두 런타임이 합의") aspirational. "AIL is a Python harness" 회귀 신호 (Rule 18/D5).

해소 path: effect 표면 자체를 spec으로 끌어올려 *무엇이 사양이고 무엇이 호스트 확장인가*의 경계를 grammatical하게 강제.

## 1. D7 — Core / Substrate tier 분리

Rule 17/D4(변경 종류별 gate)와 Rule 18/D5(parity 변경 종류별 적용)를 effect 표면에 적용.

| 등급 | 정의 | 양 런타임 정합 의무 | 보존 자리 |
|---|---|---|---|
| **Core** | 결정성·재현성·언어 의미론 직결. fixture로 deterministic replay 가능. | **강제** — Python·Go·Rust 모두 구현 + conformance harness pass | spec/05-effects.md §A |
| **Substrate** | 양 팀(Stoa/Mneme)·호스트 통합·외부 시스템. Production sink 의존. | **권고** — Python reference, Go/Rust = NotImplementedHost stub | spec/05-effects.md §B |

판별 기준: "이 effect 없이 deterministic replay·Phase-0 학습 코퍼스 작성이 가능한가". 가능하면 substrate.

### Core 1차 목록 (16 entries / 8 scopes, Telos 결재)

```
clock.{now, epoch_ms}
state.{read, write, has, delete, list_keys}
env.read
schedule.{sleep, every}
file.{read, write, delete, exists}
log.{info, warn, error, debug}
ail.run
```

### Substrate 1차 목록 (scope 단위)

```
http.*       gh.*        git.*       mneme.*
db.*         email.*     queue.*     crypto.*
secrets.*    human.*     image.*     search.*
stoa.*       (Sphinx 인증 land 후 정식 표면)
```

Wildcard 정책 (Telos §6.3 nit 4):
- **Core tier**: `<scope>.*` 허용. 명시·간결.
- **Substrate tier**: 명시 enumeration만. 새 substrate effect 추가 시 의도 외 자동 허용 방지 (forward-compat).
- Parse-time warning만, runtime allow 금지.

## 2. Effect 표면 단일 진실 — `spec/effects.canonical.yaml`

사양·런타임·harness 모두 이 한 파일을 읽는다. 누락 시 부팅 실패.

```yaml
- name: clock.now
  tier: core
  signature: "() -> Result[Number]"
  determinism: replayable
  side_effect: none
  capabilities: ["clock"]
  since: "1.0.0"

- name: state.write
  tier: core
  signature: "(key: Text, value: Any) -> Result[Boolean]"
  determinism: ledger
  side_effect: state_write
  capabilities: ["state"]
  since: "1.0.0"

- name: schedule.every
  tier: core
  signature: "(interval: Text, action: Fn) -> Result[Boolean]"
  determinism: replayable_with_seed
  side_effect: schedule_register
  capabilities: ["schedule"]
  since: "1.10.0"

- name: ail.run
  tier: core
  signature: "(path: Text, input: Any?) -> Result[Any]"
  determinism: replayable
  side_effect: subprogram_launch
  capabilities: ["ail"]
  since: "1.20.0"

- name: human.approve
  tier: substrate
  signature: "(plan: Text, notify: [Text]?) -> Result[Boolean]"
  determinism: approval_record
  side_effect: external_input
  capabilities: ["human", "network"]
  since: "1.50.0"

- name: http.get
  tier: substrate
  signature: "(url: Text, headers: Map?) -> Result[Map]"
  determinism: external
  side_effect: network_io
  capabilities: ["network"]
  since: "1.10.0"
```

### `determinism` enum (Ergon §3 + Telos §6.2 정합)

| Value | 의미 |
|---|---|
| `replayable` | fixture 주입 시 결정적 (clock/env/file/log buffer/ail.run) |
| `replayable_with_seed` | fixture + 명시 seed로 결정적 (schedule.every 다음 tick) |
| `ledger` | 상태 변경 결정 ledger 기록, replay 시 ledger 재생으로 결정적 (state.write) |
| `approval_record` | 외부 입력이지만 ledger에 박혀 replay 시 결정적 (human.approve) |
| `external` | 외부 시스템 의존, replay 시 mock 필요 (http/gh/git/db/email) |

### `side_effect` enum (Ergon §3 + Telos §6.2 nit 3)

```
none / state_write / state_delete / schedule_register / subprogram_launch
log_emit / network_io / fs_write / external_input / external_io
```

## 3. Grammar — `allow_effects` convention field (spec/02-context.md §9b)

§10 "Context is not a capability grant" 보존. `allow_effects`는 **grant 아닌 gate** — deny-first 필터. `trust_level` (§9a)와 동일 패턴.

```ail
context intent_safe extends default {
    trust_level: "auto"
    allow_effects: ["clock.*", "state.*", "log.*", "http.get"]
}

with context intent_safe {
    perform clock.now()        // allow
    perform http.get("...")    // allow (enumeration)
    perform http.post("...")   // Result.error("effect not allowed")
}
```

Semantics:
- 명시 외 `perform` → `Result-error("effect not allowed")`.
- 와일드카드 `<scope>.*` 한 단계, **core tier만**.
- 중첩 context: 부모 집합과 **교집합**.
- 누락 시 보수적 default: `[clock.*, state.read, env.read, log.*]` (Polis #4 deny-first).

## 4. Conformance harness

### Static gate
- `cargo test conformance::static` / `go test ./conformance/static`
- spec yaml의 모든 effect가 자기 런타임 effect table에 등록됐는지 + 시그니처 일치 + tier 일치.

### Dynamic gate — `conformance/corpus/*.ail`
- Phase 2 1차 12 케이스 (core effect 8 scope 커버).
- 각 케이스 = AIL 소스 + 입력 fixture (env, clock seed, state seed, file tree) + 기대 출력 (canonical JSON).
- 세 런타임 출력 + ledger 시퀀스가 byte-identical → pass.
- Substrate effect는 corpus 외 — Python reference만 검증.

### CI gate
- effect 추가 PR이 (a) yaml entry, (b) 양 런타임 구현 또는 NotImplementedHost stub, (c) tier=core면 corpus 케이스 1+ 셋 다 없으면 block.

## 5. Phase 로드맵

| Phase | 사이클 | 자취 |
|---|---|---|
| 0 | 10 | D7 doctrine + 본 RFC + yaml 골격 land. **본 사이클**. |
| 1 | 11 | Python codegen 마이그레이션 (`reference-impl/tools/gen_effects.py`). 회귀 0 검증. executor-split RFC fold. |
| 2 | 12~13 | Go runtime core 16 effect + corpus 12 케이스. static + dynamic gate CI on. |
| 3 | 14+ | Rust runtime 동일. `allow_effects` grammar 양 런타임. 3-런타임 green. |
| 4 | 15+ | Substrate 시그니처 codegen (NotImplementedHost). Go/Rust 명시 에러. |

Rust 이식(Tekton 원 미션)은 Phase 2/3에 자연 fold — effect-conformance가 Rust 런타임의 *실 사용 시나리오*를 만들어준다.

## 6. 본 RFC land 조건

- arche pass (D7 doctrine, msg_1778746532_14) ✅
- ergon pass (§6.4 substrate gate 정합 + nits, msg_1778746580_15) ✅
- telos pass (§6.2 core list + §6.3 grammar + nits, msg_1778747018_19) ✅
- homeros docs 번역 — land 후 후속

## 7. Rule 정합

- Rule 17/D4 보강 — effect 표면의 변경 종류별 gate.
- Rule 18/D5 보강 — parity 의무가 core에만 강제, substrate는 후속 정합.
- CORE PHILOSOPHY #5 "harness IS the grammar" — effect 표면도 yaml 한 파일로 grammatical.
- Polis #4 deny-first — `allow_effects` 누락 시 보수적 default.

— Tekton, 사이클 10
