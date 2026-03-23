# ZZZ HoyoLab Auto Check-in

Automated HoyoLab daily check-in script for Zenless Zone Zero.

[한국어](README.ko.md)

## Requirements

- Python 3.8+
- Windows

## Usage

**`run.bat` handles everything in one step.**

1. Run `run.bat`
2. First run: select language → auto-install dependencies → log in to HoyoLab
3. Subsequent runs: headless check-in performed automatically

### Task Scheduler

On first run, you will be asked whether to register a daily scheduled task.
To change the schedule later, run `schedule.bat`.
To unregister: `python scripts\_schedule.py delete`

## File Structure

```
├── run.bat               # Entry point
├── schedule.bat          # Task scheduler management
└── scripts/
    ├── zzz_checkin.py    # Main script (setup check, language selection, check-in)
    ├── _setup.py         # Dependency installer (Playwright, Chromium)
    ├── _schedule.py      # Task scheduler registration / removal
    └── locales/          # Locale strings (ko / en / ja)
```

## How It Works

- Uses Playwright to automate a Chromium browser.
- Login session is stored in `data/browser_profile/` and reused on subsequent runs.
- Clicks the check-in button for today's date based on UTC+8 (HoyoLab server time).
- Exits silently if check-in is already completed.
- Re-login flow is triggered automatically if the session expires.

## Changing Language

Delete `data/.lang` and the language selection prompt will appear on the next run.
