// The privileged part. Runs as SYSTEM from the "DualPair\Agent" scheduled task: at every Windows
// start, and on demand when the window asks for something only SYSTEM can do (the Bluetooth keys).
//
// The window (administrator) talks to it through files in %ProgramData%\DualPair, a folder only
// SYSTEM and administrators can write:
//   requests\<id>.json   {"op": "status"|"export"|"import"|"discard"|"restore", ...}
//   results\<id>.json    the answer
//   status.json          everything the window shows (no keys)
//   pending.json         what to tell the user at logon (readable by everyone, no keys)
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
        readonly Options opt;
        readonly BluetoothStore bt;

        public Agent(Options opt)
        {
            this.opt = opt;
            bt = new BluetoothStore(opt.ParamsPath, opt.StateDir);
        }

        string RequestsDir { get { return Path.Combine(opt.StateDir, "requests"); } }
        string ResultsDir { get { return Path.Combine(opt.StateDir, "results"); } }

        /// <summary>Task entry point: answer queued requests, apply clock requests from Linux,
        /// refresh the status files.</summary>
        public void RunTask()
        {
            using (var mb = Mailbox.Open(opt.MailboxDir))
            {
                var clockApplied = ApplyClockRequests(mb);
                if (Directory.Exists(RequestsDir))
                    foreach (var path in Directory.GetFiles(RequestsDir, "*.json"))
                    {
                        var id = Path.GetFileNameWithoutExtension(path);
                        Dictionary<string, object> result;
                        try { result = Handle(Protocol.ReadJsonFile(path), mb); }
                        catch (Exception e) { result = new Dictionary<string, object> { { "error", e.Message } }; }
                        File.Delete(path);
                        if (Guid.TryParse(id, out Guid _)) Protocol.WriteJsonFile(Path.Combine(ResultsDir, id + ".json"), result);
                    }
                WriteStatus(mb, clockApplied);
            }
        }

        /// <summary>Run one operation directly (command line, tests).</summary>
        public Dictionary<string, object> RunNow(Dictionary<string, object> request)
        {
            using (var mb = Mailbox.Open(opt.MailboxDir))
            {
                var result = Handle(request, mb);
                WriteStatus(mb, null);
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
                    return new Dictionary<string, object> { { "ok", true } };
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
                    var msg = FindMessage(mb, req);
                    if (msg == null) return Error("err.unknown_message");
                    var wanted = Addresses(req);
                    var chosen = msg.Devices.Where(d => wanted == null || wanted.Contains(d.Address)).ToList();
                    var results = bt.Import(chosen);
                    mb.Delete("windows", msg.Id);      // handled: keys do not stay on the ESP
                    return new Dictionary<string, object> { { "ok", true }, { "results", results.Select(r => (object)new Dictionary<string, object> {
                        { "address", r.Address }, { "name", r.Name }, { "result", r.Result } }).ToArray() } };
                }
                case "discard":
                {
                    var msg = FindMessage(mb, req);
                    if (msg != null) mb.Delete("windows", msg.Id);
                    return new Dictionary<string, object> { { "ok", true } };
                }
                case "restore":
                    return bt.RestoreLast() ? new Dictionary<string, object> { { "ok", true } } : Error("err.no_backups");
                default:
                    return Error("err.unknown_request");
            }
        }

        static Dictionary<string, object> Error(string code)
        {
            return new Dictionary<string, object> { { "error", Strings.T(code) }, { "code", code } };
        }

        static Message FindMessage(Mailbox mb, Dictionary<string, object> req)
        {
            object id;
            req.TryGetValue("message_id", out id);
            return mb.List("windows", false).FirstOrDefault(m => m.Type == "keys" && m.Id == (id as string));
        }

        static HashSet<string> Addresses(Dictionary<string, object> req)
        {
            object a;
            if (!req.TryGetValue("addresses", out a) || !(a is object[])) return null;
            return new HashSet<string>(((object[])a).OfType<string>().Where(Protocol.IsMac));
        }

        /// <summary>"set_clock" from Linux: the user already chose it there, so it is applied
        /// without asking again. Returns the applied value, or null.</summary>
        bool? ApplyClockRequests(Mailbox mb)
        {
            bool? applied = null;
            foreach (var m in mb.List("windows", true).Where(m => m.Type == "set_clock"))
            {
                Clock.SetRtcUtc(m.WindowsUtc);
                mb.Delete("windows", m.Id);
                applied = m.WindowsUtc;
            }
            if (applied.HasValue && opt.MailboxDir == null) Clock.Resync(3);   // network may not be up yet at boot
            return applied;
        }

        // ------------------------------------------------------------------ status
        void WriteStatus(Mailbox mb, bool? clockApplied)
        {
            var devices = bt.Devices();
            var rtcUtc = Clock.RtcUtc();
            var tz = Clock.TimeZoneName();
            var shared = new Dictionary<string, object> {
                { "dualpair", Protocol.Version }, { "system", "windows" }, { "version", Program.Version },
                { "written", Protocol.Iso(DateTime.UtcNow) },
                { "clock", new Dictionary<string, object> { { "rtc_utc", rtcUtc }, { "timezone", tz } } },
                { "bluetooth", new Dictionary<string, object> {
                    { "available", bt.Available() },
                    { "devices", devices.Select(d => (object)new Dictionary<string, object> {
                        { "adapter", d.Adapter }, { "address", d.Address }, { "name", d.Name }, { "kind", d.Kind },
                        { "fingerprint", d.Fingerprint() },
                        { "paired_at", d.PairedAt.HasValue ? Protocol.Iso(d.PairedAt.Value) : null } }).ToArray() } } } };
            try { mb.WriteStatus(shared); } catch (Exception) { }

            var linux = mb.ReadStatus("linux");
            var linuxFp = LinuxFingerprints(linux);
            var pending = mb.List("windows", false).Where(m => m.Type == "keys").Select(m => (object)new Dictionary<string, object> {
                { "id", m.Id }, { "created", Protocol.Iso(m.Created) },
                { "devices", m.Devices.Select(d => (object)new Dictionary<string, object> {
                    { "address", d.Address }, { "name", d.Name }, { "kind", d.Kind },
                    { "paired_in_windows", devices.Any(w => w.Address == d.Address) },
                    { "same", devices.Any(w => w.Address == d.Address && w.Fingerprint() == d.Fingerprint()) } }).ToArray() } }).ToArray();

            var local = new Dictionary<string, object>(shared) {
                { "esp", mb.Folder != null },
                { "linux", linux },
                { "pending", pending },
                { "device_states", devices.Select(d => (object)new Dictionary<string, object> {
                    { "address", d.Address }, { "state", StateVsLinux(d, linuxFp, linux != null) } }).ToArray() } };
            Protocol.WriteJsonFile(Path.Combine(opt.StateDir, "status.json"), local);

            var notify = new Dictionary<string, object> {
                { "keys_from_linux", pending.Length > 0 ? ((Dictionary<string, object>)pending.Last())["id"] : null },
                { "devices", pending.Length > 0 ? ((object[])((Dictionary<string, object>)pending.Last())["devices"]).Length : 0 } };
            if (clockApplied.HasValue) notify["clock_applied"] = clockApplied.Value;
            else
            {   // keep an earlier, not yet shown clock notice
                try
                {
                    var old = Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "pending.json"));
                    object c;
                    if (old.TryGetValue("clock_applied", out c)) notify["clock_applied"] = c;
                }
                catch (Exception) { }
            }
            Protocol.WriteJsonFile(Path.Combine(opt.StateDir, "pending.json"), notify);
        }

        static Dictionary<string, string> LinuxFingerprints(Dictionary<string, object> linux)
        {
            var map = new Dictionary<string, string>();
            if (linux == null) return map;
            object bt, devs;
            if (!linux.TryGetValue("bluetooth", out bt) || !(bt is Dictionary<string, object>)) return map;
            if (!((Dictionary<string, object>)bt).TryGetValue("devices", out devs) || !(devs is object[])) return map;
            foreach (var o in (object[])devs)
            {
                var d = o as Dictionary<string, object>;
                object a, f;
                if (d != null && d.TryGetValue("address", out a) && d.TryGetValue("fingerprint", out f) && Protocol.IsMac(a as string))
                    map[(string)a] = f as string;
            }
            return map;
        }

        static string StateVsLinux(Device d, Dictionary<string, string> linuxFp, bool linuxKnown)
        {
            if (!linuxKnown) return "unknown";
            string fp;
            if (!linuxFp.TryGetValue(d.Address, out fp)) return "windows_only";
            return fp == d.Fingerprint() ? "same" : "different";
        }
    }
}
