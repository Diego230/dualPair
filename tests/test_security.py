"""Security properties: the pkexec helper cannot be steered to other paths, backups cannot be
used to write or delete outside BlueZ's folder, keys are not printed, names cannot inject lines,
old backups expire."""
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from dualpair import bluez, cli, sync
from dualpair.errors import DualPairError
from dualpair.windows import clean_name, load_windows

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
HIVE = os.path.join(FIX, "SYSTEM")
AD = "C4:13:75:C0:E2:E6"
EVIL = "0A:0B:0C:0D:0E:0F"


def run_cli(argv, **kw):
    out = io.StringIO()
    with redirect_stdout(out):
        code = cli.main(argv, **kw)
    return code, json.loads(out.getvalue())


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bt = os.path.join(self.tmp, "bt")
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(os.path.join(self.bt, AD))
        self.opts = ["--json", "--win", HIVE, "--bluez-dir", self.bt, "--state-dir", self.state]

    def tearDown(self):
        shutil.rmtree(self.tmp)


class HelperRestrictions(Base):
    def test_pkexec_rejects_custom_paths(self):
        with mock.patch.dict(os.environ, {"PKEXEC_UID": "1000"}):
            for extra in (["--win", HIVE], ["--bluez-dir", self.bt], ["--state-dir", self.state]):
                code, res = run_cli(["--json", *extra, "scan"])
                self.assertEqual(code, 2)
                self.assertEqual(res["error"]["code"], "option_not_allowed", extra)

    def test_pkexec_rejects_show_keys(self):
        with mock.patch.dict(os.environ, {"PKEXEC_UID": "1000"}):
            code, res = run_cli(["--json", "sync", "--all", "--dry-run", "--show-keys"])
        self.assertEqual(res["error"]["code"], "option_not_allowed")

    def test_read_only_helper(self):
        for cmd in (["sync", "--all"], ["restore"]):
            code, res = run_cli(self.opts + cmd, read_only=True)
            self.assertEqual(res["error"]["code"], "read_only", cmd)
        code, res = run_cli(self.opts + ["scan"], read_only=True)
        self.assertEqual(code, 0)

    def test_unexpected_errors_are_json(self):
        with mock.patch("dualpair.cli.run", side_effect=RuntimeError("boom")):
            code, res = run_cli(self.opts + ["scan"])
        self.assertEqual(res["error"]["code"], "internal")


class KeysAndNames(Base):
    def test_dry_run_hides_keys(self):
        code, res = run_cli(self.opts + ["sync", "--all", "--dry-run"])
        infos = "".join(d["info"] for d in res["applied"])
        key_lines = [l for l in infos.splitlines() if l.startswith("Key=")]
        self.assertTrue(key_lines)
        self.assertTrue(all(l == "Key=<hidden>" for l in key_lines))
        code, res = run_cli(self.opts + ["sync", "--all", "--dry-run", "--show-keys"])  # root via sudo: allowed
        self.assertIn("Key=3F8A1C5E9B2D7046E1A3C5F7092B4D6E", "".join(d["info"] for d in res["applied"]))

    def test_name_cannot_inject_lines(self):
        s = sync.scan(load_windows(HIVE), self.bt)
        evil = next(p for p in s.plans if p.address == EVIL)
        self.assertNotIn("\n", evil.name)
        info = bluez.dump_info(sync.build_info(evil))
        lines = info.splitlines()
        self.assertEqual(lines.count("[LinkKey]"), 1)
        self.assertEqual([l for l in lines if l.startswith("Key=")], ["Key=0123456789ABCDEF0123456789ABCDEF"])
        self.assertEqual(sum(l.startswith("Name=") for l in lines), 1)

    def test_clean_name(self):
        self.assertEqual(clean_name(" a\tb\x00c\x7f "), "abc")
        self.assertEqual(len(clean_name("x" * 1000)), 248)
        self.assertIsNone(clean_name("\n\r"))


class Backups(Base):
    def make_backup(self, bid, entries, root=None):
        d = os.path.join(self.state, "backups", bid)
        os.makedirs(d)
        with open(os.path.join(d, "manifest.json"), "w") as f:
            json.dump({"bluez_root": root or self.bt, "entries": entries}, f)
        return d

    def test_manifest_path_traversal_refused(self):
        victim = os.path.join(self.tmp, "victim")
        os.makedirs(victim)
        self.make_backup("20260101-000000", [{"adapter": "..", "address": "../victim",
                                             "existed": False, "dir_existed": False}])
        with self.assertRaises(DualPairError) as e:
            sync.restore(None, self.state, restart=False, bluez_root=self.bt)
        self.assertEqual(e.exception.code, "bad_backup")
        self.assertTrue(os.path.isdir(victim))

    def test_manifest_other_root_refused(self):
        self.make_backup("20260101-000000", [{"adapter": AD, "address": EVIL, "existed": False}],
                         root=self.tmp)
        with self.assertRaises(DualPairError) as e:
            sync.restore(None, self.state, restart=False, bluez_root=self.bt)
        self.assertEqual(e.exception.code, "bad_backup")

    def test_backup_id_traversal_refused(self):
        self.make_backup("20260101-000000", [])
        with self.assertRaises(DualPairError) as e:
            sync.restore("../../etc", self.state, restart=False, bluez_root=self.bt)
        self.assertEqual(e.exception.code, "unknown_backup")

    def test_symlinked_backup_file_refused(self):
        d = self.make_backup("20260101-000000", [{"adapter": AD, "address": EVIL, "existed": True}])
        os.makedirs(os.path.join(d, AD, EVIL))
        os.symlink("/etc/hostname", os.path.join(d, AD, EVIL, "info"))
        with self.assertRaises(DualPairError) as e:
            sync.restore(None, self.state, restart=False, bluez_root=self.bt)
        self.assertEqual(e.exception.code, "bad_backup")

    def test_retention(self):
        for i in range(8):
            self.make_backup("20260101-00000%d" % i, [])
        sync.prune_backups(self.state)
        self.assertEqual(sorted(os.listdir(os.path.join(self.state, "backups"))),
                         ["20260101-00000%d" % i for i in range(3, 8)])
        old = time.time() - 40 * 86400
        for b in ("20260101-000003", "20260101-000004"):
            os.utime(os.path.join(self.state, "backups", b), (old, old))
        os.utime(os.path.join(self.state, "backups", "20260101-000007"), (old, old))  # newest: kept anyway
        sync.prune_backups(self.state)
        self.assertEqual(sorted(os.listdir(os.path.join(self.state, "backups"))),
                         ["20260101-000005", "20260101-000006", "20260101-000007"])

    def test_sync_prunes(self):
        for i in range(6):
            self.make_backup("20260101-00000%d" % i, [])
        sync.apply(sync.scan(load_windows(HIVE), self.bt), None, self.state, restart=False)
        self.assertEqual(len(os.listdir(os.path.join(self.state, "backups"))), sync.KEEP_BACKUPS)


if __name__ == "__main__":
    unittest.main()
