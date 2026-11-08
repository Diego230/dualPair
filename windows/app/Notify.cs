// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Diego Buono
// At logon (shortcut in the common Startup folder, runs without administrator rights): tell the
// user, once, what came from Linux or what DualPair did at startup. Reads pending.json only.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

namespace DualPair
{
    public static class Notify
    {
        public static void Run(Options opt)
        {
            Dictionary<string, object> p;
            try { p = Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "pending.json")); }
            catch (Exception) { return; }
            var seenFile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DualPair", "notified.txt");
            var seen = new HashSet<string>(File.Exists(seenFile) ? File.ReadAllLines(seenFile) : new string[0]);
            var shown = new List<string>();
            Func<string, bool> fresh = marker =>
            {
                if (seen.Contains(marker)) return false;
                shown.Add(marker);
                return true;
            };
            object v, n;
            var openApp = false;

            if (p.TryGetValue("clock_applied", out v) && v is bool && fresh("clock=" + v))
                Info(Strings.T((bool)v ? "notify.clock_utc" : "notify.clock_local"));
            if (p.TryGetValue("fast_startup_applied", out v) && v is bool && fresh("fast=" + v))
                Info(Strings.T((bool)v ? "notify.fast_on" : "notify.fast_off"));
            if (p.TryGetValue("boot_fixed", out v) && v is string && fresh("boot=" + v))
                Info(Strings.T("notify.boot_fixed"));
            if (p.TryGetValue("keys_from_linux", out v) && v is string && fresh("keys=" + v))
            {
                p.TryGetValue("devices", out n);
                openApp |= Ask(Strings.T("notify.keys", n is int ? (int)n : 0));
            }
            if (p.TryGetValue("wifi_from_linux", out v) && v is string && fresh("wifi=" + v))
            {
                p.TryGetValue("networks", out n);
                openApp |= Ask(Strings.T("notify.wifi", n is int ? (int)n : 0));
            }

            if (shown.Count > 0)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(seenFile));
                File.WriteAllLines(seenFile, seen.Concat(shown).Reverse().Take(50).Reverse());
            }
            if (openApp)
                Process.Start(new ProcessStartInfo(Process.GetCurrentProcess().MainModule.FileName) { UseShellExecute = true });
        }

        static void Info(string text)
        {
            MessageBox.Show(text, "DualPair", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        static bool Ask(string text)
        {
            return MessageBox.Show(text, "DualPair", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes;
        }
    }
}
