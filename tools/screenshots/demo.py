#!/usr/bin/python3.12
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Demo data for the README screenshots: invented devices, keys and networks, never real ones.

  demo.py build DIR     build a fake Windows hive, BlueZ folder, NetworkManager folder and ESP folder in DIR
  demo.py helper DIR …  act as the GUI helper on that data (used through DUALPAIR_HELPER)

Needs python3-hivex for `build`.
"""
import json
import os
import sys
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ADAPTER = "c41375c0e2e6"
MOUSE, KEYBOARD, HEADPHONES, SPEAKER = "fcc2073c8ad2", "e91dfe2ac3c8", "a4bfc6d0e5ff", "001b66b69ecf"

EFIBOOTMGR = """BootCurrent: 0001
BootOrder: 0000,0001,0002
Boot0000* Windows Boot Manager\tHD(1,GPT,ab,0x800,0x32000)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)WINDOWS
Boot0001* ubuntu\tHD(1,GPT,ab,0x800,0x32000)/File(\\EFI\\ubuntu\\shimx64.efi)
Boot0002  UEFI: PXE IPv4\tPciRoot(0x0)/Pci(0x1f,0x6)/MAC(001122334455,0)
"""

NM = {
    "Home.nmconnection": ("Home", "wpa-psk", "correct horse battery"),
    "Office.nmconnection": ("Office", "sae", "staple-42-office"),
}


def paths(d):
    return {"win": os.path.join(d, "Windows"), "bt": os.path.join(d, "bluetooth"), "nm": os.path.join(d, "nm"),
            "mb": os.path.join(d, "EFI", "DualPair"), "state": os.path.join(d, "state")}


def build_hive(win_root):
    import hivex
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from make_fixtures import FIX, binary, child, dword, path, qword, setvals, b

    cfg = os.path.join(win_root, "Windows", "System32", "config")
    os.makedirs(cfg, exist_ok=True)
    h = hivex.Hivex(os.path.join(FIX, "minimal.hive"), write=True)
    setvals(h, path(h, "Select"), {"Current": dword(1), "Default": dword(1)})
    keys = path(h, r"ControlSet001\Services\BTHPORT\Parameters\Keys\%s" % ADAPTER)
    setvals(h, keys, {HEADPHONES: binary(b("5a9b0b2c3d4e5f60718293a4b5c6d7e8")),
                      SPEAKER: binary(b("ffeeddccbbaa99887766554433221100"))})
    for dev, ltk, irk, ediv, rand, size in (
            (MOUSE, "3F8A1C5E9B2D7046E1A3C5F7092B4D6E", "7E21B9D4A6038F5C1D9E2B7A4C6F8E03", 38922, 12345678901234567890, 0),
            (KEYBOARD, "00112233445566778899AABBCCDDEEFF", "A1A2A3A4A5A6A7A8A9AAABACADAEAFB0", 0, 0, 16)):
        setvals(h, child(h, keys, dev), {"LTK": binary(b(ltk)), "KeyLength": dword(size), "ERand": qword(rand),
                                         "EDIV": dword(ediv), "IRK": binary(b(irk)),
                                         "Address": qword(int(dev, 16)), "AddressType": dword(1)})
    for dev, name in ((MOUSE, "MX Master 3S"), (KEYBOARD, "MX Keys")):
        inst = path(h, r"ControlSet001\Enum\BTHLE\Dev_%s\7&2b4a1c3&0&%s" % (dev, dev))
        setvals(h, inst, {"FriendlyName": {"t": 1, "value": (name + "\x00").encode("utf-16-le")}})
    devs = path(h, r"ControlSet001\Services\BTHPORT\Parameters\Devices")
    setvals(h, child(h, devs, HEADPHONES), {"Name": binary(b"WH-1000XM4\x00")})
    setvals(h, child(h, devs, SPEAKER), {"Name": binary(b"JBL Go 3\x00")})
    setvals(h, path(h, r"ControlSet001\Control\TimeZoneInformation"), {
        "TimeZoneKeyName": {"t": 1, "value": "W. Europe Standard Time\x00".encode("utf-16-le")},
        "Bias": dword(0xFFFFFFC4)})
    setvals(h, path(h, r"ControlSet001\Control\Session Manager\Power"), {"HiberbootEnabled": dword(1)})
    setvals(h, path(h, r"ControlSet001\Control\Power"), {"HibernateEnabled": dword(1)})
    h.commit(os.path.join(cfg, "SYSTEM"))


def build(d):
    from dualpair import mailbox
    p = paths(d)
    for k in ("bt", "nm", "mb", "state"):
        os.makedirs(p[k], exist_ok=True)
    os.makedirs(os.path.join(p["bt"], ":".join(ADAPTER[i:i + 2] for i in range(0, 12, 2)).upper()), exist_ok=True)
    build_hive(p["win"])
    for fname, (ssid, sec, psk) in NM.items():
        with open(os.path.join(p["nm"], fname), "w", encoding="utf-8") as f:
            f.write(f"[connection]\nid={ssid}\ntype=wifi\n\n[wifi]\nmode=infrastructure\nssid={ssid}\n\n"
                    f"[wifi-security]\nkey-mgmt={sec}\npsk={psk}\n\n[ipv4]\nmethod=auto\n")
    # mouse and keyboard already shared; the headphones were paired again on Linux, with a different key
    helper(d, ["--json", "sync", MOUSE_MAC, KEYBOARD_MAC])
    hp = os.path.join(p["bt"], "C4:13:75:C0:E2:E6", "A4:BF:C6:D0:E5:FF")
    os.makedirs(hp, exist_ok=True)
    with open(os.path.join(hp, "info"), "w") as f:
        f.write("[General]\nName=WH-1000XM4\nClass=0x240404\nTrusted=true\nBlocked=false\n\n"
                "[LinkKey]\nKey=0F1E2D3C4B5A69788796A5B4C3D2E1F0\nType=4\nPINLength=0\n")
    status = {
        "dualpair": 1, "system": "windows", "version": "0.4.1", "written": mailbox.iso(mailbox.utcnow()),
        "clock": {"rtc_utc": False, "timezone": "W. Europe Standard Time"},
        "bluetooth": {"available": True, "devices": []},
        "wifi": {"available": True, "networks": [
            {"ssid": s, "security": sec, "hidden": False, "fingerprint": mailbox.wifi_fingerprint(s, pw)}
            for s, sec, pw in (("Home", "wpa-psk", "correct horse battery"), ("Library", "wpa-psk", "x"),
                               ("Train Wi-Fi", "open", None))]},
        "power": {"fast_startup": True, "hibernated": False},
        "boot": {"first_loader": "\\EFI\\Microsoft\\Boot\\bootmgfw.efi", "fixed_at": None},
    }
    with open(os.path.join(p["mb"], "status-windows.json"), "w", encoding="utf-8") as f:
        json.dump(status, f)


MOUSE_MAC = "FC:C2:07:3C:8A:D2"
KEYBOARD_MAC = "E9:1D:FE:2A:C3:C8"


def helper(d, argv):
    from dualpair import cli
    p = paths(d)
    base = ["--win", p["win"], "--bluez-dir", p["bt"], "--state-dir", p["state"], "--mailbox-dir", p["mb"],
            "--nm-dir", p["nm"]]
    efi = os.path.join(d, "efibootmgr.txt")
    if not os.path.exists(efi):
        with open(efi, "w") as f:
            f.write(EFIBOOTMGR)
    os.environ["DUALPAIR_TEST_EFIBOOTMGR"] = efi
    with mock.patch("dualpair.clock.linux_rtc_local", return_value=False), \
            mock.patch("dualpair.clock.linux_timezone", return_value="Europe/Rome"):
        return cli.main(argv[:1] + base + argv[1:] if argv and argv[0] == "--json" else base + argv)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "build":
        build(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "helper":
        sys.exit(helper(sys.argv[2], sys.argv[3:]))
    else:
        sys.exit(__doc__)
