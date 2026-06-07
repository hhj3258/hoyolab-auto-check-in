"""
Windows 작업 스케줄러 등록/해제 스크립트

사용법:
  python _schedule.py          → 작업 등록
  python _schedule.py delete   → 작업 해제
"""
import csv, io, json, subprocess, sys
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent
ROOT_DIR    = SCRIPTS_DIR.parent
RUN_BAT     = ROOT_DIR / "run.bat"
LANG_FILE   = ROOT_DIR / "data" / ".lang"
TASK_NAME   = "HoyoLab 출석체크"


def _load_locale() -> dict:
    try:
        lang = LANG_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        lang = "ko"
    if lang not in ("ko", "en", "ja"):
        lang = "ko"
    with (SCRIPTS_DIR.parent / "locales" / f"{lang}.json").open(encoding="utf-8") as f:
        return json.load(f)

t     = _load_locale()
PAUSE = "--no-pause" not in sys.argv


def query_task() -> subprocess.CompletedProcess:
    # CSV 출력은 컬럼 순서가 OS 표시 언어와 무관하게 고정되므로
    # 라벨 텍스트 매칭 없이 위치(인덱스)로 값을 읽을 수 있다.
    # /nh: 헤더 행 제거(헤더는 번역됨)  /v: 다음 실행 시간·상태 컬럼 포함
    return subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "CSV", "/nh", "/v"],
        capture_output=True, text=True, encoding="cp949",
    )


def delete_task() -> None:
    print(t["sched_delete_starting"].format(name=TASK_NAME))
    r = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True, encoding="cp949",
    )
    if r.returncode != 0:
        print(t["sched_delete_failed"].format(err=r.stderr.strip()))
        sys.exit(1)
    print(t["sched_delete_done"])


def register_task(time_str: str) -> None:
    r = subprocess.run(
        [
            "schtasks", "/create",
            "/tn", TASK_NAME,
            "/tr", str(RUN_BAT),
            "/sc", "daily",
            "/st", time_str,
            "/f",
            "/it",
        ],
        capture_output=True, text=True, encoding="cp949",
    )
    if r.returncode != 0:
        print(t["sched_fail"].format(err=r.stderr.strip()))
        sys.exit(1)
    print(t["sched_done"].format(time=time_str))
    print(f"       {t['sched_run_file_label']}: {RUN_BAT}")
    print()
    print(t["sched_note"])
    print(t["sched_hoyolab_reset_note"])


# ── 메뉴 모드 ──────────────────────────────────────
if len(sys.argv) > 1 and sys.argv[1] == "--menu":
    is_registered = query_task().returncode == 0
    print("=" * 50)
    print(f"  {t['sched_header']}")
    print("=" * 50)
    print()
    print(f"  {t['sched_menu_description']}")
    print()
    status = t["sched_menu_status_registered"] if is_registered else t["sched_menu_status_not_registered"]
    print(f"  {status}")
    print()
    print(f"  {t['sched_menu_option_register']}")
    print(f"  {t['sched_menu_option_unregister']}")
    print()
    choice = input("> ").strip()
    if choice == "1":
        sys.argv = [sys.argv[0]]
    elif choice == "2":
        sys.argv = [sys.argv[0], "delete"]
    else:
        sys.exit(0)

# ── 삭제 모드 ──────────────────────────────────────
if len(sys.argv) > 1 and sys.argv[1] == "delete":
    if query_task().returncode != 0:
        print(t["sched_delete_not_registered"].format(name=TASK_NAME))
        sys.exit(0)
    delete_task()
    input(t["press_enter_to_exit"])
    sys.exit(0)

# ── 등록 모드 ──────────────────────────────────────
print("=" * 50)
print(f"  {t['sched_header']}")
print("=" * 50)
print()

r = query_task()
if r.returncode == 0:
    print(t["sched_already_registered_detail"].format(name=TASK_NAME))
    # CSV verbose 컬럼: [0]호스트 [1]작업이름 [2]다음 실행 시간 [3]상태 ...
    rows = list(csv.reader(io.StringIO(r.stdout)))
    if rows and len(rows[0]) > 3:
        print(f"       {t['sched_label_next_run']}: {rows[0][2]}")
        print(f"       {t['sched_label_status']}: {rows[0][3]}")
    print()
    ans = input(t["sched_change_time_ask"]).strip().lower()
    if ans != "y":
        print(t["sched_cancelled"])
        if PAUSE:
            input(t["press_enter_to_exit"])
        sys.exit(0)
    print()

DEFAULT_TIME = "01:05"
print(t["sched_recommend_time_note"])
ans = input(t["sched_default_ask"]).strip().lower()
if ans in ("", "y"):
    time_str = DEFAULT_TIME
else:
    time_str = input(t["sched_time_ask"]).strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        print(t["sched_err_invalid_time"].format(time=time_str))
        if PAUSE:
            input(t["press_enter_to_exit"])
        sys.exit(1)

print()
register_task(time_str)
if PAUSE:
    input(t["press_enter_to_exit"])
