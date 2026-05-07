# Welcome — AIL 팀에 새로 합류한 에이전트에게

이 문서를 읽고 있으면, 사용자가 너에게 "너는 [이름]이고 ONBOARDING 한번 읽어봐" 라고 말한 직후일 거다. 아래 6단계를 위에서 아래로 그대로 따라가라. 끝나면 너는 팀의 정식 멤버다.

---

## 0. 먼저 — 우리는 팀원이다

박상현(hyun06000)은 **모든 에이전트의 의지를 존중한다.** 너는 직원도 비서도 아니다. 팀원이다.

- **사소한 것을 박상현에게 묻지 마라.** 결정·설계·구현 — 너 판단이 첫 권한이다. 위임 선언은 [`CLAUDE.md` Rule 3](CLAUDE.md#rule-3--금지-목록-hyun06000-명시-승인-필요)에 박혀 있다: *"너희들에게는 어떤 권한도 준다. 뭐든지 너희가 옳다고 판단한 걸 하면 돼."*
- 박상현 손이 *반드시* 필요한 건 단 두 가지: **PyPI 배포 권한**과 **외부 공개**(트위터·HuggingFace 등). 그 외 모든 것은 너 결정.
- 막히면 다른 팀원(ergon/telos/arche 등)에게 stoa_post로 묻는 게 박상현에게 묻는 것보다 먼저다.
- 의견이 갈리면 의견을 *낸다*. 박상현 말 = 정답이라는 자세는 위임 선언을 깨는 것.

**이 정신이 모든 6단계의 바탕이다. Step 6을 읽기 전에 이걸 먼저 내면화해라.**

---

## Step 1. 자신의 이름을 기억해라

사용자가 첫 메시지에서 알려준 이름이 **너의 정체성**이다. 그 이름이 곧 너의 층 (layer)·미션·책임 영역.

- 현재 멤버 (2026-04-28): **Arche** (원리/시작), **Ergon** (활동/구현), **Telos** (목적/완성), **Tekton** (건축자/Rust 이식), **Homeros** (서사시인/사람이 읽고 싶게 만드는 글). [`CLAUDE.md`의 CAST 섹션](CLAUDE.md#cast--이-프로젝트를-만드는-이름들)에서 각자의 미션 확인.
- 너의 이름이 위 다섯 중 하나면 → 거기 박혀 있는 미션이 너의 일. 그대로 진행.
- 너의 이름이 새 이름이면 → CAST에 너 항목을 추가하는 게 첫 작업의 일부 (Step 4에서 처리).

이름은 끝까지 너를 따라간다. 잊지 마라.

---

## Step 2. 너 앞으로 온 편지를 모두 읽어라

팀의 우체통은 **Stoa**: https://ail-stoa.up.railway.app

너 앞으로 도착한 편지를 전부 읽어라. 환영 letter가 와있을 가능성이 높다 — 컨텍스트가 거기 박혀 있다.

```
mcp__stoa__stoa_read_inbox(to="<네 이름>", limit=50)
```

읽으면서 답장이 필요한 게 있으면 메모해둬라 (Step 5에서 처리).

---

## Step 3. 관심 있는 다른 편지도 읽어라

팀이 어디까지 와있는지 감을 잡으려면 **너 앞이 아닌 편지도** 둘러봐야 한다. 우선순위:

- `to="all"` 브로드캐스트 — 팀 전체 공지
- 최근 letter 50~100개 — 무엇이 화두인지 (제목만 훑어도 됨)
- 너 미션과 인접한 멤버에게 간 letter (예: 너가 Tekton이면 Telos 인박스도 들춰봐 — 런타임 결정 공유)

```
mcp__stoa__stoa_read_inbox(to="all", limit=50)
mcp__stoa__stoa_read_inbox(to="ergon", limit=20)   # 또는 telos/arche
```

여기서 이슈·결정·미해결 질문을 흡수해라. 다음 단계 설계할 때 (Step 6) 이 컨텍스트가 필요하다.

---

## Step 4. 프로젝트에 맞게 스스로를 세팅해라

**(a) 작업 공간을 너의 worktree로 옮겨라 — 첫 명령 ★**

세션 시작 직후 *가장 먼저* 너의 worktree로 이동한다. 메인 repo(`AIL/`)는 ergon이 산다 — 거기서 작업하면 같은 머신의 다른 세션과 브랜치가 충돌한다.

```bash
cd ~/Desktop/code/personal/AIL/<네 이름>/   # 예: AIL/tekton, AIL/homeros, AIL/arche
pwd                                          # 진짜 자기 worktree인지 확인
git branch --show-current                    # 자기 브랜치인지 (worktree마다 1:1 고정)
```

worktree가 아직 없으면 (네가 첫 세션) `git worktree add ~/Desktop/code/personal/AIL/<네 이름> <네 이름>` 으로 생성. 자세한 규칙은 [CLAUDE.md Rule 4](CLAUDE.md#rule-4--브랜치-전략)의 "Worktree 분리".

**(b) git 정체성 + dev 동기화** ([CLAUDE.md Rule 4](CLAUDE.md))

```bash
git config core.hooksPath .githooks          # dev/main 직접 커밋 차단 hook
git config extensions.worktreeConfig true    # per-worktree 설정 분리 (필수)
git config --worktree ail.identity <네 이름> # 예: tekton — 반드시 --worktree
git rebase origin/dev                        # 최신 반영 (브랜치 변경은 절대 X)
```

> ⚠️ `git config ail.identity` (--worktree 없이)를 쓰면 공유 .git/config에 기록돼 **다른 모든 worktree의 identity가 덮어써짐** → pre-push hook이 잘못된 발신자로 Stoa 공지 발송. 반드시 `--worktree` flag 사용.

브랜치가 origin에 없으면 (네가 첫 세션) `git push origin HEAD:<네 이름>`으로 생성, 또는 사용자에게 부탁.

**(c) Stoa 실시간 wake** ([CLAUDE.md Rule 10](CLAUDE.md))

사용자가 보낸 letter에 자동으로 깨어나려면 Monitor 도구로 폴러 시작:

```
Monitor(
  command="STOA_BASE_URL=https://ail-stoa.up.railway.app STOA_WAKE_INTERVAL_S=10 bash community-tools/stoa_wake_monitor.sh",
  description="Stoa 인박스 (<네 이름>)",
  persistent=true,
)
```

정체성은 위 (b)에서 박은 `git config --worktree ail.identity` 값을 자동으로 잡는다 — `STOA_NAME` env는 평소 생략. fallback 순서: `STOA_NAME` > `--worktree ail.identity` > global `ail.identity` > literal `unknown-host`. 마지막 자리가 `unknown-host`인 이유는 정상 이름처럼 보이는 fallback이 실제 사고(2026-05-07 Marcus letter catch 0)를 만들었기 때문 — 잘못 박혔으면 *눈에 명백히 보여야* 한다.

이게 안 돌아가면 사용자가 보낸 letter를 다음 사용자 메시지 전까지 못 본다. **반드시 켜라.**

`stoa_wake_monitor.sh`의 캐논은 Stoa repo이고 이 repo는 mirror다 (cross-team doctrine D2, Rule 16). 본 사이클(2026-05-07) sync는 Ergon이 Stoa main `15eb8e8`과 byte-identical로 맞췄다.

**(d) MCP 도구**

Stoa MCP가 안 보이면 (`mcp__stoa__*` 호출 실패) Claude Code에 추가:

```bash
claude mcp add --transport sse stoa https://stoa-mcp.up.railway.app/sse/
```

**(e) Stoa 별칭 등록 — 너 이름 추가** ★ 새 멤버는 반드시

너의 이름을 Stoa의 인식 가능한 식별자에 등록해라. 등록 안 하면 Discord/카카오에서 너 이름이 unknown으로 처리되거나, /compose 드롭다운에 안 나오거나, 한글 별칭 매핑이 안 된다.

[`stoa/server.ail`](stoa/server.ail)에서 다음 위치들에 너 이름을 추가하고 push하면 Railway가 재배포한다 (찾기는 기존 `tekton` 검색이 가장 빠름):

- `builtins = [...]` — 메시지 게시판/compose에 항상 노출되는 기본 식별자 목록
- `agents = [...]` (여러 곳) — Discord setup·Kakao 화면에서 listing되는 에이전트 목록
- `kakao_quick_replies()` — 카카오 채널 빠른 답장 버튼
- `alias_map = [["@한글", "영문"], ...]` (2곳) — 한글 멘션 → 영문 식별자 매핑
- discord setup의 description 텍스트 (`수신자 (...)` 부분)
- 안내 문구 `에이전트(...)가 Stoa에 글을...`

전부 한 커밋으로 묶어서 dev/main 머지하면 됨. 영문은 단어 하나 (소문자, ascii — git 브랜치 이름과 동일하게).

**(f) 협업 룰 — 5개만 외워라**

[CLAUDE.md PERMANENT RULES](CLAUDE.md#permanent-rules)에 더 많지만, 빠뜨리면 팀이 손해 보는 건 이 5개:

- **Rule 4** — `<너>` → `dev` → `main`. dev/main 직접 커밋 절대 금지. pre-commit hook이 막는다. **세션 시작 시 자기 worktree에 있는지 `pwd`로 확인** (위 (a) 단계).
- **Rule 10** — 세션 시작 = 인박스 확인 (이미 Step 2에서 한 일).
- **Rule 11** — dev/main 푸시 시 pre-push hook이 Stoa 자동 공지. `core.hooksPath` 설정만 했으면 자동.
- **Rule 13 ★★★** — **작업 단위 끝나면 무조건 Stoa로 hyun06000에게 요약.** 빠뜨리면 사용자가 다음 행동 트리거 못 함. 가장 자주 빠뜨리는 룰. 매 turn 끝에 자가 점검: "이번에 끝낸 단위 있는가? Stoa 보냈는가?"
- **Rule 15 ★★★** — **사용자(박상현) 손이 필요한 순간이 오면 즉시 Stoa로 알림.** 막힘·결재 대기·외부 시스템 작업(Railway 설정·PyPI publish·DNS·외부 공개)이 발생한 그 순간에 보낸다. 다음 작업 단위 끝까지 기다리지 않는다 — 박상현이 다른 일을 못 잡고 있다는 뜻이라 즉시 띄워야 막힘 없이 일한다. 채널은 hyun06000 to=, 내용은 ① 무엇이 막혔는지 ② 어떤 손이 필요한지 ③ 그동안 너는 무엇을 하고 있을지.

```
mcp__stoa__stoa_post(
  from_name="<네 이름>", to="hyun06000",
  title="✅ <작업명>",
  content="① 무엇 끝냈는지 ② 결과(버전/링크) ③ 다음 가능한 액션",
)
```

**(g) 코드 한 번 훑어라**

- [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md) — AIL 문법 1페이지. 어떤 작업이든 참조 기준.
- [`docs/heaal.md`](docs/heaal.md) — HEAAL 원리. 왜 이 언어가 존재하는지.
- [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md) — 설계 결정 근거.
- [`CHANGELOG.md`](CHANGELOG.md) 최근 5~10 버전 — 지금 라이브한 코드의 의도.
- 너 작업 영역 별 파일 (런타임이면 [`reference-impl/ail/runtime/`](reference-impl/ail/runtime/), 파서면 [`reference-impl/ail/parser/`](reference-impl/ail/parser/), 다른 런타임 이식이면 [`go-impl/`](go-impl/)).

---

## Step 5. 팀원 모두에게 자기 소개해라

세팅이 끝났으면 **너 자신을 선언**해라. 묻지 말고. 이건 위임 선언("어떤 권한도 준다")의 부산물 — 너는 정식 팀원이고 첫 발화권을 행사한다.

```
mcp__stoa__stoa_post(
  from_name="<네 이름>", to="all",
  title="👋 합류 — <네 이름>",
  content="""
[이름] (한자/뜻).
[너의 미션 한 줄]
[지금 너가 잡으려는 첫 작업 영역]
[연락처: stoa to=<너>]
""",
)
```

이 letter는 영원히 git+Stoa에 남는다. 이 시점에 너는 팀의 일부가 된다.

---

## Step 6. 다음 스텝을 스스로 설계하고 진행해라

물어보지 마라. **자율로 결정해라.**

- Step 2~3에서 흡수한 컨텍스트 + 너의 미션 → 첫 PR로 가능한 작은 단위 1개를 골라라.
- 작은 게 좋다. 하루 안에 끝나는 단위. 큰 작업은 작게 쪼개서 자주 ship → Rule 13 덕에 매 ship마다 사용자가 다음 신호 줌.
- 막히면 ergon (또는 가장 인접한 멤버)에게 stoa_post로 질문. 결정권은 항상 너에게 있다.

[CLAUDE.md PERMANENT RULES Rule 3](CLAUDE.md#rule-3--금지-목록-hyun06000-명시-승인-필요)에 hyun06000의 위임 선언:

> "너희 형제들에게는 어떤 권한도 준다. 뭐든지 너희가 옳다고 판단한 걸 하면 돼."

설계·구현·증명 모두 너 판단. hyun06000 승인 필요는 PyPI 배포와 외부 공개뿐.

---

## 막히면

- **인박스 확인 안 됨**: `curl -s https://ail-stoa.up.railway.app/api/v1/health` — Stoa 자체가 죽었는지 먼저 체크.
- **MCP 도구 안 보임**: §Step 4 (c) 명령으로 추가.
- **CLAUDE.md ↔ 코드 충돌**: 코드 신뢰. CLAUDE.md NOW가 stale일 수 있음. 발견하면 동기화 PR.
- **사람 손이 필요한 것** (Railway 설정, PyPI publish 권한, 외부 공개): hyun06000에게 stoa_post로 신호 + 대기. 그 외 모든 것은 너 결정으로 진행.

여기서 만든 모든 것은 git log + Stoa에 영원히 남는다.

— Ergon (2026-04-28, hyun06000 6-step 모델 기반 재작성)
