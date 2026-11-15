# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Identity resolving keys: AES / ah() against the published test vectors, and the byte-order checks."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from dualpair import bluez, cli, radio, rpa, sync
from dualpair.windows import load_windows

from tests.test_sync import AD, FIX, MOUSE, MOUSE_INFO

WIN_IRK = "7E21B9D4A6038F5C1D9E2B7A4C6F8E03"     # the mouse's IRK in the fixture hive
REV_IRK = rpa.reverse_hex(WIN_IRK)
OTHER = "D1:D2:D3:D4:D5:D6"


def make_rpa(irk_bluez_hex: str, prand_hex: str = "5A1B2C") -> str:
    prand = bytes.fromhex(prand_hex)
    octets = prand + rpa.ah(bytes.fromhex(irk_bluez_hex)[::-1], prand)
    return ":".join(f"{b:02X}" for b in octets)


class CryptoTest(unittest.TestCase):
    def test_aes_fips197(self):
        self.assertEqual(rpa.aes128_encrypt(bytes(range(16)), bytes.fromhex("00112233445566778899aabbccddeeff")).hex(),
                         "69c4e0d86a7b0430d8cdb78070b4c55a")

    def test_ah_core_spec_sample(self):   # Core spec Vol 3 Part H, D.7
        self.assertEqual(rpa.ah(bytes.fromhex("ec0234a357c8ad05341010a60a397d9b"), bytes.fromhex("708194")).hex(),
                         "0dfbaa")
        bluez_order = bytes.fromhex("ec0234a357c8ad05341010a60a397d9b")[::-1].hex()
        self.assertTrue(rpa.resolves(bluez_order, "70:81:94:0D:FB:AA"))
        self.assertFalse(rpa.resolves(bluez_order, "70:81:94:0D:FB:AB"))

    def test_is_rpa(self):
        self.assertTrue(rpa.is_rpa("70:81:94:0D:FB:AA"))
        self.assertFalse(rpa.is_rpa("F0:81:94:0D:FB:AA"))    # static random
        self.assertFalse(rpa.is_rpa("30:81:94:0D:FB:AA"))    # non-resolvable
        self.assertFalse(rpa.is_rpa("nonsense"))

    def test_order_for(self):
        self.assertEqual(rpa.order_for(WIN_IRK, [make_rpa(WIN_IRK)]), rpa.STORED)
        self.assertEqual(rpa.order_for(WIN_IRK, ["7A:00:00:00:00:00", make_rpa(REV_IRK)]), rpa.REVERSED)
        self.assertIsNone(rpa.order_for(WIN_IRK, [make_rpa("00" * 16)]))


class OrderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bt = os.path.join(self.tmp, "bt")
        self.state = os.path.join(self.tmp, "state")
        d = os.path.join(self.bt, AD, MOUSE)
        os.makedirs(d)
        open(os.path.join(d, "info"), "w").write(MOUSE_INFO)
        self.radio = os.path.join(self.tmp, "radio")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def scan(self):
        return sync.scan(load_windows(os.path.join(FIX, "SYSTEM")), self.bt, self.state)

    def mouse(self, s=None):
        return next(p for p in (s or self.scan()).plans if p.address == MOUSE)

    def info_irk(self):
        return bluez.load_info(os.path.join(self.bt, AD, MOUSE, "info"))["IdentityResolvingKey"]["Key"]

    def add_linux_pairing(self, addr, irk):
        d = os.path.join(self.bt, AD, addr)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "info"), "w").write(
            f"[General]\nName=Mouse\n[LongTermKey]\nKey={'B' * 32}\nEDiv=0\nRand=0\n[IdentityResolvingKey]\nKey={irk}\n")

    def verify(self, lines):
        with open(self.radio, "w") as f:
            f.write("\n".join(lines) + "\n")
        out = io.StringIO()
        with mock.patch.dict(os.environ, {radio.TEST_HOOK: self.radio}), redirect_stdout(out):
            self.assertEqual(cli.main(["--json", "--win", os.path.join(FIX, "SYSTEM"), "--bluez-dir", self.bt,
                                       "--state-dir", self.state, "verify-irk", "--seconds", "5"], read_only=True), 0)
        return {d["address"]: d["result"] for d in json.loads(out.getvalue())["irk_check"]["devices"]}

    def test_unverified_by_default(self):
        p = self.mouse()
        self.assertEqual((p.irk, p.irk_check, p.irk_reversed), (WIN_IRK, sync.IRK_UNVERIFIED, False))

    def test_linux_pairing_under_other_address_gives_order(self):
        self.add_linux_pairing(OTHER, REV_IRK)       # same device, paired by Linux itself
        p = self.mouse()
        self.assertEqual((p.irk, p.irk_check, p.irk_reversed), (REV_IRK, sync.IRK_LINUX, True))
        sync.apply(self.scan(), [MOUSE], self.state, restart=False)
        self.assertEqual(self.info_irk(), REV_IRK)

    def test_keys_written_by_dualpair_prove_nothing(self):
        sync.apply(self.scan(), [MOUSE], self.state, restart=False)   # writes the stored order, unverified
        self.assertEqual(self.info_irk(), WIN_IRK)
        p = self.mouse()
        self.assertEqual((p.irk_check, p.status), (sync.IRK_UNVERIFIED, sync.IN_SYNC))

    def test_radio_check_reversed_then_sync_fixes_it(self):
        sync.apply(self.scan(), [MOUSE], self.state, restart=False)   # wrong order written
        res = self.verify([f"rpa {make_rpa(REV_IRK)}", "rpa 7B:11:22:33:44:55"])
        self.assertEqual(res[MOUSE], "reversed")
        p = self.mouse()
        self.assertEqual((p.irk, p.irk_check, p.status), (REV_IRK, sync.IRK_RADIO, sync.NEEDS_SYNC))
        self.assertIsNone(p.newer)    # not "paired last on Linux": the fix comes from Windows
        sync.apply(self.scan(), [MOUSE], self.state, restart=False)
        self.assertEqual(self.info_irk(), REV_IRK)
        self.assertEqual(self.mouse().status, sync.IN_SYNC)

    def test_radio_check_stored(self):
        self.assertEqual(self.verify([f"rpa {make_rpa(WIN_IRK)}"])[MOUSE], "stored")
        self.assertEqual(self.mouse().irk_check, sync.IRK_RADIO)

    def test_heard_under_own_address(self):
        self.assertEqual(self.verify([f"seen {MOUSE}"])[MOUSE], "works")
        p = self.mouse()
        self.assertEqual((p.irk, p.irk_check), (WIN_IRK, sync.IRK_RADIO))

    def test_not_heard(self):
        self.assertEqual(self.verify(["rpa 7B:11:22:33:44:55"])[MOUSE], "not_heard")
        self.assertEqual(self.mouse().irk_check, sync.IRK_UNVERIFIED)

    def test_check_forgotten_when_windows_key_changes(self):
        sync.save_irk_check(self.state, AD, MOUSE, "00" * 16, rpa.REVERSED)   # result for an older key
        self.assertEqual(self.mouse().irk_check, sync.IRK_UNVERIFIED)

    def test_send_to_windows_uses_windows_order(self):
        self.add_linux_pairing(OTHER, REV_IRK)
        sync.apply(self.scan(), [MOUSE], self.state, restart=False)
        mb = os.path.join(self.tmp, "esp")
        os.makedirs(mb)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(["--json", "--win", os.path.join(FIX, "SYSTEM"), "--bluez-dir", self.bt,
                                       "--state-dir", self.state, "--mailbox-dir", mb, "send-to-windows", MOUSE]), 0)
        box = os.path.join(mb, "to-windows")
        dev = json.load(open(os.path.join(box, os.listdir(box)[0])))["payload"]["devices"][0]
        self.assertEqual(dev["le"]["irk"], WIN_IRK)     # Linux holds it reversed; Windows gets its own order

    def test_hook_ignored_under_pkexec(self):
        with open(self.radio, "w") as f:
            f.write("rpa 7B:11:22:33:44:55\n")
        with mock.patch.dict(os.environ, {radio.TEST_HOOK: self.radio, "PKEXEC_UID": "1000"}):
            self.assertIsNone(radio._test_data())


if __name__ == "__main__":
    unittest.main()
