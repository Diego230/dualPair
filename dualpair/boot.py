"""Firmware boot order (UEFI), read and changed with efibootmgr.

Some Windows updates put "Windows Boot Manager" back first, so the PC starts Windows directly
and the Linux boot menu (GRUB) is never shown. DualPair can put Linux back first, and remember
that the user wants it kept first (DualPair for Windows then restores it after such updates).
"""
from __future__ import annotations

import json
import os
import re
import subprocess

from .errors import DualPairError

_ENTRY_RE = re.compile(r"^Boot([0-9A-Fa-f]{4})(\*?)\s+(.*)$")
_LOADER_RE = re.compile(r"\\EFI\\[^\s)\t]+?\.efi", re.IGNORECASE)
WINDOWS_LOADER = "\\efi\\microsoft\\boot\\bootmgfw.efi"
SETTINGS = "settings.json"


def parse(output: str) -> dict:
    """Parse `efibootmgr -v` (old File(...) and new plain-path formats)."""
    current, order, entries = None, [], {}
    for line in output.splitlines():
        line = line.rstrip()
        if line.startswith("BootCurrent:"):
            current = line.split(":", 1)[1].strip().upper()
        elif line.startswith("BootOrder:"):
            order = [x.strip().upper() for x in line.split(":", 1)[1].split(",") if x.strip()]
        else:
            m = _ENTRY_RE.match(line)
            if m:
                rest = m.group(3)
                loader = _LOADER_RE.search(rest)
                label = re.split(r"\t|\s{2,}|\s(?=HD\(|PciRoot\(|VenHw\(|FvVol\()", rest, maxsplit=1)[0].strip()
                entries[m.group(1).upper()] = {"label": label, "active": m.group(2) == "*",
                                               "loader": loader.group(0) if loader else None}
    return {"current": current, "order": order, "entries": entries}


def read() -> dict | None:
    """Boot entries and order, or None on a non-UEFI system / without efibootmgr."""
    fake = os.environ.get("DUALPAIR_TEST_EFIBOOTMGR")   # development/screenshots only; pkexec clears the env
    if fake and "PKEXEC_UID" not in os.environ:
        with open(fake) as f:
            return parse(f.read())
    if not os.path.isdir("/sys/firmware/efi"):
        return None
    try:
        r = subprocess.run(["efibootmgr", "-v"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return parse(r.stdout)


def grub_lists_windows(cfg_paths=("/boot/grub/grub.cfg", "/boot/grub2/grub.cfg")) -> bool | None:
    """Does the GRUB menu have a Windows entry? (Many distributions turn os-prober off.)"""
    for p in cfg_paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        return bool(re.search(r"bootmgfw\.efi|menuentry ['\"]Windows", text, re.IGNORECASE))
    return None


def state(info: dict | None, settings: dict) -> dict:
    if not info:
        return {"available": False}
    cur, order, entries = info["current"], info["order"], info["entries"]
    linux = entries.get(cur) if cur else None
    win_id = next((i for i, e in entries.items() if (e["loader"] or "").lower() == WINDOWS_LOADER), None)
    return {
        "available": bool(cur and linux),
        "linux_entry": cur, "linux_label": linux["label"] if linux else None,
        "linux_loader": linux["loader"] if linux else None,
        "windows_entry": win_id,
        "first": order[0] if order else None,
        "first_label": entries.get(order[0], {}).get("label") if order else None,
        "first_is_linux": bool(order and order[0] == cur),
        "keep_linux_first": bool(settings.get("keep_linux_first")),
        "grub_lists_windows": grub_lists_windows(),
    }


def put_linux_first(info: dict):
    cur, order = info["current"], info["order"]
    if not cur:
        raise DualPairError("boot_unknown")
    new = [cur] + [x for x in order if x != cur]
    try:
        r = subprocess.run(["efibootmgr", "-o", ",".join(new)], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DualPairError("boot_failed", detail=str(e))
    if r.returncode != 0:
        raise DualPairError("boot_failed", detail=(r.stderr or r.stdout).strip())


def load_settings(state_dir: str) -> dict:
    try:
        with open(os.path.join(state_dir, SETTINGS)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(state_dir: str, data: dict):
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    path = os.path.join(state_dir, SETTINGS)
    with open(path + ".tmp", "w") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)
