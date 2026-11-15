# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Bluetooth LE resolvable private addresses (RPA) and identity resolving keys (IRK).

A device that protects its privacy advertises under a random address that changes every few
minutes. The address carries a 24-bit random part (prand) and a 24-bit hash of it made with the
device's IRK, so whoever holds the IRK can recognise the device (Core spec, Vol 3 Part H, 2.2.2):

    address = prand (3 most significant octets, top bits 01) || hash
    hash    = ah(IRK, prand) = AES-128(IRK, 0^104 || prand) mod 2^24

Windows and BlueZ do not always agree on the byte order of the IRK, so DualPair checks both
orders against addresses the device really sends, instead of guessing.

BlueZ writes the IRK in its info file least significant octet first (the kernel's order); AES
wants the most significant octet first. Addresses here are strings, most significant octet first.
"""
from __future__ import annotations

import re

_ADDR = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
STORED, REVERSED = "stored", "reversed"   # the IRK as Windows stores it fits BlueZ, or reversed

# ------------------------------------------------------------------ AES-128, encryption of one block
_SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16")


def _xtime(b: int) -> int:
    b <<= 1
    return (b ^ 0x1B) & 0xFF if b & 0x100 else b


def _expand(key: bytes) -> list[bytes]:
    w = [key[i:i + 4] for i in range(0, 16, 4)]
    rcon = 1
    for i in range(4, 44):
        t = w[i - 1]
        if i % 4 == 0:
            t = bytes(_SBOX[b] for b in t[1:] + t[:1])
            t = bytes([t[0] ^ rcon]) + t[1:]
            rcon = _xtime(rcon)
        w.append(bytes(a ^ b for a, b in zip(w[i - 4], t)))
    return [b"".join(w[r * 4:r * 4 + 4]) for r in range(11)]


def aes128_encrypt(key: bytes, block: bytes) -> bytes:
    if len(key) != 16 or len(block) != 16:
        raise ValueError("AES-128 needs a 16-byte key and block")
    rk = _expand(key)
    s = [a ^ b for a, b in zip(block, rk[0])]
    for rnd in range(1, 11):
        s = [_SBOX[b] for b in s]
        s = [s[(i + 4 * (i % 4)) % 16] for i in range(16)]          # ShiftRows (column-major state)
        if rnd != 10:
            m = []
            for c in range(4):
                a = s[4 * c:4 * c + 4]
                x = a[0] ^ a[1] ^ a[2] ^ a[3]
                m += [a[i] ^ x ^ _xtime(a[i] ^ a[(i + 1) % 4]) for i in range(4)]
            s = m
        s = [a ^ b for a, b in zip(s, rk[rnd])]
    return bytes(s)


# ------------------------------------------------------------------ addresses
def is_rpa(address: str) -> bool:
    """A resolvable private address: random address whose two top bits are 01."""
    return bool(_ADDR.match(address or "")) and (int(address[:2], 16) >> 6) == 0b01


def ah(irk_msb: bytes, prand: bytes) -> bytes:
    """The spec's ah(): IRK and prand most significant octet first; returns the 3-octet hash."""
    return aes128_encrypt(irk_msb, bytes(13) + prand)[-3:]


def resolves(irk_bluez_hex: str, address: str) -> bool:
    """Does this IRK, written as in a BlueZ info file, generate this address?"""
    if not is_rpa(address):
        return False
    try:
        irk = bytes.fromhex(irk_bluez_hex)
    except ValueError:
        return False
    if len(irk) != 16:
        return False
    octets = bytes.fromhex(address.replace(":", ""))
    return ah(irk[::-1], octets[:3]) == octets[3:]


def reverse_hex(h: str) -> str:
    return bytes.fromhex(h)[::-1].hex().upper()


def order_for(windows_irk: str, addresses) -> str | None:
    """Which byte order of Windows' IRK resolves one of these addresses, if any."""
    rev = reverse_hex(windows_irk)
    for a in addresses:
        if resolves(windows_irk, a):
            return STORED
        if resolves(rev, a):
            return REVERSED
    return None
