# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Listen for Bluetooth LE advertisements through BlueZ (D-Bus), to check IRKs against real addresses."""
from __future__ import annotations

import os
import time

from . import rpa
from .errors import DualPairError

TEST_HOOK = "DUALPAIR_TEST_RADIO"   # tests: file with "rpa <addr>" / "seen <addr>" lines; ignored under pkexec


def _test_data():
    path = os.environ.get(TEST_HOOK)
    if not path or "PKEXEC_UID" in os.environ:
        return None
    rpas, seen = set(), set()
    with open(path) as f:
        for line in f:
            kind, _, addr = line.strip().partition(" ")
            (rpas if kind == "rpa" else seen).add(addr.upper())
    return rpas, seen


def listen(adapter: str, seconds: int) -> tuple[set[str], set[str]]:
    """Scan for LE devices on the adapter (MAC) for a while.

    Returns (resolvable private addresses heard, other addresses heard). An address in the second
    set is a device the kernel recognised (resolved with the IRK it has) or one that advertises
    under its own fixed address."""
    test = _test_data()
    if test is not None:
        return test
    try:
        from gi.repository import Gio, GLib
    except ImportError as e:
        raise DualPairError("bt_unavailable", detail=str(e)) from e
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except GLib.Error as e:
        raise DualPairError("bt_unavailable", detail=e.message) from e

    def call(path, iface, method, params=None, reply=None):
        return bus.call_sync("org.bluez", path, iface, method, params,
                             GLib.VariantType(reply) if reply else None, Gio.DBusCallFlags.NONE, 10000, None)

    def objects():
        return call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None,
                    "(a{oa{sa{sv}}})").unpack()[0]

    try:
        objs = objects()
    except GLib.Error as e:
        raise DualPairError("bt_unavailable", detail=e.message) from e
    path = next((p for p, ifs in objs.items() if "org.bluez.Adapter1" in ifs
                 and str(ifs["org.bluez.Adapter1"].get("Address", "")).upper() == adapter.upper()), None)
    if path is None:
        raise DualPairError("bt_unavailable", detail=adapter)
    if not objs[path]["org.bluez.Adapter1"].get("Powered"):
        raise DualPairError("bt_off")

    try:
        call(path, "org.bluez.Adapter1", "SetDiscoveryFilter", GLib.Variant("(a{sv})", ({
            "Transport": GLib.Variant("s", "le"), "DuplicateData": GLib.Variant("b", True)},)))
    except GLib.Error:
        pass                                   # older BlueZ: plain discovery is fine too
    started = True
    try:
        call(path, "org.bluez.Adapter1", "StartDiscovery")
    except GLib.Error as e:
        if "InProgress" not in (e.message or ""):   # someone else is scanning: just watch
            raise DualPairError("bt_unavailable", detail=e.message) from e
        started = False

    rpas, seen = set(), set()
    deadline = time.monotonic() + seconds
    try:
        while True:
            for ifs in objects().values():
                d = ifs.get("org.bluez.Device1")
                if not d or d.get("Adapter") != path or "RSSI" not in d:   # RSSI: heard during this scan
                    continue
                addr = str(d.get("Address", "")).upper()
                if d.get("AddressType") == "random" and rpa.is_rpa(addr):
                    rpas.add(addr)
                else:
                    seen.add(addr)
            if time.monotonic() >= deadline:
                break
            time.sleep(1)
    finally:
        if started:
            try:
                call(path, "org.bluez.Adapter1", "StopDiscovery")
            except GLib.Error:
                pass
    return rpas, seen
