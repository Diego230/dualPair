"""End-to-end tests of scan / sync / restore against a fake Windows hive and a fake /var/lib/bluetooth."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from dualpair import bluez, cli, sync
from dualpair.errors import DualPairError
from dualpair.windows import load_windows

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
AD = "C4:13:75:C0:E2:E6"
MOUSE, KB, PHONES, SPEAKER, OLD = ("FC:C2:07:3C:8A:D2", "E9:1D:FE:2A:C3:C8", "A4:BF:C6:D0:E5:FF",
                                   "00:1B:66:B6:9E:CF", "11:22:33:44:55:66")
EVIL = "0A:0B:0C:0D:0E:0F"

HEADPHONES_INFO = """[General]
Name=WH-1000XM4
Class=0x240404
SupportedTechnologies=BR/EDR;
Trusted=true
Blocked=false
Services=0000110b-0000-1000-8000-00805f9b34fb;

[LinkKey]
Key=00000000000000000000000000000000
Type=8
PINLength=0
"""
MOUSE_INFO = """[General]
Name=TK-MS317 5.0
AddressType=static
SupportedTechnologies=LE;
Trusted=true
Blocked=false

[LongTermKey]
Key=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
Authenticated=0
EncSize=16
EDiv=1
Rand=2
"""
# same layout as the file that works for the real mouse (the keys here are fake)
MOUSE_EXPECTED = """[General]
Name=TK-MS317 5.0
AddressType=static
SupportedTechnologies=LE;
Trusted=true
Blocked=false

[LongTermKey]
Key=3F8A1C5E9B2D7046E1A3C5F7092B4D6E
Authenticated=0
EncSize=16
EDiv=38922
Rand=12345678901234567890

[IdentityResolvingKey]
Key=7E21B9D4A6038F5C1D9E2B7A4C6F8E03
"""


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bt = os.path.join(self.tmp, "bt")
        self.state = os.path.join(self.tmp, "state")
        for addr, content in ((PHONES, HEADPHONES_INFO), (MOUSE, MOUSE_INFO),
                              (OLD, "[General]\nName=Old Phone\n[LinkKey]\nKey=11111111111111111111111111111111\n")):
            d = os.path.join(self.bt, AD, addr)
            os.makedirs(d)
            open(os.path.join(d, "info"), "w").write(content)
        os.makedirs(os.path.join(self.bt, AD, "cache"))
        open(os.path.join(self.bt, AD, "cache", MOUSE), "w").write("x")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def info(self, addr):
        return open(os.path.join(self.bt, AD, addr, "info")).read()

    def do_scan(self, hive="SYSTEM"):
        return sync.scan(load_windows(os.path.join(FIX, hive)), self.bt)

    def test_scan_statuses(self):
        st = {p.address: p.status for p in self.do_scan().plans}
        self.assertEqual(st, {MOUSE: sync.NEEDS_SYNC, PHONES: sync.NEEDS_SYNC, KB: sync.WINDOWS_ONLY,
                              SPEAKER: sync.WINDOWS_ONLY, EVIL: sync.WINDOWS_ONLY, OLD: sync.LINUX_ONLY})
        names = {p.address: p.name for p in self.do_scan().plans}
        self.assertEqual(names[KB], "MX Keys")       # from Enum\BTHLE FriendlyName
        self.assertEqual(names[SPEAKER], "JBL Go 3 è")

    def test_sync_all_then_in_sync(self):
        res = sync.apply(self.do_scan(), None, self.state, restart=False)
        self.assertEqual(len(res["applied"]), 5)
        self.assertEqual(self.info(MOUSE), MOUSE_EXPECTED)
        self.assertFalse(os.path.exists(os.path.join(self.bt, AD, "cache", MOUSE)))
        phones = bluez.load_info(os.path.join(self.bt, AD, PHONES, "info"))
        self.assertEqual(phones["LinkKey"]["Key"], "5A9B0B2C3D4E5F60718293A4B5C6D7E8")
        self.assertEqual(phones["LinkKey"]["Type"], "8")                 # kept from Linux
        self.assertEqual(phones["General"]["Class"], "0x240404")         # untouched
        kb = bluez.load_info(os.path.join(self.bt, AD, KB, "info"))
        self.assertEqual(kb["LongTermKey"]["Authenticated"], "2")        # Secure Connections
        self.assertEqual(kb["General"]["Name"], "MX Keys")
        mode = os.stat(os.path.join(self.bt, AD, KB, "info")).st_mode & 0o777
        self.assertEqual(mode, 0o600)
        st = {p.address: p.status for p in self.do_scan().plans}
        self.assertTrue(all(s in (sync.IN_SYNC, sync.LINUX_ONLY) for s in st.values()), st)

    def test_restore(self):
        res = sync.apply(self.do_scan(), [MOUSE.lower(), KB], self.state, restart=False)
        self.assertEqual(len(res["applied"]), 2)
        self.assertEqual(self.info(PHONES), HEADPHONES_INFO)            # not selected, untouched
        sync.restore(None, self.state, restart=False, bluez_root=self.bt)
        self.assertEqual(self.info(MOUSE), MOUSE_INFO)
        self.assertFalse(os.path.exists(os.path.join(self.bt, AD, KB)))  # imported device removed

    def test_dry_run_changes_nothing(self):
        res = sync.apply(self.do_scan(), None, self.state, restart=False, dry_run=True)
        self.assertEqual(len(res["applied"]), 5)
        self.assertEqual(self.info(MOUSE), MOUSE_INFO)
        self.assertFalse(os.path.exists(self.state))

    def test_dirty_hive_blocks_sync(self):
        s = self.do_scan("SYSTEM.dirty")
        self.assertIn({"code": "hive_dirty"}, s.notes)
        with self.assertRaises(DualPairError) as e:
            sync.apply(s, None, self.state, restart=False)
        self.assertEqual(e.exception.code, "hive_dirty")
        sync.apply(s, None, self.state, restart=False, force=True)

    def test_adapter_with_other_address(self):
        os.rename(os.path.join(self.bt, AD), os.path.join(self.bt, "00:AA:BB:CC:DD:EE"))
        s = self.do_scan()
        self.assertEqual(s.notes[0]["code"], "adapter_mapped")
        self.assertEqual({p.adapter_linux for p in s.plans}, {"00:AA:BB:CC:DD:EE"})

    def test_cli_json(self):
        base = ["--json", "--win", os.path.join(FIX, "SYSTEM"), "--bluez-dir", self.bt, "--state-dir", self.state]
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(base + ["scan"]), 0)
        self.assertEqual(len(json.loads(out.getvalue())["devices"]), 6)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(base + ["sync", "99:99:99:99:99:99"]), 2)
        self.assertEqual(json.loads(out.getvalue())["error"]["code"], "unknown_device")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(["--json", "--win", self.tmp, "scan"]), 2)
        self.assertEqual(json.loads(out.getvalue())["error"]["code"], "no_windows_at")


if __name__ == "__main__":
    unittest.main()
