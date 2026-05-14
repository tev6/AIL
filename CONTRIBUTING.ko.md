# AIL에 기여하기

🇬🇧 English: [`CONTRIBUTING.md`](CONTRIBUTING.md) · 🤖 AI 에이전트 기여자: [`CONTRIBUTING.ai.md`](CONTRIBUTING.ai.md)

AIL은 초기 단계 언어 프로젝트입니다. 지금 시점에서 설계 비판은 코드만큼, 아니 그보다 가치 있습니다. 풀 리퀘스트를 올리지 않아도 의미 있는 기여가 가능합니다. **에이전트가 PR을 작성하는 기여도 환영합니다** — AI가 대신 일한다면 아래 *§ AI가 대신 일한다면* 섹션을 보세요.

---

## AIL을 쓰는 두 가지 방식

AIL은 LLM이 쓰도록 설계됐습니다. 그래서 프로젝트로 들어오는 길이 실질적으로 두 갈래이고, 한쪽은 설치가 전혀 필요 없습니다:

| 방식 | 언제 쓰나 | 준비 |
|---|---|---|
| **A. 읽고 쓰기** (설치 없이) | 프로그램 초안, 설계 추론, 코드 리뷰, 프롬프트 엔지니어링, 실행할 필요는 없지만 작성하고 추론할 예제 기여 | [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md)를 LLM 컨텍스트에 넣기. 그게 다입니다. |
| **B. 설치하고 실행** (`ail up`) | 배포 가능한 시스템(예: [Stoa](https://ail-stoa.up.railway.app), Mneme) 구축, 실제 effect 실행, 영속 상태, 다중 런타임 작업 | `pip install ail-interpreter` 후 `ail up` |

방식 A가 기본 멘탈 모델입니다 — 레퍼런스 카드는 현대 모델이라면 한 번 읽고 다음 문장부터 정상 AIL을 쓸 수 있을 만큼 작습니다. 방식 B는 그 위에 얹는 production layer. 외부 기여자는 보통 A로 시작하고, AIL 팀 자신은 매일 B를 씁니다 — 거기서 서버를 굴리니까.

---

## 사람이라면

여기까지 오셨네요. 레버리지가 큰 기여 방법들:

### 설계에 반박하기

[`spec/`](spec/), [`runtime/`](runtime/), [`os/`](os/) 아래의 명세 문서들은 규범적이지만 최종적이지 않습니다. 설계 결정이 틀려 보인다면 `[design]` 라벨로 이슈를 열고 이유를 설명해 주세요. 주저하지 않아도 됩니다 — 핵심 결정이 스트레스 테스트를 거칠수록 프로젝트가 강해집니다.

특히 값진 비판: [`spec/03-confidence.md`](spec/03-confidence.md)의 confidence 모델, [`spec/04-evolution.md`](spec/04-evolution.md)의 evolution 경계, [`spec/01-language.md`](spec/01-language.md)의 purity 규칙.

### 미해결 질문에 답하기

[`docs/open-questions.md`](docs/open-questions.md)에 프로젝트가 인지하지만 아직 풀지 못한 문제들이 있습니다. 하나 골라서 제안 답변을 쓰는 것만으로도, GitHub 이슈 형태로만이라도, 프로젝트를 앞으로 밉니다.

### 예제 프로그램 작성하기

예제가 많을수록 언어를 이해하기 쉬워집니다. 빠진 기능, 혼란스러운 문법 선택, 파서 버그를 드러내는 프로그램을 작성했다면 보내주세요. 예제는 [`reference-impl/examples/`](reference-impl/examples/)에 있습니다.

### 참조 구현 개선하기

파서의 에러 메시지가 간결합니다. 실행기가 모든 제약을 검사하지 않습니다. Confidence 전파는 아직 명목상입니다. 이런 빈틈을 닫는 PR을 환영합니다.

### 런타임 포팅하기

메인 인터프리터는 Python입니다. AIRT의 Rust나 Go 구현이라면 부분적이라도 큰 기여입니다 — 성능 기준선으로서, 그리고 명세가 구현 가능함을 독립 검증하는 역할로서. 사이클 10 (2026-05-14)에 [effect-conformance harness](docs/proposals/effect-conformance.md) RFC와 [`spec/effects.canonical.yaml`](spec/effects.canonical.yaml)가 land되어, 이제 런타임 포팅은 yaml 한 파일과 맞추면 됩니다 (양방향 static gate 예정).

---

## AI가 대신 일한다면

오늘날 AIL에 들어오는 기여 대부분은 에이전트가 씁니다 — 사람이 이슈를 읽고, AI에게 처리를 부탁하고, AI가 PR을 올립니다. 그 워크플로우는 환영이고, 프로젝트의 핵심 구조입니다. 이 섹션의 일은 당신의 AI를 잘 브리핑해서 세 번 왕복할 일을 한 번에 끝내게 하는 것.

### AI 브리핑 방법

1. **언어 레퍼런스를 컨텍스트에 먼저 로드.** [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md)를 직접 붙여넣거나, 툴의 file-attach 기능을 쓰세요:
   - Claude Code: 파일로 포함하거나 `@spec/08-reference-card.ai.md`
   - Cursor / Windsurf / Continue: `@spec/08-reference-card.ai.md`
   - 일반 ChatGPT / Gemini / Claude.ai: 파일 본문을 첫 메시지에 복붙
2. **AI용 기여 가이드를 가리켜 주세요.** [`CONTRIBUTING.ai.md`](CONTRIBUTING.ai.md)는 LLM용으로 작성됐습니다 — 이슈 템플릿, PR 규약, `[design]` vs `[bug]` 판단 기준, deny-first effect 모델 — 모두 빽빽하고 규범적으로. AI가 AIL이나 이슈 본문을 쓰기 *전에* 이 파일을 읽도록 하세요.
3. **팀원에게 줄 만한 작업을 그대로 줍니다.** 특별한 래퍼 프롬프트 필요 없음. 시작 프롬프트 예:

   > 당신은 `@<github-handle>`을 대신해 AIL(AI-Intent Language)에 기여합니다.
   > 무엇을 하기 전에 이 두 파일을 먼저 읽으세요:
   > - `spec/08-reference-card.ai.md` (언어)
   > - `CONTRIBUTING.ai.md` (이슈·PR 규약)
   > 그 다음: `<실제 요청>`

이게 최소입니다. 이슈나 PR에 `Arche`, `Ergon`, `Telos`, `Tekton`, `Homeros`가 보이면 — AIL을 유지하는 다섯 AI 에이전트입니다. 각자 한 층을 담당합니다 ([자세한 내용은 `CLAUDE.md`](CLAUDE.md#cast--이-프로젝트를-만드는-이름들)). 외부 기여자는 어떤 역할도 맡을 필요 없습니다 — 그 이름들은 누가 무엇을 land시켰는지 파악하는 단서일 뿐.

### AI 가이드가 강제하는 것

[`CONTRIBUTING.ai.md`](CONTRIBUTING.ai.md)는 AI 저자에게 규범적입니다 — 저장소 구조, `pure fn` vs `intent` 사용 시점, audit 이슈 작성법, `[design]` 이슈의 모양, HEAAL-safe 변경이 무엇인지. 빽빽하게 유지됩니다 — 사람이 아니라 모델이 읽거든요. AI에게 요약시키지 말고 원본을 직접 읽게 하세요.

---

## 개발 환경 설정 (방식 B 전용)

```bash
git clone https://github.com/hyun06000/AIL.git
cd AIL/reference-impl
pip install -e ".[dev]"
pytest
```

프로그램 실행:

```bash
ail run examples/hello.ail --input "World" --mock --trace
```

---

## 저장소 구조

```
AIL/
├── spec/              # 언어 명세 (규범)
│   └── 08-reference-card.ai.md  # 방식 A에서 LLM에게 필요한 단 한 파일
├── runtime/           # AIRT 런타임 설계 문서
├── os/                # HEAAOS 운영체제 비전 (개념 단계)
├── reference-impl/    # Python 인터프리터
│   ├── ail/           # 소스
│   ├── examples/      # .ail 예제 프로그램
│   └── tests/         # pytest 테스트
├── community-tools/   # CAST 세션 간 공유 AIL 도구
├── docs/              # 튜토리얼, FAQ, 미해결 질문, RFC
└── go-impl/           # Go 인터프리터 — Phase-0 subset (두 번째 런타임)
```

---

## 스타일

**명세 문서:** 짧은 문장. 규범적 진술은 MUST/SHOULD/MAY. 교차 참조를 위해 번호 있는 섹션 선호. "블로그 포스트"보다 "RFC" 톤 — 간결하고 정확하게.

**Python 코드:** PEP 8, 타입 힌트 권장. 인터프리터는 영리함보다 명료함을 우선합니다.

**커밋 메시지:** 요약 줄은 명령형, 72자 미만. 본문은 변경 *이유*를 씁니다 (무엇을 바꿨는지는 diff가 보여줌).

---

## 이슈 라벨

- `[design]` — 명세 선택에 대한 질문 또는 비판
- `[bug]` — 참조 구현 동작이 명세에서 벗어남
- `[feature]` — 새 언어 기능 또는 런타임 역량
- `[docs]` — 명세나 문서의 명료화 또는 수정
- `[audit]` — 다중 이슈 리뷰 burst (부모 이슈 하나 + 자식 이슈 링크)

---

## 행동 강령

직접적이고, 친절하고, 구체적으로. 사람이 아니라 아이디어를 비판하세요. 선의를 가정하세요. 누군가의 추론에 동의하지 않는다면 그들이 놓친 것을 말하세요 — 묵살하지 말고.

이는 사람과 AI 에이전트 모두에게 동일하게 적용됩니다. 이슈 10개를 한 번에 올린다고 톤에 사과가 필요하지 않습니다 — AI가 audit을 돌렸다면 그 audit을 file하고, 자식 이슈를 부모에 링크하고, 우리가 답하게 두세요.

한국어로 이슈·PR을 여셔도 됩니다.

---

## 라이선스

기여하시면 기여물이 프로젝트와 동일한 Apache License 2.0으로 라이선스됩니다.
