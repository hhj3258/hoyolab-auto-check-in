# ZZZ HoyoLab Auto Check-in

Automated HoyoLab daily check-in script for Zenless Zone Zero.

**Language:** English | [한국어](README.ko.md)

---

## Requirements

- [Python 3.8+](https://www.python.org/downloads/) — must be installed manually before running
- Windows

> A browser does not need to be installed separately. The script downloads and manages its own browser automatically.

---

## Usage

1. Run `run.bat`
2. First run only:
   - Select language (Korean / English / Japanese)
   - Missing dependencies are installed automatically
   - A browser window opens — log in to HoyoLab manually
3. From the second run onwards, check-in is performed silently in the background

---

## Task Scheduler

On first run, you will be asked whether to register a daily scheduled task.
To manage the schedule later, run `schedule.bat`.

> HoyoLab resets at UTC+8 midnight (01:00 KST). A run time of 01:05 KST or later is recommended.

---

## File Structure

```
├── run.bat               # Entry point
├── schedule.bat          # Task scheduler management
└── scripts/
    ├── zzz_checkin.py    # Main script
    ├── _setup.py         # Dependency installer
    ├── _schedule.py      # Task scheduler registration / removal
    └── locales/          # Locale strings (ko / en / ja)
```

---

## How It Works

### Browser Automation
Uses [Playwright](https://playwright.dev/python/) to drive a Chromium browser in headless mode.
The login session is saved locally so that logging in is only required once.

### Login Detection
After the browser opens, the script waits for login to complete.
Once detected, the session is saved and the browser closes automatically.

### Check-in
1. Opens the ZZZ HoyoLab check-in page
2. Determines today's date based on HoyoLab server time (UTC+8)
3. Scrolls to today's reward card if needed
4. Exits immediately if today's check-in is already done
5. Clicks the card and confirms the check-in was successful

### Session Expiry
If the saved session has expired, the browser opens automatically for re-login, then the check-in is retried.

---

## Security & Privacy

- **No credentials are stored.** The script never reads or saves your HoyoLab ID or password. Login is done manually through the official HoyoLab website in a real browser window.
- **Session data stays on your machine.** The browser session (cookies) is saved locally in `data/browser_profile/` and is never transmitted anywhere.
- **No external servers involved.** The script communicates only with HoyoLab directly, the same as using the website normally.
- **Open source.** You can review every line of code in this repository.

---

## Changing Language

Delete `data/.lang` and the language selection prompt will appear on the next run.
