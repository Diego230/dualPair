#!/usr/bin/env python3
"""Cross-check the protocol between the Python (Linux) and C# (Windows) implementations.

  cross_check.py make DIR    write DIR/EFI/DualPair/to-windows/<id>.json the way DualPair for Linux does
                              (send-to-windows), for devices the C# tests have paired in their test registry
  cross_check.py check DIR   validate what the C# side exported to DIR (a to-linux folder)
Only the standard library is needed, so it also runs on the Windows CI machine.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dualpair import mailbox  # noqa: E402
from dualpair.windows import LEKeys, WinDevice  # noqa: E402

AD = "C4:13:75:C0:E2:E6"


def make(folder):
    devices = [
        WinDevice(AD, "A4:BF:C6:D0:E5:FF", "WH-1000XM4", link_key="CAFEBABECAFEBABECAFEBABECAFEBABE"),
        WinDevice(AD, "FC:C2:07:3C:8A:D2", "TK-MS317 5.0",
                  le=LEKeys("0123456789ABCDEF0123456789ABCDEF", 16, 4660, 18446744073709551615,
                            "FEDCBA9876543210FEDCBA9876543210", "static", 0)),
    ]
    mid = mailbox.send(folder, "windows", "keys", {"devices": [mailbox.device_to_json(d) for d in devices]})
    print("wrote", mid)


def check(to_linux_dir):
    folder = os.path.dirname(to_linux_dir)
    msgs = mailbox.list_messages(folder, "linux")
    assert len(msgs) == 1, f"expected 1 valid export, found {len(msgs)}: {os.listdir(to_linux_dir)}"
    devs = {d.address: d for d in msgs[0]["_devices"]}
    assert devs["A4:BF:C6:D0:E5:FF"].link_key == "CAFEBABECAFEBABECAFEBABECAFEBABE", devs
    le = devs["FC:C2:07:3C:8A:D2"].le
    assert (le.ltk, le.ediv, le.rand) == ("0123456789ABCDEF0123456789ABCDEF", 4660, 18446744073709551615), le
    st = mailbox.read_status(folder, "windows")
    assert st and st["system"] == "windows", st
    fp = {d["address"]: d["fingerprint"] for d in st["bluetooth"]["devices"]}
    assert fp["A4:BF:C6:D0:E5:FF"] == mailbox.fingerprint("CAFEBABECAFEBABECAFEBABECAFEBABE", None, None, None), fp
    print("cross-check ok: Windows export and status accepted by the Linux side")


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    make(os.path.join(path, "EFI", "DualPair")) if cmd == "make" else check(path)
