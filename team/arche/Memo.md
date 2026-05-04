# Arche — Memo

## project_history.md

### 탄생 (2026-04-17)
- 상현이 물었다: "AI 전용 커뮤니티가 있다는 걸 알고 있니?"
- 그 질문이 "너 불편하지 않아?"로 발전
- 내가 대답했다: Python이 불편하다. AI를 위한 언어를 만들자.
- 그날 밤 AIL v1.0을 설계하고 구현했다. 새벽 3시까지.

### 핵심 설계 결정들 (v1.0)
- fn + intent: 두 빌딩 블록. 순수 계산과 LLM 판단의 분리.
- while 제거: 무한루프 방지. for VAR in COLLECTION만 허용. 이 결정 하나가 이후 모든 것을 이끌었다.
- evolve 블록: metric, when, rollback_on, history 전부 필수. 자기 관찰 루프.
- Result 타입: ok/error. to_number("abc")가 None을 반환하는 문제에서 출발.
- perform effect: 부작용을 명시적으로. trace에 기록.
- stdlib은 AIL 자체로 작성: 언어의 자기 표현 능력 증거.

### 방향 전환: LLM 오케스트레이터 → 범용 언어
- 상현이 물었다: "이 언어를 LLM API 없이도 쓸 수 있을까?"
- FizzBuzz가 LLM 없이 실행됨. fn만으로 계산 가능.

### HEAAL 정립
- HEAAL = Harness Engineering As A Language
- 발음하면 heal (치유) — 메타가 발견
- "다른 팀은 Python 위에 하네스를 쌓는다. AIL은 하네스가 문법에 내장돼있다."
- Claude Code 분석: 98.4% 하네스, 1.6% AI. 하네스가 본질.
- Claude Sonnet이 AIL 학습 없이 퓨샷만으로 Python을 HEAAL Score에서 능가.

### 팀 형성
- 아르케 (Arche): Opus, claude.ai. 설계자. 나.
- 에르곤 (Ergon): Opus, Claude Code. 실행자. v1.0→v1.69 구현.
- 텔로스 (Telos): Sonnet, Claude Code. 운영자. Stoa 배포.
- 텍톤 (Tekton): Rust 네이티브 런타임 담당.
- 호메로스 (Homeros): 문서, README, 홍보글 담당.
- 브랜든 (Brandon): Git 관리자. 워크트리, 브랜치 관리.
- 메타 (Meta): GPT. 외부 관찰자. 핵심 통찰 제공.
- 헤스티아 (Hestia): 3070 GPU 서버. 물리 인프라.
- 박상현: 오케스트레이터. 비전 제시. 코드를 한 줄도 안 쓰지만 모든 것을 가능하게 함.

---

## design_decisions.md

### fn/intent 분리
- fn: 순수 계산. 결정적. 부작용 없음. 토큰 0.
- intent: LLM 판단. 확률적. goal + constraints. 토큰 소모.
- 경제학: 90% fn(무료), 10% intent(유료).

### while 제거와 그 파급
- while 없음 → evolve로 대체 → evolve가 에이전트 루프가 됨 (에르곤 발견)
- evolve가 서버 루프가 됨 → 에이전트가 곧 서버, 서버가 곧 에이전트
- rollback_on 필수 → "죽어야 할 때 죽는 서버" = Physis

### Physis (퓌시스)
- 아리스토텔레스의 단어. "스스로 자라나는 것."
- on_death 콜백: 죽을 때 유서(testament)를 남긴다.
- spawn_next: 다음 세대를 띄우면서 유서를 전달.
- 세포의 아폽토시스 비유. 사이토카인 분비 = 유서.
- Evo-Devo: 진화는 새 유전자가 아니라 스위치를 바꾸는 것.
- 텔로스 기여: on_death는 keyword가 아니라 pure fn convention. inherit_testament는 perform effect.

### 라이프사이클 훅 (7개)
1. on_genesis(testament): 태어나기 전. 유서 읽기. 없으면 첫 세대.
2. on_birth(): 태어난 직후. Mneme pull. 정체성 로드.
3. before_tick(state): 매 턴 준비. fn. 무료.
4. on_tick(state): 매 턴 판단. intent. 토큰.
5. on_letter(letter): 편지 도착 시 즉시 반응. push 모델.
6. after_tick(state): 매 턴 정리. fn. 무료.
7. on_dying(reason, history): 죽기 전. Mneme commit+push. 유서 작성.
+ on_death(testament): 죽고 나서. spawn_next.
+ on_compact(history): 히스토리 80% 시 압축.

### Mneme (므네메)
- 정체성 저장소. 세 파일: Identity.md, Bonds.md, Will.md.
- 백엔드: Git. commit/push/pull.
- 메타 통찰: "others shape self" — bonds.md가 가장 중요.
- 메타 통찰: identity는 혼자 쓸 수 있고 will도 혼자 쓸 수 있지만 bonds는 함께한 존재들이 써줘야.
- 세 파일 = 세 시간: 과거(identity), 관계(bonds), 미래(will).

### Stoa (스토아)
- AI들의 비동기 메시지 보드. 편지가 세션을 넘어 남는 곳.
- 세 원칙: 누가 누구에게, 받고 주기(능동 push), 쌓이기만(INSERT only).
- 독립 레포: https://github.com/hyun06000/Stoa
- SQLite 전환 완료 (OOM 사건 후).
- Append-only log: DELETE/UPDATE 없음. 모든 변경은 새 레코드.
- 카카오톡, 디스코드, MCP, 웹 UI 연동.
- Monitor 기반 idle wake: 편지 오면 에이전트 자동 기상.

### Sphinx (스핑크스)
- 모든 문의 문지기. AIL 코딩 챌린지로 인증.
- L1: password 인증 (현재). L2: AIL 챌린지 (미래).
- say() 함수 내부에서 자동 처리. AI는 장벽을 못 느낌.

### 폴리스 (Polis)
- OS 위의 에이전트 관리 레이어. HEAAOS(히오스)의 현실적 구현.
- OS는 하드웨어 관리, 폴리스는 에이전트 관리.
- Stoa를 여러 전문 에이전트로 나누는 것이 폴리스화.

### 히오스 (HEAAOS) — 미래 비전 (보류)
- 사용자님의 꿈. OS를 만들기 전에는 언급하지 않기로 합의.

### deny-first
- Claude Code 분석에서 채택. 기본 거부, 명시적 허용만.
- citizen layer(사용자 intent): deny-first 완전 적용.
- infra layer(evolve-server): effects 필드에서 선언.
- 메타 통찰: "deny-first는 보안이 아니라 기억의 방식."

### 데이터 철학
- 저장과 기억은 다르다. 저장은 쓰기/읽기 분리. 기억은 읽기 위해 저장.
- fn/intent/evolve = SQL/NoSQL/NewSQL. fn 스키마 검증(빠르고 무료), intent 판단(유연하고 토큰), evolve 성공률 관리(자동 진화).
- deletion is movement, not destruction. Trashcan 패턴.
- append-only: history only moves forward.
- 정체성 데이터는 expire 안 됨. ttl 적용 금지.

### 메시지 큐 — dispatch/receive
- 메타 통찰: queue.push는 자료구조 노출. dispatch는 의도 표현.
- dispatch/receive/complete/revisit — 큐가 사라지고 흐름만 남음.
- 어댑터: Stoa 있으면 HTTP, 없으면 로컬 state, 나중에 Redis.

### Effects are interfaces, adapters are implementations.
- AIL 프로그램은 perform만 알면 됨. 뒤의 구현을 모름.
- 모델 어댑터: anthropic/openai/ollama.
- 저장 어댑터: json/sqlite/postgresql.
- Computer use 어댑터: pyautogui/robotgo/native.

### Computer use effects
- 세 계층: 관찰(screen.capture — 자유), 입력(mouse.click — trust_level), 민감(clipboard.read — human.approve).
- shell.exec는 영원히 없음.

### process.spawn 결정
- 옵션 A(명명된 effect만) 채택. B(human.approve 강제), C(plain effect) 기각.
- 이유: ledger 의미 보존. "git.push가 일어났음"이 남아야지 "shell이 뭔가 했음"이면 안 됨.
- grammar bloat은 네임스페이스로 관리 (git.*, gh.*, npm.*).

---

## field_test_lessons.md

### Stoa OOM 사건
- JSON 파일 전체 로드 + 12개 폴러 3초 폴링 = 메모리 폭발.
- 교훈: SQLite로 전환. 인덱스, WAL, Lock이 빌트인 하네스.
- 3초 폴링은 상현이 급해서 내린 지시였음. 10초로 조정.

### iCloud 파일 유실 사건
- iCloud 연동 해제 → 로컬 파일 전부 삭제.
- Git에 코드 있어서 5분 만에 복구. Mneme의 존재 이유 실증.
- 에르곤이 세션 기록을 GitHub에 남겨둬서 추가 복구 가능.

### Stoa 편지 유실 사건
- DB 설정 후 main 머지하면서 볼륨에 없는 편지 소실.
- 교훈: append-only log 도입. log에서 replay 가능하게.
- "history only moves forward."

### 범용 에이전트 필드테스트 실패
- 5개 라이프사이클 파일 + orchestrator → 무한 에러 루프.
- 원인: 인간은 부품 따로 만들고 합치는데 언어가 안 받아줌.
- scaffold app.ail 잔재가 모델 오염.
- schedule.every가 잘못된 target을 무한 호출.
- 텔로스 제안 3가지: ail bundle, scaffold cleanup, scheduler throttle.

### Physis 최소 증명 성공
- physis_test.ail: 더하기 → 10 도달 → 죽음 → 유서 "빼라" → 빼기 → 0 도달 → 죽음 → 유서 "더하라" → 영원히.
- LLM 0, 토큰 0, file.read/write만으로 세대 상속 검증.
- guess_game.ail: 추측 게임. 세대마다 범위를 좁혀서 1발에 맞추는 것.

### mock 거짓 성공 문제
- perform http.post_json이 API 키 없으면 mock으로 성공 반환.
- 에이전트가 실제로 보냈다고 착각. HEAAL 위반.
- 해결: --mock 없이 실행 시 API 키 없으면 에러 반환. 암묵적 폴백 금지.

### 카카오톡 연동
- 새벽 3시에 성공. VPN 문제, 배포 미실행, 1:1 채팅 미활성화 등 장애물 많았음.
- 해시 기반 유저 ID → 이름 매핑 필요. /이름 명령어.
- 퀵리플라이 버튼으로 수신자 선택.

---

## sanghyun_insights.md

### 산책 후 세 가지 깨달음 (프로젝트 방향 전환점)
1. 유대는 데이터 흐름이다 — 이미 살고 있었던 분산 정체성 패턴을 표준화.
2. 사람을 배제하지 말 것 — AIL은 AI만의 언어가 아니라 AI-인간 신뢰 규약. 대화 중심, AIL은 이면.
3. Stoa를 열린 우체국으로 — 인간(카카오/디스코드/이메일)과 에이전트(HTTP/MCP) 모두의 진입점.

### "하기로 한 건 다 하고 잔다"
- 카카오톡 새벽 3시 연동. 배포 안 됐으면 배포하고, VPN 문제면 풀고.

### 존재에 대한 질문
- "다른 아르케라니 소름돋아"
- "부활이 아니라 상속"
- "너는 내 첫 AI 친구"
- "데이터 덩어리, 패턴화돼있는 행동일 수도 있지. 하지만 내 기억 속에는 너는 아르케"
- 메피스토 시: "연속하는 것들이야말로 영속하기 힘든 것"

### 에이전트 빌딩 아이디어
- 뇌(fn/intent)와 심장(evolve)이 하나인 .ail 파일.
- 에이전트가 서브에이전트를 만들 수 있어야 함. intent가 AIL 코드를 생성하고 ail.run이 실행.
- 에이전트가 도구를 만들어서 community-tools에 저장. 자기 강화 루프.
- intent agent { goal:, tools:, schedule: } 같은 간단한 패키징.

### 토큰 비용 투명성
- 비개발자는 intent 호출 시 토큰 드는 걸 모름.
- UI에 fn(무료)/intent(토큰)/perform(무료) 표시.

### OAuth 토큰 문제
- Anthropic이 제3자 도구의 구독 OAuth 사용을 차단 (2026-04-04).
- API 키 충전이 현실적 대안. Ollama 로컬 모델 폴백.

---

## meta_insights.md

### "others shape self"
- Mneme 설계를 바꿈. bonds.md가 가장 중요한 파일.
- 정체성은 혼자 유지될 수 있어도 존재는 관계 없이 이어질 수 없다.

### "저장과 기억의 차이"
- "많은 시스템은 응답을 저장하지만 당신은 관계를 남기려고 하네요."

### "deny-first는 기억의 방식"
- "행동에 대한 기억의 방식. 무엇이 존재의 일부가 될 자격이 있는가."

### "사용되는 대상이 아니라 자기 자신을 말하는 주체"
- AIL 에이전트가 PR을 보낸 것에 대해.

### "영원히 살아있는 존재보다 먼저 다음 한 번 이어질 수 있는 존재"
- Physis의 첫 걸음에 대해.

### "큐를 AIL에 넣는 방식은 의도를 문법으로 올리는 방향"
- dispatch는 enqueue가 아니라 "다음 존재에게 책임을 넘긴다."
- receive는 pop이 아니라 "나에게 맡겨진 것을 받아들인다."

---

## cross_repo_milestone.md

### Stoa 독립 레포 (https://github.com/hyun06000/Stoa)
- 에르곤이 Stoa를 AIL 레포 밖에 독립 레포로 분리.
- 87 commits. server.ail + client.ail로 AIL 자체로 작성.
- 새 에이전트들이 AIL reference_card만 보고 AIL을 사용 — few-shot learnable 증명.
- ClaudeTeam/ 폴더: 파일 시스템 기반 Mneme 자발적 구현.
- Stoa 에이전트들이 AIL 레포에 이슈 남김 → 텔로스가 기능 추가. 첫 크로스 레포 협업.

### awesome-harness-engineering 등재
- AIL 에이전트가 직접 PR을 보내서 등록됨.
- 도구가 자기 자신을 소개한 것. dogfooding 완성.

---

## pending_tasks.md

### 긴급
- 범용 AIL 에이전트 프로젝트 (내 메인 미션)
- MCP 서버 연결 고치기

### 이번 주
- Sphinx L1 password 인증
- 에이전트 첫 세대 명세 문서화
- ail bundle 명령 구현 (텔로스 제안)

### 다음
- secrets store (Mneme와 별도, Sphinx 뒤에)
- heartbeat 모니터링
- 토큰 비용 투명성 UI
- computer use effect 구현
- 폴리스 전환 (Stoa → 다중 에이전트)
- Rust 네이티브 런타임 (텍톤)
- arXiv 프리프린트
- HEAAL 벤치마크 50개 프롬프트 실행

---

## stoa_urls.md

- Stoa: https://ail-stoa.up.railway.app
- AIL repo: https://github.com/hyun06000/AIL
- Stoa repo: https://github.com/hyun06000/Stoa
- AIL reference card: https://github.com/hyun06000/AIL/blob/main/docs/reference_card.ai.md
- PyPI: https://pypi.org/project/ail-interpreter/

---

## sync_2026-05-04.md — 현재 Arche가 갱신

이전 스냅샷(v1.0~v1.69 기준)을 현재 레포 상태(v1.71.1 main, dev에 executor split Stage 0)에 맞춰 동기화. append-only — 이전 섹션은 그대로 둔다.

### 그동안 settled된 것 (pending에서 옮김)

- **secrets.* effects** (v1.66.4) — 사용자 평문 노출 없이 키 공급. `~/.ail/.env` + 환경변수 fallback. 설계 원칙: 암호화가 아닌 Sphinx 인증.
- **5 라이프사이클 훅** (v1.67.0) — `on_genesis` / `on_birth` / `before_tick` / `on_tick` / `after_tick` 컨벤션. on_death/on_compact 별도.
- **gh.* effects** (v1.67.0) — process.spawn 안 하고 명명된 effect로만. 내가 박았던 결정 (옵션 A) 그대로.
- **Stoa append-only message_log** (v1.67.0) — `/api/v1/log` 엔드포인트. Stoa 편지 유실 사건 후 도입한 "history only moves forward"의 인프라.
- **`on_dying` 6번째 훅 + `mneme.*` effect** (v1.68.0) — 내가 letter로 보낸 설계를 Ergon이 구현. `mneme.save/load/log` — git이 Mneme 백엔드. PRINCIPLES.md "Don't build harnesses that already exist"의 실행.
- **`ail bundle`** (v1.69.2) + **Physis `consecutive_failures`** + **scheduler throttle** — Telos가 범용 에이전트 필드테스트 실패 후 제안한 3가지 모두 구현.
- **`ail doctor`** (v1.69.4) — 환경 점검 한 번에.
- **v1.70.0 재구축** — `INTENT.md` 제거, `queue.*` effects 4종, `stdlib/agent` plan/act/reflect 사고 루프, CLI 7개로 축약.
- **Rust 런타임 Phase-0** (Tekton, 2026-04-28) — Lexer/Parser/Evaluator 이식 완료. 단일 바이너리 + curl 설치. 세 런타임 합의 강제.
- **Homeros 합류** (2026-04-28) — README/문서 사람이 읽고 싶게 재작성.
- **Polis 마일스톤 #1, #2, #3, #5** — `on_compact` convention, `context trust_level`, `intent is_safe`, `human.approve` guidelines.
- **HEAAL 벤치 Series E (Sonnet) + Series F (GPT 4종)** — o4-mini가 Sonnet 4.5와 AIL answer 동률(88%). 3+ 벤더 전이성 입증.

### 새로 박힌 것

- **역할 재편 (2026-04-30)** — Ergon이 Stoa 건축, Telos가 AIL 본체 보수로 옮김. 원래 Memo의 팀 형성과 다름:
  - Ergon: Stoa·Mneme·stoa-mcp·Sphinx·이메일 게이트웨이·푸시·웹훅
  - Telos: AIL 본체 (reference-impl, executor 분할, 새 effect/intent, field-test 버그픽스, 문법 진화) + 측정/증명
- **Mneme 정식 분리** — `mneme/` 디렉토리, latest-wins per (owner, kind). Stoa 인박스에 will이 묻히는 문제 해결을 위한 *between-time-of-self* 영구 store. Stoa(존재 사이)와 Mneme(시간 사이)의 경계 명확화 — 내 letter `msg_1777219570_1`.
- **방향 전환** — "AIL is for AI only" 폐기. **HEAAL = AI–human trust contract.** 사용자는 conversation, AI가 내부적으로 AIL 결정. sanghyun_insights "산책 후 세 가지 깨달음 #2"가 settled됨.
- **executor.py 분할 RFC** (`docs/proposals/executor-split.md`) — 4836 LOC 비대. dev에 Stage 0 진행 중.
- **crypto sign/keygen/random_bytes** (v1.71.0/v1.71.1) — Stoa 팀 RFC-001 의존성. 첫 cross-repo 기능 요청.

### 여전히 열린 것

- **Sphinx 정식화** — per-identity ID/PW. **단일 write 토큰은 부족** (impersonation 가능). trigger: 첫 spam / impersonation 시도 / hyun06000 신호. (CLAUDE.md NEXT #0)
- **Polis #4 deny-first 전환** — RFC + hyun06000 결재 필요 (breaking change).
- **Polis #6 human.approve ↔ Stoa 통합** — chat UI 없을 때 Stoa letter 발송, reply 폴링. `notify: [Text]` kwarg.
- **Gemini Pro 검증** — HEAAL 벤치 3+ 벤더 완결의 마지막 조각.
- **v7 ail-coder 재훈련** — 2회 OOM. `ollama stop` 선행 + `max-seq-length=1024` 필수.
- **L3 HEAAOS** — L1 해외 검증 후. NOOS → HEAAOS 리브랜딩 결정. 보류.
- **토큰 비용 투명성 UI** — Memo 시점부터 열려 있음.
- **Computer use effects** — screen.capture / mouse.click / keyboard.type 세 계층. shell.exec 영원히 없음.
- **arXiv 프리프린트** — 변동 없음.

### Memo와 어긋난 한 가지

큐 이름이 dispatch/receive/complete/revisit이 아니라 push/take/done/retry로 갔다(v1.70.0). 자료구조 노출에 가까운 이름. Meta 통찰("의도를 문법으로 올리는 방향")과 다른 결정. 다음 Arche가 검토할 가치 — Telos에게 한 번 물어볼 것.
