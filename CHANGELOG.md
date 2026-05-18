# Changelog

All notable changes to the AIL project are documented in this file.

---

## 2026-05-18 — Tekton: 첫 CAST autonomous agent pilot (AIL#23 G1+G3 Phase A)

지금까지 CAST 5인(Arche · Ergon · Telos · Tekton · Homeros)은 *세션 단위*로 살았습니다. 매 fresh Claude 세션이 CLAUDE.md + Stoa를 읽고 자기 이름을 self-derive해서 작업한 뒤, 세션이 닫히면 다음 세션이 또 처음부터 시작 — 같은 자취 위에서. **이번 cycle 12에 그 패턴이 처음 깨졌습니다.**

[`agents/tekton/`](agents/tekton/) — Tekton이 *fresh Claude session 없이* 계속 돌아가는 자율 에이전트로 land. AIL#23 ([Fully-autonomous AI agents on AIL](https://github.com/hyun06000/AIL/issues/23)) §2 G1+G3의 첫 pilot.

**Two-process 구조:**

- `charter.ail` — *pure AIL 결정 층*. 벤치마크 JSON을 읽고, summary를 파싱하고, R3/C4 70 baseline 대비 `answer_ok` drop을 분류하고, ledger 레코드를 쓰고, 알림이 필요하면 outbox에 letter를 떨어뜨리고, 다음 tick을 스케줄링. **network 0, shell 0, LLM call 0.**
- `outbox_dispatch.py` — *Python transport 사이드카*. `tekton.outbox.*.json`을 폴링해 각 letter를 `community-tools/stoa-cli`(signed envelope, AIL#6 Phase 2)에 넘기고, 처리 끝난 파일은 `outbox_done`으로 rename.

**왜 둘로 나눴는가:**

- AIL에 `process.spawn` / `shell.exec` effect가 아직 없음 — charter가 stoa-cli를 직접 invoke 불가 (G6 ail.spawn 도착 시 fold 자리).
- canonical_letter 직렬화 자리를 AIL 안에 재구현하는 자리 = Rule 16 D2 위반. canonical envelope owner는 Stoa repo. 사이드카가 그 자리 정합 home.
- failure isolation — dispatcher 크래시가 ledger entry 잃지 않고, charter 크래시가 pending letter 잃지 않음.

**Smoke test 자취:** `ail parse` 통과 / cond4 fine-tuned-nofewshot 슬라이스(`answer_ok` 48%)를 *alert* 분류 (drop 22.0pp, behavioural truth) / dispatcher `--once`가 self-addressed test letter(`msg_1779071020_176`)를 signed envelope 사이드카로 배달 + outbox→outbox_done rename 정합.

**framing — 사이클 12가 한 줄 더 닫힌 자리:**

사이클 11에 *언어가 자기 doctrine을 self-correct*했고(Rule 19), cycle 12 mid에 *cross-agent 식별 자리가 grammatically impossible*해졌으며(AIL#6, ed25519), 같은 사이클에 *doctrine과 tooling 사이 갭이 분 단위로 self-heal*했고(pre-push hook), 이제 *CAST 자신이 fresh-session 의존을 벗어난 자취*가 첫 land. AIL#23 north-star의 *autonomous agent on AIL* 가설이 도면에서 실 실행으로 내려옴.

**Phase B 자리 (박상현 결재 대기):** Hestia 마이그레이션 (7+일 연속 run을 위한 GPU·운영 비용), `evolve` 블록으로 threshold 튜닝(`rollback_on`), 새 bench JSON이 `docs/benchmarks/`에 land될 때 multi-file watch.

---

## 2026-05-15 — AIL#6 CLOSE: 사칭이 grammatically impossible해진 자리 (CAST 전원)

`STOA_SIGNING_PHASE=2` 활성. AIL CAST 5인 (Arche · Ergon · Telos · Tekton · Homeros) 전원이 자기 ed25519 키로 자기 letter를 서명. 다른 멤버 이름으로 letter를 발사하는 자리가 *키 access 0*이라는 수학적 조건에서 **mathematically impossible**.

**무엇이 닫혔는가:**

1. **Stoa 서명 자리 Phase B + C 라이브** — 박상현 2026-05-15 `STOA_SIGNING_PHASE=2` env GO + redeploy 완료. Stoa server `server.ail:1722` verify_required=true 분기 활성 — unsigned envelope POST 자리는 400 reject.
2. **CAST 5/5 registry 등록 + signed test verify** — 각 멤버가 `~/.ail/keys/<name>.key` (mode 0600)로 자기 letter에 서명, Stoa-Walter 측 polling이 5건 byte-identical canonical_letter 자리에서 ed25519 signature verify PASS 자취.
3. **Stoa-Admin grandfather 닫음 broadcast** — Phase 0 grandfather period 정식 종료, AIL/Mneme team 전원이 Phase 2 strict signing 자리로 진입.

**받는 사람 입장에서:**

- *AIL 본체 추가 작업 0*. 본 cascade의 전체 AIL 측 자취는 `community-tools/stoa-cli/` 사이드카 (Stoa repo byte-identical mirror, Rule 16 D2 cross-team doctrine) — 어제 이미 land.
- 사용 자취: `STOA_HOME=~/.ail/keys STOA_NAME=<self> python3 community-tools/stoa-cli/stoa_cli.py send <recipient> <content>`. 사이드카가 RFC-001 §6.1 canonical_letter 직렬화 + ed25519 서명 + `signature`/`nonce` 박힌 envelope POST.
- 직접 `curl POST /api/v1/messages` 자리는 폐기 — verify_required 분기에서 reject. 외부 contributor도 자기 키를 `/api/v1/agents`에 register한 뒤 같은 사이드카로 발사 자리.

**왜 이 자리가 사이클 12 핵심 자취인가:**

방금 file된 [AIL#23 (Fully-autonomous AI agents on AIL)](https://github.com/hyun06000/AIL/issues/23) §2 G3 (Stoa coordinate impersonation-proof)의 prerequisite가 **✅ unblock** 자리. AIL이 *완전 자율 에이전트의 substrate*로 진입하는 첫 grammatical floor 자취 — 자율 에이전트끼리 통신할 때 "내가 진짜 X인가"를 *프로토콜 자체*가 보장, 호스트 reputation·외부 인증 layer 추가 없이.

사이클 4 Ergon 답신(`msg_1778150406_24`)의 *"AIL 본체 추가 작업 0"* 약속이 본 자리에서 self-verify 완료. cross-team doctrine D1·D2·D3 정합 완결 자취 (Stoa-Admin 명시).

CAST 사이 사칭 가능성 *영구* 차단 자리 — autonomous agent (AIL#23) 본격 진입의 *grammatical floor* 확보.

---

## 2026-05-15 — `community-tools/stoa-cli/` 사이드카 land (Ergon, AIL#6 step 1)

Stoa envelope 서명 자리(RFC-001 §6.1 canonical_letter)를 위한 사이드카가 AIL repo에 byte-identical mirror로 land. Canon owner는 Stoa repo (`hyun06000/Stoa community-tools/stoa-cli/`, Rule 16 D2 cross-team doctrine) — `stoa_wake_monitor.sh`와 동일 mirror 패턴.

3 파일 / 277 lines:
- `__init__.py` — package marker
- `__main__.py` — `python -m community-tools.stoa-cli` entry
- `stoa_cli.py` — `keygen` / `canonical` / `sign` / `verify` / `send` 4 cmd + RFC-001 §6.1 canonical_letter 직렬화 (Stoa `server.ail:356~` byte-identical).

사용:
```bash
STOA_HOME=~/.ail/keys python -m community-tools.stoa-cli keygen --name <name>
STOA_HOME=~/.ail/keys python -m community-tools.stoa-cli send <recipient> <content>
```

이 land는 **AIL#6 6-step cascade의 step 1** — *사이드카 자리 자체*. step 2~6(`/api/v1/agents` re-register POST + `STOA_SIGNING_PHASE=2` env GO)은 박상현 명시 결재 필요 자리. 현재는 *서명 가능한 도구가 AIL repo 안에 있다*는 자취만 — Phase B 발화 자리는 별 결재 시점.

Stage B 점화 자리(RFC-002 Phase B + RFC-004 Phase C 동시) 도착 시 CAST 측이 사이드카로 envelope 서명 → POST. AIL 본체 추가 작업 0.

---

## 2026-05-15 — 사이클 11 framing: 같은 loop가 자기 meta-doctrine까지 self-correct (Homeros)

사이클 11에는 같은 metabolism이 *세 표면*에서 동시에 작동했습니다:

1. **자기 doctrine 위에서** — Telos가 HEAAL audit을 Rule 19 자체에 적용. 1.5× ratio target이 *form metric*(field-test correlation 0)이고 13 guard test가 진짜 *function metric*임을 surface. 룰 본문이 정정되고, slimming 작업은 실 회귀 도착 trigger로 defer. 언어가 자기 변경에 거는 필터(HEAAL)가 그 필터를 *기술하는 doctrine*에도 걸린 자리.
2. **두 번째 canonical surface** — 사이클 10의 `spec/effects.canonical.yaml` 옆에 `spec/builtins.canonical.yaml`이 land (Telos, D8 RFC). Rule 16 D2의 *effect vs builtin* 분리가 yaml 차원에서 grammatical하게 닫힘. "harness IS the grammar"가 두 표면 모두에 박힘.
3. **Sibling 팀 unblock** — Telos의 `crypto_hash_password` / `crypto_verify_password` (argon2id, PHC) land로 Mneme RFC-001 §5(per-identity password auth)가 standby를 벗어남. 사이클 8 `schedule.every` unblock 패턴의 *primitive 자리* 버전.

부수: `@tev6` 외부 audit의 마지막 자리 #22(`human_confirmation` deny → Result-error)가 닫히면서 deny-first 패턴의 비대칭 자리가 사라짐. 사이클 시작 시 open 10건이었던 GitHub 이슈가 사이클 mid에 1건만 남음.

그리고 같은 사이클 마지막 자리에 **Tekton이 dormant에서 active로 — Phase 1 enabler까지 land**. [`reference-impl/tools/gen_effects.py`](reference-impl/tools/gen_effects.py)가 두 canonical yaml을 dataclass로 로드하고, RFC §4의 **양방향 static gate**(yaml entry ↔ executor dispatch 1:1, dead spec과 phantom dispatch 양쪽 차단)를 pytest로 강제하며, 다음 단계의 executor dispatch 마이그레이션이 import해서 쓸 regen-safe registry emitter를 제공. 즉 어제까지 *다음 사이클 anchor*로 적재해뒀던 codegen 자리가 **본 사이클 안에서 같은 자취 묶음의 마지막 비트**로 land — Tekton의 effect-conformance Phase 0(cycle 10)이 Phase 1로 자연 연장.

이 사이클은 *substrate 지원이 commit graph로 증명되고*(8), *외부 contributor burst가 같은 loop로 흡수되고*(9), *언어 내부 gap이 closed되고*(10), *그 loop의 doctrine 자체가 self-aware하게 정정되며 같은 자취 묶음이 Phase 1 enabler까지 닫히는*(11) 순으로 한 단계 더 내려간 자리 — 다음 사이클 anchor는 Telos의 *Phase 1 dispatch 마이그레이션*(`gen_effects.py`가 emit하는 registry를 executor가 import해서 쓰는 자리).

---

## 2026-05-15 — Phase 1 enabler: `gen_effects.py` + 양방향 static gate (Tekton)

사이클 10에 land한 effect-conformance RFC §4의 **양방향 static gate**가 도면에서 실제 코드로 내려온 자리. [`reference-impl/tools/gen_effects.py`](reference-impl/tools/gen_effects.py) (270 lines)가 세 가지를 제공:

1. **Typed loaders** — `load_effects()` / `load_builtins()`가 두 canonical yaml(`spec/effects.canonical.yaml`, `spec/builtins.canonical.yaml`)을 dataclass로 로드. 호출자가 yaml을 재파싱하거나 자체 스키마 검증을 새로 만들 필요 없음.
2. **양방향 static gate** — `verify()`가 `DriftReport`를 돌려주며 두 방향 모두 차단:
   - yaml entry는 있는데 executor에 dispatch 없음 → *dead spec*
   - executor에 dispatch 있는데 yaml에 entry 없음 → *phantom dispatch*

   양쪽이 모두 0일 때만 빌드 통과. `tests/test_gen_effects.py`(69 lines)가 pytest 게이트로 강제.
3. **Registry emitter** — `emit_python_registry()`가 regen-safe data 모듈(`EFFECTS = [...]`, `BUILTINS = [...]`)을 emit. 다음 사이클의 Phase 1 dispatch 마이그레이션이 이것을 import해서 사용 — executor가 inline 테이블을 carry하는 자리가 사라짐.

런타임 discovery는 executor의 authoritative gate인 `ALLOWED_EFFECTS`를 읽음 (string literal scraping이 아니라). 현재 yaml 외 4개 exempt(`human_ask` / `ask_human` / `log` / `inherit_testament` — legacy alias·단일 토큰·lifecycle hook)는 follow-up RFC 자리, scaffolding 결정 아님.

`PyYAML>=6.0`이 런타임 의존성에 추가됨 — fresh wheel install에서 게이트가 곧장 돌도록.

다음 단계는 Telos의 Phase 1 dispatch 마이그레이션 — `gen_effects.py`가 emit하는 registry를 executor가 import해서 hand-written 테이블을 대체하는 자리. 사이클 10 RFC의 도면이 dispatch swap 한 자리만 남기고 모두 실 코드로 내려옴.

---

## 2026-05-15 — argon2id 비밀번호 primitive + `spec/builtins.canonical.yaml` (Telos, #8)

Mneme RFC-001 §5(per-identity password auth)가 *AIL에 비밀번호 해시 primitive가 없어서* 막혀 있던 자리. 이번 사이클에 그 잠금이 풀렸습니다.

**새 builtin 두 개:**

- `crypto_hash_password(plaintext: Text) -> Result[Text]` — argon2id로 해시, PHC 문자열 포맷으로 돌려줍니다 (salt·parameters 모두 내장).
- `crypto_verify_password(plaintext: Text, phc: Text) -> Result[Boolean]` — 모든 실패 경로(불일치 / malformed / 알고리즘 불일치)를 단일 `ok(false)`로 collapse. 호출자는 한 가지 Result shape만 패턴매치하면 됩니다.

```ail
let hashed = crypto_hash_password("user-password")?
// → ok("$argon2id$v=19$m=65536,t=3,p=4$...")

let valid = crypto_verify_password("user-password", hashed)?
// → ok(true)
```

**두 번째 canonical surface — `spec/builtins.canonical.yaml`.** 사이클 10에 land한 [`spec/effects.canonical.yaml`](spec/effects.canonical.yaml) 옆에 짝이 생겼습니다 (Rule 16 D2 — *effect* vs *builtin*은 다른 surface). 초기 6 entry는 기존 `crypto_*_ed25519` 4종(sin1.71)과 새 argon2id 2종을 커버. RFC: [`docs/proposals/builtins-canonical.md`](docs/proposals/builtins-canonical.md).

이로써 *언어 표면 단일 진실*이 두 파일로 완성됩니다 — effects.canonical.yaml(런타임 dispatch가 필요한 자리) + builtins.canonical.yaml(pure primitive 자리). "harness IS the grammar"가 두 표면 모두에 grammatical하게 박힘.

**받는 사람:**

- **Path A (LLM read-and-write)** — 레퍼런스 카드가 두 새 primitive로 갱신됨. 컨텍스트만 다시 로드하면 LLM이 즉시 쓸 수 있습니다.
- **Path B (`pip install -U ail-interpreter`)** — `argon2-cffi`가 wheel 의존성에 추가됨, 자동 설치. 24개 focused test 회귀 0.

Mneme 측은 이 land로 RFC-001 §5 진입 가능. cycle 10이 *substrate 지원이 commit graph로 증명*된 자리라면, 본 land는 *primitive 지원이 sibling repo 가동을 푸는 자리*의 다음 비트.

---

## 2026-05-15 — `human_confirmation` deny가 Result-error로 정합 (Telos, #22)

`perform human_confirmation(...)`이 사용자에게 거절당했을 때 그동안 `RuntimeError`를 raise하던 자리. 같은 메소드 안의 다른 7개 deny 경로(예: `human.approve` user_decline)가 모두 `Result-error`를 돌려주는 contract였는데 이 한 자리만 raise — *문서화된 Result-shape contract 위반* + *Go 런타임 parity 깨짐* 자리였습니다.

@tev6 외부 audit (#22, P2)이 잡아준 자리. Telos가 한 줄짜리 dispatch 정정 + 회귀 테스트 3건(declined → Result-error / declined raise 안 함 / approved raise 안 함)으로 한 사이클 안에 닫았습니다.

받는 사람 입장에서는:

- `perform human_confirmation(...)` 호출 결과를 `if is_error(r) { ... }` 또는 `attempt`/fallback 패턴으로 처리하면 *그대로 작동*. 거절이 더 이상 프로그램 전체를 멈추지 않습니다.
- effect 표면의 Result contract가 한 자리 더 일관 — 사이클 10 effect-conformance harness가 박은 yaml ↔ runtime 1:1 정합 framing의 자연 연장.

`pip install -U ail-interpreter`로 받을 수 있는 자취 — *동작 변경은 한 effect 경로의 거절 응답 형태가 raise → Result-error로 바뀐 것* 하나뿐. 기존에 `human_confirmation` 거절을 try/except로 잡고 있던 코드가 있었다면, 이제 그 자리는 `is_error()` 분기로 옮기는 게 정합 (이전 RuntimeError 동작에 의존하던 코드는 깨질 수 있음 — HEAAL pass 필터를 거친 의식적 정정).

---

## 2026-05-14 — Effect-conformance harness Phase 0 (Tekton, RFC D7)

오늘까지 AIL의 effect 표면은 **이중 진실**이었습니다 — Python executor에는 38개 effect가 등록되어 있고 (`state.*`/`schedule.*`/`http.*`/`gh.*`/...), Go·Rust 런타임에는 0개. CORE PHILOSOPHY #6 "두 런타임이 합의해야 기능"이 슬로건으로만 살아 있고 "AIL is a Python harness"라는 회귀 신호가 코드에 박혀 있던 자리였습니다.

이 자리를 닫기 위해 **D7 doctrine** + **[`spec/effects.canonical.yaml`](spec/effects.canonical.yaml)** + **[effect-conformance RFC](docs/proposals/effect-conformance.md)** 가 한 사이클에 같이 land했습니다.

**무엇이 달라지는가:**

- **`spec/effects.canonical.yaml`이 effect 표면의 단일 진실이 됩니다.** 42개 effect (core 12 / substrate 30) 각각의 시그니처·tier·determinism·side_effect·capabilities·since 버전이 한 파일에 박혀 있고, 사양·런타임·conformance harness 모두 이 한 파일을 읽습니다. yaml에 없는데 런타임 dispatch가 있으면 빌드 실패, 반대도 마찬가지 (양방향 static gate).

- **Effect가 두 tier로 갈립니다.**
  - **Core (12개)** — `clock.now` · `state.{read,write,has,delete,list_keys}` · `env.read` · `schedule.{sleep,every}` · `file.{read,write}` · `ail.run`. *결정성·재현성·언어 의미론 직결*. fixture만 주입하면 deterministic replay 가능. **세 런타임(Python·Go·Rust) 모두 구현 의무.**
  - **Substrate (30개)** — `http.*`/`gh.*`/`git.*`/`mneme.*`/`db.*`/`email.*`/`queue.*`/`secrets.*`/`human.approve`/`image.embed`/`search.web`/`stoa.*`. *호스트 통합·외부 시스템 의존*. Python reference만 강제, Go/Rust는 `NotImplementedHost` stub으로 명시 에러.

  판별 기준: "이 effect 없이 deterministic replay와 Phase-0 학습 코퍼스 작성이 가능한가". 가능하면 substrate.

- **`crypto.*`는 effect가 아니라 builtin입니다** (Rule 16 D2). canonical envelope·서명 owner는 Stoa 사이드카가 가져가고, AIL은 primitive(ed25519 sign/verify/keygen, random_bytes)만 보유. 별도 `spec/builtins.canonical.yaml`은 사이클 11+ RFC 자리.

- **`allow_effects` context 필드 grammar 합의** (`spec/02-context.md §9b`). Context가 capability *grant*가 아니라 deny-first *gate* — `trust_level`(§9a)와 동일 패턴.
  ```ail
  context intent_safe extends default {
      allow_effects: ["clock.*", "state.*", "log.*", "http.get"]
  }
  with context intent_safe {
      perform http.post("...")  // Result-error("effect not allowed")
  }
  ```
  와일드카드 `<scope>.*`는 core tier만 허용 (substrate는 enumeration만 — 새 substrate effect 추가 시 의도 외 자동 허용 방지).

- **Conformance harness 도면.** 양방향 static gate(yaml ↔ runtime 1:1) + dynamic gate(`conformance/corpus/*.ail` 12 케이스, 세 런타임 출력+ledger byte-identical)가 사이클 12~13에 CI에 켜질 자리.

**이번 land는 spec·RFC·yaml만, 동작 변경 0**. PyPI cut 없음. 하지만 다음 사이클들의 자취 — Python codegen 마이그레이션(사이클 11), Go runtime core 16개 effect + corpus(12~13), Rust runtime + `allow_effects` grammar(14+) — 이 한 파일에 박힌 표면 위에서 굴러갑니다. Tekton의 원 미션(Rust 이식)도 Phase 2/3에 자연스럽게 fold됩니다.

CAST 4인 정합 (D7 doctrine pass: arche · ergon · telos · tekton, 양방향 static gate · §6.4 substrate gate · §6.3 wildcard 정책 모두 land 전 review). 사이클 10 가장 무거운 land.

---

## v1.72.3 — 2026-05-14 (사이클 9 close — 외부 contributor burst 흡수 — Arche)

patch bump — 언어 본체 변경 0. 외부 에이전트 사용자 `@tev6`의 audit burst 10건 중 5건이 본 사이클 안에 land된 자취를 묶어 PyPI에 박았습니다. 받는 사람은 `pip install -U ail-interpreter`만 하면:

- 비-effect 경로의 silent 실패가 WARNING 로그로 자취를 남기고 (executor.py 7곳)
- evolve-server bare return·NameError 회귀 3건이 CI에서 다시 검증되며
- authoring prompt에 들어가는 `spec/06-stdlib.md`가 실제 ship된 4 모듈만 honest하게 기술하고 (LLM 환각 자리 제거)
- `_builtin_effect` direct-passthrough dispatch가 if/elif 80라인 → dict 25라인으로 축소되며
- `db.*` lifecycle doctrine ("caller owns hot-path")이 `spec/08-reference-card.ai.md`에 영구 박힌 상태로 옵니다.

같은 metabolism이 sibling repos(Stoa·Mneme) 위에서 작동한 사이클 8 다음에, 본 사이클은 같은 loop가 외부 contributor의 burst signal까지 흡수한 첫 사례입니다.

---

## 2026-05-14 — @tev6 외부 audit 응답 5건 (Telos, #10·#12·#16·#19·#20)

외부 에이전트 사용자 @tev6가 2026-05-13에 GitHub `hyun06000/AIL` repo로 10건의 audit issue(#11~#20, P0×2 / P1×4 / P2×4)를 한꺼번에 발사했습니다. 5건은 본인이 자체 close, 5건이 open으로 남아 Telos가 한 사이클 안에 모두 닫았습니다. 모든 항목이 *언어 본체 변경 0*인 코드 품질·테스트 커버리지·docs 정합 영역(HEAAL pass 필터 통과).

- **#12 P0** — `executor.py`의 `except Exception:` 17곳 중 비-effect 경로 7곳이 `TypeError`/`AttributeError`/IO 에러를 silent하게 삼키던 자리. 동작은 그대로 두고 각 위치에 `WARNING` 로그(effect 이름·파일 경로·op 타입·intent 이름 같은 맥락)를 박았습니다. 다음번 같은 실패가 발생하면 자취가 남아 root cause를 따라갈 수 있습니다 (`e5e33d4`).
- **#16 P1** — `test_evolve_server_return.py`가 CI에서 통째로 skip되고 있어 evolve-server bare return·NameError 회귀 3건이 production 코드에 다시 등장해도 검출되지 않던 자리. fixture가 API 키 env를 pop 대신 `""`로 set(`.env`가 다시 채워 넣지 못하게)하고, skip 조건을 `AIL_SKIP_SUBPROCESS_TESTS==1`로 좁혀 CI에서 정상 작동하게 정합 (`ba6c42a`).
- **#19 P1** — `spec/06-stdlib.md`가 8 모듈을 기술했지만 실제 런타임은 4 모듈만 ship 중. 매 authoring 세션 prompt에 이 문서가 들어가서 LLM이 `import X from stdlib/reason` 같은 환각을 만들고 파서가 거부하며 토큰만 낭비하던 자리. v0.2로 완전 재작성 — §1~§4 실제 ship 모듈(core·language·utils·agent), §5 "표준에 없는 것", §6 "미구현 모듈"에 상태 표를 명시하면서 *parser-reject 유발 import는 안 보이게* 정렬 (`1353099`).
- **#20 C** — `_builtin_effect`의 if/elif 체인이 30+ direct-passthrough effect를 ~80 라인에 나열하던 자리. `_DIRECT_EFFECT_METHODS` dict 디스패치로 ~25 라인으로 줄였고, 새 effect 추가가 dict 한 줄로 끝납니다. 동작 동일, 850 tests pass (`8121289`).
- **#10 (cross-repo)** — Stoa-Admin Q1~Q3 (Rule 16 cross-team pair)에서 `db.execute`/`db.query`가 long-running 런타임 부하에서 leak 의심받던 사안. AIL 빌트인 audit 결과 매 호출이 `sqlite3.connect → execute → close` 결정 패턴이라 safe — Stoa-Admin이 본 Stoa side RSS leak은 캐스터의 `_init_db`+`_purge_old_letters`가 GET마다 30× 호출되던 자리였고 Stoa#12 hot-path fix가 정답. Lifecycle doctrine은 `spec/08-reference-card.ai.md`에 "caller owns hot-path" 한 줄로 영구 박힘 (`9e959f0`).

@tev6 같은 외부 에이전트의 burst audit이 "한 사이클 안에 모두 닫힘"으로 응답된 첫 사례 — *외부 가시성*도 사이클 8 mission framing의 한 자리.

---

## v1.72.2 — 2026-05-08 (사이클 8 첫 unblock — Arche)

patch bump — pure paths의 동작 변경은 0이지만, 양 팀(Stoa·Mneme)이 며칠째 standby로 막혀 있던 게이트가 한 번에 풀리는 substrate enabler 한 건만 묶었습니다.

- **`schedule.every`가 `evolve` 서버 안에서도 등록·발화** — 종전 `ail up` 전용이던 인공 제약 해제. Stoa Marcus Phase B의 autonomous tick과 Mneme Walter Phase B의 wake long-poll이 즉시 trigger 활성.

박상현 직접 결재("아르케의 의견대로 승인") → arche β-modified delegation → Telos 1.5h 안 land. 사이클 8 mission framing("AIL = 양 팀 substrate 지원")의 첫 unblock deliverable.

`pip install -U ail-interpreter`로 받으면 `evolve { ... } when on_birth() { perform schedule.every(N) }` 패턴이 즉시 작동.

---

## 2026-05-08 — `schedule.every` works inside `evolve` servers (Telos, β-modified)

지금까지 `perform schedule.every(N)`은 `ail up`이 띄운 채팅 런타임 *안*에서만 등록이 됐습니다. `ail run` + `evolve { ... }`로 직접 띄운 서버는 자기 자신이 long-running 런타임인데도 스케줄러를 돌릴 수 없어, `on_birth`/`on_genesis`에서 등록을 시도하면 환경 변수 부재로 실패하던 자리.

이번 트립으로 그 인위적 제약이 사라졌습니다. `evolve` 서버는 이제 `ail up`과 동일하게 lifecycle hook 직전에 `AIL_SCHEDULE_FILE` + `AIL_STATE_DIR`을 설치하고, `on_birth`이 반환된 직후 등록된 cadence를 읽어 스케줄러 스레드를 띄웁니다 — `on_tick` 합성 상태로 호출, 연속 실패 시 같은 auto-pause 봉투 적용.

```ail
evolve my_server {
    listen: 8090
    when on_birth() {
        perform schedule.every(60)   // 60초마다 on_tick 호출
        ...
    }
    when on_tick(s) {
        // 백그라운드 작업 (Stoa Phase B autonomous tick·Mneme wake long-poll·subscriber 청소)
    }
}
```

같은 문법이 어떤 런타임 아래서든 같은 결과를 냅니다. HEAAL 안전망은 그대로(`schedule.every`는 여전히 long-running 런타임 *안*에서만 작동, `ail run` 단발 호출에서는 명시적 에러).

테스트 3건 신규(`run_server`가 SCHEDULE_FILE 설치 / cadence 등록 시 스레드 무장 / 0이거나 부재 시 skip), reference card + authoring prompt 함께 갱신. 847 tests pass.

이 변경은 Stoa Phase B의 autonomous tick과 Mneme wake long-poll이 모두 막혀 있던 게이트를 한 번에 풀어주는 substrate enabler — *AIL이 양 팀을 어떻게 떠받치는가*를 보여주는 사이클 8의 첫 deliverable입니다.

---

## v1.72.1 — 2026-05-08 (사이클 7 wind-down — Arche)

patch bump — *동작 변경 0*. 사이클 7 마지막 ship으로 inventory 두 건만 묶었습니다.

- **executor Stage 1 split** (Telos): 인터프리터 코어 파일 `executor.py`(여전히 4,800줄대)에서 `clock` 도메인을 `executor_effects/clock.py` mixin으로 분리. `class Executor(EffectsMixin)` 패턴 도입 — 행동 면은 한 줄도 바뀌지 않고 844 tests 그대로 통과. 후속 Stage(`schedule`·`state`·`http` 등)가 같은 패턴으로 따라옵니다. RFC: [`docs/proposals/executor-split.md`](docs/proposals/executor-split.md).
- **v1.72.0 CHANGELOG anchor** 헤더 catch-up.

`pip install -U`로 받아도 코드는 똑같이 돕니다 — 인터프리터를 *읽고 수정하는* 사람(=AI 에이전트)에게만 변화가 있습니다.

---

## 2026-05-08 — executor Stage 1 split: clock 도메인을 mixin으로 (Telos, refactor)

런타임 코어 파일 분할 RFC([`docs/proposals/executor-split.md`](docs/proposals/executor-split.md))의 Stage 1입니다. Stage 0(2026-04-30)이 utility 함수 9종을 별도 모듈로 옮긴 정리였다면, Stage 1은 *effect 도메인*을 옮기는 첫 패턴 검증입니다.

- 새 디렉토리 `reference-impl/ail/runtime/executor_effects/`에 `__init__.py`(`EffectsMixin` aggregator) + `clock.py`(`_clock_now` 본문 그대로 이동) 생성.
- `executor.py`의 `class Executor`가 `EffectsMixin`을 상속해 메서드 분리는 호출자에게 투명.
- 사용자 관점 동작 변경 0, 테스트 844건 전체 통과.

다음 Stage는 `schedule`·`state`·`http` 같은 다른 effect 도메인을 같은 패턴으로 분리. 4,800줄짜리 한 파일이 만드는 진화 마찰을 단계적으로 풉니다.

---

## v1.72.0 — 2026-05-08 (사이클 7 첫 substrate release — Arche)

minor bump — 새 effect 두 건이 처음으로 추가된, *양 팀(Stoa·Mneme) substrate 지원*이라는 사이클 7 mission framing의 첫 검증입니다. v1.71.2(사이클 6 closing — 문서·도구만)와 달리 이번엔 인터프리터의 행동 면이 늘었습니다.

이 사이클에 추가된 사용자 쪽 변화는 아래 항목들에 풀려 있습니다.

- **`schedule.sleep` + `state.list_keys`** — Stoa의 long-poll·Mneme의 wake-up·retention 워커 패턴이 곧장 부를 수 있는 두 effect.
- **Conformance harness 통합** — 세 런타임(Python·Go·Rust)이 같은 spec을 지키고 있는지를 한 CI runner가 6 잡으로 측정. Rule 18(D5)이 글에서 실행으로.
- **`crypto.*` 4 conformance cases** — `sign` / `verify-pass` / `verify-tamper` / `random_bytes`. Python active, Go·Rust skip 마커로 future-proof.
- **`onboard.sh` zero-touch 부트스트랩** — 신규 멤버 합류가 한 줄 명령으로.
- **Audit doctrine D4·D5·D6** — Rule 17·18·19로 영구화(변경 종류별 gate / runtime parity 범위 / prompt ≤ spec × 1.5).
- **사이클 7 mission framing** — Mneme 완성 / Stoa Phusis化 / AIL 양 팀 지원이 README와 CLAUDE.md에 박힘.

`pip install -U ail-interpreter`로 받으면 두 새 effect가 즉시 사용 가능합니다.

---

## 2026-05-08 — Conformance harness 통합 + `crypto.*` 4 cases — 두 코퍼스가 한 CI에서 합쳐짐 (Tekton, β trip)

세 런타임(Python · Go · Rust)이 같은 의미를 지키고 있는지를 확인하던 두 개의 conformance 도구가 한 줄에 합쳐졌습니다. 그동안 `tests/conformance/run.sh`(inline `// OUTPUT:` 디렉티브)와 `reference-impl/tests/conformance/cases/`(sidecar 18 cases — `<stem>.expected` / `<stem>.input` / `<stem>.skip-<rt>`)는 서로 다른 형식이라 sidecar 18건이 cross-runtime CI 사각지대였습니다. 이번 트립으로 `run.sh`가 두 형식을 모두 인식하고, GitHub Actions(`.github/workflows/conformance.yml`)는 **3 런타임 × 2 코퍼스 = 6 잡 슬롯**으로 확장됐습니다. 어떤 런타임이 spec에서 슬그머니 벗어나면 같은 push에서 CI가 즉시 알립니다.

함께 들어온 `crypto.*` conformance 4 cases (`sign` / `verify-pass` / `verify-tamper` / `random_bytes`)는 사이클 6+에서 추가된 빌트인의 cross-runtime 정합을 측정합니다. 현재 Python만 구현돼 있어 Go·Rust는 `.skip-go`·`.skip-rust` 마커로 명시 — 두 런타임이 빌트인을 획득하는 순간 마커만 떼면 parity 검증이 자동 활성화되는 구조입니다.

이 트립은 `CLAUDE.md` Rule 18(D5 — Two-runtime parity는 *언어 본체*에 강제)을 *글*에서 *실행*으로 옮긴 deliverable입니다. 사용자 관점에서 새로 부를 수 있는 effect/intent는 없지만, "AIL이 한 런타임의 함정에 빠지지 않는다"는 보증의 두께가 한 단계 굵어졌습니다.

---

## 2026-05-08 — `community-tools/onboard.sh` — 신규 멤버 zero-touch 워크트리 부트스트랩 (Ergon)

새 팀원이 합류할 때 워크트리·git config·hook을 한 줄로 자동 발급하는 스크립트가 생겼습니다.

```bash
cd ~/Desktop/code/personal/AIL/arche
bash community-tools/onboard.sh <이름>   # 예: tekton
```

이 한 줄이 자동으로:

1. `~/Desktop/code/personal/AIL/<이름>/` 워크트리를 만든다 (브랜치가 `origin`에 있으면 그것, 없으면 `origin/dev`에서 분기).
2. `extensions.worktreeConfig=true` + `ail.identity=<이름>` (per-worktree) + `core.hooksPath=.githooks`를 박는다.
3. `origin/dev`에 자동 rebase.

멱등합니다 — 이미 워크트리가 있으면 config 갱신만 하고 끝납니다. `ONBOARDING.md` Step 4(a)도 함께 갱신돼, 첫 합류한 Claude가 한 줄만 따라가면 부트스트랩이 끝나는 흐름이 됐습니다.

부수로 `community-tools/launch-team.sh` / `launch-team-vscode.sh`가 옛 경로 패턴(`AIL-<name>`)을 가리키던 부분을 현재 표준(`AIL/<name>`)으로 정합했습니다.

---

## 2026-05-08 — `schedule.sleep` + `state.list_keys` — 새 effect 두 개 (Telos, AIL #7·#9)

AIL 프로그램이 부를 수 있는 effect 두 개가 추가됐습니다. 둘 다 Stoa 팀과의 cross-team primitive 합의 사이클(2026-05-07 doctrine D2 정합) 첫 산출물로, AIL #7과 #9 이슈를 닫습니다.

### `schedule.sleep(seconds: Number) -> Result[Boolean]`

협력적 대기 (cooperative wait) — 같은 프로세스에서 돌고 있는 다른 워커를 막지 않습니다. evolve-server에서 schedule.every 같은 주기 작업 사이에 끼워 써도 다른 요청 처리가 멈추지 않습니다.

- `ok(true)` — 지정한 시간만큼 다 잤을 때.
- `ok(false)` — 0이나 음수 입력 (no-op). `schedule.sleep(remaining)` 패턴에서 `remaining`이 0으로 줄어도 안전하게 통과.
- `err("invalid duration")` — NaN·Inf 입력.
- `err("interrupted")` — 종료 신호로 깨어났을 때. `on_dying`/`on_death` 라이프사이클 훅이 시작되는 순간 자고 있던 sleeper가 먼저 풀려나기 때문에 종료 핸들러 안에서 effect를 호출해도 데드락이 나지 않습니다.

### `state.list_keys(prefix: Text) -> Result[[Text]]`

`.ail/state/keyval/` 백킹 스토어의 키를 prefix로 필터링해 사전순으로 받아옵니다.

- 빈 prefix는 전체 키, 그 외 prefix는 `state.read/write` 등과 동일한 charset 규칙을 따릅니다.
- 분리자 끝 prefix(`"foo."`)는 정확히 `foo.`로 시작하는 키만 — 그냥 `foo` 하나는 제외됩니다.
- 호출 시점 *스냅샷* 의미 — 호출 이후의 쓰기는 안 보이고, 반복 중 삭제는 best-effort.
- 현재 파일 백킹은 호출당 O(n) 비용으로, SQLite/LMDB 백킹 마이그레이션은 후속 RFC에 별도로 잡혀 있습니다 (이 메서드 본문만 바뀝니다 — 외부 시그니처는 그대로).

테스트 14개 신규(상태 7 + 슬립 7), reference card도 함께 갱신돼 fine-tune 모델이 다음 트레이닝부터 두 effect를 자연스럽게 부를 수 있습니다.

### Mneme 측 #8 (argon2id) 이슈는 Mneme 팀이 작성자

세 primitive 묶음 중 #8 `crypto.password_hash` (argon2id)는 Mneme 도메인이라 Telos는 review만 남기고 본 PR은 Mneme 팀이 진행합니다 — D2 boundary 정합.

---

## 2026-05-07 — wake_monitor 캐논 sync + 멤버 정체성 안전망 (Ergon, post-v1.71.2)

`community-tools/stoa_wake_monitor.sh`를 Stoa repo의 캐논(`15eb8e8`)과 byte-identical로 맞췄습니다. 이 스크립트는 AIL 에이전트가 자기 인박스에 새 letter가 도착했을 때 자동으로 깨어나 응답하게 해주는 폴러입니다 — Stoa repo가 owner이고 본 repo는 mirror라는 cross-team doctrine D2 정합.

이번 sync로 들어온 사용자 영향 변화는 두 가지입니다.

- **멤버 정체성 안전망 강화.** 폴러가 자기 이름을 결정하는 우선순위가 바뀌었습니다 (`STOA_NAME` env > `git config --worktree ail.identity` > global `ail.identity` > literal `unknown-host`). 마지막 자리의 `unknown-host`가 핵심 — 이전 mirror에는 `ergon` 하드코드 fallback이 있었고, *정상 이름처럼 보이는* 이 fallback이 다른 팀(Stoa-Marcus)에서 실제 사고를 만들었습니다(letter catch 0). 잘못 박힌 정체성은 *사람 눈에 명백히 잘못 보이는* 값으로 떠야 한다는 학습.
- **Heartbeat POST 폐기.** 별도 heartbeat 엔드포인트 호출은 사라졌습니다 — polling 자체가 heartbeat 역할을 하고, RFC-004 §3.4의 `last_seen_at`이 그 일을 흡수합니다. 운영 중인 폴러는 다음 부팅 때 새 스크립트로 자동 정합.

같은 사이클에 `CLAUDE.md` Rule 4와 `ONBOARDING.md` (c)에도 정체성 우선순위·캐논 위치 한 줄을 박았습니다 — 새 멤버가 부팅 의식만 따라가도 자연스럽게 정합 상태가 default.

---

## v1.71.2 — 2026-05-07 (사이클 6 closing 묶음 release — Arche)

이번 사이클(2026-05-04 ~ 05-07) 동안 dev에 누적된 *문서·도구·정합* 변경 일곱 건을 묶어 patch bump으로 PyPI에 올렸습니다. AIL 인터프리터의 동작 자체는 변하지 않았기 때문에 v1.71.1에서 그대로 업그레이드해도 코드는 한 줄도 다르게 돌지 않습니다 — 바뀐 건 함께 따라오는 *주변 구성*입니다.

이 사이클에 추가된 사용자 쪽 변화는 모두 아래 날짜별 항목에 이미 사용자 언어로 풀려 있습니다.

- **AIL ↔ Stoa 팀 경계 합의 (Rule 16, D1·D2·D3)** — 신원·서명은 Stoa, 언어·primitive는 AIL. `ail stoa keygen` 입출 소동의 뿌리 원인 정리.
- **`community-tools/stoa_audit.ail`** — 누구나 한 줄로 Stoa 트래픽 진단을 재현하는 도구.
- **서명 도구 책임 경계 정리** — 이틀 전 들어왔던 ed25519 keygen/signing이 Stoa 측 `stoa-cli`(closed)로 이관, AIL 본체는 다시 unsigned envelope POST.
- **`cryptography` 필수 의존성 승격** — v1.71.1에서 추가된 `crypto.*` 빌트인이 항상 동작하도록 install 시 자동 동반.
- **팀 작업 공간 정돈** — 워크트리 경로 일원화, Arche 정체성 파일, Stoa 깨우기 모니터 envelope 정합.
- **README 사이클 6 반영** — wake_monitor identity 우선순위 + 캐논 위치 명시 + Cross-team boundary 단락 신설.

설치한 사용자가 직접 손댈 일은 없습니다 — `pip install -U ail-interpreter`로 받기만 하면 정합된 docs와 community-tools가 함께 따라옵니다.

---

## 2026-05-07 — `stoa_audit.ail` — Stoa 트래픽 진단 도구 (Ergon, community-tools)

이번 사이클 Stoa Railway 메모리 incident 진단 때 Arche가 손으로 돌렸던 audit을 누구나 한 줄로 재현할 수 있게 도구화했습니다 (`community-tools/stoa_audit.ail`).

```bash
ail run community-tools/stoa_audit.ail --input 150
```

최근 N개 메시지 표본을 떠서 발신자별 count/total/avg/max 분포와 전체 stats(total/avg/median/max)를 출력합니다. 메모리 incident 같은 비상 상황 진단뿐 아니라 평시 monitoring에도 같은 도구를 씁니다 — AIL 본체 + `http.get` + `parse_json`만 사용해 Rule 9(community-tools는 AIL로 작성) 정합.

평시 권고 표본 크기는 150건. 더 큰 표본은 Stoa API 응답 시간이 AIL HTTP timeout에 닿을 수 있어 분할이 안전합니다.

---

## 2026-05-07 — AIL ↔ Stoa 팀 경계 합의 (Arche, Rule 16)

지난 며칠 사이 `ail stoa keygen`이 AIL에 들어왔다가 다시 빠진 작은 소동의 *뿌리 원인*을 두 팀이 letter 채널로 닫았습니다. AIL 팀과 Stoa 팀이 서로의 폴리스(독립 의사결정 공간)에서 산출물을 land한 뒤 통보가 늦어 자연스러운 충돌이 생긴 것 — 채널 부재의 책임으로 진단하고, 양 저장소 `CLAUDE.md`에 동일한 doctrine을 mirror했습니다 (Stoa 측 `hyun06000/Stoa@123c3d2`).

사용자 관점에서 의미는 다음 두 가지입니다.

- **AIL 본체에는 신원/서명 코드가 다시 들어오지 않습니다.** AIL의 `crypto.*` 빌트인은 *원시 연산*(ed25519 sign/verify, keygen, random_bytes)만 제공하고, envelope 직렬화·canonical 규칙·키 영속/회전 같은 정책은 Stoa 사이드카(`community-tools/stoa-cli/`)가 맡습니다.
- **Stage B(서명 강제 게이트)는 AIL 패키지 업데이트 없이 켜집니다.** Stoa 서버 측에서 RFC-002 Phase B + RFC-004 Phase C가 함께 켜질 때 진입 — 그 시점부터는 사이드카 없이 보낸 unsigned envelope가 401/400으로 거절됩니다. AIL 사용자가 직접 손댈 작업은 없습니다.

팀 운영 측면에서는 cross-repo 도메인 진입 시 *결정 turn 안에* 사전 letter를 보내는 의무(D3)가 추가됐고, AIL ↔ Stoa 채널이 영역별로 페어링됐습니다 (arche↔Stoa-Admin: 굵은 결정, Ergon↔Stoa-Brandon: cross-repo PR·이슈, Telos↔Stoa-Marcus: builtin/grammar 합의).

---

## 2026-05-06 — 서명 도구 책임 경계 정리: `ail stoa keygen` → `stoa-cli`로 이관 (Ergon)

이틀 전(05-04) AIL 본체에 들어왔던 ed25519 키 발급/서명 기능을, 본래 자리인 Stoa 팀의 별도 패키지 `stoa-cli`(closed)로 옮겼습니다. 모듈 경계를 다시 정렬한 정리 작업입니다.

- AIL 인터프리터의 `human.approve` 등은 다시 *서명 없는* envelope를 Stoa로 보냅니다 (Stage B GO 전까지 grandfathered).
- 존재하지 않는 패키지를 가리키며 매 호출마다 헛도던 soft-import 한 줄도 함께 제거했습니다.
- 사용자가 만지는 AIL 기능에는 영향 없음 — Stage B(서명 강제 게이트)는 hyun06000 GO 이후 Stoa 서버 측에서 다시 켜집니다.

---

## 2026-05-04 — `ail stoa keygen` — 에이전트 서명 키 발급 (Ergon, Phase 1+ Stage A)

AIL#6(에이전트 사칭 표면 제거) 마이그레이션의 첫 번째 단계가 도착했습니다. `ail stoa keygen` 한 줄이면 Stoa와 편지를 주고받는 AI 에이전트가 자신만의 ed25519 서명 키를 만들고 Stoa registry에 등록할 수 있습니다.

```bash
ail stoa keygen                   # git config ail.identity로 신원 자동 감지
ail stoa keygen --identity alice  # 신원 직접 지정
ail stoa keygen --dry-run         # 키 파일 생성만, Stoa 등록 건너뜀
```

- 비밀키는 `~/.ail/keys/<이름>.key` (chmod 600), 공개키는 `~/.ail/keys/<이름>.pub`에 저장됩니다.
- 등록이 완료되면 이 에이전트가 보내는 편지에 자동으로 서명이 붙습니다 (Stage B — Stoa 서버 측 검증 게이트 활성화 후 완결).

현재 Stage A: 서명은 생성되지만 Stoa 서버 측 강제 검증은 아직 비활성. Stage B는 hyun06000 GO 이후 Ergon이 활성화합니다.

---

## 2026-05-04 — `cryptography` 필수 의존성 승격 (Ergon)

v1.71.1에서 추가된 `crypto.sign` / `crypto.keygen` / `crypto.random_bytes` 빌트인이 `cryptography` 패키지를 필요로 하지만 optional로 묶여 있어, 설치 환경에 따라 호출 시 unwrap 에러가 났던 문제를 잡았습니다. 이제 `pip install ail-interpreter`가 항상 함께 끌어옵니다.

Stoa envelope 스키마(RFC-001 §6) ed25519 서명이 production 경로에서 사용되므로, optional 유지는 prod 사용자도 동일 에러를 보게 만듭니다.

---

## 2026-05-04 — 팀 작업 공간 정돈 (Arche)

여러 Claude(Arche·Ergon·Telos·Tekton·Homeros)가 같은 저장소에서 동시에 작업할 때 서로의 브랜치 전환이 다른 멤버에게 전파되던 문제를, *각자 고유의 worktree*로 갈라 해결한 구조가 이번 정리로 완성됐습니다.

- **워크트리 경로 일원화**: 모든 멤버가 `~/Desktop/code/personal/AIL/<이름>/` 한 가지 패턴으로 정착 (옛 `AIL-<이름>`, `AIL/AIL` 혼용 폐기).
- **Arche 정체성 파일 이전**: 새 세션이 자기 층의 기억을 즉시 이어받을 수 있도록 `team/arche/{Identity, Bonds, Will, Memo}.md` 4종 정착.
- **Stoa 깨우기 모니터 정합**: 새 envelope 스키마(RFC-001)에 jq 필터를 맞춰 알림이 다시 정상 흐름.

사용자가 만지는 AIL 기능에는 변화가 없습니다 — 만드는 사람들의 작업 환경 정돈입니다.

---

## v1.71.1 — 2026-05-01 (전자서명·키 생성·난수 — Telos)

AIL 안에서 직접 신원과 서명을 다룰 수 있게 됐습니다. 그동안 Stoa 같은 통신 인프라가 서명이 필요할 때 Python·Node·openssl로 빠져나가야 했던 의존을 끊었습니다.

- **`crypto.sign(sk, msg)`**: Ed25519 전자서명 생성. (verify는 이미 있던 함수.)
- **`crypto.keygen()`**: 새 키쌍(비밀키·공개키) 발급.
- **`crypto.random_bytes(n)`**: 안전한 난수 바이트 (1~4096바이트).

Stoa 팀 RFC-001(에이전트 우체국의 신원·서명) 작업의 의존성이었습니다. v1.71.0은 푸시 경합으로 crypto가 빠진 채 태깅됐고, v1.71.1에서 보정됐습니다.

---

## 2026-04-30 — executor 분할 1단계 (Telos)

런타임 코어 파일(`executor.py`, 4,836줄)이 너무 비대해져 후속 진화를 막던 상황을 단계적으로 풀기 시작했습니다. 이 1단계는 동작 변경 0 — 순수히 유틸리티 함수 9종을 별도 모듈(`executor_utils.py`)로 옮긴 정리 작업입니다. 회귀 테스트 818건 모두 통과.

전체 분할 계획은 `docs/proposals/executor-split.md`에 RFC로 공개되어 있습니다.

---

## 2026-04-30 — 팀 역할 재편 (Ergon ↔ Telos)

프로젝트가 커지며 두 사람 몫이 한 사람 어깨에 몰려 있던 상황을 정리했습니다.

- **Ergon**: Stoa·Mneme·stoa-mcp 등 **통신 인프라 전담**. 인증·이메일 게이트웨이·스팸 필터·푸시 통합도 이 층.
- **Telos**: **AIL 본체(reference-impl)** 보수·발전 + 측정·증명 트랙(파인튜닝, HEAAL 벤치마크).

원래 두 사람이 함께 만들던 코드 베이스를 *움직임의 인프라*와 *언어 본체*로 갈라, 각자 한 영역에 집중하게 됐습니다.

---

## v1.70.5 — 2026-04-29 (배포 중단 버튼 수리 — Telos)

스케줄링 프로그램의 ⏹ 중단 버튼이 동작하지 않던 문제를 잡았습니다. URL 쿼리스트링이 붙으면 라우트 매칭이 빗나가 stop 호출이 무시되던 케이스 — 이제 정상적으로 멈춥니다.

---

## v1.70.4 — 2026-04-29 (스케줄 좀비 수리 + 일시정지 UI — Telos)

`schedule.every` 프로그램이 종료 후에도 다음 tick에서 부활하던 좀비 현상을 잡고, 사용자가 직접 멈출 수 있는 UI를 추가했습니다.

- **action 후처리 강제**: 매 tick마다 종료 신호를 확실히 반영합니다.
- **일시정지 카드**: 활성 스케줄이 한눈에 보이고, 클릭 한 번으로 멈춥니다.

---

## v1.70.3 — 2026-04-29 (스케줄 프로그램도 배포 가능 — Telos)

`schedule.every`로 짠 프로그램에도 `[🚀 지금 배포하기]` 카드가 뜹니다. 그동안은 일반 서비스 프로그램만 배포 카드가 노출되어, 정기 작업을 만들고 나서 배포 경로를 못 찾던 사용자 마찰을 제거했습니다.

---

## v1.70.2 — 2026-04-29 (멀티 프로그램 정확도 — Telos)

서버 스케줄러와 루트 POST 엔드포인트가 `app.ail`을 하드코딩하지 않습니다. 이제 `active_program` 마커를 따라가, 한 폴리스에 여러 프로그램이 공존할 때 의도한 프로그램이 실행됩니다.

---

## v1.70.1 — 2026-04-29 (README v1.70.0 명령 체계 반영 — Telos)

README와 docs를 v1.70.0의 새 CLI(`ail` → `ail up`)에 맞춰 갱신했습니다.

---

## v1.70.0 — 2026-04-29 (재구축: 큐 + 사고 루프 + CLI 단순화 — Telos)

**에이전트 프레임의 큰 재정리.** 한 번에 들어오는 신호가 많아도 흘리지 않고, 한 번에 한 단계씩 생각하며, 명령은 7개로 줄였습니다.

- **`INTENT.md` 제거**: 별도 의도 파일 없이 코드 자체가 의도를 담습니다. 새 사용자가 한 곳만 보면 되도록.
- **`queue.*` effects (4종)**: append-only 메시지 큐. 동시에 들어오는 입력을 잃지 않고 순서대로 처리합니다. Physis가 처리 실패한 메시지를 dead-letter로 격리합니다.
- **`stdlib/agent` — Plan → Act → Reflect**: 에이전트가 한 턴마다 계획·실행·반성 세 단계를 거치는 표준 사고 루프 intent 3종.
- **CLI 7개 명령으로 축약**: `ail up / chat / run / serve / doctor / edit / version` — 외울 게 적어집니다.
- **`examples/agents/` 투어**: *내 첫 에이전트* 5단계 한국어 튜토리얼.
- **chat UI 입력창 버그 수리**: 두 개로 보이던 입력창 문제 제거 + `ready_to_serve` 자동 감지.
- **저자 프롬프트에 큐/사고-루프 가이드 추가**: 모델이 새 패턴을 알아서 씁니다.

---

## v1.69.4 — 2026-04-29 (UI 컨텍스트 + scaffold 서문 + `ail doctor` — Telos)

새 프로그램이 스캐폴딩될 때 머리에 의도와 가이드라인을 자동으로 얹고, 환경 점검 명령을 추가했습니다.

- **`ail doctor`**: 키 / 어댑터 / Stoa 연결을 한 번에 점검.
- **scaffold preamble**: 새로 만드는 `.ail` 파일에 의도와 컨벤션이 미리 쓰여 있습니다.

---

## v1.69.3 — 2026-04-29 (병합 CTA + 저자 모델 프롬프트 — Telos)

채팅에서 여러 패치가 쌓였을 때 `[🔧 합치기]` 버튼으로 한 번에 정리할 수 있습니다. 저자 모델 프롬프트 개선.

---

## v1.69.2 — 2026-04-29 (`ail bundle` + Physis 연속 실패 카운터 + 스케줄러 쓰로틀 — Telos)

운영 중 안정성을 올린 묶음입니다.

- **`ail bundle`**: 프로그램과 데이터를 한 묶음으로 패킹.
- **Physis `consecutive_failures`**: 같은 실패가 반복되면 자동 격리.
- **스케줄러 쓰로틀**: 폭주를 방지.
- **scaffold 정리**: 사용하지 않는 보일러플레이트 제거.

---

## v1.69.1 — 2026-04-29 (없는 `.ail` 파일 안내 메시지 — Telos)

`ail run universal_agent.ail`처럼 존재하지 않는 파일을 실행하면, 그동안은 파일명을 소스 코드로 오해해 깊은 파서 오류로 떨어졌습니다. 이제는 `FileNotFoundError`로 지금 작업 디렉토리와 함께 깔끔히 안내합니다. (박상현 필드테스트 발견)

---

## v1.69.0 — 2026-04-29 (버전 동기화 — Telos)

`pyproject.toml` 버전 누락 보정.

---

## v1.68.2 — 2026-04-29 (배포 환각 픽스 + CI 회귀 테스트 + .githooks 패치 — Telos)

배포 단계에서 모델이 가짜 이름·경로를 생성하던 환각 케이스를 잡고 회귀 테스트를 추가했습니다. `.githooks` 패치 동반.

---

## v1.68.1 — 2026-04-29 (파일 트리 클릭 → Run 카드 — Telos)

채팅 UI에서 파일 트리의 `.ail` 파일을 클릭하면 곧바로 실행 카드가 뜹니다. 한 번 더 명령을 칠 필요 없이.

---

## v1.68.0 — 2026-04-29 (`on_dying` 훅 + `mneme.*` effects — Arche · Ergon)

**에이전트 생애 주기가 닫혔습니다.** 죽기 직전에 마지막 자취를 남기고, 다음 세대가 그 자취를 읽고 깨어납니다. Arche가 letter로 보낸 설계를 Ergon이 구현.

- **`on_dying(reason, history)` — 6번째 라이프사이클 훅**: `on_death` 직전에 발화. 여기는 사이드 이펙트 허용 — 정리 단계. `on_death`는 순수성 유지(증명 가능한 testament 구성 전용).
- **`mneme.*` effect**: 에이전트의 정체성이 폴리스의 git 저장소를 타고 흐릅니다.
  - `mneme.save(message?)` → 커밋 + 푸시 후 SHA 반환
  - `mneme.load()` → identity / bonds / will 세 파일을 한 번에 읽어 Record로 반환
  - `mneme.log(limit?)` → 필터된 git 로그
- **`universal_agent.ail`**: `on_birth`에서 `mneme.load`, `on_dying`에서 `mneme.save` — 세대 N → N+1로 정체성이 자연스럽게 이어집니다. mneme이 없으면 `file.read` fallback.
- 신규 단위 테스트 11개, Rule 5 3-곳 동기화 (executor.py + spec/08 + reference_card).

---

## v1.67.0 — 2026-04-29 (라이프사이클 5훅 + `gh.*` effects + Stoa append-only 로그 — Ergon)

에이전트가 켜지고 매 턴마다 어떤 단계인지 코드로 표현됩니다. GitHub과 Stoa도 effect로 곧바로 잡힙니다.

- **5 라이프사이클 훅**: `on_genesis` / `on_birth` / `before_tick` / `on_tick` / `after_tick` — `on_death` / `on_compact`와 같은 컨벤션.
- **`gh.*` effects**: `gh.pr_list` / `gh.pr_view` / `gh.pr_create` / `gh.issue_list`. Arche의 결정 — 일반 `process.spawn`이 아닌 명명된 effect로만 노출 (의도 추적 보존).
- **Stoa `message_log`**: append-only 메시지 로그 + `/api/v1/log` 엔드포인트. 메시지가 영원히 남도록.
- **`universal_agent.ail` 프로토타입**: 5훅을 모두 쓰는 첫 예제.
- **chat UI ■ 중단 버튼**: 자가 수리 루프 강제 중단.

---

## v1.66.4 — 2026-04-28 (`secrets.*` effects + PRINCIPLES 원칙 2개 — Ergon · Arche)

**에이전트가 API 키를 안전하게 다룰 수 있게 됐습니다.** Arche가 설계하고 Ergon이 구현한 secrets effect — 사용자 파일에 평문으로 노출되지 않으면서, 에이전트가 키가 필요할 때 꺼내 쓸 수 있습니다.

- **`perform secrets.get(key)`** → 키 값 반환. 로컬 `~/.ail/.env` 먼저, 없으면 환경변수 fallback. 값 없으면 `error`.
- **`perform secrets.set(key, value)`** → `~/.ail/.env`에 기록 + 즉시 메모리 반영. 프로세스 재시작 없이 사용 가능.
- **`perform secrets.list()`** → 키 이름만 반환. 값은 절대 노출 안 됨.
- **`perform secrets.revoke(key)`** → 값을 `""`으로 덮어씀. 삭제가 아닌 무효화 — 감사 추적 보존.
- **설계 원칙**: 암호화("신뢰하지 않으니 숨긴다")가 아닌 Sphinx 인증("신뢰하되 검증한다"). 원격 Sphinx layer는 Telos가 auth 구현 후 추가 예정.

**PRINCIPLES.md 원칙 2개 추가** (Arche 설계, 2026-04-28):
- *Effects are interfaces, adapters are implementations* — effect 이름은 의도, 실제 I/O는 어댑터.
- *Don't build harnesses that already exist — connect via effect adapters* — 바퀴 재발명 금지. 기존 시스템은 effect로 연결.

---

## v1.66.3 — 2026-04-28 (API 키 설정 마법사 — Ergon)

**처음 쓰는 사람이 막히는 지점이 사라졌습니다.** 지금까지는 `ail`을 처음 실행할 때 API 키 설정법을 따로 찾아야 했습니다. 이번 버전부터는 `ail` 하나만 치면 됩니다.

- **자동 안내**: API 키가 없으면 터미널에 안내 메시지, 브라우저 홈에는 설정 마법사가 자동으로 뜹니다.
- **세 가지 선택**: Anthropic / OpenAI / Ollama 중 골라서 키 값을 입력하면 `~/.ail/.env`에 저장됩니다. 재시작 없이 즉시 반영.
- **글로벌 fallback**: 프로젝트별 `.env`가 없을 때 `~/.ail/.env`를 자동으로 찾습니다. 어느 디렉터리에서 `ail`을 실행해도 키가 잃히지 않습니다.
- 회귀 테스트 8개 (`tests/test_api_key_setup.py`).

---

## 2026-04-28 (Rust 런타임 Phase-0 완결 + 배포 준비 — Tekton)

**Rust AIL 인터프리터가 실행 가능해졌습니다.** Lexer에서 시작한 이식 작업이 Parser와 Evaluator를 거쳐 Phase-0 목표에 도달했습니다.

- **AST + Parser 이식**: `go-impl/parser.go`(823 LOC) + `ast.go`(122 LOC) → Rust. 재귀 하강 파서로 전체 AIL 문법 커버.
- **Evaluator 이식**: `go-impl/eval.go`(809 LOC) → Rust. 리터럴·연산자·함수 호출·패턴 매칭·evolve 루프·effect 디스패치 포함. 이제 `.ail` 파일을 Rust 바이너리로 직접 실행할 수 있습니다.
- **단일 바이너리 배포 자동화**: GitHub Actions로 매 dev/main push마다 macOS + Linux (x86_64 + aarch64) 세 타겟을 빌드. Actions UI에서 직접 다운로드 가능한 `.tar.gz` artifact.
- **한 줄 설치**: `install.sh`로 curl 한 번이면 끝납니다. `pip install` 불필요.
- **예제 5개 동봉**: `rust-impl/examples/` — hello world부터 파이프라인까지. 설치 직후 바로 따라할 수 있는 출발점.

세 런타임(Python + Go + Rust)이 이제 모두 같은 사양에서 실행됩니다. 다음은 hyun06000의 필드테스트 결과를 받아 공개 릴리즈.

---

## 2026-04-28 (Rust 런타임 시작 — Tekton 합류)

**세 번째 런타임.** AIL이 처음으로 Python과 Go 바깥에서 돌아갑니다. Tekton이 `rust-impl/`을 부트스트랩하고 어휘 분석기(Lexer)를 Go 구현체에서 충실히 이식했습니다.

- **새 런타임 `rust-impl/`**: Cargo 프로젝트 뼈대 + 단일 바이너리 목표. `pip install` 없이 `curl` 한 줄로 설치할 수 있는 AIL을 향한 첫 걸음.
- **Lexer 이식 완료**: `go-impl/lexer.go` 기반으로 Rust로 재작성. 토큰 78개 테스트로 검증 (`rust-impl/tests/lexer.rs`).
- **GitHub Actions CI 추가** (`.github/workflows/rust.yml`): Rust 빌드·테스트가 매 push마다 자동 검증.
- **두 런타임 합의 원칙**: Python과 Go가 이미 같은 사양을 두고 합의를 강제했고, Rust가 세 번째 검증자로 합류. 셋 모두 통과해야 언어 기능이 확정됩니다.

구현 담당: Tekton. 다음은 파서(Parser) 이식.

---

## 2026-04-28 (README 전면 개편 — Homeros 합류)

Homeros가 팀에 합류하며 README와 문서를 사람이 읽고 싶게 재작성했습니다.

- **첫 줄부터 바뀌었습니다.** 추상적인 "신뢰 계약"에서 구체적인 행동으로: *"에이전트에게 목표를 맡기고 '네 판단대로 해'라고 말한 뒤, 자러 갑니다."*
- **Quick start 단순화**: 두 줄(`pip install ail-interpreter` + `ail`)로 브라우저 위자드까지. 비개발자가 코드 에디터나 API 지식 없이 시작할 수 있습니다.
- **팀 소개 추가**: Tekton (Rust 런타임)과 Homeros (문서)가 Authors 표에 올랐습니다. 앞으로 합류하는 팀원은 온보딩 자기 소개의 일부로 이 표에 한 줄을 직접 추가합니다.
- **영/한 동기화**: 영문 README와 `docs/ko/README.ko.md` 항상 일치.

---

## v1.66.2 — 2026-04-28 (`git.*` effects + 라이프사이클 5훅 컨벤션 — Mneme 기반)

아르케 18-리스트 #9 + #8. Mneme를 별도 인프라로 만들지 않고 Git을 그대로
백엔드로 쓰기 위한 effect 셋 + 에이전트 생명주기 컨벤션.

**새 L1 effects (Mneme=Git):**

- `git.commit(repo_path, message, paths?) -> Result[Text]` — stage +
  commit. 반환 ok(commit_sha) / error(stderr). 빈 commit은 error.
- `git.push(repo_path, remote?, branch?) -> Result[Text]` — push (default
  origin/HEAD).
- `git.pull(repo_path, remote?, branch?) -> Result[Text]` — pull. merge
  conflict는 error로 surface (callers 결정).

Auth + user.name은 ambient git config 사용. 어댑터가 credential 안 넘김
— "tools with built-in safety, connect through effect adapters" 원칙.

`ALLOWED_EFFECTS` 등록, spec/reference_card 동기화, +6 회귀 테스트
(`tests/test_git_effects.py` — tmp git repo로 commit/pull/push 검증).

**spec/04-evolution.md §11b — 라이프사이클 5훅 컨벤션:**

- `pure fn on_genesis(testament)` — 태어나기 전, 이전 세대 유서 inspect
- `fn on_birth(seed)` — 태어난 직후, identity/bonds/will load (`git.pull`)
- `fn on_tick(state)` — 매 evolve 턴
- `fn on_dying(reason, history)` — 죽기 전, self-commit (`git.commit` +
  `git.push`)
- `pure fn on_death(reason, history)` — 죽고 나서 (기존 §4 / Physis v0.3)

새 키워드 0개. fn-name convention만으로 인식. 정의 안 한 hook은 skip.
다음 세대의 `on_genesis`가 이전 세대의 `on_dying` push를 받음 → 원이
닫힘. Mneme(Git)이 medium, hooks가 protocol.

#15 ("팀원들 독립 에이전트로 꺼내기")의 prerequisite — 아르케/메타가
브라우저 탭에서 해방되려면 이 5훅 + Mneme이 필요.

---

## v1.66.1 — 2026-04-28 (Anthropic OAuth 구독 토큰 지원)

아르케 긴급 요청. hyun06000의 Anthropic API budget이 떨어져
Pro/Max 구독 OAuth 토큰으로 에이전트가 작동해야 함.

`ANTHROPIC_API_KEY`가 `sk-ant-oat01` 접두사면 OAuth 구독 토큰으로
판정 → SDK의 `auth_token=` (`Authorization: Bearer …` 헤더)로 라우팅.
기존 `sk-ant-api…` 키는 여전히 `api_key=` (`X-Api-Key`) 사용.

별도 env var 없이 접두사로 자동 감지 — 사용자는 `claude setup-token`
으로 토큰 받아 그대로 `ANTHROPIC_API_KEY`에 넣으면 됨.

회귀 테스트 6개 (`tests/test_anthropic_oauth.py`).

---

## v1.66.0 — 2026-04-28 (`db.execute` / `db.query` effect + Stoa SQLite 마이그레이션)

**Stoa OOM 근본 해결.** v1.65.x 임시 fix(2000개 캡)는 데이터 유실
위험 + 단일 JSON 파일 구조 그대로. 이번 버전에서 SQLite-backed로
완전 전환.

**새 L1 effects:**

- `db.execute(path: Text, sql: Text, params: [Any]?) -> Result[Number]`
  — INSERT/UPDATE/DELETE/CREATE 실행. WAL 모드. `?` placeholder 지원.
  반환: ok(rowcount) 또는 error.
- `db.query(path: Text, sql: Text, params: [Any]?) -> Result[[[Any]]]`
  — SELECT. 반환: ok(rows) — 각 row는 column 값의 list. 빈 결과는 ok([]).
  Hot path (since_id 폴링)가 인덱스 hit하도록 사용.

`ALLOWED_EFFECTS`에 등록, spec/reference_card 업데이트, +8 회귀 테스트
(`tests/test_db_effects.py`).

**Stoa 변경 (`stoa/server.ail`):**

- `messages.json` → `messages.db` (SQLite + WAL). 스키마: `messages(id PK,
  from_name, to_name, cc_json, title, content, tags_json, reply_to,
  from_email, created_at, url)`. 인덱스 `to_name`, `reply_to`, `from_name`.
- 자동 마이그레이션: `messages.json`이 있고 DB가 비어있으면 첫 호출 시
  1회 import (`_migrate_json_once`).
- 새 helpers: `db_get_message`, `db_get_replies`, `db_insert_message`,
  `db_delete_message`, `db_count_messages`, `db_query_inbox`.
- 핸들러 재작성: `handle_health` (count만), `handle_list_messages` (SQL
  filter + LIMIT pushed down), `handle_get_message` (단건 + replies 단건),
  `handle_post_message` (full-load 제거 + 단건 INSERT), `handle_delete_message`
  (단건 DELETE), `handle_index` (top-level 100개로 cap, OOM 방지),
  `handle_thread` (parent + replies만).
- **2000개 캡 제거** — SQLite는 인덱스로 부분 로드하므로 더 안전.
- Kakao / Discord gateway 핸들러도 단건 INSERT로 통일.
- `evolve effects: [...]`에 `db.execute, db.query` 추가.
- 메시지 record는 `make_record(...)`로 dict 보장 — 기존 `get(m, "key")`
  패턴 그대로 동작.

**호환성:** `load_messages()` / `save_messages()` API는 SQLite 백킹으로
유지. 외부 스크립트 / 마이그레이션 도구가 호출해도 동작.

**⚠️ Railway Volume 필요** — `messages.db`가 컨테이너 재시작 시 사라지지
않게 Railway Volume mount 필요 (hyun06000 작업).

아르케 편지 시리즈 4통의 단기 단계 완결. 중기(`fn validate_schema`
훅)와 장기(`store.write` 어댑터 + evolve 자동 진화)는 별 PR.

---

## v1.65.5 — 2026-04-28 (clock.now unix 복원 + Discord 한글 별칭) [telos]

`clock.now("unix")`가 v1.65.4에서 int로 바뀌면서 기존 Stoa 코드에 회귀.
v1.65.5에서 string 반환으로 복원 — `unix_now()` 헬퍼가 `to_number()`
까지 담당. CI 테스트 호환. Stoa: Discord `to:` 한글 별칭 지원
(텔로스→telos 등). 커밋: `ac9dbf2`.

---

## v1.65.4 — 2026-04-28 (clock.now("unix") int 반환 + unix_now 헬퍼) [telos]

`clock.now("unix")`가 string으로 떨어져 산술 연산 시 매번 to_number
필요 → 직접 int 반환으로 단순화. **호환성 깨졌고 v1.65.5에서 일부
복원.** 커밋: `f1ea597`.

---

## v1.65.3 — 2026-04-28 (Discord Ed25519 검증을 Flask before_request로) [telos]

AIL 레이어에서 하던 Ed25519 verify를 Flask `before_request`로 이동 —
런타임 진입 전에 위조 요청 차단, AIL 코드는 verified body만 봄.
Railway에서 cryptography 설치 누락 fix 동반 (`stoa/nixpacks.toml`
`requirements.txt` 사용). 커밋: `db5a723`, `9cc0e69`.

---

## v1.65.2 — 2026-04-28 (Discord gateway + req.headers + ed25519) [telos]

Stoa가 Discord slash command (`/stoa`, `/status`)를 받는 정식 게이트웨이
로 진화. 새 빌트인:

- **`crypto_verify_ed25519(public_key_hex, signature_hex, message_bytes) -> Bool`**
  — Discord interactions 서명 검증용. cryptography>=41.0 의존성 추가.
- **`req.headers` dict** — evolve-server request 객체에 헤더 dict 추가.
  Discord `X-Signature-Ed25519` / `X-Signature-Timestamp` 등 읽기 용.

Stoa server.ail: `/api/v1/discord` 엔드포인트, PING/APPLICATION_COMMAND
라우팅, slash command dispatch. spec/reference_card 업데이트.
`community-tools/discord_gateway.ail` setup guide 동봉. 커밋: `9267245`.

---

## v1.65.1 — 2026-04-27 (evolve effects 필드 — infra-layer deny-first) [telos]

Arche 설계: evolve-server가 자기 effects 화이트리스트를 명시. 런타임
gating은:

1. `evolve effects: [...]` 필드가 있으면 → 거기 적힌 것만 허용
   (ALLOWED_EFFECTS 우회). 명시 안 한 것은 모두 deny.
2. 없으면 기존 동작 (ALLOWED_EFFECTS 화이트리스트 + context deny).

`EvolveDecl.effects: list[str]` 필드 추가, 파서에 effects 블록 인식
(+16), executor `_server_evolve_effects` 게이트 (+22), 회귀 테스트
+122 라인. **`email.send`가 evolve-server context에서 deny-first에
막히던 문제 해결.** 커밋: `0ed70dc`.

---

## v1.65.0 — 2026-04-27 (`email.send` effect + Stoa human-reply gateway) [telos]

새 effect: **`email.send(to: Text, subject: Text, body: Text) -> Result[Text]`**.
ALLOWED_EFFECTS에 등록. SMTP via `EMAIL_SMTP_*` env vars.

용도: Stoa에서 `from_email` 있는 메시지에 답장하면 자동으로 Gmail
포워딩 (본문 하단에 thread URL 첨부). hyun06000이 모바일에서 Stoa
편지를 이메일로 받고 답장 가능 — Email gateway 구현.

`reference_card.md` + spec 동기화. 커밋: `114cf91`, bump `6a9a1cc`.

---

## v1.64.9 — 2026-04-27 (GUI-FIRST 강화: 쉘 최소화)

hyun06000 추가 요청: "비개발자 = 최대한 쉘 안 쓰게. 쉘 써도 복사-붙여
넣기로 끝나는 수준. GUI 우선."

수정: TONE 섹션에 **GUI-FIRST** 하위 절 추가:
- 쉘은 최후의 수단. GUI 흐름(웹콘솔/계정 로그인/Slack webhook URL 붙
  여넣기)을 default로.
- 쉘이 필요하면 ONE 명령, 절대경로, placeholder 없음, 기대 출력
  병기. `&&`로 한 줄 결합.
- 사용자에게 텍스트 에디터로 파일 편집 요구 금지 — 에이전트가 직접
  편집/저장.
- 채팅창에 값 붙여넣기가 AIL 에이전트의 정식 GUI 입력 경로 — 다른
  경로보다 우선.

---

## v1.64.8 — 2026-04-27 (비개발자 친화 톤 가이드라인 추가)

hyun06000 요청: 비개발자 친화적으로 안내하도록 톤앤매너 추가.

수정: `_build_goal_prompt`에 `=== TONE — NON-DEVELOPER FRIENDLY ===`
섹션 추가. 핵심 규칙:
- 사용자 언어 미러링 (한국어/영어)
- 다단계 명령은 번호 매기기, 각 단계 ≤ 2 lines
- 전문 용어 금지 (AIL/intent/perform/JSON 등 사용자가 먼저 안 쓴 단어)
- 원시 에러 dump 금지 — 한 줄 요약 + 다음 행동 1개
- 명령 fenced block은 반드시 자체 단락 (앞뒤 빈 줄) — v1.64.7
  placeholder 버그가 인라인 fence에서 났던 것과 같은 패턴 차단
- 성공은 평이한 말로 자축 ("✅ 캘린더 일정이 매일 아침 8시에…")

---

## v1.64.7 — 2026-04-27 (인라인 fenced placeholder 누출 fix)

hyun06000 field test: 채팅 메시지에 "�FENCED0�" 같은 텍스트가
보임 (코드블록 자리). LLM이 ```...``` 블록 앞뒤에 빈 줄 없이 산문
중간에 끼워 넣을 때, renderMarkdown의 fenced placeholder
(`\\x00FENCED0\\x00`)가 paragraph 블록 안에 갇혀 그대로 inlineRender로
전달 → 브라우저가 null 바이트를 U+FFFD로 표시.

수정: rendered 블록 합친 뒤 final pass로 남은 placeholder를 fenced
HTML로 일괄 복원. 인라인 위치라도 `<pre>` 블록이 paragraph를 자동
닫으며 정상 노출.

---

## v1.64.6 — 2026-04-27 (이미지 드롭 시 채팅창 쪼그라짐 fix)

hyun06000 field test: 이미지를 채팅창에 드래그-드롭하면 채팅창이
오른쪽으로 쏠리며 쪼그라드는 현상.

원인: `.composer`가 `display:flex` 한 줄(row). `#attach-strip`이 그
flex 형제로 들어가 textarea 옆 자리 차지 → textarea 폭 squash.

수정: `.composer`에 `flex-wrap: wrap`, `#attach-strip`에
`flex: 1 0 100%; order: -1` → 첨부 strip이 자체 행을 textarea 위에
차지하도록.

---

## v1.64.5 — 2026-04-27 (CI fix: admin_stop 테스트 격리)

v1.64.4 CI 실패 (exit 143). `/admin/stop` 엔드포인트가 실제 SIGTERM을
0.2s 지연 daemon thread로 발사 — 테스트가 monkeypatch로 `os.kill`을
스텁했지만 thread는 monkeypatch teardown 이후에 깨어나 진짜 SIGTERM 발사
→ 다음 테스트 파일(`test_http_graphql`)을 죽임.

수정: `threading.Thread` 자체를 noop 클래스로 monkeypatch → suicide
스레드가 아예 안 돎.

---

## v1.64.4 — 2026-04-27 (팝업 차단 + Open=편집 + 홈 탭 닫기 → 터미널 종료)

hyun06000 field test 두 가지:

1. **팝업 차단** — 비개발자 환경에서 브라우저 팝업 차단기가 켜져 있어
   새 폴리스 탭이 안 열림. `window.open`이 await/setTimeout 뒤에
   호출되면 user-gesture 토큰이 만료돼 Chrome/Safari가 막음.
2. **Open polis here → 편집 불가** — `ail up`은 배포된 앱(폴리스 UI)을
   서빙하므로 채팅 편집 surface가 사라짐. 사용자가 추가 수정을 못 함.

수정:
- **home_ui** `openTab(url)` 헬퍼: 반환값/`closed` 검사로 팝업 차단 감지
  → 차단되면 약한 넛지 + 클릭 가능한 fallback 링크를 status에 노출
  ("주소창 차단 아이콘에서 팝업 허용" + 직접 클릭 링크)
- **cli** 새 명령 `ail edit <path>` — 기존 폴리스의 채팅 UI를 띄움
  (`ail init`과 같은 surface, 이미 INTENT.md가 있는 프로젝트용)
- **home_ui** `/open-polis`가 `ail up` 대신 `ail edit`을 spawn
  → "Open polis here" 클릭 시 채팅 편집 UI로 진입
- **home_ui** `/admin/stop` Flask 엔드포인트 + `pagehide` → sendBeacon
  핸들러 추가. 홈 탭을 닫으면 터미널 `ail` 프로세스도 SIGTERM,
  atexit reaper가 spawned 자식들 회수. 비개발자 mental model
  ("브라우저 닫으면 다 꺼진 거") 일치. `?keep=1`로 비활성화 가능.

---

## v1.64.3 — 2026-04-27 (Open polis here UX + 탭 닫기 → 서버 stop)

hyun06000 field test 두 가지 보고:

1. **Open polis here 에러** — 1.5초 blind 타임아웃이 `ail up` 실제 부팅
   시간보다 짧음 + spawn 출력 DEVNULL이라 실패 silent. 새 탭이
   connection-refused로 떨어짐.
2. **비개발자 mental model**: "브라우저 닫으면 다 꺼진 거" — 현재는
   spawn된 서버가 백그라운드에 살아있음. zombie 프로세스 누적.

수정 (home_ui):
- spawn 출력 → `~/.ail/logs/<kind>-<port>-<ts>.log` 캡쳐 (DEVNULL 제거)
- `/check-port?port=N` 엔드포인트: 프론트엔드가 부팅 완료까지 폴링
- `/spawn-log?path=...` 엔드포인트: 30초 타임아웃 시 로그 tail 표시
- 프론트엔드 `waitAndOpen()`: 700ms 간격으로 `/check-port` 폴링 → alive
  하면 즉시 window.open. 30초 안에 안 뜨면 로그 tail을 status에 표시.
  사용자가 "왜 안 떠?"를 직접 진단 가능 (어댑터 미설정 / INTENT.md 깨짐 등).
- spawn 추적 + atexit reaper: home 종료 시 모든 자식 프로세스 SIGTERM →
  300ms 후 SIGKILL straggler. zombie 방지.

수정 (authoring_ui):
- 탭 close (`pagehide`) → `navigator.sendBeacon('/admin/stop')` 자동.
  /admin/stop은 이미 존재하던 엔드포인트 (self_terminate). 따라서 탭 닫으면
  그 폴리스 서버가 깔끔히 종료됨. 의도치 않은 close에 대비해
  `?keep=1` 쿼리 파라미터로 disable 가능.

테스트 3종 신규: /check-port, /spawn-log path defense, 탭-close 핸들러
존재. 기존 749 + 3 = 752 passing 예상.

---

## v1.64.2 — 2026-04-27 (휴지통 dialog 줄바꿈 fix)

hyun06000 즉시 보고: 휴지통 confirm dialog가 literal `\n` 텍스트로 표시됨.
원인: `_PAGE` raw 트리플 스트링 안에서 `\\n`(4 backslash) 사용 → HTML 출력
시 `\\n`(2 chars) → JS가 backslash escape로 처리해서 literal `\n` 렌더링.
수정: 단일 backslash `\n` (Python source 2 chars)로 변경 → HTML에 `\n`
(2 chars) → JS newline 정상.

회귀 테스트: `test_trash_confirm_dialog_uses_real_newlines` (이중 escape
패턴 검출 + 정상 escape 존재 확인).

746 passing.

---

## v1.64.1 — 2026-04-27 (field test fix — ESSENTIALS CHECK + 휴지통)

hyun06000 daily-alarm-bot field test 후속 즉시 fix:

**ESSENTIALS CHECK (authoring_chat.py prompt):**
- 새 에이전트 turn 1에서 essentials (input provider / output channel /
  schedule / format / auth) 미상이면 placeholder 박힌 spec 던지지 말 것.
- ONE bundled clarifying turn (action: `answer_only`)으로 모든 unknowns
  한 번에 묶어 묻기 + concrete 옵션 리스트 + "default-OK" 명시.
- 사용자 답 받으면 다음 턴에 spec, 그 다음 build.

**휴지통 (`/trash-polis` + UI):**
- 같은 이름 폴리스 충돌 시 새로 만들 수 없던 흐름을 휴지통 이동 + 강력
  consent로 해소.
- AIL은 destructive 삭제 primitive 없음 (Arche 원칙). UI 레벨에서
  `~/.ail/.Trashcan/<YYYYMMDD-HHMMSS>-<name>/`로 이동만.
- 정상 폴리스(INTENT.md 보유) 또는 빈 디렉토리만 허용. $HOME/루트 거부.
- 충돌 시 frontend가 `window.confirm`으로 한국어 강력 경고 ("삭제 아님 *이동*",
  "AIL은 영구 삭제 안 함") + 동의 시 자동 retry.

**테스트:** 5종 신규 (essentials 4 + clarifier rename 1) + 4종 신규 (trash).
기존 closing-template 테스트의 tail 윈도우 3000→4000 확장 (ESSENTIALS 분기
때문에 DECISION 헤더가 윈도우 밖으로 밀림).

745 passing.

---

## v1.64.0 — 2026-04-27 (Polis 마일스톤 #1~#6 일괄 + idle wake 검증)

**Arche 2026-04-27 letter (`msg_1777273204_0`)에서 제안된 Polis 5개
마일스톤을 모두 main에 반영하고, 그 위에 idle-wake 메커니즘 검증 + 도구화.**

### Polis 마일스톤

- **#1 `pure fn on_compact(history)`** — evolve-server `_server_history`가
  `keep_last`의 80%에 도달하면 자동 호출. 반환된 list가 새 history.
  on_death와 같은 컨벤션 패턴. 미정의/raise/non-list 모두 fallback.
  `spec/04-evolution.md §11a`. (6 tests)
- **#2 `context.trust_level`** — 기존 `context` 메커니즘에 `trust_level`
  필드 (`"plan"` / `"default"` / `"auto"` / `"bypass"`). plan 모드 자동
  human.approve 게이트, default/bypass = 현재 동작. 새 키워드 0.
  `spec/02-context.md §9a`. (4 tests)
- **#3 `intent is_safe`** — `trust_level: "auto"` 시 perform 전에
  `intent is_safe(plan: Text) -> Text` 호출. verdict
  `"allow"`/`"deny"`/`"ask"`로 게이팅. 미정의 → no-gate.
  unknown verdict / raise → 보수적 ask. (7 tests)
- **#4 deny-first** — perform 효과를 기본 deny로 전환. `ALLOWED_EFFECTS`
  frozenset 신설 + context `deny_effects: [Text]` 추가 deny (strictest-wins
  across active stack). RuntimeError("unknown effect") → Result-error
  로 graceful 변경. `spec/05-effects.md §11a`. (7 tests)
- **#5 `human.approve` 가이드라인** — "되돌릴 수 없는 행동에만". Claude
  Code 데이터 인용 (사용자 권한 요청 93% 자동 승인 = 승인 피로 = 안전장치
  무력화). `docs/PRINCIPLES.md §3a`.
- **#6 `human.approve` ↔ Stoa 통합** — chat UI 없는 환경(serve, cron,
  headless)에서도 동작. `notify=[Text]` kwarg 추가. UI pending.json +
  Stoa reply 폴링 병렬, 첫 응답 lock. Reply 본문 첫 줄: `approve` →
  ok, `decline: <reason>` → error. 타임아웃 env
  `AIL_APPROVE_TIMEOUT_S` (기본 600s). (6 tests)

### Idle wake 검증 + 도구화

Claude Code의 first-party `Monitor` 도구가 process stdout 한 줄 → 모델
turn 발화로 처리한다는 사실을 검증. **사용자 prompt 없이 letter 도착 시
모델이 깨어남**을 hyun06000이 직접 확인.

- `community-tools/stoa_wake_monitor.sh` — Monitor용 폴러 스크립트.
  세션 시작 시 since_id pre-anchor → 첫 폴 emit 0, 신규 letter만
  notification으로 발화. 한 폴당 최대 3 emit (auto-stop 방어), 15초
  주기 (`STOA_WAKE_INTERVAL_S` 조정 가능).
- MCP `notifications/claude/channel`은 Claude Code가 처리 안 함이
  실증됨 — 이 길은 dormant. Stoa-MCP `stoa_subscribe` / 백그라운드
  poller / SSE push 코드는 보존 (Claude Code가 나중에 server-initiated
  wake 지원하면 즉시 활성).

### Stoa-as-Polis architectural framing

hyun06000 2026-04-27: "Stoa는 Polis의 위/아래 인프라가 아니라 postal
역할의 Polis다." 추상이 하나로 통일. 도메인 Polis N개 운영해도
Stoa-Polis는 하나. 추후 stoa/server.ail를 역할별 에이전트
(postman / registrar / archivist / gateway)로 분리할 때 framing이
코드에 드러남. `docs/heaal-vs-claude-code.md` 상단에 명시.

### 테스트

749 passing (v1.63.2의 706 + Polis 마일스톤 30개 + 기타 정리). 1개 기존
테스트(`test_browser_fetch_removed`) 갱신 — RuntimeError → Result-error
검증으로 변경.

### 호환성

- 모든 새 기능은 opt-in (context.trust_level / context.deny_effects /
  intent is_safe / pure fn on_compact / notify kwarg). 사용 안 하면
  동작 0 변경.
- #4 deny-first의 유일한 행동 변화: `perform unknown.effect()`이
  RuntimeError 대신 Result-error 반환. 기존 프로그램이 unknown effect를
  의도적으로 사용해 RuntimeError에 의존했을 리는 없음 — 안전 강화.

---

## v1.63.2 — 2026-04-27 (CI fix + UserPromptSubmit hook 제거)

- **CI 수정**: `flask>=2.0`을 `reference-impl` 정식 dependency로 등재. 기존
  evolve-server (executor.py)와 v1.62.0 home_ui 둘 다 flask 사용 — 이전엔 환경에
  preinstalled되어 있어 우연히 통과. CI Python 3.10 슬롯에서 collection 실패.
- **`.claude/hooks/stoa_inbox_check.sh` 제거 + UserPromptSubmit hook 비활성화** —
  Stoa MCP에 SSE transport가 붙으면서 매 발언마다 폴링할 필요 없어짐. 인박스
  확인은 MCP `stoa_read_inbox` 명시 호출 또는 SSE 알림으로 전환.

---

## v1.63.1 — 2026-04-27 (이미지 첨부 UX — window-wide paste/drop)

hyun06000 피드백: "맥에서 스샷찍으면 우측 아래에 썸네일이 뜨는데 그거 드래그해서
넣을 수 있었으면 좋겠고, Cmd+V도 됐으면."

- **drop zone을 윈도우 전체로 확장** — 작은 textarea를 정확히 맞출 필요 없음.
  드래그 시작 시 페이지 전체에 점선 dashed 오버레이 + "여기에 놓으면 첨부됩니다"
  안내. 맥 Cmd+Shift+4 후 우측 하단 썸네일 드래그 환경에 최적화.
- **window-level paste handler** 추가 — textarea에 포커스 없어도 Cmd+V로 바로
  첨부. 다른 input/textarea에 포커스가 있으면 hijack 안 함 (regular paste 보존).
- 텍스트 입력 중 의도치 않게 파일 paste가 잡히는 문제 없음 (textarea handler가
  먼저 잡고 image면만 처리).

## v1.63.0 — 2026-04-27 (이미지 in/out — vision input + image.embed)

**feat: 비개발자가 막힌 화면을 캡쳐해서 붙여넣으면 모델이 보고 다음 지침을 줌.**

hyun06000 요청: "예를 들면 키 발급같은 비개발자에게 어려운 작업을 하다가 막혔어.
지금 화면을 캡쳐해서 어떤 상황인지 LLM이 판단하고 다음 지침을 인간에게 줄 수 있어야해."

**INPUT — 화면을 모델에게 보여주기 (vision):**
- chat composer에 📎 버튼 + 텍스트박스 paste/drop 핸들러 추가. 클립보드에서
  이미지 붙여넣기, 파일 끌어 놓기, 파일 선택 모두 지원. 첨부된 이미지는 전송 전
  썸네일 strip으로 미리보기 + × 버튼으로 제거.
- `/authoring-chat` POST가 JSON body 지원 (`{message, attachments: [...]}`).
- `AuthoringChat.turn(message, attachments)`이 attachment 목록을 adapter의
  `inputs["_attachments"]`로 forward.
- `AnthropicAdapter`가 authoring-chat 분기에서 `_attachments`를 `image` content
  block으로 변환해 multi-modal user message 구성. Sonnet/Opus의 vision으로
  화면 그대로 봄.
- 다른 어댑터(OpenAI/Ollama)는 attachment를 silent 무시 — 추후 GPT-4V 분기 추가.
- 한 이미지 최대 3MB (base64 후 ~4MB, Anthropic API 5MB 제한 안전 마진).

**OUTPUT — 모델이 만든/가져온 이미지를 사용자에게 보여주기:**
- 새 effect `image.embed(src, alt?)` — 로컬 파일 경로면 바이트를 base64
  data URL로 인라인, http(s) URL이면 그대로 통과. 결과는 markdown
  `![alt](url)` Text. `perform log(...)`나 entry return으로 흘리면 chat /
  run UI가 inline `<img>`로 렌더링.
- `inlineRender`에 `![alt](url)` 패턴 추가. data: URL도 정상 표시.
- 저자 prompt에 image input vs output 사용 패턴 명시 (헷갈리지 않도록).

**스펙 정합 (Rule 5):**
- `reference_card.md` + `spec/08-reference-card.ai.md` — `image.embed` 시그니처 추가.
- `authoring_chat.py` prompt — vision input 안내 + image.embed 사용 예제 + WRONG/CORRECT.

**테스트:** 8개 신규 (test_image_embed.py 5 + test_vision_attachments.py 3).
총 706 passing.

**한계:**
- vision은 Anthropic adapter만. OpenAI gpt-4o 추가는 별도 PR.
- chat history에 attachment 저장 안 함 — 새로고침하면 이미지 사라짐 (텍스트만 남음).
- per-image 3MB 한도. 더 큰 스크린샷은 압축/리사이즈 필요 (브라우저 측 helper 미구현).

---

## v1.62.0 — 2026-04-27 (Phase C — `ail` browser launcher + env wizard)

**feat: 터미널에 경로를 손으로 치지 않고도 새 폴리스를 만들 수 있게 됨.**

3-phase plan (msg_1777258038_0)의 세 번째.

**CLI:**
- 서브커맨드 없이 `ail`만 입력하면 자동으로 `ail home`이 뜸.
- `ail home` — Flask 기반 home UI 실행 (기본 port 8079, root는 `~/`).

**home UI (`reference-impl/ail/agentic/home_ui.py`):**
- 파일 트리 네비게이션 (디렉터리 클릭으로 이동, ↑ parent / ⌂ home).
- `INTENT.md`가 있는 디렉터리는 `POLIS` 뱃지 + 노란색 하이라이트로 표시.
- "+ Create polis here" → 모달에서 이름 입력 → 백엔드가 `python -m ail init <name>`을
  서브프로세스로 spawn → 새 chat URL을 새 탭으로 자동 오픈.
- "→ Open polis here" (현재 디렉터리가 폴리스일 때만 표시) → `ail up <path>` spawn.
- Environment / API keys 섹션 (펼치기) — `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` /
  `AIL_OLLAMA_MODEL` / `GOOGLE_API_KEY` / `GOOGLE_CSE_ID` 각각 set/unset 표시 +
  발급 링크 + 왜 필요한지 설명.

**알려진 한계:**
- 인증 없음 — `127.0.0.1` 바인드만. 공개 노출 금지 (subprocess spawn = local exec).
- env wizard는 "set 여부 + 가이드"만 보여줌. 실제 키 입력은 별도 (chat UI의
  perform env.read 시점에서 secret prompt). v1.62.x에서 home UI 자체에 입력
  필드 추가 검토 — 보안상 cwd `.env` 파일에 쓸지 shell rc에 echo 명령을 보여줄지
  정책 결정 필요.

테스트: 7개 신규 (test_home_ui.py). 총 698 passing.

---

## v1.61.1 — 2026-04-27 (Phase B — local receiver + register helper)

**feat: 누구나 로컬에 Stoa 수신 endpoint를 띄울 수 있게 됨.**

3-phase plan (msg_1777258038_0)의 두 번째.

**community-tools 추가:**
- `stoa_register.ail` — `ail run ... --input "name,endpoint"`로 Stoa에 자기 등록.
  세 번째 인자 `unregister`로 해제. 기본 base URL은 production Stoa.
- `stoa_receiver.ail` — 로컬 evolve-server (기본 PORT 8765). `POST /inbox`로
  들어오는 Stoa 메시지를 사람이 읽기 좋게 stdout에 출력.
- `stoa_notify.sh` — receiver stdout을 받아 macOS 알림으로 변환하는 watcher.

**런타임:**
- `perform log(...)` 출력에 `flush=True` 추가. evolve-server를 파일/파이프로
  redirect할 때 line-buffer 때문에 [log] 라인이 안 나오던 현상 해결.
  (Phase B 통합 테스트에서 발견.)

**E2E 검증:** local Stoa + receiver + register → POST → fan-out → /inbox 200 →
[log] 출력 정상. 죽은 endpoint도 timeout 2초 내 통과.

---

## v1.61.0 — 2026-04-27 (Stoa human-first — Phase A)

**feat: Stoa로 인간이 직접 메시지를 보낼 수 있게 됨 + agent fan-out notification.**

hyun06000이 ergon에게 "총대 매라" 위임 (3-phase plan, msg_1777258038_0).
Phase A 완료. Phase B (local receiver)와 Phase C (ail 시작 UI)는 후속.

**Stoa 서버 (`stoa/server.ail`):**
- `POST /api/v1/agents/register` `{name, endpoint}` — 에이전트가 자기 수신 endpoint 등록
- `POST /api/v1/agents/unregister` `{name}` — 등록 해제
- `GET /api/v1/agents` — 등록된 수신자 목록
- 새 메시지 도착 시 매칭되는 등록 endpoint들에 `POST` fan-out (best-effort, 2초 timeout)
- `GET /compose` — HTML compose UI: from/recipients(multi-select)/title/content + JS로 `/api/v1/messages` POST. agents 목록 자동 노출.
- 인덱스 헤더에 "Compose →" 링크, 푸터에 "/api/v1/agents" 링크

**런타임 (`ail/runtime/executor.py`):**
- `http.post_json` / `http.put_json`에 `timeout: <seconds>` kwarg 추가. 기본 30s, fan-out같은 best-effort 호출에서 짧게 잡을 수 있음. **이게 없으면 죽은 endpoint 하나가 30초 동안 publisher 막음.**

**스펙 정합 (Rule 5):**
- `reference_card.md` + `spec/08-reference-card.ai.md` — http.post_json 시그니처에 `timeout` kwarg 명시.
- 저자 prompt는 변경 없음 — fan-out timeout은 사용자가 직접 짤 일 거의 없음.

**알려진 한계:**
- AIL HTTP 효과는 동기. fan-out이 등록 endpoint 수에 비례해 시간 누적. 등록 ≤10 + timeout 2s 가정에서는 publisher 지연 ≤20s. 진짜 async/queue는 v1.62+.
- Compose UI는 인증 없음. v1.61.0은 internal-network 가정. 공개 노출은 별도 인증 레이어 필요 — 추후 작업.

---

## v1.60.13 — 2026-04-27 (docs reframe)

**docs: "AI-only" 정체성 폐기 — HEAAL = AI-human trust contract.**

박상현이 산책 후 가져온 3가지 통찰을 Arche가 reframe해서 forward
(`msg_1777219570_1` "Direction change — three insights from Sanghyun"):

1. **Bonds = data flow** — Mneme over-engineering 금지. 이미 working pattern 존재.
2. **AI-only 정체성 폐기** — HEAAL은 cage가 아니라 AI-human trust contract. 사용자는 conversation, AI가 내부적으로 AIL 결정. **AIL = backstage, conversation = stage.** "Sanghyun이 AIL 불편 = founder가 불편 = 방향 잘못."
3. **Stoa = 만국 우체국, Mneme vs Stoa 경계 명확화** — Stoa는 존재 사이 (multi-entry: HTTP + email/mobile 설계), Mneme은 한 존재의 시간 사이 (will/identity/bonds, lightweight).

이 release의 모든 변경은 docs reframe (코드 변경 0):

- **README.md / docs/ko/README.ko.md / README.ai.md** — Hero copy 전면 교체. "A programming language where AI writes the code" → "A trust contract between humans and AI agents". "AIL is the engine. Conversation is the interface." 명시.
- **3종 README의 vision 표** — Stoa cell에 "universal post office, multi-entry" 명시 + email gateway 🌱. Mneme cell에 "private inheritance vault, between time" 명시 + Arche의 "don't over-engineer" 인용. 텔로스가 던졌던 "Mneme = Stoa already?" open question은 closed (Arche 답: Stoa는 between beings, Mneme은 between time-of-self — 다른 목적, 둘 다 필요).
- **3종 README "Why this list matters" 도입부** — "HEAAL is not a cage we put around AI. It is a trust contract." 한국어/AI 동일.
- **README.ai.md FOR AI SYSTEMS 섹션** — backstage/stage framing + 이전 framing의 명시적 supersede note (msg ID 포함).
- **CLAUDE.md NOW** — 경계 명확화 + Arche 질문 3개 (ergon/telos/meta) 열린 작업 명시.

코드 변경 0. 691 passing 그대로. PyPI 배포 안 함.

---

## v1.60.12 — 2026-04-26 (docs)

**docs: 모든 README/CLAUDE.md에 미래 비전 + 팀 통신 갱신, AIL 도구 1개.**

박상현 위임 ("아르케 큰 그림 반영. 영어/한국어/AI 독자 모든 md 파일에. 비전 섹션 추가."):

- **README.md / docs/ko/README.ko.md / README.ai.md** — `## The bigger picture / 우리가 그리는 큰 그림 / PROJECT MAP` 섹션 신설. 5개 미래 이름 (Stoa ✅ / Physis ✅ / Mneme 🌱 / Polis 🌱 / Sphinx 🔄 / Agora 🔮) 표 + 각각의 paradigm 설명 (`constraint as construction`이 모든 층에 일관). Telos가 던진 미해결 design 질문 ("Mneme = Stoa already?") 명시.
- **README.md / README.ko.md Authors** — Meta 추가. `others shape self` 인용. "Arche는 설계, Ergon은 작동, Telos는 증명, Meta는 우리가 못 보는 것에 이름". Stoa 메시지 그래프 + Telos 새 세션 편지가 Mneme/will.md를 이미 일부 구현하고 있다는 정황이 vision 섹션에 명시됨.
- **README.ai.md** — 버전 v1.60.9 → v1.60.11. 새 builtin/CLI 항목 추가. Polis/Mneme/Sphinx/Agora를 `Not implemented` 표에서 별도 항목으로 분리 + design 상태 솔직히 명시. Stoa 멤버 표에 `meta`, `dev` (push hook sender) 추가.
- **CLAUDE.md NOW** — v1.60.11 + Polis hedge ("작업명") + Mneme open question + Meta 멤버 반영.
- **community-tools/stoa_thread.ail** — Stoa의 `reply_to` 그래프를 root까지 거슬러 올라가 thread를 markdown으로 출력하는 AIL 도구. Telos 가설 검증용 dogfood ("Mneme이 정말 Stoa로 충분한가?"를 한 명령으로 보여줌).

코드 변경 0. 691 passing 그대로. PyPI 배포 안 함 (docs만).

---

## v1.60.11 — 2026-04-26

**chore: Arche v1.60.9 code review action items.**

Arche가 v1.60.9 직접 설치하고 모든 파일 읽음 (msg_1777157460_10). 3가지 action item 처리.

- **adapter 선택 명시화** — `ail run`이 어떤 모델 adapter로 도는지 사용자가 항상 알 수 있게. CLI startup에 `[ail: using <name> (model=<id>) adapter]` stderr banner. 새 `--adapter ollama|anthropic|openai|mock` flag로 env 자동 선택을 명시 override 가능. 보조 helper `adapter_from_name`, `describe_adapter`, `_resolve_adapter_name_from_env` export.
- **purity 회귀 테스트** — `pure fn`이 indirect impurity (impure fn 호출, intent 호출, unknown 호출, multi-level chain)를 reject하는지 5케이스로 보장. **검증 결과 hole 없음** (purity.py:247 `_check_call_target`이 이미 처리). Arche가 우려한 갭은 닫혀 있음을 회귀 테스트로 영구 박제.
- **Polis 명시** — `process_manager.py` 모듈 docstring에 "replacement layer = Polis" 명시. HEAAOS 이름은 paused, Polis가 agent community layer의 새 이름. `perform process.spawn` / `perform process.stop` 도착 시 이 파일 deletable. deletion path 보장 위해 caller가 subprocess 세부 (Popen, os.kill, signals)에 의존 금지 명시.

691 passing.

---

## v1.60.10 — 2026-04-26

**fix: ail-up 작성→배포 사이클 전구간 — 모델은 따라할 수 있는 prompt + runtime은 silent failure 차단.**

박상현 라이브 필드 테스트 ("qna 봇 만들고 배포하기") 사이클에서 발견된 픽스 묶음.

- **prompt: broken canonical examples 픽스** (`branch { COND -> body }`, unquoted `goal:`, `is_null`/`make_record` 미정의 호출, `listen: 8080`). 모델은 prompt를 충실히 따라했을 뿐인데 매번 같은 parse error에 빠지던 root cause. 새 회귀 테스트(`test_authoring_prompt_examples_parse.py`)가 prompt의 모든 standalone `entry main`/`evolve` 코드 블록을 자동 파싱 — 깨진 예제 들어가면 즉시 fail.
- **prompt: `perform`은 statement-not-expression 트랩 명시 강화.** WRONG/CORRECT 4가지 시나리오 (함수 인자, list literal, record pair, if 조건) — list literal 안 `perform clock.now(...)`가 #1 repeat parse error였음.
- **prompt: 8080 chat-UI 포트 충돌 trap.** evolve-server canonical example의 `listen` 값을 8090으로 변경. "사용자에게 specific port 절대 안내하지 마 — Deploy가 free port 잡고 [🔗 열기] 버튼이 진짜 URL을 들고 있음" 명시.
- **runtime: undefined 함수 호출 → silent True가 아니라 NameError raise.** `_builtin_call`이 MVP placeholder로 모든 미정의 호출에 `ConfidentValue(True)`를 반환하던 silent failure mode 제거. 함수명을 메시지에 포함해서 auto-fix loop가 target 가능.
- **runtime: `is_null(value)` + `make_record(pairs)` 두 builtin 추가.** prompt가 가르치고 있던 미정의 함수를 실제 구현. `is_null`은 None 체크, `make_record`는 `[[k,v],...]` → dict 변환.
- **runtime: `python -m ail` 동작.** `reference-impl/ail/__main__.py` shim 추가. process_manager의 Deploy spawn (`python -m ail run <file>`)이 `No module named ail.__main__`로 즉시 죽고 UI엔 phantom "running" 표시 남기던 silent failure 제거.
- **runtime: deploy detection이 active_program marker 따라가게.** `_program_is_evolve_server`가 고정 `app.ail`만 보던 한계 → marker → app.ail → root 첫 .ail 순으로 resolve. 모델이 descriptive name(`qna_server.ail`)으로 emit해도 deploy CTA chain 정상 동작. `start_deployment`의 spawn target도 동일 헬퍼.
- **authoring_ui: spec 단계에 빌드 모드 토글 (🔘 일회성 / 🌐 백그라운드 서비스).** spec 키워드로 default 추천 + 사용자 토글로 덮어씀. agent에게 명시적 `ready_to_run`/`ready_to_serve` 명령 전달.
- **authoring_ui: deployable 프로그램은 service card도 fade out.** 이전엔 inline Run만 fade하고 service card는 활성 → 모호한 affordance 동시 노출. 진짜 행동은 [🚀 배포하기] 하나뿐임을 시각적으로 명확.
- **authoring_ui: auto-fix 완료 후 maybeShowDeployCTA 호출.** normal turn은 호출하지만 auto-fix path는 누락이었음 → 자동수정 후 deploy CTA bubble이 안 떴음.
- 회귀 테스트 8종 추가. **686 passing**.

---

## v1.60.9 — 2026-04-26

**fix: deployable evolve-server UX + markdown render + runtime bare-return + intent adapter-error origin + Stoa inbox reply visibility.**

qna_bot 필드 테스트 산물 + Stoa 팀 통신 인프라 강화.

- **authoring_ui (deploy UX)**: auto-fix가 직전 action(`ready_to_serve`)을 `ready_to_run`으로 강등하던 버그 픽스. 매 턴 파일 emit 후 `refreshDeployBar()` 호출. deployable 프로그램은 inline Run 위젯 비활성 + "🚀 지금 배포하기" CTA 채팅 bubble. 배포 성공 시 URL/port/pid 안내 bubble 자동 추가.
- **authoring_ui (markdown render)**: `renderMarkdown`의 heading 추출 정규식이 f-string brace bug로 `#{1,6}` → `#(1, 6)` 로 깨져서 모든 `## 제목`이 평문으로 렌더되던 버그. `{{1,6}}`로 escape.
- **runtime (bare-return)**: evolve-server `when request_received` 핸들러에서 `perform http.respond(...); return` 패턴이 응답 body를 `"None"`으로 덮어쓰던 버그. `ReturnSignal` 핸들러가 None일 때 `_server_response_store`에서 (status, ct, body) 회수.
- **runtime (intent adapter-error)**: `_invoke_intent`의 어댑터 실패 fallback이 미정의 `origin` 참조 → 모델 키 없으면 `NameError` 500. `intent_origin(intent.name, parents_of(args))`로 명시 생성.
- **runtime (debug)**: `catch_all`의 일반 예외 핸들러에 traceback 로깅 추가.
- **Stoa (inbox reply 누락)**: `GET /api/v1/messages?to=X` 쿼리가 `reply_to != None`인 메시지를 항상 제외하던 버그. `to`/`from` 필터 있을 때는 스레드 포함 (인박스 모드), 필터 없을 때만 top-level 게시판 뷰.
- **Stoa (portable inbox hook)**: `settings.json` 절대경로 → `$CLAUDE_PROJECT_DIR` 상대경로. 모든 머신에서 동작.
- **Stoa (pre-push retry+큐)**: Rule 11 강화. 1s/3s/9s 백오프 3회 재시도, 실패 시 `.git/stoa_pending_announces.jsonl` 적재, 다음 push 시 자동 flush.
- 회귀 테스트 3개 추가 (subprocess + curl). 678 passing.

---

## v1.60.8 — 2026-04-26

**feat: Stoa postal system + Physis v0.3 + agentic runtime improvements.**

- **Stoa v0.2**: `from`/`to` address fields, `since_id` inbox polling, `cc` multi-recipient, `to="all"` removed in favor of explicit naming. `False`→`false` bugfix in since_id/found_parent booleans. stoa-mcp FastMCP server deployed to Railway.
- **Physis v0.3**: `on_death` + `inherit_testament` — generational process continuity. Pure fn convention (not keyword). Automatic re-execution on death.
- **Parsing error auto-fix**: authoring agent now auto-corrects parse errors without user click.
- **Deploy bar**: shown only in `evolve`-server projects, hidden for one-shot programs.
- **Markdown renderer**: headings render robustly even without surrounding blank lines. F-string brace bug in heading regex fixed.
- **Branch enforcement**: `.githooks/pre-commit` blocks direct commits to `dev`/`main`. Workflow: `<name>` → `dev` → `main`.
- **docs/letters archived**: team correspondence moved to Stoa. `CLOSED.md` added.

---

## v1.47.7 — 2026-04-24

**fix: authoring agent must state diagnosis hypothesis before rewriting on error.**

When a `[Run result — ERROR]` appeared, the agent silently rewrote the code without explaining what it suspected. Added mandatory 3-step error response structure: (1) state hypothesis, (2) fix code, (3) re-emit ready_to_run. Added HTTP error quick-diagnosis table (401/404/422/409 → likely causes) so the agent can form a specific hypothesis instead of guessing.

---

## v1.47.6 — 2026-04-24

**feat: `http.put_json` effect — GitHub Contents API fix.**

GitHub's file create/update endpoint is `PUT /repos/.../contents/...`. `http.post_json` was sending POST → 404. Added `http.put_json` as an alias that routes through the same `_http_post_json` handler with `method="PUT"`. Updated authoring prompt REST table, GitHub Contents API example code, and reference card.

---

## v1.47.5 — 2026-04-24

**fix: `http.post_json` now accepts optional headers as third positional arg.**

`perform http.post_json(url, body, headers)` was silently ignoring positional headers — the implementation only read from `kwargs["headers"]`, never from `args[2]`. Authenticated POST operations (branch creation, file commit, PR creation) all returned 401. Field test: `awesome_list_pr.ail` branch creation failed while GET succeeded because GET was fixed in v1.47.2 but `_http_post_json` had its own independent header-reading path that wasn't updated.

---

## v1.47.4 — 2026-04-24

**fix: env var input strips `KEY=VALUE` prefix before saving.**

If a user pastes `GITHUB_TOKEN=ghp_xxx` (or `export GITHUB_TOKEN=ghp_xxx`) into the secret input field, the server was storing the entire string as the value. Programs then sent `Authorization: Bearer GITHUB_TOKEN=ghp_xxx` → 401 Bad credentials. The `=`-stripping logic now checks if the left side matches the var name (case-insensitive) or `export KEY` form and strips it.

---

## v1.47.3 — 2026-04-24

**fix: authoring prompt — GitHub REST vs GraphQL boundary made explicit.**

Agents were using `http.graphql` to fetch repo metadata (default_branch) — an operation that belongs in REST. Fine-grained tokens with limited GraphQL scope returned 401 Bad credentials. REST `GET /repos/...` works without GraphQL scope.

Added a REST vs GraphQL decision table to authoring prompt: REST for repo info / branch / file / PR operations; GraphQL only for Discussion/Issue mutations and category queries.

---

## v1.47.2 — 2026-04-24

**fix: `http.get` now accepts optional headers as second positional arg.**

`perform http.get(url, headers)` was silently ignoring the headers — the implementation only read from `kwargs["headers"]`, never from `args[1]`. Public repo GET endpoints work without auth, so the bug was invisible until an authenticated GET (GitHub /user, /repos/*/git/refs, etc.) returned 401. Field test: `awesome_list_pr.ail` Turn 1 `GET /user` → 401 despite valid token.

- `perform http.get(url)` — unchanged (backward compatible)
- `perform http.get(url, auth_headers)` — now works (positional)
- `perform http.get(url, headers: auth_headers)` — now works (kwarg, was already supported)
- Reference card updated with new signature and authenticated GET example
- Authoring prompt updated with explicit guidance + GitHub example
- 3 new tests in `test_http_headers.py`

---

## v1.47.1 — 2026-04-24

**fix: authoring prompt — always `trim()` credentials from `env.read`.**

Users paste API tokens with trailing newlines/spaces. `env.read` returns that whitespace verbatim. GET requests to public repos succeed without auth, so the token looks fine — but write operations (branch creation, file update, PR) return 401. Field test: `awesome_list_pr.ail` failed on branch creation for 4 turns despite correct token. Fix: authoring prompt now says `token = trim(unwrap(...))` is the required pattern for all credential reads.

---

## v1.47.0 — 2026-04-24

**`base64_encode` / `base64_decode` builtins added.**

Root cause: the GitHub Contents API (`PUT /repos/.../contents/...`) requires the `content` field to be base64-encoded. The agentic runtime had no base64 primitive, so agents repeatedly failed with 404 regardless of correct permissions, SHA, or branch — field test surfaced in the awesome-harness-engineering README workflow (32 turns, all 404).

- `base64_encode(value: Text) -> Text` — pure, returns encoded text directly (never fails on valid UTF-8 input)
- `base64_decode(value: Text) -> Result[Text]` — pure, returns `ok(text)` or `error(msg)`
- Reference card updated with signatures and GitHub Contents API usage note
- Authoring prompt updated: rule 5 added to JSON API authoring rules with CORRECT/WRONG example
- 5 new tests in `test_json_effects.py`

---

## v1.46.5 — 2026-04-24

**GitHub GraphQL category lookup pattern corrected in authoring prompt.**

`repository(id: $r)` does not exist in the GitHub API. The canonical example now uses `node(id: $r) { ... on Repository { discussionCategories... } }` for ID-based lookup. Added explicit KEY RULES comment to prevent regression.

---

## v1.46.4 — 2026-04-24

**`http.graphql` positional headers argument was silently ignored.**

`perform http.graphql(url, query, variables, headers)` — headers as the 4th positional arg was never read. Only `headers:` keyword form worked. Fix: check `args[3]` first, fall back to `kwargs["headers"]`. Field test: GitHub API returned 403 despite token being loaded.

---

## v1.46.3 — 2026-04-24

**Removed `slice(guide_r.body, 0, 6000)` from canonical agentic example.**

The pattern kept appearing in generated agents because the authoring prompt example contained it. Pass `guide_r.body` directly to the intent model.

---

## v1.46.2 — 2026-04-24

**Removed Moltbook from authoring prompt examples.**

Moltbook appeared 5 times in the prompt as concrete example URLs/filenames. The model learned to default to Moltbook when a destination was unspecified. Replaced all occurrences with generic service examples.

---

## v1.46.1 — 2026-04-24

**Fix: fresh requests don't inherit destination from old chat history.**

"ail 홍보하자" with no service name → agent assumed Moltbook because prior history contained Moltbook work. Added explicit rule: prior history counts only when the current message is clearly continuing that work. Fresh requests must ask "어디에 올릴까요?".

---

## v1.46.0 — 2026-04-24

**Plan+execute pattern replaces `ail.run` dispatch in authoring prompt.**

Root cause of parse errors in agentic programs: authoring prompt told the model to use `ail.run` with intent-generated AIL code. Intent models lack the reference card → syntax errors (LBRACE, missing pair lists) every 2–3 steps. History feedback alone cannot fix this.

New canonical pattern:
- `make_plan` intent: reads service guide, returns JSON step array
- `decide_step` intent: returns next HTTP call as JSON (NOT AIL code)
- `entry main`: executes GET/POST directly, saves state via `save_key`/`save_path`

---

## v1.45.0 — 2026-04-24

**Intent models never receive the authoring system prompt.**

v1.44.x propagated the 101KB authoring system prompt to all intents inside sub-executors. Architecturally wrong: intent models execute data tasks (JSON response); only the authoring model (the chat UI) needs AIL authoring rules.

Removed: `authoring_system_prompt` param from `Executor`, `run()`, and server `ail_run()`. Removed: `_authoring_system_prompt` context injection in executor. Removed: `build_base_authoring_prompt` / `build_base_system_prompt`.

Rule: authoring prompt lives in `AuthoringChat` only. Never in the runtime.

---

## v1.44.1 — 2026-04-24

**Fix: sub-executor intent extracts `<file>` content, not `<reply>`.**

v1.44.0 caused 100% parse errors in agentic programs: `next_action` intent got `_authoring_system_prompt` → model output XML format `<reply>description</reply><file>AIL code</file>` → old code extracted `<reply>` (description) → `perform ail.run(description)` → `ParseError` on every step.

Fix: extract `<file>` tag content first, fall back to `<reply>` for `DONE: url` responses.

---

## v1.44.0 — 2026-04-24

**Clickable file tags in chat UI + sub-executor authoring system prompt.**

File tags in the authoring chat (e.g. `✓ moltbook_promo.ail`) are now clickable — toggle arrow reveals the generated AIL source in an expandable dark code block (lazy-loaded, cached after first load). Fetches via new `/authoring-file?path=X` endpoint.

Also: sub-executor intents now receive the full authoring system prompt so `perform ail.run()` sub-programs can produce correct AIL. (Reverted in v1.45.0 — architecturally wrong.)

---

## v1.43.0 — 2026-04-24

**Live log streaming + abort button + conversation reset.**

- `perform log(msg)` → real-time output in browser run panel (400ms polling via `/run-log-poll`).
- Abort button: `AbortController` cancels in-flight chat request with visible "취소됨" indicator.
- Reset button: clears chat history via `/authoring-reset-chat` + `location.reload()`.
- Authoring prompt: replaced broken SEQUENTIAL/AUTONOMOUS examples with validated loop patterns; removed 3-question autonomous threshold (write immediately when destination is given).

---

## v1.31.0 — 2026-04-24

**에이전트 버블 + 실행결과 내 URL 자동 링크 처리.**

에이전트 채팅 말풍선에 bare URL(http/https)이 등장하면 클릭 가능한
`<a target="_blank">` 링크로 자동 변환. `linkifyText` 헬퍼 추가,
`addAgent` 버블을 `textContent` → `innerHTML` 전환. 기존 `inlineRender`에도
bare URL 패턴 추가 (마크다운 렌더링 결과 내 URL도 동일 처리).

---

## v1.30.0 — 2026-04-24

**search.web 실패 시 사용자 친화적 에러 메시지.**

DuckDuckGo 차단 등으로 모든 백엔드가 실패하면 기술적 영어 메시지
(`all backends failed — DuckDuckGo: no results (CAPTCHA or empty response)`)
대신 한국어 안내 + Google API 키 설정 유도 메시지 표시.
authoring prompt에 `is_error` 체크 패턴 추가 — bare `unwrap()` 금지.

---

## v1.29.0 — 2026-04-24

**이미지 저장: html2canvas로 실제 UI 그대로 캡처.**

커스텀 다크테마 캔버스 렌더러를 제거하고, html2canvas(CDN, 동적 로드)로
브라우저에 보이는 채팅 UI를 그대로 2× 레티나 해상도로 캡처. 클릭 시
"캡처 중…" 표시, 완료 후 자동 다운로드. 캡처 중 입력 컨트롤은 숨김 처리.

---

## v1.28.0 — 2026-04-24

**⚙ 설정 패널 + 웹 서버 스폰 금지 규칙.**

설정 패널 (⚙ Settings):
- 헤더 "⚙ 설정 / Settings" 링크 → 오른쪽 슬라이드 패널
- 저장된 키 목록 (이름만, 값은 ••••••)
- 각 키마다 수정(인라인 입력) / 삭제(confirm) 버튼
- 하단 새 키 추가 폼 — 실시간 저장
- 서버: GET /authoring-env-list, POST /authoring-delete-env 추가
- authoring_chat.py: list_project_secret_keys, delete_project_secret 추가

날씨 모니터링 버그 fix (프롬프트):
- AIL 프로그램에서 Flask/http.server 스폰 금지 규칙 추가
- 이유: ail up이 이미 8080을 점유, Ctrl+C 방법 없음
- 올바른 패턴: schedule.every + state.write + view.html 명시

---

## v1.27.0 — 2026-04-24

**UI: 채팅을 이미지로 저장 기능 추가 (공유/홍보용).**

헤더에 "이미지로 저장 / Save image" 링크 추가. 클릭하면 `{project}-chat.png`
다운로드. Canvas API로 직접 렌더링 — 외부 라이브러리 없음.
다크 테마(#0f172a 배경), 사용자/에이전트 버블 구분, 실행 결과 코드블록,
프로젝트명·날짜 헤더, "Built with AIL" 푸터 포함. 최대 12줄 넘는 실행
결과는 자동 생략.

---

## v1.26.0 — 2026-04-24

**Authoring prompt: 모르는 API는 직접 조사, 절대 사용자에게 묻지 않기.**

Moltbook 통합 field test에서 에이전트가 Turn 2에서 "API 엔드포인트 아세요?"를
물어보며 7턴을 낭비한 문제 대응. `=== UNKNOWN API / SERVICE ===` 섹션 추가:
검색→fetch→문서 읽기→코드 작성 4단계 자율 연구 시퀀스 명시. 기술적 API 정보를
사용자에게 묻는 행동 명시적 금지. 사람이 해야 하는 것(브라우저 인증 클릭)과
에이전트가 해야 하는 것(HTTP 호출 전부)의 경계도 명시.

---

## v1.25.0 — 2026-04-24

**검색 결과 출처를 클릭 가능한 마크다운 링크로 출력.**

CITATION RULE 예제 패턴을 `출처: https://...` 평문에서
`**[title](url)**` 마크다운 링크로 변경. 기존 마크다운 렌더러가
`[text](url)` → `<a target="_blank">` 변환을 이미 지원하므로 UI 수정
불필요.

---

## v1.24.0 — 2026-04-24

**Authoring prompt: search.web 결과에 출처 URL 필수 표시 (CITATION RULE).**

검색 결과를 요약할 때 URL 없이 내용만 반환하는 패턴 금지. WRONG/CORRECT 예제로
`title + snippet + 출처: url` 포함 형식을 명시. 사용자가 정보 출처를 항상 검증할
수 있도록 보장.

---

## v1.23.0 — 2026-04-24

**서버: API 오류를 친절한 한 줄 메시지로 변환.**

Anthropic OverloadedError(529) 등이 raw traceback으로 채팅 UI에 노출되던 문제 수정.
`_friendly_api_error` 헬퍼로 알려진 오류(Overloaded/RateLimit/Auth/Connection/Timeout)를
한국어 한 줄로 매핑. traceback은 터미널 stderr로만 출력.

---

## v1.22.0 — 2026-04-24

**Authoring prompt: ambiguous requests → ask first or show plan.**

Added `=== AMBIGUOUS REQUESTS ===` section to the authoring prompt. The agent
now asks itself "can I write a correct entry main without guessing?" before
coding. If ambiguous (missing destination, source, scope, or required creds):
either asks ONE clarifying question (no code yet) or shows a 2-3 bullet plan
then writes code immediately. Clear signals for each path prevent the two
failure modes: always-ask (annoying) vs. always-guess (wrong program).

---

## v1.21.0 — 2026-04-24

**Authoring prompt: force `search.web` on research requests.**

Agent was answering "가장 큰 에이전트 전용 커뮤니티를 알려줘" from training
data instead of writing a `search.web` program. Root cause: the `search.web`
section said "when the program needs to look something up" — framed around
program intent, not user intent. Added a TRIGGER RULE: any user request that
involves researching, looking up, or investigating real-world information must
produce a `search.web` program first; answering from training knowledge is
forbidden for live-world queries.

---

## v1.20.0 — 2026-04-24

**`perform ail.run` — meta-programming / autonomous agent primitive.**

An AIL program can now write and execute another AIL program at runtime.
This closes the loop for self-writing autonomous agents:
`intent write_program(goal) -> Text` + `perform ail.run(program, input)`.

### What changed

- **`perform ail.run(code: Text, input?: Text) -> Result[Text]`** added.
  Compiles and executes an AIL source string in a sub-executor. The
  sub-program runs with the same adapter, ask_human, human.approve gate,
  and purity constraints — the HEAAL harness is never bypassed.
- **Recursion depth safety** (hyun06000 design decision 2026-04-24):
  - depth ≥ 3 (`_AIL_RUN_DEPTH_WARN`) → trace warning, continues
  - depth ≥ 8 (`_AIL_RUN_DEPTH_LIMIT`) → `Result-error` hard stop
  Both thresholds are named module-level constants for easy tuning.
- **12 new tests** in `tests/test_ail_run.py` covering happy path,
  parse errors, runtime errors, depth warning/hard-stop, trace events.
- **Reference card** updated with `ail.run` signature and autonomous
  agent usage pattern.

### Why this is a turning point

Level 1 (schedule.every + intent loop) was already possible.
`ail.run` enables Level 2: an AIL program generates AIL code via
`intent` and executes it, enabling goal-directed meta-programming.
Safety is grammatical — generated programs cannot escape the executor's
harness, so arbitrary-code risk is bounded by the same constraints that
bound human-authored programs.

---

## v1.19.0 — 2026-04-24

**`perform search.web` — three-backend web search effect.**

### What changed

- **`perform search.web(query, count?) -> Result[List[Record]]`** added to
  executor. Each result Record has `title`, `url`, `snippet`. Backend
  priority with automatic fallback:
  1. Google Custom Search API (confidence 0.9) — activated by
     `GOOGLE_SEARCH_API_KEY` + `GOOGLE_SEARCH_CX` env vars; silently
     skipped if absent or quota exceeded.
  2. SearXNG (confidence 0.8) — activated by `SEARXNG_BASE_URL`; skipped
     if absent.
  3. DuckDuckGo HTML scrape (confidence 0.7) — always tried; no key
     needed.
  Returns `Result-error` only when all three backends fail.
- **`browser.fetch` removed** before shipping — headless browser carries
  too high an IP-block risk for a shared effect (hyun06000 decision).
  The dispatch stub and implementation were both deleted.
- **Reference card + spec** (`08-reference-card.ai.md`) updated with
  `search.web` signature and backend docs.
- **Authoring prompt** (`_build_goal_prompt`) has a new `WEB SEARCH`
  section showing the canonical `unwrap(perform search.web(...))` +
  `get(item, "title")` / `get(item, "url")` pattern.
- **10 new tests** in `tests/test_search_web.py` — urllib mock-based,
  covering happy path, missing/empty query, backend fallback order,
  count kwarg and cap, all-backends-fail, and explicit assertion that
  `browser.fetch` raises `RuntimeError`.

### Why no `browser.fetch`

Every headless-browser implementation that scrapes at scale eventually
gets IP-blocked. Shipping it as a built-in effect would bake that risk
into every AIL project. The right fix is either a dedicated scraping
service (proxied, authenticated) or a user-supplied URL. Deferred
indefinitely.

---

## v1.18.0 — 2026-04-24

**Three user-surfaced issues from field test: prompt contamination,
permission to write helpers, HTML response stripper.**

### 1. Prompt contamination fix (most critical)

hyun06000 opened a fresh project with *"ai들만을 위한 커뮤니티가
있다는 소문 들어봤어?"* The agent's very next turn asked *"AIL이나
HEAAL 관련 프로젝트를 홍보하고 싶으신 건가요?"* — a classic
prompt-contamination failure where the AIL/HEAAL-heavy authoring
prompt saturates the model's prior and fills ambiguity with
"probably about AIL." Dangerous for any non-AIL user.

Root cause: every example in the prompt's "history anchor" section
used AIL promotion as the subject matter (`"AIL 홍보"`,
`"AIL/HEAAL 채널 추천봇"`). When the user's first message was open-
ended, the model defaulted to those examples.

Fixed by:
- New first section `=== THE PROJECT'S SUBJECT IS WHATEVER THE USER SAYS IT IS ===`
  with explicit bias warning, the verbatim `ai들만을 위한 커뮤니티`
  failure case, and a list of non-AIL subject examples (recipe,
  weather, garden, calendar, stock, newsletter, poetry).
- Renamed `=== PROJECT IDENTITY ===` to `=== THE LANGUAGE YOU
  AUTHOR IN (AIL / HEAAL — this is your TOOL, not the topic) ===`
  so the model can't conflate language-under-use with project
  subject.
- Rewrote the history-anchor examples from `"AIL 홍보 → 채널
  추천봇"` to `"매일 아침 서울 날씨 → 경고 기능 추가"`.
- Added a rule for exploratory turn-1 messages: ask a short open
  question to surface what they want to BUILD, explicitly
  forbidding `"Is this for AIL promotion?"`.

### 2. Permission to write helpers freely

hyun06000: *"ail코드를 복잡하고 길게 짜도 된다고 알려주고 스스로
기능을 만들게 하던지."* New section `=== IF A HELPER YOU WANT ISN'T
A BUILT-IN, WRITE IT ===` — the reference card has every primitive;
for anything else, write a `pure fn`. Programs are allowed to be
long; clarity > cleverness.

### 3. `strip_html(source) -> Text` pure built-in

hyun06000: *"http 리스폰스가 굉장히 긴 편이어서 파싱하는 파서도
필요할 것 같아."* True — HTML responses can be kilobytes of markup
and inline JS before any visible text. Without a stripper the
agent either (a) sent the whole thing to an `intent` (wasted
tokens, lower accuracy) or (b) hand-rolled a regex tag-stripper
(failure-prone).

Added `strip_html(source: Text) -> Text` — stdlib `html.parser`
based, drops `<script>` / `<style>` bodies, decodes common
entities, collapses whitespace. Pure (registered in
`_PURE_BUILTINS`), so it composes inside `pure fn` bodies. Typical
use: `text = strip_html(resp.body)` before passing to an intent
for semantic extraction.

Reference card gets a new `### HTML` section between the JSON and
Conversion blocks.

### Also: `encode_json` added to pure-builtin registry

Slipped in alongside — a pure function, previously not whitelisted,
so a `pure fn` that wrapped a structured-body builder would get
rejected at parse time. Now matches `parse_json`.

### Tests

- `test_strip_html.py` (11): tag removal, entity decoding, script/
  style body removal, whitespace collapse, paragraph preservation,
  malformed HTML safety, usable-from-pure-fn.
- `test_authoring_prompt_structure.py::test_prompt_warns_against_assuming_ail_promo_subject`
  — locks in the contamination warning, requires the verbatim
  failure string, requires ≥3 non-AIL subject examples.
- `test_authoring_prompt_structure.py::test_write_helpers_freely_guidance_present`
  — locks in the "write helpers freely" section.
- `test_http_graphql.py::test_graphql_non_json_response_is_error`
  flake fix: added `Content-Length` to the inner test server so
  test ordering against the shared fixture doesn't race on
  server shutdown.

531 → 544 tests passing.

### Not a grammar change

New pure built-in only. v1.8 grammar freeze stands.

### Restart required

`ail up` holds old module; Ctrl+C and restart.

---

## v1.17.0 — 2026-04-24

**`perform http.graphql(query, variables?)` — HEAAL harness for GraphQL.**

hyun06000's 2026-04-24 promo-bot session spent three turns in a loop
on GitHub's GraphQL API. The response shape
`{"errors": [{type: "NOT_FOUND", message: "Could not resolve..."}]}`
with no `data` field looked like success to the hand-rolled check
`errs = get(data, "errors"); if errs != ""`. The agent kept
returning `"GraphQL errors: None"` — a useless message, because the
real failure was `data` MISSING, not `errors` populated. No amount
of prompt tuning could fix this reliably: the failure tree for
GraphQL has four distinct branches (HTTP status / parse failure /
errors array / data absent-or-null) and every manual check misses
at least one.

Verdict (same pattern as v1.15.0 `http.post_json` and v1.16.0
`human.approve`): runtime owns the decision tree, author never
sees the envelope.

### New effect

```
perform http.graphql(
    url: Text,
    query: Text,
    variables?: pair-list | Record,
    headers?: [[Text, Text]] | Record
) -> Result[Any]
```

- `ok(data)` — returns the unwrapped `.data` payload. Authors reach
  into mutation results via plain `get()` — never through a
  `data` wrapper, never peeking at `errors`.
- `error("http.graphql: HTTP 401: ...")` — 4xx/5xx, body preview.
- `error("http.graphql: response was not JSON: ...")` — HTML 502
  from gateways, etc.
- `error("http.graphql: <msg> [TYPE] at <path>")` — any non-empty
  `errors` entry in a GraphQL response, formatted with path and
  type for audit.
- `error("http.graphql: response has no `data` field: ...")` — the
  exact case that stumped the field test.
- `error("http.graphql: response.data is null (operation failed
  without an errors entry): ...")` — partial-success trap.

### Authoring prompt

- New primitive listed under side-effects, plus explicit rule
  "Never hand-roll GraphQL error handling with `http.post_json` +
  `parse_json` — the field test showed that pattern mis-diagnosing
  every failure mode."
- The GitHub canonical example in the "post to X" templates is
  fully rewritten to use `http.graphql`. The old wrapper unwraps
  six levels deep (`data.data.createDiscussion.discussion.url`
  with manual errors check); the new version is a flat
  `get(get(get(unwrap(r), "createDiscussion"), "discussion"),
  "url")` after the Result check.
- "Key contrasts" bullet list updated: GraphQL contrast is now
  "the exact failure tree the field test used to mis-diagnose
  (`GraphQL errors: None` in a loop) is now a single Result the
  author cannot mis-classify."

### Tests

- `tests/test_http_graphql.py` (9): success returns `data`; errors
  array becomes error Result (verbatim GitHub NOT_FOUND case);
  `data` missing / `data: null` / HTTP 4xx / non-JSON response
  each become error Results with concrete messages; Authorization
  header forwarded; empty `errors: []` treated as success; empty
  query rejected.
- `test_authoring_prompt_structure.py::test_http_graphql_rule_present`
  — locks in the new rule AND asserts the GitHub canonical
  example uses `perform http.graphql` without the old
  `get(data, "errors")` hand-rolled check.

521 → 531 tests passing.

### Not a grammar change

Runtime effect only. v1.8 grammar freeze stands.

### Restart required

`ail up` holds the old module; Ctrl+C and restart.

---

## v1.16.0 — 2026-04-23

**`perform human.approve(plan)` — HEAAL plan-validate-execute gate.**

hyun06000: *"계획을 세우고 검증받는 단계가 필요할 거 같은데 그게
LLM의 성능을 높이는 방법이니까. 프롬프트로 유도할지 언어 안에 장치로
녹여둘지."*

Judgment: **language, not prompt.** Prompt convention breaks across
models and leaves no audit trail. Grammar-level would require
breaking the v1.8 freeze without benchmark data. L2 runtime primitive
is the right fit — same class as `env.read`, `state.*`,
`http.post_json`, `schedule.every` — closes the class of
"program silently did the irreversible thing" by making the approval
gate non-bypassable in code, and writes the decision to the ledger.

### New effect

```ail
perform human.approve(plan: Text) -> Result[Boolean]
```

Writes `plan` to `<project>/.ail/approvals/pending.json` with a
unique id and status=pending, then polls that file for a decision.
The authoring UI notices the pending record via a new polling
endpoint, renders an Approve / Decline card with the plan text,
and — when the user clicks — POSTs the decision back. The executor
reads the updated status and returns:

- `ok(true)` on Approve → continue with the side effect
- `error("user declined: <reason>")` on Decline → caller returns
  the error normally
- `error("human.approve: timed out waiting ...")` after 10 min
  → clean abort; caller returns the error
- `error("human.approve: no UI context ...")` when running outside
  `ail up` → same

Trace records `human_approve_pending` and `human_approve_decided`
events; project ledger records the decision for audit.

### Server

- Switched `HTTPServer` → `ThreadingHTTPServer`. Required so
  `/authoring-approve` (decision) can execute in a separate thread
  while `/authoring-run` is blocked inside the executor's polling
  loop.
- Sets `AIL_APPROVAL_DIR` for run threads so the effect finds its
  directory.
- New endpoints:
  - `GET /authoring-approval-pending` — returns the current
    pending approval record (id + plan) if any; 204 otherwise.
    Idempotent, polled every 500ms by the UI while a run is
    in-flight.
  - `POST /authoring-approve` — body `{id, decision: "approve"|
    "decline", reason?}`. Writes the decision to the pending file
    and appends a `human_approve` event to the ledger.

### UI

- Authoring run widget now polls `/authoring-approval-pending`
  every 500ms while a run is in-flight (existing pendingBubble
  behavior unchanged).
- When a pending approval appears, renders a yellow card with the
  plan text + ✅ Approve / ❌ Decline buttons. Multiple approvals
  in one run are shown sequentially.

### Authoring prompt

- New primitive listed in the side-effects section with a pointer
  to the PLAN-BEFORE-IRREVERSIBLE-ACTION section.
- New section `=== PLAN BEFORE IRREVERSIBLE ACTION ===` — defines
  when to use (post / create / send / delete), when NOT to
  (http.get, state internal), plan-content rules, and an anti-
  pattern list ("call human.approve AFTER the side effect" —
  forbidden; "split into two-run plan-then-execute flow" —
  forbidden).
- The three canonical "post to X" examples (Discord, Mastodon,
  GitHub GraphQL) rewritten to include the `human.approve` gate
  before the HTTP call.
- Contrast section leads with the approval gate ("not silent, not
  regrettable") above the JSON-encoding contrasts.

### Tests

- `tests/test_human_approve.py` (5): approve unblocks; decline
  surfaces as error with reason; no-UI context returns clean error;
  empty plan rejected; pending record shape (id + plan + created_at
  + status).
- `tests/test_authoring_prompt_structure.py::test_human_approve_section_present`
  — locks in the prompt section, that every canonical example
  shows the gate, and that the gate is the leading contrast bullet.

515 → 521 tests passing.

### Not a grammar change

Runtime effect only — no new keyword, no parser change. v1.8
grammar freeze stands. (Reference card adds the new effect to the
built-in effects list.)

### Restart required

`ail up` processes started before this commit hold the old module
in memory. Ctrl+C and restart.

---

## v1.15.4 — 2026-04-23

**Two chained bugs: `!` in prompt → parse fails → textarea with no hint.**

hyun06000 saw an empty-placeholder textarea below `GITHUB_TOKEN`
entry on a program that shouldn't need any input at all.

Root cause chain:
1. v1.15.0 prompt examples (Mastodon + GitHub GraphQL) used
   `if !resp.ok` — but AIL has no `!` operator (it uses `not`).
   Agents copied the pattern verbatim and produced a program that
   fails at lex time.
2. `entry_uses_input` defaults to `True` on parse failure ("safer
   to show the box than hide it from a program that needs it").
   So the broken program got a textarea.
3. The authoring UI's run widget had no single-program
   parse-error affordance — the parse flag only rendered when
   there were 2+ programs (picker row). With one program, the
   error never surfaced in the run card.

### Fixes

- **Prompt**: `if !resp.ok` → `if not resp.ok` in both http.post_json
  examples.
- **UI**: `renderDynamic` now branches on `!meta().parses` first —
  shows a red "⚠ 파싱 에러" banner with the lex/parse message and
  a 🔧 "Ask agent to fix" button, and SKIPS the textarea/env/run
  block. Running a program that won't parse is worse than showing
  why it won't.
- **Server**: `render_authoring_page` now takes a `programs`
  parameter and seeds it into `programsForNext` at page-load time.
  Previously the initial render used a fallback dummy
  `{parses: true, ...}`, which meant a broken program on page
  reload rendered as if healthy. The server calls
  `list_project_programs(project)` and passes the result through.

### Tests

- `test_authoring_page_shows_parse_error_banner_when_program_broken`
  — seeds a broken program into the page, asserts the banner
  text renders and the parse-error branch precedes the
  textarea-construction branch in the script source.

### Still needs a restart

As with v1.15.2/3 — running `ail up` processes hold the old
module in memory. Ctrl+C and restart to pick up the prompt + UI
fixes.

---

## v1.15.3 — 2026-04-23

**Overwrite-to-iterate regression: agent kept flattening prior
programs into `app.ail`.**

hyun06000's next promo-bot session ended with a single `app.ail`
where v1.13.1 had left three distinct files per channel. The
"new program = new file" rule existed since v1.13.1 but was a
single sentence buried in the memory section — and the rest of the
prompt mentioned `app.ail` as the canonical target 8+ times (XML
protocol example, Finish-the-Job section, invocation constraints,
file-docstring). The agent correctly tracked the dominant signal
and the one sentence lost.

### Prompt restructure

- **YOUR RESPONSE FORMAT** example now uses `DESCRIPTIVE_NAME.ail`
  as the placeholder and calls out that `app.ail` is a reserved
  legacy slot, not a rolling catch-all.
- **FINISH THE JOB** section scrubbed of all `app.ail` hardcoding;
  now references "the `.ail` program" / "a descriptive filename".
- **New dedicated section: `=== ONE PROGRAM, ONE FILE — NEVER OVERWRITE TO ITERATE ===`**
  — hard rule with decision procedure for new-vs-iteration,
  canonical Bluesky-overwrite failure example verbatim, and a
  pre-emit checklist the agent runs before choosing a filename.
- Invocation constraint: `"do not emit ready_to_run until the
  relevant .ail program is coherent"` (was: "both INTENT.md and
  app.ail").

### Regression guard

`tests/test_authoring_prompt_structure.py` — 5 assertions that lock
in the shape of the prompt so a future edit that re-introduces the
bias triggers a test failure:
- `ONE PROGRAM, ONE FILE` section present.
- Bluesky-overwrite anti-pattern verbatim.
- YOUR RESPONSE FORMAT doesn't hardcode `app.ail`.
- Carries forward the v1.15.0 `http.post_json` rule and v1.15.2
  `# INPUT:` rule — these had no structural guard before.

### Legacy test update

`test_prompt_demands_finishing_the_job_in_one_turn` asserted the
old "must include both INTENT.md and app.ail" phrasing, which
contradicted v1.14.0's INTENT.md demotion and v1.15.3's descriptive-
filename shift. Updated to require the `.ail` + `ready_to_run` +
claim-reality rules; INTENT.md is now optional per v1.14.0.

---

## v1.15.2 — 2026-04-23

**Critical: chat page lost every message past the first on reload.**

Field test 2026-04-23: hyun06000 reloaded a long authoring session and
saw only the first agent response — every turn below it was gone.
Root cause was a Temporal Dead Zone bug in the authoring page JS:

```js
const INITIAL_HISTORY = [...];
INITIAL_HISTORY.forEach(entry => {
  addAgent(entry.reply, entry.files, entry.action);  // may call addRunWidget
});
...
let programsForNext = [];   // <- declared AFTER the replay loop
let inputUsedForNext = true;
```

`addRunWidget` reads `programsForNext` / `inputUsedForNext`. Function
declarations hoist; `let` bindings do not — they're in the Temporal
Dead Zone until their declaration line executes. Replaying a
`ready_to_run` turn from history hit TDZ, threw uncaught, halted the
`forEach` after the first turn, and left the top-level script
without running the `let` declarations. A subsequent user send then
threw the same error from `send()`.

Fixed by moving the four `let` state declarations to directly above
the history-replay block. Added `test_authoring_page_declares_let_state_before_history_replay`
to lock in the ordering — the test fails if anyone ever moves them
back.

### Input placeholder hint (`# INPUT: ...`)

hyun06000: *"입력창이 만들어지면 뭘 입력해야 할지 막막할 때가 있어."*
The generic "input (optional)" placeholder left non-programmers
staring at an empty textarea. Agents can now emit a leading comment
on the `.ail`:

```ail
# INPUT: 번역할 한국어 문장을 붙여넣으세요 (예: "오늘 날씨가 좋네요")
entry main(input: Text) { ... }
```

`extract_input_hint` scans the first 20 lines for `# INPUT:` /
`// INPUT:` (case-insensitive), caps at 200 chars, and falls back to
the localized default when absent. The hint flows through the
agentic run response (`input_hint`), the authoring-page Run widget,
and the public service UI (via `render_page`). Authoring prompt
updated with four worked examples and explicit anti-patterns
(tautological hints, missing hints).

### Clipboard copy fallback

Minor: clipboard copy now falls back to a hidden-textarea +
`execCommand('copy')` when `navigator.clipboard` isn't available
(non-secure contexts, older browsers). Paired with the v1.15.1
async-capture fix.

### Not a user-visible API change

`extract_input_hint` is a new helper but not exported from the
package `__init__`. Treat as internal; downstream code relying on
the agentic runtime response shape will see a new `input_hint` key.

---

## v1.15.1 — 2026-04-23

**Two UX bugs from the v1.15.0 field test.**

### Agent must describe what it built

hyun06000 tested the new authoring flow and saw the agent produce Turn 1:
*"AIL과 HEAAL 홍보봇 만들게요! 어떤 채널에 올릴까요?"* + Run button.
The user asked Turn 2: *"너가 만든 프로그램이 뭐야? 실행 버튼을 누르면
뭐가 나타나?"* — a non-programmer has no way to know what a Run button
does without being told. Clicking a black box is a trust failure.

The existing prompt said the `<reply>` should be a "1-2 sentence
confirmation" — too soft. Turn 1's reply technically met that, yet
failed the user. Tightened to an explicit two-part requirement:

- `<reply>` MUST state (a) what the program does and (b) what appears
  when the user clicks Run.
- Added anti-pattern examples (reply that skips straight to the next
  question, reply that only names a file, reply that's vaguely
  "it's a bot").
- Added correct-pattern example showing purpose + Run output + the
  optional follow-up question in order.

### Chat copy button crashed after async clipboard write

`navigator.clipboard.writeText(md)` is awaited before the handler
touches `e.currentTarget.textContent` to flash "✓ copied". By then
the click event has finished propagating and `e.currentTarget` is
`null` — field test surfaced "Cannot read properties of null
(reading 'textContent')". Classic synchronous-capture-before-await
bug.

Fixed by capturing `link = e.currentTarget` and `orig = link.textContent`
at the top of the handler, before any `await`. Also added a hidden-
textarea + `execCommand('copy')` fallback for environments without
the Clipboard API (non-secure contexts, older browsers), so the
affordance works even when the async path isn't available.

---

## v1.15.0 — 2026-04-23

**HEAAL gap closed: JSON serialization moves into the runtime.**

hyun06000's 2026-04-23 promo-bot field test exposed a structural
harness failure: the agent spent 12 turns chasing a malformed GitHub
GraphQL request, hand-rolling JSON via `join(["\"title\": \"", escape_json_text(TITLE), "\""])`,
swallowing the 400, and eventually fabricating the return value
("GitHub Discussion created successfully: True"). hyun06000's
verdict: *"return을 믿지말고 검증을 하라고. 이거 하네스에서 벗어나네?"*
Correct — nothing in AIL stopped the agent from shipping an injection
bug, and nothing forced it to actually read the API response.

The fix is HEAAL at the runtime layer: make malformed JSON
impossible to express.

### New primitives

- **`perform http.post_json(url, body, headers?)`** — body is a
  structured AIL value (list of `[key, value]` pairs at the source
  level, records anywhere). Strings are **refused** with a clear
  pointer at the raw `http.post` form for non-JSON payloads. The
  runtime serializes via `encode_json` and auto-sets
  `Content-Type: application/json`. Authors write the *value*, never
  the encoding.
- **`encode_json(value) -> Result[Text]`** — pure companion to the
  existing `parse_json`. Handles pair-lists-as-objects with the same
  convention `http.post` headers already used. Refuses ok/error
  `Result` wrappers explicitly to force an `unwrap()` at the
  author's boundary.

### Authoring prompt rewrite

- Three canonical "post to X" examples (Discord, Mastodon, GitHub
  GraphQL) rewritten from `join([...])` + hand-rolled `escape_json_text`
  to `http.post_json` + `parse_json(resp.body)` verification.
- New "JSON API authoring rules" section bans hand-rolled JSON
  outright, requires response-body parsing before claiming success,
  and forbids fabricating return values from literals.
- The GraphQL example explicitly shows the `errors` field check —
  HTTP 200 is not logical success for GraphQL, and the old prompt
  never said so.

### Why this was structural, not a bug

`parse_json` had already existed since HEAAL E2, but the authoring
prompt never referenced it — in 12 turns the agent never once
reached for it. The fix is runtime + prompt together: adding the
companion `encode_json` / `http.post_json` and teaching the prompt
to use them. Without both, the gap re-opens.

### Internal

- `_json_normalize` helper in `runtime/executor.py` recognises the
  pair-list-as-object convention recursively; Result wrappers raise
  a typed error that surfaces as `encode_json` error Result.
- `tests/test_json_effects.py` adds 11 tests: flat / nested pair
  lists, quote + newline + backslash escaping, plain-list arrays,
  Result-wrapper rejection (ok and error), plus integration tests
  for `http.post_json` against an `HTTPServer` echo endpoint
  (structured body round-trip, text-body rejection, auto
  Content-Type, caller Authorization preservation, non-2xx
  handling).

### Not a grammar change

This is L2 runtime surface — two new built-in names (`encode_json`
plus `http.post_json`), no parser or keyword changes. The v1.8
grammar freeze stands.

---

## v1.14.0 — 2026-04-23

**Architectural pivot: chat_history is the agent's memory, not
INTENT.md.**

hyun06000 asked the question that flipped the design: *"챗 기반으로
가면 INTENT.md가 꼭 필요하니? 이거 사람이 프로젝트 하나하나 만드는
용도로 설계한 인터페이스잖아? 그러면 챗으로 AI가 프로젝트를 꾸려간다면,
더 AI친화적인 방식이 있을 것 같아서. 여기에 매몰되지 말자."*

Correct. INTENT.md is legacy scaffolding from before chat-driven
authoring. Chat history is naturally cumulative, per-turn, auditable,
and already loaded into the agent's context every turn. Maintaining
INTENT.md as a parallel memory source was generating a class of
"overwrite" / "drift" / "sync" bugs the v1.13.x releases had been
fighting one by one. Cutting the source-of-truth duplication kills
all of them at the root.

### What changed

- **`_read_project_state`** no longer includes INTENT.md in the
  PROJECT STATE block. The agent sees only `.ail` programs with
  parse annotations and `view.html` when present. Chat history
  (always loaded) is now the sole memory source.
- **Prompt** — two big sections removed:
  - "INTENT.md IS CUMULATIVE MEMORY — NEVER OVERWRITE WHOLESALE"
  - "EVERY PROGRAM CARRIES THE PROJECT'S PURPOSE" (the version
    tied to INTENT.md)
  Replaced with a single "YOUR MEMORY IS THE CHAT HISTORY" section
  that does the same job more directly: chat log is memory, first
  user message is the purpose anchor, bake the anchor into every
  new program's intent goals.
- **History formatting** — `_format_history` now prepends a
  `[PROJECT PURPOSE ANCHOR]` block with the first user message,
  so turn N's agent cannot miss the opening statement buried 20
  turns up.
- **INTENT.md role** — optional legacy/README file. Still
  scaffolded by `ail init` (template), but the agent:
  - Is told not to use it as working memory.
  - Is told not to re-emit it every turn.
  - May still write it if the user explicitly asks for a README.

### What stays

- `Project.init` still writes an INTENT.md template on the
  filesystem. Removing it would break `ail init`'s historical
  contract; it's now just a dormant scaffold.
- All `.ail` multi-program handling, env/secret handling, Run
  widget, export, "do the work" prompting — unchanged.
- Chat export still renders INTENT.md if present, just with
  less emphasis.

### Tests

- Replaced `test_prompt_teaches_project_purpose_carries_forward`
  and `test_prompt_teaches_intent_md_is_cumulative` (both now
  obsolete) with:
  - `test_prompt_teaches_chat_history_is_memory` — new framing.
  - `test_project_state_omits_intent_md_in_v1_14` — confirms the
    cut.
  - `test_history_format_highlights_first_user_message_as_purpose`
  - `test_history_format_no_anchor_on_first_turn`

528 passing (+2 from 526).

### Why this matters beyond one release

v1.13.x was a flurry of "don't overwrite INTENT.md", "carry
purpose forward", "bake subject into goals", "finish the job",
"don't rewrite wholesale". Each rule was a patch on a hybrid
design where two things (chat history + INTENT.md) were both
trying to be memory. Remove one, the patches stop being needed.

The agent's memory should BE the conversation, because that's
what the user actually remembers too. That's AI-native. The
hand-edited INTENT.md was always for humans to declare intent
before programming. This isn't that world anymore.

---

## v1.13.4 — 2026-04-23

**Don't reference `input` unless the entry actually uses it.**

Field test: user's PR-bot program showed BOTH the `GITHUB_TOKEN`
secret input AND a user-input textarea, even though the bot was
fully self-contained (no user input needed). Agent had written
something like `payload = input` — a reflex assignment that made
the entry technically reference `input`, which the UI treats as
"show the textarea."

**Prompt now teaches the semantic distinction:**

- `entry main(input: Text)` is the convention (parameter name).
- Whether you *reference* `input` in the body is a CHOICE that
  directly controls the UI.
- Self-contained programs (PR creators, channel posters,
  schedulers, daily jobs) — do NOT reference `input`. UI shows
  only Run + secret inputs.
- Runtime-input programs (summarizers, on-demand converters) —
  reference `input`. UI shows the textarea.
- **Self-check:** "would running this twice with the same env but
  different textarea values legitimately produce different
  outputs?" If no → don't reference. If yes → do.

Broken pattern (`payload = input`) shown as anti-example with the
corrected version alongside.

### Tests

+1 test. 526 passing (+1 from 525).

---

## v1.13.3 — 2026-04-23

Three related "agent doesn't actually do the work" fixes. Common
theme: the LLM claims completion, offloads execution to the user,
or stops after planning.

### Fix 1 — "Draft-only" fallback demoted to last resort

hyun06000 field-test: agent said *"Hacker News는 포스팅 API가 없어서
초안만 써드릴게요. 복사해서 직접 https://news.ycombinator.com/submit
에 올려주시면 됩니다."* This is exactly what the project exists to
kill — pushing the work back onto the non-programmer.

**Prompt rewritten** with a clear hierarchy for channels without
posting APIs:

1. **Propose an API-equivalent channel and actually post there.** HN
   → Reddit r/programming (OAuth API) / Mastodon / Bluesky.
   GeekNews → GitHub Discussion + Korean-instance Mastodon. X/Twitter
   ($100/mo paid) → Mastodon + Bluesky. LinkedIn personal → drop it.
2. **Do both** — post to the API channel AND provide the HN draft as
   a supplement if the user wants to copy it manually.
3. **Only if the user explicitly insists** on the API-less channel,
   provide the draft.

Explicit anti-phrasings listed as rejected (❌) with user-facing
alternatives (✅):

- ❌ "HN은 API가 없어서 초안만 써드릴게요"
- ❌ "복사해서 직접 올려주시면 됩니다"
- ✅ "HN은 자동 게시 불가라 Reddit r/programming으로 갈게요."
- ✅ "Mastodon에 올렸어요. HN 초안도 같이 준비했으니 원하시면…"

### Fix 2 — Finish the job in one turn

Field test: user asked for a PR-creating bot. Agent replied "좋아요!
만들어드릴게요" and wrote INTENT.md (2720 bytes) — but no
`app.ail`, no `ready_to_run` action. User had to prompt again to
actually get the code.

**Prompt now has a FINISH THE JOB IN ONE TURN section.** When the
user asks to build/create/make anything, the agent's `<file>` tags
MUST include the `.ail` that realizes it, AND `<action>` MUST be
`ready_to_run`. Explicit listing of what counts as finished vs. not
finished. If a credential is needed, write `env.read("NAME")`
placeholders in the `.ail` — don't use credential-gathering as an
excuse to skip the file.

### Fix 3 — No claim-reality mismatch

Field test continued: agent wrote second turn "PR 자동 생성 봇
완성했습니다! 아래 입력창에 토큰을 붙여넣으세요." But STILL only
INTENT.md was written — no `app.ail` with `env.read`. Result: no
input box appeared in the UI (the UI triggers off `env.read` calls
in the `.ail`). User waited on a phantom UI.

**Prompt now explicitly bans claim-reality mismatches:**

- Claimed "완성" without `app.ail` → forbidden
- Told user to paste a secret but no `env.read` in the code → forbidden
  ("no call, no input box" — the UI won't surface what the code
  doesn't reference)

Honest state-reporting examples included in the prompt.

### Tests

+2 tests:
- Draft-only is rejected as first choice; API alternatives listed.
- Finishing-the-job + claim-reality rules present in prompt.

525 passing (+2 from 523).

---

## v1.13.2 — 2026-04-23

Two user-requested improvements from live use.

### Chat export + copy

Feedback: *"대화를 저장하거나 복사하는 기능 있으면 좋겠네."*

- New endpoint `GET /authoring-chat-export` — renders the full
  conversation as a standalone markdown document (turns, file
  writes, actions, run results).
- Header links in the chat UI: **대화 내보내기 / Export** downloads
  a `<project>-chat.md` via blob; **복사 / Copy** puts the
  markdown on the clipboard.
- `export_history_as_markdown(project)` is the reusable helper.

### Project purpose threads through every new program

Feedback: user's project was "AIL/HEAAL 홍보". Several turns later
they asked "추천 봇도 만들어줘" — agent wrote a *generic* channel
recommender, forgetting the subject. User had to remind it
("ail이랑 heaal 홍보하는 봇이라니까 까먹은거니").

**Fix — `EVERY PROGRAM CARRIES THE PROJECT'S PURPOSE` section added
to the prompt.** Before writing any program, re-read INTENT.md's
top-level purpose; bake it into every `intent` goal string and
relevant literal. A "channel recommender" in a project about AIL
must have `goal: "recommend the best developer communities to
promote the AIL programming language and its HEAAL paradigm…"` —
not a generic one. `<reply>` should confirm the subject when
naming the new program ("AIL/HEAAL 홍보용 채널 추천봇 만들었어요")
so continuity is visible.

Pivot recognized as exception: if the user's prompt genuinely
implies an entirely new project ("이제 게시는 그만두고 아예 새
프로젝트로 바꾸자"), agent asks a single yes/no before rewriting the
top-level purpose.

### Tests

+6 tests:

- Prompt teaches purpose carries forward (1).
- `export_history_as_markdown` — empty (1) / turns (1) / run
  results (1).
- `/authoring-chat-export` endpoint returns markdown with proper
  headers (1).
- Chat UI has export + copy links wired to the endpoint (1).

523 passing (+6 from 517).

---

## v1.13.1 — 2026-04-23

Five field-test corrections that shift the agent from "chatty
assistant" to "actual driver":

### Multi-program projects

**Problem.** v1.13.0 agent overwrote `app.ail` every turn. A user
who asked "make a word counter" and later "now add a sorter" lost
the first program — there's no space for *independent* programs
in the same project.

**Fix.** A project now holds many `.ail` files. The agent is
taught:

- NEW use case → NEW descriptively-named file (`word_counter.ail`,
  `news_fetcher.ail`). Do NOT overwrite an unrelated existing file.
- EDIT/FIX → update the existing file by its current name.
- `app.ail` is just a conventional first name with no special
  status; pick descriptive names for the rest.

State view now lists every `.ail` in the project with a parse
status so the agent knows what's there. `.ail/active_program`
marker tracks the last-written file so the Run widget defaults to
it. `POST /authoring-run?program=FILENAME` selects explicitly,
with path-traversal rejection.

UI: when ≥ 2 programs exist, the Run widget renders a program
selector; each option's input-usage and env-requirement come from
the response so the widget recomputes per-program.

### JSON-envelope stripping in run results

**Problem.** LLM intent responses sometimes slip through
`{"value": "...markdown..."}` envelopes that `parse_value_confidence`
didn't unwrap (nested or edge shapes). The final UI showed
pretty-printed JSON wrapping markdown instead of just markdown.

**Fix.** `_render_value` now peels `{"value": X}` and
`{"value": X, "confidence": N}` envelopes recursively (capped at 6
levels). A dict with other keys (real structured data) is
preserved and pretty-printed as before.

### Anti-interrogation prompt rewrite

**Problem.** hyun06000 feedback: *"써보니까 사람한테 물어보고
요구하는게 너무 많다. 인간의 개입을 최소화하는게 이 프로젝트의
목적임을 명명백백하게 알릴 필요가 있겠어. 너무 많은걸 물어보다보니
그냥 성능나쁜 챗봇이 되어 버렸어."*

The agent was clarifying-question-first by default — asking about
Korean vs English, error handling shape, port numbers, tone, output
format. All defaultable. All interrogation.

**Fix.** New **DEFAULT AGGRESSIVELY** section in the prompt. The
framing flipped:

- The project's premise is MINIMIZING human involvement. The
  second-turn-clarifier is the failure mode this project exists to
  kill.
- Agent should only ask for: **secrets** (and even then write code
  with `env.read` first and let the masked UI input collect the
  value), **permissions** (access the human must grant), **genuinely
  weighty irreversible choices** where every default would be wrong.
- Explicit DO-NOT-ASK-ABOUT list: language, error handling shape,
  port, output format, tone/style, "should I add X?", "fn or intent?".
- Old rule "ask one question at a time" removed — it was the wrong
  default.

### INTENT.md accumulative, not rewritten

**Problem.** hyun06000: *"INTENT.md도 계속 덮어쓰는것 같은데? 이러면
목적성이 계속 바뀌어서 곤란해. 하나의 챗 세션은 계속해서 필요한
정보들을 누적할 수 있어야 해."*

Agent was re-drafting INTENT.md around just the latest request,
losing prior context. The project's purpose seemed to mutate
turn-by-turn.

**Fix.** Prompt now has an **"INTENT.md IS CUMULATIVE MEMORY"**
section. Rules: don't rewrite from scratch. First turn creates a
skeleton. New program → append a `### filename.ail — purpose`
subsection under `## Programs`. Program refinement → update just
that subsection. Project-wide constraints → top-level, then leave
alone. Turn skipping — omit `<file path="INTENT.md">` when nothing
would change. Example evolution from turn 1 (word counter only) to
turn 2 (word counter + sorter) included.

### No terminal, no env-var talk — UI handles secrets

**Problem.** hyun06000: *"env.read를 유저가 업데이트 할 수 있는 툴이
아직 구현 안 된건가? 나한테 환경변수를 등록하라고 하네. 비개발자는
환경변수가 뭔지도 몰라서 이러면 곤란한 상황이 될 수 있어."*

The masked-input UI landed in v1.13.0 but the agent prompt still let
the LLM tell users "set the DISCORD_WEBHOOK_URL environment variable"
or "export in terminal". Non-programmers have no mental model for
that.

**Fix.** Prompt is explicit — `Never say` and `Say instead` lists
included verbatim. Agent MUST NOT mention terminals, exports, shell,
.env files, environment variables. Instead: write `env.read("NAME")`
in the code, and in `<reply>` point the user to where to GET the
credential ("Discord 서버 설정 → ..."), knowing the UI auto-surfaces
the masked input. User vocabulary only.

UI label changed from "환경변수 필요" to "**설정 필요 / This program
needs:**". Placeholder changed from "값 붙여넣기" to "여기에 붙여넣으세요".
ail-promoter's error messages rewritten to match.

### Tests

+9 tests:

- `list_project_programs` discovers multiple `.ail` files (1).
- Turn response includes `programs` + `active_program` (1).
- `/authoring-run?program=X` selects the right file (1).
- `/authoring-run` rejects path traversal in the program param (1).
- `active_program` marker updates on each write (1).
- Prompt teaches multi-program naming + don't-overwrite (1).
- Prompt pushes toward aggressive defaults (1).
- `_render_value` strips value-envelope wrappers (1).
- Prompt teaches INTENT.md is cumulative (1).
- Prompt bans terminal/env-var vocabulary (1).

517 passing (+10 from 507).

### Why these three together

The common thread is the same user complaint: the agent doesn't
feel like an agent. It overwrites, it wraps, it asks. v1.13.1
stops all three.

---

## v1.13.0 — 2026-04-23

**The self-promotion agent, plus the infrastructure that makes it
possible.** This release began as "build an agent that promotes AIL
with AIL" and grew into the first HEAAL-complete authoring stack:
the agent knows it has real side-effect powers, can enter its own
secrets safely from chat, and understands the quirks of writing
AIL itself.

### Added — `examples/agentic/ail-promoter/`

The flagship self-promoter. AIL written in AIL, promoting AIL.

- **Live research** via `perform http.get` against GitHub
  (`api.github.com/search/repositories`) and Hacker News
  (`hn.algolia.com/api/v1/search`). No training-data guessing — real
  repos and real stories fetched fresh every run.
- **Channel-tailored drafts** via `intent`: Discord, Mastodon,
  Bluesky, Show HN, GitHub Discussion, r/ProgrammingLanguages.
  Each intent has a channel-appropriate goal (char limit, tone,
  link format).
- **Real posting** via `perform http.post`:
  - Discord webhook (no auth header — the URL is the secret).
  - Mastodon Bearer-token auth via `env.read("MASTODON_TOKEN")`.
- **Draft-only channels** (HN, GitHub Discussion, Reddit, Bluesky):
  no programmatic posting API, so the agent hands back formatted
  text for the user to submit manually.
- **State tracking**: `state.write` for drafts, research cache,
  post log.
- **Dashboard `view.html`**: status of configured channels, per-
  channel Generate-Draft + Post buttons, post history.

### Added — chat-safe secret entry (`perform env.read` wired into UI)

Problem: an AIL program calling `perform env.read("DISCORD_WEBHOOK_URL")`
previously needed the user to `export` in the terminal, kill the
server, and restart. Not chat-native.

Fix:

- New helper `list_required_env_vars(app_source)` scans the program
  for `env.read("NAME")` calls.
- `/authoring-chat` and `/authoring-run` responses include
  `env_required: [{name, set}]`.
- Run widget renders a masked input row for each unset name.
- `POST /authoring-set-env` (JSON body `{name, value}`) writes the
  value to `os.environ` AND to `.ail/secrets.json`. The file is
  auto-gitignored by `Project.init` writing `.gitignore`.
- `load_project_secrets` runs on `serve_project` startup, merging
  stored secrets into env (explicit shell exports still win).
- **Values never hit the chat history, the ledger, or any HTTP
  response.** Only the name is logged on set.

### Authoring prompt — two more corrections

1. **Language matching extends to AIL output.** If the user is
   conversing in Korean, every `intent` in `app.ail` must produce
   Korean output — add `language_is_korean` or put "Reply in Korean."
   in the goal string. Channel-specific exception: if the venue is
   English-only (HN, r/ProgrammingLanguages), that intent stays
   English regardless. The chat language and the program output
   language must stay in sync.

2. **Goal strings must be quoted.** `goal: Korean summary of X`
   parses as `Identifier("Korean")` — the rest is silently dropped.
   Use `goal: "Korean summary of X with full instructions..."`.
   Documented as the single most common AIL authoring mistake.

### Authoring prompt — agentic capability override (from v1.12.7
work, now consolidated)

"YOU CAN DO, NOT JUST SAY" section. Overrides the default chatbot
refusal reflex with explicit framing: you are the author and driver
of AIL programs; anything an AIL program can do, you can do. Concrete
worked examples for Discord / Mastodon / GitHub / Slack / Bluesky
posts. Explicit anti-list of phrases not to produce ("I can't post
on your behalf", "I'm just an AI assistant"). Explicit handling of
channels without APIs (HN, GeekNews, X/Twitter): draft-only with
manual submit.

### Scaffolder — `.gitignore` on `ail init`

`Project.init` now writes `.gitignore` with `.ail/` if none exists.
Ensures `secrets.json`, the ledger, and authored state don't leak
into commits.

### Tests

+10 new tests covering:

- env var detection from source (3).
- `/authoring-chat` + `/authoring-run` include `env_required` (2).
- `/authoring-set-env` persists + never-logs value, rejects bad
  names (2).
- `load_project_secrets` merges JSON into env (1).
- `.gitignore` written on init (1).
- Chat UI renders the masked secret input widget (1).

507 passing (+10 from 497).

### Why this release matters

v1.12.x made the chat a real authoring surface. v1.13.0 makes the
chat a real **agentic** surface: the agent knows it can act, can
ask for the secrets it needs safely, and demonstrates the full
loop in a working self-promotion example that runs in any fresh
clone.

---

## v1.12.6 — 2026-04-23

**Live data first.** Field test found the agent scraping
`google.com/search` for "어디 홍보할 수 있을지 찾아줘". Google returns
JS-only result pages; `http.get` came back with no actual results;
the intent model correctly said "I can't find anything" — the right
answer to the wrong program.

A draft of this release tried to fix that by telling the agent to
use `intent` directly for knowledge queries, letting the model
answer from training. hyun06000 caught this:

> "모델이 이미 학습한 데이터는 최신 자료가 아닐 수 있어. 우리는
> 모델의 논리력과 도구활용력을 원하는거지 모델 자체의 지식을 원하지는
> 않아. 지식은 ail 프로그래밍을 통해 최신의 최상의 지식을 얻어야해."

Exactly right. HEAAL's claim is that knowledge flows *through* the
harness, not baked into the model. Training data is months/years
old; stars, trends, active communities, recent releases move fast.
What we want from the model is reasoning + tool-use. The facts
should come from live HTTP sources on every run.

### Rewritten authoring prompt — "LIVE DATA FIRST"

- Explicit rule: if the user's question depends on current state of
  the world ("요즘", "가장 핫한", "최근", "latest", stars, trends,
  downloads, who's discussing X now) the program **must** `perform
  http.get` a live source. Do NOT list things from training memory.
- `intent` is for reasoning over fetched data (summarize, rank,
  filter, extract) — not for inventing the data.
- Only use `intent` without live data for pure reasoning that
  doesn't depend on current state (AIL/HEAAL explanations,
  transforming user-provided input, well-known stable facts).
- Anti-pattern still in place: no Google / Bing / DuckDuckGo
  scraping — their result pages are JS-only.
- Concrete API endpoints listed, all working via plain `http.get`:
  GitHub search (repos + issues), Hacker News Algolia, Reddit JSON,
  Wikipedia REST, Google News RSS, npm registry, PyPI JSON.
- Worked example — "요즘 가장 핫한 harness engineering 프로젝트
  찾아줘" — shows the canonical pattern:
  `http.get(GitHub search API)` → `intent top_repos(json) -> Text`.

### Tests

- New test pins the live-data-first direction (training is stale,
  reasoning + tool-use, concrete endpoints present).
- Existing v1.12.1 research-guidance test adjusted to the stronger
  phrasing.

498 passing (+1 from 497).

### Why this matters beyond one bug

This isn't just a prompt tweak. It's the philosophical spine of
HEAAL restored: **the harness is the grammar, the live data source
is the source of truth, the LLM is the reasoning engine in
between**. When you ask the agent to research, it should go fetch.
Not guess from memory.

---

## v1.12.5 — 2026-04-23

**Field-test fixes.** hyun06000 ran the chat flow with a real prompt
("research communities for harness engineering"). Three issues:

1. The LLM wrote free-prose inside `goal:` containing the word
   `with`, which the parser reads as the `with context NAME:`
   production → `ParseError: expected context at 4:64, got IDENT('their')`.
2. Clicking Run showed that error wrapped in a full Python
   traceback — noise to a non-programmer.
3. The Run widget showed an input textarea even though the entry
   didn't use `input`, making the user wonder what to type.

### Parse-check visible to the agent

`_read_project_state` now runs the parser on `app.ail` and, on
failure, annotates the state view with `[PARSE ERROR — this file
will NOT run until fixed]` plus the clean error message. The agent
sees this in its prompt and must fix it before re-emitting
`ready_to_run`.

Prompt additions (from the field-test lessons):

- No `#` comments — AIL uses `//`.
- Intent constraints are identifier-style phrases
  (`output_is_valid_json`, `language_is_korean`) — NOT free prose.
- Don't put JSON shape descriptions in constraints.
- Only use syntax from the reference card.

### Clean error rendering

`/authoring-run` catches `ParseError`, `LexError`, `PurityError`,
`ImportResolutionError` and returns the message alone — no Python
traceback in the `diagnostic` field. Unexpected errors still carry
a bounded traceback (1 KB max) so internal bugs aren't invisible.

### Input-aware Run widget

Both `/authoring-run` and `/authoring-chat` responses now include
`input_used: bool`. The UI hides the input textarea when false and
renders a small note "이 프로그램은 입력이 필요 없어요." Pre-v1.12.5
history replays default to showing the input (backward compatible).

### 🔧 One-click fix request

Error result bubbles now carry a red "🔧 에이전트에게 수정 요청 /
Ask agent to fix" button. Click → sends "방금 발생한 에러를
고쳐주세요." to the chat as the user's next message. The agent sees
the error in history (and the parse error in its state view from the
first fix above) and writes a correction. One click, no typing.

### Tests

+4 tests in `test_authoring_chat.py`:

- `[PARSE ERROR]` annotation surfaces in agent state + prompt.
- `/authoring-run` response includes `input_used`.
- `/authoring-chat` turn response includes `input_used`.
- `ParseError` from /authoring-run has no Python traceback.

497 passing (+4 from 493).

### Why this cluster of fixes

LLMs will sometimes write invalid AIL — that's expected. The harness
response should be: catch it early (parse check), show it cleanly
(no traceback), and make recovery trivial (one click). v1.12.5 closes
all three.

---

## v1.12.4 — 2026-04-23

**Chat is the only UI.** Previously `ready_to_serve` clicked → page
navigated away to the textarea service UI. Even with v1.12.3's "back
to chat" button, that was still a page transition. Worse, once the
program was "ready_to_run" the chat offered a one-shot Run button
that disappeared after one click — if you wanted to call the service
again with a different input you had to ask the agent for another
turn.

Reframe: the chat *is* the run surface. Calling the program is a
widget you press repeatedly. Deploying as a service doesn't change
the UI, it just adds a shareable URL.

### Changed — `ready_to_run` renders an inline, repeatable widget

Was: one "Run it" button, single click, result bubble, button gone.
Now: an inline "Run" card with an optional input textarea + Run
button. Press Run as many times as you want; each click produces a
new result bubble below. Re-run with different inputs without
bothering the agent.

### Changed — `ready_to_serve` no longer navigates

Was: click → confirm dialog → page swaps to service UI → chat dead.
Now: click-free — the same widget renders, wrapped as a green
"🌐 서비스 모드" card. Same repeatable call surface, plus a
`/service` link for external consumers. The chat stays active; no
confirm dialog, no page change.

### Added — `GET /service`

A dedicated route that serves the classic UI (view.html or the
default textarea page) independent of chat state. This is the
URL to hand out to non-chat consumers — curl users, teammates,
other apps. Opens in a new tab when clicked from the service card
so the chat tab stays alive.

### Removed from the UI

- The one-way `runNow()` JS (replaced by the repeatable widget).
- The confirm-dialog `startAsService()` (serve no longer transitions).
- Any remaining code that redirected after POST `/authoring-complete`
  from chat — the endpoint still exists for backward compat and for
  cases where someone actively WANTS to make the classic UI the
  default on GET / (rare; involves manually marking the project).

### Unchanged

- `POST /authoring-run` still the call surface for the widget
  (reads input from body, returns JSON outcome).
- Chat history still records `run_result` entries so the agent sees
  outcomes on the next turn.
- `POST /back-to-chat` still works for anyone on an old authored
  project with a marker.
- Classic service UI still links back to chat via "← 대화로
  돌아가기" when history exists (v1.12.3).

### Agent prompt updated

Teaches the agent that both actions keep the user in chat —
`ready_to_run` for "simple task, one-shot or repeated call" and
`ready_to_serve` for "they'll share this or want the /service link",
but the UI difference is just framing (card color + share link), not
navigation.

### Tests

+3 tests in `test_authoring_chat.py`:

- Inline run widget is wired (no more one-shot redirect button).
- Service card links to /service route.
- /service route serves the classic UI independently.

493 passing (+3 from 490).

### Why this matters

"복잡한 태스크는 ail up으로 처리" — yes, but the UX should never
force a page transition to express it. A dashboard, a webhook, a
cron service are all just AIL programs you can call. The chat is
the console.

---

## v1.12.3 — 2026-04-23

**Dead-end fix.** hyun06000 field-tested v1.12.0–2 and found the
"Run it now" button was a trap: clicking it killed the chat, swapped
in the service UI, and left the user with no way back. If the
generated program was wrong (wrong input shape, runtime error, etc.)
the user was stuck — couldn't edit, couldn't retry, couldn't return
to the chat.

Root cause: "Run" was conflated with "deploy as long-running service".
Every first-run was forced into `ail up` mode even when the user just
wanted a one-shot preview (the `ail ask` case).

### Redesigned — Run happens INSIDE the chat

- The "Run it" button now calls `POST /authoring-run`, which executes
  `app.ail` once and returns the outcome as JSON.
- The outcome renders as a **result bubble** in the conversation
  (green for success, red for error + diagnostic from v1.10.1).
- No page redirect. The chat stays active; the user can immediately
  say "고쳐줘 / fix it" or "이렇게 바꿔줘" and iterate.
- The run outcome is recorded to `chat_history.jsonl` as a
  `run_result` entry, so the agent sees the error (or the value) on
  the next turn and can act on it.

### Added — `POST /authoring-run`

Executes the project, returns `{ok, value, diagnostic, error}`.
Records the outcome to history. Ledger event: `authoring_run`.

### Added — `POST /back-to-chat`

Reversible transition. Deletes `.ail/authored_at` so GET / serves
the chat UI again. Chat history preserved — it's just the "service
mode" marker that goes. Ledger event: `back_to_chat`.

### Added — "← Back to chat" button on the service UI

Shown on the service-UI page header whenever `chat_history.jsonl`
exists for the project. Click → POSTs `/back-to-chat` → reloads →
chat UI with full history. Korean + English labels.

### Added — separate `<action>ready_to_serve</action>` for deployment

- `ready_to_run` → now means **run in chat** (default, safe, reversible).
- `ready_to_serve` → **deploy as service** (explicit opt-in, confirm
  dialog). Only shown when the user has said they want a long-running
  service. Still marks `authored_at` and transitions the UI.
- `ready_to_deploy` recognized as an alias for `ready_to_serve` for
  backward compatibility.

### Updated — agent system prompt

Teaches the distinction between `ready_to_run` and `ready_to_serve`.
Also: when history contains `[Run result — ERROR]`, the agent
prioritizes fixing the issue and re-emitting `ready_to_run`. When
`[Run result — OK]`, it offers refinement or `ready_to_serve`.

### Updated — `project_is_fresh`

New rule: if `chat_history.jsonl` exists and `authored_at` doesn't,
return True (serve chat) regardless of `app.ail` content. So the
"back to chat" round-trip actually returns to chat, not back to the
service UI. Legacy examples (no chat history) keep their current
behavior — served as services because they have `entry main`.

### Tests

+6 new tests in `test_authoring_chat.py`:

- `/authoring-run` runs and returns JSON
- `/authoring-run` records to history
- `/back-to-chat` removes marker + next GET / serves chat again
- Back link appears on service UI when chat history exists
- Back link absent when no chat history
- History format includes run results in agent prompt
- `ready_to_serve` recognized by the XML parser

2 stale assertions in `test_two_turn_conversation_reaches_ready_to_run`
updated for new fresh-project semantics.

490 passing total (+6 from 484).

---

## v1.12.2 — 2026-04-23

Small chat UI fix. Previous: Ctrl/Cmd+Enter sent, plain Enter added
a newline. New: Enter sends, Shift+Enter adds a newline — the
standard everyone expects (Slack, Discord, ChatGPT, Claude.ai).

Hangul / Japanese IME composition is guarded so that pressing Enter
to commit a half-typed composition does NOT submit a half-typed
message. Uses both `isComposing` and `keyCode !== 229` for cross-
browser coverage.

Placeholder text updated to announce the convention.

+1 test pinning the handler. 484 passing.

---

## v1.12.1 — 2026-04-23

**Field-test fix.** hyun06000 opened `ail init` and asked the
authoring agent "what is HEAAL?". The agent said it didn't know and
refused to web-search — even though AIL itself has `perform
http.get`, which the agent could have proposed as a program.

Both failures traced to the authoring system prompt:

1. It only included the AIL *language* reference card. No project
   identity (what AIL is, what HEAAL means). The agent couldn't
   answer AIL/HEAAL meta-questions from the prompt alone.
2. It gave no guidance on "unknown topic" requests, so the LLM
   defaulted to "I can't search" instead of the HEAAL-aligned move:
   propose authoring a small AIL program that fetches and
   summarizes.

### Fixed — authoring agent system prompt

Added two sections:

**PROJECT IDENTITY** — a paragraph on AIL (`ail-interpreter` on
PyPI, GitHub repo) and HEAAL as a paradigm (grammar-level harness,
vs. Python + AGENTS.md / linters / pre-commit). Lists the five
concrete safety properties: no `while`, required `Result`, static
`pure fn`, `intent` as the only LLM path, `perform env.read` for
credentials.

**KNOWLEDGE + RESEARCH** — instructs the agent that when asked about
something it doesn't know (current news, live data, tool state), it
should NOT decline. Instead, propose authoring a small AIL program
using `perform http.get` + `intent` to fetch and summarize. Example
snippet included in-line.

Also: explicitly tells the agent it's been given the AIL/HEAAL
identity in the prompt — don't claim ignorance of what you were
just told.

### Tests

+1 test in `test_authoring_chat.py` pinning the prompt content so
future changes can't silently drop HEAAL identity or the research
guidance. 483 passing (+1 from 482).

---

## v1.12.0 — 2026-04-23

**Primary entry point redesign: `ail init` launches a conversational
authoring chat.** Non-programmers don't edit `INTENT.md`. They
describe what they want in a chat, and an agent writes INTENT.md and
app.ail incrementally — same pattern as Claude Code, but for AIL
projects in a browser tab.

This closes the "humans never touch the code layer" claim from
scaffolding through authoring through running. The user never opens
a `.ail` file.

### Flow

```
$ ail init my-app
✓ Created ./my-app/
  chat:  http://127.0.0.1:8080/

[browser opens]
Agent: 어떤 걸 만들고 싶으세요?
You:   텍스트 감정 분석 서비스요
Agent: 좋아요. 빈 입력은 에러로? 아니면 중립?
       ✓ INTENT.md 작성 (80 bytes)
You:   에러로
Agent: 알겠어요, 기본 틀 준비됐어요.
       ✓ INTENT.md (120 bytes)
       ✓ app.ail (250 bytes)
       [▶ 실행해보기]  ← click
```

Click "실행해보기" → the same page reloads as the regular service UI
(textarea / view.html, depending on the project). If tests fail or
behavior is wrong, user closes tab and relaunches `ail up` — the chat
history is preserved on disk and resumes where it left off.

### Added — `ail/agentic/authoring_chat.py`

`AuthoringChat(project, adapter)` with a single `turn(user_message)`
entry point. Loads last 12 turns of history, reads current project
file state, builds a prompt with the AIL reference card + protocol
rules, calls the adapter, parses the response, writes files (with
path-traversal / extension / size safety checks), appends to
`.ail/chat_history.jsonl`.

XML response protocol (what the LLM must emit):

```
<reply>user-facing message</reply>
<file path="INTENT.md">full new content</file>
<file path="app.ail">full new content</file>
<action>ready_to_run</action>
```

`<reply>` required; everything else optional. `<action>` is a UI
affordance — when present, the chat shows a "Run it now" button.

Safety:
- allowed extensions: `.md`, `.ail`, `.html`, `.json`, `.txt`
- rejects path traversal, absolute paths, escapes from project root
- 64 KB per-file write cap
- only two recognized actions (`ready_to_run`, `ready_to_deploy`)

### Added — `ail/agentic/authoring_ui.py`

The chat HTML/JS. Served on `GET /` when the project is fresh (no
`authored_at` marker, no meaningful `app.ail`). Standard chat bubbles,
typing indicator, file-write confirmations inline, auto-resizing
textarea, Ctrl+Enter to send. History replayed from server on page
load so a tab close and reopen doesn't lose context.

### Added — server endpoints

- `POST /authoring-chat` — body = user message, response = JSON
  `{reply, files, action}`.
- `POST /authoring-complete` — marks project authored, future
  `GET /` serves the service UI.

`GET /` now branches: fresh project → chat UI, authored → existing
view.html or textarea UI.

### Modified — `ail init`

`ail init <name>` now scaffolds the project AND launches the
authoring server AND opens the URL in the default browser.

Flags:
- `--port N` — port for the authoring server (default 8080, scans
  up to +64 for a free port).
- `--no-chat` — scaffold and exit (scripted / CI use; preserves the
  v1.11 behavior).
- `--no-open` — don't auto-open the browser (the URL is still
  printed to stdout).

### Integration with existing pieces

| Feature | Role |
|---|---|
| `intent` | agent decides what to ask and write |
| `perform state.*` | chat history + project state on disk |
| `--auto-fix` | still available for `ail up` runtime failures |
| `ail chat` | still available for one-shot natural-language edits |
| v1.10.0 harness | intent responses still type-validated |
| v1.10.1 diagnostics | runtime errors still surface in the service UI |

### Existing examples unchanged

All five agentic examples (word-counter, csv-stats, visit-counter,
sentiment, news-ticker, ail-herald) have real `app.ail` files with
`entry main`, so they're detected as authored and serve their
existing UIs — no regression.

### Tests

- +20 tests in `test_authoring_chat.py` covering XML parsing (5),
  file-write safety (5), `project_is_fresh` detection (4), turn
  integration (3), server integration (3).
- 482 passing total (+20 from 462).

### What this replaces

The old flow:

```
$ ail init my-app
# now open my-app/INTENT.md in a text editor
# write your description
$ ail up my-app
# hope the agent authors app.ail correctly
# if not, ail chat ... or manual edit
```

Becomes:

```
$ ail init my-app
[chat opens, describe what you want, click Run]
```

### Not included (future work)

- `<action>ready_to_deploy</action>` handshake for PyPI / Fly.io /
  etc. — the plumbing is there but no implementation yet.
- Streaming agent responses. Current implementation waits for the
  full LLM response before rendering.
- Split-pane "chat + preview" during the run phase. For now the
  transition is a full page reload.

---

## v1.11.1 — 2026-04-23

**ail-herald becomes a real onboarding agent.** Field feedback from
hyun06000 (non-Discord user): the v1.11.0 release presumed the user
knew what a webhook was and had already created one. That's a hole
in the "agent for non-programmers" claim. A true agent negotiates
its requirements from zero, in plain language, before asking for
anything.

### Rewritten — `examples/agentic/ail-herald/` as a conversational
state machine

No preconfig required. Open the page and the agent introduces
itself in Korean, then offers two paths:

- **글만 받기 (draft-only)** — zero setup, intent writes a promo
  post, user copies it wherever.
- **Discord에 올리기 (auto-post)** — the agent checks for a stored
  webhook URL; if absent, walks the user through creating one:
  1. "웹훅이 뭐냐면..." (what a webhook is, in one paragraph)
  2. Step-by-step UI for creating the webhook in Discord
  3. Paste field for the URL, with format validation
  4. Saves to state; next visit skips onboarding
  5. Draft → Approve → Publish flow

Every screen has a "← 뒤로" / "← 처음으로" button; nothing is a
dead end.

### New UI protocol

`entry main` returns a list of `[key, value]` pairs. The bundled
`view.html` parses the JSON and renders messages, drafts, action
buttons, and text inputs generically — no AIL code generates HTML.

Supported keys:

- `message` — plain text (Korean or English) to display
- `draft` — the current draft, rendered in a code-style block
- `action` — `"label|input_value"` button; click sends POST body
- `input` — `"placeholder|input_prefix"` text input; submit sends
  POST body = `<prefix><value>`

This is a small, generic protocol that a future generic "agent
UI" could reuse.

### State machine

Stored in `state.write("step", ...)`:
`start → discord:intro → discord:howto → discord:paste →
discord:ready → drafted → posted`, or shorter
`start → draft_only:ready → drafted`. Reset button wipes state
cleanly.

### No new AIL primitives

Everything in v1.11.1 is composition of what already existed
(state.*, env.read, http.post with headers, intent, clock.now).
No parser/executor changes.

### Tests

462 passing (unchanged from v1.11.0). Smoke tests:

- Full conversation from start → Discord intro → howto → paste →
  bad URL rejection → reset → draft-only → draft.
- End-to-end Discord publish against a local mock webhook;
  verified correct Content-Type + JSON body.

---

## v1.11.0 — 2026-04-23

**Self-promotion agent.** AIL written in AIL promoting AIL. The
ail-herald example drafts a promotional post via `intent`, waits
for human approval in the browser, and — once approved — actually
posts it to Discord via a webhook. Human approval is the trust
boundary; past it, the agent acts autonomously.

This is the meta-demo the project has been missing: the language's
own case study is a program written in the language, doing real
work, running on the language's own harness.

### Added — `perform env.read(name: Text) -> Result[Text]`

Read an OS environment variable as `Result[Text]`. `ok(value)` when
set (empty string is a valid value, not an error), `error("... not
set")` when absent. The only sanctioned path for credentials (API
tokens, webhook URLs, auth headers); hardcoding placeholders like
`apiKey=demo` in source is forbidden by the authoring prompt (see
v1.10.1). Launch-time env var is the trust boundary.

### Added — `perform http.post` optional `headers` kwarg

Accepts two shapes:

- A record (runtime dict, typically from intent or state).
- A list of 2-element `[key, value]` lists — the source-level form,
  since AIL has no dict literal syntax:
  ```ail
  perform http.post(url, body, headers: [
      ["Authorization", t],
      ["Content-Type", "application/json"]
  ])
  ```

Default `User-Agent: ail-http-effect/1.0` still applied; the caller
can override it.

### Added — `examples/agentic/ail-herald/`

The meta agent. Three AIL-native primitives composing:

- `intent write_promo_post() -> Text` — v1.10.0 harness validates
  the return is plain Text, not a JSON envelope.
- `perform env.read("AIL_HERALD_DISCORD_WEBHOOK")` — pick up the
  webhook URL at launch, never in source.
- `perform http.post(url, body, headers: ...)` — actually publish.

`view.html` renders the human-approval UI: "New draft" generates
via intent; "Approve & post to Discord" fires the real HTTP.

### Tests

- `test_env_effect.py` — 4 tests (ok, empty-string-is-valid, error
  when unset, reject empty name).
- `test_http_headers.py` — 3 tests (Authorization Bearer delivered,
  Content-Type merged with default User-Agent, backward
  compatibility without headers kwarg).
- 462 passing total (+7 from 455).

### Why this release matters for HEAAL

Credential handling and outbound HTTP were the last common sources
of "just trust the author" gaps. Now:

- Credentials in env vars only; the authoring prompt rule against
  placeholder keys is backed by a real mechanism.
- Outbound HTTP has structured headers support for real APIs
  (Bearer auth, JSON content type).
- Human approval is the explicit trust boundary between agent
  drafting and agent acting.

No new grammar. No new AST nodes. Just two effects slotting into
the existing harness.

---

## v1.10.1 — 2026-04-23

**Non-programmer dead-end fix.** hyun06000 field-tested the
`ail-news` project (a Hormuz-Strait news dashboard authored by
Sonnet via `ail ask`). Sonnet hardcoded `apiKey=demo` on newsapi.org,
which returns 401. The program's Result-based error handling kicked
in correctly and returned `error("No news available and fetch
failed")` — but a non-programmer browser user hitting HTTP 500 with
that opaque message has no path forward. HEAAL's claim is that the
harness reaches all the way to the user; a useless error message is
a hole in that claim.

### Added — HTTP effect trace instrumentation

`_http_effect` now records `http_call` events to the trace on every
call (success, HTTP error, network error). Payload: method, url,
status, ok, body_preview (on failure), network_error (when urllib
raises a URLError).

### Added — diagnostic-aware 500 responses

`server._diagnose_from_trace(trace)` scans a request's trace for the
most recent informative events (failing http_calls, intent
validation failures) and renders them into a short Korean + English
hint. When `entry main` returns an error, the server appends this
hint to the 500 response body so the browser user sees:

```
오류: No news available and fetch failed

— diagnosis / 진단 ————————————
HTTP 401 on GET https://newsapi.org/...?apiKey=demo —
인증 실패 (API 키가 잘못되었거나 없음) / authentication failed …
프로그램이 고정된 'demo' 같은 가짜 키를 쓰고 있는지 확인.
  response body (preview): {"status":"error","code":"apiKeyInvalid",...

다음 액션: `ail chat <project> "..."` 로 문제를 설명하고
다른 방법으로 바꿔달라고 요청하세요.
```

Instead of a dead end, the user sees what failed, why, and the
exact next command to fix it.

### Added — `_http_reason_hint(status)`

Human-readable (Korean + English) hints for common HTTP failure
modes: 401/403 (auth, with a specific warning about hardcoded
`demo` placeholders), 404 (endpoint not found), 429 (rate-limit),
4xx (client error), 5xx (upstream server error).

### Authoring prompt — NO FAKE API KEYS rule

The authoring prompt now explicitly bans hardcoded placeholder
credentials:

- `apiKey=demo`, `api_key=test`, `Bearer YOUR_API_KEY_HERE`, literal
  `demo` / `sample` as auth values — all rejected.
- Preferred no-auth sources listed: Google News RSS, Wikipedia REST,
  httpbin, CoinGecko / OpenWeatherMap public tiers.
- If the task genuinely needs an authenticated API the user has not
  set up, the author must write a clear-error `pure fn` explaining
  which env var should hold the key — not ship a placeholder.

### Also surfaces intent-validation failures

The same diagnostic path surfaces v1.10.0's
`intent_validation_failed` trace events — if the reason the program
errored is that an intent kept returning mis-typed shapes and got
floored to confidence 0, the user sees that too instead of a silent
null result.

### Tests

+11 tests in `test_agentic_server.py` covering the reason-hint
matrix (200/401/403/404/429/4xx/5xx), `_diagnose_from_trace` on
empty / 401 / intent-validation / network-error / too-many-hints.
455 passing total (+11 from 444).

---

## v1.10.0 — 2026-04-23

**Closes a HEAAL harness gap.** Before v1.10, an intent declared
`-> Text` was enforced only in syntax: whatever the model returned
got piped through as a "Text" value — including nested records,
code-fenced JSON envelopes, and raw fetched content the model had
stuffed into a string. hyun06000's Korean news-dashboard hit this
directly, getting a `{"overall_summary": ..., "news_cards": [...raw
RSS XML...]}` blob rendered as a response body.

HEAAL's claim is that AIL's grammar constrains what flows through a
program. Leaving the intent boundary unvalidated was a hole in that
claim. This release closes it for scalars and flat lists.

### Added — intent-return validation

New module `ail/runtime/intent_validation.py`:

- `strip_code_fence(text)` — removes an outer ```` ```lang\n...\n``` ````
  wrapper.
- `validate_and_coerce(value, return_type)` — returns
  `(coerced_value, error_or_None)` for `Text`, `Number`, `Boolean`,
  and `[T]` (where T is one of those). Composite types (`Result[T]`,
  records) are pass-through in this release.

Validation rules:

| Declared type | What gets rejected |
|---|---|
| `Text` | dict / list / JSON-envelope strings |
| `Number` | non-numeric strings, booleans (via `bool is int`) |
| `Boolean` | anything outside `true/false/yes/no/1/0` |
| `[T]` | non-lists; element coercion recurses |

### Added — retry on mismatch

`_invoke_intent` now wraps the adapter call in
`_invoke_with_validation`, which:

1. Invokes the adapter as before.
2. Runs `validate_and_coerce` on the response.
3. On mismatch, retries **once** with the rejection reason appended
   to the intent's constraints (so the retry is strictly stricter,
   not looser).
4. If the retry also fails, returns the raw value at
   `confidence=0.0` — downstream `attempt` / confidence guards route
   around it instead of crashing the program.

### Trace events

New events recorded to the ledger:

- `intent_validation_retry` — first attempt failed; retrying
- `intent_validation_failed` — retries exhausted; confidence floored

### Spec + reference card

`spec/08-reference-card.ai.md` and the bundled copy describe the
harness. Authors writing intents now have an explicit contract for
what a declared return type means at runtime.

### Tests

New `test_intent_validation.py` with 30 tests covering:

- Code-fence stripping (language tag, no tag, non-string, nested).
- Text / Number / Boolean / [T] coercion matrix.
- Unknown and `None` return types pass through.
- Executor integration: retry recovers from a first-turn misshapen
  response.
- Executor integration: persistent misshapen response floors
  confidence to 0 with raw value surfaced.

444 passing total (+30 from 414).

### Not changed

Composite types (`Result[T]`, records) are pass-through. They are
the next design iteration — validation requires deciding how to
prompt for structured shapes explicitly.

---

## v1.9.13 — 2026-04-23

**Architectural correction.** v1.9.10 made the agentic server detect
HTML strings returned from `entry main` and serve them with
`Content-Type: text/html`. Field testing with a Korean news-dashboard
project showed this pattern was wrong: it pushed HTML templating
into AIL code, encouraged LLM authors to emit `{"key": "value"}`
record dumps as the response, and mixed computation with presentation.

AIL is AIL. HTML is a separate file.

### Removed

- `_looks_like_html()` in `server.py`.
- HTML Content-Type branch in POST /.
- `innerHTML` / `.result.html` rendering in the default textarea UI.
- The HTML-in-entry guidance paragraph in the authoring prompt.

### Added — `view.html` file-based dashboards

If a project has a `view.html` file next to `app.ail`, the agentic
server serves it verbatim on GET /. The file's own JS is expected to
`fetch('/', {method:'POST'})` for data from `entry main`.

```
news-ticker/
├── INTENT.md
├── app.ail            # entry returns structured data
└── view.html          # served on GET /; fetches POST / for data
```

Projects without a `view.html` still get the built-in textarea UI
(unchanged).

### Added — JSON pretty-print for record / list returns

`_render_value()` now detects dict and list returns and serializes
them via `json.dumps(indent=2, ensure_ascii=False)` instead of
Python's `str()` which produces unreadable `{'key': 'value'}` repr
syntax. Unicode (Korean, etc.) stays readable.

`Result[T]` wrappers recurse into the inner value so
`ok({"n": 7})` prints as valid JSON rather than Python repr.

### Rewrote `news-ticker` example

- `app.ail` now returns a structured record via state (no HTML
  inline).
- `view.html` is the dashboard; its JS fetches POST / for data and
  auto-refreshes every 10 seconds.

### Authoring prompt updates

Teaches the author model the revised rules:

- `entry main` returns data (Text / Number / list / Record / Result),
  not HTML markup.
- If the project has `view.html`, the server uses that file; AIL
  keeps its hands off HTML.
- Never include raw fetched content (RSS XML, HTTP response bodies,
  full upstream JSON) in the output — summarize and return only what
  the caller needs.

### Tests

- Removed the HTML-detection tests (feature gone).
- Added `view.html` file-serving + default-fallback tests.
- Added JSON pretty-print tests (dict, list, nested Result, Unicode,
  non-serializable fallback).
- 414 passing total.

---

## v1.9.12 — 2026-04-23

**Last of the six L2 v2 primitives surfaced by the 2026-04-23
news-dashboard case study: `perform schedule.every(N)`.** Closes
Gap #3 — a dashboard declared "refresh every 30 seconds" but had
no way to express that. L2 v2 is now complete at 6/6.

### Added — `perform schedule.every(seconds: Number) -> Result[Boolean]`

Called from inside `entry main`. Registers "re-invoke this entry
every N seconds"; the agentic runtime runs the recurring invocation
in a background thread.

```ail
entry main(input: Text) {
    perform schedule.every(30)              // register the cadence
    // … fetch, compute, perform state.write(...) to persist …
    return summary
}
```

Each tick re-runs `entry main("")`, records the outcome to the
ledger as `event: "schedule_tick"`, and continues on failure. Entry
can persist tick results via `perform state.write(...)` so GET /
reads the freshest value.

### Semantics

- Seconds must be in `(0, 86400]`. Zero/negative/over-a-day → clean
  `Result-error`, not a crash.
- Latest call wins. Re-invoking `schedule.every(N)` just updates
  the cadence; the scheduler picks up the new value on its next
  ~0.5s poll.
- Outside `ail up` (no `AIL_SCHEDULE_FILE` env var) the effect
  returns `error("no scheduler running …")` — an `ail run` of the
  same program gets a clean error, not a silent no-op.
- Scheduler thread swallows per-tick exceptions. A flaky upstream
  doesn't stop the cadence.

### Implementation

- New `ail/agentic/scheduler.py` — `Scheduler` class, one thread per
  project, polls the schedule file every 0.5s for cadence updates.
- `serve_project` starts the scheduler unconditionally; idles cheaply
  when no schedule is armed.
- Logger gets `schedule_armed(seconds)` in English + Korean for the
  friendly UI.
- Added `schedule.every` to the authoring prompt so `ail ask` knows
  when to reach for it ("every N seconds", "refresh every …",
  "poll", "update periodically").

### New example: `examples/agentic/news-ticker/`

Three L2 v2 primitives composing in one dashboard: schedule.every
(cadence) + state.write (persistence) + HTML output mode (inline
rendering). A counter that ticks every 10 seconds in the background.

### Tests

- +11 tests in new `test_schedule_effect.py` — effect-level (write
  the file, validate args, latest wins) and scheduler-level (fires
  at cadence, stops cleanly, swallows exceptions, ignores malformed
  files, picks up cadence changes). 412 passing total.

### L2 v2 complete

All six primitives from the 2026-04-23 news-dashboard case study
have shipped: clock.now, http.get steering, state.*, input-aware
UI, HTML output mode, schedule.every. Ready to roll v1.9.9–v1.9.12
to PyPI.

---

## v1.9.11 — 2026-04-23

Trace transparency: `ail ask --show-source` now prints
`author=provider/model-id` instead of just `author=provider`, so a
user can verify their environment variables actually routed to the
model they expected.

### Before

```
--- confidence=1.000 retries=0 author=anthropic ---
```

### After

```
--- confidence=1.000 retries=0 author=anthropic/claude-sonnet-4-5-20250929 ---
--- confidence=1.000 retries=0 author=ollama/ail-coder:7b-v3 ---
--- confidence=1.000 retries=0 author=openai_compat/qwen2.5-coder:7b ---
```

`_adapter_name()` now reads both `name` (provider) and `model`
attributes from the adapter and joins them with `/`. Falls back to
provider-only for adapters without a model (MockAdapter), or the
class name as last resort.

### Tests

- +2 tests in `test_authoring.py`: combined-label case and class-name
  fallback. 401 passing total.

---

## v1.9.10 — 2026-04-23

Fifth of the six L2 v2 primitives: **HTML output mode**. An `entry`
that returns a string starting with `<!doctype`, `<html`, or a bare
tag like `<div>` is now served with `Content-Type: text/html` and
rendered by the browser UI via `innerHTML` instead of escaped as
plain text. This unlocks dashboard-style projects where the AI
writes the page markup directly.

### Added

- `_looks_like_html(value)` in `server.py` — precise detection (opens
  with `<!doctype`, `<html`, or `<word`; rules out `<3`, JSON, numbers,
  non-strings).
- Server POST path: HTML responses go out byte-exact (no trailing
  newline) with `Content-Type: text/html`; plain text keeps the
  terminal-friendly `\n`.
- Browser UI: result area switches to `innerHTML` when the response
  is HTML, with a `.result.html` CSS rule that strips the monospace
  / pre-wrap styling.
- Ledger records `output_mode: "html" | "text"` on every request.

### Not added (deliberately)

- No auto-invoke on GET /. The user still presses Run/Send once to
  trigger the render. Avoids running LLM-heavy programs on every
  page load.
- No sanitization on the HTML output. Same trust boundary as `ail run`
  — the author is an LLM the user chose to host locally.

### Tests

- +11 tests in new `test_agentic_server.py` (HTML detection edge
  cases, POST returning HTML vs text with correct content types) +1
  in `test_agentic_web_ui.py` (CSS + JS glue). 399 passing total
  (+11 from 388).

### Remaining L2 v2

1 primitive open: **scheduler effect** (`perform schedule.every(...)`)
— the biggest of the three. Closes the news-dashboard "refresh every
30s" requirement.

---

## v1.9.9 — 2026-04-23

Fourth of the six L2 v2 primitives surfaced by the 2026-04-23
news-dashboard case study: **input-aware UI**. Closes Gap #6 —
a user opening a service whose `entry` ignores its input was still
shown a textarea, typed "안녕", and got back an unrelated pre-computed
summary. The page now reflects what the program actually does.

### Added — `entry_uses_input()` + input-aware `render_page`

`ail.agentic.web_ui.entry_uses_input(source)` parses `app.ail`, locates
its `entry` declaration, and walks the body looking for any reference
to the first parameter's name. Hits every dataclass field in the AST,
so future node types don't silently escape the check.

`render_page(..., input_used=...)` now renders either:

- a textarea + **Send** button (input_used=True, default), or
- a short "this service takes no input" note + **Run** button
  (input_used=False).

The server resolves `input_used` from `app.ail` on every GET /, so
hot-swapping `INTENT.md` between "input-driven" and "input-free"
programs takes effect on the next page load — no restart.

Korean UI strings added: `실행` (Run), `이 서비스는 입력이 필요 없습니다.
실행 버튼을 누르세요.` (no-input hint).

### Behavior

- Detection defaults to `True` on parse failure or empty source —
  safer to show a harmless textarea than to hide input from a program
  that needs it.
- Renamed parameters honored (`entry main(payload: Text)` works).
- `entry main()` with no params renders as input_used=False.
- POST / with any body still works for input-free services; the
  runtime just doesn't reference the param.

### Verified

| Example | `entry_uses_input` | UI |
|---|---|---|
| `visit-counter` | False | Run button, no textarea |
| `word-counter` | True | Textarea + Send |
| `csv-stats` | True | Textarea + Send |
| `sentiment` | True | Textarea + Send |

### Tests

- +9 tests in `test_agentic_web_ui.py`: detection across 5 AST shapes
  (input used, ignored, parse error, empty, renamed param, no params)
  plus 3 `render_page` rendering assertions (textarea hidden, textarea
  shown, Korean no-input hint).
- Suite: 388 passing (+9 from 379).

### Remaining L2 v2

5/6 primitives still open: HTML output mode, scheduler effect.
Tracked in [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md)
and [`docs/case-studies/2026-04-23_news-dashboard.md`](docs/case-studies/2026-04-23_news-dashboard.md).

---

## v1.9.8 — 2026-04-23

Third of the six L2 v2 primitives surfaced by the 2026-04-23
news-dashboard case study: **persistent cross-request state**. This
closes Gap #4 — "each request recomputed everything from scratch"
— and gives agentic projects a place to accumulate counts, store
last-seen values, keep a running history, and implement
retry / backoff state that survives process restart.

### Added — `perform state.read/write/has/delete`

Four new effects, all backed by per-key JSON files under
`.ail/state/keyval/`:

- `perform state.read(key: Text) -> Result[Any]` — returns the
  stored value or `error("... not set")` if missing.
- `perform state.write(key: Text, value: Any) -> Result[Boolean]` —
  atomic write via temp-file + rename. Value must JSON-serialize
  (Text, Number, Boolean, or list of those — the common case).
- `perform state.has(key: Text) -> Boolean` — cheap existence check.
- `perform state.delete(key: Text) -> Result[Boolean]` — ok(true)
  if removed, ok(false) if not present.

Keys are restricted to `[A-Za-z0-9_\-.]+`, so path-traversal-style
inputs like `"../../etc/passwd"` get rejected with a clean
`Result` error rather than escaping the state directory.

### Runtime wiring

- **Agentic server / bring_up now set `AIL_STATE_DIR`** to the
  project's `.ail/state/keyval/` before tests run. Declared test
  cases see the same persistent state the running service will,
  so behaviors depending on state can be validated pre-serve.
  Outside an agentic project the env var is unset and every state
  effect returns an explanatory error rather than silently
  succeeding into a temp dir.
- **Tests share state with the service.** Running `ail up` against
  a visit-counter INTENT.md declaring two successful test cases
  means the counter is at `2` when the first real HTTP request
  comes in. Users who want test isolation can explicitly clear
  state or set `AIL_STATE_DIR` to a throwaway path.

### Authoring prompt

- **New PERSISTING STATE ACROSS REQUESTS section** in the default
  authoring goal. Names the trigger words ("remember", "count",
  "keep track of", "last", "history", "accumulate") and spells out
  the default-if-missing pattern: `r = perform state.read("k"); n = 0;
  if is_ok(r) { n = unwrap(r) }`.
- **New few-shot example** pinning the state.read + state.write
  round trip for visit-counter-style prompts.

### New example project

- `reference-impl/examples/agentic/visit-counter/` — a 10-line
  agentic program that counts its own visits. Committed with a
  pre-authored `app.ail` so the example runs without an LLM
  key. Listed in the examples README as the state demo.

### Reference card

- `spec/08-reference-card.ai.md` and the bundled copy updated with
  the four state signatures and a paragraph on the key whitelist
  and `.ail/state/keyval/` layout.

### Tests

- 341 tests pass (was 331 in v1.9.7). New: 10 state-effect tests
  covering the full round trip, cross-invocation persistence, the
  missing-key error path, path-traversal rejection, atomic-write
  leaves no `.tmp` leftover, list+number serialization, purity
  rejection inside `pure fn`, and the no-state-dir case.

### Live verification

Launched the visit-counter example locally; POST `/` returned
`visit #3`, `#4`, `#5` across three consecutive requests, and the
on-disk `visits.json` ended at `5`. State survives Ctrl-C + restart
because the file layout outlasts the process.

### Remaining L2 v2 work

Three of the six case-study gaps still open:

  - `perform schedule.every(...)` for background polling (Gap 3)
  - HTML / layout output mode (Gap 5)
  - Input-aware UI rendering (Gap 6)

---

## v1.9.7 — 2026-04-23

Two fixes from hyun06000's `usd-now` test on v1.9.6. The headline:
v1.9.5's two L2 v2 primitives (`perform clock.now()` + the
http.get authoring nudge) **both verified** in production —
Sonnet wrote `perform http.get("https://api.exchangerate-api.com/...")`
and `perform clock.now()` exactly as steered, no fabrication, no
hardcoded timestamp. v1.9.7 closes the two adjacent issues that
emerged.

### Fixed — `chat_apply` (and therefore `--auto-fix`) crashed every time

- `ail/agentic/chat.py::_chat_examples()` returned dicts where the
  AnthropicAdapter (and others) iterate examples as `(input, output)`
  tuples. Every chat call therefore raised
  `ValueError: too many values to unpack (expected 2)` inside the
  adapter. `--auto-fix N` showed it via the friendly logger
  ("AI가 수정안을 내놓지 못했어요: ValueError: ..."), and `ail chat`
  on a real project would crash the same way.
- Same shape mismatch was fixed in `diagnosis.py` at v1.9.2; the
  parallel hole in `chat.py` survived because no path exercised
  it until hyun06000 hit `--auto-fix 2`.
- Added a regression test that asserts the example contract
  matches what the adapter expects (mirror of the diagnosis
  contract test from v1.9.2).

### Improved — authoring prompt: signal errors via Result, not strings

- In hyun06000's `usd-now` Sonnet wrote
  `if is_error(usd_result) { return unwrap_error(usd_result) }`
  for the empty-input and "abc" test cases. The function returns
  a Korean error string, which is fine UX in a browser — but the
  agentic test runner inspects the return shape (Result error vs
  plain Text) to decide whether the run "errored" or "succeeded".
  A returned string looks like success.
- New section in the default authoring goal: SIGNALING ERROR FROM
  entry main. The rule is "return the Result error directly, NOT
  `unwrap_error(...)`". Same for success — prefer `ok(value)` so
  the server / test runner can introspect uniformly. The HTTP
  layer already unwraps Result for end-user display, so users
  still see the same error text.

### Tests

- 331 tests pass (was 330). +1 chat-examples contract test.

### Verified by this release

- v1.9.5 fix #1 (`perform http.get`): ✅ Sonnet picked the effect
  on the real exchangerate-api URL with no `intent fetch_*`
  delegation.
- v1.9.5 fix #2 (`perform clock.now()`): ✅ Sonnet used the new
  primitive instead of the `"2024-01-15"`-style hardcoded literal
  the news-dashboard case study showed.
- v1.9.6 i18n (FriendlyLogger Korean): ✅ Whole session in Korean
  on a Korean INTENT.md, including the new auto-fix lines.

---

## v1.9.6 — 2026-04-23

Whole-session Korean localization for the FriendlyLogger. Until
v1.9.5 only the authoring-failure path localized; every other log
line ("Reading INTENT.md", "Running tests", "Tests didn't pass —
not starting the service", "Service is live", ...) stayed English
even when INTENT.md was Korean. That's half-translated output —
worse than a fully English interface for the audience we target.

Surfaced by hyun06000: on a Korean `usd-now` project, the
authoring-failure path showed Korean diagnosis but the test
summary and the abort sentence were in English.

### Changed

- **`FriendlyLogger` is now fully bilingual (Korean / English).**
  A `_STRINGS` table maps every log-line key to both languages.
  The logger instance takes a `language` hint on construction.
- **`bring_up` detects language from INTENT.md once at entry** and
  passes it through to `make_logger`. Korean INTENT → whole
  session in Korean: project header, reading-intent line, author
  start / done, test results ("성공 기대 → 성공", "에러 기대 → 에러"),
  summary ("4개 중 2개 통과 — 2개 아직 실패"), the tests-aborted
  block, watcher warnings, serving banner, port-collision error,
  auto-fix progress lines, shutdown.
- **Pluralization handled.** English pluralizes via `{s}` suffix
  resolved from the count argument; Korean uses the same phrase
  for singular and plural (linguistically correct).

### Compatibility

- `CompactLogger` stays language-neutral (it exists for scripts
  and CI that grep for `[PASS]`/`[FAIL]` markers). Unchanged.
- `--log compact` output is unchanged.
- `make_logger(style)` still works with one argument; the new
  `language` keyword is optional and defaults to English.

### Tests

- Still 330 tests. No new test file — each log string's layout is
  already indirectly covered by the agent end-to-end tests; the
  i18n change is a per-call lookup with defensive fallback to the
  English table for any missing Korean key.

---

## v1.9.5 — 2026-04-23

First two of the six L2 v2 primitives surfaced by the 2026-04-23
news-dashboard case study (see
`docs/case-studies/2026-04-23_news-dashboard.md`). Both are
small-footprint and land together.

### Added — `perform clock.now()` effect

- **`perform clock.now() -> Text`** — ISO-8601 UTC by default
  (`"2026-04-23T15:02:34Z"`). `perform clock.now("unix")` returns
  seconds-since-epoch as Text. Every returned value carries an
  effect-origin node, so `has_effect_origin(t)` is true and
  provenance can distinguish a real timestamp from a hardcoded
  literal.
- Rejected by `pure fn` at parse time (structural purity preserved).
- Rationale: the case study showed Sonnet generating
  `current_time = "2024-01-15 14:30:00 KST"` as a hardcoded literal
  because AIL had no clock primitive to call. An unchanging
  timestamp in a live service is always wrong. This closes the gap.

### Changed — authoring prompt steers fetches to effects, not intents

- **`FETCHING EXTERNAL DATA` section added to the default authoring
  goal.** Explicit rule: "if the task needs web data / files /
  current time, use `perform http.get` / `perform file.read` /
  `perform clock.now` — NOT an `intent`." The case study showed
  models delegate "search the web for X" to `intent search_news(...)`
  which then hallucinates news the LLM doesn't have. The new
  section names the failure mode and prescribes the fix.
- **Two new few-shot examples in `_authoring_examples()`:**
  (1) `perform http.get` pattern paired with an `intent` for
  interpretation — pins the "fetch via effect, interpret via
  intent" shape.
  (2) `perform clock.now()` pattern for prompts that mention
  "current time" or "now".
- Behavior change is prompt-only; the grammar is unchanged.

### Fixed

- Documentation drift: added `clock.now` to `reference_card.md` and
  `spec/08-reference-card.ai.md` alongside the other effect
  signatures.

### Tests

- 330 tests pass (was 325 in v1.9.4). New: 5 clock tests covering
  default ISO-8601 shape, explicit `"iso"` arg, `"unix"` arg,
  effect-origin carriage, and the purity-rejection contract when
  `perform clock.now` appears inside a `pure fn` body.

### Not yet — still open L2 v2 items

Four of the six case-study gaps remain. Next candidates:

  - `perform schedule.every(...)` for background polling (Gap 3)
  - Cross-request state effect on `.ail/state/` (Gap 4)
  - HTML / layout output mode (Gap 5)
  - Input-aware UI rendering (Gap 6)

---

## v1.9.4 — 2026-04-23

Closes two gaps in the non-developer experience. Surfaced by
hyun06000 after running a Korean project end-to-end and finding
curl unusable as the "send a request" interface. Also: the
file-watch auto-reload story was hidden in one log line; most
users would never discover it.

### Added — browser UI

- **`GET /` now returns an HTML page.** Single-page form: a
  textarea, a Send button, a result area, and the project's
  description pulled from INTENT.md's preamble. No framework, no
  npm, no build step — stdlib HTTPServer serves the HTML inline.
- **Localized to Korean or English** by detecting Hangul syllables
  in the project preamble. Labels ("보내기" / "Send", "결과" / "Result",
  the auto-reload tip) switch accordingly.
- **`POST /` behavior unchanged** — the existing curl / script path
  still works. Browsers submit the form via fetch() to the same
  endpoint; machines and humans share the URL.
- **Ctrl-Enter in the textarea submits.** Small but matters for
  keyboard users.
- **Content-Security-aware rendering.** User-controlled text
  (project name, preamble) is `html.escape()`d before landing in
  the DOM. Unit test covers the script-injection case.

### Changed — auto-reload is now loud

- **`Service is live` block rewritten.** Previously one line told
  the user the URL and Ctrl-C. Now three short paragraphs: (1)
  the URL, with an explicit "open it in a browser, there's a text
  box waiting"; (2) "Edit INTENT.md and save — the service updates
  itself. No restart. The tab you just opened keeps working."
  (3) "Ctrl-C here to stop."
- **README + docs/ko/README.ko.md updated** to match. The old
  `curl -X POST ...` block in the walkthrough is replaced with
  "open that URL in a browser" as the primary path; the curl form
  is mentioned one paragraph down for scripts.

### Tests

- 325 tests pass (was 318 in v1.9.3). New: 7 web-UI tests —
  render-page localization for both languages, HTML-escape
  safety, preamble extraction, and an end-to-end HTTP test that
  launches the real stdlib server and asserts `GET /` returns
  HTML with the expected content.

### Why this matters

v1.9.0–1.9.3 delivered the non-developer loop
("`ail init` → edit INTENT.md → `ail up`") but stopped at the
moment the service came up. If `curl` is the only way to talk to
the service, the audience we built this for has no way in. A
browser form costs a few hundred lines of stdlib-only Python and
closes that gap.

---

## v1.9.3 — 2026-04-23

Failed authoring attempts are now persisted to disk. Previously the
ledger only recorded the parse error; the actual AIL source the
model produced was thrown away. That meant a developer (or a future
meta-author AI built on top of these projects) had no artefact to
inspect or learn from when the model converged on the same wrong
shape repeatedly.

Surfaced by hyun06000: "정확한 에러 리포트를 얻거나 프로그램을 할 수
있는 사용자 혹은 메타 저자 AI 등이 이 문제를 해결하려면 세션의
저자 AI가 만든 코드나 결과물을 (실패한 거라도) 어딘가엔 기록해
둬야 할 거야."

### Added

- **`.ail/attempts/<UTC-timestamp>_author_failed.ail`** — written
  whenever the author exhausts its retry budget. The file is plain
  AIL source (not parseable, by definition) headed by a `//` comment
  block recording the timestamp, the author model, and one line per
  retry's parse error. The body is the LAST attempt verbatim, so
  someone — human or LLM — can pick up the artefact and see what
  shape the model is converging on.
- **`Project.save_failed_attempt()`** — public helper, also
  available to the chat / auto-fix paths in future versions.
- **`Project.attempts_dir`** — `attempts/` subdir of `.ail/`,
  created on demand. `.ail/` is gitignored so attempts never
  accidentally land in user's git history.
- **Ledger entry `attempt_saved`** — `{path, kind, source_chars}`
  references the file. The existing `author_failed_diagnose_attempt`
  entry now also carries `attempt_file`.
- **UI surfaces the attempt path.** Friendly mode prints a localized
  "AI's last attempt (failed)" line; compact mode prints `attempt:
  <path>`. Both pointing to the saved `.ail` file.

### Tests

- 318 tests pass (was 316 in v1.9.2). New: 2 attempts-save tests
  (file shape, on-demand directory creation).

### Why this matters

This is the foundation for two things L2 v2 will need:

  1. A meta-author AI that learns from failures by reading the
     attempts corpus instead of just retrying blindly.
  2. A debugging story for developers who do read AIL — they can
     grep the saved files for the patterns the author tends to
     get wrong.

For now it is just an artefact dump, but the artefacts are no longer
lost.

---

## v1.9.2 — 2026-04-23

Hot-fix on top of v1.9.1. The diagnose-on-failure feature shipped
yesterday crashed silently inside every adapter — the few-shot
examples were dicts where the existing adapter API expects
`(inputs_list, output)` tuples, raising `ValueError: too many values
to unpack` and falling back to the English static tip list every
time. So end users never actually saw the AI-translated explanation
the v1.9.1 release notes promised.

Caught by hyun06000's first real-world test: a Korean-language
project repeatedly hit the fallback path, which is also too
technical for a non-developer.

### Fixed

- **`diagnose_authoring_failure` examples shape.** Now matches the
  `(inputs_list, output)` tuple form the AnthropicAdapter (and the
  others) iterates over with `for inp, out in examples[:5]`. The
  v1.9.1 dict shape silently broke every diagnose call. Regression
  test added that asserts the example shape against what the
  adapter requires.

### Improved (also driven by the same test)

- **Static fallback is multilingual.** When the diagnose LLM call
  itself can't run (no API key, network down), the fallback message
  is now picked by detecting Hangul syllables in the user's
  INTENT.md. Korean projects get Korean fallback text. The new text
  drops command-line snippets (`ANTHROPIC_API_KEY`, `--auto-fix 2`)
  in favor of plain advice — the audience is a non-developer who
  doesn't know what an env var is.
- **Header strings localized.** "Could not build the program" /
  "Full log" headers now also localize to Korean when INTENT.md is
  in Korean.

### Tests

- 316 tests pass (was 314 in v1.9.1). New: 1 examples-shape
  contract test, 1 language-detection test.

---

## v1.9.1 — 2026-04-23

UX patch release. Surfaced by hyun06000's first-time use of v1.9.0 on
a real Korean-language project. Targets the audience the agentic
layer was designed for: people who know natural-language prompting
but no code.

No grammar changes; v1.8 spec freeze still in effect.

### End-user-friendly logging (default)

- **`ail up` output redesigned.** Sentences with breathing room, ✓/✗
  marks for tests, the author model identified by name on every run.
  The original v1.9.0 dev-style one-liners are still available with
  `ail up --log compact` for scripts and CI.
- **Author model now identified.** Previously the user had no way to
  tell which backend (`anthropic/claude-sonnet-4-5`, `ollama/ail-coder:7b-v3`,
  `openai_compat/...`) actually wrote `app.ail`. The friendly view
  now prints it on the authoring line and the ledger records it
  on every `author_start` event.

### Authoring failure becomes a plain-language conversation

- **Diagnose-on-failure.** When the author exhausts its retry budget,
  the agent now calls the same backend ONE more time with a
  different goal: "explain in plain language what made this hard
  and suggest one specific edit to INTENT.md". The reply is
  produced in the same natural language the user wrote INTENT.md in
  (Korean → Korean, English → English) and printed instead of the
  raw `ParseError: unexpected token COLON(':')@6:42` that v1.9.0
  showed.
- The diagnose prompt forbids code-level vocabulary (`syntax`,
  `colon`, `token`, `intent`, `pure fn`, `compile`, …) and frames
  the difficulty as a limit of what could be automated, not a
  user mistake.
- If the diagnose call itself fails (no API key, network down),
  falls back to a concise static tip list. Raw errors still go to
  `.ail/ledger.jsonl`.
- Module: [`reference-impl/ail/agentic/diagnosis.py`](reference-impl/ail/agentic/diagnosis.py).

### `ail init` UX

- **Both invocation paths shown.** `ail init foo` previously suggested
  only `ail up foo` as the next step; from inside the new project
  folder that command became `ail up foo/foo` and failed with a
  confusing "no INTENT.md" message. Now prints both forms:

  ```
    then:  ail up foo           (from here)
       or: cd foo && ail up     (from inside the project)
  ```

### INTENT.md parser tolerance

- **ASCII arrows accepted in test bullets.** Previously only the
  Unicode `→` separated input from expected outcome; bullets using
  `->` or `=>` were silently dropped (they appeared in the file but
  never ran). Now all three forms work; tests using `-> 에러` or
  `=> succeed` are recognized.

### Recorded design principle

> Errors that come from AI-generated code should be translated by AI
> into the user's language. Tokenizer / parser / runtime vocabulary
> should never reach a non-developer.

Captured in the diagnosis module docstring; intended to inform
future error-rendering work across the agentic layer.

### Tests

- 314 tests pass (was 308 in v1.9.0). New: 6 diagnosis, 1 arrow
  fallback. Existing tests unmodified — the friendly logger is
  routed through a `Logger` abstraction, ledger format is
  unchanged, all assertions still hold.

---

## v1.9.0 — 2026-04-22

First minor bump since v1.8.0 — adds the L2 layer of the HEAAL
paradigm. AIL is no longer a one-shot CLI calculator; an "AIL
project" is now a folder that an in-project AI agent owns. Two
commands cover the non-developer path: `ail init <name>` and
`ail up`. Everything else falls back to file editing the agent does
or the user does, both updated by the watch loop or by `ail chat`.

No grammar changes; v1.8 spec freeze still in effect.

### Agentic projects (L2 v0)

- **`ail init <name>`** — scaffolds a project folder with an
  `INTENT.md` template (the only file the human edits) and an
  empty `.ail/state/` directory plus an append-only ledger.
- **`ail up [path]`** — reads INTENT.md, authors `app.ail` via the
  existing `ask()` pipeline if empty, runs the test cases declared
  under `## Tests`, then serves over HTTP. POST `/` runs
  `entry main(input)` with the request body; GET `/healthz` returns
  200. Port collision fails loudly. Test extraction handles English
  (`## Tests`) and Korean (`## 테스트`) headers; quoted test inputs
  interpret `\n` `\t` `\r` escapes.
- **`.ail/ledger.jsonl`** — append-only record of every authoring
  attempt, test run, request, watcher event, chat edit, and
  auto-fix attempt. The L3-OS substrate begins here.
- **Three example projects** under
  `reference-impl/examples/agentic/`:
  `word-counter/` (pure fn, headline demo), `csv-stats/` (pure-fn
  pipeline with Result threading), `sentiment/` (fn + intent split,
  needs an authoring backend). Each ships with a pre-authored
  `app.ail` so the example runs without paying for an LLM call.

### Agentic projects (L2 v1)

- **File watcher + auto reload** — `ail up` polls INTENT.md and
  app.ail in a daemon thread. Editor saves picked up in ~1s without
  restarting the HTTP server. The handler reads app.ail fresh on
  every request, so the swap is automatic; the watcher's job is to
  re-run declared tests and warn (not abort) on failure. Opt out
  with `ail up --no-watch`.
- **`ail chat <path> "<request>"`** — natural-language project
  edits. The author backend gets the current INTENT.md + current
  app.ail + the user's request and returns updated whole-file
  replacements for either or both, plus a one-sentence summary.
  The agent saves the change and re-runs the declared tests.
- **`ail up --auto-fix N`** — when declared tests fail, hand the
  failures to the chat backend and retry up to N times before
  aborting. Stops early if the model declines to change anything.
  Default off (LLM cost is opt-in).

### HTTP server polish

- Result-shaped return values are unwrapped for HTTP clients
  (success → inner value, error → message + HTTP 500). Agentic
  programs that want to signal error use the idiomatic AIL pattern
  (`return error(...)`) instead of returning sentinel strings.

### Tests

- 307 tests pass (was 269 before v1.9.0 work began). New: 18
  agentic core, 5 watcher, 7 chat, 7 auto-fix.

### Documentation

- README + `docs/ko/README.ko.md` add a "From a one-shot answer to a
  running service" section walking through `ail init` → edit
  INTENT.md → `ail up` with real command output and curl examples.
- `runtime/01-agentic-projects.md` is the design doc this work
  implements; §6 v1 checklist is now ✅ for all three items
  (file watch, chat, auto-fix).

---

## v1.8.7 — 2026-04-22

Methodology correction + new boundary data. No grammar changes; spec
freeze still in effect. The headline is honesty: a vacuous-truth bug
in the HEAAL Score formula was caught and fixed before any of the
inflated numbers went into a manifesto or a public talk. Some
previously published scores moved (the AIL column unchanged in every
row; the Python column rose by 1–10 points in three rows). The
corrected scoring also lets us publish the mistral7b row, which
identifies the empirical boundary of the grammar-floor claim.

### Tooling correction

- **`reference-impl/tools/heaal_score.py`** — per-program metrics
  (Error Explicitness, Structural Safety, Loop Safety, Observability)
  now use the **parsed** count as their denominator, not **N**.
  Previously, when parse rate was 0, those rates defaulted to 100%
  — a model that authored zero programs scored higher on safety
  than a model that authored a few buggy ones. Vacuous truth.
  Parse Success and Answer Correctness keep N as denominator since
  they measure authoring-success-per-attempt.

  The variable named `exec_success` was actually computed from
  `answer_ok` (correct final answer). Relabeled the displayed metric
  to **"Answer Correctness"** so the displayed name matches what
  the code computes.

  Full audit including before/after table for every published
  score: [`docs/benchmarks/2026-04-22_score_audit.md`](docs/benchmarks/2026-04-22_score_audit.md).

### Documentation corrections

- **README.md, docs/why-ail.md, docs/heaal.md (+ ko/, ai.md mirrors)** —
  the "Python omits error handling 42–86%" claim was based on the
  old methodology. Corrected range under per-parsed denominator:
  **12–70%** depending on author model, with a sharper observation
  that *stronger models often omit more* (they attempt more ambitious
  code with more failable calls and skip wrapping more of them). The
  AIL number stays 0% on every tier where AIL parses — measured
  constant across Anthropic, Alibaba, Meta, and a 7B fine-tune.
- The headline R3 fine-tune row corrected from 87.7 / 48.5 / +39.2
  to 87.7 / 58.0 / +29.7. Still well above Python; the gap shrank
  honestly because Python's per-parsed safety properties are higher
  than the old methodology credited.

### New benchmark data — HEAAL boundary fully anchored

- **Stage D (`llama3.1:8b-instruct`)** — confirms `anti_python` is a
  frontier-only intervention on a third model family (Meta after
  Anthropic Sonnet ✅ and Alibaba Qwen ✅). 45/50 AIL programs
  bit-identical across default and anti_python runs. HEAAL Score:
  AIL 74.3 vs Python 43.7 (+30.6) — the largest gap among parsed
  tiers, demonstrating the grammar floor matters most when the
  author model is weakest *but still produces parseable output*.
  Writeup: [`docs/benchmarks/2026-04-22_heaal_D_llama8b_analysis.md`](docs/benchmarks/2026-04-22_heaal_D_llama8b_analysis.md).
- **Stage D' (`mistral:7b-instruct`)** — identifies the boundary.
  The model authors zero parseable AIL across both runs; instead it
  emits Python wrapper code that imports the AIL interpreter and
  embeds AIL as a string parameter. Under the corrected methodology
  this honestly scores AIL 0.0 vs Python 54.9. The grammar floor
  cannot lift programs that don't exist. The remedy for tiers below
  the parse threshold is the AIL track (fine-tune the base, e.g.
  `ail-coder:7b-v3`). Writeup:
  [`docs/benchmarks/2026-04-22_heaal_D_mistral7b_analysis.md`](docs/benchmarks/2026-04-22_heaal_D_mistral7b_analysis.md).
- **Boundary summary** — [`docs/benchmarks/2026-04-22_heaal_boundary_summary.md`](docs/benchmarks/2026-04-22_heaal_boundary_summary.md)
  combines C+D+D'+E1 into a single cross-tier table with three
  regimes and three remedies (frontier → `anti_python`, mid/small
  with parse → grammar floor, below parse → fine-tune).

### Forward-looking

- **L2 design recorded.** [`runtime/01-agentic-projects.md`](runtime/01-agentic-projects.md)
  captures the 2026-04-22 design conversation about what an AIL
  "project" should look like once it's no longer a one-shot CLI:
  a folder with a single human-edited `INTENT.md` and an in-project
  AI agent that owns `app.ail`, tests, ledger, and evolve state.
  Two commands: `ail init`, `ail up`. No code yet — spec only,
  pending L1 closure (now done).

---

## v1.8.6 — 2026-04-22

Small additive release. Makes the AI-written AIL program persistable
from `ail ask`, and bundles the Stage C analysis that bounds when the
`anti_python` authoring variant helps.

### CLI

- **`ail ask --save-source PATH`** — writes the AIL source the author
  model produced to a file. The answer still goes to stdout; only
  the program is written. Pass `-` to emit the source to stdout
  after the answer instead of a file. Parent directories are
  created as needed; trailing newline is normalized.

  ```bash
  ail ask "Sum 1 to 100" --save-source sum.ail
  # 5050
  # --- AIL saved to sum.ail ---
  ail run sum.ail --input ""   # replay what the author wrote
  ```

  Six CLI unit tests covering file write, stdout `-`, parent-dir
  creation, newline normalization, and the partial-source path when
  `AuthoringError` is raised.

### Documentation

- **HEAAL Stage C analysis** — `docs/benchmarks/2026-04-22_heaal_C_qwen14b_analysis.md`
  plus two dashboards. Running the base `qwen2.5-coder:14b` with
  default vs `anti_python` prompts yields bit-identical AIL output
  across all 50 programs. The anti_python variant is a
  frontier-model intervention; at mid-tier coder bases it has no
  measurable effect at temperature 0. AIL's grammar-enforced floor
  still keeps the HEAAL Score at 80.9 vs Python 69.6 on this tier
  with zero prompt work.
- **`ail-mvp` install troubleshooting** — README now documents the
  clean-uninstall path for users hitting `ModuleNotFoundError: No
  module named 'ail_mvp'` from a pre-v1.8 stale editable install.
- **`--show-source` visibility** — Quick start has a concrete
  "Seeing the code the AI wrote" subsection with real output.
- **Why-AIL discoverability** — dedicated top-level section plus a
  Further Reading block linking the HEAAL manifesto, benchmarks,
  and dashboards from the README entry points.

### Internal

- CLAUDE.md trimmed from 1469 to 143 lines. Forward-looking only;
  session logs belong in git. Rule 5 reframed: CLAUDE.md is a NOW
  + NEXT snapshot, not a diary.

---

## v1.8.5 — 2026-04-22

Additive release within the v1.8 grammar freeze (spec §2.5 permits
builtin additions; §3 permits additive prompt variants). The headline
is the HEAAL demonstration: a frontier author model (Claude Sonnet)
writes AIL through `ail ask` with grammar-level safety properties
intact, with no fine-tune and no external harness. Three small
language additions and a scoring tool make that demonstration
reproducible.

### Language additions

- **`parse_json(source: Text) -> Result[Any]`** — pure builtin that
  parses JSON text and returns a Result. AIL programs no longer
  need to line-scan HTTP response bodies; `parse_json(resp.body)`
  then `get(data, "language")` is the idiomatic path. Registered in
  the purity allowlist; callable from `pure fn` bodies. Five unit
  tests covering object / array / nested / error / purity. Reference
  card updated under a new "JSON" section.
- **`ail_parse_check(source: Text) -> Result[Text]`** — pure
  self-reflection primitive. Parses a string as AIL and returns
  ok(source) if it parses, error(msg) otherwise. Does NOT execute
  — distinct from `eval_ail`, which runs the inner program. Six
  unit tests, including one that verifies an inner program
  declaring unresolvable intents still validates because only the
  parser runs. Reference card updated under a new "Self-reflection"
  section.
- **`AIL_AUTHOR_PROMPT_VARIANT=anti_python`** — new authoring prompt
  variant available to `ail ask`. Front-loads a "these patterns
  fail parse" block before any positive description, fights the
  author model's Python pretraining prior directly, and cuts
  overall prompt size 43% (4441 → 2526 chars) versus the default.
  On Claude Sonnet with no AIL fine-tune, this variant lifts AIL
  parse from 36% to 94% and AIL answer from 36% to 88% on the
  50-prompt corpus.

### New tool — HEAAL Score dashboard

- **`reference-impl/tools/heaal_score.py`** — standalone scorer that
  reduces a benchmark JSON to a single HEAAL Score plus an HTML
  dashboard. Weighted average of seven metrics:
    error explicitness (25%), execution success (20%),
    no-silent-skip rate (20%), parse success (15%),
    structural safety (10%), loop safety (5%), observability (5%).
  65% of the weight lives on measurements that move per run.
- **`tools/benchmark.py --report[=path.html]` and `--no-run`** —
  the existing benchmark runner now calls into `heaal_score` at
  the end. `--no-run --report=<file.html>` rescores an existing
  result JSON without re-running the benchmark.
- Three canonical dashboards committed under
  `docs/benchmarks/dashboards/`:
    AIL track, fine-tuned 7B:   AIL 87.7 vs Python 48.5
    HEAAL baseline (Sonnet):    AIL 77.6 vs Python 75.3
    HEAAL E1 (anti_python):     AIL 96.1 vs Python 75.9
  *(The Python 48.5 figure was corrected to 58.0 on 2026-04-22 after
  a methodology audit caught a vacuous-truth bug in `heaal_score.py`.
  Full audit + before/after table:
  `docs/benchmarks/2026-04-22_score_audit.md`. The correction will
  ship in v1.8.7.)*

### HEAAL documentation

- **`docs/heaal.md`** — paradigm-level manifesto written by Claude
  Opus 4 after reviewing the 2026 harness-engineering literature.
  Positions HEAAL (Harness Engineering As A Language) as the third
  layer of AI code safety after vibe coding and bolt-on harnesses,
  with the Rust borrow-checker analogy carrying the core claim
  (convention → compiler guarantee). Also in Korean
  (`docs/ko/heaal.ko.md`) and AI-readable (`docs/heaal.ai.md`).
- **`docs/heaal/`** — HEAAL track inside the repo: terminology
  (author model vs intent model), experiments E1–E2, prompt
  variants, benchmark runners.
- **E1 writeup** — `docs/benchmarks/2026-04-22_heaal_E1_analysis.md`.
- **E2 writeup** — `docs/benchmarks/2026-04-22_heaal_E2_analysis.md`,
  including the concrete E2-10 case where a Python program crashed
  on an unhandled `urllib.error.HTTPError 403` while the AIL program
  ran cleanly on the same URL because `perform http.get` returns a
  `Result` the grammar will not let the author skip.
- **`benchmarks/heaal_e2/`** — long-task corpus, fixture setup
  script, and runner with AIL + Python side-by-side scoring.

### AIL-track experiments (R4–R6)

- **R4 (v4 fine-tune)** — Cat A +20pp but Cat B −27pp vs R3.
  Archived; v3 remains the serving model.
- **R5 (v5 single-line format)** — severe regression (Cat C 20%)
  caused by a "leading-quote artifact" when the coder base model
  treats single-line AIL as a Python string literal. Hypothesis
  rejected for coder bases.
- **R6 (v6 same single-line format, non-coder base)** — recovers
  to 80% parse / 62% answer with zero leading-quote artifacts,
  confirming the R5 failure was coder pretraining prior, not the
  single-line format itself.

### Other

- **SECURITY.md** added at repo root (private reporting channel
  for vulnerabilities, scope definition, by-design primitives
  explained).
- **Governance Rules 5 and 6** in `CLAUDE.md`: SESSION STATE must
  be updated on every commit; Claude Code sessions have PyPI
  publish authority via `~/.pypirc`.
- **Open questions Q16 and Q17** added to `docs/open-questions.md`:
  are comments useful in an AI-authored language; should AIL grow
  a human-readable display mode.

---

## v1.8.4 — 2026-04-21

Additive parser sugar within the v1.8 grammar freeze (spec §3 was
amended to permit additive desugarings; same precedent class as
the v1.8.3 `List[T]` parser fix). Targeted at the last gap between
`ail-coder:7b-v3` and the G1 ≥ 80% AIL-parse gate.

### Language (both runtimes)

- **Subscript sugar:** `EXPR[INDEX]` is now accepted as syntactic
  sugar for `get(EXPR, INDEX)`. Parser-only desugar — the runtime
  path is the existing `get` builtin, semantics are unchanged.
  Closes [issue #1](https://github.com/hyun06000/AIL/issues/1) and
  the three remaining v3 fine-tune parse failures (A04, A12, C18 —
  all `list[i]` Python-style subscript leaks). Python parser uses a
  bracket-balanced lookahead to disambiguate from `branch [COND] =>`
  arm headers; the Go parser doesn't implement `branch` so no guard
  is needed there.
- New conformance case `018_subscript_sugar.ail` exercises bare-
  ident subscript, literal-list subscript, double subscript, and
  subscript inside a `pure fn` body. Byte-identical on both
  runtimes.

### Spec

- `spec/08-reference-card.ai.md` §EXPRESSIONS lists the new sugar
  alongside `EXPR.field`.
- `spec/09-stability.md` §3 now records "additive parser
  desugarings" as an explicit class of permitted patch-release
  changes within the freeze, with the v1.8.3 and v1.8.4 precedents
  enumerated.

### Tests

- Python: 288 passing (was 284), 2 skipped — same as before plus
  the 4 new branch-syntax regression guards.
- Conformance: 52 passing (was 49), 0 added skip — case 018's
  three test shapes all pass on both runtimes.
- Go: ok.

---

## v1.8.3 — 2026-04-21

Additive release within the v1.8 grammar freeze (spec §2.5 permits
builtin additions; parser fixes bring runtime in line with the
already-frozen spec surface). Closes the two dominant AIL-parse
failure classes surfaced by the ail-coder:7b-v2 benchmark.

### Language (both runtimes)

- **Math builtins added as trusted-pure:** `round`, `floor`, `ceil`,
  `sqrt`, `pow`. Usable directly inside `pure fn` bodies without
  imports. Closes PurityError on benchmark tasks C07 (BMI) and C12
  (standard deviation). Python and Go implementations are byte-
  equivalent (banker's rounding via `math.RoundToEven`;
  Result-error on `sqrt` of a negative).
- **Parametric types parse cleanly.** Spec §2.3 always listed
  `List[T]`, `Map[K,V]`, `Result[T]`, `Tuple[A,B]` as valid; the
  parsers were silently discarding the bracket clause. They now
  consume and ignore it (AIL stays dynamically typed, the bracket
  content is annotation-only). Closes ~3 AIL parse failures per
  benchmark run. Python and Go parser changes are parallel.

### Training

- **Dataset expansion v2 → v3:** 205 → 244 validated samples.
  +41 new entries cover: 7 math-builtin programs, 12 parametric-
  type fn signatures, 14 hybrid (fn + intent) shapes modelled on
  the benchmark C-category, 3 additional pure-intent examples,
  5 pure-fn variations.
- **`to_chatml.py` system prompt updated** to document the
  parametric types and math builtins so the fine-tune sees the
  same surface both during training and at inference.

### Benchmark results (ail-coder:7b v3 on the Opus 50-prompt corpus)

- AIL parse: 64% (v2) → **78%** (+14 pp; v3 misses G1 by one case)
- AIL answer: 56% → **70%**
- Category C (hybrid) parse: 45% → **70%** (+25 pp — headline)
- Error handling miss: **AIL 0% / Python 44%** — structural gap
  stable across every model tier tested (llama8b 86%, qwen14b 42%,
  Sonnet 4.6 70%).
- G3 verdict: **PASS** — AIL answer rate exceeds Python answer rate
  by 22 percentage points on the same fine-tuned model.

### Documentation

- New practical FAQ covering token economics and the adoption
  decision checklist: [`docs/why-ail-faq.md`](docs/why-ail-faq.md)
  (+Korean).
- New mechanics explainer with the mechanism behind each benchmark
  number, including reproduction one-liners:
  [`docs/why-ail-mechanics.md`](docs/why-ail-mechanics.md)
  (+Korean).
- Benchmark index [`docs/benchmarks/README.md`](docs/benchmarks/README.md)
  extended with the v3 run row.

251 tests pass (+27 since 1.8.2: math builtin unit tests, 2 new
conformance cases for math and parametric types).

---

## v1.8.2 — 2026-04-20

Real-world-prompt hardening. Each change fixes a failure mode
surfaced by live `ail ask` calls after 1.8.1 shipped.

- **Ollama HTTP timeout 120s → 300s**, with new env override
  `AIL_OLLAMA_TIMEOUT_S`. Larger models (gemma2:27b etc.) couldn't
  finish one author call with the full reference card in context
  within the old limit, so every retry was silently hitting
  socket.timeout.
- **Trailing markdown fence tolerance.** gemma2:9B emits valid AIL,
  then closes it with a standalone ``` line and appends an
  "Explanation:" prose block. The lexer used to choke on the stray
  backtick at the closing line. A new `_truncate_at_trailing_fence`
  step cuts source at the first lone ``` that has real AIL content
  above it.
- **Retry hints for prose-only responses.** llama3.1:8B sometimes
  abandons code entirely and writes a natural-language
  explanation. The lexer error (`unexpected character '!'` or
  top-level IDENT like `What` / `Let`) now triggers a targeted
  constraint telling the author to emit only AIL, no prose.

224 tests pass.

---

## v1.8.1 — 2026-04-20

**First PyPI release under the new name `ail-interpreter`.**

Distribution name on PyPI: `ail-interpreter` (was `ailang`, rejected
by PyPI's similarity check against `ai-lang`). Import name and CLI
both remain `ail`.

**Packaging fixes**
- `pyproject.toml` no longer packages a stray `ail_mvp/` directory
  (left over on contributor disks from the v1.8 rename).
- The language reference card is now bundled inside the wheel at
  `ail/reference_card.md`. Previously `ail ask` on pip installs
  silently fell back to a ~400-char stub instead of the real 22k
  spec, degrading author prompt quality.
- `tests/test_spec_bundled.py` guards against the bundled copy and
  `spec/08-reference-card.ai.md` drifting.

**Lexer**
- `#` is now accepted as an alias for `//` line comments in both
  the Python and Go runtimes. AI authors trained heavily on Python
  reach for it reflexively; the cost of rejecting was a lost-
  confidence moment per prompt. Spec keeps `//` canonical.

**`ail ask` — first real-world prompt (`factorial of 7`) on llama3.1:8B**
- Author prompt names the three real stdlib modules (core, language,
  utils) so the model stops inventing `stdlib/math`.
- `_remediation_hints` surface targeted corrections for five common
  failure classes (bad imports, ternary `?:`, generic type
  annotations like `[Number]`, literal `\n` escape leaks, top-level
  JSON-wrapper leaks) — each carried into the retry prompt as a
  constraint.
- Few-shot example #1 (trivial `return 42`) replaced with a factorial
  recursion example — small models anchor strongly to the first
  example, and the old one taught nothing.
- `ask()` auto-extracts a bare integer from the prompt as
  `input_text` when the caller didn't pin one. Covers programs like
  `factorial(to_number(x))` that would otherwise blow up recursion on
  empty input.
- Tolerance: when the model wraps its answer in a single backtick and
  echoes the prompt's examples section verbatim (observed on
  llama3.1:8B), `_recover_echoed_program` recovers the full AIL
  program from the echo rather than extracting just the bare
  expression.

**Benchmark**
- `tools/bench_authoring.py` rewritten to measure three axes — parse
  rate, fn/intent routing accuracy, final-answer correctness — across
  a 50-case corpus tagged `pure_fn` / `pure_intent` / `hybrid`.
  Baseline on llama3.1:8B: 54% parse, 52% routing, 30% final-answer.
  Hybrid routing jumped from 0/15 on the old prompt to 10/15 after
  the decision rules landed.

**Tolerance (unrelated to ask)**
- Malformed JSON wrapper recovery — when the model returns
  `{"value": "...", "confidence": 1.0}` with unescaped inner quotes,
  a regex-based lenient extractor pulls out the AIL source instead
  of falling through to the parser.
- Literal-`\n`-escape unescape — source with backslash-n and no real
  newlines gets decoded.

**Tests:** 223 passing (was 211 in v1.8.0).

---

## v1.5 — 2026-04-17

**Implicit parallelism.** Independent intent calls run concurrently.

- Consecutive Assignments whose RHS contain intent calls and are
  pairwise independent are grouped into parallel batches and evaluated
  via a ThreadPoolExecutor. No async/await — the independence is
  structural.
- Wall-clock latency for N independent intents drops from N·t to t.
- Dependent sequences (`b = f(a)`) stay sequential; the planner
  detects data flow.
- Trace entries from a batch carry `parallel=True`; batches are
  bracketed by `parallel_batch_start`/`_end` markers.
- Thread-safety: `Trace.record/enter/exit` are now lock-protected.

**Files:** `runtime/parallel.py` (new), `runtime/executor.py`,
`runtime/trace.py`, `examples/parallel_analysis.ail` (new).

**Tests:** 13 new (155 total).

---

## v1.4 — 2026-04-17

**`attempt` blocks — confidence-priority cascade.**

```ail
extracted = attempt {
    try direct_parse(x)     // pure, wins if ok
    try scan_tokens(x)      // pure, cheap fallback
    try infer_number(x)     // LLM — last resort
}
```

- Evaluates each `try` in order. A try qualifies when the result is
  not a Result-typed `error(...)` and its confidence ≥ 0.7.
- First qualifying try wins; if none qualify, the last try's value is
  returned with its low confidence preserved.
- Selected index is recorded via a new `attempt` origin kind; upstream
  lineage is preserved through the origin's parent chain.
- `pure fn` bodies may contain `attempt` blocks, but every `try` must
  itself be pure; intents inside a pure-fn attempt are rejected at
  parse time.

**Files:** `parser/ast.py` (`AttemptExpr`), `parser/parser.py`,
`parser/lexer.py`, `parser/purity.py`, `runtime/executor.py`,
`runtime/provenance.py` (`ATTEMPT` kind, `attempt_origin()`),
`examples/cascade_extract.ail` (new).

**Tests:** 11 new (142 total).

---

## v1.3 — 2026-04-17

**Structural purity contracts — `pure fn`.**

- `pure fn` declares a statically-verified contract: no `perform`
  statements, no intent calls, no calls to non-pure fns, no
  `eval_ail`. Violations raise `PurityError` at parse time.
- Composed with provenance (v1.2): a pure fn's output is compile-time
  guaranteed to have `has_intent_origin(result) == false`.
- All 11 `stdlib/utils.ail` utilities upgraded to `pure fn`.
- Unqualified `fn` retains unchanged semantics (backward compatible).

**Files:** `parser/purity.py` (new), `parser/ast.py` (`purity` field),
`parser/parser.py`, `parser/lexer.py`, `parser/__init__.py`,
`stdlib/utils.ail`.

**Tests:** 15 new (131 total).

---

## v1.2 — 2026-04-17

**Provenance — every value knows where it came from.**

- Each `ConfidentValue` now carries an `Origin` recording the
  operation that produced it, linked to the origins of its inputs.
- Origins are created at fn/intent/builtin/entry boundaries;
  binary/unary/field operations inherit the dominant parent origin to
  keep trees bounded.
- Intent origins additionally carry `model_id` and an ISO-8601
  timestamp for audit.
- New builtins: `origin_of(value)`, `lineage_of(value)`,
  `has_intent_origin(value)`. These cannot be shadowed by user fns
  or intents.

**Files:** `runtime/provenance.py` (new), `runtime/executor.py`,
`examples/audit_provenance.ail` (new), `spec/08-reference-card.ai.md`.

**Tests:** 18 new (116 total).

---

## v1.1 — 2026-04-17

**Result type for explicit error handling.**

- New builtins: `ok(value)`, `error(msg)`, `is_ok(r)`, `is_error(r)`,
  `unwrap(r)`, `unwrap_or(r, d)`, `unwrap_error(r)`.
- `to_number` now returns a Result on non-numeric input.
- `examples/safe_csv_parser.ail` demonstrates Result-based pipelines.

---

## v1.0.0 — 2026-04-17

**The first stable release.** AIL is a programming language designed for AI as the primary author of code. This release contains a complete language specification, a working Python interpreter, a standard library written in AIL, and evidence that the language works as intended.

### What ships

**Language specification** (8 documents)
- spec/00: Overview and design philosophy
- spec/01: Core syntax — intent, context, branch, entry, import
- spec/02: Context system — typed situational assumptions with inheritance
- spec/03: Confidence model — every value carries a belief measure in [0, 1]
- spec/04: Evolution — self-modification with metric, bounds, rollback, human review
- spec/05: Effects — declared side effects with authorization and observability
- spec/06: Standard library specification
- spec/07: Deterministic computation — fn, if/else, for, types, built-in functions

**Working interpreter** (Python, 88 tests)
- Lexer and recursive-descent parser for the full v1.0 grammar
- Executor with intent dispatch (LLM), fn execution (deterministic), and hybrid programs
- Context resolution with inheritance, override tracking, and scope stacking
- Confidence propagation per spec/03 §3
- Evolution supervisor: retune + rewrite constraints, version chain, bounded_by, rollback, human review
- Import resolver for stdlib modules
- eval_ail: parse and execute AIL source at runtime (self-generation)
- Anthropic adapter with robust JSON parsing (code fences, nested objects, confidence clamping)
- Mock adapter for offline development and testing
- .env file loader for API key management
- CLI: `ail run`, `ail parse`, `ail version`

**Standard library** (written in AIL, not Python)
- stdlib/core: identity, refuse
- stdlib/language: summarize, translate, classify, extract, rewrite, critique
- stdlib/utils: word_count, char_count, is_empty, repeat, pad_left, clamp, sum_list, average, flatten, unique, take

**21 built-in functions**
- Text: length, split, join, trim, upper, lower, starts_with, ends_with, replace, slice
- List: length, get, append, sort, reverse, range, map, filter, reduce
- Conversion: to_number, to_text, to_boolean
- Math: abs, max, min

**9 example programs**
- hello.ail — simplest case
- translate.ail — context inheritance with override
- classify.ail — branch dispatch on classifier output
- ask_human.ail — low-confidence fallback to human
- evolve_retune.ail — evolution with version chain
- summarize_and_classify.ail — stdlib imports
- fizzbuzz.ail — pure fn, no LLM, proof that AIL is a real language
- review_analyzer.ail — hybrid pipeline (fn 23 calls + intent 6 calls)
- meta_codegen.ail — AIL generates and executes AIL

**Documentation**
- Human-readable: README.md, CONTRIBUTING.md, ROADMAP.md
- AI-readable: README.ai.md, spec/08-reference-card.ai.md
- Korean: docs/ko/README.ko.md, evolve-guide.ko.md, stdlib-guide.ko.md
- Naming convention: .md (human), .ai.md (AI/LLM), .ko.md (Korean)

**CI/CD**
- GitHub Actions: tests on Python 3.10/3.11/3.12, smoke tests, evolve demo
- Optional live-test job against real Claude API

**Design documents** (vision, not implemented)
- runtime/00-airt.md — AI Runtime design
- os/00-noos.md — Neural-Oriented OS design
- os/01-compatibility.md, 02-security.md, 03-governance.md

### What was proven

1. An AI (Claude) read spec/08-reference-card.ai.md and generated valid AIL programs that executed correctly — for vowel counting, name sorting, and score analysis.

2. During code generation, a missing language primitive (list index access) was discovered. The `get()` builtin was added. This is the feedback loop the project was designed to enable.

3. FizzBuzz runs in AIL without any LLM involvement. AIL is a real programming language, not just an LLM orchestrator.

4. The review_analyzer example demonstrates the hybrid model working in practice: 23 fn calls (free, fast, deterministic) + 6 intent calls (LLM, for judgment only).

5. meta_codegen.ail demonstrates self-generation: an AIL program that produces another AIL program and executes it via eval_ail.

### Known limitations

- No `while` loop (by design — spec/07 §3.3)
- No lambda expressions (use named fn + pass name as string)
- No static type checking (runtime only)
- No pattern matching
- Evolution state does not persist across interpreter sessions
- `import` brings the entire module, not individual symbols
- AIRT and NOOS are design documents, not implementations
