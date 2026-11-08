// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Diego Buono
// Setup steps run by the installer (--install / --uninstall): the SYSTEM scheduled task and the
// protected %ProgramData%\DualPair folder. Also how the window asks the task for work.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Threading;

namespace DualPair
{
    public static class Install
    {
        public const string TaskName = @"DualPair\Agent";

        static int Run(string exe, string args)
        {
            var psi = new ProcessStartInfo(exe, args) { UseShellExecute = false, CreateNoWindow = true,
                                                        RedirectStandardOutput = true, RedirectStandardError = true };
            using (var p = Process.Start(psi))
            {
                p.WaitForExit(60000);
                return p.HasExited ? p.ExitCode : -1;
            }
        }

        static FileSystemAccessRule Rule(WellKnownSidType sid, FileSystemRights rights)
        {
            return new FileSystemAccessRule(new SecurityIdentifier(sid, null), rights,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow);
        }

        /// <summary>Only SYSTEM and administrators can write; users can read the status (no keys);
        /// backups (old keys) are not readable by users.</summary>
        public static void SecureStateDir(string dir)
        {
            Directory.CreateDirectory(dir);
            var ds = new DirectorySecurity();
            ds.SetAccessRuleProtection(true, false);
            ds.AddAccessRule(Rule(WellKnownSidType.LocalSystemSid, FileSystemRights.FullControl));
            ds.AddAccessRule(Rule(WellKnownSidType.BuiltinAdministratorsSid, FileSystemRights.FullControl));
            ds.AddAccessRule(Rule(WellKnownSidType.BuiltinUsersSid, FileSystemRights.ReadAndExecute));
            new DirectoryInfo(dir).SetAccessControl(ds);
            foreach (var sub in new[] { "requests", "results" }) Directory.CreateDirectory(Path.Combine(dir, sub));
            var backups = Path.Combine(dir, "backups");
            Directory.CreateDirectory(backups);
            var bs = new DirectorySecurity();
            bs.SetAccessRuleProtection(true, false);
            bs.AddAccessRule(Rule(WellKnownSidType.LocalSystemSid, FileSystemRights.FullControl));
            bs.AddAccessRule(Rule(WellKnownSidType.BuiltinAdministratorsSid, FileSystemRights.FullControl));
            new DirectoryInfo(backups).SetAccessControl(bs);
        }

        static string Xml(string s) { return System.Security.SecurityElement.Escape(s); }

        public static int Setup(string exePath, Options opt)
        {
            SecureStateDir(opt.StateDir);
            var xml = "<?xml version=\"1.0\" encoding=\"UTF-16\"?>\n" +
                "<Task version=\"1.2\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\">\n" +
                " <RegistrationInfo><Description>DualPair: applies requests from DualPair for Linux and does the Bluetooth key work that needs SYSTEM.</Description></RegistrationInfo>\n" +
                " <Triggers><BootTrigger><Enabled>true</Enabled><Delay>PT20S</Delay></BootTrigger></Triggers>\n" +
                " <Principals><Principal id=\"Author\"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal></Principals>\n" +
                " <Settings>\n" +
                "  <MultipleInstancesPolicy>Queue</MultipleInstancesPolicy>\n" +
                "  <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n" +
                "  <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n" +
                "  <StartWhenAvailable>true</StartWhenAvailable>\n" +
                "  <AllowStartOnDemand>true</AllowStartOnDemand>\n" +
                "  <Enabled>true</Enabled>\n" +
                "  <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>\n" +
                " </Settings>\n" +
                " <Actions Context=\"Author\"><Exec><Command>" + Xml(exePath) + "</Command><Arguments>--agent</Arguments></Exec></Actions>\n" +
                "</Task>\n";
            var tmp = Path.Combine(Path.GetTempPath(), "dualpair-task-" + Guid.NewGuid().ToString("N") + ".xml");
            File.WriteAllText(tmp, xml, Encoding.Unicode);
            try { return Run("schtasks.exe", "/Create /TN \"" + TaskName + "\" /XML \"" + tmp + "\" /F"); }
            finally { File.Delete(tmp); }
        }

        public static int Remove(Options opt)
        {
            Run("schtasks.exe", "/Delete /TN \"" + TaskName + "\" /F");
            // the folder holds backups of old keys: do not leave it behind
            try { if (Directory.Exists(opt.StateDir)) Directory.Delete(opt.StateDir, true); } catch (Exception) { }
            return 0;
        }

        /// <summary>Ask the SYSTEM task to do one operation and wait for the answer.</summary>
        public static Dictionary<string, object> Ask(Options opt, Dictionary<string, object> request, int timeoutSeconds = 60)
        {
            if (Environment.GetEnvironmentVariable("DUALPAIR_INPROC") == "1")   // tests: no task
                return new Agent(opt).RunNow(request);
            var id = Guid.NewGuid().ToString();
            var reqDir = Path.Combine(opt.StateDir, "requests");
            var result = Path.Combine(opt.StateDir, "results", id + ".json");
            Protocol.WriteJsonFile(Path.Combine(reqDir, id + ".json"), request);
            if (Run("schtasks.exe", "/Run /TN \"" + TaskName + "\"") != 0)
            {
                File.Delete(Path.Combine(reqDir, id + ".json"));
                return new Dictionary<string, object> { { "error", Strings.T("err.no_agent") } };
            }
            var deadline = DateTime.UtcNow.AddSeconds(timeoutSeconds);
            while (DateTime.UtcNow < deadline)
            {
                if (File.Exists(result))
                {
                    Thread.Sleep(200);
                    try
                    {
                        var r = Protocol.ReadJsonFile(result);
                        File.Delete(result);
                        return r;
                    }
                    catch (IOException) { }
                }
                Thread.Sleep(300);
            }
            return new Dictionary<string, object> { { "error", Strings.T("err.no_agent") } };
        }
    }
}
