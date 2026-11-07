"""BlueZ pairing storage: /var/lib/bluetooth/<adapter>/<device>/info (GKeyFile/INI)."""
from __future__ import annotations

import configparser
import io
import os
import re
from dataclasses import dataclass

BLUEZ_DIR = "/var/lib/bluetooth"
MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def new_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser(interpolation=None, delimiters=("=",), strict=False)
    cfg.optionxform = str  # keep key case (Key, EDiv, ...)
    return cfg


def load_info(path: str) -> configparser.ConfigParser:
    cfg = new_config()
    with open(path, encoding="utf-8", errors="replace") as f:
        cfg.read_file(f)
    return cfg


def dump_info(cfg: configparser.ConfigParser) -> str:
    buf = io.StringIO()
    cfg.write(buf, space_around_delimiters=False)
    return buf.getvalue().rstrip("\n") + "\n"


def write_bytes(data: bytes, path: str):
    """Atomic write, readable by root only. Refuses to follow symlinks."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    os.chmod(os.path.dirname(path), 0o700)
    tmp = path + ".dualpair-tmp"
    if os.path.lexists(tmp):
        os.remove(tmp)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def write_info(cfg: configparser.ConfigParser, path: str):
    write_bytes(dump_info(cfg).encode("utf-8"), path)


@dataclass
class LinuxDevice:
    adapter: str
    address: str
    path: str
    cfg: configparser.ConfigParser

    @property
    def name(self) -> str | None:
        return self.cfg.get("General", "Alias", fallback=None) or self.cfg.get("General", "Name", fallback=None)

    @property
    def link_key(self) -> str | None:
        k = self.cfg.get("LinkKey", "Key", fallback=None)
        return k.upper() if k else None

    @property
    def ltk(self) -> tuple[str, int, int] | None:
        if not self.cfg.has_section("LongTermKey"):
            return None
        s = self.cfg["LongTermKey"]
        try:
            return s.get("Key", "").upper(), int(s.get("EDiv", "0")), int(s.get("Rand", "0"))
        except ValueError:
            return s.get("Key", "").upper(), -1, -1

    @property
    def paired(self) -> bool:
        return bool(self.link_key or self.ltk)


def adapters(root: str = BLUEZ_DIR) -> list[str]:
    try:
        return sorted(e for e in os.listdir(root) if MAC_RE.match(e) and os.path.isdir(os.path.join(root, e)))
    except FileNotFoundError:
        return []


def devices(adapter: str, root: str = BLUEZ_DIR) -> dict[str, LinuxDevice]:
    out = {}
    base = os.path.join(root, adapter)
    for e in sorted(os.listdir(base)):
        info = os.path.join(base, e, "info")
        if MAC_RE.match(e) and os.path.isfile(info):
            try:
                out[e] = LinuxDevice(adapter, e, info, load_info(info))
            except (configparser.Error, OSError):
                continue
    return out
