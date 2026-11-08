# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Exchange with DualPair for Windows through the EFI System Partition (see docs/protocol.md).

Folder: <ESP>/EFI/DualPair/ with status-linux.json, status-windows.json, to-windows/, to-linux/.
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
import secrets
import subprocess
import tempfile
from dataclasses import dataclass

from . import __version__
from .errors import DualPairError
from .windows import LEKeys, WinDevice, WindowsData, clean_name

PROTOCOL = 1
ESP_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
FOLDER = ("EFI", "DualPair")
MAX_FILE = 64 * 1024
MAX_DEVICES = 64
MAX_LIFETIME = datetime.timedelta(days=7)

ID_RE = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")
MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")
HEX32_RE = re.compile(r"^[0-9A-F]{32}$")
UINT64_RE = re.compile(r"^[0-9]{1,20}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class InvalidMessage(ValueError):
    pass


SECURITIES = ("open", "wpa-psk", "sae")
HEX64_RE = re.compile(r"^[0-9A-Fa-f]{64}$")


@dataclass
class WifiNetwork:
    ssid: str
    security: str             # open, wpa-psk, sae
    password: str | None
    hidden: bool = False

    def fingerprint(self) -> str:
        return wifi_fingerprint(self.ssid, self.password)


def wifi_fingerprint(ssid: str, password: str | None) -> str:
    return hashlib.sha256(f"dualpair-fp-v1|wifi|{ssid}|{password or ''}".encode("utf-8")).hexdigest()[:8]


def check_wifi(n) -> WifiNetwork:
    if not isinstance(n, dict):
        raise InvalidMessage("bad network")
    ssid, sec, pw, hidden = n.get("ssid"), n.get("security"), n.get("password"), n.get("hidden", False)
    if not (isinstance(ssid, str) and 1 <= len(ssid.encode("utf-8")) <= 32 and not _CONTROL.search(ssid)):
        raise InvalidMessage("bad ssid")
    if sec not in SECURITIES:
        raise InvalidMessage("bad security")
    if sec == "open":
        if pw is not None:
            raise InvalidMessage("open network with password")
    elif not (isinstance(pw, str) and (8 <= len(pw) <= 63 and not _CONTROL.search(pw) or HEX64_RE.match(pw))):
        raise InvalidMessage("bad password")
    if not isinstance(hidden, bool):
        raise InvalidMessage("bad hidden")
    return WifiNetwork(ssid, sec, pw, hidden)


# ---------------------------------------------------------------- time, ids, fingerprints
def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def iso(dt: datetime.datetime | None) -> str | None:
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_iso(s) -> datetime.datetime:
    if not isinstance(s, str):
        raise InvalidMessage("bad time")
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        raise InvalidMessage("bad time")


def new_id(now: datetime.datetime | None = None) -> str:
    return (now or utcnow()).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def fingerprint(link_key: str | None, ltk: str | None, ediv: int | None, rand: int | None) -> str:
    parts = []
    if link_key:
        parts.append(link_key.upper())
    if ltk:
        parts += [ltk.upper(), str(ediv or 0), str(rand or 0)]
    return hashlib.sha256(("dualpair-fp-v1|" + "|".join(parts)).encode("ascii")).hexdigest()[:8]


# ---------------------------------------------------------------- locating the ESP
def _esp_partitions():
    out = subprocess.run(["lsblk", "-J", "-p", "-o", "NAME,PARTTYPE,MOUNTPOINT"],
                         capture_output=True, text=True, check=True).stdout
    stack = list(json.loads(out).get("blockdevices", []))
    while stack:
        d = stack.pop(0)
        stack[0:0] = d.get("children") or []
        if (d.get("parttype") or "").lower() == ESP_TYPE:
            yield d["name"], d.get("mountpoint")


@contextlib.contextmanager
def open_mailbox(override: str | None = None, create: bool = False, disabled: bool = False):
    """Yield the DualPair folder on the ESP (None if there is no ESP or no folder and create=False).

    An ESP that is not mounted is mounted for the duration, readable by root only.
    disabled: yield None without looking (tests with fake BlueZ folders never touch the real ESP)."""
    if (disabled or os.geteuid() != 0) and not override:   # only root can mount and write the ESP
        yield None
        return
    if override:
        if create:
            os.makedirs(override, mode=0o700, exist_ok=True)
        yield override if os.path.isdir(override) else None
        return
    candidates = []
    try:
        candidates = list(_esp_partitions())
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass
    # prefer an ESP that already has our folder; then one that is mounted (the one Linux booted from)
    temp_mounts = []
    try:
        chosen = None
        for dev, mnt in sorted(candidates, key=lambda c: c[1] is None):
            if not mnt:
                mnt = tempfile.mkdtemp(prefix="dualpair-esp-")
                r = subprocess.run(["mount", "-o", "umask=0077,nosuid,nodev,noexec", dev, mnt], capture_output=True)
                if r.returncode != 0:
                    os.rmdir(mnt)
                    continue
                temp_mounts.append(mnt)
            folder = _find_folder(mnt)
            if folder:
                chosen = folder
                break
            if chosen is None and create:
                chosen = os.path.join(mnt, *FOLDER)
        if chosen and create:
            try:
                os.makedirs(chosen, mode=0o700, exist_ok=True)
            except OSError:
                chosen = None
        yield chosen if chosen and os.path.isdir(chosen) else None
    finally:
        for m in temp_mounts:
            subprocess.run(["umount", m], capture_output=True)
            with contextlib.suppress(OSError):
                os.rmdir(m)


def _find_folder(root: str) -> str | None:
    cur = root
    for part in FOLDER:  # FAT is case-insensitive, Linux paths are not
        try:
            match = next((e for e in os.listdir(cur) if e.lower() == part.lower()), None)
        except OSError:
            return None
        if match is None:
            return None
        cur = os.path.join(cur, match)
    return cur if os.path.isdir(cur) else None


# ---------------------------------------------------------------- file helpers
def _read_json(path: str):
    if os.path.islink(path) or os.path.getsize(path) > MAX_FILE:
        raise InvalidMessage("too big or a link")
    with open(path, "rb") as f:
        data = json.loads(f.read().decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise InvalidMessage("not an object")
    return data


def _write_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------- status files
def read_status(folder: str | None, system: str) -> dict | None:
    if not folder:
        return None
    path = os.path.join(folder, f"status-{system}.json")
    try:
        data = _read_json(path)
    except (OSError, ValueError):
        return None
    if data.get("dualpair") != PROTOCOL or data.get("system") != system:
        return None
    return data


def write_status(folder: str, clock_rtc_utc: bool, timezone: str | None, devices: list[dict], bt_available: bool,
                 wifi: dict | None = None, boot: dict | None = None):
    data = {
        "dualpair": PROTOCOL, "system": "linux", "version": __version__, "written": iso(utcnow()),
        "clock": {"rtc_utc": clock_rtc_utc, "timezone": timezone},
        "bluetooth": {"available": bt_available, "devices": devices},
    }
    if wifi is not None:
        data["wifi"] = wifi
    if boot is not None:
        data["boot"] = boot
    _write_json(os.path.join(folder, "status-linux.json"), data)


def wifi_to_json(n: WifiNetwork) -> dict:
    return {"ssid": n.ssid, "security": n.security, "password": n.password, "hidden": n.hidden}


# ---------------------------------------------------------------- messages
def _check_le(le) -> LEKeys:
    if not isinstance(le, dict):
        raise InvalidMessage("bad le")
    ltk, irk, rand = le.get("ltk"), le.get("irk"), le.get("rand")
    enc, ediv, auth = le.get("enc_size"), le.get("ediv"), le.get("authenticated", 0)
    if not (isinstance(ltk, str) and HEX32_RE.match(ltk)):
        raise InvalidMessage("bad ltk")
    if irk is not None and not (isinstance(irk, str) and HEX32_RE.match(irk)):
        raise InvalidMessage("bad irk")
    if not (isinstance(rand, str) and UINT64_RE.match(rand) and int(rand) < 2 ** 64):
        raise InvalidMessage("bad rand")
    for v, lo, hi in ((enc, 7, 16), (ediv, 0, 65535), (auth, 0, 4)):
        if not (isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi):
            raise InvalidMessage("bad number")
    if le.get("address_type") not in ("public", "static"):
        raise InvalidMessage("bad address type")
    return LEKeys(ltk=ltk, enc_size=enc, ediv=ediv, rand=int(rand), irk=irk,
                  address_type=le["address_type"], authenticated=auth)


def parse_devices(payload) -> list[WinDevice]:
    devs = payload.get("devices") if isinstance(payload, dict) else None
    if not isinstance(devs, list) or not 0 < len(devs) <= MAX_DEVICES:
        raise InvalidMessage("bad device list")
    out = []
    for d in devs:
        if not isinstance(d, dict):
            raise InvalidMessage("bad device")
        adapter, address = d.get("adapter"), d.get("address")
        if not (isinstance(adapter, str) and MAC_RE.match(adapter) and isinstance(address, str) and MAC_RE.match(address)):
            raise InvalidMessage("bad address")
        lk = d.get("link_key")
        if lk is not None and not (isinstance(lk, str) and HEX32_RE.match(lk)):
            raise InvalidMessage("bad link key")
        le = _check_le(d["le"]) if d.get("le") is not None else None
        if lk is None and le is None:
            raise InvalidMessage("no keys")
        out.append(WinDevice(adapter, address, clean_name(d.get("name")), lk, le))
    return out


def validate(msg: dict, sender: str, filename: str, now: datetime.datetime | None = None) -> dict:
    now = now or utcnow()
    if msg.get("dualpair") != PROTOCOL:
        raise InvalidMessage("unknown protocol version")
    mid = msg.get("id")
    if not (isinstance(mid, str) and ID_RE.match(mid) and filename == mid + ".json"):
        raise InvalidMessage("bad id")
    if msg.get("from") != sender:
        raise InvalidMessage("wrong sender")
    created, expires = parse_iso(msg.get("created")), parse_iso(msg.get("expires"))
    if expires <= now or expires - created > MAX_LIFETIME or expires < created:
        raise InvalidMessage("expired")
    t = msg.get("type")
    if t == "keys":
        msg["_devices"] = parse_devices(msg.get("payload"))
    elif t == "set_clock":
        p = msg.get("payload")
        if not (isinstance(p, dict) and isinstance(p.get("windows_utc"), bool)):
            raise InvalidMessage("bad payload")
    elif t == "set_fast_startup":
        p = msg.get("payload")
        if not (isinstance(p, dict) and isinstance(p.get("enabled"), bool)):
            raise InvalidMessage("bad payload")
    elif t == "wifi":
        nets = (msg.get("payload") or {}).get("networks") if isinstance(msg.get("payload"), dict) else None
        if not isinstance(nets, list) or not 0 < len(nets) <= MAX_DEVICES:
            raise InvalidMessage("bad network list")
        msg["_networks"] = [check_wifi(n) for n in nets]
    else:
        raise InvalidMessage("unknown type")
    return msg


def list_messages(folder: str | None, to: str, delete_invalid: bool = False) -> list[dict]:
    """Valid messages addressed to `to` ('linux' or 'windows'), oldest first."""
    if not folder:
        return []
    box = os.path.join(folder, f"to-{to}")
    sender = "windows" if to == "linux" else "linux"
    out = []
    try:
        names = sorted(os.listdir(box))
    except OSError:
        return []
    for name in names:
        path = os.path.join(box, name)
        if not name.endswith(".json") or not os.path.isfile(path):
            continue
        try:
            out.append(validate(_read_json(path), sender, name))
        except (OSError, ValueError, KeyError):
            if delete_invalid:
                with contextlib.suppress(OSError):
                    os.remove(path)
    return out


def device_to_json(d: WinDevice) -> dict:
    le = None
    if d.le:
        le = {"ltk": d.le.ltk, "enc_size": d.le.enc_size, "ediv": d.le.ediv, "rand": str(d.le.rand),
              "irk": d.le.irk, "address_type": d.le.address_type, "authenticated": d.le.authenticated}
    return {"adapter": d.adapter, "address": d.address, "name": d.name, "link_key": d.link_key, "le": le}


def send(folder: str, to: str, mtype: str, payload: dict, replace_same_type: bool = True) -> str:
    """Write a message for the other system. Unhandled older messages of the same type are removed,
    so keys never pile up on the ESP."""
    box = os.path.join(folder, f"to-{to}")
    os.makedirs(box, mode=0o700, exist_ok=True)
    if replace_same_type:
        for m in list_messages(folder, to):
            if m["type"] == mtype:
                delete(folder, to, m["id"])
    now = utcnow()
    mid = new_id(now)
    msg = {"dualpair": PROTOCOL, "id": mid, "type": mtype, "from": "windows" if to == "linux" else "linux",
           "created": iso(now), "expires": iso(now + MAX_LIFETIME), "payload": payload}
    _write_json(os.path.join(box, mid + ".json"), msg)
    return mid


def delete(folder: str, to: str, mid: str):
    if not ID_RE.match(mid or ""):
        raise DualPairError("unknown_message", id=mid)
    with contextlib.suppress(FileNotFoundError):
        os.remove(os.path.join(folder, f"to-{to}", mid + ".json"))


# ---------------------------------------------------------------- Windows data from DualPair for Windows
def windows_from_mailbox(folder: str | None) -> WindowsData | None:
    """When Linux cannot read the Windows disk (BitLocker), use what DualPair for Windows exported:
    the newest 'keys' message and the clock setting from status-windows.json."""
    msgs = [m for m in list_messages(folder, "linux") if m["type"] == "keys"]
    status = read_status(folder, "windows")
    if not msgs and not status:
        return None
    data = WindowsData(source="DualPair for Windows", hive_dirty=False, control_set=0,
                       bt_present=bool(msgs))
    if status:
        clock = status.get("clock") or {}
        data.rtc_utc = clock.get("rtc_utc") is True
        tz = clock.get("timezone")
        data.timezone = clean_name(tz) if isinstance(tz, str) else None
    if msgs:
        m = msgs[-1]
        data.source = f"DualPair for Windows ({m['created']})"
        data.export_id = m["id"]
        data.devices = m["_devices"]
        data.adapters = sorted({d.adapter for d in data.devices})
    return data
