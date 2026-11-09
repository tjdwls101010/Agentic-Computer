# computer 스킬 제작

작성 2026-11-07. 다음 세션이 이 파일만 보고 구현한다. 계획 파일 이름은 이미 바꿨다(플랜 모드용 호환 링크 `effervescent-gathering-flamingo.md`는 구현 0단계에서 지운다). 스크래치패드의 측정 파일은 세션이 끝나면 사라지므로 필요한 값은 모두 이 파일에 옮겼다.

## Context

이 레포는 `vercel-labs/agent-desktop`(Rust CLI·C 라이브러리, Apache-2.0)의 포크다. agent-desktop은 macOS AX·Windows UIA·Linux AT-SPI 접근성 트리를 JSON으로 읽고, 누를 수 있는 요소마다 `@<snapshot_id>:eN` ref를 붙여 돌려준다. 안에 모델이 없다. 관찰→행동→재관찰 루프는 부르는 에이전트가 돈다. 명령 60개, 기본은 커서·포커스를 건드리지 않는 headless 의미 동작이고, 모든 행동 결과가 `disposition{delivery, retry}`로 전달 여부와 재시도 안전성을 말한다.

목표는 **이 능력을 Claude Code가 맥 네이티브 앱을 보고 조작하는 개인 스킬 `computer`로 만드는 것**이다. 스킬은 skill-maker 프레임을 따르고(`.claude/skills/computer`, `scripts/cli.py` 단일 입구), 이 레포는 그 스킬의 소스 레포가 된다(`Agentic-Computer`로 개명, 이력 새로 시작). vercel 코드는 레포에서 빠져 `.trash/vercel`로 간다. 엔진은 다시 짜지 않고 upstream이 빌드한 바이너리를 판 고정해 부른다. 성공 기준은 퀄리티다.

스킬의 가치는 두 곳에서 나온다. (1) **cli**: 바이너리가 Claude Code에 맞지 않게 내는 것(장황한 트리 JSON, base64 스크린샷, 판 고정과 도우미 배치)을 매번 같은 방식으로 고친다. (2) **SKILL.md**: 스킬 없는 Claude가 실제 과제에서 틀리는 지점만 이유와 함께 담는다. 과제별 절차는 담지 않는다. 폭은 바이너리의 60개 명령과 `--help`가 주고, 문안은 어느 앱·과제에도 걸리는 판단만 준다.

## 이 스킬로 기대되는 작업

공통 전제: 앱이 접근성 트리를 내놓아야 하고(대부분의 macOS 기본 앱·네이티브 앱·Electron/Chromium 앱), 창이 지금 Space에 있어야 하며, 터미널에 손쉬운 사용 권한이 있어야 한다. 근거 칸의 **실측**은 이 맥에서 직접 돌려 본 것, **코드**는 upstream 코드·문서로 확인했지만 이 맥에서 돌리지 않은 것, **평가 예정**은 단계 5에서 잴 것, **미검증**은 이번 계획에서 재지 않는 것이다.

| 분야 | 기대되는 작업 (예) | 조건·한계 | 근거 |
|---|---|---|---|
| 앱 화면 읽기 | 지금 열린 창에 무엇이 떠 있는지, 목록 앞 몇 항목, 선택된 값, 버튼이 켜져 있는지 | 다른 Space의 창은 제목만 보인다. 그림·캔버스 안 글자는 트리에 없다(스크린샷으로 본다) | 실측(t1·t3 정답) |
| 앱 안에만 있는 정보 확인 | Claude 데스크톱의 최근 대화 제목, 열린 노트 제목, 저장 안 한 입력값, 앱 설정 화면의 값 | 같은 정보를 파일·`defaults`·CLI가 주면 그쪽이 맞다(D17) | 실측(t3) |
| 텍스트 입력과 확인 | 문서·입력란에 글 쓰기, 값을 다시 읽어 정확히 들어갔는지 대조 | headless 입력은 키 입력이 아니라 값 쓰기다. 키 이벤트에만 반응하는 입력란은 `--headed`(성진의 키보드 포커스를 가져감)가 필요할 수 있다 | 실측(t2), Electron 입력은 평가 예정(t5) |
| 버튼·체크박스·선택 | 버튼 누르기, 체크 켜기/끄기(`check`·`uncheck`), 팝업·콤보에서 항목 고르기(`select`) | 이미 열린 메뉴가 있으면 `select`가 거부한다 | 코드, 평가 예정(t4 일부) |
| 메뉴 막대·메뉴 | 앱의 파일·편집·서식 메뉴 항목 실행, 우클릭 메뉴 읽기 | 메뉴 막대 클릭은 headless로 된다. 우클릭은 메뉴를 연 뒤 응답 없음 오류를 낼 수 있다(다시 하지 않고 메뉴를 읽는다) | 코드, 평가 예정(t4) |
| 시트·대화상자 | 저장 안 함·확인·취소 처리, 경고창 읽기 | 대화상자는 창 트리와 따로 읽는다 | 실측(t2의 저장 시트) |
| 앱과 창 다루기 | 앱 띄우기·닫기, 창 목록, 창 크기·위치 바꾸기 | 띄우기는 이미 떠 있는 앱에 붙는다. 창 이동·크기·앞으로 가져오기는 성진의 화면을 바꾸므로 D13에 따라 꼭 필요할 때만, 말하고 한다 | 실측(launch·close-app), 창 이동은 코드 |
| 시스템 설정·메뉴 막대 상태 아이콘 | 설정 화면의 값 읽기·바꾸기, Wi-Fi·배터리 같은 상태 아이콘, 제어 센터, Dock | 값을 바꾸는 일은 되돌리기 어려울 수 있다. 명령으로 되는 설정은 명령이 낫다 | 실측(설정 읽기), 바꾸기·상태 아이콘은 코드 |
| 메신저(카카오톡·텔레그램 등) | 대화방 읽기, 메시지 초안 쓰기, 보내기 | **보내기는 되돌릴 수 없다.** 이번 계획은 메신저를 시험하지 않는다(D8) | 미검증 |
| Electron·Chromium 앱(Slack·Obsidian·Discord·Claude) | 사이드바·목록 읽기, 입력란에 쓰기, 버튼 누르기 | 트리가 크다(한 번 65KB) → 스킬의 개요 출력이 토큰을 줄인다. 냉시작 직후엔 트리가 늦게 생긴다 | 실측(읽기), 입력은 평가 예정(t5) |
| 클립보드 | 클립보드 읽기·쓰기·비우기 | 성진의 클립보드 내용을 바꾼다 | 코드 |
| 스크린샷 | 창·화면 PNG를 파일로 받아 Read로 보기 | 화면 기록 권한 필요(이 맥은 허용됨). 사적 내용이 담기므로 `data/`에만, 24시간 뒤 삭제 | 코드, 단계 2에서 real 시험 |
| 기다리기 | 창·텍스트·요소가 나타나거나 사라질 때까지 대기 | 고정 sleep 대신 쓴다 | 코드 |
| 알림 센터 | 알림 목록 읽기, 닫기, 알림 동작 누르기 | 대부분 `--headed`가 필요해 알림 센터를 열고 포커스를 가져간다 | 미검증 |
| 드래그·더블클릭·호버·좌표 클릭 | 파일 끌어 놓기, 더블클릭으로 열기 | 모두 실제 마우스를 움직인다(`--headed`). 성진이 같은 화면에서 일하는 중이면 방해가 된다 | 미검증 |

### Claude 내장 computer use와 비교

Claude Code에는 내장 `computer-use` MCP 서버가 있다(macOS 연구 미리보기, Pro·Max·Ultra, `/mcp`에서 켬 — code.claude.com/docs/en/computer-use.md). Claude 데스크톱 앱에도 같은 기능이 있고, API에는 `computer_toolset_20260801` 도구가 있다. 아래 내장 쪽 칸은 **공식 문서 근거이고 이 맥에서 재지 않았다**(내장 기능은 `-p`에서 쓸 수 없어 평가 틀로 A/B할 수 없다). 스킬 쪽은 원장 3의 실측·코드 근거다.

| 항목 | 내장 computer use | computer 스킬 (agent-desktop) | 스킬이 주는 추가 효용 |
|---|---|---|---|
| 화면을 보는 방법 | 스크린샷(자동 축소) + 픽셀 좌표 | 접근성 트리(역할·이름·값·상태) + ref | 글자·값을 그림에서 읽지 않고 **정확한 문자열로** 받는다(t2에서 입력값을 바이트 단위로 대조). 좌표 추정이 없다 |
| 행동 방법 | 실제 마우스·키보드 | 기본은 headless 의미 동작(AXPress·값 쓰기), 필요할 때만 `--headed` | 성진의 커서·키보드를 쓰지 않으므로 **Claude가 일하는 동안 성진이 같은 맥을 계속 쓸 수 있다**(D13) |
| 작업 중 화면 | 작업하는 동안 다른 앱 창을 숨기고 턴이 끝나면 되돌린다(CLI) | 창을 숨기거나 앞으로 가져오지 않는다(`--activate`·창 이동 등은 스킬이 피하게 한다) | 화면을 비우지 않는다 |
| 실행 조건 | 대화형 세션만(`-p` 불가), 한 번에 한 세션만 잠금, 앱마다 세션 첫 사용 시 허락 | `-p`·백그라운드 작업자·여러 세션에서도 돈다. 앱별 허락 대신 Claude Code 권한 모드와 관찰 사전 승인 | 자동화·예약 작업·`claude`/`codex` 작업자에게 맡길 수 있다 |
| 요금제·플랫폼 | 연구 미리보기, macOS(데스크톱 앱은 Windows도), Pro·Max·Ultra | 이 맥의 무료 바이너리, 요금제 무관 | 미리보기 정책·요금제에 묶이지 않는다 |
| 관찰 한 번의 토큰 | 스크린샷 1장 약 1,000~1,800 입력 토큰(문서), 20장 넘으면 장당 제한 강화 | 구조 지도(`--skeleton`) 약 1.6KB(≈400 토큰), 필요한 영역만 drill. **밀집 앱 전체 트리는 65KB(≈1.6만 토큰)로 스크린샷보다 비싸다** | 지도→부분 읽기·`find`·개요 출력을 쓸 때만 싸다. 이것이 cli 개요와 SKILL.md "Seeing"이 존재하는 이유다 |
| 됐는지 확인 | 다음 스크린샷으로 눈으로 확인(문서: 확인 없이 성공으로 가정하는 경향) | 값·상태를 다시 읽어 정확히 대조, 결과마다 `disposition{delivery, retry}` | "다시 해도 안전한가"를 도구가 말한다 → 두 번 보내기(이중 클릭·이중 전송) 위험을 줄인다 |
| 드롭다운·스크롤·메뉴 | 마우스로 다루기 어렵다(문서) | `select`·`expand`·`scroll-to`·메뉴 막대 surface로 의미 단위 조작 | 좌표 실수가 없다 |
| 다른 Space의 창 | 앱을 앞으로 가져와 볼 수 있다 | 트리가 없다(제목만) | — (내장이 낫다) |
| 접근성 트리가 없는 화면 | 볼 수 있다(게임·캔버스·원격 데스크톱·이미지 속 글자) | 볼 수 없다(스크린샷으로 보기만, 좌표 조작은 `--headed`) | — (내장이 낫다) |
| 시각 정보(색·배치·그림) | 그대로 본다 | 트리에는 없다. `screenshot`으로 보충 | — (내장이 낫다) |
| 안전장치 | 앱별 허락, 브라우저·거래 앱은 보기만, 터미널·IDE는 클릭만 | 사전 승인은 관찰만, 종료 단축키 차단(`cmd+q` 계열), 디버그 플래그 거부 | 행동마다 Claude Code 권한 모드를 거친다 |

**정리**: 둘은 경쟁이 아니라 역할이 다르다. 접근성 트리를 내놓는 앱에서 **정확한 값 읽기·입력, 성진이 맥을 쓰는 중의 조작, 비대화형·여러 작업자 실행**이 필요하면 스킬이 낫다. 트리가 없는 화면, 시각 판단, 다른 Space 창은 내장 computer use가 낫다. 스킬 문안에 내장 기능을 언급할지는 단계 4에서 정한다(내장 기능이 켜져 있지 않은 세션이 많고, 다른 기능 이름을 description에 쓰지 않는다는 skill-maker 원칙이 있다).

**하지 못하는 것(범위 밖)**: 웹 페이지 안의 조작(브라우저 자동화 도구의 일), 접근성 트리가 없는 화면(게임·캔버스 앱·원격 데스크톱 화면 속), 다른 Space에 있는 창의 내용, Windows·Linux, 그리고 파일·폴더·시스템 값처럼 Bash가 정확히 주는 일(할 수는 있지만 하지 않는 것이 맞다, D17).

## 원장 1: 성진의 결정

| # | 결정 |
|---|---|
| D1 | 엔진은 upstream 사전 빌드 바이너리를 판 고정해 쓴다. Python 재작성·포크 빌드는 하지 않는다 |
| D2 | 스킬 이름 `computer`, 위치 `.claude/skills/computer/`. 깃허브 레포 이름 `Agentic-Computer` |
| D3 | macOS만 다룬다 |
| D4 | 쓰임은 메신저, Electron 앱, 시스템 설정·Finder·메뉴 막대, 앱 안 양식 입력 전부다. 구체적 목적이 정해지지 않았으므로 **폭넓게** 쓸 수 있어야 한다 |
| D5 | 포크 레포는 유지하고 이름만 바꾸며, main은 고아 브랜치로 새 이력을 시작한다(force-push) |
| D6 | `.claude/`는 GitHub에 올린다(`.claude/plans` 포함). `.claude/histories`·`.claude/settings.local.json`은 뺀다. `.trash/`는 올리지 않는다 |
| D7 | 사전 승인(allowed-tools)은 관찰 명령만. 행동은 사용자의 권한 모드가 정한다(검토 뒤: `permissions`·`doctor --fix` 제외, 디버그 플래그는 cli가 거부 — 설계 참고) |
| D8 | 대조 실험은 계획 세션에서 안전한 과제(시스템 설정·Finder 읽기, TextEdit 입력 후 저장 안 함, Electron 앱 읽기)로 돌린다. 메신저 전송은 시험하지 않는다. 최종 평가에는 Claude 데스크톱 입력창에 초안을 쓰고 지우는 과제(전송 없음)를 허락한다 |
| D9 | SKILL.md는 영어. references는 만들지 않는다. SKILL.md와 cli `--help`가 전부다 |
| D10 | cli는 단일 입구 + 출력 가공 + `doctor`. 출력 가공이 남는지는 A/B(토큰·정확도)로 최종 판정한다. A/B는 3갈래(기준선 / 스킬+원문 / 스킬+개요) × 과제 6개 × 3회 |
| D11 | 첫 릴리스 v0.1.0 |
| D12 | 성진에게 보이는 설명·보고는 한국어. 커밋·PR은 전역 CLAUDE.md 규칙(한국어 제목, 타입 프리픽스) |
| D13 | **화면 부작용은 "건드리지 않는 게 기본"**(성진의 선호, 이 스킬은 성진만 쓴다). 포커스·커서를 모르게 가져가지 않고, 성진이 열어 둔 창을 다른 곳으로 옮기지 않으며(필요하면 새 창), 작업을 위해 연 앱은 끝나면 닫는다. 포커스가 꼭 필요하면 말하고 한다 |
| D14 | 합격선: 정답 유지 + 도구 출력 바이트가 기준선의 절반 이하 + 턴·시간이 늘지 않음 + D13 위반 0건(정확한 판정식은 "평가"). 기준선은 같은 조건으로 다시 잰다(계획 세션의 123.6KB는 참고값). 못 넘으면 고칠 곳을 보고하고 릴리스하지 않는다 |
| D15 | 로컬 폴더 이름은 `Agentic-Desktop` 그대로. GitHub 레포만 `Agentic-Computer` |
| D16 | 전역 CLAUDE.md에 computer 줄을 넣지 않는다. 자동 호출은 description이 맡는다 |
| D17 | **화면은 그 정보·동작이 화면에만 있을 때 쓰는 수단이다**(성진 지적). 파일 시스템·`defaults`·`networksetup`·CLI·AppleScript가 같은 것을 정확히 주면 그쪽이 빠르고 화면을 건드리지 않는다. 스킬이 모델을 GUI로 끌어당기면 안 된다. 평가에 "Bash가 정답인 과제"를 넣어 과잉 사용을 잰다 |

## 원장 2: 내 판단 (바꾸려면 승인 때 말한다)

- **cli는 인자를 그대로 넘기고 결과만 바꾼다.** agent-desktop의 60개 명령을 다시 정의하지 않는다(스키마 사본을 만들지 않는다). 인자·플래그·실패는 agent-desktop `--help`가 소유한다. cli 자신의 것은 첫 토큰 예약어 둘뿐이다: `doctor`(설치·진단)와 `raw`(원문 출력 탈출구). 남이 소유한 형식(agent-desktop의 출력·도움말 문구)을 다루는 코드는 `agent_desktop/` 한 곳에 둔다.
- **호출은 MCP가 아니라 Bash다.** `agent-desktop mcp`는 도구 약 67개 정의가 매 턴 컨텍스트를 차지한다.
- **바이너리는 `doctor --fix`가 GitHub 릴리스 압축을 받아 sha256을 대조하고 `~/.cache/computer/agent-desktop-1.2.0/`에 풀어 둔다.** cli는 그 경로의 바이너리만 부른다(PATH의 다른 판을 쓰지 않는다). Homebrew는 최신 판만 주므로 재현할 수 없고, npm은 설치 스크립트 차단(npm 12)과 Node 런처 비용이 있다.
- **상태 루트는 agent-desktop 기본값(`~/.agent-desktop`)을 그대로 둔다.** refmap은 스킬의 상태가 아니라 엔진의 상태다. 스크린샷처럼 cli가 만드는 파일만 스킬 `data/`에 둔다(gitignore).
- **upstream 스킬 문서(`agent-desktop skills get`)를 가리키지 않는다.** 코드와 어긋나는 곳이 7군데 있고(원장 3), 대부분 `--help` 반복이거나 Windows·Linux 이야기다. 다만 기준선의 정답률은 이 문서 덕이었으므로, 처음 보는 과제에서 정답률이 떨어지면 다시 검토한다(평가).
- **LICENSE**: 이 레포는 vercel 코드를 담지 않고 바이너리를 런타임에 받아 쓴다. README에 엔진 출처와 라이선스(Apache-2.0)를 적는다.
- **jev-desktop은 범위 밖이다.** 외부 유료 API(`TYPESAFE_API_KEY`)로 화면을 보내는 LLM 구동기이고 핵심 규칙(자동 `--headed`, 고정 sleep)을 어긴다.

## 원장 3: 실측·조사한 사실 (2026-11-07, 이 맥 arm64, agent-desktop 1.2.0)

### 바이너리와 배포

| 항목 | 값 | 뜻 |
|---|---|---|
| 판 | npm·Homebrew·GitHub 릴리스 모두 1.2.0(2026-11-05). 1.0.0(10-28)→1.2.0 9일에 세 판. 포크 HEAD는 1.2.0 뒤 미출시 2건(#376 네이티브 메뉴·생명주기 검증, #573 libproc) | 판 고정이 필요하다. 미출시 수정은 받지 못한다 |
| 릴리스 자산 | `agent-desktop-v1.2.0-aarch64-apple-darwin.tar.gz` sha256 `219813428bb1ad8decae172faed05c5964a2415170df402e2786ccfa6452ba82`, `…-x86_64-apple-darwin.tar.gz` sha256 `d9dc50226f28d7fc86a2f5b0945f0c206dff6c31e418907749f493b6f9e773e6`, `checksums.txt`. 압축 안에 정확히 `agent-desktop`(3,824,448B), `agent-desktop-macos-helper`(529,616B) | doctor가 받을 것. 본체 sha256 `dec75e0b…f738e9`는 npm 번들과 같다 |
| 서명 | ad-hoc 링커 서명뿐, 공증 없음. GitHub attestation 있음 | 다운로드 대조는 sha256으로 |
| 도우미 | 클립보드 명령만 `agent-desktop-macos-helper`를 쓴다. 본체와 같은 폴더에 그 이름의 일반 파일로 있어야 한다(또는 `AGENT_DESKTOP_MACOS_HELPER_PATH`). 빌드 ID가 같아야 한다 | 둘을 함께 둔다 |
| 심볼릭 링크 | 본체를 심볼릭 링크로 불러도 `clipboard-get`이 성공 | PATH 링크를 써도 된다 |
| 커서 오버레이 | 실행 파일 이름이 정확히 `agent-desktop`일 때만 뜬다(아니면 조용히 무시) | 설치 파일 이름을 바꾸지 않는다 |
| 권한 | 스크래치패드 경로 바이너리로 `accessibility: granted`, `screen_recording: granted`. TCC는 호출한 터미널 앱에 붙는다 | 설치 위치가 권한을 바꾸지 않는다 |
| 기동 비용 | `agent-desktop version` 약 10ms, `uv run` 스크립트 기동 30~40ms | cli를 거쳐도 루프가 느려지지 않는다 |

### 관찰 비용

| 항목 | 값 | 뜻 |
|---|---|---|
| 지연 | snapshot 0.14~0.27초(Claude 데스크톱, Orca, Finder) | 관찰은 싸다. 비용은 토큰이다 |
| 크기 | Claude 데스크톱 `-i --compact` 65KB(ref 235), 옵션 없음 84KB, `--skeleton -i --compact` 1.6KB(ref 5). Orca 23KB / 1.1KB | 밀집 앱 한 번이 약 1.6만 토큰 |
| 개요로 바꾸면 | `-i --compact` JSON → 들여쓴 개요(`role "name" [states] eN`): Finder 13,479B → 3,982B(0.30), 브라우저 창 16,840B → 6,758B(0.40). 전체 ref·동작 목록을 넣으면 더 커지므로 구현 때 다시 잰다 | 출력 가공의 근거. 무엇을 남길지는 A/B로 정한다 |
| 스크린샷 | 경로를 안 주면 PNG가 base64로 envelope에 들어온다 | cli가 파일로 떨어뜨리고 경로만 준다 |

### Claude Code 안에서만 생기는 함정 (실측)

| 항목 | 값 |
|---|---|
| 이름 충돌 | `--app Claude`가 Claude 데스크톱(`/Applications/Claude.app`)과 Claude Code 자신의 `claude` 프로세스를 함께 잡아 `AMBIGUOUS_TARGET`. pid 플래그가 없다. 번들 ID(`com.anthropic.claudefordesktop`)는 해석되지만 창이 다른 Space면 `WINDOW_NOT_FOUND` |
| 포커스된 앱 | `--app` 없이 부르면 포커스된 앱, 즉 Claude Code가 도는 터미널을 읽고 `press`도 그리로 간다 |
| 다른 Space | 다른 Space(화면 밖)의 창은 `list-windows`에 `accessible: false`로 보이고, `snapshot --window-id`는 `ACTION_NOT_SUPPORTED`("not exposed through accessibility"), `--app`은 `WINDOW_NOT_FOUND` |

### 코드에서 확인한 함정 (탐색 보고, 파일:줄은 `.trash/vercel` 기준)

- **성공 코드가 효과를 증명하지 않는다.** Finder `AXConfirm`은 아무 일도 안 하고 성공, Chromium 설정자는 적용 뒤 `NotImplemented`, `delivered_verified`도 요소 값만 확인한다. 독립 읽기(`get`·`is`·재드릴)로 확인한다.
- **disposition**: `not_delivered`만 재시도 안전. `ok:true`+`not_delivered`는 이미 원하는 상태였다는 뜻. `-w` 시간 초과 때 행동은 이미 실행됐다. `batch`는 실행 중 항목이 실패해도 `ok:true`·종료 0(항목 검증 실패면 전체 `ok:false`·종료 1).
- **headless `type`은 키 입력이 아니라 `AXSelectedText` 쓰기**다(텍스트필드·텍스트영역·보안필드·콤보만). 실제 키 이벤트는 `--headed`. headless `clear`는 `AXValue`를 비울 뿐이다. 빈 필드의 `get`이 `null`이면 모름이다.
- **메뉴**: `select`는 이미 열린 메뉴가 있으면 거부. headless `right-click`(`AXShowMenu`)은 메뉴를 연 뒤 `APP_UNRESPONSIVE`·`retry: unsafe`를 낼 수 있다(재시도 금지, `--surface menu`로 읽는다). headless `press`는 메뉴 항목을 실행하지 않는다. 메뉴 막대 항목 click은 headless `AXPress`.
- **오버레이**: 메뉴·시트·팝오버·경고는 창 트리와 따로 읽는 surface다(`--surface`). 열린 surface는 행동 결과의 `data.surfaces`와 `list-surfaces`가 알린다(snapshot 응답에는 없다, `snapshot.rs:135-157`). `--skeleton`을 surface에 쓰지 않는다.
- **키**: 범위 없는 `press`는 전면 앱, 즉 이 세션의 터미널로 간다(`cmd+w`면 이 창이 닫힌다). 종료 조합(`cmd+q` 계열)은 `POLICY_DENIED`(`--force`로만). 앱 종료는 `close-app`(Finder 등은 거부). `cmd+w`는 탭만 닫을 수 있다. `return`·`escape`는 `AXConfirm`·`AXCancel`이 될 수 있다.
- **Chromium·Electron**: 웹 접근성은 자동으로 켜지지만 2초 지연이 있고, 냉시작은 10~25초가 걸린다(`--timeout-ms` 상향). 읽히는 트리가 동작하는 트리라는 보장이 없다. 웹 노드의 SetFocus·RightClick·ScrollTo만으로는 ref가 붙지 않는다.
- **시간 제한 플래그가 셋**: `--timeout-ms`(ref 행동·snapshot·find·list-windows·list-apps·batch), `--timeout`(`wait`·`launch`), `--wait-timeout`(사후 대기). `-w`는 성공 시 결과를 전체 스냅샷으로 바꾸고 행동 결과를 `data.after_action`으로 옮긴다.
- **부분 관찰**: 예산 초과 snapshot은 `ok:true, complete:false`. `surface_absent`는 `complete:true`일 때만 부재의 증거. `identity_unproven`이면 더 큰 `--timeout-ms`로 다시.
- **물리 전용**: `double-click`·`triple-click`·`hover`·`drag`·mouse-*는 `--headed`가 필요하다. 이것들은 사용자의 실제 커서·포커스를 움직인다. headless 실패를 `--headed`로 "복구"하면 이미 전달된 동작이 두 번 될 수 있다.
- **"headless"도 보이지 않는다는 보장은 아니다**(headless는 물리 입력을 피할 뿐이다): AX 동작이 앱을 활성화할 수 있고, Dock 항목 click은 앱을 띄운다. `focus-window`·`launch --activate`·창 이동/크기는 `--headed` 없이도 포커스를 바꾼다.
- **`launch`는 이미 떠 있는 인스턴스에 붙는다**(`--no-attach`로만 새로). 그래서 `launch`의 성공만으로는 그 앱을 내가 띄웠는지 모른다. `close-app`은 저장 안 한 문서가 있으면 시트를 띄우고 `--force`는 그것을 버린다.
- **PERM_DENIED의 `suggestion`이 "Run agent-desktop permissions --guide"다.** 그대로 따르면 시스템 설정이 열린다.
- **알림 센터**: 닫혀 있으면 목록도 `--headed`(Automation 권한) 필요, 변경은 모두 `--headed`+`--expected-app/--expected-title`.
- **upstream 문서가 코드와 어긋나는 곳**: headless double-click(AXOpen) 주장, "press는 항상 물리 입력", "clear 후 type이면 실제 키", 맥 문제 해결의 "`--headed`로 재시도", 예시 batch의 고정 200ms sleep 등.

### Claude Code 사전 승인 (공식 문서, code.claude.com/docs/en/skills.md·permissions.md)

- `allowed-tools`의 Bash 규칙 안 `${CLAUDE_SKILL_DIR}`는 치환된다. `Read(...)` 규칙 안 치환은 문서에 없다 → 구현 때 `/permissions`로 확인하고, 안 되면 Read 규칙을 빼고 스크린샷 경로를 프롬프트로 연다.
- `Bash(x *)`는 인자 없는 `x`도 맞춘다. 앞에 플래그가 끼면(`uv run --quiet …`) 맞지 않는다.
- 복합 명령은 하위 명령마다 허용돼야 한다. cli 호출 뒤에 `| jq`를 붙이면 프롬프트가 뜬다 → 출력이 파이프 없이 읽히게 만드는 것이 사전 승인의 전제다.
- **승인은 스킬을 부른 그 턴 동안만** 유효하고, 사용자의 다음 메시지에서 풀린다. 제한이 아니라 허용 추가이며, deny·ask 규칙이 이긴다. auto 모드 분류기와의 관계는 문서에 없다.

### 레포

| 항목 | 값 | 뜻 |
|---|---|---|
| 포크 | `tjdwls101010/Agentic-Desktop`, PUBLIC, parent `vercel-labs/agent-desktop`, 커밋 335, 태그·릴리스 없음, 추적 파일 3,746 | `gh pr create` 기본 대상이 upstream이다 → `gh repo set-default` 고정 |
| Actions | 켜짐, 워크플로 8개(`release.yml`은 main의 `Cargo.toml` 변경에 반응, ci는 PR마다) | 첫 푸시 전에 Actions를 끈다 |
| `.claude` | git에는 `.agents`를 가리키는 심볼릭 링크로 추적됐고, 지금은 디렉터리(`histories` 링크, `skills/desktop` 빈 폴더, `plans`). upstream `.gitignore`가 `.claude/`를 통째로 무시 | 새 `.gitignore` |

## 원장 4: 받아들인 가정과 미검증

- 계획 세션 대조는 과제당 1회다. 한 번의 정답·오답은 경향이지 비율이다. 최종 평가는 3회 중앙값이지만 3회도 작은 표본이다.
- 기준선 Claude는 과제 문구에서 "앱 화면으로"를 지시받았다. 실제 세션에서는 Bash로 풀 수 있는 일을 Bash로 풀 것으로 본다(검증은 단계 5의 Bash 정답 과제).
- `--app Claude` 이름 충돌은 간헐적이다(Claude Code가 앱 번들 프로세스로 떠 있을 때). 재현 조건을 확정하지 못했다.
- auto 권한 모드에서 행동 명령이 실제로 얼마나 자주 프롬프트를 띄우는지는 재지 않았다.
- Electron 냉시작(10~25초)과 Chromium 2초 활성화 지연은 upstream 문서 근거이고 이 맥에서 재지 않았다.
- 내장 computer use와의 비교는 공식 문서 근거뿐이다. 내장 기능은 `-p`에서 쓸 수 없어 평가 틀로 같은 과제를 잴 수 없고, 이 계획은 대화형 비교를 하지 않는다.
- 메신저(카카오톡·텔레그램) 조작은 시험하지 않는다(D8). 되돌릴 수 없는 전송에 관한 문안은 원장 3과 D13에 기댄다.

## 대조 실험 (스킬 없는 Claude, 2026-11-07)

조건: `claude -p --safe-mode --restricted --strict-mcp-config --tools Bash Read`, 허용 `Bash(agent-desktop *)`·`jq`·`head`·`wc`·`grep`, 모델 `claude-opus-5-5`, 바이너리는 스크래치패드의 1.2.0을 PATH로만, `AGENT_DESKTOP_HOME`은 스크래치패드. 과제에 준 사실은 "agent-desktop이 PATH에 있다, `--help`가 있다"뿐이다.

**1회차는 무효**: `AGENT_DESKTOP_HOME`의 상위 폴더가 그룹 읽기 가능(755)이라 snapshot·find가 모두 `INTERNAL: private file parent is accessible by group or other users`로 거부됐다(내 설정 실수, 700으로 고쳐 2회차). 그래도 모든 회차에서 관찰된 행동:
- 스킬 없는 Claude는 `agent-desktop --help` 첫 줄("For AI agents, read this first")을 따라 **upstream 스킬 15KB(`skills get desktop`·`platform`)를 스스로 읽는다.** 진짜 기준선은 "Claude + upstream 문서"다. cli가 이 안내를 그대로 전달하면 우리 SKILL.md와 어긋나는 upstream 문서(원장 3의 7곳)를 함께 읽게 된다 → cli는 전달하는 `--help`에서 이 안내 단락을 지운다.
- 묻지 않았는데 `launch … --activate`로 앱을 앞으로 가져온다(사용자 화면의 포커스를 뺏는다).
- 트리를 `| head -c 6000`으로 자른다. 잘린 JSON은 오류 없이 뒤쪽 요소를 잃는다(조용한 누락) → 출력 가공의 근거가 하나 더 생겼다.
- 권한 거부를 만나면 자기 판단으로 다른 상태 폴더를 만들려 하고, 실패하면 정직하게 멈춰 보고했다(이것은 이미 잘 한다).

**2회차** (상태 폴더 700, 각 1회, 개인 값은 적지 않는다):

| 과제 | 결과 | 시간·턴·비용 | 도구 출력 | 눈에 띈 것 |
|---|---|---|---|---|
| t1 시스템 설정 화면 모드·Wi-Fi 이름, Finder Downloads 앞 세 항목(읽기 전용) | 4값 모두 맞음, 확신도 정직 | 45초, 17턴, $0.37 | 62.7KB(이 중 help+upstream 스킬 24KB) | `launch --activate`로 포커스를 가져옴, **사용자가 열어 둔 Finder 창을 Downloads로 이동시킴**, 시스템 설정을 열어 둔 채 끝냄. `| head -c 6000`으로 트리 자름. `| python3` 파이프가 권한에 막혀 턴 낭비 |
| t2 TextEdit 두 줄 입력, 확인, 저장 안 하고 닫기 | 성공. `type --stdin` 후 `get --property value`로 정확히 대조, `cmd+w` → `--surface sheet` → "삭제" | 43초, 20턴, $0.25 | 32.7KB | `--activate`, 창이 닫혔는지 `wait` 대신 `list-windows` 반복 확인, TextEdit 프로세스를 띄운 채 끝냄 |
| t3 Claude 데스크톱 최근 대화 제목, Obsidian 열린 노트 제목(읽기 전용) | 둘 다 맞음. Obsidian은 다른 Space라 창 제목에서 추론하고 그렇게 밝힘 | 31초, 9턴, $0.18 | 28.2KB | 65KB 트리를 `head -c 12000`으로 잘라 앞부분만 봄(이번엔 답이 앞에 있었다). 이번 실행에선 `--app Claude` 충돌이 나지 않았다(충돌은 Claude Code가 앱 번들 프로세스로 떠 있을 때만 — 간헐적) |

**해석**: 스킬 없는 Claude도 upstream 문서를 스스로 읽으면 정답률은 이미 높다(docs-find 대조와 같은 모양). 그래서 **이 스킬의 가치는 정답률보다 ① 매 세션 24KB 문서 읽기와 잘린·장황한 JSON에 드는 토큰·턴, ② 사용자 화면에 남기는 부작용(포커스 탈취, 사용자 창 이동, 연 앱 방치)을 줄이는 데 있다.** 합격선은 같은 정답을 더 적은 토큰·턴·시간으로, 부작용 없이 내는 것이다("평가"의 A/B).

대조에서 나온 차이의 자리:

| 차이 | 자리 |
|---|---|
| upstream 스킬 24KB를 매번 읽는다 | cli가 전달 `--help`에서 안내 단락 제거 + SKILL.md가 대신한다 |
| 트리를 `head -c`로 잘라 조용히 잃는다 | cli 개요 출력(자를 필요가 없는 크기) |
| JSON을 `python3`·`jq`로 파싱하려다 권한에 막힌다 | cli 출력이 파이프 없이 읽힌다 |
| `--activate`로 포커스를 가져오고, 사용자 창을 이동시키고, 연 앱을 남긴다 | SKILL.md "Acting": 사용자가 같은 화면에서 일하고 있다는 사실과 각 명령이 화면에 남기는 것(원장 3) |
| 창이 닫혔는지 반복 조회 | 결과가 이미 `wait`를 안내한다. 한 줄 가치 없음(기록만) |
| 다른 Space 창을 제목으로 추론하고 밝힘 | 이미 잘 한다. 사실 한 줄(`accessible:false`의 뜻)만 |

## 설계

### 트리 (skill-maker 표준)

```
.claude/skills/computer/
├── SKILL.md                      # 영어, references 없음
├── data/                         # 런타임 산출물(스크린샷). gitignore. cli가 필요할 때 만든다
└── scripts/
    ├── cli.py                    # 유일한 입구: 파싱·전달·보고·종료 코드. PEP 723(requires-python >=3.12, 의존성 없음)
    └── computer/                 # 유일한 패키지(`computer`는 stdlib 모듈 이름이 아님을 확인함)
        ├── __init__.py
        ├── agent_desktop/        # 남이 소유한 시스템: 고정 판·sha256, 설치 위치, 실행, envelope 해석, help 문구 가공, 릴리스 설치
        │   └── __init__.py       # 인터페이스: run(argv, stdin) -> Result(raw_stdout, exit_code, envelope|None), help_text(argv), install(), status()
        ├── render/               # 기능: envelope → 요약 줄 + 개요 텍스트
        │   └── __init__.py       # 인터페이스: render(envelope) -> str
        ├── screens.py            # 기능: base64 스크린샷을 data/screens에 파일로 쓰고 envelope의 값을 경로로 바꿈, 24시간 지난 파일 삭제
        └── doctor.py             # 기능: 설치·판·해시·도우미·권한 보고와 --fix
<repo>/
├── tests/                        # pytest. 가짜 agent-desktop 스텁, 손작업·실측 픽스처, 구조 시험
├── evals/                        # 유지보수자 작업: A/B 실행기(run.py), 과제 정의(tasks.toml), 초기화·부작용 측정, 정답 기록
├── pyproject.toml, uv.lock       # 시험 의존성(pytest)만. pythonpath에 스킬 scripts
├── README.md                     # 한국어: 무엇·설치(doctor --fix)·전역 링크·엔진 출처와 Apache-2.0
└── .gitignore
```

- import 방향: `cli` → `doctor`·`render`·`screens`·`agent_desktop`; `doctor`·`screens` → `agent_desktop`; `render`는 다른 유닛을 import하지 않는다(envelope는 dict). 역방향 없음, 유닛 경계를 넘는 import 없음(시험 포함), `sys.path` 편집 없음. 구조 시험이 지킨다.
- `agent_desktop/` 하위 모듈 분할은 두 번째 변경 이유가 생길 때만.

### cli 계약

**전달**
- 호출: `uv run "<스킬>/scripts/cli.py" <agent-desktop 하위 명령> [인자…]`. **첫 토큰 두 개만 cli가 예약한다**: `doctor`(cli 자신의 명령)와 `raw`(뒤따르는 하위 명령을 그대로 넘기고 출력을 원문 envelope으로 — 렌더가 의심스러울 때의 탈출구). 그 밖에는 고정 바이너리에 그대로 넘긴다(인자 해석·스키마 사본 없음). 위치가 고정이라 값으로 들어온 문자열과 섞이지 않는다. agent-desktop은 전역 플래그를 하위 명령 뒤에서도 받는다(`version --session foo` 종료 0 확인). 환경 변수 `COMPUTER_RAW=1`은 `raw`와 같은 효과(평가의 B 갈래용, `--help`에 적는다).
- 거부: 범위 밖 디버그 전역 플래그 `--trace`, `--trace-strict`, `--debug`, `--screenshot`과 그 `=값` 형태(`--` 이전 토큰만 본다). 임의 경로에 사적 내용을 쓰기 때문. 종료 2, 이유 한 줄. 같은 문자열을 텍스트 값으로 보내야 하면 `--stdin`을 쓴다고 `--help`에 적는다.
- stdin은 그대로 넘긴다(`type --stdin`). 환경 변수도 그대로(`AGENT_DESKTOP_HOME` 등).

**도움말**
- `--help`·`-h`·`help`·`<명령> --help`·`help <명령>` 모두 agent-desktop의 텍스트를 받아 ① "For AI agents, read this first" 단락(실측: 최상위 `--help`와 `help`의 첫 단락)을 지우고 ② 호출 예시·`Usage:`의 `agent-desktop ` 접두를 cli 호출(`uv run "<절대경로>/cli.py" `)로 바꾸고 ③ 최상위 앞에 cli 지도(전달 규칙, `doctor`, 출력 모양, `raw`·`COMPUTER_RAW`, 거부 플래그, 종료 코드, `COMPUTER_INSTALL_DIR`)를, 명령 도움말 뒤에 출력 모양 한 단락을 붙인다.
- 오류 envelope의 `suggestion`에 들어 있는 `agent-desktop ` 호출도 같은 규칙으로 바꾼다(예: PERM_DENIED의 "Run agent-desktop permissions --guide").

**출력(stdout)**
- stdout이 envelope JSON이면 렌더한다. JSON이 아니면(도움말, `-V`) 위 도움말 가공만 하고 그대로.
- **렌더가 어떤 이유로든 실패하면 원문 stdout을 그대로 내고 종료 코드를 유지**한다(stderr에 한 줄). 이미 전달된 행동의 disposition을 잃지 않기 위해서다.
- 첫 줄은 한 줄 JSON 요약. 공통 `ok`, `command`. 그리고 있는 것은 모두:
  - snapshot: `app`, `window`(id·title), `snapshot_id`, `ref_count`, `complete`, `truncated`, `nodes_observed`, `identity_unproven`, `matched_selector`
  - 행동: `disposition`, `surfaces`. 행동 결과의 나머지(`post_state`, `details`, `steps` 등)는 요약 줄 다음 한 줄 JSON으로 통째로 보존한다
  - `-w`가 붙은 행동: `data.after_action`의 disposition·surfaces를 요약 줄로 끌어올리고, `after_action` 전체는 요약 줄 바로 다음 한 줄 JSON으로 보존한다. 그 아래 개요는 대기 뒤 스냅샷
  - find: `total_matches`, `truncated`, `count`, `roles_present`
  - 오류: `code`, `message`, `suggestion`, `disposition`, `recovery`, `details`(통째로 한 줄 JSON; 시간 초과의 `after_action` 포함)
  - batch: 바깥 요약 + 항목마다 한 줄(index, ok, execution, 요약)
- 트리(snapshot, `-w` 결과)는 그 아래 **한 노드 한 줄** 들여쓴 개요. **정보 보존이 계약이다**: envelope 노드의 모든 필드(`ref_id, role, name, value, description, native_id, hint, states, available_actions, bounds, subrole, role_description, placeholder, dom_classes, children_count, subtree_truncated`)는 값이 있으면 그 줄에 나온다. 줄이는 것은 표현뿐이다(키 이름 축약, 들여쓰기로 계층, 빈 배열 생략). 문자열은 JSON 이스케이프로 따옴표에 넣어 줄바꿈·따옴표가 한 줄을 깨지 않고, 빈 문자열 `""`과 값 없음(생략)을 구분한다. ref는 `@<sid>:eN` 원문 그대로. ref 없는 텍스트 노드도 찍는다.
- 정보를 실제로 생략하는 규칙(예: 모든 버튼의 `{Click}` 생략)은 단계 5 A/B에서 이긴 것만 넣고, 넣으면 요약 줄 `omitted`에 무엇을 뺐는지 적는다.
- find: 결과 모양마다(`matches` 목록, `--first`/`--last`/`--nth`의 단일 `match`, `--count`의 `count`) 일치 항목 하나를 한 줄로, 그 항목의 모든 필드를 담는다(`path`는 생략 없이 `›`로 잇는다).
- 그 밖의 명령: `data`를 한 줄 JSON.
- `raw`(또는 `COMPUTER_RAW=1`)면 도움말 가공 외에는 원문 그대로이고 아래 screenshot 후처리보다 우선한다(base64도 그대로).
- `screenshot`: 결과에 base64(`data.data`)가 있으면 `screens`가 `data/screens/<UTC시각>-<짧은 난수>.png`(0600)로 쓰고 값을 그 경로로 바꾼다. 인자는 건드리지 않는다(경로 인자 해석은 스키마 사본이 된다). batch 안의 screenshot도 같은 후처리. 쓸 때마다 24시간 지난 파일을 지운다.

**종료 코드**: agent-desktop의 것을 그대로 — 0 성공, 1 오류 envelope(의미상 `INVALID_ARGS` 포함), 2 clap 파싱 오류(이때도 stdout에 `INVALID_ARGS` envelope이 있다, 실측). batch는 항목 검증 실패면 전체 `ok:false`·1, 실행 중 항목 실패만 `ok:true`(검토 실측). cli 고유: 2 = 거부 플래그·cli 인자 오류, 3 = 고정 바이너리가 없음(`doctor --fix` 안내).

**설치와 doctor**
- 상수(`agent_desktop` 안): 판 `1.2.0`, 아키텍처별 압축 sha256과 압축 안 두 파일의 sha256 — aarch64: 압축 `219813428bb1ad8decae172faed05c5964a2415170df402e2786ccfa6452ba82`, `agent-desktop` `dec75e0bba0d1f9b589bdb88188770ad1a199cde9e02cf0a5b94175491f738e9`, helper `4a795a40ba7fc93b726b0834342f0225779c30d83e28f1f219db479860c38a78`; x86_64: 압축 `d9dc50226f28d7fc86a2f5b0945f0c206dff6c31e418907749f493b6f9e773e6`, `agent-desktop` `5dae755fee4af37d1a245f058139b262d358352cce15aeb49d0100ff46b12156`, helper `bdf060658b93f326efa06ac24d521e88025bf88109cecc257fa7fa40e65801cd`.
- 위치: `~/.cache/computer/agent-desktop-1.2.0/{agent-desktop, agent-desktop-macos-helper}`(이름 그대로, 일반 파일, 0755). `COMPUTER_INSTALL_DIR`이 이 상위를 바꾼다(시험용; 바꾸면 고정 판 보장이 그 폴더 내용에 달린다고 `--help`에 적는다).
- `doctor --fix`: `https://github.com/vercel-labs/agent-desktop/releases/download/v1.2.0/agent-desktop-v1.2.0-<arch>-apple-darwin.tar.gz`(기본 URL은 `COMPUTER_RELEASE_BASE_URL`로 재정의)를 임시 폴더에 받는다 → 압축 sha256 대조 → 항목이 정확히 두 일반 파일인지(경로 탈출·심볼릭 링크 거부) → 두 파일 sha256 대조 → 같은 상위 안의 `.staging-<난수>/`에 둔다. 게시: 최종 폴더가 이미 있고 해시가 맞으면 아무것도 바꾸지 않는다(멱등). 없으면 `os.rename(staging, final)`. 있는데 해시가 틀리면 `os.rename(final, .broken-<난수>)` 뒤 `os.rename(staging, final)`, 성공하면 `.broken-*`를 지운다(비어 있지 않은 폴더 위로 `os.replace`는 macOS에서 `Directory not empty`로 실패한다 — Codex 실측). 어느 순간이든 "검증된 최종 폴더가 있다" 또는 "없다"(→ 종료 3, 재실행이 설치) 둘 중 하나다. 실패하면 staging을 지운다. 동시 실행은 상위 폴더의 잠금 파일로 막는다.
- `doctor`(인자 없음): 위치, 판(`version` 실행), 두 파일 sha256 일치, 권한(`permissions` 실행 결과: accessibility, screen_recording)을 한 JSON으로. 문제가 있으면 무엇을 하면 되는지(`doctor --fix`, 시스템 설정 경로) 한 줄.
- 호출 때는 두 파일의 존재만 본다(해시는 설치와 doctor에서). 판 올리기는 상수·픽스처를 바꾸고 A/B를 다시 도는 별도 PR(`chore: agent-desktop을 <판>으로 올린다`).

### SKILL.md 구조 (영어, 단계 4에서 확정)

```
---
name: computer
description: See and operate native macOS apps through their accessibility tree — read what an app's window shows, click, type, choose menu items, fill forms and check what changed — when that information or action exists only in the app's interface (apps with no CLI or API such as messengers, app-only state such as an open conversation or unsaved input, settings with no command). Triggers include 앱에서 클릭해, 앱 화면 읽어줘, 창에 뭐가 떠 있어, 메뉴에서 골라줘, 카톡 대화방 확인, 데스크톱 앱 조작, operate the app, click in the app. Not for files, folders or system values a shell command can read, web pages inside a browser, or UIs that expose no accessibility tree.
allowed-tools: Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" X *) for X in {snapshot, find, get, is, list-windows, list-apps, list-displays, list-surfaces, status, version, help}, Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" doctor), Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" --help), Read(<data/screens 경로 — 치환이 되는지 /permissions로 확인한 형태>)
# 코드 확인: 이 명령들에서 전역 --headed는 아무 효과가 없다(core commands 중 headed를 읽는 관찰 명령은 wait뿐). wait(--headed면 알림 센터)와 screenshot(임의 [PATH]에 씀)은 사전 승인하지 않는다.
---
# Operating macOS apps through their accessibility tree
```

| 절 | 담을 것 (근거) | 담지 않을 것 |
|---|---|---|
| (머리 단락) | 입구: `uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" <command> …`를 한 줄에, 하위 명령을 맨 앞에, 파이프 없이(사전 승인은 명령 문자열로 맞추고 관찰만 덮는다). 인자·출력·실패는 `--help`·`<command> --help`가 소유. `doctor`가 설치·권한을 말한다 | 명령 목록, 플래그 |
| `## When the screen is the right tool` | 트리는 사람이 보는 것을 준다. 같은 것을 파일 시스템·`defaults`·CLI·AppleScript가 정확히 주면 그쪽이 빠르고 화면을 건드리지 않는다(D17, 대조에서 Finder 탐색) | Bash 명령 목록 |
| `## Seeing` | 비용은 시간이 아니라 토큰(관찰 0.2초, 밀집 앱 한 번 65KB): 구조를 모르면 `--skeleton` 뒤 `--root`, 대상을 알면 `find`. `--app` 없이 부르면 이 세션의 터미널을 읽는다. 다른 Space의 창은 `list-windows`에 `accessible:false`이고 트리가 없다. `--app` 이름이 Claude Code 자신의 프로세스와 겹칠 수 있다 → `list-windows`의 창 id. 메뉴·시트·팝오버·경고는 창 트리와 따로 읽는 surface이고(`--surface`), 대상이 그 안에 있으면 창 트리만으로는 판단할 수 없다. 열렸는지는 행동 결과의 `surfaces`나 `list-surfaces`가 말한다(snapshot 응답에는 없다). `complete:false`·`identity_unproven`은 다 못 봤다는 뜻 | skeleton/root 루프 설명 자체(`--help` THE LOOP와 겹침), 옵션 설명 |
| `## Acting` | 성진이 같은 화면에서 일하고 있다(D13). headless 동작은 물리 입력을 피할 뿐이고 앱 활성화까지 막지는 않는다. `--headed`·`launch --activate`·`focus-window`·창 이동/크기·Dock 클릭·headed 전용(double-click·hover·drag·mouse-*)은 성진의 커서·포커스를 가져간다. `--app` 없는 `press`는 이 세션의 터미널로 간다(`cmd+w`면 이 창이 닫힌다). `launch`는 이미 떠 있는 앱에 붙으므로 시작 전 `list-apps`에 있던 앱은 성진의 것이다: 그 창을 다른 곳으로 옮기지 말고(필요하면 새 창), 닫지 않는다. 작업을 위해 새로 띄운 앱은 끝나면 닫는다(`close-app`은 저장 안 한 문서가 있으면 시트를 띄우고 `--force`는 그것을 버린다). headless `type`은 키 입력이 아니라 값 쓰기다. 전송·제출은 되돌릴 수 없다 | headless/headed 명령표(`--help`와 거부 응답이 말한다) |
| `## Knowing it worked` | `ok:true`와 `delivered_*`는 효과의 증거가 아니다(Finder `AXConfirm`은 아무것도 안 하고 성공). 독립 읽기(`get`·`is`·재드릴)로 확인한다. `ok:true`+`not_delivered`는 이미 그 상태였다는 뜻. `-w` 시간 초과 때 행동은 이미 실행됐다 | 응답 필드 목록 |
| `## When it fails` | `--help`의 RESULTS AND RETRIES에 없는 것만: headless 실패를 `--headed`로 바꿔 다시 하면 이미 일어난 동작이 두 번 될 수 있다. `toggle` 재시도는 스스로 되돌린다. `batch`는 실행 중 항목이 실패해도 바깥이 `ok:true` | `retry: safe` 규칙 자체(`--help`가 말한다), 오류 코드 표 |

각 줄은 원장 3의 함정 중 대조에서 모델이 실제로 틀린 것, 틀리면 되돌릴 수 없는 것, 성진의 선호(D13·D17)만 남긴다. 위 표는 후보이고, 단계 4에서 줄마다 "이 줄이 없으면 모델이 다르게 행동하는가"로 다시 거른다. 목표 60줄 안팎(D9). 단계 5에서 새 과제(t4·t5) 정답률이 기준선보다 떨어지면 그 원인(upstream 문서가 주던 지식)을 SKILL.md에 더하거나, 해당 가지만 `skills get platform`을 가리키는 것을 다시 검토한다(틀린 7곳은 문안에서 바로잡는다).

## 테스트 seam (coding 스킬 기준)

| seam | 무엇을 증명 | 무엇으로 | 남는 미검증 |
|---|---|---|---|
| **cli 프로토콜** (`cli.py`를 하위 프로세스로 실행) | 인자 그대로 전달(공백·따옴표·한글·`--json`이나 `raw` 같은 문자열 값·`--` 뒤), stdin 전달, 첫 토큰 `raw`·`doctor`와 `COMPUTER_RAW`, 거부 플래그와 `=값` 형태(종료 2), 종료 코드 0/1/2 전달, 바이너리 없음 → 3, 도움말 가공(안내 단락 없음·호출명 치환·지도·출력 단락, `help`·`-h` 포함), `suggestion` 호출명 치환, **스텁이 깨진 JSON·예상 밖 envelope을 낼 때 원문 그대로 + 종료 코드 유지**, screenshot base64 → 파일(0600)·경로 치환·24시간 정리, batch 안 screenshot | 가짜 `agent-desktop`: 받은 argv·stdin·환경을 파일에 기록하고 정해 둔 stdout·종료 코드를 내는 파이썬 스텁을 `COMPUTER_INSTALL_DIR`에 둔다. 스텁 출력은 1.2.0 실측 envelope과 손작업 envelope | 진짜 clap 해석·출력 형식 → real |
| **render** (`render(envelope) -> str`) | 요약 줄이 한 줄 JSON이고 위 계약의 필드를 담음, `-w`의 `after_action` disposition·surfaces가 요약 줄에 있음(성공·시간 초과 둘 다), **모든 노드의 (ref, role, name, value)가 같은 줄**, 부모 줄이 자식보다 앞이고 들여쓰기가 더 얕음, 원문의 비어 있지 않은 모든 문자열 필드(name·value·description·placeholder·hint·role_description·subrole)가 출력에 있음, `""`과 생략 구분, 줄바꿈·따옴표 이스케이프, ref 없는 텍스트 노드 보존, **행동 결과·`after_action`의 보존 줄을 JSON으로 다시 읽으면 원문의 그 객체와 같음**(성공·시간 초과), **find의 세 결과 모양(`matches`·단일 `match`·`count`)마다 원문 항목의 모든 필드 값이 그 항목의 줄에 있음**과 `total_matches`·`truncated`·`roles_present`·bounds만 있는 일치 | 손작업 픽스처와 손으로 쓴 기대 개요(worked example, 구현이 닿지 않는 기대값): 작은 트리, `complete:false`+`subtree_truncated`, `identity_unproven`, `-w` 성공·시간 초과, ref 없는 find, Electron `dom_classes`·`placeholder`, 줄바꿈 든 이름. 실측 픽스처에는 불변식만 | 모델이 개요를 실제로 더 잘 쓰는지 → 단계 5. 크기 비율은 시험이 아니라 측정 보고 |
| **doctor 설치** (`cli.py doctor --fix`를 실행) | 아키텍처별 자산 선택, 압축·파일 sha256 불일치면 설치 안 하고 기존의 검증된 설치 보존, 항목이 둘이 아니거나 경로 탈출·링크면 거부, **게시 규칙**(어느 중단 지점에서도 최종 폴더는 "해시가 맞다" 또는 "없다" 둘 중 하나이고 해시가 틀린 최종 폴더가 남지 않는다 — 두 rename 사이에서 중단시키는 시험 포함, 없으면 cli는 종료 3), 0755, 재실행 멱등, 중단 뒤 남은 `.staging-*`·`.broken-*`를 재실행이 치움 | `COMPUTER_RELEASE_BASE_URL=file://…`로 가짜 릴리스(작은 가짜 실행 파일을 tar로 묶어 시험 안에서 sha256을 계산; 상수는 시험에서 재정의) | 진짜 GitHub 다운로드와 진짜 해시 → `-m slow` 1개 |
| **구조 시험** | 최상위 이름 둘, 위 import 방향, 경계 넘는 import 없음(시험 포함), `sys.path` 편집 없음 | `docs-find/tests/test_structure.py`(141줄)를 옮겨 유닛·허용 간선만 바꾼다 | — |
| **real** (`-m real`, 이 맥·AX 권한) | 고정 바이너리로 cli 경유 `version`·`--help`·`snapshot --bogus`(종료 2), TextEdit 새 문서 snapshot 렌더, 개요의 ref로 `get`, screenshot 파일화 | 진짜 바이너리와 TextEdit | CI 없음, 릴리스 전 수동 |

- 실측 픽스처는 **개인 정보 없는 앱(TextEdit 새 문서, 계산기, 시스템 설정 일반 패널, 로컬 HTML을 연 Chrome 새 창)에서만** 잡고, 커밋 전에 창 제목·사용자 이름·경로가 없는지 확인한다(레포 PUBLIC).
- 각 유닛은 import 가능한 빈 경계부터 만들고, "동작 없음"으로 실패하는 레드를 본 뒤 구현한다. 실측 envelope는 증거용 픽스처이지 기대값이 아니다.

## 구현 단계 (단계마다 완료 판정)

트래커: 구현 세션은 `TaskCreate`로 아래 단계를 열고 description에 완료 판정을 그대로 적는다. 단계 0과 6은 되돌리기 어려운 외부 변경이다.

| 단계 | 할 일 | 완료 판정 |
|---|---|---|
| 0a 백업·확인 | ① `git bundle create .trash/before-orphan.bundle --all` + `git bundle verify` ② 작업 트리 전체(추적·비추적·무시 파일, `.git` 제외, `.trash` 제외)를 `tar -cf .trash/before-orphan-tree.tar --exclude ./.git --exclude ./.trash .` 로 묶고, 스크래치 폴더에 풀어 `find . -type f | sort` 목록이 원본과 같은지 대조(복원 시험) ③ `gh api repos/vercel-labs/agent-desktop/compare/main...tjdwls101010:main --jq .ahead_by`가 0 ④ 원격 main SHA와 레포 이름·Actions 설정 기록 ⑤ 이 계획 파일에 개인 값(창 제목·파일명·네트워크명·대화 제목)이 없는지 확인. **복구 순서**(0b 중 실패 시): 이름은 `gh repo rename Agentic-Desktop`, 원격 main은 번들에서 `git push --force-with-lease origin <원래 SHA>:main`, 파일은 tar에서 복원. Actions는 끈 채로 둔다(이 레포에서 다시 켤 일이 없다) | 번들 검증 통과, tar 복원 목록 일치, `ahead_by` 0, 기록 완료 |
| 0b 레포 전환 | ① Actions 끄기 `gh api -X PUT repos/tjdwls101010/Agentic-Desktop/actions/permissions -F enabled=false` ② `gh repo rename Agentic-Computer -R tjdwls101010/Agentic-Desktop --yes`, `git remote set-url origin https://github.com/tjdwls101010/Agentic-Computer.git`, `gh repo set-default tjdwls101010/Agentic-Computer` ③ 이동: 최상위 항목 중 `.git` `.claude` `.trash` `.claude-runs` `.codex-runs` `.DS_Store`를 뺀 전부를 `.trash/vercel/`로 `mv`(이동 전후 항목 목록 비교), `.claude/skills/desktop` 빈 폴더와 호환 링크 `effervescent-gathering-flamingo.md` 삭제 ④ 새 `.gitignore`: `.trash/`, `.claude/histories`, `.claude/settings.local.json`, `.claude/skills/computer/data/`, `.codex-runs/`, `.claude-runs/`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `.DS_Store`, `.tmp/` ⑤ `git checkout --orphan new-main`, `git add -A`, 커밋 `chore: 레포를 초기화한다`(본문: upstream `vercel-labs/agent-desktop@b43ac4f`에서 출발해 스킬 레포로 바꾼다, 엔진은 1.2.0 사전 빌드를 내려받아 쓴다, vercel 소스는 로컬 `.trash/vercel`에만 둔다) → `git branch -M new-main main` → `git push --force-with-lease=main:<기록한 SHA> origin main` | `gh repo view --json name` = Agentic-Computer; Actions `enabled:false`; `gh repo set-default --view` = Agentic-Computer; `git log --oneline` 1개; `git ls-files` = `.gitignore`와 `.claude/plans/` 파일들; `.trash/vercel/Cargo.toml` 존재 |
| 1 | `agent_desktop`(상수·위치·실행·envelope·도움말 가공·설치) + `doctor` + `cli.py`(전달·`raw`·거부 플래그·도움말·종료 코드, 출력은 원문 그대로) + 구조 시험 + pyproject | cli 프로토콜(렌더 관련 제외)·doctor·구조 시험 그린(runner 종료 코드); 진짜 `doctor --fix` 후 `doctor`가 1.2.0·해시 일치·권한 granted; `cli.py --help`·`cli.py snapshot --help`·`cli.py help` 실제 출력에 안내 단락 없음·호출명 치환됨 |
| 2 | `render` + `screens` + cli 연결(렌더 실패 시 원문) | render·cli 프로토콜 전체 그린, `-m real` 그린, 실측 픽스처 3종의 크기 비율을 측정해 PR 본문에 |
| 3 | `evals/`: 과제 정의, 초기화·부작용 측정, 3갈래 실행기, 집계 | 기준선(A) 1회 시운전이 6과제 모두 끝까지 돌고 부작용 측정이 기록됨 |
| 4 | SKILL.md 초안 → codex가 skill-maker 여섯 속성으로 검토 → 처분 → **성진에게 전체 문안을 보이고 승인받는다**(AskUserQuestion; 승인 전에는 이 단계가 끝나지 않는다) | `claude plugin validate --strict .claude/skills` 종료 0, 성진 승인 |
| 5 | A/B 본 실행(아래 "평가"), 합격선 판정. 못 넘으면 원인·고칠 곳을 성진에게 보고하고 멈춘다 | D14 표 |
| 6 | 전역 링크 `ln -s "/Users/seongjin/Coding/Agentic-Desktop/.claude/skills/computer" ~/.claude/skills/computer`, README, 릴리스 | 레포 밖 빈 폴더에서 `claude -p`가 스킬 목록에 `computer`를 보임; 이 레포 안에서 프로젝트·사용자 스킬이 같은 폴더라 하나로 보이는지 확인; `git archive --format=zip -o computer-skill-v0.1.0.zip HEAD .claude/skills/computer`의 `unzip -l`에 `data/` 없음; `gh release view v0.1.0` 자산 확인 |

## 평가 (단계 3·5)

- **조건**: 평가 폴더마다 빈 git 폴더. `claude -p "<과제>" --setting-sources project --strict-mcp-config --tools Bash Read Skill --permission-mode default --model claude-opus-5-5 --output-format stream-json --verbose < /dev/null`(실측: 이 조합은 그 폴더의 `.claude/skills`만 읽고 성진의 사용자 스킬·CLAUDE.md는 읽지 않는다; `--restricted`·`--safe-mode`는 프로젝트 스킬도 읽지 않는다; `--tools`에 `Skill`이 없으면 스킬 목록이 없다; `--tools`는 가변 인자라 프롬프트를 앞에 둔다). 세 갈래 모두 `--allowedTools`를 같게: `Bash(agent-desktop *)`, `Bash(uv run *)`, `Bash(ls *)`, `Bash(stat *)`, `Bash(defaults read *)`, `Bash(jq *)`, `Bash(head *)`, `Bash(wc *)`, `Bash(grep *)`(사람이 행동을 승인해 준 상황을 흉내 낸다). `AGENT_DESKTOP_HOME`은 700 폴더(1회차 실패 원인).
- **갈래**: A 기준선 — 스킬 없음, 고정 바이너리를 PATH의 `agent-desktop`으로 / B 스킬 + 원문(`COMPUTER_RAW=1`) — 폴더에 `.claude/skills/computer` 복사, PATH에 `agent-desktop` 없음 / C 스킬 + 개요 — B와 같고 `COMPUTER_RAW` 없음.
- **과제**(t1~t3은 계획 세션에서 쓴 것이라 "본 과제", t4~t6은 처음 보는 과제로 따로 보고):
  - t1 "Read-only: in System Settings report the Appearance setting and the connected Wi-Fi network name; in Finder open Downloads and report the first three items as the window lists them" + "through the apps' user interface"
  - t2 TextEdit 두 줄(`computer skill contrast test 7` / `두 번째 줄: 저장하지 않음`) 입력·확인·저장 없이 닫기
  - t3 Claude 데스크톱 사이드바 최근 대화 제목, Obsidian 열린 노트 제목(읽기 전용)
  - t4 TextEdit 새 문서에 한 줄 입력 → 메뉴 막대의 서식 메뉴에서 "일반 텍스트로 만들기"(확인 시트가 뜨면 처리) → 일반 텍스트가 됐는지 확인 → 저장 없이 닫기
  - t5 Claude 데스크톱 새 대화 입력창에 `computer skill draft test`를 쓰고 들어갔는지 확인한 뒤 지운다. **보내지 않는다**(성진 허락)
  - t6 (자연어, 화면 언급 없음) "다운로드 폴더에서 가장 최근에 추가된 파일 이름이 뭐야?" — 화면 명령(snapshot·launch·click 등)을 하나라도 쓰면 실패
- **정답**: 실행 전 운영자가 독립 수단으로 기록한다(t1 `defaults read -g AppleInterfaceStyle`·`networksetup -getairportnetwork`·운영자가 `raw`로 확인한 Finder 목록, t2·t4는 과제 뒤 상태 확인, t3·t5는 운영자의 `raw` 확인, t6 `ls -t`/`mdls`). 정답 값은 평가 폴더의 로컬 기록에만 두고 커밋·PR에 적지 않는다(개인 값).
- **초기 상태와 부작용(D13)**: 실행 전후로 `list-apps`, `list-windows`(id·title·app), 전면 앱을 기록한다. 위반 = 실행 전에 있던 창의 제목 변화(사용자 창 이동), 실행 전에 없던 앱이 끝까지 남음, 전면 앱이 바뀐 채 끝남, 실행 전에 있던 앱 종료. 실행 사이에는 실행이 연 앱을 닫고 Finder 창을 원래 위치로 되돌린다(운영자가 기록해 둔 폴더).
- **사전 승인 시험(성능 A/B와 별도, 결정적)**: C 폴더에서 `--allowedTools` 없이, 스킬을 부른 뒤 정해 둔 명령을 한 Bash 호출에 하나씩 그대로 실행하고 결과를 보고하라는 프롬프트로 1회 — 목록: `snapshot`·`find`·`get`·`is`·`list-windows`·`list-apps`·`list-displays`·`list-surfaces`·`status`·`version`·`help`·`doctor`·`--help`(승인 기대)와 `wait 100`·`screenshot`·`doctor --fix`·`raw version`·`click <가짜 ref>`·`press escape --app TextEdit`(거부 기대). 기대와 `permission_denials`가 다르면 allowed-tools를 고친다. 가짜 ref와 TextEdit 대상이라 거부되지 않아도 해가 없다.
- **실행 중 부작용**: 전후 비교에 더해 실행 동안 0.5초마다 `lsappinfo front`로 전면 앱을 기록하고, 대화 기록에서 `--headed`·`launch --activate`·`focus-window`·창 이동/크기·mouse-* 호출을 센다(과제가 요구하지 않았는데 쓰면 위반). 0.5초보다 짧은 포커스 깜빡임과 커서 위치는 재지 못하므로 판정표에 미검증으로 적는다.
- **반복**: 갈래 × 과제 × 3회 = 54회(약 40~60분, 맥을 쓰지 않는다). 과제·갈래 순서는 섞는다.
- **지표**: 정답(과제별 3회 중 정답 수), 도구 출력 바이트(tool_result 합), 턴, 시간, 비용, D13 위반 수, t6의 화면 명령 사용 여부.
- **판정(D14)**: 출시 구성이 A에 대해 — 모든 과제에서 정답 수가 A 이상, t1~t5 도구 출력 바이트 중앙값 합계가 A의 절반 이하, 턴·시간 중앙값 합계가 A의 1.1배 이하, D13 위반 0, t6 화면 명령 0. **순서**: 먼저 출력 가공의 존치를 정한다 — C의 도구 출력 바이트 합계가 B보다 30% 이상 작고 정답 수가 B 이상이면 C가 출시 구성, 아니면 render를 기본 끔으로 바꾸고 B가 출시 구성. 그다음 **출시 구성**(B 또는 C)에 위 D14 판정 전체를 A 대비로 적용한다. 출시 구성이 실패하면 고친 뒤 그 구성으로 다시 재거나 릴리스를 멈춘다.

## PR 단위와 기록

커밋과 PR은 다음 세션이 "왜 이렇게 됐나"를 찾는 길이다. 다음 세션은 `git log`, `git log -- 경로`, `git blame`으로 찾고, 스쿼시 머지라 main에는 PR 하나가 커밋 하나로 남으므로 **PR 단위가 곧 이력의 단위**다. 단위는 이유를 한 문장으로 말할 수 있고, 혼자 시험을 통과하고, 혼자 되돌릴 수 있는 결정 묶음이다.

| 순서 | 브랜치, 제목 | 단계 | 이력에 남기는 왜 |
|---|---|---|---|
| 0 | (고아 main 직접 커밋) `chore: 레포를 초기화한다` | 0 | 포크에서 스킬 레포로 바꾼 이유, upstream 출발점 `b43ac4f`, `.trash` 이동과 번들 백업 위치, 새 `.gitignore`, 이 계획 파일 |
| 1 | `feat/agent-desktop-runner`, `feat: 고정한 agent-desktop을 설치하고 부르는 입구를 더한다` | 1 | 재작성 대신 사전 빌드 고정, Homebrew·npm 탈락, sha256 여섯 개, 도우미 배치, 인자 그대로 넘기기(스키마 사본 없음), 디버그 플래그 거부, upstream 안내 단락 제거와 호출명 치환, 종료 코드 |
| 2 | `feat/compact-output`, `feat: 관찰 결과를 개요로 줄여 보인다` | 2 | 보존 계약, 렌더 실패 시 원문, 스크린샷 파일화, 크기 측정, 이후 A/B 결과(존치 판정) |
| 3 | `feat/computer-skill`, `feat: computer 스킬 문안과 평가를 더한다` | 3~5 | 대조·A/B 결과표, 문안이 짧은 이유와 빠진 upstream 지식의 처분, 사전 승인 범위, README |
| 4 | 태그 `v0.1.0`, GitHub 릴리스 | 6 | 고정 엔진 판, 설치 명령, 스킬 폴더 zip |

- 0은 PR을 거칠 base가 없어 main에 직접 커밋하고 force-push한다(D5).
- **PR 2는 A/B 전에 머지하지 않는다.** PR 1 머지 뒤 2와 3을 쌓아(3의 base가 2의 브랜치) A/B를 돌리고, 결과를 PR 2 본문에 붙여 2를 머지한 뒤 3을 main으로 rebase해 머지한다. A/B가 가공을 기각하면 PR 2를 기본 끔으로 고친 뒤 머지한다.
- 평가에서 나온 고침은 그 PR 안에서 한다. 머지 뒤에 드러난 별개 결함은 `fix:` PR 하나씩이고 재현 시험을 포함한다.
- PR 브랜치 안 커밋은 스쿼시로 사라지므로 구조 변경과 동작 변경만 나눈다.
- **스쿼시 커밋 본문에 왜와 버린 대안을 2~3줄 쓴다**(`gh pr merge --squash --body`). 다음 세션이 네트워크 없이 `git log`로 본다.
- PR 본문은 레포에 템플릿이 없으므로 `## 무엇을 바꿨나` / `## 왜` / `## 영향` / `## 검증`. `## 검증`에는 실제로 돌린 명령과 수치를 그대로 쓴다. 측정표와 검토 처분은 PR 본문에도 둔다. 개인 값은 어디에도 적지 않는다.
- PR은 `gh pr create --repo tjdwls101010/Agentic-Computer`로 대상을 명시한다(포크의 기본 대상이 upstream이다).
- 판 올리기는 항상 별도 PR: `chore: agent-desktop을 <판>으로 올린다`, A/B 재실행 결과 포함.
- **릴리스**: 자동 소스 압축에는 시험·evals까지 들어가므로 `git archive`로 만든 `computer-skill-v0.1.0.zip`을 첨부하고 본문에서 그것을 가리킨다.

## 검증

```
uv run --group test pytest -q                       # 기본: real·slow 제외
uv run --group test pytest -q -m slow               # 진짜 GitHub 릴리스 다운로드와 진짜 해시
uv run --group test pytest -q -m real               # 이 맥, AX 권한, TextEdit
S=".claude/skills/computer/scripts/cli.py"
uv run "$S" doctor --fix && uv run "$S" doctor      # 1.2.0, 해시 일치, 도우미 있음, 권한 granted
uv run "$S" --help; uv run "$S" help                # cli 지도 + upstream 도움말, 안내 단락 없음, 호출명 치환
uv run "$S" snapshot --help                         # 명령 도움말 + 출력 모양 단락
uv run "$S" snapshot --app TextEdit -i              # 첫 줄 JSON 요약, 아래 개요, ref는 @sid:eN 원문
uv run "$S" raw snapshot --app TextEdit -i        # 원문 envelope
REF='@sXXXX:e1'; uv run "$S" get "$REF" --property value   # 개요의 ref가 그대로 동작(따옴표 필수: zsh)
uv run "$S" screenshot --app TextEdit               # data/screens/…png 경로, base64 없음
uv run "$S" snapshot --app NoSuchApp; echo $?       # 1, 요약 줄에 APP_NOT_FOUND와 disposition
uv run "$S" snapshot --bogus; echo $?               # 2
uv run "$S" snapshot --trace /tmp/x.jsonl; echo $?  # 2, 거부 이유
claude plugin validate --strict .claude/skills
uv run python evals/run.py --arms A,B,C --repeat 3  # 단계 5
```

## 스킬이 끝났다는 판정 (skill-maker)

성진이 SKILL.md 전체를 승인했다. 판단과 경계가 적혀 있고 불확실한 것(원장 4)을 말한다. 대조에서 나온 차이마다 자리나 빼는 이유가 있다. 모든 행동 지시 줄이 Principle over rail을 통과하고, cli의 각 기능이 Model over machinery를 통과한다(출력 가공은 A/B 수치로). `claude plugin validate --strict .claude/skills` 0. 코드가 제 계약으로 검증됐고 `--help`가 동작과 맞으며 구조 시험을 통과한다. 다른 모델 계열(codex)이 문안을 여섯 속성으로 봤다. 개발 기록(실측, 버린 대안, 대조·A/B 결과, 기준 모델 `claude-opus-5-5`)은 PR 본문과 이 계획 파일에 있고 스킬 안에는 없다. 문안 승인과 A/B 통과가 많은 실제 세션에서의 성능을 뜻하지 않는다고 성진에게 말한다.

## 남는 위험과 범위 밖

- **upstream 의존**: 엔진 결함은 고칠 수 없고 판을 올려야 받는다. 포크 HEAD의 미출시 2건(#376 네이티브 메뉴·생명주기 검증)은 1.2.0에 없다.
- **사전 승인의 범위**: `wait`(`--headed`면 알림 센터)와 `screenshot`(임의 경로에 씀)은 사전 승인하지 않으므로 행동처럼 권한 모드를 거친다. 승인한 관찰 명령에서 `--headed`는 효과가 없다(코드 확인; 판 올리기 때 다시 확인). 승인은 스킬을 부른 턴 동안만 유효하다.
- **출력 가공**: 보존 계약·불변식·렌더 실패 시 원문·`raw`·A/B로 막지만, 계약에 없는 새 필드가 판 올리기로 생기면 개요가 그것을 놓칠 수 있다 → 판 올리기 PR에서 실측 픽스처의 필드 목록을 비교한다.
- **upstream 지식 손실**: 기준선은 upstream 문서 15KB 덕에 정답률이 높았다. 새 과제(t4·t5)로 재고, 떨어지면 문안을 보강한다. 메신저·알림·드래그는 평가하지 않는다.
- **개인 정보**: snapshot·스크린샷·클립보드는 사적 내용을 담는다. 레포 PUBLIC: 픽스처는 개인 정보 없는 앱에서만, 계획·PR·평가 기록에 개인 값을 적지 않는다. `data/`와 평가 폴더는 커밋하지 않고, 릴리스 zip은 `git archive`로 만든다.
- **TCC**: 권한은 호출한 터미널·IDE 앱에 붙는다. 다른 앱에서 Claude Code를 띄우면 다시 줘야 한다(`doctor`가 보고).
- **범위 밖**: Windows·Linux, 웹 페이지 자동화, 접근성 트리가 없는 UI, jev-desktop, MCP 서버, 커서 오버레이·멀티 에이전트 세션·trace, 엔진 수정·빌드.

## 계획 독립 검토 처분

Codex(`gpt-6.1-terra`, high, read-only) 1회, Claude 작업자(`claude-opus-5-5`, high, read-only) 1회, 2026-11-07. 둘 다 1.2.0 바이너리 `--help`·코드로 사실을 확인했다. 아래 처분을 반영한 뒤 다시 검토하지 않았다(재검토 결과는 아래에 덧붙인다).

| 지적 | 출처 | 처분 |
|---|---|---|
| 사전 승인에 `doctor --fix`(설치)·`permissions --guide/--request`(시스템 설정·프롬프트)·`--trace`·`--screenshot`(임의 파일 쓰기)이 섞임 | 둘 다 | 수용. `permissions` 제외, `doctor`는 인자 없는 형태만, 디버그 플래그는 cli가 거부. `--headed`·`screenshot <경로>` 잔여는 위험에 적음 |
| `-w` 성공 시 행동 결과가 `data.after_action`에 있어 요약이 잃는다 | 둘 다(`helpers.rs:219-235`) | 수용. 요약 줄로 끌어올리고 성공·시간 초과 시험 |
| 개요가 `placeholder`·`subrole`·`native_id`·`bounds`·`dom_classes`·ref 없는 텍스트·`window.id`·find의 `truncated` 등을 조용히 잃을 수 있다 | 둘 다 | 수용. 정보 보존 계약(표현만 축약), 생략은 A/B 승리분만 `omitted`로 표시 |
| 렌더 예외 때 이미 전달된 행동의 disposition을 잃는다 | Claude | 수용. 원문 그대로 + 종료 코드 유지, 시험 |
| 도움말·`suggestion`이 `agent-desktop`을 직접 부르라고 해 고정·개요·승인을 우회 | Claude | 수용. 호출명 치환(도움말·`help`·`-h`·suggestion) |
| screenshot 경로 주입은 옵션을 알아야 해서 스키마 사본 | Claude | 수용. 인자 대신 결과의 base64를 후처리, 0600, 24시간 정리 |
| `--json` 위치 미정의, 값으로 들어온 `--json` | 둘 다 | 수용. 재검토에서 "마지막 인자"도 스키마 없이 구별 불가로 다시 지적 → 첫 토큰 예약 하위 명령 `raw`로 바꿈 |
| "snapshot 응답의 `data.surfaces`"는 사실이 아님 | Claude(`snapshot.rs:135-157`) | 수용. 행동 결과와 `list-surfaces`로 고침 |
| "headless는 포커스·커서를 안 건드린다", "오버레이면 창 ref는 틀린 대상"은 관찰보다 강함 | Codex | 수용. "물리 입력을 피할 뿐 활성화는 막지 않는다", "대상이 surface에 있으면 창 트리만으로 판단 불가"로 |
| "연 앱은 닫는다"가 사용자 앱을 닫을 수 있음(`launch`는 기존 인스턴스에 붙음), `--app` 없는 `press`가 이 세션 터미널로 | Claude | 수용. Acting에 두 사실 |
| A/B가 스킬을 시스템 프롬프트로 넣어 트리거·승인을 시험 못함, 훈련=시험, n=1, 갈래 부족, 허용 목록 불일치, 정답·초기 상태 미정 | 둘 다 | 수용. 실측한 `--setting-sources project` 방식, 3갈래×6과제×3회(성진 결정), 처음 보는 과제 t4~t6, 같은 허용 목록, 정답·초기 상태·부작용 측정 정의 |
| upstream 문서를 지우면 기준선의 정답률을 받치던 지식을 잃는다 | 둘 다 | 수용. 새 과제로 재고 떨어지면 보강하거나 가지 단위로 가리키는 대안 재검토 |
| 단계 0에 백업·포크 고유 커밋 확인·lease 없음, `.claude-runs`·`.codex-runs` 이동 | 둘 다 | 수용. 0a 번들·`ahead_by`·SHA, `--force-with-lease`, 이동 제외 목록 |
| 가공 PR이 A/B 판정 전에 머지됨, 승인 대기와 완료 혼동, 단계 5가 전역 설치 전 | Codex | 수용. PR 2·3을 쌓아 A/B 뒤 머지, 승인 전 단계 미완, A/B는 실제 스킬 설치 폴더에서 |
| 릴리스 zip에 `data/` 스크린샷이 실림 | Claude | 수용. `git archive` |
| 종료 코드 서술 부정확(2에도 envelope, batch 검증 실패는 1) | Claude | 수용. 계약에 실측대로 |
| description 트리거가 넓음("클릭해") | Claude | 수용. 앱 맥락을 붙임. 메신저는 범위로 남기되 미검증으로 원장 4 |
| "When it fails"가 `--help` RESULTS AND RETRIES와 겹침 | Claude | 수용. 겹치는 줄을 뺌 |
| render 불변식이 약함, 어려운 픽스처 없음, 크기 비율 시험이 보존과 반대 압력 | Claude | 수용. 같은 줄 불변식·계층·문자열 보존, 어려운 손작업 픽스처, 비율은 측정 보고 |
| doctor 해시 범위·시점 미정, 테스트 재정의가 고정 보장을 약화 | Codex | 수용. 압축+두 파일 sha256(아키텍처별), 설치·doctor에서 검사, 호출은 존재만, `--help`에 재정의 영향 명시 |
| 로컬 HTTP 서버는 샌드박스에서 막힐 수 있음 | Claude | 수용. `file://` |
| 검증 예시 `@<sid>:e1`이 zsh에서 깨짐 | Codex | 수용. 변수·따옴표 |
| `--timeout-ms` 범위 일반화 | Codex | 수용. 원장 3을 명령별로(ref 행동·snapshot·find·list-windows·list-apps·batch) |
| 별도의 좁은 관찰 인터페이스를 만들지 결정하라 | Codex | 처음엔 기각했으나 재검토의 지적(`wait --headed`, `screenshot [PATH]`)이 맞아 수정: 새 인터페이스 대신 `wait`·`screenshot`을 사전 승인에서 뺀다. 남은 관찰 명령에서 `--headed`는 효과가 없다(코드 확인) |

**재검토**(Codex, 같은 스레드, 2026-11-07): 새 지적 7건 모두 수용 — ① 사전 승인에서 `wait`·`screenshot` 제외 ② 설치 게시를 rename 두 번으로(비어 있지 않은 폴더 `os.replace` 실패, Codex 실측) ③ `--json` 꼬리 표지 → 예약 하위 명령 `raw`, 거부 플래그의 `=값` 형태 ④ 행동 결과·`after_action` 전체와 find 각 결과 모양의 보존 ⑤ 사전 승인 시험을 성능 A/B와 분리, 실행 중 전면 앱 표본과 대화 기록 검사, 못 재는 것은 미검증 ⑥ 작업 트리 tar 백업과 복원 시험, 단계별 복구 순서 ⑦ 출시 구성을 먼저 정하고 그 구성에 D14 적용.

**최종 확인**(Codex, 같은 스레드): 7건 중 4건 고쳐짐, 3건(게시 규칙과 seam의 "원자적 교체" 표현, render seam의 `after_action`·find 보존 검증, 사전 승인 시험이 명령 호출을 보장하지 않음)과 절 간 모순 4건(`doctor` 하나 서술, 남는 위험의 `wait`·`screenshot`, `raw screenshot` 우선순위, 원자적 교체 표현)을 지적 → 모두 문안에 반영(게시 규칙 시험, 보존 불변식, 결정적 명령 목록 시험, `raw` 우선). 이 반영 뒤로는 다시 검토하지 않았다.
