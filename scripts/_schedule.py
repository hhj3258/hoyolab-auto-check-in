"""
Windows 작업 스케줄러 등록/해제 스크립트

사용법:
  python _schedule.py          → 작업 등록
  python _schedule.py delete   → 작업 해제
"""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent
ROOT_DIR    = SCRIPTS_DIR.parent
RUN_BAT     = ROOT_DIR / "run.bat"
LANG_FILE   = ROOT_DIR / "data" / ".lang"
TASK_NAME   = "ZZZ HoyoLab 출석체크"


def _load_locale() -> dict:
    try:
        lang = LANG_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        lang = "ko"
    if lang not in ("ko", "en", "ja"):
        lang = "ko"
    with (SCRIPTS_DIR / "locales" / f"{lang}.json").open(encoding="utf-8") as f:
        return json.load(f)

t = _load_locale()


def query_task() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST"],
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
    for line in r.stdout.splitlines():
        line = line.strip()
        if any(k in line for k in ("다음 실행 시간", "Next Run Time", "次の実行時刻", "상태", "Status", "状態")):
            print(f"       {line}")
    print()
    ans = input(t["sched_change_time_ask"]).strip().lower()
    if ans != "y":
        print(t["sched_cancelled"])
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
        input(t["press_enter_to_exit"])
        sys.exit(1)

print()
register_task(time_str)
input(t["press_enter_to_exit"])
