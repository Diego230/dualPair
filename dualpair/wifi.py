# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Saved Wi-Fi networks in NetworkManager (/etc/NetworkManager/system-connections/*.nmconnection).

Only personal networks are shared: open, WPA/WPA2-Personal (wpa-psk), WPA3-Personal (sae).
Networks whose password is kept in a user keyring (psk-flags) cannot be read, so are skipped.
"""
from __future__ import annotations

import configparser
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass

from .mailbox import WifiNetwork

NM_DIR = "/etc/NetworkManager/system-connections"
_BYTES_RE = re.compile(r"^(\d{1,3};)+\d{0,3}$")


@dataclass
class SavedNetwork:
    network: WifiNetwork
    path: str


def _unescape(v: str) -> str:
    """GKeyFile escapes: \\s \\n \\t \\r \\\\."""
    out, i = [], 0
    while i < len(v):
        c = v[i]
        if c == "\\" and i + 1 < len(v):
            out.append({"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}.get(v[i + 1], v[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _escape(v: str) -> str:
    v = v.replace("\\", "\\\\")
    if v.startswith(" "):
        v = "\\s" + v[1:]
    return v


def _config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser(interpolation=None, delimiters=("=",), strict=False,
                                    comment_prefixes=("#",), inline_comment_prefixes=None)
    cfg.optionxform = str
    return cfg


def _ssid(raw: str) -> str | None:
    if _BYTES_RE.match(raw):   # older files: the SSID as a list of byte values
        try:
            return bytes(int(b) for b in raw.split(";") if b).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    return _unescape(raw)


def parse(path: str) -> WifiNetwork | None:
    cfg = _config()
    try:
        with open(path, encoding="utf-8") as f:
            cfg.read_file(f)
    except (OSError, configparser.Error, UnicodeDecodeError):
        return None
    if cfg.get("connection", "type", fallback="") not in ("wifi", "802-11-wireless"):
        return None
    wifi = "wifi" if cfg.has_section("wifi") else "802-11-wireless"
    if cfg.get(wifi, "mode", fallback="infrastructure") != "infrastructure":
        return None
    ssid = _ssid(cfg.get(wifi, "ssid", fallback=""))
    if not ssid or len(ssid.encode("utf-8")) > 32:
        return None
    hidden = cfg.get(wifi, "hidden", fallback="false").lower() == "true"
    sec = "wifi-security" if cfg.has_section("wifi-security") else "802-11-wireless-security"
    if not cfg.has_section(sec):
        return WifiNetwork(ssid, "open", None, hidden)
    km = cfg.get(sec, "key-mgmt", fallback="")
    if km not in ("wpa-psk", "sae"):
        return None                       # WEP, enterprise, OWE: not shared
    psk = cfg.get(sec, "psk", fallback=None)
    if psk is None:
        return None                       # password kept in a keyring
    return WifiNetwork(ssid, km, _unescape(psk), hidden)


def networks(nm_dir: str = NM_DIR) -> list[SavedNetwork] | None:
    """Saved networks, or None if NetworkManager's folder is not there."""
    if not os.path.isdir(nm_dir):
        return None
    out = []
    for name in sorted(os.listdir(nm_dir)):
        path = os.path.join(nm_dir, name)
        if os.path.isfile(path) and not os.path.islink(path):
            n = parse(path)
            if n:
                out.append(SavedNetwork(n, path))
    return out


def _filename(nm_dir: str, ssid: str) -> str:
    base = re.sub(r"[^\w.-]+", "_", ssid).strip("._") or "wifi"
    path = os.path.join(nm_dir, base + ".nmconnection")
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(nm_dir, f"{base}-{n}.nmconnection")
    return path


def _write(path: str, text: str):
    tmp = path + ".dualpair-tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def new_connection(n: WifiNetwork) -> str:
    lines = ["[connection]", f"id={_escape(n.ssid)}", f"uuid={uuid.uuid4()}", "type=wifi", "",
             "[wifi]", "mode=infrastructure", f"ssid={_escape(n.ssid)}"]
    if n.hidden:
        lines.append("hidden=true")
    lines.append("")
    if n.security != "open":
        lines += ["[wifi-security]", f"key-mgmt={n.security}", f"psk={_escape(n.password)}", ""]
    lines += ["[ipv4]", "method=auto", "", "[ipv6]", "addr-gen-mode=default", "method=auto", ""]
    return "\n".join(lines)


def import_networks(nets: list[WifiNetwork], nm_dir: str, state_dir: str, reload: bool = True) -> list[dict]:
    """Add new networks; for one already saved with another password, update the password
    (the old file is backed up first). Returns what was done for each network."""
    saved = {s.network.ssid: s for s in (networks(nm_dir) or [])}
    os.makedirs(nm_dir, mode=0o700, exist_ok=True)
    results, backup_dir = [], None
    for n in nets:
        old = saved.get(n.ssid)
        if old and old.network.password == n.password and old.network.security == n.security:
            results.append({"ssid": n.ssid, "result": "same"})
            continue
        if old:
            if backup_dir is None:
                backup_dir = os.path.join(state_dir, "backups-wifi", time.strftime("%Y%m%d-%H%M%S"))
                os.makedirs(backup_dir, mode=0o700, exist_ok=True)
                os.chmod(state_dir, 0o700)
            shutil.copy2(old.path, os.path.join(backup_dir, os.path.basename(old.path)))
            cfg = _config()
            with open(old.path, encoding="utf-8") as f:
                cfg.read_file(f)
            sec = "wifi-security" if cfg.has_section("wifi-security") or not cfg.has_section("802-11-wireless-security") \
                else "802-11-wireless-security"
            if n.security == "open":
                cfg.remove_section(sec)
            else:
                if not cfg.has_section(sec):
                    cfg.add_section(sec)
                cfg[sec]["key-mgmt"] = n.security
                cfg[sec]["psk"] = _escape(n.password)
                cfg.remove_option(sec, "psk-flags")
            import io
            buf = io.StringIO()
            cfg.write(buf, space_around_delimiters=False)
            _write(old.path, buf.getvalue())
            results.append({"ssid": n.ssid, "result": "updated"})
        else:
            _write(_filename(nm_dir, n.ssid), new_connection(n))
            results.append({"ssid": n.ssid, "result": "added"})
    if reload and any(r["result"] != "same" for r in results):
        try:
            subprocess.run(["nmcli", "connection", "reload"], capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return results


def compare(linux: list[WifiNetwork], windows_status: dict | None) -> dict:
    """Compare with the networks listed in status-windows.json (fingerprints only)."""
    win = {}
    if windows_status:
        for n in ((windows_status.get("wifi") or {}).get("networks") or []):
            if isinstance(n, dict) and isinstance(n.get("ssid"), str):
                win[n["ssid"]] = n
    out = []
    for n in linux:
        w = win.get(n.ssid)
        state = "unknown" if windows_status is None or "wifi" not in windows_status else \
            ("only_linux" if w is None else ("same" if w.get("fingerprint") == n.fingerprint() else "different"))
        out.append({"ssid": n.ssid, "security": n.security, "hidden": n.hidden, "state": state})
    names = {n.ssid for n in linux}
    only_windows = [{"ssid": s, "security": w.get("security")} for s, w in sorted(win.items()) if s not in names]
    return {"networks": out, "only_windows": only_windows}
