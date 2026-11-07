"""Tests for the hive parser: a hivex-built hive plus a hand-built one with li/ri lists,
big data and UTF-16 names (layouts real Windows hives use but hivex does not write)."""
import os
import struct
import unittest

from dualpair.regf import Hive, HiveError, REG_BINARY, REG_SZ

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class Builder:
    """Tiny regf writer: just enough to lay out cells by hand."""

    def __init__(self):
        self.bins = bytearray()

    def cell(self, payload: bytes) -> int:
        size = (len(payload) + 4 + 7) & ~7
        off = len(self.bins)
        self.bins += struct.pack("<i", -size) + payload + b"\x00" * (size - 4 - len(payload))
        return off

    def nk(self, name, subkeys_off=0xFFFFFFFF, n_sub=0, values_off=0xFFFFFFFF, n_val=0, utf16=False):
        raw = name.encode("utf-16-le") if utf16 else name.encode("latin-1")
        flags = 0 if utf16 else 0x20
        p = bytearray(76)
        p[0:2] = b"nk"
        struct.pack_into("<H", p, 2, flags)
        struct.pack_into("<I", p, 20, n_sub)
        struct.pack_into("<I", p, 28, subkeys_off)
        struct.pack_into("<I", p, 36, n_val)
        struct.pack_into("<I", p, 40, values_off)
        struct.pack_into("<H", p, 72, len(raw))
        return self.cell(bytes(p) + raw)

    def vk(self, name, vtype, data: bytes, big=False):
        if len(data) <= 4:
            size = len(data) | 0x80000000
            off = struct.unpack("<I", data.ljust(4, b"\x00"))[0]
        elif big:
            segs = [self.cell(data[i:i + 16344]) for i in range(0, len(data), 16344)]
            lst = self.cell(struct.pack(f"<{len(segs)}I", *segs))
            off = self.cell(b"db" + struct.pack("<HI", len(segs), lst))
            size = len(data)
        else:
            off, size = self.cell(data), len(data)
        raw = name.encode("latin-1")
        return self.cell(b"vk" + struct.pack("<HIIIHH", len(raw), size, off, vtype, 1, 0) + raw)

    def build(self, root_off, minor=5):
        base = bytearray(4096)
        base[0:4] = b"regf"
        struct.pack_into("<IIQII", base, 4, 7, 7, 0, 1, minor)
        struct.pack_into("<II", base, 36, root_off, len(self.bins))
        return bytes(base) + bytes(self.bins)


class HandBuiltHive(unittest.TestCase):
    def setUp(self):
        b = Builder()
        leaves = [b.nk("Key%03d" % i) for i in range(6)]
        u16 = b.nk("Ünicode", utf16=True)
        big = b.vk("Big", REG_BINARY, bytes(range(256)) * 100, big=True)   # 25600 bytes -> db
        small = b.vk("Small", 4, struct.pack("<I", 42))                    # inline dword
        sz = b.vk("Text", REG_SZ, "ciao\x00".encode("utf-16-le"))
        vals = b.cell(struct.pack("<3I", big, small, sz))
        li = b.cell(b"li" + struct.pack("<H", 3) + struct.pack("<3I", *leaves[:3]))
        lh = b.cell(b"lh" + struct.pack("<H", 4) + b"".join(struct.pack("<II", o, 0) for o in leaves[3:] + [u16]))
        ri = b.cell(b"ri" + struct.pack("<H", 2) + struct.pack("<2I", li, lh))
        root = b.nk("ROOT", ri, 7, vals, 3)
        self.hive = Hive(b.build(root))

    def test_ri_li_lh(self):
        names = [k.name for k in self.hive.root.subkeys()]
        self.assertEqual(names, ["Key000", "Key001", "Key002", "Key003", "Key004", "Key005", "Ünicode"])
        self.assertIsNotNone(self.hive.open("key004"))  # case-insensitive

    def test_values(self):
        r = self.hive.root
        self.assertEqual(r.get("Small"), 42)
        self.assertEqual(r.get("text"), "ciao")
        self.assertEqual(r.get("Big"), bytes(range(256)) * 100)
        self.assertIsNone(r.get("missing"))

    def test_not_a_hive(self):
        with self.assertRaises(HiveError):
            Hive(b"\x00" * 8192)


class HivexHive(unittest.TestCase):
    def test_fixture(self):
        h = Hive.from_file(os.path.join(FIX, "SYSTEM"))
        self.assertFalse(h.dirty)
        self.assertEqual(h.open("Select").get("Current"), 1)
        mouse = h.open(r"ControlSet001\Services\BTHPORT\Parameters\Keys\c41375c0e2e6\fcc2073c8ad2")
        self.assertEqual(mouse.get("ERand"), 12345678901234567890)
        self.assertEqual(mouse.get("EDIV"), 38922)
        self.assertEqual(mouse.get("LTK").hex().upper(), "3F8A1C5E9B2D7046E1A3C5F7092B4D6E")

    def test_dirty(self):
        self.assertTrue(Hive.from_file(os.path.join(FIX, "SYSTEM.dirty")).dirty)


if __name__ == "__main__":
    unittest.main()
