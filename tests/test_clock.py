"""Dual-boot clock check and fixes."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from dualpair import cli, clock, sync
from dualpair.errors import DualPairError
from dualpair.windows import load_windows

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def done(stdout="", code=0, stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class WindowsSide(unittest.TestCase):
    def test_local_by_default(self):
        w = load_windows(os.path.join(FIX, "SYSTEM"))
        self.assertFalse(w.rtc_utc)
        self.assertEqual(w.timezone, "W. Europe Standard Time")

    def test_real_time_is_universal_qword(self):
        self.assertTrue(load_windows(os.path.join(FIX, "SYSTEM.utc")).rtc_utc)


class States(unittest.TestCase):
    def test_all_combinations(self):
        local = load_windows(os.path.join(FIX, "SYSTEM"))
        utc = load_windows(os.path.join(FIX, "SYSTEM.utc"))
        self.assertEqual(clock.status(local, linux_local=False)["state"], clock.CONFLICT)
        self.assertEqual(clock.status(local, linux_local=True)["state"], clock.OK_LOCAL)
        self.assertEqual(clock.status(utc, linux_local=False)["state"], clock.OK_UTC)
        self.assertEqual(clock.status(utc, linux_local=True)["state"], clock.CONFLICT_REVERSE)
        self.assertIn("RealTimeIsUniversal /t REG_DWORD /d 1", clock.status(local, False)["windows_command"])


class LinuxSide(unittest.TestCase):
    @mock.patch("dualpair.clock.subprocess.run")
    def test_timedatectl(self, run):
        run.return_value = done("yes\n")
        self.assertTrue(clock.linux_rtc_local())
        run.return_value = done("no\n")
        self.assertFalse(clock.linux_rtc_local())

    @mock.patch("dualpair.clock.subprocess.run", side_effect=FileNotFoundError)
    def test_adjtime_fallback(self, run):
        for content, expected in (("0.0 0 0\n0\nLOCAL\n", True), ("0.0 0 0\n0\nUTC\n", False)):
            with mock.patch("builtins.open", mock.mock_open(read_data=content)):
                self.assertEqual(clock.linux_rtc_local(), expected)
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertFalse(clock.linux_rtc_local())

    @mock.patch("dualpair.clock.subprocess.run")
    def test_set_linux_keeps_system_clock(self, run):
        run.return_value = done()
        clock.set_linux(local=True)
        self.assertEqual(run.call_args[0][0], ["timedatectl", "set-local-rtc", "1"])
        clock.set_linux(local=False)
        self.assertEqual(run.call_args[0][0], ["timedatectl", "set-local-rtc", "0"])
        self.assertNotIn("--adjust-system-clock", run.call_args[0][0])

    @mock.patch("dualpair.clock.subprocess.run")
    def test_set_linux_failure(self, run):
        run.return_value = done(code=1, stderr="Access denied")
        with self.assertRaises(DualPairError) as e:
            clock.set_linux(local=True)
        self.assertEqual(e.exception.code, "clock_failed")


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "C4:13:75:C0:E2:E6"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, argv, **kw):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("dualpair.clock.linux_rtc_local", return_value=False):
            code = cli.main(argv, **kw)
        return code, json.loads(out.getvalue())

    def test_scan_includes_clock(self):
        code, res = self.run_cli(["--json", "--win", os.path.join(FIX, "SYSTEM"), "--bluez-dir", self.tmp, "scan"])
        self.assertEqual(res["clock"]["state"], clock.CONFLICT)

    def test_clock_command(self):
        code, res = self.run_cli(["--json", "--win", os.path.join(FIX, "SYSTEM.utc"), "clock"])
        self.assertEqual(res["clock"]["state"], clock.OK_UTC)

    def test_read_only_helper_cannot_set(self):
        code, res = self.run_cli(["--json", "--win", os.path.join(FIX, "SYSTEM"), "clock", "--set", "linux-local"],
                                 read_only=True)
        self.assertEqual(res["error"]["code"], "read_only")
        code, res = self.run_cli(["--json", "--win", os.path.join(FIX, "SYSTEM"), "clock"], read_only=True)
        self.assertEqual(code, 0)

    def test_no_bluetooth_adapter_is_not_fatal(self):
        empty = tempfile.mkdtemp()
        try:
            s = sync.scan(load_windows(os.path.join(FIX, "SYSTEM")), empty)
            self.assertEqual(s.plans, [])
            self.assertIn({"code": "no_linux_adapter"}, s.notes)
        finally:
            os.rmdir(empty)


if __name__ == "__main__":
    unittest.main()
