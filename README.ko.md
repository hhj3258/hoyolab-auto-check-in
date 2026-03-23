# 젠레스 존 제로 자동 출석체크

HoyoLab 젠레스 존 제로 출석체크를 자동으로 수행하는 스크립트입니다.

**언어:** [English](README.md) | 한국어

---

## 요구사항

- Python 3.8 이상
- Windows

## 사용법

**`run.bat` 하나로 모든 것을 처리합니다.**

1. `run.bat` 실행
2. 최초 1회만:
   - 언어 선택 (한국어 / English / 日本語)
   - 미설치 패키지 자동 설치 (Playwright, Chromium)
   - 브라우저가 열리면 HoyoLab에 수동으로 로그인
3. 이후 실행: 백그라운드에서 자동으로 출석체크 수행

### 작업 스케줄러 등록

최초 실행 시 매일 자동 실행 여부를 물어봅니다.
나중에 변경하려면 `schedule.bat`을 실행하세요.
등록 해제: `python scripts\_schedule.py delete`

> HoyoLab은 UTC+8 자정(KST 01:00)에 초기화됩니다. KST 01:05 이후 실행을 권장합니다.

## 파일 구조

```
├── run.bat               # 단일 진입점
├── schedule.bat          # 작업 스케줄러 관리
└── scripts/
    ├── zzz_checkin.py    # 메인 스크립트
    ├── _setup.py         # 의존성 설치
    ├── _schedule.py      # 작업 스케줄러 등록/해제
    └── locales/          # 다국어 문자열 (ko / en / ja)
```

## 동작 방식

### 브라우저 자동화
[Playwright](https://playwright.dev/python/)를 사용해 Chromium 브라우저를 헤드리스 모드로 실행합니다.
영구 브라우저 프로필(`data/browser_profile/`)에 HoyoLab 세션이 저장되므로 로그인은 최초 1회만 필요합니다.

### 로그인 감지
브라우저가 열린 후 0.5초 간격으로 `ltoken_v2` 쿠키를 폴링합니다(최대 5분).
감지되면 세션이 저장되고 브라우저가 자동으로 닫힙니다.

### 출석체크 로직
1. ZZZ HoyoLab 출석체크 페이지로 이동 (DOM 셀렉터 안정성을 위해 한국어 로케일 고정)
2. UTC+8 기준 오늘 날짜를 계산 (HoyoLab 서버 기준)
3. 15일 이후면 '더 보기'를 클릭해 해당 날짜 카드로 스크롤
4. 오늘 카드가 이미 `received` 상태인지 확인 — 완료 시 종료
5. 카드를 클릭하고 완료 팝업 또는 `received` 상태 전환을 확인

### 세션 만료 처리
출석체크 달력 로딩에 실패하면(세션 만료) 자동으로 브라우저를 열어 재로그인 후 출석체크를 재시도합니다.

### 봇 감지 우회
- `--disable-blink-features=AutomationControlled` 브라우저 실행 인자 적용
- init script로 `navigator.webdriver` 속성을 `undefined`로 덮어씁니다

## 언어 변경

`data/.lang` 파일을 삭제하면 다음 실행 시 언어 선택 화면이 다시 나타납니다.
