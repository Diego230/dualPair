// The hardware clock standard. Windows reads the RTC as local time unless
// HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation\RealTimeIsUniversal = 1.
using System;
using System.Diagnostics;
using System.ServiceProcess;
using System.Threading;
using Microsoft.Win32;

namespace DualPair
{
    public static class Clock
    {
        public const string DefaultKey = @"SYSTEM\CurrentControlSet\Control\TimeZoneInformation";
        public static string KeyPath = DefaultKey;   // tests point this elsewhere

        public static bool RtcUtc()
        {
            using (var k = Registry.LocalMachine.OpenSubKey(KeyPath))
            {
                var v = k == null ? null : k.GetValue("RealTimeIsUniversal");
                return (v is int && (int)v == 1) || (v is long && (long)v == 1);
            }
        }

        public static void SetRtcUtc(bool utc)
        {
            using (var k = Registry.LocalMachine.CreateSubKey(KeyPath))
            {
                if (utc) k.SetValue("RealTimeIsUniversal", 1, RegistryValueKind.DWord);
                else if (k.GetValue("RealTimeIsUniversal") != null) k.DeleteValue("RealTimeIsUniversal");
            }
        }

        public static string TimeZoneName()
        {
            try { return TimeZoneInfo.Local.DisplayName; } catch (Exception) { return null; }
        }

        /// <summary>Ask the Windows Time service to sync now. Returns true on success.</summary>
        public static bool Resync(int attempts = 1)
        {
            for (int i = 0; i < attempts; i++)
            {
                if (i > 0) Thread.Sleep(20000);
                try
                {
                    using (var sc = new ServiceController("w32time"))
                    {
                        if (sc.Status != ServiceControllerStatus.Running)
                        {
                            sc.Start();
                            sc.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(15));
                        }
                    }
                    var psi = new ProcessStartInfo("w32tm.exe", "/resync /force") { UseShellExecute = false, CreateNoWindow = true,
                                                                                  RedirectStandardOutput = true, RedirectStandardError = true };
                    using (var p = Process.Start(psi))
                    {
                        p.WaitForExit(30000);
                        if (p.HasExited && p.ExitCode == 0) return true;
                    }
                }
                catch (Exception) { }
            }
            return false;
        }
    }
}
