# 젠레스 존 제로 자동 출석체크

HoyoLab 젠레스 존 제로 출석체크를 자동으로 수행하는 스크립트입니다.

[English](README.md)

## 요구사항

- Python 3.8 이상
- Windows

## 사용법

**`run.bat` 하나로 모든 것을 처리합니다.**

1. `run.bat` 실행
2. 최초 1회: 언어 선택 → 미설치 패키지 자동 설치 → HoyoLab 로그인
3. 이후 실행: 자동으로 헤드리스 출석체크 수행

### 작업 스케줄러 등록

최초 실행 시 매일 자동 실행 여부를 물어봅니다.
나중에 변경하려면 `schedule.bat`을 실행하세요.
등록 해제: `python scripts\_schedule.py delete`

## 파일 구조

```
├── run.bat               # 실행 파일 (단일 진입점)
├── schedule.bat          # 작업 스케줄러 관리
└── scripts/
    ├── zzz_checkin.py    # 메인 스크립트 (설치 확인, 언어 선택, 출석체크)
    ├── _setup.py         # 의존성 설치 (Playwright, Chromium)
    ├── _schedule.py      # 작업 스케줄러 등록/해제
    └── locales/          # 다국어 문자열 (ko / en / ja)
```

## 동작 방식

- Playwright를 이용해 Chromium 브라우저를 자동 조작합니다.
- 로그인 정보는 `data/browser_profile/` 폴더에 저장되며 재사용합니다.
- UTC+8(HoyoLab 서버 기준) 오늘 날짜의 출석 버튼을 클릭합니다.
- 이미 완료된 경우 별도 조작 없이 종료합니다.
- 세션 만료 시 자동으로 재로그인 플로우를 진행합니다.

## 언어 변경

`data/.lang` 파일을 삭제하면 다음 실행 시 언어 선택 화면이 다시 나타납니다.
