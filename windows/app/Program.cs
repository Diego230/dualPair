// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Diego Buono
// DualPair for Windows.
//
//   DualPair.exe                     the window (asks for administrator rights)
//   DualPair.exe --notify            at logon: tells the user if Linux sent something
//   DualPair.exe --agent             SYSTEM task (installed by --install)
//   DualPair.exe --install|--uninstall
// Command line, as administrator (also used by the tests):
//   --status [--json]  --set-clock utc|local  --resync
//   --run <status|export|import|discard|restore> [--message ID] [--address MAC]...   (asks the task;
//       with DUALPAIR_INPROC=1 runs in this process)
//   --mailbox-dir DIR  --registry-params PATH  --state-dir DIR    (tests only)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Windows.Forms;

namespace DualPair
{
    public static class Program
    {
        public const string Version = "0.4.1";

        public static bool IsAdmin()
        {
            return new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator);
        }

        [DllImport("kernel32.dll")] static extern bool AttachConsole(int processId);

        static string Arg(List<string> args, string name)
        {
            var i = args.IndexOf(name);
            return i >= 0 && i + 1 < args.Count ? args[i + 1] : null;
        }

        [STAThread]
        static int Main(string[] argv)
        {
            var args = argv.ToList();
            var opt = new Options();
            if (Arg(args, "--state-dir") != null) opt.StateDir = Arg(args, "--state-dir");
            opt.MailboxDir = Arg(args, "--mailbox-dir");
            opt.ParamsPath = Arg(args, "--registry-params");
            if (Arg(args, "--clock-key") != null) Clock.KeyPath = Arg(args, "--clock-key");
            if (Arg(args, "--power-key") != null) FastStartup.KeyPath = Arg(args, "--power-key");
            var json = args.Contains("--json");

            try
            {
                if (args.Contains("--agent")) { new Agent(opt).RunTask(); return 0; }
                if (args.Contains("--install")) return Install.Setup(Process.GetCurrentProcess().MainModule.FileName, opt);
                if (args.Contains("--uninstall")) return Install.Remove(opt);
                if (args.Contains("--notify")) { Notify.Run(opt); return 0; }

                if (args.Contains("--status") || args.Contains("--set-clock") || args.Contains("--resync") || args.Contains("--run"))
                {
                    // a windowed program has no console: use the terminal it was started from, if any
                    try { if (AttachConsole(-1)) { Console.SetOut(new System.IO.StreamWriter(Console.OpenStandardOutput()) { AutoFlush = true }); } }
                    catch (Exception) { }
                    if (!IsAdmin()) { Console.Error.WriteLine("Run as administrator."); return 1; }
                    var result = new Dictionary<string, object>();
                    var clock = Arg(args, "--set-clock");
                    if (clock == "utc" || clock == "local") Clock.SetRtcUtc(clock == "utc");
                    else if (clock != null) { Console.Error.WriteLine("--set-clock utc|local"); return 2; }
                    if (clock != null || args.Contains("--resync")) result["synced"] = Clock.Resync();
                    var op = Arg(args, "--run");
                    if (op != null)
                    {
                        var req = new Dictionary<string, object> { { "op", op } };
                        if (Arg(args, "--message") != null) req["message_id"] = Arg(args, "--message");
                        var addrs = args.Select((a, i) => a == "--address" && i + 1 < args.Count ? args[i + 1] : null).Where(a => a != null).ToArray();
                        if (addrs.Length > 0) req["addresses"] = addrs.Cast<object>().ToArray();
                        result["result"] = Install.Ask(opt, req);
                    }
                    result["rtc_utc"] = Clock.RtcUtc();
                    result["fast_startup"] = FastStartup.Enabled();
                    if (args.Contains("--status"))
                    {
                        var boot = FirmwareBoot.Read();   // read only
                        result["boot"] = boot == null ? null : new Dictionary<string, object> {
                            { "first", boot.First != null ? boot.First.Path : null }, { "order", boot.Order.Count },
                            { "entries", boot.Entries.Values.Select(e => (object)(e.Id + " " + e.Path)).ToArray() } };
                    }
                    result["timezone"] = Clock.TimeZoneName();
                    result["version"] = Version;
                    Console.WriteLine(json ? Protocol.Serializer().Serialize(result)
                                           : Strings.T(Clock.RtcUtc() ? "clock.utc" : "clock.local"));
                    object r;
                    return result.TryGetValue("result", out r) && r is Dictionary<string, object> && ((Dictionary<string, object>)r).ContainsKey("error") ? 3 : 0;
                }

                // the window
                if (!IsAdmin())
                {
                    try
                    {
                        Process.Start(new ProcessStartInfo(Process.GetCurrentProcess().MainModule.FileName) { UseShellExecute = true, Verb = "runas" });
                    }
                    catch (System.ComponentModel.Win32Exception) { }   // the user said no
                    return 0;
                }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new MainForm(opt));
                return 0;
            }
            catch (Exception e)
            {
                if (args.Contains("--agent") || args.Contains("--install") || args.Contains("--uninstall") || json)
                {
                    Console.Error.WriteLine(e.ToString());
                    return 10;
                }
                MessageBox.Show(e.Message, "DualPair", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 10;
            }
        }
    }
}
