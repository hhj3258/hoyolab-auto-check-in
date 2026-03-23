#!/usr/bin/env python3
"""젠레스 존 제로 HoyoLab 자동 출석체크"""

import asyncio, json, os, re, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    from playwright.async_api import async_playwright
    _playwright_ok = True
except ImportError:
    _playwright_ok = False

# ── 경로 상수 ──────────────────────────────────────
SCRIPTS_DIR = Path(__file__).parent
ROOT_DIR    = SCRIPTS_DIR.parent
DATA_DIR    = ROOT_DIR / "data"

PROFILE_DIR = DATA_DIR / "browser_profile"
LOGGED_IN   = DATA_DIR / ".logged_in"
LANG_FILE   = DATA_DIR / ".lang"
SCHED_FILE  = DATA_DIR / ".sched_asked"

# 출석체크 페이지는 항상 한국어로 고정 (lang=ko-kr).
# 페이지 내 텍스트 셀렉터("이번 달 출석 체크", "N일 차" 등)는 이 언어에 의존하므로
# UI 언어(ko/en/ja)와 무관하게 페이지 언어는 반드시 한국어여야 합니다.
CHECKIN_URL    = (
    "https://act.hoyolab.com/bbs/event/signin/zzz/"
    "e202406031448091.html?act_id=e202406031448091&lang=ko-kr"
)
PAGE_LOCALE    = "ko-KR"   # 페이지 셀렉터가 한국어 텍스트에 의존하므로 고정

LAUNCH_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
]
WEBDRIVER_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
TASK_NAME = "ZZZ HoyoLab 출석체크"


class SessionExpiredError(Exception):
    pass


# ── 다국어 로딩 ────────────────────────────────────
LOCALES_DIR     = SCRIPTS_DIR / "locales"
SUPPORTED_LANGS = ("ko", "en", "ja")

def _load_locale(lang: str) -> dict:
    path = LOCALES_DIR / f"{lang}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ── 언어 선택 ──────────────────────────────────────
def select_language() -> str:
    if LANG_FILE.exists():
        lang = LANG_FILE.read_text(encoding="utf-8").strip()
        if lang in SUPPORTED_LANGS:
            return lang

    print("언어를 선택하세요 / Select language / 言語を選択してください")
    print("  1. 한국어")
    print("  2. English")
    print("  3. 日本語")
    choices = {"1": "ko", "2": "en", "3": "ja"}
    while True:
        ch = input("> ").strip()
        if ch in choices:
            lang = choices[ch]
            LANG_FILE.write_text(lang, encoding="utf-8")
            print()
            return lang
        print("1, 2, 3 중 선택 / Please choose 1, 2, or 3 / 1、2、3 から選択してください")


# ── 설치 확인 ──────────────────────────────────────
def _chromium_exists() -> bool:
    base = Path.home() / "AppData/Local/ms-playwright"
    return bool(list(base.glob("chromium-*"))) if base.exists() else False


def check_setup(t: dict) -> None:
    if _playwright_ok and _chromium_exists():
        return
    print(t["setup_needed"])
    r = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "_setup.py"), "--no-pause"],
        check=False,
    )
    if r.returncode != 0:
        print(t["setup_fail"])
        sys.exit(1)
    print(t["setup_done"])
    subprocess.run([sys.executable] + sys.argv)
    sys.exit(0)


# ── 스케줄러 등록 제안 ─────────────────────────────
def offer_scheduler(t: dict) -> None:
    if SCHED_FILE.exists():
        return
    r = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True,
    )
    if r.returncode == 0:
        print(t["sched_exists"])
        SCHED_FILE.touch()
        return

    print()
    ans = input(t["sched_ask"]).strip().lower()
    if ans != "y":
        print(t["sched_skip"])
        SCHED_FILE.touch()
        return

    subprocess.run([sys.executable, str(SCRIPTS_DIR / "_schedule.py"), "--no-pause"])
    SCHED_FILE.touch()
    print()


# ── UTC+8 날짜 ─────────────────────────────────────
def hoyolab_today() -> int:
    return datetime.now(timezone(timedelta(hours=8))).day


# ── 로그인 플로우 ──────────────────────────────────
async def login_flow(t: dict) -> None:
    print()
    print(t["login_guide1"])
    print(t["login_guide2"])

    for attempt in range(1, 4):
        if attempt > 1:
            print(t["retry_label"].format(n=attempt))

        login_ok = False

        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=False,
                locale=PAGE_LOCALE,
                args=LAUNCH_ARGS,
            )
            await ctx.add_init_script(WEBDRIVER_SCRIPT)
            await ctx.clear_cookies()

            page = await ctx.new_page()
            await page.goto("https://www.hoyolab.com/", wait_until="domcontentloaded")

            try:
                login_btn = page.locator(".login-box-side_bottom__btn")
                await login_btn.wait_for(timeout=8000)
                await login_btn.click(force=True)
            except Exception:
                pass

            print(t["login_no_close"])
            for tick in range(600):
                await asyncio.sleep(0.5)
                dots = "." * (tick % 3 + 1)
                print(f"\r{t['login_waiting']}{dots:<3}", end="", flush=True)
                try:
                    cookies = await ctx.cookies()
                except Exception:
                    break
                if any(c["name"] == "ltoken_v2" and c["value"] for c in cookies):
                    print(t["login_detected"])
                    login_ok = True
                    await asyncio.sleep(1)
                    break
            print()

            try:
                await ctx.close()
            except Exception:
                pass

        if login_ok:
            LOGGED_IN.touch()
            print(t["login_saved"])
            return

        if attempt < 3:
            print(t["login_warn"])

    print()
    print("=" * 50)
    print(t["login_fail"])
    print("=" * 50)
    sys.exit(1)


# ── 출석체크 플로우 ────────────────────────────────
async def do_checkin(t: dict, headless: bool) -> bool:
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=headless,
            locale=PAGE_LOCALE,
            args=LAUNCH_ARGS,
        )
        await ctx.add_init_script(WEBDRIVER_SCRIPT)

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print(t["connecting"])
        try:
            await page.goto(CHECKIN_URL, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(t["page_fail"].format(err=e))
            await ctx.close()
            return False

        today = hoyolab_today()

        try:
            await page.wait_for_selector("p:has-text('이번 달 출석 체크')", timeout=10000)
            await page.wait_for_selector("text=1일 차", timeout=10000)
        except Exception:
            await ctx.close()
            raise SessionExpiredError(t["session_err"])

        if today > 14:
            try:
                await page.get_by_text("더 보기").first.click()
                await page.wait_for_timeout(1000)
            except Exception:
                pass

        try:
            await page.wait_for_function(
                """() => {
                    const el = [...document.querySelectorAll('p')]
                        .find(p => p.textContent.includes('이번 달 출석 체크'));
                    return el && !el.textContent.includes('0회');
                }""",
                timeout=5000,
            )
        except Exception:
            pass
        count_text = await page.locator(
            "p:has-text('이번 달 출석 체크')"
        ).first.text_content()
        match = re.search(r"\d+", count_text or "")
        count = match.group() if match else "?"
        print(t["status"].format(count=count))
        print(t["date_today"].format(day=today))

        day_loc = page.get_by_text(f"{today}일 차", exact=True).first
        try:
            await day_loc.wait_for(timeout=5000)
        except Exception:
            print(t["btn_not_found"].format(day=today))
            await ctx.close()
            return False

        parent = day_loc.locator("xpath=..")
        if await parent.locator("img[class*='received']").count() > 0:
            print(t["already_done"].format(day=today))
            await ctx.close()
            return True

        print(t["executing"].format(day=today))
        await day_loc.click()

        # 1단계: 완료 팝업
        try:
            await page.wait_for_selector("text=오늘의 출석체크 완료", timeout=5000)
            print(t["check_success"])
            await ctx.close()
            return True
        except Exception:
            pass

        # 2단계: received 이미지 (렌더링 지연 대응)
        for _ in range(2):
            if await parent.locator("img[class*='received']").count() > 0:
                print(t["check_success"])
                await ctx.close()
                return True
            await page.wait_for_timeout(1000)

        print(t["check_fail"])
        await ctx.close()
        return False


# ── 메인 ──────────────────────────────────────────
async def main(t: dict) -> None:
    print("=" * 50)
    print(f"  {t['title']}")
    print(f"  {t['run_time']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    offer_scheduler(t)

    if not LOGGED_IN.exists():
        await login_flow(t)
        print()

    try:
        success = await do_checkin(t, headless=True)
    except SessionExpiredError as e:
        print(t["session_exp"].format(err=e))
        print(t["relogin"])
        LOGGED_IN.unlink(missing_ok=True)
        await login_flow(t)
        print()
        success = await do_checkin(t, headless=True)

    if not success:
        print(t["retry_vis"])
        success = await do_checkin(t, headless=False)

    if not success:
        print()
        print("=" * 50)
        print(t["final_fail"])
        print("=" * 50)


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lang = select_language()
    t = _load_locale(lang)
    check_setup(t)
    try:
        asyncio.run(main(t))
    except KeyboardInterrupt:
        print(t["interrupted"])
    except Exception as e:
        print()
        print("=" * 50)
        print(t["unexpected"].format(etype=type(e).__name__, err=e))
        print("=" * 50)
        sys.exit(1)
