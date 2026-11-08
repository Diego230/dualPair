// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Diego Buono
// Bluetooth pairing keys in the Windows registry (readable and writable only by SYSTEM):
//   HKLM\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys\<adapter>\
//       <device>    REG_BINARY 16 bytes  -> classic link key
//       <device>\   subkey               -> LE keys (LTK, KeyLength, ERand, EDIV, IRK, AddressType, ...)
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;

namespace DualPair
{
    public class ImportResult
    {
        public string Address;
        public string Name;
        public string Result;     // "imported", "not_paired", "no_adapter"
    }

    public class BluetoothStore
    {
        public const string DefaultParams = @"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters";
        const string BthLe = @"SYSTEM\CurrentControlSet\Enum\BTHLE";
        static readonly Regex Hex12 = new Regex("^[0-9a-fA-F]{12}$");

        readonly string paramsPath;   // under HKLM; tests use HKLM\SOFTWARE\DualPairTest\...
        readonly string stateDir;

        public BluetoothStore(string paramsPathOverride, string stateDir)
        {
            paramsPath = string.IsNullOrEmpty(paramsPathOverride) ? DefaultParams : paramsPathOverride;
            this.stateDir = stateDir;
        }

        bool IsTest { get { return paramsPath != DefaultParams; } }

        // ------------------------------------------------------------------ reading
        public bool Available()
        {
            using (var k = Registry.LocalMachine.OpenSubKey(paramsPath + @"\Keys")) return k != null;
        }

        public List<string> Adapters()
        {
            using (var keys = Registry.LocalMachine.OpenSubKey(paramsPath + @"\Keys"))
                return keys == null ? new List<string>()
                    : keys.GetSubKeyNames().Where(n => Hex12.IsMatch(n)).Select(Protocol.MacFromHex12).ToList();
        }

        public List<Device> Devices()
        {
            var result = new List<Device>();
            using (var keys = Registry.LocalMachine.OpenSubKey(paramsPath + @"\Keys"))
            {
                if (keys == null) return result;
                foreach (var adapterName in keys.GetSubKeyNames().Where(n => Hex12.IsMatch(n)))
                using (var adapter = keys.OpenSubKey(adapterName))
                {
                    if (adapter == null) continue;
                    var found = new Dictionary<string, Device>();
                    Func<string, Device> dev = hex =>
                    {
                        Device d;
                        if (!found.TryGetValue(hex.ToLowerInvariant(), out d))
                        {
                            d = new Device { Adapter = Protocol.MacFromHex12(adapterName), Address = Protocol.MacFromHex12(hex), Name = DeviceName(hex) };
                            found[hex.ToLowerInvariant()] = d;
                        }
                        return d;
                    };
                    var adapterTime = LastWrite(adapter);
                    foreach (var v in adapter.GetValueNames().Where(n => Hex12.IsMatch(n)))
                    {
                        var data = adapter.GetValue(v) as byte[];
                        if (adapter.GetValueKind(v) == RegistryValueKind.Binary && data != null && data.Length == 16)
                        {
                            var d = dev(v);
                            d.LinkKey = Protocol.Hex(data);
                            d.PairedAt = adapterTime;   // values have no time of their own
                        }
                    }
                    foreach (var sub in adapter.GetSubKeyNames().Where(n => Hex12.IsMatch(n)))
                    using (var k = adapter.OpenSubKey(sub))
                    {
                        var ltk = k == null ? null : k.GetValue("LTK") as byte[];
                        if (ltk == null || ltk.Length != 16) continue;
                        var d = dev(sub);
                        var t = LastWrite(k);
                        if (t.HasValue && (!d.PairedAt.HasValue || t > d.PairedAt)) d.PairedAt = t;
                        var irk = k.GetValue("IRK") as byte[];
                        var ediv = AsInt(k.GetValue("EDIV"));
                        var rand = AsULong(k.GetValue("ERand"));
                        var auth = (ediv == 0 && rand == 0) ? 2 : 0;
                        if ((AsInt(k.GetValue("AuthReq")) & 0x04) != 0) auth += 1;
                        var keyLength = AsInt(k.GetValue("KeyLength"));
                        d.Le = new LEKeys
                        {
                            Ltk = Protocol.Hex(ltk), EncSize = keyLength > 0 ? keyLength : 16, Ediv = ediv, Rand = rand,
                            Irk = irk != null && irk.Length == 16 && irk.Any(b => b != 0) ? Protocol.Hex(irk) : null,
                            AddressType = AsInt(k.GetValue("AddressType")) == 1 ? "static" : "public",
                            Authenticated = auth,
                        };
                        if (d.Name == null) d.Name = LeName(sub);
                    }
                    result.AddRange(found.Values);
                }
            }
            return result;
        }

        string DeviceName(string hex)
        {
            using (var k = Registry.LocalMachine.OpenSubKey(paramsPath + @"\Devices\" + hex.ToLowerInvariant()))
            {
                if (k == null) return null;
                var v = k.GetValue("Name");
                var bytes = v as byte[];
                if (bytes != null)
                {
                    var end = Array.IndexOf(bytes, (byte)0);
                    return Protocol.CleanName(Encoding.UTF8.GetString(bytes, 0, end < 0 ? bytes.Length : end));
                }
                return Protocol.CleanName(v as string);
            }
        }

        string LeName(string hex)
        {
            if (IsTest) return null;
            using (var k = Registry.LocalMachine.OpenSubKey(BthLe + @"\Dev_" + hex.ToLowerInvariant()))
            {
                if (k == null) return null;
                foreach (var inst in k.GetSubKeyNames())
                using (var i = k.OpenSubKey(inst))
                {
                    var n = i == null ? null : Protocol.CleanName(i.GetValue("FriendlyName"));
                    if (n != null) return n;
                }
            }
            return null;
        }

        static int AsInt(object o) { return o is int ? (int)o : (o is long ? (int)(long)o : 0); }
        static ulong AsULong(object o) { return o is long ? unchecked((ulong)(long)o) : (o is int ? unchecked((ulong)(uint)(int)o) : 0UL); }

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode)]
        static extern int RegQueryInfoKey(SafeRegistryHandle hKey, IntPtr lpClass, IntPtr lpcbClass, IntPtr lpReserved,
            IntPtr lpcSubKeys, IntPtr lpcbMaxSubKeyLen, IntPtr lpcbMaxClassLen, IntPtr lpcValues,
            IntPtr lpcbMaxValueNameLen, IntPtr lpcbMaxValueLen, IntPtr lpcbSecurityDescriptor, out long lpftLastWriteTime);

        static DateTime? LastWrite(RegistryKey k)
        {
            try
            {
                long ft;
                if (RegQueryInfoKey(k.Handle, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero,
                                    IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, out ft) == 0 && ft > 0)
                    return DateTime.FromFileTimeUtc(ft);
            }
            catch (Exception) { }
            return null;
        }

        // ------------------------------------------------------------------ writing (import from Linux)
        /// <summary>Update the keys of devices already paired in Windows. Never creates devices.
        /// The previous values are saved to a backup first.</summary>
        public List<ImportResult> Import(IEnumerable<Device> devices)
        {
            var results = new List<ImportResult>();
            var backup = new List<object>();
            var adapters = Adapters();
            using (var keys = Registry.LocalMachine.OpenSubKey(paramsPath + @"\Keys", true))
            {
                foreach (var d in devices)
                {
                    var r = new ImportResult { Address = d.Address, Name = d.Name };
                    results.Add(r);
                    var adapterMac = adapters.Contains(d.Adapter) ? d.Adapter : (adapters.Count == 1 ? adapters[0] : null);
                    if (keys == null || adapterMac == null) { r.Result = "no_adapter"; continue; }
                    var hex = Protocol.Hex12FromMac(d.Address);
                    using (var adapter = keys.OpenSubKey(Protocol.Hex12FromMac(adapterMac), true))
                    {
                        if (adapter == null) { r.Result = "no_adapter"; continue; }
                        var hasClassic = adapter.GetValueNames().Any(n => string.Equals(n, hex, StringComparison.OrdinalIgnoreCase));
                        var leKey = adapter.GetSubKeyNames().FirstOrDefault(n => string.Equals(n, hex, StringComparison.OrdinalIgnoreCase));
                        if ((d.LinkKey != null && !hasClassic) || (d.Le != null && leKey == null) || (d.LinkKey == null && d.Le == null))
                        { r.Result = "not_paired"; continue; }
                        var entry = new Dictionary<string, object> { { "adapter", adapterMac }, { "address", d.Address } };
                        if (d.LinkKey != null)
                        {
                            var name = adapter.GetValueNames().First(n => string.Equals(n, hex, StringComparison.OrdinalIgnoreCase));
                            entry["link_key"] = Protocol.Hex((byte[])adapter.GetValue(name));
                            adapter.SetValue(name, Protocol.FromHex(d.LinkKey), RegistryValueKind.Binary);
                        }
                        if (d.Le != null)
                        using (var k = adapter.OpenSubKey(leKey, true))
                        {
                            var old = new Dictionary<string, object>();
                            foreach (var v in new[] { "LTK", "KeyLength", "ERand", "EDIV", "IRK" })
                            {
                                var val = k.GetValue(v);
                                if (val is byte[]) old[v] = "hex:" + Protocol.Hex((byte[])val);
                                else if (val != null) old[v] = Convert.ToString(val, CultureInfo.InvariantCulture);
                            }
                            entry["le"] = old;
                            k.SetValue("LTK", Protocol.FromHex(d.Le.Ltk), RegistryValueKind.Binary);
                            k.SetValue("KeyLength", d.Le.EncSize, RegistryValueKind.DWord);
                            k.SetValue("ERand", unchecked((long)d.Le.Rand), RegistryValueKind.QWord);
                            k.SetValue("EDIV", d.Le.Ediv, RegistryValueKind.DWord);
                            if (d.Le.Irk != null) k.SetValue("IRK", Protocol.FromHex(d.Le.Irk), RegistryValueKind.Binary);
                        }
                        backup.Add(entry);
                        r.Result = "imported";
                    }
                }
            }
            if (backup.Count > 0) SaveBackup(backup);
            return results;
        }

        // ------------------------------------------------------------------ backups
        string BackupDir { get { return Path.Combine(stateDir, "backups"); } }

        void SaveBackup(List<object> entries)
        {
            Directory.CreateDirectory(BackupDir);
            var name = DateTime.UtcNow.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture) + ".json";
            Protocol.WriteJsonFile(Path.Combine(BackupDir, name), new Dictionary<string, object> {
                { "params", paramsPath }, { "entries", entries } });
            // old backups hold old keys: keep the newest 5
            foreach (var f in Directory.GetFiles(BackupDir, "*.json").OrderByDescending(f => f, StringComparer.Ordinal).Skip(5))
                File.Delete(f);
        }

        public bool RestoreLast()
        {
            if (!Directory.Exists(BackupDir)) return false;
            var last = Directory.GetFiles(BackupDir, "*.json").OrderByDescending(f => f, StringComparer.Ordinal).FirstOrDefault();
            if (last == null) return false;
            var data = Protocol.ReadJsonFile(last);
            if ((data["params"] as string) != paramsPath) return false;
            using (var keys = Registry.LocalMachine.OpenSubKey(paramsPath + @"\Keys", true))
            {
                foreach (Dictionary<string, object> e in (object[])data["entries"])
                {
                    var adapterMac = e["adapter"] as string;
                    var address = e["address"] as string;
                    if (!Protocol.IsMac(adapterMac) || !Protocol.IsMac(address) || keys == null) continue;
                    using (var adapter = keys.OpenSubKey(Protocol.Hex12FromMac(adapterMac), true))
                    {
                        if (adapter == null) continue;
                        var hex = Protocol.Hex12FromMac(address);
                        object lk;
                        if (e.TryGetValue("link_key", out lk) && Protocol.IsHex32(lk as string))
                            adapter.SetValue(hex, Protocol.FromHex((string)lk), RegistryValueKind.Binary);
                        object le;
                        if (e.TryGetValue("le", out le) && le is Dictionary<string, object>)
                        using (var k = adapter.OpenSubKey(hex, true))
                        {
                            if (k == null) continue;
                            foreach (var kv in (Dictionary<string, object>)le)
                            {
                                var s = kv.Value as string;
                                if (s == null) continue;
                                if (s.StartsWith("hex:")) k.SetValue(kv.Key, Protocol.FromHex(s.Substring(4)), RegistryValueKind.Binary);
                                else if (kv.Key == "ERand") k.SetValue(kv.Key, long.Parse(s, CultureInfo.InvariantCulture), RegistryValueKind.QWord);
                                else k.SetValue(kv.Key, int.Parse(s, CultureInfo.InvariantCulture), RegistryValueKind.DWord);
                            }
                        }
                    }
                }
            }
            File.Delete(last);
            return true;
        }
    }
}
