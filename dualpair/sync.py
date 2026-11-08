# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Compare Windows and Linux pairings and copy Windows keys into BlueZ."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field

from . import bluez
from .errors import DualPairError
from .windows import WindowsData, WinDevice

STATE_DIR = "/var/lib/dualpair"
KEEP_BACKUPS = 5             # newest backups kept; older ones are deleted
MAX_BACKUP_AGE_DAYS = 30     # ...and none older than this, except the newest
_BACKUP_ID = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
_KEY_LINE = re.compile(r"^(Key=).*$", re.MULTILINE)

IN_SYNC = "in_sync"            # works on both systems
NEEDS_SYNC = "needs_sync"      # paired on both, keys differ -> copy from Windows
WINDOWS_ONLY = "windows_only"  # paired only on Windows -> import into Linux
LINUX_ONLY = "linux_only"      # paired only on Linux -> pair it on Windows first
ACTIONABLE = (NEEDS_SYNC, WINDOWS_ONLY)


@dataclass
class Plan:
    status: str
    address: str
    adapter_linux: str | None
    adapter_windows: str | None
    name: str | None
    kind: str
    win: WinDevice | None = None
    linux: bluez.LinuxDevice | None = None

    @property
    def newer(self) -> str | None:
        """For keys that differ: which system stored its keys last (a hint of who paired last)."""
        if self.status != NEEDS_SYNC or not self.win or not self.linux:
            return None
        w, l = self.win.paired_at, self.linux.paired_at
        if not w or not l:
            return None
        return "linux" if l > w else "windows"

    @property
    def experimental(self) -> bool:
        # a new classic device gets a guessed key type; LE imports are well understood
        return self.status == WINDOWS_ONLY and self.kind in ("classic", "dual")

    def to_dict(self):
        return {
            "status": self.status, "address": self.address, "name": self.name, "kind": self.kind,
            "adapter_linux": self.adapter_linux, "adapter_windows": self.adapter_windows,
            "experimental": self.experimental, "newer": self.newer,
        }


@dataclass
class Scan:
    windows: WindowsData
    bluez_root: str
    plans: list[Plan] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)

    def to_dict(self):
        return {
            "version": 1,
            "windows": {"source": self.windows.source, "hive_dirty": self.windows.hive_dirty,
                        "control_set": self.windows.control_set},
            "notes": self.notes,
            "devices": [p.to_dict() for p in self.plans],
        }


def _map_adapters(win: list[str], lin: list[str], notes: list) -> dict[str, str]:
    mapping = {a: a for a in win if a in lin}
    rest_w = [a for a in win if a not in mapping]
    rest_l = [a for a in lin if a not in mapping.values()]
    if len(rest_w) == 1 and len(rest_l) == 1 and not mapping:
        mapping[rest_w[0]] = rest_l[0]
        notes.append({"code": "adapter_mapped", "windows": rest_w[0], "linux": rest_l[0]})
    else:
        for a in rest_w:
            notes.append({"code": "adapter_unmatched", "windows": a})
    return mapping


def _matches(w: WinDevice, l: bluez.LinuxDevice) -> bool:
    if w.link_key and l.link_key != w.link_key:
        return False
    if w.le:
        if l.ltk != (w.le.ltk, w.le.ediv, w.le.rand):
            return False
    return True


def scan(windows: WindowsData, bluez_root: str = bluez.BLUEZ_DIR) -> Scan:
    if bluez_root == bluez.BLUEZ_DIR and os.geteuid() != 0:
        raise DualPairError("not_root")
    s = Scan(windows, bluez_root)
    if windows.hive_dirty:
        s.notes.append({"code": "hive_dirty"})
    if not windows.bt_present:
        s.notes.append({"code": "no_bt_keys"})
    lin_adapters = bluez.adapters(bluez_root)
    if not lin_adapters:  # not fatal: the other dual-boot checks (clock) still work
        s.notes.append({"code": "no_linux_adapter"})
        return s
    mapping = _map_adapters(windows.adapters, lin_adapters, s.notes)
    lin_devs = {a: bluez.devices(a, bluez_root) for a in lin_adapters}
    seen = set()
    for w in windows.devices:
        la = mapping.get(w.adapter)
        if la is None:
            continue
        l = lin_devs[la].get(w.address)
        seen.add((la, w.address))
        if l is None or not l.paired:
            status = WINDOWS_ONLY
        else:
            status = IN_SYNC if _matches(w, l) else NEEDS_SYNC
        s.plans.append(Plan(status, w.address, la, w.adapter, w.name or (l.name if l else None),
                            w.kind, w, l))
    for la in lin_adapters:
        for addr, l in lin_devs[la].items():
            if (la, addr) not in seen and l.paired:
                kind = "dual" if l.link_key and l.ltk else ("le" if l.ltk else "classic")
                s.plans.append(Plan(LINUX_ONLY, addr, la, None, l.name, kind, None, l))
    order = {NEEDS_SYNC: 0, WINDOWS_ONLY: 1, IN_SYNC: 2, LINUX_ONLY: 3}
    s.plans.sort(key=lambda p: (order[p.status], (p.name or p.address).lower()))
    return s


# ---------------------------------------------------------------- building info files
def build_info(p: Plan):
    """New BlueZ info content for a plan: the existing file with Windows' keys merged in."""
    w = p.win
    cfg = bluez.load_info(p.linux.path) if p.linux else bluez.new_config()
    if not cfg.has_section("General"):
        cfg.add_section("General")
    g = cfg["General"]
    if "Name" not in g:
        g["Name"] = w.name or p.address
    techs = [t for t in g.get("SupportedTechnologies", "").split(";") if t]
    if w.link_key and "BR/EDR" not in techs:
        techs.append("BR/EDR")
    if w.le and "LE" not in techs:
        techs.append("LE")
    g["SupportedTechnologies"] = ";".join(techs) + ";"
    if w.le:
        g["AddressType"] = w.le.address_type
    g.setdefault("Trusted", "true")
    g.setdefault("Blocked", "false")

    if w.link_key:
        if not cfg.has_section("LinkKey"):
            cfg.add_section("LinkKey")
        lk = cfg["LinkKey"]
        lk["Key"] = w.link_key
        lk.setdefault("Type", "4")       # kept from the Linux pairing when there was one
        lk.setdefault("PINLength", "0")

    if w.le:
        le = w.le
        old_auth = None
        if cfg.has_section("LongTermKey"):
            try:
                old_auth = int(cfg["LongTermKey"].get("Authenticated", ""))
            except ValueError:
                pass
        else:
            cfg.add_section("LongTermKey")
        auth = le.authenticated
        # same pairing method as the Linux pairing (legacy vs Secure Connections): keep its MITM flag
        if old_auth is not None and (old_auth >= 2) == le.secure_connections:
            auth = old_auth
        t = cfg["LongTermKey"]
        t["Key"] = le.ltk
        t["Authenticated"] = str(auth)
        t["EncSize"] = str(le.enc_size)
        t["EDiv"] = str(le.ediv)
        t["Rand"] = str(le.rand)
        if le.irk:
            if not cfg.has_section("IdentityResolvingKey"):
                cfg.add_section("IdentityResolvingKey")
            cfg["IdentityResolvingKey"]["Key"] = le.irk
    return cfg


# ---------------------------------------------------------------- applying, backups
def _systemctl(action: str, enabled: bool):
    if not enabled:
        return
    try:
        subprocess.run(["systemctl", action, "bluetooth"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _backup_root(state_dir: str) -> str:
    root = os.path.join(state_dir, "backups")
    os.makedirs(root, mode=0o700, exist_ok=True)
    os.chmod(state_dir, 0o700)
    return root


def redact(info: str) -> str:
    return _KEY_LINE.sub(r"\1<hidden>", info)


def apply(s: Scan, addresses: list[str] | None, state_dir: str = STATE_DIR,
          restart: bool = True, force: bool = False, dry_run: bool = False, show_keys: bool = False) -> dict:
    """Copy Windows keys for the given addresses (None = every actionable device)."""
    if s.windows.hive_dirty and not force:
        raise DualPairError("hive_dirty")
    wanted = None if addresses is None else {a.upper() for a in addresses}
    todo = [p for p in s.plans if p.status in ACTIONABLE and (wanted is None or p.address in wanted)]
    if wanted:
        known = {p.address for p in s.plans}
        missing = sorted(wanted - known)
        if missing:
            raise DualPairError("unknown_device", address=", ".join(missing))
    if not todo:
        return {"applied": [], "backup_id": None, "dry_run": dry_run}

    contents = [(p, bluez.dump_info(build_info(p))) for p in todo]
    if dry_run:
        return {"applied": [dict(p.to_dict(), info=c if show_keys else redact(c)) for p, c in contents],
                "backup_id": None, "dry_run": True}

    backup_id = time.strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(_backup_root(state_dir), backup_id)
    n = 1
    while os.path.exists(bdir):
        n += 1
        bdir = os.path.join(_backup_root(state_dir), f"{backup_id}-{n}")
    backup_id = os.path.basename(bdir)
    os.makedirs(bdir, mode=0o700)
    manifest = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "bluez_root": s.bluez_root, "entries": []}
    for p in todo:
        dev_dir = os.path.join(s.bluez_root, p.adapter_linux, p.address)
        existed = os.path.isfile(os.path.join(dev_dir, "info"))
        if existed:
            dst = os.path.join(bdir, p.adapter_linux, p.address)
            os.makedirs(dst, mode=0o700)
            shutil.copy2(os.path.join(dev_dir, "info"), os.path.join(dst, "info"))
        manifest["entries"].append({"adapter": p.adapter_linux, "address": p.address,
                                    "name": p.name, "existed": existed, "dir_existed": os.path.isdir(dev_dir)})
    with open(os.path.join(bdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    _systemctl("stop", restart)
    try:
        for p, content in contents:
            path = os.path.join(s.bluez_root, p.adapter_linux, p.address, "info")
            cfg = bluez.new_config()
            cfg.read_string(content)
            bluez.write_info(cfg, path)
            cache = os.path.join(s.bluez_root, p.adapter_linux, "cache", p.address)
            if os.path.isfile(cache):
                os.remove(cache)
    finally:
        _systemctl("start", restart)
    prune_backups(state_dir)
    return {"applied": [p.to_dict() for p in todo], "backup_id": backup_id, "dry_run": False}


def prune_backups(state_dir: str = STATE_DIR, keep: int = KEEP_BACKUPS, max_age_days: int = MAX_BACKUP_AGE_DAYS):
    """Old backups hold old keys in clear text: keep only the few newest, and none older than a month."""
    root = os.path.join(state_dir, "backups")
    if not os.path.isdir(root):
        return
    ids = sorted((b for b in os.listdir(root) if _BACKUP_ID.match(b)), reverse=True)
    cutoff = time.time() - max_age_days * 86400
    for i, b in enumerate(ids):
        path = os.path.join(root, b)
        if i >= keep or (i > 0 and os.path.getmtime(path) < cutoff):
            shutil.rmtree(path, ignore_errors=True)


def list_backups(state_dir: str = STATE_DIR) -> list[dict]:
    root = os.path.join(state_dir, "backups")
    out = []
    if not os.path.isdir(root):
        return out
    for b in sorted(os.listdir(root), reverse=True):
        if not _BACKUP_ID.match(b):
            continue
        m = os.path.join(root, b, "manifest.json")
        if os.path.isfile(m):
            with open(m) as f:
                man = json.load(f)
            out.append({"id": b, "created": man.get("created"),
                        "devices": [e.get("name") or e["address"] for e in man.get("entries", [])]})
    return out


def restore(backup_id: str | None = None, state_dir: str = STATE_DIR, restart: bool = True,
            bluez_root: str = bluez.BLUEZ_DIR) -> dict:
    backups = list_backups(state_dir)
    if not backups:
        raise DualPairError("no_backups")
    if backup_id is None:
        backup_id = backups[0]["id"]
    if not _BACKUP_ID.match(backup_id):
        raise DualPairError("unknown_backup", backup=backup_id)
    bdir = os.path.join(state_dir, "backups", backup_id)
    if not os.path.isfile(os.path.join(bdir, "manifest.json")):
        raise DualPairError("unknown_backup", backup=backup_id)
    with open(os.path.join(bdir, "manifest.json")) as f:
        man = json.load(f)
    # never trust paths from the manifest: names must be MAC addresses, target is our BlueZ folder
    if os.path.realpath(man.get("bluez_root", "")) != os.path.realpath(bluez_root):
        raise DualPairError("bad_backup", backup=backup_id)
    entries = man.get("entries", [])
    for e in entries:
        if not (isinstance(e, dict) and bluez.MAC_RE.match(str(e.get("adapter")))
                and bluez.MAC_RE.match(str(e.get("address")))):
            raise DualPairError("bad_backup", backup=backup_id)
        if e.get("existed"):
            src = os.path.join(bdir, e["adapter"], e["address"], "info")
            if os.path.islink(src) or not os.path.isfile(src):
                raise DualPairError("bad_backup", backup=backup_id)
    _systemctl("stop", restart)
    try:
        for e in entries:
            dev_dir = os.path.join(bluez_root, e["adapter"], e["address"])
            if e["existed"]:
                with open(os.path.join(bdir, e["adapter"], e["address"], "info"), "rb") as f:
                    bluez.write_bytes(f.read(), os.path.join(dev_dir, "info"))
            elif not e.get("dir_existed") and os.path.isdir(dev_dir) and not os.path.islink(dev_dir):
                shutil.rmtree(dev_dir)
            elif os.path.isfile(os.path.join(dev_dir, "info")):
                os.remove(os.path.join(dev_dir, "info"))
            cache = os.path.join(bluez_root, e["adapter"], "cache", e["address"])
            if os.path.isfile(cache):
                os.remove(cache)
    finally:
        _systemctl("start", restart)
    return {"restored": backup_id, "devices": [e.get("name") or e["address"] for e in entries]}
