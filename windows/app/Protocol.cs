// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Diego Buono
// Exchange protocol with DualPair for Linux (docs/protocol.md). Mirrors dualpair/mailbox.py.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

namespace DualPair
{
    public class InvalidMessageException : Exception
    {
        public InvalidMessageException(string why) : base(why) { }
    }

    public class LEKeys
    {
        public string Ltk;            // 32 uppercase hex, Windows byte order
        public int EncSize = 16;
        public int Ediv;
        public ulong Rand;
        public string Irk;            // or null
        public string AddressType = "public";
        public int Authenticated;
        public bool SecureConnections { get { return Ediv == 0 && Rand == 0; } }
    }

    public class Device
    {
        public string Adapter;        // AA:BB:CC:DD:EE:FF
        public string Address;
        public string Name;
        public string LinkKey;        // classic, or null
        public LEKeys Le;             // LE, or null
        public DateTime? PairedAt;    // UTC

        public string Kind { get { return LinkKey != null && Le != null ? "dual" : (Le != null ? "le" : "classic"); } }

        public string Fingerprint()
        {
            return Protocol.Fingerprint(LinkKey, Le != null ? Le.Ltk : null, Le != null ? Le.Ediv : 0, Le != null ? Le.Rand : 0);
        }
    }

    public class WifiNetwork
    {
        public string Ssid;
        public string Security;       // open, wpa-psk, sae
        public string Password;       // null for open networks
        public bool Hidden;
        public string Fingerprint() { return Protocol.WifiFingerprint(Ssid, Password); }
    }

    public class Message
    {
        public string Id;
        public string Type;           // "keys" or "set_clock"
        public string From;
        public DateTime Created;
        public DateTime Expires;
        public List<Device> Devices = new List<Device>();   // type keys
        public bool WindowsUtc;                              // type set_clock
        public bool FastStartupEnabled;                      // type set_fast_startup
        public List<WifiNetwork> Networks = new List<WifiNetwork>();   // type wifi
    }

    public static class Protocol
    {
        public const int Version = 1;
        public const int MaxFile = 64 * 1024;
        public const int MaxDevices = 64;
        public static readonly TimeSpan MaxLifetime = TimeSpan.FromDays(7);

        static readonly Regex IdRe = new Regex(@"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$");
        static readonly Regex MacRe = new Regex(@"^([0-9A-F]{2}:){5}[0-9A-F]{2}$");
        static readonly Regex Hex32Re = new Regex(@"^[0-9A-F]{32}$");
        static readonly Regex UInt64Re = new Regex(@"^[0-9]{1,20}$");
        static readonly Regex Hex64Re = new Regex(@"^[0-9A-Fa-f]{64}$");
        static readonly Regex ControlRe = new Regex(@"[\x00-\x1f\x7f]");
        public static readonly string[] Securities = { "open", "wpa-psk", "sae" };

        public static bool IsMac(string s) { return s != null && MacRe.IsMatch(s); }
        public static bool IsHex32(string s) { return s != null && Hex32Re.IsMatch(s); }
        public static bool IsId(string s) { return s != null && IdRe.IsMatch(s); }

        // ------------------------------------------------------------------ JSON
        public static JavaScriptSerializer Serializer()
        {
            return new JavaScriptSerializer { MaxJsonLength = MaxFile * 4 };
        }

        public static Dictionary<string, object> ReadJsonFile(string path)
        {
            var info = new FileInfo(path);
            if (!info.Exists || info.Length > MaxFile || (info.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidMessageException("missing, too big or a link");
            var text = File.ReadAllText(path, new UTF8Encoding(false));
            var obj = Serializer().DeserializeObject(text) as Dictionary<string, object>;
            if (obj == null) throw new InvalidMessageException("not an object");
            return obj;
        }

        public static void WriteJsonFile(string path, object data)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var tmp = path + ".tmp";
            File.WriteAllText(tmp, Serializer().Serialize(data), new UTF8Encoding(false));
            if (File.Exists(path)) File.Delete(path);
            File.Move(tmp, path);
        }

        // ------------------------------------------------------------------ time, ids, names
        public static string Iso(DateTime utc)
        {
            return utc.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture);
        }

        public static DateTime ParseIso(object o)
        {
            var s = o as string;
            DateTime t;
            if (s == null || !DateTime.TryParseExact(s, "yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out t))
                throw new InvalidMessageException("bad time");
            return t;
        }

        public static DateTime UtcNow()
        {
            var n = DateTime.UtcNow;
            return new DateTime(n.Year, n.Month, n.Day, n.Hour, n.Minute, n.Second, DateTimeKind.Utc);
        }

        public static string NewId(DateTime utc)
        {
            var b = new byte[3];
            using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(b);
            return utc.ToString("yyyyMMdd-HHmmss-", CultureInfo.InvariantCulture) + Hex(b).ToLowerInvariant();
        }

        public static string CleanName(object o)
        {
            var s = o as string;
            if (s == null) return null;
            var sb = new StringBuilder();
            foreach (var c in s) if (c >= 0x20 && c != 0x7f) sb.Append(c);
            var r = sb.ToString().Trim();
            if (r.Length > 248) r = r.Substring(0, 248);
            return r.Length == 0 ? null : r;
        }

        public static string Hex(byte[] b)
        {
            var sb = new StringBuilder(b.Length * 2);
            foreach (var x in b) sb.Append(x.ToString("X2", CultureInfo.InvariantCulture));
            return sb.ToString();
        }

        public static byte[] FromHex(string h)
        {
            var b = new byte[h.Length / 2];
            for (int i = 0; i < b.Length; i++) b[i] = byte.Parse(h.Substring(i * 2, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture);
            return b;
        }

        public static string MacFromHex12(string hex12)
        {
            var h = hex12.ToUpperInvariant();
            var parts = new string[6];
            for (int i = 0; i < 6; i++) parts[i] = h.Substring(i * 2, 2);
            return string.Join(":", parts);
        }

        public static string Hex12FromMac(string mac) { return mac.Replace(":", "").ToLowerInvariant(); }

        // ------------------------------------------------------------------ fingerprints
        public static string Fingerprint(string linkKey, string ltk, int ediv, ulong rand)
        {
            var parts = new List<string>();
            if (linkKey != null) parts.Add(linkKey.ToUpperInvariant());
            if (ltk != null)
            {
                parts.Add(ltk.ToUpperInvariant());
                parts.Add(ediv.ToString(CultureInfo.InvariantCulture));
                parts.Add(rand.ToString(CultureInfo.InvariantCulture));
            }
            using (var sha = SHA256.Create())
            {
                var h = sha.ComputeHash(Encoding.ASCII.GetBytes("dualpair-fp-v1|" + string.Join("|", parts)));
                return Hex(h).Substring(0, 8).ToLowerInvariant();
            }
        }

        public static string WifiFingerprint(string ssid, string password)
        {
            using (var sha = SHA256.Create())
            {
                var h = sha.ComputeHash(Encoding.UTF8.GetBytes("dualpair-fp-v1|wifi|" + ssid + "|" + (password ?? "")));
                return Hex(h).Substring(0, 8).ToLowerInvariant();
            }
        }

        public static WifiNetwork ParseWifi(object o)
        {
            var n = o as Dictionary<string, object>;
            if (n == null) throw new InvalidMessageException("bad network");
            var ssid = Get(n, "ssid") as string;
            var sec = Get(n, "security") as string;
            var pw = Get(n, "password");
            var hidden = n.ContainsKey("hidden") ? n["hidden"] : false;
            if (ssid == null || Encoding.UTF8.GetByteCount(ssid) < 1 || Encoding.UTF8.GetByteCount(ssid) > 32 || ControlRe.IsMatch(ssid))
                throw new InvalidMessageException("bad ssid");
            if (Array.IndexOf(Securities, sec) < 0) throw new InvalidMessageException("bad security");
            if (sec == "open") { if (pw != null) throw new InvalidMessageException("open network with password"); }
            else
            {
                var p = pw as string;
                if (p == null || !((p.Length >= 8 && p.Length <= 63 && !ControlRe.IsMatch(p)) || Hex64Re.IsMatch(p)))
                    throw new InvalidMessageException("bad password");
            }
            if (!(hidden is bool)) throw new InvalidMessageException("bad hidden");
            return new WifiNetwork { Ssid = ssid, Security = sec, Password = pw as string, Hidden = (bool)hidden };
        }

        public static Dictionary<string, object> WifiJson(WifiNetwork n)
        {
            return new Dictionary<string, object> { { "ssid", n.Ssid }, { "security", n.Security }, { "password", n.Password }, { "hidden", n.Hidden } };
        }

        // ------------------------------------------------------------------ validation
        static int Int(object o, int lo, int hi)
        {
            if (o is bool) throw new InvalidMessageException("bad number");
            long v;
            if (o is int) v = (int)o;
            else if (o is long) v = (long)o;
            else throw new InvalidMessageException("bad number");
            if (v < lo || v > hi) throw new InvalidMessageException("number out of range");
            return (int)v;
        }

        static LEKeys ParseLe(object o)
        {
            var le = o as Dictionary<string, object>;
            if (le == null) throw new InvalidMessageException("bad le");
            var ltk = Get(le, "ltk") as string;
            var irk = Get(le, "irk");
            var rand = Get(le, "rand") as string;
            if (!IsHex32(ltk)) throw new InvalidMessageException("bad ltk");
            if (irk != null && !IsHex32(irk as string)) throw new InvalidMessageException("bad irk");
            ulong r;
            if (rand == null || !UInt64Re.IsMatch(rand) || !ulong.TryParse(rand, NumberStyles.None, CultureInfo.InvariantCulture, out r))
                throw new InvalidMessageException("bad rand");
            var at = Get(le, "address_type") as string;
            if (at != "public" && at != "static") throw new InvalidMessageException("bad address type");
            return new LEKeys
            {
                Ltk = ltk, Irk = irk as string, Rand = r, AddressType = at,
                EncSize = Int(Get(le, "enc_size"), 7, 16),
                Ediv = Int(Get(le, "ediv"), 0, 65535),
                Authenticated = le.ContainsKey("authenticated") ? Int(le["authenticated"], 0, 4) : 0,
            };
        }

        static object Get(Dictionary<string, object> d, string k)
        {
            object v;
            return d.TryGetValue(k, out v) ? v : null;
        }

        public static List<Device> ParseDevices(object payload)
        {
            var p = payload as Dictionary<string, object>;
            var list = p != null ? Get(p, "devices") as object[] : null;
            if (list == null || list.Length == 0 || list.Length > MaxDevices) throw new InvalidMessageException("bad device list");
            var result = new List<Device>();
            foreach (var item in list)
            {
                var d = item as Dictionary<string, object>;
                if (d == null) throw new InvalidMessageException("bad device");
                var adapter = Get(d, "adapter") as string;
                var address = Get(d, "address") as string;
                if (!IsMac(adapter) || !IsMac(address)) throw new InvalidMessageException("bad address");
                var lk = Get(d, "link_key");
                if (lk != null && !IsHex32(lk as string)) throw new InvalidMessageException("bad link key");
                var le = Get(d, "le") != null ? ParseLe(d["le"]) : null;
                if (lk == null && le == null) throw new InvalidMessageException("no keys");
                result.Add(new Device { Adapter = adapter, Address = address, Name = CleanName(Get(d, "name")), LinkKey = lk as string, Le = le });
            }
            return result;
        }

        public static Message Validate(Dictionary<string, object> m, string sender, string fileName, DateTime now)
        {
            if (!(Get(m, "dualpair") is int) || (int)m["dualpair"] != Version) throw new InvalidMessageException("unknown protocol version");
            var id = Get(m, "id") as string;
            if (!IsId(id) || fileName != id + ".json") throw new InvalidMessageException("bad id");
            if ((Get(m, "from") as string) != sender) throw new InvalidMessageException("wrong sender");
            var created = ParseIso(Get(m, "created"));
            var expires = ParseIso(Get(m, "expires"));
            if (expires <= now || expires < created || expires - created > MaxLifetime) throw new InvalidMessageException("expired");
            var msg = new Message { Id = id, From = sender, Created = created, Expires = expires, Type = Get(m, "type") as string };
            if (msg.Type == "keys") msg.Devices = ParseDevices(Get(m, "payload"));
            else if (msg.Type == "set_clock")
            {
                var p = Get(m, "payload") as Dictionary<string, object>;
                if (p == null || !(Get(p, "windows_utc") is bool)) throw new InvalidMessageException("bad payload");
                msg.WindowsUtc = (bool)p["windows_utc"];
            }
            else if (msg.Type == "set_fast_startup")
            {
                var p = Get(m, "payload") as Dictionary<string, object>;
                if (p == null || !(Get(p, "enabled") is bool)) throw new InvalidMessageException("bad payload");
                msg.FastStartupEnabled = (bool)p["enabled"];
            }
            else if (msg.Type == "wifi")
            {
                var p = Get(m, "payload") as Dictionary<string, object>;
                var list = p != null ? Get(p, "networks") as object[] : null;
                if (list == null || list.Length == 0 || list.Length > MaxDevices) throw new InvalidMessageException("bad network list");
                foreach (var n in list) msg.Networks.Add(ParseWifi(n));
            }
            else throw new InvalidMessageException("unknown type");
            return msg;
        }

        // ------------------------------------------------------------------ serializing
        public static Dictionary<string, object> DeviceJson(Device d)
        {
            object le = null;
            if (d.Le != null)
                le = new Dictionary<string, object> {
                    { "ltk", d.Le.Ltk }, { "enc_size", d.Le.EncSize }, { "ediv", d.Le.Ediv },
                    { "rand", d.Le.Rand.ToString(CultureInfo.InvariantCulture) }, { "irk", d.Le.Irk },
                    { "address_type", d.Le.AddressType }, { "authenticated", d.Le.Authenticated } };
            return new Dictionary<string, object> {
                { "adapter", d.Adapter }, { "address", d.Address }, { "name", d.Name },
                { "link_key", d.LinkKey }, { "le", le } };
        }

        public static Dictionary<string, object> NewMessage(string type, string from, object payload, out string id)
        {
            var now = UtcNow();
            id = NewId(now);
            return new Dictionary<string, object> {
                { "dualpair", Version }, { "id", id }, { "type", type }, { "from", from },
                { "created", Iso(now) }, { "expires", Iso(now + MaxLifetime) }, { "payload", payload } };
        }
    }
}
