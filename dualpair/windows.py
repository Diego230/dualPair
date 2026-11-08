"""Read Bluetooth pairing keys from a Windows installation, without booting Windows.

Windows keeps them in the SYSTEM registry hive:
  ControlSet00N\\Services\\BTHPORT\\Parameters\\Keys\\<adapter>\\
      <device>         REG_BINARY, 16 bytes  -> classic (BR/EDR) link key
      <device>\\        subkey               -> Bluetooth LE keys (LTK, EDIV, ERand, IRK, ...)
The hive is opened read-only: Windows is never modified.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

from .errors import DualPairError
from .regf import Hive, HiveError, REG_BINARY

_HEX12 = re.compile(r"^[0-9a-fA-F]{12}$")
HIVE_RELPATH = ("Windows", "System32", "config", "SYSTEM")


_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_name(name) -> str | None:
    """Device names come from the Windows registry, i.e. from outside: drop control characters
    (a newline could add lines to the BlueZ file) and cap the length (Bluetooth names are <= 248 bytes)."""
    if not isinstance(name, str):
        return None
    name = _CONTROL.sub("", name).strip()[:248]
    return name or None


def to_mac(hex12: str) -> str:
    h = hex12.upper()
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


@dataclass
class LEKeys:
    ltk: str                 # hex, as stored by Windows (same byte order BlueZ uses)
    enc_size: int
    ediv: int
    rand: int
    irk: str | None
    address_type: str        # "public" or "static"
    authenticated: int       # BlueZ LTK type: 0 legacy, 2 Secure Connections (+1 if MITM)

    @property
    def secure_connections(self) -> bool:
        return self.ediv == 0 and self.rand == 0


@dataclass
class WinDevice:
    adapter: str             # MAC, e.g. C4:13:75:C0:E2:E6
    address: str
    name: str | None = None
    link_key: str | None = None   # classic
    le: LEKeys | None = None
    paired_at: datetime.datetime | None = None   # when Windows last stored keys for it

    @property
    def kind(self) -> str:
        if self.link_key and self.le:
            return "dual"
        return "le" if self.le else "classic"


@dataclass
class WindowsData:
    source: str
    hive_dirty: bool
    control_set: int
    adapters: list[str] = field(default_factory=list)
    devices: list[WinDevice] = field(default_factory=list)
    bt_present: bool = True              # False: Windows has no Bluetooth pairings at all
    rtc_utc: bool = False                # RealTimeIsUniversal=1: Windows reads the hardware clock as UTC
    timezone: str | None = None          # Windows time zone name, e.g. "W. Europe Standard Time"
    export_id: str | None = None         # set when the data comes from a DualPair for Windows export
    fast_startup: bool | None = None     # Windows Fast Startup (HiberbootEnabled); None if unknown
    hibernated: bool | None = None       # hiberfil.sys holds a hibernation image right now


# ---------------------------------------------------------------- hive parsing
def _name_from_devices(devices_key, hex12: str) -> str | None:
    if devices_key is None:
        return None
    k = devices_key.subkey(hex12)
    if k is None:
        return None
    raw = k.get("Name")
    if isinstance(raw, bytes):
        return clean_name(raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace"))
    return clean_name(raw)


def _name_from_bthle(bthle_key, hex12: str) -> str | None:
    """LE device names live in Enum\\BTHLE\\Dev_<address>\\<instance>\\FriendlyName."""
    if bthle_key is None:
        return None
    k = bthle_key.subkey("Dev_" + hex12)
    for inst in (k.subkeys() if k else []):
        name = clean_name(inst.get("FriendlyName"))
        if name:
            return name
    return None


def read_hive(hive: Hive, source: str) -> WindowsData:
    select = hive.open("Select")
    current = 1
    if select is not None:
        current = select.get("Current") or select.get("Default") or 1
    bthle_key = hive.open(r"ControlSet%03d\Enum\BTHLE" % current)
    params = hive.open(r"ControlSet%03d\Services\BTHPORT\Parameters" % current)
    keys = params.subkey("Keys") if params else None
    devices_key = params.subkey("Devices") if params else None

    data = WindowsData(source=source, hive_dirty=hive.dirty, control_set=current, bt_present=keys is not None)
    hiberboot = hive.open(r"ControlSet%03d\Control\Session Manager\Power" % current)
    power = hive.open(r"ControlSet%03d\Control\Power" % current)
    hb = hiberboot.get("HiberbootEnabled") if hiberboot is not None else None
    hibernate = power.get("HibernateEnabled") if power is not None else None
    if isinstance(hb, int):
        data.fast_startup = bool(hb) and hibernate != 0   # no hibernation, no Fast Startup
    tz = hive.open(r"ControlSet%03d\Control\TimeZoneInformation" % current)
    if tz is not None:
        data.rtc_utc = tz.get("RealTimeIsUniversal") == 1     # DWORD or QWORD
        name = tz.get("TimeZoneKeyName")
        data.timezone = clean_name(name) if isinstance(name, str) else None
    for adapter in (keys.subkeys() if keys is not None else []):
        if not _HEX12.match(adapter.name):
            continue
        amac = to_mac(adapter.name)
        data.adapters.append(amac)
        found: dict[str, WinDevice] = {}

        def dev(hex12):
            d = found.get(hex12.lower())
            if d is None:
                d = found[hex12.lower()] = WinDevice(amac, to_mac(hex12), _name_from_devices(devices_key, hex12))
            return d

        for v in adapter.values():  # classic link keys; skips MasterIRK, CentralIRK, ...
            if _HEX12.match(v.name) and v.type == REG_BINARY and len(v.raw) == 16:
                d = dev(v.name)
                d.link_key = v.raw.hex().upper()
                d.paired_at = adapter.last_written   # values have no time of their own
        for sk in adapter.subkeys():  # Bluetooth LE
            if not _HEX12.match(sk.name):
                continue
            ltk = sk.get("LTK")
            if not isinstance(ltk, bytes) or len(ltk) != 16:
                continue
            ediv = sk.get("EDIV") or 0
            rand = sk.get("ERand") or 0
            irk = sk.get("IRK")
            d = dev(sk.name)
            if sk.last_written and (d.paired_at is None or sk.last_written > d.paired_at):
                d.paired_at = sk.last_written
            if not d.name:
                d.name = _name_from_bthle(bthle_key, sk.name)
            auth = 2 if (ediv == 0 and rand == 0) else 0
            authreq = sk.get("AuthReq")
            if isinstance(authreq, int) and authreq & 0x04:  # MITM protection
                auth += 1
            d.le = LEKeys(
                ltk=ltk.hex().upper(),
                enc_size=sk.get("KeyLength") or 16,
                ediv=ediv,
                rand=rand,
                irk=irk.hex().upper() if isinstance(irk, bytes) and len(irk) == 16 and any(irk) else None,
                address_type="static" if sk.get("AddressType") == 1 else "public",
                authenticated=auth,
            )
        data.devices.extend(found.values())
    return data


# ---------------------------------------------------------------- finding Windows
def _find_ci(root: str, parts) -> str | None:
    """Find root/parts... matching each component case-insensitively."""
    cur = root
    for part in parts:
        try:
            entries = os.listdir(cur)
        except OSError:
            return None
        match = next((e for e in entries if e.lower() == part.lower()), None)
        if match is None:
            return None
        cur = os.path.join(cur, match)
    return cur if os.path.isfile(cur) else None


def _block_devices():
    out = subprocess.run(["lsblk", "-J", "-p", "-o", "NAME,FSTYPE,LABEL,MOUNTPOINT"],
                         capture_output=True, text=True, check=True).stdout
    stack = list(json.loads(out).get("blockdevices", []))
    while stack:
        d = stack.pop(0)
        stack[0:0] = d.get("children") or []
        if not d.get("fstype"):  # lsblk relies on udev; ask blkid directly when it has no answer
            r = subprocess.run(["blkid", "-o", "value", "-s", "TYPE", d["name"]], capture_output=True, text=True)
            d["fstype"] = r.stdout.strip() or None
        yield d


def _mount_ro(dev: str) -> str | None:
    mnt = tempfile.mkdtemp(prefix="dualpair-")
    for extra in ([], ["-t", "ntfs3"], ["-t", "ntfs-3g"]):
        r = subprocess.run(["mount", *extra, "-o", "ro,nosuid,nodev,noexec", dev, mnt], capture_output=True)
        if r.returncode == 0:
            return mnt
    os.rmdir(mnt)
    return None


def _umount(mnt: str):
    subprocess.run(["umount", mnt], capture_output=True)
    try:
        os.rmdir(mnt)
    except OSError:
        pass


def hibernated(windows_root: str) -> bool | None:
    """True if hiberfil.sys holds an image (Fast Startup or hibernation): the Windows partition
    must not be written to, and its registry may not have the latest changes."""
    p = _find_ci(windows_root, ("hiberfil.sys",))
    if p is None:
        return False
    try:
        with open(p, "rb") as f:
            return f.read(4).lower() == b"hibr"
    except OSError:
        return None


def _load(path: str, source: str) -> WindowsData:
    try:
        hive = Hive.from_file(path)
    except (HiveError, OSError) as e:
        raise DualPairError("hive_invalid", path=path, detail=str(e))
    return read_hive(hive, source)


def load_windows(explicit: str | None = None) -> WindowsData:
    """Locate the Windows SYSTEM hive and read the Bluetooth keys from it.

    explicit: a hive file, or the root folder of a mounted Windows partition.
    Otherwise every NTFS partition is checked, mounting it read-only if needed.
    """
    if explicit:
        if os.path.isfile(explicit):
            return _load(explicit, explicit)
        p = _find_ci(explicit, HIVE_RELPATH)
        if p is None:
            raise DualPairError("no_windows_at", path=explicit)
        data = _load(p, explicit)
        data.hibernated = hibernated(explicit)
        return data

    if os.geteuid() != 0:
        raise DualPairError("not_root")
    bitlocker = []
    for d in _block_devices():
        fstype = (d.get("fstype") or "").lower()
        if fstype == "bitlocker":
            bitlocker.append(d["name"])
            continue
        if fstype != "ntfs":
            continue
        mp, temp = d.get("mountpoint"), None
        if not mp:
            mp = temp = _mount_ro(d["name"])
            if not mp:
                continue
        try:
            p = _find_ci(mp, HIVE_RELPATH)
            if p:
                # copy first, so the partition can be unmounted right away
                with open(p, "rb") as src, \
                        tempfile.NamedTemporaryFile(prefix="dualpair-hive-", delete=False) as tmp:
                    shutil.copyfileobj(src, tmp)
                try:
                    data = _load(tmp.name, d["name"])
                    data.hibernated = hibernated(mp)
                    return data
                finally:
                    os.unlink(tmp.name)
        finally:
            if temp:
                _umount(temp)
    if bitlocker:
        raise DualPairError("bitlocker", devices=", ".join(bitlocker))
    raise DualPairError("no_windows")
