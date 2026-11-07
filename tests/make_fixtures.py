#!/usr/bin/python3.12
"""Build fake Windows SYSTEM hives for the tests, using libhivex (python3-hivex).

Run with the system Python that has the hivex binding:  python3.12 tests/make_fixtures.py
Output: tests/fixtures/SYSTEM (clean) and tests/fixtures/SYSTEM.dirty
"""
import os
import struct
import hivex

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")

ADAPTER = "c41375c0e2e6"
MOUSE = "fcc2073c8ad2"          # LE legacy pairing (the real TK-MS317 case)
KEYBOARD = "e91dfe2ac3c8"       # LE Secure Connections (EDiv=0, Rand=0)
HEADPHONES = "a4bfc6d0e5ff"     # classic, already paired on Linux with an old key
SPEAKER = "001b66b69ecf"        # classic, only paired on Windows

REG_BINARY, REG_DWORD, REG_QWORD = 3, 4, 11


def b(hexstr):
    return bytes.fromhex(hexstr)


def dword(n):
    return {"t": REG_DWORD, "value": struct.pack("<I", n)}


def qword(n):
    return {"t": REG_QWORD, "value": struct.pack("<Q", n)}


def binary(data):
    return {"t": REG_BINARY, "value": data}


def setvals(h, node, vals):
    h.node_set_values(node, [dict(key=k, **v) for k, v in vals.items()])


def child(h, parent, name):
    return h.node_get_child(parent, name) or h.node_add_child(parent, name)


def path(h, p):
    node = h.root()
    for part in p.split("\\"):
        node = child(h, node, part)
    return node


def build(out):
    h = hivex.Hivex(os.path.join(FIX, "minimal.hive"), write=True)
    setvals(h, path(h, "Select"), {"Current": dword(1), "Default": dword(1)})
    # a decoy control set that must be ignored
    setvals(h, path(h, r"ControlSet002\Services\BTHPORT\Parameters\Keys\deadbeef0001"),
            {"112233445566": binary(b("00" * 16))})

    keys = path(h, r"ControlSet001\Services\BTHPORT\Parameters\Keys\%s" % ADAPTER)
    setvals(h, keys, {
        "MasterIRK": binary(b("0102030405060708090a0b0c0d0e0f10")),
        HEADPHONES: binary(b("5a9b0b2c3d4e5f60718293a4b5c6d7e8")),
        SPEAKER: binary(b("ffeeddccbbaa99887766554433221100")),
    })
    mouse = child(h, keys, MOUSE)
    setvals(h, mouse, {
        "LTK": binary(b("3F8A1C5E9B2D7046E1A3C5F7092B4D6E")),
        "KeyLength": dword(0),
        "ERand": qword(12345678901234567890),
        "EDIV": dword(38922),
        "IRK": binary(b("7E21B9D4A6038F5C1D9E2B7A4C6F8E03")),
        "Address": qword(0xFCC2073C8AD2),
        "AddressType": dword(1),
    })
    kb = child(h, keys, KEYBOARD)
    setvals(h, kb, {
        "LTK": binary(b("00112233445566778899AABBCCDDEEFF")),
        "KeyLength": dword(16),
        "ERand": qword(0),
        "EDIV": dword(0),
        "IRK": binary(b("A1A2A3A4A5A6A7A8A9AAABACADAEAFB0")),
        "Address": qword(0xE91DFE2AC3C8),
        "AddressType": dword(1),
    })
    inst = path(h, r"ControlSet001\Enum\BTHLE\Dev_%s\7&2b4a1c3&0&%s" % (KEYBOARD, KEYBOARD))
    setvals(h, inst, {"FriendlyName": {"t": 1, "value": "MX Keys\x00".encode("utf-16-le")}})
    # many sibling keys so the subkey list is not trivial
    devs = path(h, r"ControlSet001\Services\BTHPORT\Parameters\Devices")
    for i in range(300):
        child(h, devs, "%012x" % (0x100000000000 + i))
    setvals(h, child(h, devs, HEADPHONES), {"Name": binary(b"WH-1000XM4\x00")})
    setvals(h, child(h, devs, SPEAKER), {"Name": binary("JBL Go 3 è\x00".encode())})
    h.commit(out)


def make_dirty(src, dst):
    data = bytearray(open(src, "rb").read())
    seq = struct.unpack_from("<I", data, 4)[0]
    struct.pack_into("<I", data, 8, seq - 1)  # secondary != primary
    open(dst, "wb").write(data)


if __name__ == "__main__":
    out = os.path.join(FIX, "SYSTEM")
    build(out)
    make_dirty(out, os.path.join(FIX, "SYSTEM.dirty"))
    print("written", out)
