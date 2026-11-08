# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Wi-Fi (NetworkManager), Windows Fast Startup and firmware boot order."""
import io
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from dualpair import boot, cli, mailbox, wifi
from dualpair.mailbox import WifiNetwork

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
AD = "C4:13:75:C0:E2:E6"

NM = {
    "Casa.nmconnection": "[connection]\nid=Casa\nuuid=1\ntype=wifi\n\n[wifi]\nmode=infrastructure\nssid=Casa\n\n"
                         "[wifi-security]\nkey-mgmt=wpa-psk\npsk=una password\n\n[ipv4]\nmethod=auto\n",
    "W3.nmconnection": "[connection]\nid=W3\ntype=wifi\n[wifi]\nssid=Caffè\nhidden=true\n[wifi-security]\nkey-mgmt=sae\npsk=\\sspazio\\\\x\n",
    "Open.nmconnection": "[connection]\nid=Bar\ntype=wifi\n[wifi]\nssid=Bar Open\n",
    "Old.nmconnection": "[connection]\nid=Old\ntype=802-11-wireless\n[802-11-wireless]\nssid=79;108;100;\n"
                        "[802-11-wireless-security]\nkey-mgmt=wpa-psk\npsk=oldoldold\n",
    "Work.nmconnection": "[connection]\nid=Work\ntype=wifi\n[wifi]\nssid=Work\n[wifi-security]\nkey-mgmt=wpa-eap\n[802-1x]\neap=peap\n",
    "Keyring.nmconnection": "[connection]\nid=K\ntype=wifi\n[wifi]\nssid=K\n[wifi-security]\nkey-mgmt=wpa-psk\npsk-flags=1\n",
    "Wired.nmconnection": "[connection]\nid=Wired\ntype=ethernet\n",
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.nm = os.path.join(self.tmp, "nm")
        self.mb = os.path.join(self.tmp, "EFI", "DualPair")
        self.bt = os.path.join(self.tmp, "bt")
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.nm)
        os.makedirs(self.mb)
        os.makedirs(os.path.join(self.bt, AD))
        for name, text in NM.items():
            with open(os.path.join(self.nm, name), "w", encoding="utf-8") as f:
                f.write(text)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, args, read_only=False):
        base = ["--json", "--win", os.path.join(FIX, "SYSTEM"), "--bluez-dir", self.bt, "--state-dir", self.state,
                "--mailbox-dir", self.mb, "--nm-dir", self.nm]
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("dualpair.clock.linux_rtc_local", return_value=False), \
                mock.patch("dualpair.clock.linux_timezone", return_value="Europe/Rome"):
            code = cli.main(base + args, read_only=read_only)
        return code, json.loads(out.getvalue())


class Wifi(Base):
    def test_parse(self):
        nets = {s.network.ssid: s.network for s in wifi.networks(self.nm)}
        self.assertEqual(sorted(nets), ["Bar Open", "Caffè", "Casa", "Old"])   # no enterprise, keyring, wired
        self.assertEqual((nets["Casa"].security, nets["Casa"].password), ("wpa-psk", "una password"))
        self.assertEqual((nets["Caffè"].security, nets["Caffè"].password, nets["Caffè"].hidden), ("sae", " spazio\\x", True))
        self.assertEqual((nets["Bar Open"].security, nets["Bar Open"].password), ("open", None))
        self.assertEqual(nets["Old"].password, "oldoldold")
        self.assertIsNone(wifi.networks(os.path.join(self.tmp, "missing")))

    def test_import(self):
        res = wifi.import_networks([
            WifiNetwork("Casa", "wpa-psk", "una password"),            # same
            WifiNetwork("Old", "wpa-psk", "newnewnew"),                 # other password
            WifiNetwork("Nuova", "sae", " lead space\\", True),         # new
        ], self.nm, self.state, reload=False)
        self.assertEqual([r["result"] for r in res], ["same", "updated", "added"])
        nets = {s.network.ssid: s for s in wifi.networks(self.nm)}
        self.assertEqual(nets["Old"].network.password, "newnewnew")
        self.assertEqual((nets["Nuova"].network.password, nets["Nuova"].network.hidden), (" lead space\\", True))
        self.assertEqual(stat.S_IMODE(os.stat(nets["Nuova"].path).st_mode), 0o600)
        backups = os.listdir(os.path.join(self.state, "backups-wifi"))
        self.assertEqual(len(backups), 1)

    def test_compare_with_windows(self):
        status = {"wifi": {"networks": [
            {"ssid": "Casa", "fingerprint": mailbox.wifi_fingerprint("Casa", "una password")},
            {"ssid": "Old", "fingerprint": mailbox.wifi_fingerprint("Old", "other")},
            {"ssid": "Ufficio", "security": "wpa-psk", "fingerprint": "00000000"}]}}
        c = wifi.compare([s.network for s in wifi.networks(self.nm)], status)
        st = {n["ssid"]: n["state"] for n in c["networks"]}
        self.assertEqual(st, {"Bar Open": "only_linux", "Caffè": "only_linux", "Casa": "same", "Old": "different"})
        self.assertEqual(c["only_windows"], [{"ssid": "Ufficio", "security": "wpa-psk"}])

    def test_cli_send_and_import(self):
        code, res = self.run_cli(["wifi", "--send", "Casa", "Caffè"])
        self.assertEqual(code, 0, res)
        m = [m for m in mailbox.list_messages(self.mb, "windows") if m["type"] == "wifi"][0]
        self.assertEqual([n.ssid for n in m["_networks"]], ["Casa", "Caffè"])
        st = json.load(open(os.path.join(self.mb, "status-linux.json")))
        self.assertNotIn("una password", json.dumps(st))                    # no passwords in the status
        self.assertEqual(len(st["wifi"]["networks"]), 4)
        # networks sent by Windows
        mailbox_msg = {"networks": [{"ssid": "Ufficio", "security": "wpa-psk", "password": "pass-ufficio", "hidden": False}]}
        mid = mailbox.send(self.mb, "linux", "wifi", mailbox_msg)
        code, res = self.run_cli(["scan"])
        self.assertEqual(res["wifi"]["from_windows"][0]["networks"][0], {"ssid": "Ufficio", "security": "wpa-psk", "state": "new"})
        code, res = self.run_cli(["wifi", "--import", mid])
        self.assertEqual(res["wifi"]["results"], [{"ssid": "Ufficio", "result": "added"}])
        self.assertFalse(os.path.exists(os.path.join(self.mb, "to-linux", mid + ".json")))   # passwords removed

    def test_restrictions(self):
        for args in (["wifi", "--send", "Casa"], ["wifi", "--import", "20261108-000000-abcdef"],
                     ["power", "--set-fast-startup", "off"], ["boot", "--linux-first"], ["boot", "--keep", "on"]):
            code, res = self.run_cli(args, read_only=True)
            self.assertEqual(res["error"]["code"], "read_only", args)
        with mock.patch.dict(os.environ, {"PKEXEC_UID": "1000"}):
            out = io.StringIO()
            with redirect_stdout(out):
                cli.main(["--json", "--nm-dir", self.nm, "wifi"])
            self.assertEqual(json.loads(out.getvalue())["error"]["code"], "option_not_allowed")


class Power(Base):
    def test_fast_startup(self):
        code, res = self.run_cli(["scan"])
        self.assertEqual(res["power"]["fast_startup"], True)
        code, res = self.run_cli(["power", "--set-fast-startup", "off"])
        self.assertIs(res["power"]["pending"], False)
        m = mailbox.list_messages(self.mb, "windows")[0]
        self.assertEqual((m["type"], m["payload"]), ("set_fast_startup", {"enabled": False}))


EFI_OUT = """BootCurrent: 0001
BootOrder: 0000,0001,0002
Boot0000* Windows Boot Manager\tHD(1,GPT,ab,0x800,0x32000)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)WINDOWS
Boot0001* ubuntu\tHD(1,GPT,ab,0x800,0x32000)/File(\\EFI\\ubuntu\\shimx64.efi)
Boot0002  UEFI: PXE IPv4\tPciRoot(0x0)/Pci(0x1f,0x6)/MAC(001122334455,0)
"""


class Boot(unittest.TestCase):
    def test_state(self):
        st = boot.state(boot.parse(EFI_OUT), {"keep_linux_first": True})
        self.assertEqual((st["linux_entry"], st["linux_loader"], st["windows_entry"]), ("0001", "\\EFI\\ubuntu\\shimx64.efi", "0000"))
        self.assertFalse(st["first_is_linux"])
        self.assertEqual(st["first_label"], "Windows Boot Manager")
        self.assertTrue(st["keep_linux_first"])
        self.assertEqual(boot.state(None, {}), {"available": False})

    @mock.patch("dualpair.boot.subprocess.run")
    def test_put_linux_first(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        boot.put_linux_first(boot.parse(EFI_OUT))
        self.assertEqual(run.call_args[0][0], ["efibootmgr", "-o", "0001,0000,0002"])

    def test_grub_lists_windows(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("menuentry 'Ubuntu' {\n}\nmenuentry 'Windows Boot Manager (on /dev/nvme0n1p1)' {\n chainloader /EFI/Microsoft/Boot/bootmgfw.efi\n}\n")
        try:
            self.assertTrue(boot.grub_lists_windows((f.name,)))
            with open(f.name, "w") as g:
                g.write("menuentry 'Ubuntu' {\n}\n")
            self.assertFalse(boot.grub_lists_windows((f.name,)))
            self.assertIsNone(boot.grub_lists_windows(("/nonexistent",)))
        finally:
            os.unlink(f.name)

    def test_settings(self):
        d = tempfile.mkdtemp()
        try:
            self.assertEqual(boot.load_settings(d), {})
            boot.save_settings(d, {"keep_linux_first": True})
            self.assertEqual(boot.load_settings(d), {"keep_linux_first": True})
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
