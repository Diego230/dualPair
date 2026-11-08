// At logon (shortcut in the common Startup folder, runs without administrator rights): if Linux
// sent keys or changed the clock, say so once. Reads %ProgramData%\DualPair\pending.json only.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
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
            var seen = File.Exists(seenFile) ? File.ReadAllText(seenFile).Trim() : "";

            object keys, n, clock;
            p.TryGetValue("keys_from_linux", out keys);
            p.TryGetValue("devices", out n);
            p.TryGetValue("clock_applied", out clock);
            var marker = (keys as string ?? "") + "|" + (clock is bool ? clock.ToString() : "");
            if (marker == seen || marker == "|") return;
            Directory.CreateDirectory(Path.GetDirectoryName(seenFile));
            File.WriteAllText(seenFile, marker);

            if (clock is bool && !(seen.EndsWith("|" + clock)))
                MessageBox.Show(Strings.T((bool)clock ? "notify.clock_utc" : "notify.clock_local"), "DualPair",
                                MessageBoxButtons.OK, MessageBoxIcon.Information);
            if (keys is string && !seen.StartsWith((string)keys))
            {
                var answer = MessageBox.Show(Strings.T("notify.keys", n is int ? (int)n : 0), "DualPair",
                                             MessageBoxButtons.YesNo, MessageBoxIcon.Question);
                if (answer == DialogResult.Yes)
                    Process.Start(new ProcessStartInfo(Process.GetCurrentProcess().MainModule.FileName) { UseShellExecute = true });
            }
        }
    }
}
