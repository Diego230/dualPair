// The DualPair folder on the EFI System Partition, shared with DualPair for Linux.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;

namespace DualPair
{
    public sealed class Mailbox : IDisposable
    {
        public string Folder { get; private set; }     // ...\EFI\DualPair, or null if the ESP is not reachable
        string mountedLetter;

        Mailbox() { }

        /// <summary>Open the folder. With an override (tests) that folder is used; otherwise the ESP
        /// is mounted on a free drive letter with mountvol /S and unmounted on Dispose.</summary>
        public static Mailbox Open(string overrideFolder)
        {
            var mb = new Mailbox();
            if (!string.IsNullOrEmpty(overrideFolder))
            {
                Directory.CreateDirectory(overrideFolder);
                mb.Folder = overrideFolder;
                return mb;
            }
            var used = new HashSet<char>(DriveInfo.GetDrives().Select(d => char.ToUpperInvariant(d.Name[0])));
            char letter = '\0';
            for (char c = 'Z'; c >= 'D'; c--) if (!used.Contains(c)) { letter = c; break; }
            if (letter == '\0') return mb;
            if (Run("mountvol.exe", letter + ": /S") != 0) return mb;
            mb.mountedLetter = letter + ":";
            var folder = Path.Combine(letter + @":\", "EFI", "DualPair");
            try { Directory.CreateDirectory(folder); mb.Folder = folder; }
            catch (Exception) { mb.Dispose(); }
            return mb;
        }

        static int Run(string exe, string args)
        {
            var psi = new ProcessStartInfo(exe, args) { UseShellExecute = false, CreateNoWindow = true,
                                                        RedirectStandardOutput = true, RedirectStandardError = true };
            try
            {
                using (var p = Process.Start(psi))
                {
                    p.WaitForExit(30000);
                    return p.HasExited ? p.ExitCode : -1;
                }
            }
            catch (Exception) { return -1; }
        }

        public void Dispose()
        {
            if (mountedLetter != null) { Run("mountvol.exe", mountedLetter + " /D"); mountedLetter = null; }
        }

        string Box(string to) { return Path.Combine(Folder, "to-" + to); }

        // ------------------------------------------------------------------ status files
        public Dictionary<string, object> ReadStatus(string system)
        {
            if (Folder == null) return null;
            try
            {
                var d = Protocol.ReadJsonFile(Path.Combine(Folder, "status-" + system + ".json"));
                object v, s;
                if (!d.TryGetValue("dualpair", out v) || !(v is int) || (int)v != Protocol.Version) return null;
                if (!d.TryGetValue("system", out s) || (s as string) != system) return null;
                return d;
            }
            catch (Exception) { return null; }
        }

        public void WriteStatus(object status)
        {
            if (Folder == null) return;
            Protocol.WriteJsonFile(Path.Combine(Folder, "status-windows.json"), status);
        }

        // ------------------------------------------------------------------ messages
        /// <summary>Valid messages for 'to', oldest first. Invalid or expired files are deleted
        /// when deleteInvalid is set (only the receiver does that).</summary>
        public List<Message> List(string to, bool deleteInvalid)
        {
            var result = new List<Message>();
            if (Folder == null || !Directory.Exists(Box(to))) return result;
            var sender = to == "windows" ? "linux" : "windows";
            var now = Protocol.UtcNow();
            foreach (var path in Directory.GetFiles(Box(to), "*.json").OrderBy(p => p, StringComparer.Ordinal))
            {
                try { result.Add(Protocol.Validate(Protocol.ReadJsonFile(path), sender, Path.GetFileName(path), now)); }
                catch (Exception)
                {
                    if (deleteInvalid) { try { File.Delete(path); } catch (Exception) { } }
                }
            }
            return result;
        }

        public string Send(string to, string type, object payload)
        {
            if (Folder == null) throw new IOException(Strings.T("err.no_esp"));
            foreach (var old in List(to, false).Where(m => m.Type == type)) Delete(to, old.Id);  // keys never pile up
            string id;
            var msg = Protocol.NewMessage(type, to == "linux" ? "windows" : "linux", payload, out id);
            Protocol.WriteJsonFile(Path.Combine(Box(to), id + ".json"), msg);
            return id;
        }

        public void Delete(string to, string id)
        {
            if (Folder == null || !Protocol.IsId(id)) return;
            var path = Path.Combine(Box(to), id + ".json");
            if (File.Exists(path)) File.Delete(path);
        }
    }
}
