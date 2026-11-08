// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Diego Buono
// Windows settings that matter for dual boot: Fast Startup, firmware boot order, Wi-Fi profiles.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Xml;
using Microsoft.Win32;

namespace DualPair
{
    static class Exec
    {
        public static int Run(string exe, string args, out string output, int timeoutMs = 60000)
        {
            var psi = new ProcessStartInfo(exe, args) { UseShellExecute = false, CreateNoWindow = true,
                                                        RedirectStandardOutput = true, RedirectStandardError = true };
            try
            {
                using (var p = Process.Start(psi))
                {
                    var stdout = p.StandardOutput.ReadToEndAsync();
                    var stderr = p.StandardError.ReadToEndAsync();
                    if (!p.WaitForExit(timeoutMs)) { try { p.Kill(); } catch (Exception) { } output = ""; return -1; }
                    output = stdout.Result + stderr.Result;
                    return p.ExitCode;
                }
            }
            catch (Exception e) { output = e.Message; return -1; }
        }
    }

    // ------------------------------------------------------------------ Fast Startup
    public static class FastStartup
    {
        public const string DefaultKey = @"SYSTEM\CurrentControlSet\Control\Session Manager\Power";
        public static string KeyPath = DefaultKey;   // tests point this elsewhere

        /// <summary>true/false, or null if Windows has no setting (then it depends on hibernation).</summary>
        public static bool? Enabled()
        {
            using (var k = Registry.LocalMachine.OpenSubKey(KeyPath))
            {
                var v = k == null ? null : k.GetValue("HiberbootEnabled");
                if (v is int) return (int)v != 0;
                return null;
            }
        }

        public static void Set(bool enabled)
        {
            using (var k = Registry.LocalMachine.CreateSubKey(KeyPath))
                k.SetValue("HiberbootEnabled", enabled ? 1 : 0, RegistryValueKind.DWord);
        }
    }

    // ------------------------------------------------------------------ firmware boot order
    public class FirmwareEntry
    {
        public string Id;      // {bootmgr} or {guid}
        public string Path;    // \EFI\...\x.efi, or null
    }

    public class BootInfo
    {
        public List<string> Order = new List<string>();
        public Dictionary<string, FirmwareEntry> Entries = new Dictionary<string, FirmwareEntry>(StringComparer.OrdinalIgnoreCase);
        public FirmwareEntry First { get { return Order.Count > 0 && Entries.ContainsKey(Order[0]) ? Entries[Order[0]] : null; } }

        public FirmwareEntry FindLoader(string loader)
        {
            if (string.IsNullOrEmpty(loader)) return null;
            return Entries.Values.FirstOrDefault(e => e.Path != null && string.Equals(e.Path, loader, StringComparison.OrdinalIgnoreCase));
        }
    }

    public static class FirmwareBoot
    {
        static readonly Regex Brace = new Regex(@"\{[^}\s]+\}");
        static readonly Regex Efi = new Regex(@"\\EFI\\\S+?\.efi", RegexOptions.IgnoreCase);

        /// <summary>Parse `bcdedit /enum firmware`. Field names are translated into the Windows
        /// language, so only the layout is used: blocks separated by blank lines, the first {id}
        /// of a block is its identifier, a \EFI\...efi value is its loader, and in the
        /// {fwbootmgr} block the first field made only of {ids} is the display order.</summary>
        public static BootInfo Parse(string text)
        {
            var info = new BootInfo();
            var blocks = Regex.Split(text.Replace("\r\n", "\n"), @"\n\s*\n");
            foreach (var block in blocks)
            {
                var lines = block.Split('\n').Where(l => l.Trim().Length > 0 && !Regex.IsMatch(l.Trim(), "^-+$")).ToList();
                if (lines.Count < 2) continue;
                // fields: a line starting with a non-space starts a field; indented lines continue it
                var fields = new List<List<string>>();
                foreach (var l in lines.Skip(1))
                {
                    if (!char.IsWhiteSpace(l[0])) fields.Add(new List<string> { l });
                    else if (fields.Count > 0) fields[fields.Count - 1].Add(l);
                }
                if (fields.Count == 0) continue;
                var idMatch = Brace.Match(string.Join(" ", fields[0]));
                if (!idMatch.Success) continue;
                var id = idMatch.Value;
                if (string.Equals(id, "{fwbootmgr}", StringComparison.OrdinalIgnoreCase))
                {
                    foreach (var f in fields.Skip(1))
                    {
                        // the first line ends with an {id} (the field name may be several words in some
                        // languages); every continuation line is exactly one {id}
                        var first = Regex.Match(f[0], @"(\{[^}\s]+\})\s*$");
                        var rest = f.Skip(1).Select(l => l.Trim()).ToList();
                        if (first.Success && rest.All(v => Brace.IsMatch(v) && Brace.Match(v).Value == v))
                        {
                            info.Order = new[] { first.Groups[1].Value }.Concat(rest).ToList();
                            break;
                        }
                    }
                    continue;
                }
                var path = Efi.Match(block);
                info.Entries[id] = new FirmwareEntry { Id = id, Path = path.Success ? path.Value : null };
            }
            return info;
        }

        public static BootInfo Read()
        {
            string output;
            if (Exec.Run("bcdedit.exe", "/enum firmware", out output) != 0) return null;
            var info = Parse(output);
            return info.Order.Count > 0 ? info : null;
        }

        public static bool PutFirst(FirmwareEntry e)
        {
            string output;
            return Exec.Run("bcdedit.exe", "/set {fwbootmgr} displayorder " + e.Id + " /addfirst", out output) == 0;
        }
    }

    // ------------------------------------------------------------------ Wi-Fi profiles
    public static class Wifi
    {
        const string Ns = "http://www.microsoft.com/networking/WLAN/profile/v1";

        public static string LastError;   // why the last Export found nothing (shown in the window)

        // ---- native WLAN API: profiles come back as XML in memory, nothing written to disk
        [DllImport("wlanapi.dll")] static extern uint WlanOpenHandle(uint clientVersion, IntPtr reserved, out uint negotiated, out IntPtr handle);
        [DllImport("wlanapi.dll")] static extern uint WlanCloseHandle(IntPtr handle, IntPtr reserved);
        [DllImport("wlanapi.dll")] static extern uint WlanEnumInterfaces(IntPtr handle, IntPtr reserved, out IntPtr list);
        [DllImport("wlanapi.dll")] static extern uint WlanGetProfileList(IntPtr handle, ref Guid iface, IntPtr reserved, out IntPtr list);
        [DllImport("wlanapi.dll", CharSet = CharSet.Unicode)]
        static extern uint WlanGetProfile(IntPtr handle, ref Guid iface, string name, IntPtr reserved, out IntPtr xml, ref uint flags, out uint access);
        [DllImport("wlanapi.dll", CharSet = CharSet.Unicode)]
        static extern uint WlanSetProfile(IntPtr handle, ref Guid iface, uint flags, string xml, string security, bool overwrite, IntPtr reserved, out uint reason);
        [DllImport("wlanapi.dll")] static extern void WlanFreeMemory(IntPtr p);
        const uint WLAN_PROFILE_GET_PLAINTEXT_KEY = 4;
        const int InterfaceInfoSize = 16 + 512 + 4;   // GUID, WCHAR[256], WLAN_INTERFACE_STATE
        const int ProfileInfoSize = 512 + 4;          // WCHAR[256], DWORD flags

        static List<Guid> Interfaces(IntPtr h)
        {
            var result = new List<Guid>();
            IntPtr list;
            var rc = WlanEnumInterfaces(h, IntPtr.Zero, out list);
            if (rc != 0) throw new InvalidOperationException("WlanEnumInterfaces: error " + rc);
            try
            {
                var n = Marshal.ReadInt32(list);
                for (int i = 0; i < n; i++)
                {
                    var bytes = new byte[16];
                    Marshal.Copy(IntPtr.Add(list, 8 + i * InterfaceInfoSize), bytes, 0, 16);
                    result.Add(new Guid(bytes));
                }
            }
            finally { WlanFreeMemory(list); }
            return result;
        }

        /// <summary>Saved networks with their passwords (open, WPA/WPA2/WPA3-Personal only), or null
        /// if they cannot be read (LastError says why). Needs administrator or SYSTEM rights for the
        /// passwords; uses the WLAN API, and netsh only if that is not available.</summary>
        public static string LastSource;  // "api" or "netsh" (diagnostics)

        public static List<WifiNetwork> Export(string workDir)
        {
            // The WLAN API keeps passwords in memory only. It is not testable on the CI machines (no
            // Wi-Fi there), so if it finds nothing, netsh (known to work) is tried as well.
            var viaApi = ExportApi(workDir);
            if (viaApi != null && viaApi.Count > 0) { LastSource = "api"; return viaApi; }
            if (LastError == "wlan_service" || LastError == "no_adapter") { LastSource = "api"; return null; }
            var apiError = LastError;
            LastError = null;
            var viaNetsh = ExportNetsh(workDir);
            LastSource = "netsh";
            if (viaNetsh == null && apiError != null) LastError = apiError + "; " + LastError;
            return viaNetsh ?? viaApi;
        }

        static List<WifiNetwork> ExportApi(string workDir)
        {
            LastError = null;
            IntPtr h = IntPtr.Zero;
            try
            {
                uint version;
                var rc = WlanOpenHandle(2, IntPtr.Zero, out version, out h);
                if (rc == 1062) { LastError = "wlan_service"; return null; }        // WLAN AutoConfig not running: no Wi-Fi
                if (rc != 0) throw new InvalidOperationException("WlanOpenHandle: error " + rc);
                var result = new List<WifiNetwork>();
                var ifaces = Interfaces(h);
                if (ifaces.Count == 0) { LastError = "no_adapter"; return null; }
                foreach (var g in ifaces)
                {
                    var iface = g;
                    IntPtr plist;
                    rc = WlanGetProfileList(h, ref iface, IntPtr.Zero, out plist);
                    if (rc != 0) throw new InvalidOperationException("WlanGetProfileList: error " + rc);
                    var names = new List<string>();
                    try
                    {
                        var n = Marshal.ReadInt32(plist);
                        for (int i = 0; i < n; i++) names.Add(Marshal.PtrToStringUni(IntPtr.Add(plist, 8 + i * ProfileInfoSize)));
                    }
                    finally { WlanFreeMemory(plist); }
                    foreach (var name in names)
                    {
                        IntPtr xml;
                        uint flags = WLAN_PROFILE_GET_PLAINTEXT_KEY, access;
                        if (WlanGetProfile(h, ref iface, name, IntPtr.Zero, out xml, ref flags, out access) != 0) continue;
                        string text;
                        try { text = Marshal.PtrToStringUni(xml); } finally { WlanFreeMemory(xml); }
                        var net = ParseProfile(text);
                        if (net != null && !result.Any(x => x.Ssid == net.Ssid)) result.Add(net);
                    }
                }
                return result;
            }
            catch (Exception e) when (e is DllNotFoundException || e is EntryPointNotFoundException)
            {
                LastError = "no WLAN API";
                return null;
            }
            catch (Exception e)
            {
                LastError = e.Message;
                return null;
            }
            finally { if (h != IntPtr.Zero) WlanCloseHandle(h, IntPtr.Zero); }
        }

        static List<WifiNetwork> ExportNetsh(string workDir)
        {
            var dir = Path.Combine(workDir, "wifi-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            try
            {
                string output;
                var rc = Exec.Run("netsh.exe", "wlan export profile key=clear folder=\"" + dir + "\"", out output);
                var result = new List<WifiNetwork>();
                foreach (var f in Directory.GetFiles(dir, "*.xml"))   // use whatever was exported, even if netsh reported an error
                {
                    var n = ParseProfile(File.ReadAllText(f));
                    if (n != null && !result.Any(x => x.Ssid == n.Ssid)) result.Add(n);
                }
                if (result.Count == 0 && rc != 0)
                {
                    LastError = "netsh: " + string.Join(" ", output.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries).Take(2));
                    return null;
                }
                return result;
            }
            finally { try { Directory.Delete(dir, true); } catch (Exception) { } }
        }

        public static WifiNetwork ParseProfile(string xml)
        {
            var doc = new XmlDocument { XmlResolver = null };
            try { doc.LoadXml(xml); } catch (XmlException) { return null; }
            var ns = new XmlNamespaceManager(doc.NameTable);
            ns.AddNamespace("w", Ns);
            Func<string, string> text = xp => { var node = doc.SelectSingleNode(xp, ns); return node == null ? null : node.InnerText; };
            if ((text("/w:WLANProfile/w:connectionType") ?? "ESS") != "ESS") return null;
            var ssid = text("/w:WLANProfile/w:SSIDConfig/w:SSID/w:name");
            var hex = text("/w:WLANProfile/w:SSIDConfig/w:SSID/w:hex");
            if (hex != null && hex.Length % 2 == 0 && hex.Length > 0)
            {
                try { ssid = new UTF8Encoding(false, true).GetString(Protocol.FromHex(hex)); } catch (Exception) { }
            }
            if (string.IsNullOrEmpty(ssid) || Encoding.UTF8.GetByteCount(ssid) > 32) return null;
            var auth = text("/w:WLANProfile/w:MSM/w:security/w:authEncryption/w:authentication") ?? "";
            var oneX = text("/w:WLANProfile/w:MSM/w:security/w:authEncryption/w:useOneX") ?? "false";
            var key = text("/w:WLANProfile/w:MSM/w:security/w:sharedKey/w:keyMaterial");
            var isProtected = text("/w:WLANProfile/w:MSM/w:security/w:sharedKey/w:protected") ?? "false";
            var hidden = (text("/w:WLANProfile/w:SSIDConfig/w:nonBroadcast") ?? "false") == "true";
            if (oneX == "true") return null;
            string sec;
            if (auth == "open" && (text("/w:WLANProfile/w:MSM/w:security/w:authEncryption/w:encryption") ?? "none") == "none") sec = "open";
            else if (auth == "WPAPSK" || auth == "WPA2PSK") sec = "wpa-psk";
            else if (auth == "WPA3SAE") sec = "sae";
            else return null;                            // WEP, enterprise, OWE: not shared
            if (sec != "open" && (key == null || isProtected == "true")) return null;
            var net = new WifiNetwork { Ssid = ssid, Security = sec, Password = sec == "open" ? null : key, Hidden = hidden };
            try { Protocol.ParseWifi(Protocol.WifiJson(net)); } catch (InvalidMessageException) { return null; }
            return net;
        }

        public static string BuildProfile(WifiNetwork n)
        {
            var sb = new StringBuilder();
            var s = new XmlWriterSettings { Indent = true, Encoding = new UTF8Encoding(false), OmitXmlDeclaration = false };
            using (var w = XmlWriter.Create(sb, s))
            {
                w.WriteStartElement("WLANProfile", Ns);
                w.WriteElementString("name", Ns, n.Ssid);
                w.WriteStartElement("SSIDConfig", Ns);
                w.WriteStartElement("SSID", Ns);
                w.WriteElementString("hex", Ns, Protocol.Hex(Encoding.UTF8.GetBytes(n.Ssid)));
                w.WriteElementString("name", Ns, n.Ssid);
                w.WriteEndElement();
                w.WriteElementString("nonBroadcast", Ns, n.Hidden ? "true" : "false");
                w.WriteEndElement();
                w.WriteElementString("connectionType", Ns, "ESS");
                w.WriteElementString("connectionMode", Ns, "auto");
                w.WriteStartElement("MSM", Ns);
                w.WriteStartElement("security", Ns);
                w.WriteStartElement("authEncryption", Ns);
                w.WriteElementString("authentication", Ns, n.Security == "open" ? "open" : (n.Security == "sae" ? "WPA3SAE" : "WPA2PSK"));
                w.WriteElementString("encryption", Ns, n.Security == "open" ? "none" : "AES");
                w.WriteElementString("useOneX", Ns, "false");
                w.WriteEndElement();
                if (n.Security != "open")
                {
                    w.WriteStartElement("sharedKey", Ns);
                    w.WriteElementString("keyType", Ns, n.Password.Length == 64 ? "networkKey" : "passPhrase");
                    w.WriteElementString("protected", Ns, "false");
                    w.WriteElementString("keyMaterial", Ns, n.Password);
                    w.WriteEndElement();
                }
                w.WriteEndElement();
                w.WriteEndElement();
                w.WriteEndElement();
            }
            return sb.ToString();
        }

        static bool ImportNetsh(WifiNetwork n, string workDir)
        {
            var dir = Path.Combine(workDir, "wifi-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            try
            {
                var file = Path.Combine(dir, "profile.xml");
                File.WriteAllText(file, BuildProfile(n), new UTF8Encoding(false));
                string output;
                return Exec.Run("netsh.exe", "wlan add profile filename=\"" + file + "\" user=all", out output) == 0;
            }
            finally { try { Directory.Delete(dir, true); } catch (Exception) { } }
        }

        /// <summary>Add (or update) profiles for all users, with the WLAN API (nothing written to
        /// disk). Returns per-network results.</summary>
        public static List<KeyValuePair<string, string>> Import(IEnumerable<WifiNetwork> nets, List<WifiNetwork> existing, string workDir)
        {
            var results = new List<KeyValuePair<string, string>>();
            IntPtr h = IntPtr.Zero;
            try
            {
                uint version;
                if (WlanOpenHandle(2, IntPtr.Zero, out version, out h) != 0) h = IntPtr.Zero;
                var ifaces = h != IntPtr.Zero ? Interfaces(h) : new List<Guid>();
                foreach (var n in nets)
                {
                    var old = existing == null ? null : existing.FirstOrDefault(e => e.Ssid == n.Ssid);
                    if (old != null && old.Fingerprint() == n.Fingerprint() && old.Security == n.Security)
                    { results.Add(new KeyValuePair<string, string>(n.Ssid, "same")); continue; }
                    var ok = false;
                    foreach (var g in ifaces)
                    {
                        var iface = g;
                        uint reason;
                        ok |= WlanSetProfile(h, ref iface, 0, BuildProfile(n), null, true, IntPtr.Zero, out reason) == 0;   // 0 = all users
                    }
                    if (!ok) ok = ImportNetsh(n, workDir);   // same safety net as for reading
                    results.Add(new KeyValuePair<string, string>(n.Ssid, !ok ? "failed" : (old != null ? "updated" : "added")));
                }
            }
            catch (Exception)
            {
                for (int i = results.Count; i < nets.Count(); i++) results.Add(new KeyValuePair<string, string>(nets.ElementAt(i).Ssid, "failed"));
            }
            finally { if (h != IntPtr.Zero) WlanCloseHandle(h, IntPtr.Zero); }
            return results;
        }
    }
}
