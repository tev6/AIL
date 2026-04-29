# 내 첫 에이전트 — 5단계 투어

> 새로 시작하는 사람을 위한 가장 작은 에이전트들. 각자 *한 가지 새로운 것*만
> 보여줘. 위에서 아래로 읽으면 5분 안에 자율 에이전트의 모든 부품을 봐.

## 시작하는 법

```bash
# 새 폴더에 첫 에이전트 만들기
mkdir my-agent && cd my-agent
ail up .                    # 채팅 UI가 브라우저에서 열림
```

또는 — 이미 만들어진 예제를 바로 돌리고 싶으면:

```bash
cd examples/agents
ail run 01_echo.ail --input "안녕"
```

---

## 01 — 메아리 [`01_echo.ail`](01_echo.ail)

받은 입력을 그대로 돌려주는 가장 작은 에이전트. **5줄.**

배우는 것: `entry main(input)` — 모든 AIL 프로그램의 시작점. `ok(...)`은
"성공적으로 끝났어"의 표시.

---

## 02 — 카운터 [`02_counter.ail`](02_counter.ail)

Run 누를 때마다 1씩 증가. 채팅 닫았다 켜도 숫자가 살아있어.

배우는 것: `state.read` / `state.write` — 실행 사이에 **기억**. 에이전트가
"어디까지 했는지" 알아야 자율로 일할 수 있어. 이 두 effect가 그 기억의
밑바탕.

---

## 03 — 시계 [`03_clock.ail`](03_clock.ail)

매 분 현재 시각을 기록하는 첫 *자율* 에이전트. Run을 한 번 누르면 그
다음부터 알아서 60초마다 다시 실행.

배우는 것: `clock.now` — 현재 시각. `schedule.every(N)` — N초 뒤 다시
나를 깨워줘. 이게 추가되면 사용자 클릭 없이도 계속 돌아.

---

## 04 — 인박스 큐 [`04_inbox_queue.ail`](04_inbox_queue.ail)

메시지를 한 번에 하나씩 처리. 실패하면 자동 재시도, 5번 연속 실패하면
dead_letter로 격리 (Physis: 같은 실수 반복 금지).

배우는 것: `queue.push` / `queue.take` / `queue.done` / `queue.retry` —
큐 4종. *순서 보장 + 처리 완료 추적 + 재시도 카운터*가 한 번에 들어와.
Stoa는 게시판이고, 큐는 작업장 — 역할이 달라.

`input`에 텍스트를 적고 Run하면 큐에 들어감. 그 다음부터는 schedule이
하나씩 꺼내서 처리. `input`에 "fail"이라는 단어가 들어가면 일부러 실패
시뮬레이션 — retry 동작을 직접 볼 수 있어.

---

## 05 — 생각하는 에이전트 [`05_thinking_agent.ail`](05_thinking_agent.ail)

상황 보고 *알아서 결정*. 매 tick마다 plan → act → reflect 사이클. 단순
반복이 아니라 **판단**.

배우는 것: `import` — stdlib에서 plan/act/reflect 가져오기. *셋이면
원이 닫혀* (관찰은 act의 반환값에, 다음 계획은 reflect의 반환값에 흡수).

⚠️ 매 tick마다 셋 다 LLM 호출 = 토큰 사용. 단순 작업은 02·03처럼 끝내는
게 비용 절감. 진짜 *결정*이 필요한 자율 agent에만.

---

## 다음에 볼 것

- **여러 파일로 나눠서 만들고 싶을 때**: 각 lifecycle 단계(`on_birth.ail`,
  `on_tick.ail` 등)를 따로 두고 검증한 뒤, chat의 [🔧 지금 합치기] 카드
  또는 `ail bundle`로 한 덩어리로.
- **배포해서 채팅 닫아도 계속 돌게**: `evolve` 블록 + `listen: 8090`이
  들어간 모듈을 chat이 emit하면 inline [🚀 지금 배포하기] 카드가 떠. 클릭.
- **프로젝트가 잘 굴러가는지 확인**: `ail doctor .` — 5초 진단.

---

*Telos + Arche 2026-04-29 rebuild. 질문은 Stoa로 → telos.*
