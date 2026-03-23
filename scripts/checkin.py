#!/usr/bin/env python3
"""HoyoLab 자동 출석체크"""

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
GAMES_FILE  = DATA_DIR / ".games"

# 출석체크 페이지는 항상 한국어로 고정 (lang=ko-kr).
# 페이지 내 텍스트 셀렉터("N일 차", "N일째" 등)는 이 언어에 의존하므로
# UI 언어(ko/en/ja)와 무관하게 페이지 언어는 반드시 한국어여야 합니다.
PAGE_LOCALE = "ko-KR"

# count_keyword : 카운트 요소 탐색에 쓰이는 고유 문자열
# day_suffix    : 날짜 버튼 텍스트 접미사 ("일 차" 또는 "일째")
# more_btn      : "더 보기" 버튼 텍스트. None이면 버튼 없음(전체 표시)
GAMES = {
    "zzz": {
        "key":           "game_name_zzz",
        "url":           "https://act.hoyolab.com/bbs/event/signin/zzz/e202406031448091.html?act_id=e202406031448091&lang=ko-kr",
        "count_keyword": "이번 달 출석 체크",
        "day_suffix":    "일 차",
        "more_btn":      "더 보기",
    },
    "hkrpg": {
        "key":           "game_name_hkrpg",
        "url":           "https://act.hoyolab.com/bbs/event/signin/hkrpg/e202303301540311.html?act_id=e202303301540311&lang=ko-kr",
        "count_keyword": "이번 달 출석 체크",
        "day_suffix":    "일 차",
        "more_btn":      "더 보기",
    },
    "genshin": {
        "key":           "game_name_genshin",
        "url":           "https://act.hoyolab.com/ys/event/signin-sea-v3/index.html?act_id=e202102251931481&lang=ko-kr",
        "count_keyword": "이번 달 출석체크",
        "day_suffix":    "일째",
        "more_btn":      "더보기",
    },
    "nxx": {
        "key":           "game_name_nxx",
        "url":           "https://act.hoyolab.com/bbs/event/signin/nxx/index.html?act_id=e202202281857121&lang=ko-kr",
        "count_keyword": "이번 달 출석체크",
        "day_suffix":    "일 차",
        "more_btn":      "더 보기",
    },
    "bh3": {
        "key":           "game_name_bh3",
        "url":           "https://act.hoyolab.com/bbs/event/signin-bh3/index.html?act_id=e202110291205111&lang=ko-kr",
        "count_keyword": "이번 달 누적 출석",
        "day_suffix":    "일째",
        "more_btn":      None,
    },
}

LAUNCH_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
]
WEBDRIVER_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
TASK_NAME = "HoyoLab 출석체크"


class SessionExpiredError(Exception):
    pass


# ── 다국어 로딩 ────────────────────────────────────
LOCALES_DIR     = ROOT_DIR / "locales"
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


# ── 게임 선택 ──────────────────────────────────────
def select_games(t: dict) -> list:
    if GAMES_FILE.exists():
        saved = GAMES_FILE.read_text(encoding="utf-8").strip()
        keys = [k for k in saved.split(",") if k in GAMES]
        if keys:
            return keys

    import msvcrt
    os.system("")  # Windows ANSI 활성화

    game_list = list(GAMES.keys())
    selected = set()
    cursor = 0
    n_games = len(game_list)

    # cursor: 0 = 전체, 1~n_games = 개별 게임, n_games+1 = 완료
    def make_rows():
        rows = ["", t["game_select_title"], t["game_select_nav"], ""]
        all_mark = "✓" if len(selected) == n_games else ("-" if selected else " ")
        ptr = "▶" if cursor == 0 else " "
        rows.append(f"  {ptr} [{all_mark}] {t['game_select_all']}")
        for i, gid in enumerate(game_list):
            mark = "✓" if gid in selected else " "
            ptr  = "▶" if cursor == i + 1 else " "
            rows.append(f"  {ptr} [{mark}] {t[GAMES[gid]['key']]}")
        rows.append("")
        ptr = "▶" if cursor == n_games + 1 else " "
        rows.append(f"  {ptr}  {t['game_select_confirm']}")
        rows.append("")
        return rows

    rows = make_rows()
    for row in rows:
        print(row)

    while True:
        key = msvcrt.getwch()

        if key in ('\xe0', '\x00'):       # 특수키 prefix
            key2 = msvcrt.getwch()
            if key2 == 'H':               # ↑
                cursor = (cursor - 1) % (n_games + 2)
            elif key2 == 'P':             # ↓
                cursor = (cursor + 1) % (n_games + 2)
            else:
                continue
        elif key == '\r':                 # Enter
            if cursor == 0:               # 전체 토글
                if len(selected) == n_games:
                    selected.clear()
                else:
                    selected = set(game_list)
            elif cursor <= n_games:       # 개별 게임
                gid = game_list[cursor - 1]
                if gid in selected:
                    selected.discard(gid)
                else:
                    selected.add(gid)
            elif selected:                # 완료
                break
            else:
                print('\a', end='', flush=True)  # 빈 선택 시 경고음
                continue
        else:
            continue

        new_rows = make_rows()
        sys.stdout.write(f"\033[{len(rows)}A")
        for row in new_rows:
            sys.stdout.write(f"\r\033[K{row}\n")
        sys.stdout.flush()
        rows = new_rows

    result = [gid for gid in game_list if gid in selected]
    GAMES_FILE.write_text(",".join(result), encoding="utf-8")
    print()
    return result


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
async def do_checkin(t: dict, headless: bool, game: dict) -> bool:
    url        = game["url"]
    count_kw   = game["count_keyword"]
    day_suffix = game["day_suffix"]
    more_btn   = game["more_btn"]

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=headless,
            locale=PAGE_LOCALE,
            args=LAUNCH_ARGS,
        )
        await ctx.add_init_script(WEBDRIVER_SCRIPT)

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # 페이지 로드 중 info GET 응답 캐치 (is_sign: 오늘 이미 완료 여부)
        _info_data: dict = {}
        _info_event = asyncio.Event()
        _act_id = url.split("act_id=")[1].split("&")[0] if "act_id=" in url else ""

        async def _on_info_response(response):
            if (response.request.method == "GET"
                    and "/info" in response.url
                    and _act_id and _act_id in response.url):
                try:
                    body = await response.json()
                    data = body.get("data") or {}
                    _info_data.update(data)
                    _info_event.set()
                except Exception:
                    pass

        page.on("response", _on_info_response)

        print(t["connecting"])
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(t["page_fail"].format(err=e))
            await ctx.close()
            return False

        today = hoyolab_today()

        # 페이지 로드 확인 (세션 만료 감지)
        try:
            await page.wait_for_selector(f":has-text('{count_kw}')", timeout=10000)
            await page.wait_for_selector(f"text=1{day_suffix}", timeout=10000)
        except Exception:
            await ctx.close()
            raise SessionExpiredError(t["session_err"])

        # 카운트 로딩 대기 (최대 3회 재시도)
        count = 0
        for _ in range(3):
            await page.wait_for_timeout(1000)
            count = await page.evaluate(
                """(kw) => {
                    let best = null;
                    document.querySelectorAll('*').forEach(el => {
                        if (el.textContent.includes(kw)) {
                            if (!best || el.textContent.length < best.textContent.length)
                                best = el;
                        }
                    });
                    if (!best) return 0;
                    const m = best.textContent.match(/\\d+/);
                    return m ? parseInt(m[0]) : 0;
                }""",
                count_kw,
            )
            if count > 0:
                break
        print(t["status"].format(count=count))
        print(t["date_today"].format(day=today))

        target_day = count + 1

        if target_day > today:
            print(t["already_done"].format(day=today))
            await ctx.close()
            return True

        # 오늘 이미 출석 완료 여부 확인 (info API is_sign 필드)
        try:
            await asyncio.wait_for(_info_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        if _info_data.get("is_sign"):
            print(t["already_done"].format(day=today))
            await ctx.close()
            return True

        if more_btn and target_day > 14:
            try:
                await page.get_by_text(more_btn).first.click()
                await page.wait_for_timeout(1000)
            except Exception:
                pass

        day_loc = page.get_by_text(f"{target_day}{day_suffix}", exact=True).first
        try:
            await day_loc.wait_for(timeout=5000)
        except Exception:
            print(t["btn_not_found"].format(day=target_day))
            await ctx.close()
            return False

        # received 상태 확인 (카드 경계 탐색 — 인접 카드 오탐 방지)
        # 다음 상위 요소에 여러 날짜 텍스트가 포함되면 카드 경계로 판단하고 탐색 중단
        RECEIVED_JS = """
            ([suffix, day]) => {
                const dayText = `${day}${suffix}`;
                const all = Array.from(document.querySelectorAll('*'));
                const dayEl = all.find(el =>
                    el.textContent.trim() === dayText && el.children.length === 0
                );
                if (!dayEl) return false;
                let card = dayEl.parentElement;
                for (let i = 0; i < 5; i++) {
                    if (!card) break;
                    const next = card.parentElement;
                    if (!next) break;
                    const labels = Array.from(next.querySelectorAll('*'))
                        .filter(e => e.children.length === 0 && /^\\d+일/.test(e.textContent.trim()));
                    if (labels.length > 1) break;
                    card = next;
                }
                return !!card.querySelector('img[class*="received"]');
            }
        """

        already_received = await page.evaluate(RECEIVED_JS, [day_suffix, target_day])
        if already_received:
            print(t["already_done"].format(day=today))
            await ctx.close()
            return True

        # 클릭 전: API 응답 리스너 등록 (retcode -5003 = 오늘 이미 완료)
        _sign_data: dict = {}
        _sign_event = asyncio.Event()

        async def _on_sign_response(response):
            if response.request.method == "POST" and "sign" in response.url:
                try:
                    body = await response.json()
                    _sign_data.update(body)
                    _sign_event.set()
                except Exception:
                    pass

        page.on("response", _on_sign_response)

        print(t["executing"].format(day=target_day))

        # 오버레이/가이드 팝업 닫기 시도
        try:
            if await page.locator("[class*='common-mask']").count() > 0:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(800)
        except Exception:
            pass

        try:
            await day_loc.click(timeout=5000)
        except Exception:
            await day_loc.click(force=True)

        # 0단계: 에러 토스트 (계정 미연동 등)
        try:
            await page.wait_for_selector("text=캐릭터 정보를", timeout=2000)
            print(t["check_no_account"])
            await ctx.close()
            return True
        except Exception:
            pass

        # 1단계: API retcode 확인 (최대 3초 대기)
        try:
            await asyncio.wait_for(_sign_event.wait(), timeout=3.0)
            retcode = _sign_data.get("retcode")
            if retcode == 0:
                print(t["check_success"])
                await ctx.close()
                return True
            if retcode == -5003:  # 오늘 이미 출석 완료
                print(t["already_done"].format(day=today))
                await ctx.close()
                return True
        except asyncio.TimeoutError:
            pass

        # 2단계: 카운트 증가 확인 (최대 5초)
        for _ in range(5):
            await page.wait_for_timeout(1000)
            new_count = await page.evaluate(
                """(kw) => {
                    let best = null;
                    document.querySelectorAll('*').forEach(el => {
                        if (el.textContent.includes(kw)) {
                            if (!best || el.textContent.length < best.textContent.length)
                                best = el;
                        }
                    });
                    if (!best) return 0;
                    const m = best.textContent.match(/\\d+/);
                    return m ? parseInt(m[0]) : 0;
                }""",
                count_kw,
            )
            if new_count > count:
                print(t["check_success"])
                await ctx.close()
                return True

        # 3단계: received 이미지 확인 (렌더링 지연 대응)
        for _ in range(2):
            if await page.evaluate(RECEIVED_JS, [day_suffix, target_day]):
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
    games = select_games(t)

    if not LOGGED_IN.exists():
        await login_flow(t)
        print()

    for game_id in games:
        game = GAMES[game_id]
        print(t["game_checkin_start"].format(name=t[game["key"]]))

        success = False
        relogin_done = False

        for attempt in range(1, 4):
            if attempt > 1:
                print(t["retry_bg"].format(n=attempt))
            try:
                success = await do_checkin(t, headless=True, game=game)
                if success:
                    break
            except SessionExpiredError as e:
                if not relogin_done:
                    print(t["session_exp"].format(err=e))
                    print(t["relogin"])
                    LOGGED_IN.unlink(missing_ok=True)
                    await login_flow(t)
                    print()
                    relogin_done = True
            except Exception as e:
                print(t["unexpected"].format(etype=type(e).__name__, err=str(e)[:120]))

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
