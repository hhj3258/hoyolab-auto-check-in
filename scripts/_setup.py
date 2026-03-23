import json, subprocess, sys, importlib.util, importlib.metadata
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
LANG_FILE   = SCRIPTS_DIR.parent / "data" / ".lang"
PAUSE       = "--no-pause" not in sys.argv


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


def fail(msg: str, link: str = "") -> None:
    print()
    print("=" * 50)
    print(f"  {t['setup_err_prefix']} {msg}")
    if link:
        print(f"  {t['setup_download_label']}: {link}")
    print("=" * 50)
    if PAUSE:
        input(t["press_enter_to_exit"])
    sys.exit(1)


# ── 헤더 ──────────────────────────────────────────
print("=" * 50)
print(f"  {t['setup_header']}")
print("=" * 50)
print(f"\n  {t['setup_label_python_path']}: {sys.executable}")
print(f"  {t['setup_label_python_version']}: {sys.version.split()[0]}")
print()

# ── Python 버전 확인 ──────────────────────────────
if sys.version_info < (3, 8):
    fail(
        t["setup_err_python_too_old"].format(ver=sys.version.split()[0]),
        "https://www.python.org/downloads/",
    )

# ── 1단계: pip 확인 ───────────────────────────────
print(t["setup_step1_checking_pip"])
r = subprocess.run(
    [sys.executable, "-m", "pip", "--version"],
    capture_output=True,
)
if r.returncode != 0:
    fail(t["setup_err_pip_not_found"], "https://pip.pypa.io/en/stable/installation/")
print(f"  → {r.stdout.decode().strip().split('from')[0].strip()}")

# ── 2단계: playwright 패키지 ──────────────────────
print()
print(t["setup_step2_checking_playwright"])
if importlib.util.find_spec("playwright") is not None:
    version = importlib.metadata.version("playwright")
    print(t["setup_playwright_already_ok"].format(ver=version))
else:
    print(t["setup_playwright_installing"])
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--prefer-binary", "--disable-pip-version-check", "playwright"],
        check=False,
    )
    if r.returncode != 0:
        fail(t["setup_err_playwright_failed"], "https://playwright.dev/python/docs/intro")
    print(t["setup_playwright_done"])

# ── 3단계: Chromium 브라우저 ──────────────────────
print()
print(t["setup_step3_checking_chromium"])
chromium_path = Path.home() / "AppData/Local/ms-playwright"
chromium_dirs = list(chromium_path.glob("chromium-*")) if chromium_path.exists() else []

if chromium_dirs:
    print(t["setup_chromium_already_ok"].format(name=chromium_dirs[0].name))
else:
    print(t["setup_chromium_installing"])
    r = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
    )
    if r.returncode != 0:
        fail(t["setup_err_chromium_failed"], "https://playwright.dev/python/docs/intro")
    print(t["setup_chromium_done"])

# ── 완료 ──────────────────────────────────────────
print()
print("=" * 50)
if PAUSE:
    print(f"  {t['setup_all_done']}")
print("=" * 50)
if PAUSE:
    input(t["press_enter_to_exit"])
