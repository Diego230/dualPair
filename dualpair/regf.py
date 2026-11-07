"""Minimal read-only parser for Windows registry hive files (regf format).

Only what DualPair needs: walk keys by path, list subkeys and values, read value
data. No writing, no transaction-log replay. Pure Python, no dependencies.

Format reference: https://github.com/msuhanov/regf/blob/master/Windows%20registry%20file%20format%20specification.md
"""
from __future__ import annotations

import struct

REG_NONE = 0
REG_SZ = 1
REG_EXPAND_SZ = 2
REG_BINARY = 3
REG_DWORD = 4
REG_DWORD_BIG_ENDIAN = 5
REG_MULTI_SZ = 7
REG_QWORD = 11

_BASE_BLOCK_SIZE = 4096
_KEY_COMP_NAME = 0x0020
_VALUE_COMP_NAME = 0x0001
_BIG_DATA_SEGMENT = 16344
_MAX_DEPTH = 64


class HiveError(Exception):
    """The file is not a valid hive or is corrupted."""


def _decode_name(raw: bytes, compressed: bool) -> str:
    if compressed:
        return raw.decode("latin-1")
    return raw.decode("utf-16-le", errors="replace")


class Hive:
    def __init__(self, data: bytes):
        if len(data) < _BASE_BLOCK_SIZE or data[:4] != b"regf":
            raise HiveError("not a registry hive (missing 'regf' signature)")
        self.data = data
        self.primary_seq, self.secondary_seq = struct.unpack_from("<II", data, 4)
        self.major, self.minor = struct.unpack_from("<II", data, 20)
        (root_off,) = struct.unpack_from("<I", data, 36)
        self.root = Key(self, root_off)
        if self.root.sig != b"nk":
            raise HiveError("root cell is not a key node")

    @classmethod
    def from_file(cls, path) -> "Hive":
        with open(path, "rb") as f:
            return cls(f.read())

    @property
    def dirty(self) -> bool:
        """True if Windows did not finish writing the hive (pending transaction logs).

        Recent changes may then exist only in SYSTEM.LOG1/LOG2 and not in this file.
        """
        return self.primary_seq != self.secondary_seq

    # -- cells -------------------------------------------------------------
    def cell(self, offset: int) -> bytes:
        """Return the payload of the cell at the given hive-bins offset."""
        pos = _BASE_BLOCK_SIZE + offset
        if offset == 0xFFFFFFFF or pos + 4 > len(self.data):
            raise HiveError(f"cell offset out of range: {offset:#x}")
        (size,) = struct.unpack_from("<i", self.data, pos)
        size = abs(size)
        if size < 4 or pos + size > len(self.data):
            raise HiveError(f"bad cell size at {offset:#x}")
        return self.data[pos + 4 : pos + size]

    def open(self, path: str) -> "Key | None":
        return self.root.subkey_path(path)


class Key:
    def __init__(self, hive: Hive, offset: int):
        self.hive = hive
        self.offset = offset
        c = hive.cell(offset)
        if len(c) < 76:
            raise HiveError(f"key node too short at {offset:#x}")
        self.sig = c[:2]
        if self.sig != b"nk":
            raise HiveError(f"expected key node at {offset:#x}, found {self.sig!r}")
        (self.flags,) = struct.unpack_from("<H", c, 2)
        (self._n_subkeys,) = struct.unpack_from("<I", c, 20)
        (self._subkeys_off,) = struct.unpack_from("<I", c, 28)
        (self._n_values,) = struct.unpack_from("<I", c, 36)
        (self._values_off,) = struct.unpack_from("<I", c, 40)
        (name_len,) = struct.unpack_from("<H", c, 72)
        self.name = _decode_name(c[76 : 76 + name_len], bool(self.flags & _KEY_COMP_NAME))

    def __repr__(self):
        return f"<Key {self.name!r}>"

    # -- subkeys -----------------------------------------------------------
    def subkeys(self) -> list["Key"]:
        if self._n_subkeys == 0 or self._subkeys_off == 0xFFFFFFFF:
            return []
        return [Key(self.hive, off) for off in self._list_offsets(self._subkeys_off, 0)]

    def _list_offsets(self, off: int, depth: int) -> list[int]:
        if depth > _MAX_DEPTH:
            raise HiveError("subkey list nesting too deep")
        c = self.hive.cell(off)
        sig = c[:2]
        (count,) = struct.unpack_from("<H", c, 2)
        if sig in (b"lf", b"lh"):
            return [struct.unpack_from("<I", c, 4 + 8 * i)[0] for i in range(count)]
        if sig == b"li":
            return [struct.unpack_from("<I", c, 4 + 4 * i)[0] for i in range(count)]
        if sig == b"ri":
            out: list[int] = []
            for i in range(count):
                (sub,) = struct.unpack_from("<I", c, 4 + 4 * i)
                out.extend(self._list_offsets(sub, depth + 1))
            return out
        raise HiveError(f"unknown subkey list type {sig!r}")

    def subkey(self, name: str) -> "Key | None":
        lname = name.lower()
        for k in self.subkeys():
            if k.name.lower() == lname:
                return k
        return None

    def subkey_path(self, path: str) -> "Key | None":
        key: Key | None = self
        for part in [p for p in path.replace("/", "\\").split("\\") if p]:
            key = key.subkey(part) if key else None
            if key is None:
                return None
        return key

    # -- values ------------------------------------------------------------
    def values(self) -> list["Value"]:
        if self._n_values == 0 or self._values_off == 0xFFFFFFFF:
            return []
        c = self.hive.cell(self._values_off)
        offs = struct.unpack_from(f"<{self._n_values}I", c, 0)
        return [Value(self.hive, o) for o in offs]

    def value(self, name: str) -> "Value | None":
        lname = name.lower()
        for v in self.values():
            if v.name.lower() == lname:
                return v
        return None

    def get(self, name: str, default=None):
        v = self.value(name)
        return v.parsed() if v is not None else default


class Value:
    def __init__(self, hive: Hive, offset: int):
        self.hive = hive
        c = hive.cell(offset)
        if c[:2] != b"vk":
            raise HiveError(f"expected value node at {offset:#x}")
        name_len, self._size, self._data_off, self.type, flags = struct.unpack_from("<HIIIH", c, 2)
        self.name = _decode_name(c[20 : 20 + name_len], bool(flags & _VALUE_COMP_NAME)) if name_len else ""

    def __repr__(self):
        return f"<Value {self.name!r} type={self.type}>"

    @property
    def raw(self) -> bytes:
        size = self._size
        if size & 0x80000000:  # data stored inline in the offset field
            size &= 0x7FFFFFFF
            return struct.pack("<I", self._data_off)[:size]
        if size == 0:
            return b""
        if size > _BIG_DATA_SEGMENT and (self.hive.major, self.hive.minor) >= (1, 4):
            c = self.hive.cell(self._data_off)
            if c[:2] == b"db":
                n, list_off = struct.unpack_from("<HI", c, 2)
                segs = struct.unpack_from(f"<{n}I", self.hive.cell(list_off), 0)
                data = b"".join(self.hive.cell(s)[:_BIG_DATA_SEGMENT] for s in segs)
                return data[:size]
        return self.hive.cell(self._data_off)[:size]

    def parsed(self):
        raw = self.raw
        t = self.type
        if t == REG_DWORD and len(raw) >= 4:
            return struct.unpack_from("<I", raw)[0]
        if t == REG_DWORD_BIG_ENDIAN and len(raw) >= 4:
            return struct.unpack_from(">I", raw)[0]
        if t == REG_QWORD and len(raw) >= 8:
            return struct.unpack_from("<Q", raw)[0]
        if t in (REG_SZ, REG_EXPAND_SZ):
            return raw.decode("utf-16-le", errors="replace").split("\x00", 1)[0]
        if t == REG_MULTI_SZ:
            return [s for s in raw.decode("utf-16-le", errors="replace").split("\x00") if s]
        return raw
