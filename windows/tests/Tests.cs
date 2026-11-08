// Tests for DualPair for Windows. Run as administrator on Windows (CI), or under Mono (emulated registry).
// Uses a test registry path, a test mailbox folder and a test state folder: never the real ones.
//   Tests.exe <path to tests/protocol_vectors.json> [<folder with a message written by Python>]
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using Microsoft.Win32;

namespace DualPair.Tests
{
    public static class Tests
    {
        const string Params = @"SOFTWARE\DualPairTest\BTHPORT\Parameters";
        const string ClockKey = @"SOFTWARE\DualPairTest\TimeZoneInformation";
        static int failures;

        static void Check(bool ok, string what)
        {
            Console.WriteLine((ok ? "ok   " : "FAIL ") + what);
            if (!ok) failures++;
        }

        static void Seed()
        {
            Registry.LocalMachine.DeleteSubKeyTree(@"SOFTWARE\DualPairTest", false);
            using (var a = Registry.LocalMachine.CreateSubKey(Params + @"\Keys\c41375c0e2e6"))
            {
                a.SetValue("a4bfc6d0e5ff", Protocol.FromHex("00000000000000000000000000000000"), RegistryValueKind.Binary);
                a.SetValue("MasterIRK", Protocol.FromHex("0102030405060708090A0B0C0D0E0F10"), RegistryValueKind.Binary);
                using (var m = a.CreateSubKey("fcc2073c8ad2"))
                {
                    m.SetValue("LTK", Protocol.FromHex("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"), RegistryValueKind.Binary);
                    m.SetValue("KeyLength", 0, RegistryValueKind.DWord);
                    m.SetValue("ERand", 2L, RegistryValueKind.QWord);
                    m.SetValue("EDIV", 1, RegistryValueKind.DWord);
                    m.SetValue("AddressType", 1, RegistryValueKind.DWord);
                }
            }
            using (var d = Registry.LocalMachine.CreateSubKey(Params + @"\Devices\a4bfc6d0e5ff"))
                d.SetValue("Name", System.Text.Encoding.UTF8.GetBytes("WH-1000XM4\0"), RegistryValueKind.Binary);
            Registry.LocalMachine.CreateSubKey(ClockKey).Dispose();
        }

        public static int Main(string[] args)
        {
            var vectors = (Dictionary<string, object>)Protocol.Serializer().DeserializeObject(File.ReadAllText(args[0]));
            var tmp = Path.Combine(Path.GetTempPath(), "dualpair-tests-" + Guid.NewGuid().ToString("N"));
            var opt = new Options { MailboxDir = Path.Combine(tmp, "EFI", "DualPair"), ParamsPath = Params, StateDir = Path.Combine(tmp, "state") };
            Clock.KeyPath = ClockKey;
            Directory.CreateDirectory(opt.MailboxDir);
            try
            {
                VectorTests(vectors);
                Seed();
                StoreTests(opt);
                ImportTests(opt);
                ExportAndStatusTests(opt);
                ClockTests(opt);
                if (args.Length > 1) CrossTests(opt, args[1]);
            }
            finally
            {
                Registry.LocalMachine.DeleteSubKeyTree(@"SOFTWARE\DualPairTest", false);
                if (args.Length <= 1) Directory.Delete(tmp, true);
                else Console.WriteLine("export for Python: " + Path.Combine(opt.MailboxDir, "to-linux"));
            }
            Console.WriteLine(failures == 0 ? "ALL PASSED" : failures + " FAILED");
            return failures == 0 ? 0 : 1;
        }

        static void VectorTests(Dictionary<string, object> v)
        {
            foreach (Dictionary<string, object> f in (object[])v["fingerprints"])
            {
                var ediv = f["ediv"] is int ? (int)f["ediv"] : 0;
                var rand = f["rand"] is string ? ulong.Parse((string)f["rand"], CultureInfo.InvariantCulture) : 0UL;
                Check(Protocol.Fingerprint(f["link_key"] as string, f["ltk"] as string, ediv, rand) == (string)f["expected"],
                      "fingerprint " + f["expected"]);
            }
            var now = Protocol.ParseIso(v["now"]);
            var valid = (Dictionary<string, object>)v["valid_keys_message"];
            var fname = valid["id"] + ".json";
            var msg = Protocol.Validate(Clone(valid), "linux", fname, now);
            Check(msg.Devices.Count == 2 && msg.Devices[0].Le.Rand == 12345678901234567890UL, "valid message");
            foreach (Dictionary<string, object> c in (object[])v["invalid_messages"])
            {
                var m = Clone(valid);
                object patch, dpatch;
                if (c.TryGetValue("patch", out patch)) foreach (var kv in (Dictionary<string, object>)patch) m[kv.Key] = kv.Value;
                if (c.TryGetValue("device_patch", out dpatch))
                {
                    var dev = (Dictionary<string, object>)((object[])((Dictionary<string, object>)m["payload"])["devices"])[0];
                    foreach (var kv in (Dictionary<string, object>)dpatch) dev[kv.Key] = kv.Value;
                }
                var rejected = false;
                try { Protocol.Validate(m, "linux", fname, now); } catch (InvalidMessageException) { rejected = true; }
                Check(rejected, "rejects: " + c["why"]);
            }
        }

        static Dictionary<string, object> Clone(Dictionary<string, object> d)
        {
            var s = Protocol.Serializer();
            return (Dictionary<string, object>)s.DeserializeObject(s.Serialize(d));
        }

        static void StoreTests(Options opt)
        {
            var devs = new BluetoothStore(opt.ParamsPath, opt.StateDir).Devices();
            Check(devs.Count == 2, "reads 2 devices (MasterIRK ignored)");
            var phones = devs.FirstOrDefault(d => d.Address == "A4:BF:C6:D0:E5:FF");
            Check(phones != null && phones.Kind == "classic" && phones.Name == "WH-1000XM4", "classic device and name");
            var mouse = devs.FirstOrDefault(d => d.Address == "FC:C2:07:3C:8A:D2");
            Check(mouse != null && mouse.Le.EncSize == 16 && mouse.Le.Ediv == 1 && mouse.Le.Rand == 2 && mouse.Le.AddressType == "static",
                  "LE device (KeyLength 0 means 16)");
        }

        static string WriteLinuxMessage(Options opt, List<Device> devices)
        {
            string id;
            var msg = Protocol.NewMessage("keys", "linux", new Dictionary<string, object> {
                { "devices", devices.Select(d => (object)Protocol.DeviceJson(d)).ToArray() } }, out id);
            Protocol.WriteJsonFile(Path.Combine(opt.MailboxDir, "to-windows", id + ".json"), msg);
            return id;
        }

        static void ImportTests(Options opt)
        {
            var id = WriteLinuxMessage(opt, new List<Device> {
                new Device { Adapter = "C4:13:75:C0:E2:E6", Address = "A4:BF:C6:D0:E5:FF", Name = "WH-1000XM4", LinkKey = "5A9B0B2C3D4E5F60718293A4B5C6D7E8" },
                new Device { Adapter = "C4:13:75:C0:E2:E6", Address = "FC:C2:07:3C:8A:D2", Name = "TK-MS317 5.0",
                             Le = new LEKeys { Ltk = "3F8A1C5E9B2D7046E1A3C5F7092B4D6E", EncSize = 16, Ediv = 38922, Rand = 12345678901234567890UL,
                                               Irk = "7E21B9D4A6038F5C1D9E2B7A4C6F8E03", AddressType = "static" } },
                new Device { Adapter = "C4:13:75:C0:E2:E6", Address = "11:22:33:44:55:66", Name = "Never paired here", LinkKey = "11111111111111111111111111111111" } });
            var agent = new Agent(opt);
            agent.RunNow(new Dictionary<string, object> { { "op", "status" } });
            var st = Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "status.json"));
            var pending = (object[])st["pending"];
            Check(pending.Length == 1, "pending message shown in status");
            var pdevs = (object[])((Dictionary<string, object>)pending[0])["devices"];
            Check(pdevs.Cast<Dictionary<string, object>>().Count(d => (bool)d["paired_in_windows"]) == 2, "knows which are paired in Windows");

            var r = agent.RunNow(new Dictionary<string, object> { { "op", "import" }, { "message_id", id },
                { "addresses", new object[] { "A4:BF:C6:D0:E5:FF", "FC:C2:07:3C:8A:D2", "11:22:33:44:55:66" } } });
            var results = ((object[])r["results"]).Cast<Dictionary<string, object>>().ToDictionary(x => (string)x["address"], x => (string)x["result"]);
            Check(results["A4:BF:C6:D0:E5:FF"] == "imported" && results["FC:C2:07:3C:8A:D2"] == "imported", "imports paired devices");
            Check(results["11:22:33:44:55:66"] == "not_paired", "does not create devices");
            using (var a = Registry.LocalMachine.OpenSubKey(Params + @"\Keys\c41375c0e2e6"))
            {
                Check(Protocol.Hex((byte[])a.GetValue("a4bfc6d0e5ff")) == "5A9B0B2C3D4E5F60718293A4B5C6D7E8", "classic key written");
                Check(a.GetValue("112233445566") == null, "no value created for unpaired device");
                using (var m = a.OpenSubKey("fcc2073c8ad2"))
                {
                    Check(Protocol.Hex((byte[])m.GetValue("LTK")) == "3F8A1C5E9B2D7046E1A3C5F7092B4D6E", "LTK written");
                    Check(unchecked((ulong)(long)m.GetValue("ERand")) == 12345678901234567890UL, "ERand written as QWORD");
                    Check((int)m.GetValue("EDIV") == 38922 && (int)m.GetValue("KeyLength") == 16, "EDIV and KeyLength written");
                    Check((int)m.GetValue("AddressType") == 1, "AddressType kept");
                }
            }
            Check(!File.Exists(Path.Combine(opt.MailboxDir, "to-windows", id + ".json")), "message deleted after import");
            Check(Directory.GetFiles(Path.Combine(opt.StateDir, "backups")).Length == 1, "backup saved");

            r = agent.RunNow(new Dictionary<string, object> { { "op", "restore" } });
            using (var a = Registry.LocalMachine.OpenSubKey(Params + @"\Keys\c41375c0e2e6"))
            using (var m = a.OpenSubKey("fcc2073c8ad2"))
            {
                Check(Protocol.Hex((byte[])a.GetValue("a4bfc6d0e5ff")) == "00000000000000000000000000000000", "restore: classic key back");
                Check(Protocol.Hex((byte[])m.GetValue("LTK")) == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" && (long)m.GetValue("ERand") == 2L, "restore: LE keys back");
            }
            r = agent.RunNow(new Dictionary<string, object> { { "op", "import" }, { "message_id", "../../evil" } });
            Check(r.ContainsKey("error"), "unknown message id refused");
        }

        static void ExportAndStatusTests(Options opt)
        {
            Protocol.WriteJsonFile(Path.Combine(opt.MailboxDir, "status-linux.json"), new Dictionary<string, object> {
                { "dualpair", 1 }, { "system", "linux" }, { "version", "0.3.0" }, { "written", Protocol.Iso(DateTime.UtcNow) },
                { "clock", new Dictionary<string, object> { { "rtc_utc", true }, { "timezone", "Europe/Rome" } } },
                { "bluetooth", new Dictionary<string, object> { { "available", true }, { "devices", new object[] {
                    new Dictionary<string, object> { { "adapter", "C4:13:75:C0:E2:E6" }, { "address", "A4:BF:C6:D0:E5:FF" }, { "kind", "classic" },
                        { "fingerprint", Protocol.Fingerprint("00000000000000000000000000000000", null, 0, 0) } } } } } } });
            var r = new Agent(opt).RunNow(new Dictionary<string, object> { { "op", "export" } });
            Check(r.ContainsKey("message_id") && (int)r["devices"] == 2, "export");
            var msgs = Mailbox.Open(opt.MailboxDir).List("linux", false);
            Check(msgs.Count == 1 && msgs[0].Devices.Count == 2, "export message valid for Linux");
            var st = Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "status.json"));
            var states = ((object[])st["device_states"]).Cast<Dictionary<string, object>>().ToDictionary(d => (string)d["address"], d => (string)d["state"]);
            Check(states["A4:BF:C6:D0:E5:FF"] == "same" && states["FC:C2:07:3C:8A:D2"] == "windows_only", "compares with Linux by fingerprint");
            var shared = File.ReadAllText(Path.Combine(opt.MailboxDir, "status-windows.json"));
            Check(!shared.Contains("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA") && shared.Contains("\"fingerprint\""), "shared status has no keys");
        }

        static void ClockTests(Options opt)
        {
            Clock.SetRtcUtc(false);
            string id;
            var msg = Protocol.NewMessage("set_clock", "linux", new Dictionary<string, object> { { "windows_utc", true } }, out id);
            Protocol.WriteJsonFile(Path.Combine(opt.MailboxDir, "to-windows", id + ".json"), msg);
            new Agent(opt).RunTask();
            Check(Clock.RtcUtc(), "set_clock from Linux applied at task run");
            Check(!File.Exists(Path.Combine(opt.MailboxDir, "to-windows", id + ".json")), "set_clock message deleted");
            var p = Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "pending.json"));
            Check(p.ContainsKey("clock_applied") && (bool)p["clock_applied"], "logon notice prepared");
            Clock.SetRtcUtc(false);
            Check(!Clock.RtcUtc(), "back to local time");
        }

        /// <summary>Import a message written by the Python side (send-to-windows).</summary>
        static void CrossTests(Options opt, string pythonBox)
        {
            var dst = Path.Combine(opt.MailboxDir, "to-windows");
            Directory.CreateDirectory(dst);
            foreach (var f in Directory.GetFiles(Path.Combine(pythonBox, "to-windows"), "*.json"))
                File.Copy(f, Path.Combine(dst, Path.GetFileName(f)), true);
            var msgs = Mailbox.Open(opt.MailboxDir).List("windows", false).Where(m => m.Type == "keys").ToList();
            Check(msgs.Count == 1, "Python message accepted");
            var r = new Agent(opt).RunNow(new Dictionary<string, object> { { "op", "import" }, { "message_id", msgs[0].Id } });
            var ok = ((object[])r["results"]).Cast<Dictionary<string, object>>().All(x => (string)x["result"] == "imported");
            Check(ok, "Python keys imported");
            // leave an export for the Python side to validate
            new Agent(opt).RunNow(new Dictionary<string, object> { { "op", "export" } });
        }
    }
}
