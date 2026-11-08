// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Diego Buono
// The privileged part. Runs as SYSTEM from the "DualPair\Agent" scheduled task: at every Windows
// start, and on demand when the window asks for something only SYSTEM can do (Bluetooth keys,
// Wi-Fi passwords).
//
// The window (administrator) talks to it through files in %ProgramData%\DualPair, a folder only
// SYSTEM and administrators can write:
//   requests\<id>.json   {"op": ..., ...}
//   results\<id>.json    the answer
//   status.json          everything the window shows (no keys, no passwords)
//   pending.json         what to tell the user at logon (readable by everyone, no secrets)
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace DualPair
{
    public class Options
    {
        public string MailboxDir;     // tests: a folder instead of the ESP
        public string ParamsPath;     // tests: registry path instead of BTHPORT\Parameters
        public string StateDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "DualPair");
    }

    public class Agent
    {
        // Seams for the tests (null = the real thing)
        public static Func<List<WifiNetwork>> WifiSource;
        public static Func<IEnumerable<WifiNetwork>, List<KeyValuePair<string, string>>> WifiSink;
        public static Func<BootInfo> BootSource;
        public static Func<FirmwareEntry, bool> BootSetter;

        readonly Options opt;
        readonly BluetoothStore bt;

        public Agent(Options opt)
        {
            this.opt = opt;
            bt = new BluetoothStore(opt.ParamsPath, opt.StateDir);
        }

        string RequestsDir { get { return Path.Combine(opt.StateDir, "requests"); } }
        string ResultsDir { get { return Path.Combine(opt.StateDir, "results"); } }
        bool IsTest { get { return opt.MailboxDir != null; } }

        List<WifiNetwork> WifiNetworks() { return WifiSource != null ? WifiSource() : Wifi.Export(opt.StateDir); }
        BootInfo Boot() { return BootSource != null ? BootSource() : (IsTest ? null : FirmwareBoot.Read()); }

        /// <summary>Task entry point: apply requests from Linux, answer queued requests from the
        /// window, refresh the status files.</summary>
        public void RunTask()
        {
            using (var mb = Mailbox.Open(opt.MailboxDir))
            {
                var notices = ApplyRequestsFromLinux(mb);
                KeepLinuxFirst(mb, notices);
                if (Directory.Exists(RequestsDir))
                    foreach (var path in Directory.GetFiles(RequestsDir, "*.json"))
                    {
                        var id = Path.GetFileNameWithoutExtension(path);
                        Dictionary<string, object> result;
                        try { result = Handle(Protocol.ReadJsonFile(path), mb); }
                        catch (Exception e) { result = new Dictionary<string, object> { { "error", e.Message } }; }
                        File.Delete(path);
                        Guid g;
                        if (Guid.TryParse(id, out g)) Protocol.WriteJsonFile(Path.Combine(ResultsDir, id + ".json"), result);
                    }
                WriteStatus(mb, notices);
            }
        }

        /// <summary>Run one operation directly (command line, tests).</summary>
        public Dictionary<string, object> RunNow(Dictionary<string, object> request)
        {
            using (var mb = Mailbox.Open(opt.MailboxDir))
            {
                var result = Handle(request, mb);
                WriteStatus(mb, new Dictionary<string, object>());
                return result;
            }
        }

        Dictionary<string, object> Handle(Dictionary<string, object> req, Mailbox mb)
        {
            object op;
            req.TryGetValue("op", out op);
            switch (op as string)
            {
                case "status":
                    return Ok();
                case "export":
                {
                    var devices = bt.Devices();
                    if (devices.Count == 0) return Error("err.no_devices");
                    var id = mb.Send("linux", "keys", new Dictionary<string, object> {
                        { "devices", devices.Take(Protocol.MaxDevices).Select(d => (object)Protocol.DeviceJson(d)).ToArray() } });
                    return new Dictionary<string, object> { { "ok", true }, { "message_id", id }, { "devices", devices.Count } };
                }
                case "import":
                {
                    var msg = FindMessage(mb, req, "keys");
                    if (msg == null) return Error("err.unknown_message");
                    var wanted = Strings_(req, "addresses", Protocol.IsMac);
                    var results = bt.Import(msg.Devices.Where(d => wanted == null || wanted.Contains(d.Address)).ToList());
                    mb.Delete("windows", msg.Id);      // handled: keys do not stay on the ESP
                    return new Dictionary<string, object> { { "ok", true }, { "results", results.Select(r => (object)new Dictionary<string, object> {
                        { "address", r.Address }, { "name", r.Name }, { "result", r.Result } }).ToArray() } };
                }
                case "export_wifi":
                {
                    var nets = WifiNetworks();
                    if (nets == null || nets.Count == 0) return Error("err.no_wifi");
                    var wanted = Strings_(req, "ssids", s => true);
                    var chosen = nets.Where(n => wanted == null || wanted.Contains(n.Ssid)).Take(Protocol.MaxDevices).ToList();
                    if (chosen.Count == 0) return Error("err.no_wifi");
                    var id = mb.Send("linux", "wifi", new Dictionary<string, object> { { "networks", chosen.Select(n => (object)Protocol.WifiJson(n)).ToArray() } });
                    return new Dictionary<string, object> { { "ok", true }, { "message_id", id }, { "networks", chosen.Count } };
                }
                case "import_wifi":
                {
                    var msg = FindMessage(mb, req, "wifi");
                    if (msg == null) return Error("err.unknown_message");
                    var wanted = Strings_(req, "ssids", s => true);
                    var chosen = msg.Networks.Where(n => wanted == null || wanted.Contains(n.Ssid)).ToList();
                    var results = WifiSink != null ? WifiSink(chosen) : Wifi.Import(chosen, WifiNetworks(), opt.StateDir);
                    mb.Delete("windows", msg.Id);      // passwords do not stay on the ESP
                    return new Dictionary<string, object> { { "ok", true }, { "results", results.Select(r => (object)new Dictionary<string, object> {
                        { "ssid", r.Key }, { "result", r.Value } }).ToArray() } };
                }
                case "discard":
                {
                    var msg = FindMessage(mb, req, null);
                    if (msg != null) mb.Delete("windows", msg.Id);
                    return Ok();
                }
                case "restore":
                    return bt.RestoreLast() ? Ok() : Error("err.no_backups");
                case "boot_linux_first":
                {
                    var linux = LinuxEntry(mb, Boot());
                    if (linux == null) return Error("err.no_linux_entry");
                    return (BootSetter != null ? BootSetter(linux) : FirmwareBoot.PutFirst(linux)) ? Ok() : Error("err.boot_failed");
                }
                default:
                    return Error("err.unknown_request");
            }
        }

        static Dictionary<string, object> Ok() { return new Dictionary<string, object> { { "ok", true } }; }

        static Dictionary<string, object> Error(string code)
        {
            return new Dictionary<string, object> { { "error", Strings.T(code) }, { "code", code } };
        }

        static Message FindMessage(Mailbox mb, Dictionary<string, object> req, string type)
        {
            object id;
            req.TryGetValue("message_id", out id);
            return mb.List("windows", false).FirstOrDefault(m => (type == null || m.Type == type) && m.Id == (id as string));
        }

        static HashSet<string> Strings_(Dictionary<string, object> req, string key, Func<string, bool> valid)
        {
            object a;
            if (!req.TryGetValue(key, out a) || !(a is object[])) return null;
            return new HashSet<string>(((object[])a).OfType<string>().Where(valid));
        }

        /// <summary>set_clock and set_fast_startup from Linux: the user already chose them there,
        /// so they are applied without asking again.</summary>
        Dictionary<string, object> ApplyRequestsFromLinux(Mailbox mb)
        {
            var notices = new Dictionary<string, object>();
            foreach (var m in mb.List("windows", true))
            {
                if (m.Type == "set_clock")
                {
                    Clock.SetRtcUtc(m.WindowsUtc);
                    notices["clock_applied"] = m.WindowsUtc;
                    mb.Delete("windows", m.Id);
                }
                else if (m.Type == "set_fast_startup")
                {
                    FastStartup.Set(m.FastStartupEnabled);
                    notices["fast_startup_applied"] = m.FastStartupEnabled;
                    mb.Delete("windows", m.Id);
                }
            }
            if (notices.ContainsKey("clock_applied") && !IsTest) Clock.Resync(3);   // network may not be up yet at boot
            return notices;
        }

        static Dictionary<string, object> LinuxBoot(Mailbox mb)
        {
            var linux = mb.ReadStatus("linux");
            object b;
            return linux != null && linux.TryGetValue("boot", out b) ? b as Dictionary<string, object> : null;
        }

        static FirmwareEntry LinuxEntry(Mailbox mb, BootInfo info)
        {
            var b = LinuxBoot(mb);
            object loader;
            if (info == null || b == null || !b.TryGetValue("linux_loader", out loader)) return null;
            return info.FindLoader(loader as string);
        }

        /// <summary>If the user asked in DualPair for Linux to keep Linux first and a Windows update
        /// moved Windows first, put Linux back first.</summary>
        void KeepLinuxFirst(Mailbox mb, Dictionary<string, object> notices)
        {
            var b = LinuxBoot(mb);
            object keep;
            if (b == null || !b.TryGetValue("keep_linux_first", out keep) || !(keep is bool) || !(bool)keep) return;
            var info = Boot();
            var linux = LinuxEntry(mb, info);
            if (linux == null || info.First == null || info.First.Id == linux.Id) return;
            if (BootSetter != null ? BootSetter(linux) : FirmwareBoot.PutFirst(linux))
            {
                var when = Protocol.Iso(DateTime.UtcNow);
                notices["boot_fixed"] = when;
                Protocol.WriteJsonFile(Path.Combine(opt.StateDir, "boot.json"), new Dictionary<string, object> { { "fixed_at", when } });
            }
        }

        // ------------------------------------------------------------------ status
        static Dictionary<string, string> Fingerprints(Dictionary<string, object> status, string section, string list, string key)
        {
            var map = new Dictionary<string, string>();
            object s, l;
            if (status == null || !status.TryGetValue(section, out s) || !(s is Dictionary<string, object>)) return map;
            if (!((Dictionary<string, object>)s).TryGetValue(list, out l) || !(l is object[])) return map;
            foreach (var o in (object[])l)
            {
                var d = o as Dictionary<string, object>;
                object k, f;
                if (d != null && d.TryGetValue(key, out k) && d.TryGetValue("fingerprint", out f) && k is string)
                    map[(string)k] = f as string;
            }
            return map;
        }

        static string Compare(string fp, Dictionary<string, string> other, bool known, string key)
        {
            if (!known) return "unknown";
            string o;
            if (!other.TryGetValue(key, out o)) return "windows_only";
            return o == fp ? "same" : "different";
        }

        /// <summary>Run one part of the status; if it fails, the others still run and the window shows why.</summary>
        static T Safe<T>(Func<T> f, T fallback, string section, Dictionary<string, object> errors)
        {
            try { return f(); }
            catch (Exception e) { errors[section] = e.GetType().Name + ": " + e.Message; return fallback; }
        }

        void WriteStatus(Mailbox mb, Dictionary<string, object> notices)
        {
            var errors = new Dictionary<string, object>();
            var devices = Safe(() => bt.Devices(), new List<Device>(), "bluetooth", errors);
            var nets = Safe(() => WifiNetworks(), null, "wifi", errors);
            if (nets == null && !errors.ContainsKey("wifi") && Wifi.LastError != null && WifiSource == null) errors["wifi"] = Wifi.LastError;
            var boot = Safe(() => Boot(), null, "boot", errors);
            string fixedAt = null;
            try { fixedAt = Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "boot.json"))["fixed_at"] as string; } catch (Exception) { }
            var fast = Safe(() => FastStartup.Enabled(), null, "power", errors);
            var rtcUtc = Safe(() => Clock.RtcUtc(), false, "clock", errors);
            var btAvailable = Safe(() => bt.Available(), false, "bluetooth", errors);

            var shared = new Dictionary<string, object> {
                { "dualpair", Protocol.Version }, { "system", "windows" }, { "version", Program.Version },
                { "written", Protocol.Iso(DateTime.UtcNow) },
                { "clock", new Dictionary<string, object> { { "rtc_utc", rtcUtc }, { "timezone", Clock.TimeZoneName() } } },
                { "bluetooth", new Dictionary<string, object> {
                    { "available", btAvailable },
                    { "devices", devices.Select(d => (object)new Dictionary<string, object> {
                        { "adapter", d.Adapter }, { "address", d.Address }, { "name", d.Name }, { "kind", d.Kind },
                        { "fingerprint", d.Fingerprint() },
                        { "paired_at", d.PairedAt.HasValue ? Protocol.Iso(d.PairedAt.Value) : null } }).ToArray() } } },
                { "wifi", new Dictionary<string, object> {
                    { "available", nets != null },
                    { "networks", (nets ?? new List<WifiNetwork>()).Select(n => (object)new Dictionary<string, object> {
                        { "ssid", n.Ssid }, { "security", n.Security }, { "hidden", n.Hidden }, { "fingerprint", n.Fingerprint() } }).ToArray() } } },
                { "power", new Dictionary<string, object> { { "fast_startup", fast } } },
                { "boot", new Dictionary<string, object> {
                    { "first_loader", boot != null && boot.First != null ? boot.First.Path : null }, { "fixed_at", fixedAt } } } };
            try { mb.WriteStatus(shared); } catch (Exception) { }

            var linux = Safe(() => mb.ReadStatus("linux"), null, "esp", errors);
            var linuxBt = Fingerprints(linux, "bluetooth", "devices", "address");
            var linuxWifi = Fingerprints(linux, "wifi", "networks", "ssid");
            var linuxHasWifi = linux != null && linux.ContainsKey("wifi");
            var messages = Safe(() => mb.List("windows", false), new List<Message>(), "esp", errors);
            var pending = messages.Where(m => m.Type == "keys").Select(m => (object)new Dictionary<string, object> {
                { "id", m.Id }, { "created", Protocol.Iso(m.Created) },
                { "devices", m.Devices.Select(d => (object)new Dictionary<string, object> {
                    { "address", d.Address }, { "name", d.Name }, { "kind", d.Kind },
                    { "paired_in_windows", devices.Any(w => w.Address == d.Address) },
                    { "same", devices.Any(w => w.Address == d.Address && w.Fingerprint() == d.Fingerprint()) } }).ToArray() } }).ToArray();
            var pendingWifi = messages.Where(m => m.Type == "wifi").Select(m => (object)new Dictionary<string, object> {
                { "id", m.Id }, { "created", Protocol.Iso(m.Created) },
                { "networks", m.Networks.Select(n => (object)new Dictionary<string, object> {
                    { "ssid", n.Ssid }, { "security", n.Security },
                    { "state", nets == null ? "unknown" : (!nets.Any(w => w.Ssid == n.Ssid) ? "new"
                               : (nets.Any(w => w.Ssid == n.Ssid && w.Fingerprint() == n.Fingerprint()) ? "same" : "different")) } }).ToArray() } }).ToArray();
            var lb = LinuxBoot(mb);
            var linuxEntry = LinuxEntry(mb, boot);
            var keepObj = lb != null && lb.ContainsKey("keep_linux_first") ? lb["keep_linux_first"] : null;

            var local = new Dictionary<string, object>(shared) {
                { "esp", mb.Folder != null },
                { "errors", errors },
                { "wifi_source", WifiSource == null ? Wifi.LastSource : "test" },
                { "linux", linux },
                { "pending", pending },
                { "pending_wifi", pendingWifi },
                { "device_states", devices.Select(d => (object)new Dictionary<string, object> {
                    { "address", d.Address }, { "state", Compare(d.Fingerprint(), linuxBt, linux != null, d.Address) } }).ToArray() },
                { "wifi_states", (nets ?? new List<WifiNetwork>()).Select(n => (object)new Dictionary<string, object> {
                    { "ssid", n.Ssid }, { "state", Compare(n.Fingerprint(), linuxWifi, linuxHasWifi, n.Ssid) } }).ToArray() },
                { "boot_state", new Dictionary<string, object> {
                    { "available", boot != null },
                    { "first_loader", boot != null && boot.First != null ? boot.First.Path : null },
                    { "first_is_windows", boot != null && boot.First != null && boot.First.Path != null &&
                                          boot.First.Path.IndexOf(@"\Microsoft\", StringComparison.OrdinalIgnoreCase) >= 0 },
                    { "linux_loader", linuxEntry != null ? linuxEntry.Path : null },
                    { "first_is_linux", linuxEntry != null && boot.First != null && boot.First.Id == linuxEntry.Id },
                    { "keep_linux_first", keepObj is bool && (bool)keepObj },
                    { "fixed_at", fixedAt } } } };
            Protocol.WriteJsonFile(Path.Combine(opt.StateDir, "status.json"), local);

            // logon notices: keep earlier ones not shown yet
            var notify = new Dictionary<string, object>();
            try
            {
                foreach (var kv in Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "pending.json")))
                    if (kv.Key != "keys_from_linux" && kv.Key != "devices" && kv.Key != "wifi_from_linux" && kv.Key != "networks") notify[kv.Key] = kv.Value;
            }
            catch (Exception) { }
            foreach (var kv in notices) notify[kv.Key] = kv.Value;
            if (pending.Length > 0)
            {
                var last = (Dictionary<string, object>)pending.Last();
                notify["keys_from_linux"] = last["id"];
                notify["devices"] = ((object[])last["devices"]).Length;
            }
            if (pendingWifi.Length > 0)
            {
                var last = (Dictionary<string, object>)pendingWifi.Last();
                notify["wifi_from_linux"] = last["id"];
                notify["networks"] = ((object[])last["networks"]).Length;
            }
            Protocol.WriteJsonFile(Path.Combine(opt.StateDir, "pending.json"), notify);
        }
    }
}
