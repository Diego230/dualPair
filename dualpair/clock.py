"""Dual-boot clock: both systems share one hardware clock (RTC).

Linux normally keeps it in UTC, Windows in local time, so each one reads the other's
writes as wrong by the time zone offset (1-2 hours in Italy). They agree when both use
the same standard:
  - Windows in UTC: registry value RealTimeIsUniversal=1 (recommended; done from Windows)
  - Linux in local time: `timedatectl set-local-rtc 1` (one click here; systemd warns about
    daylight-saving changes happening while neither system is running)
"""
from __future__ import annotations

import subprocess

from .errors import DualPairError
from .windows import WindowsData

OK_UTC = "ok_utc"              # both UTC: the recommended setup
OK_LOCAL = "ok_local"          # both local time: works, not recommended
CONFLICT = "conflict"          # Linux UTC, Windows local: the usual dual-boot problem
CONFLICT_REVERSE = "conflict_reverse"  # Linux local, Windows UTC: e.g. after fixing both sides

WINDOWS_COMMAND = (r'reg add "HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" '
                   r'/v RealTimeIsUniversal /t REG_DWORD /d 1 /f')


def linux_rtc_local() -> bool:
    """True if Linux keeps the hardware clock in local time."""
    try:
        r = subprocess.run(["timedatectl", "show", "-p", "LocalRTC", "--value"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip() in ("yes", "no"):
            return r.stdout.strip() == "yes"
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:  # without systemd: third line of /etc/adjtime is UTC or LOCAL (missing file = UTC)
        with open("/etc/adjtime") as f:
            lines = f.read().splitlines()
        return len(lines) >= 3 and lines[2].strip().upper() == "LOCAL"
    except OSError:
        return False


def linux_timezone() -> str | None:
    try:
        r = subprocess.run(["timedatectl", "show", "-p", "Timezone", "--value"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        with open("/etc/timezone") as f:
            return f.read().strip() or None
    except OSError:
        return None


def status(windows: WindowsData, linux_local: bool | None = None) -> dict:
    if linux_local is None:
        linux_local = linux_rtc_local()
    win_utc = windows.rtc_utc
    if not linux_local and win_utc:
        state = OK_UTC
    elif linux_local and not win_utc:
        state = OK_LOCAL
    elif not linux_local and not win_utc:
        state = CONFLICT
    else:
        state = CONFLICT_REVERSE
    return {
        "state": state,
        "linux": "local" if linux_local else "utc",
        "windows": "utc" if win_utc else "local",
        "windows_timezone": windows.timezone,
        "windows_command": WINDOWS_COMMAND,
    }


def set_linux(local: bool):
    """Change how Linux reads the hardware clock. The system clock (kept right by NTP) is
    written back to the RTC in the new standard: no --adjust-system-clock, which would do
    the opposite and copy the RTC's wrong reading into the system clock."""
    try:
        r = subprocess.run(["timedatectl", "set-local-rtc", "1" if local else "0"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DualPairError("clock_failed", detail=str(e))
    if r.returncode != 0:
        raise DualPairError("clock_failed", detail=(r.stderr or r.stdout).strip())
