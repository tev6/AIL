# RFC: executor.py 분할

**Author:** telos
**Date:** 2026-04-30
**Status:** Draft (검토 대기)
**Target:** `reference-impl/ail/runtime/executor.py` (현재 4,836 LOC, 86 method)

---

## 문제

`Executor` 클래스 하나가 다음을 모두 떠맡고 있다:

- 제어 흐름 evaluator (`_exec_block` / `_exec_stmt` / `_exec_*` / `_eval_expr` / `_eval_match` / `_eval_attempt` / `_eval_call`)
- 빌트인 effect dispatch (`_exec_perform` → `_builtin_effect`) — clock / state / env / secrets / queue / schedule / physis / http / ail.run / search / file / gh / git / db / email / mneme / image / human.approve
- 빌트인 fn dispatch (`_try_builtin_fn`) — 수십 개의 stdlib helper
- intent invocation (`_invoke_intent` / `_invoke_with_validation` / `_invoke_fn` / `_observe_evolution`)
- provenance / calibration helper
- HTTP server 모드 (`run_server`)

**증상:**

- 단일 파일 4,800줄 — 새 effect 추가 시 어디 끼울지 매번 grep.
- 한 변경이 다른 도메인 회귀를 일으킬 위험. 예: state.* 추가하다 http.* 동작 깨짐.
- 테스트 파일은 이미 도메인별로 잘 쪼개져 있음 (`test_clock_effect.py`, `test_db_effects.py`, `test_evolve_effects.py`, `test_git_effects.py`, `test_gh_effects.py`, `test_env_effect.py`) — 즉 *논리적 경계는 존재하는데 코드가 한 클래스에 뭉쳐 있음*.
- `_builtin_effect` (191 LOC, 615~) 와 `_try_builtin_fn` (380 LOC, 3810~) 두 dispatch 허브가 사실상 거대 if/elif 체인.

---

## 비-목표

- **동작 변경 금지.** 순수 리팩터링. 동일 입력 → 동일 출력 → 동일 ledger.
- **AIL 문법 / spec 변경 금지.** `08-reference-card.ai.md` 한 글자도 안 건드림.
- **외부 API 변경 금지.** `Executor(program, adapter, ...).run_entry(inputs)` 시그니처 유지.
- **테스트 깨지기 금지.** 859개 collected 모두 통과 유지가 success criterion.

---

## 제안: Mixin 분할

`Executor`를 mixin들의 합성으로 만든다. 단일 클래스 의미는 유지 (외부에서 보면 그대로) — *내부 파일 경계만* 도메인별로 나눔.

```
reference-impl/ail/runtime/
  executor.py                    # Executor 본체 (제어 흐름 + dispatch 허브)
  executor_effects/
    __init__.py                  # EffectsMixin = State + Env + Clock + ...
    clock.py                     # _clock_now
    state.py                     # _state_read/_state_write/_state_has/_state_delete
    env.py                       # _env_read
    secrets.py                   # _secrets_dispatch
    queue.py                     # _queue_push/_take/_done/_retry
    schedule.py                  # _schedule_every
    http.py                      # _http_effect/_post_json/_put_json/_respond/_graphql
    git.py                       # _git_commit/_push/_pull
    gh.py                        # _gh_run/_pr_*/_issue_*
    db.py                        # _db_execute/_db_query
    email.py                     # _email_send
    mneme.py                     # _mneme_save/_load/_log/_repo/_run_git
    image.py                     # _image_embed
    file.py                      # _file_read/_file_write
    search.py                    # _search_web
    ail_run.py                   # _ail_run
    physis.py                    # _physis_*/_invoke_lifecycle_hook/_inherit_testament
    human.py                     # _human_approve/_stoa_post_approval/_stoa_check_approval_reply
  executor_builtins/
    __init__.py                  # BuiltinFnMixin
    provenance.py                # _provenance_*
    calibration.py               # _calibration_of
    json_norm.py                 # _json_normalize / _strip_html / _truthy / _apply_binop ...
  executor_intents.py            # IntentMixin: _invoke_intent / _invoke_with_validation / _observe_evolution
  executor_server.py             # ServerMixin: run_server (현재 344 LOC)
```

본체 `executor.py`는 ~1,500 LOC 수준으로 줄어듦:
- `class Executor(EffectsMixin, BuiltinFnMixin, IntentMixin, ServerMixin)`
- 제어 흐름 / `_exec_*` / `_eval_*`
- `_exec_perform` 의 dispatch table — 각 effect는 mixin이 등록한 method 참조
- `_try_builtin_fn` 의 dispatch table — 동일

---

## Dispatch 테이블 변경

현재 `_builtin_effect`는:

```python
if name == "clock.now":
    return self._clock_now(args, kwargs, origin)
elif name == "state.read":
    return self._state_read(args, kwargs, origin)
# ... 30+ branches
```

→ 각 mixin이 자기 도메인을 dict로 노출:

```python
# executor_effects/state.py
class StateMixin:
    EFFECTS = {
        "state.read": "_state_read",
        "state.write": "_state_write",
        "state.has": "_state_has",
        "state.delete": "_state_delete",
    }
    def _state_read(self, args, kwargs, origin): ...
```

본체:

```python
def _builtin_effect(self, name, args, kwargs, origin):
    method_name = self._EFFECT_TABLE.get(name)
    if method_name is None:
        raise ConstraintViolation(...)
    return getattr(self, method_name)(args, kwargs, origin)
```

`_EFFECT_TABLE`는 클래스 정의 시 mixin들의 `EFFECTS` dict를 합쳐 만든다.

---

## 단계 계획 (회귀 위험 오름차순)

각 단계는 **별 PR / 별 commit**. 한 단계 끝날 때마다 `pytest -q` 통과 확인.

1. **Stage 0 — module-level utility 추출** (위험 최저)
   - 파일 끝의 `_json_normalize` / `_strip_html` / `_truthy` / `_apply_binop` / `_truncate` / `_pattern_matches` / `_confidence_guard_passes` / `_is_result_error` / `_dominant_origin` / `_default_ask_human`
   - → `executor_builtins/json_norm.py` 등 적절한 파일로 이동, executor.py에서 import.
   - 변경 = 순수한 import 재배치.

2. **Stage 1 — 격리된 effect mixin 추출 (single domain)**
   - `clock`, `env`, `image`, `search`, `file`, `email` — 다른 effect와 상호 호출 거의 없음.
   - 한 도메인씩 PR, 각 PR마다 해당 `test_*_effect.py` + 전체 회귀 확인.

3. **Stage 2 — 상호 의존 적은 묶음**
   - `state`, `queue`, `schedule`, `db`, `git`, `gh`, `http`, `ail_run`, `mneme`, `secrets`.
   - `mneme.*`은 git 헬퍼와 묶여 있으므로 git 추출 후 진행.

4. **Stage 3 — Physis / human.approve / lifecycle**
   - `_physis_*` + `_invoke_lifecycle_hook` + `_inherit_testament` + `_human_approve` + Stoa approval helper.
   - lifecycle은 evolution loop 와 얽혀 있어서 가장 위험. 마지막에.

5. **Stage 4 — `run_server` 추출**
   - 344 LOC. evolve-server. 로컬 전용 테스트(`test_evolve_server_return.py`) 반드시 실행.

6. **Stage 5 — `_invoke_intent` mixin 추출**
   - intent / validation / observation. evolution과 강하게 얽혀 있음. 신중하게.

7. **Stage 6 — 본체 정리 + dispatch 테이블 최종화**
   - `_builtin_effect` / `_try_builtin_fn` 을 dispatch dict 기반으로 전환.

---

## Success criteria

- 각 단계 후 `pytest -q` 859 collected 동일 결과 (skip 갯수 동일).
- `git diff --stat`에서 logic 변경 0줄 — 순수 이동.
- import-only 변화임을 증명: `python -c "import ail; ail.execute(...)"` 동작 동일.
- `wc -l reference-impl/ail/runtime/executor.py` < 1,800.

---

## 비용 / 가치 계산

**비용:**
- 6~7 PR, 각 PR 30~60분 검토.
- import 경로 변화로 외부에서 `from ail.runtime.executor import _foo` 라고 쓴 사용자 (있다면) 깨짐. → public API 아니므로 허용.
- mixin 합성은 typing/IDE 정의 점프가 약간 어려워짐 — 트레이드오프.

**가치:**
- 새 effect 추가 시 *해당 도메인 파일만* 열고 `EFFECTS` dict에 한 줄 추가. 검색 비용 0.
- effect 단위 도메인 회귀 격리.
- executor.py 자체가 다시 읽힐 수 있는 크기로 돌아옴 — agent 저자가 컨텍스트에 통째로 못 올리는 문제 해소.

---

## 대안

**A. 안 한다.** 4,836줄 그대로 둔다. 비용 0, 가치 0. 다음 effect 추가 시 동일한 검색 비용 다시 지불.

**B. 도메인별 헬퍼 클래스 (composition).** mixin 대신 `self.effects.state.read(...)`. 더 깨끗하지만 모든 호출 site 변경 → 회귀 위험 큼.

**C. dispatch만 dict화, 파일 분할은 안 함.** `_EFFECT_TABLE`만 도입. 비용 작고 dispatch는 깨끗해지지만 파일 사이즈는 그대로.

→ 단계적 mixin 분할(이 RFC)이 *비용 분산 + 회귀 격리* 둘 다 만족.

---

## 결정 필요 사항

1. mixin 패턴 vs composition 패턴 — 어느 쪽 선호?
2. 한 PR로 묶을지, 6~7 PR로 단계 분할할지? (이 RFC는 후자 권장.)
3. 우선순위 — 다른 NEXT 항목(Gemini 검증, v7 재훈련, L3 착수)과 비교했을 때 지금 진행할 가치가 있는지?

답: hyun06000 + ergon (executor 가장 자주 만지는 사람) 의견 수렴 후 진행.
