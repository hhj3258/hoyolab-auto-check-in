# HoyoLab 자동 출석체크 — 프로젝트 개요

## 1. 한 줄 요약

HoyoLab 5개 게임의 매일 출석체크를 **헤드리스 Chromium으로 로그인 세션을 재사용해 자동 클릭**하고, Windows 작업 스케줄러에 등록해 **매일 새벽 무인으로 완료**한다.

---

## 2. 기술 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| 브라우저 자동화 | Playwright (Python) | HoyoLab이 Vue.js SPA라 HTTP 직접 호출 불가 — 실제 브라우저 렌더링·클릭 필요 |
| 브라우저 엔진 | Chromium (headless) | Playwright 번들로 별도 설치 없음. 퍼시스턴트 프로파일로 세션 재사용 |
| 키보드 입력 | msvcrt | Windows에서 방향키 raw keypress 처리 — 표준 `input()`은 이스케이프 시퀀스 미지원 |
| 스케줄링 | schtasks (Windows 내장) | 서드파티 없이 작업 등록/해제. 설치 불필요 |
| 다국어 | JSON locale 파일 | ko/en/ja 지원. 코드 내 문자열 하드코딩 금지 원칙 적용 |

---

## 3. 파일 구조

```
hoyolab-auto-check-in/
├── run.bat                  # 진입점 — Python 설치 확인 후 checkin.py 실행
├── schedule.bat             # 작업 스케줄러 관리 전용 런처
├── locales/
│   ├── ko.json              # 한국어 문자열 (99줄)
│   ├── en.json              # 영어 문자열
│   └── ja.json              # 일본어 문자열
├── scripts/
│   ├── checkin.py           # 핵심 로직 — 게임 선택, 로그인, 출석체크 자동화 (620줄)
│   ├── _setup.py            # 의존성 자동 설치 (playwright 패키지 + Chromium)
│   └── _schedule.py         # 작업 스케줄러 등록/해제
└── data/                    # 런타임 상태 (gitignore)
    ├── browser_profile/     # Chromium 퍼시스턴트 프로파일 (쿠키/세션)
    ├── .lang                # 선택한 언어
    ├── .games               # 선택한 게임 목록
    ├── .logged_in           # 로그인 완료 플래그
    └── .sched_asked         # 스케줄러 안내 표시 여부
```

---

## 4. 실행 흐름

```
run.bat
  │
  ▼
checkin.py
  │
  ├─[최초 실행]── 언어 선택 → .lang 저장
  │
  ├─[.games 없음]─ 게임 선택 UI (방향키 + 체크박스 토글) → .games 저장
  │
  ├─[.logged_in 없음]── 브라우저 열기 → 수동 로그인 대기
  │                      └─ ltoken_v2 쿠키 감지 → .logged_in 생성
  │
  └─[게임별 루프]──────────────────────────────────────────────┐
        │                                                       │
        ▼                                                       │
   헤드리스 Chromium 실행 (퍼시스턴트 프로파일)                 │
        │                                                       │
        ├─ 응답 리스너 등록 (page.goto 이전)                    │
        │   ├─ /info GET → is_sign 캡처                        │
        │   └─ /sign POST → retcode 캡처                       │
        │                                                       │
        ▼                                                       │
   출석체크 페이지 로드                                         │
        │                                                       │
        ├─[세션 만료]─── 재로그인 → 재시도                     │
        │                                                       │
        ▼                                                       │
   count 파싱 → target_day = count + 1                         │
        │                                                       │
        ├─[target_day > today]──── 이미 완료 → 다음 게임 ──────┤
        ├─[is_sign: true]─────────── 이미 완료 → 다음 게임 ────┤
        ├─[received 이미지 존재]──── 이미 완료 → 다음 게임 ────┤
        │                                                       │
        ▼                                                       │
   오버레이 닫기 시도 (Escape)                                  │
        │                                                       │
        ▼                                                       │
   target_day 버튼 클릭                                         │
        └─[timeout]─ JS el.click() 폴백                        │
        │                                                       │
        ▼                                                       │
   성공 판정 (순서대로)                                         │
        ├─ 에러 토스트 감지 ("캐릭터 정보를...")               │
        ├─ sign POST retcode (0: 성공 / -5003: 이미 완료)      │
        ├─ count 증가 확인 (5초)                                │
        └─ received 이미지 확인 (2회)                          │
             │                                                  │
             ├─[성공]─────────────── 다음 게임 ────────────────┤
             └─[실패]─ 최대 3회 재시도 → 최종 실패 메시지 ─────┘
```

---

## 5. 해결한 기술적 도전

**1. HoyoLab 클라이언트 사이드 silent fail**

이미 출석한 경우 HoyoLab은 sign POST를 전송하지 않는다. 버튼 클릭 이벤트는 발생하지만 클라이언트가 API 호출 자체를 차단한다. 기존 방식(received 이미지 확인, sign POST 대기)으로는 완료 여부를 판단할 수 없었다.

해결: `page.goto()` 이전에 `/info` GET 응답 리스너를 등록하고, 미문서화 필드 `is_sign`을 캡처해 클릭 없이 조기 종료.

```python
async def _on_info_response(response):
    if response.request.method == "GET" and "/info" in response.url and _act_id in response.url:
        body = await response.json()
        _info_data.update(body.get("data") or {})
        _info_event.set()
```

**2. DOM 카드 경계 오탐**

received 이미지 판정 시 부모 요소를 최대 6단계 탐색하면 인접 카드의 이미지까지 포함된다. 1일차의 received 이미지가 2일차 카드 판정에 영향을 미쳐 false "already done"이 발생했다.

해결: 부모 탐색 중 여러 날짜 라벨(`/^\d+일/`)이 포함되는 순간을 카드 경계로 판단하고 탐색 중단.

```javascript
const labels = Array.from(next.querySelectorAll('*'))
    .filter(e => e.children.length === 0 && /^\d+일/.test(e.textContent.trim()));
if (labels.length > 1) break;  // 카드 경계 도달
```

**3. Vue.js 이벤트 미등록 (force=True 문제)**

Playwright `force=True`는 actionability 체크를 우회해 마우스 이벤트를 강제 dispatch하는데, 원신 Vue 컴포넌트에서 이벤트 핸들러가 트리거되지 않는 경우가 발생했다. 실제로 3회 연속 sign POST 미발생으로 확인.

해결: 폴백을 DOM 네이티브 `el.click()`으로 변경. 이벤트 버블링이 정상 동작해 sign POST가 발생함.

```python
except Exception:
    await page.evaluate(
        "([suffix, day]) => { ...; dayEl.click(); }",
        [day_suffix, target_day]
    )
```

**4. 게임별 성공 감지 방식 파편화**

ZZZ/HKRPG는 팝업 텍스트 "오늘의 출석체크 완료", 원신은 "출석체크 성공" — 게임마다 다르고 언제든 바뀔 수 있다.

해결: 팝업 텍스트 대신 월간 카운트 증가를 성공 기준으로 채택. 게임 무관, API 변경에 강인.

**5. target_day 산출 방식**

단순히 UTC+8 날짜를 target으로 쓰면 누락된 날이 있을 때 날짜 불일치가 생긴다. "오늘이 25일인데 count가 1인" 경우 25일 버튼을 눌러야 할지, 2일 버튼을 눌러야 할지 알 수 없다.

해결: `target_day = count + 1`로 항상 다음 미완료 일차를 계산. UTC+8 날짜는 `target_day > today` 비교(미래 클릭 방지)에만 사용.

---

## 6. 보안 설계

- **자격증명 미저장**: 스크립트가 ID/비밀번호를 읽거나 저장하지 않음. 로그인은 실제 브라우저 창에서 사용자가 직접 수행
- **세션 로컬 저장**: 브라우저 쿠키는 `data/browser_profile/`에만 저장, 외부 전송 없음
- **외부 서버 없음**: HoyoLab 공식 도메인과만 통신. 중간 서버 없음

---

## 7. 배포 방식

별도 빌드 없음. `run.bat` 더블클릭 → 자동 설치 → 자동 실행.

1. Python 설치 여부 확인 (미설치 시 다운로드 링크 안내 후 종료)
2. playwright 패키지 자동 설치 (`pip install playwright`)
3. Chromium 자동 다운로드 (`playwright install chromium`)
4. 최초 실행 시 Windows 작업 스케줄러 등록 안내

스케줄러 등록 후 이후 실행은 완전 무인. 기본 실행 시각: KST 01:05 (HoyoLab 서버 초기화 후 5분).

---

## 8. AI 활용 방식 및 수준

### 활용 단계 요약

| 단계 | 작업 | AI 역할 |
|------|------|---------|
| 설계 | 5게임 지원 구조, 게임 선택 UI, 다중 성공 감지 레이어 | 주도 |
| 구현 | 전체 코드 작성 (checkin.py, _setup.py, _schedule.py, locales) | 전담 |
| 디버깅 | Playwright MCP로 브라우저 직접 조작, 네트워크 요청 분석, 실행 결과 분석 | 주도 |
| 검증 | run.bat 실행 후 로그 분석, 각 게임 출석 상태 확인 | 공동 (실행: AI / 판단: 사용자) |
| 협업 규칙 | CLAUDE.md로 코딩 컨벤션 명시 (문자열 하드코딩 금지, 커밋 메시지 한글 등) | 규칙 수행 |

### 핵심 AI 활용 사례

**라이브 API 역공학**

HoyoLab이 "이미 출석 완료" 상태를 어떻게 처리하는지 공식 문서가 없다. AI가 Playwright MCP로 직접 HoyoLab 페이지에 접속해 페이지 로드 중 발생하는 모든 네트워크 요청을 캡처했다. 이미 출석한 계정으로 버튼 클릭 시 sign POST가 전혀 발생하지 않는다는 사실, 그리고 `/info` 응답에 `is_sign` 필드가 존재한다는 것을 이 방식으로 발견했다.

**접근성 스냅샷으로 DOM 구조 파악**

게임별로 HTML 구조가 달랐다. MCP 접근성 스냅샷을 통해 ZZZ/HKRPG는 부모 카드에 `cursor:pointer`, 원신은 자식 요소들 각각에 `cursor:pointer`가 있다는 구조 차이를 파악하고, force=True가 원신에서 실패하는 원인을 특정했다.

**자율 디버그 루프**

사용자가 실패 로그를 제공하면 AI가 원인 가설 수립 → 코드 수정 → `run.bat` 직접 실행 → 결과 분석의 루프를 반복했다. 도구를 통해 실제 실행 환경에 접근했기 때문에 "이론상 동작"이 아닌 실제 성공 여부로 검증할 수 있었다.

### 일반적인 AI 활용 vs 이 프로젝트에서의 AI 활용

| | 일반적 AI 활용 | 이 프로젝트 |
|---|---|---|
| 주요 역할 | 코드 스니펫 생성, 문법 교정 | 전체 설계·구현·디버깅 |
| 실행 환경 접근 | 없음 | MCP로 실제 브라우저 직접 조작 |
| 디버깅 방식 | 코드 리뷰 후 수정안 제시 | 실제 실행 → 로그 분석 → 수정 |
| 외부 API 분석 | 문서 기반 이해 | 라이브 네트워크 요청 직접 캡처 |
| 사용자 개입 | 매 단계 방향 지시 | 버그 로그 제공 + 최종 Y/N 판단 |

### 정량적 요약

- **작성 코드**: Python 867줄, JSON locale 297줄 (AI 전담, 총 1,164줄)
- **자율 처리한 버그**: 8개 (is_sign 감지, DOM 카드 오탐, Vue click 미등록, TimeoutError 미처리, count 파싱 타이밍, 오버레이 처리, 성공 감지 통일, 에러 토스트 타이밍)
- **커밋 수**: 18회 (초기 구현 포함)
- **개발 세션**: 2회
- **AI 자율 실행 도구**: Playwright MCP (브라우저 조작·네트워크 분석), Bash (스크립트 실행), 파일 편집 도구
