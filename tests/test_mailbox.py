"""Exchange with DualPair for Windows through the ESP folder (docs/protocol.md)."""
import copy
import datetime
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from dualpair import cli, mailbox
from dualpair.errors import DualPairError
from dualpair.windows import load_windows

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures")
VEC = json.load(open(os.path.join(HERE, "protocol_vectors.json")))
NOW = mailbox.parse_iso(VEC["now"])
AD = "C4:13:75:C0:E2:E6"


class Vectors(unittest.TestCase):
    def test_fingerprints(self):
        for v in VEC["fingerprints"]:
            rand = int(v["rand"]) if v["rand"] else None
            self.assertEqual(mailbox.fingerprint(v["link_key"], v["ltk"], v["ediv"], rand), v["expected"])

    def test_valid_message(self):
        m = copy.deepcopy(VEC["valid_keys_message"])
        m = mailbox.validate(m, "linux", m["id"] + ".json", now=NOW)
        self.assertEqual([d.address for d in m["_devices"]], ["FC:C2:07:3C:8A:D2", "A4:BF:C6:D0:E5:FF"])
        self.assertEqual(m["_devices"][0].le.rand, 12345678901234567890)

    def test_wifi(self):
        for v in VEC["wifi_fingerprints"]:
            self.assertEqual(mailbox.wifi_fingerprint(v["ssid"], v["password"]), v["expected"])
        m = copy.deepcopy(VEC["valid_wifi_message"])
        m = mailbox.validate(m, "linux", m["id"] + ".json", now=NOW)
        self.assertEqual([n.ssid for n in m["_networks"]], ["Casa", "Bar Open", "Caffè"])
        for case in VEC["invalid_wifi_networks"]:
            m = copy.deepcopy(VEC["valid_wifi_message"])
            m["payload"]["networks"] = [case["network"]]
            with self.assertRaises(mailbox.InvalidMessage, msg=case["why"]):
                mailbox.validate(m, "linux", m["id"] + ".json", now=NOW)
        m = copy.deepcopy(VEC["valid_fast_startup_message"])
        self.assertFalse(mailbox.validate(m, "linux", m["id"] + ".json", now=NOW)["payload"]["enabled"])

    def test_invalid_messages(self):
        for case in VEC["invalid_messages"]:
            m = copy.deepcopy(VEC["valid_keys_message"])
            m.update(case.get("patch", {}))
            if "device_patch" in case:
                m["payload"]["devices"][0].update(case["device_patch"])
            fname = VEC["valid_keys_message"]["id"] + ".json"
            with self.assertRaises((mailbox.InvalidMessage, ValueError), msg=case["why"]):
                mailbox.validate(m, "linux", fname, now=NOW)


class Box(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mb = os.path.join(self.tmp, "EFI", "DualPair")
        self.bt = os.path.join(self.tmp, "bt")
        os.makedirs(self.mb)
        os.makedirs(os.path.join(self.bt, AD))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, args, read_only=False, win=os.path.join(FIX, "SYSTEM")):
        base = ["--json", "--bluez-dir", self.bt, "--state-dir", os.path.join(self.tmp, "state"),
                "--mailbox-dir", self.mb]
        if win:
            base += ["--win", win]
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("dualpair.clock.linux_rtc_local", return_value=False), \
                mock.patch("dualpair.clock.linux_timezone", return_value="Europe/Rome"):
            code = cli.main(base + args, read_only=read_only)
        return code, json.loads(out.getvalue())

    def windows_export(self, devices=None):
        """What DualPair for Windows writes when the disk is encrypted."""
        w = load_windows(os.path.join(FIX, "SYSTEM"))
        devs = devices or [mailbox.device_to_json(d) for d in w.devices]
        msg = copy.deepcopy(VEC["valid_keys_message"])
        now = mailbox.utcnow()
        msg.update({"from": "windows", "id": mailbox.new_id(now), "created": mailbox.iso(now),
                    "expires": mailbox.iso(now + datetime.timedelta(days=1)), "payload": {"devices": devs}})
        os.makedirs(os.path.join(self.mb, "to-linux"), exist_ok=True)
        with open(os.path.join(self.mb, "to-linux", msg["id"] + ".json"), "w") as f:
            json.dump(msg, f)
        with open(os.path.join(self.mb, "status-windows.json"), "w") as f:
            json.dump({"dualpair": 1, "system": "windows", "version": "0.3.0", "written": mailbox.iso(now),
                       "clock": {"rtc_utc": True, "timezone": "W. Europe Standard Time"},
                       "bluetooth": {"available": True, "devices": []}}, f)
        return msg["id"]

    def test_send_list_delete_and_replace(self):
        a = mailbox.send(self.mb, "windows", "set_clock", {"windows_utc": True})
        b = mailbox.send(self.mb, "windows", "set_clock", {"windows_utc": False})   # replaces a
        msgs = mailbox.list_messages(self.mb, "windows")
        self.assertEqual([m["id"] for m in msgs], [b])
        self.assertFalse(msgs[0]["payload"]["windows_utc"])
        mailbox.delete(self.mb, "windows", b)
        self.assertEqual(mailbox.list_messages(self.mb, "windows"), [])
        with self.assertRaises(DualPairError):
            mailbox.delete(self.mb, "windows", "../../etc/passwd")
        self.assertNotEqual(a, b)

    def test_invalid_files_skipped_and_cleaned(self):
        box = os.path.join(self.mb, "to-linux")
        os.makedirs(box)
        open(os.path.join(box, "20261108-000000-abcdef.json"), "w").write("{not json")
        open(os.path.join(box, "huge.json"), "w").write("x" * (mailbox.MAX_FILE + 1))
        self.assertEqual(mailbox.list_messages(self.mb, "linux"), [])
        mailbox.list_messages(self.mb, "linux", delete_invalid=True)
        self.assertEqual(os.listdir(box), [])

    def test_scan_publishes_status_without_keys(self):
        bt_dev = os.path.join(self.bt, AD, "FC:C2:07:3C:8A:D2")
        os.makedirs(bt_dev)
        open(os.path.join(bt_dev, "info"), "w").write(
            "[General]\nName=TK\n[LongTermKey]\nKey=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nEDiv=1\nRand=2\nEncSize=16\n")
        code, res = self.run_cli(["scan"])
        self.assertEqual(code, 0)
        raw = open(os.path.join(self.mb, "status-linux.json")).read()
        st = json.loads(raw)
        self.assertEqual(st["system"], "linux")
        self.assertTrue(st["clock"]["rtc_utc"])
        self.assertEqual(st["bluetooth"]["devices"][0]["fingerprint"],
                         mailbox.fingerprint(None, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", 1, 2))
        self.assertIsNone(re.search(r"[0-9A-F]{32}", raw))        # no keys in the status file
        self.assertEqual(res["source_kind"], "disk")
        self.assertIsNone(res["windows_app"])

    def test_bitlocker_falls_back_to_export(self):
        export_id = self.windows_export()
        with mock.patch("dualpair.cli.load_windows", side_effect=DualPairError("bitlocker", devices="/dev/x")):
            code, res = self.run_cli(["scan"], win=None)
            self.assertEqual(code, 0, res)
            self.assertEqual(res["source_kind"], "export")
            self.assertEqual(res["clock"]["windows"], "utc")          # from status-windows.json
            self.assertEqual(res["windows_app"]["version"], "0.3.0")
            self.assertEqual(len([d for d in res["devices"] if d["status"] == "windows_only"]), 5)
            code, res = self.run_cli(["sync", "FC:C2:07:3C:8A:D2"], win=None)
            self.assertEqual(code, 0, res)
        self.assertTrue(os.path.isfile(os.path.join(self.bt, AD, "FC:C2:07:3C:8A:D2", "info")))
        self.assertFalse(os.path.exists(os.path.join(self.mb, "to-linux", export_id + ".json")))  # keys removed

    def test_bitlocker_without_export_is_an_error(self):
        with mock.patch("dualpair.cli.load_windows", side_effect=DualPairError("bitlocker", devices="/dev/x")):
            code, res = self.run_cli(["scan"], win=None)
        self.assertEqual(res["error"]["code"], "bitlocker")

    def test_send_to_windows(self):
        bt_dev = os.path.join(self.bt, AD, "A4:BF:C6:D0:E5:FF")
        os.makedirs(bt_dev)
        open(os.path.join(bt_dev, "info"), "w").write(
            "[General]\nName=WH-1000XM4\n[LinkKey]\nKey=11112222333344445555666677778888\nType=8\n")
        code, res = self.run_cli(["send-to-windows", "a4:bf:c6:d0:e5:ff"])
        self.assertEqual(code, 0, res)
        msgs = mailbox.list_messages(self.mb, "windows")
        self.assertEqual(len(msgs), 1)
        d = msgs[0]["_devices"][0]
        self.assertEqual((d.adapter, d.address, d.link_key), (AD, "A4:BF:C6:D0:E5:FF", "11112222333344445555666677778888"))
        code, res = self.run_cli(["pending"])
        self.assertEqual(res["pending"][0]["devices"], ["WH-1000XM4"])
        code, res = self.run_cli(["pending", "--cancel", msgs[0]["id"]])
        self.assertEqual(res["pending"], [])

    def test_clock_request_for_windows(self):
        code, res = self.run_cli(["clock", "--set", "windows-utc"])
        self.assertEqual(code, 0, res)
        self.assertTrue(res["clock"]["pending"])
        m = mailbox.list_messages(self.mb, "windows")[0]
        self.assertEqual((m["type"], m["payload"]), ("set_clock", {"windows_utc": True}))

    def test_restrictions(self):
        for args in (["send-to-windows", "A4:BF:C6:D0:E5:FF"], ["pending", "--cancel", "20261108-000000-abcdef"],
                     ["clock", "--set", "windows-utc"]):
            code, res = self.run_cli(args, read_only=True)
            self.assertEqual(res["error"]["code"], "read_only", args)
        with mock.patch.dict(os.environ, {"PKEXEC_UID": "1000"}):
            out = io.StringIO()
            with redirect_stdout(out):
                cli.main(["--json", "--mailbox-dir", self.mb, "scan"])
            self.assertEqual(json.loads(out.getvalue())["error"]["code"], "option_not_allowed")


if __name__ == "__main__":
    unittest.main()
