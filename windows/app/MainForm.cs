// The window: Bluetooth and Clock tabs. Runs as administrator; anything that needs SYSTEM (the
// Bluetooth keys) is asked of the agent task through Install.Ask.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace DualPair
{
    public class MainForm : Form
    {
        readonly Options opt;
        Dictionary<string, object> status;

        readonly Label linuxLine = new Label { AutoSize = true, ForeColor = Color.DimGray, Padding = new Padding(0, 6, 0, 0) };
        readonly ListView devices = new ListView { View = View.Details, FullRowSelect = true, HeaderStyle = ColumnHeaderStyle.Nonclickable, Dock = DockStyle.Fill };
        readonly GroupBox pendingBox = new GroupBox { Dock = DockStyle.Top, Height = 190, Visible = false, Padding = new Padding(10) };
        readonly CheckedListBox pendingList = new CheckedListBox { Dock = DockStyle.Fill, CheckOnClick = true };
        readonly Button importBtn = new Button { AutoSize = true };
        readonly Button discardBtn = new Button { AutoSize = true };
        readonly Button exportBtn = new Button { AutoSize = true };
        readonly Button restoreBtn = new Button { AutoSize = true };
        readonly Button refreshBtn = new Button { AutoSize = true };
        readonly Label clockState = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 90, Font = new Font("Segoe UI", 10, FontStyle.Bold) };
        readonly Label clockLinux = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 28 };
        readonly Button utcBtn = new Button { Dock = DockStyle.Top, Height = 38 };
        readonly Button localBtn = new Button { Dock = DockStyle.Top, Height = 38 };
        readonly Button syncBtn = new Button { Dock = DockStyle.Top, Height = 38 };
        readonly Label tzLabel = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 30, ForeColor = Color.DimGray };
        readonly Label busy = new Label { AutoSize = true, ForeColor = Color.DimGray, Padding = new Padding(0, 6, 0, 0) };
        // Wi-Fi tab
        readonly ListView wifiList = new ListView { View = View.Details, FullRowSelect = true, CheckBoxes = true, HeaderStyle = ColumnHeaderStyle.Nonclickable, Dock = DockStyle.Fill };
        readonly GroupBox wifiPendingBox = new GroupBox { Dock = DockStyle.Top, Height = 190, Visible = false, Padding = new Padding(10) };
        readonly CheckedListBox wifiPendingList = new CheckedListBox { Dock = DockStyle.Fill, CheckOnClick = true };
        List<string> wifiPendingSsids = new List<string>();
        string wifiPendingId;
        // Startup tab
        readonly Label fastState = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 28, Font = new Font("Segoe UI", 10, FontStyle.Bold) };
        readonly Button fastBtn = new Button { Dock = DockStyle.Top, Height = 38 };
        readonly Label bootState = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 28, Font = new Font("Segoe UI", 10, FontStyle.Bold) };
        readonly Label bootKeep = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 48 };
        readonly Button bootBtn = new Button { Dock = DockStyle.Top, Height = 38 };
        List<Dictionary<string, object>> pendingDevices = new List<Dictionary<string, object>>();
        string pendingId;

        public MainForm(Options opt)
        {
            this.opt = opt;
            Text = "DualPair " + Program.Version;
            Font = new Font("Segoe UI", 9.5f);
            ClientSize = new Size(760, 600);
            MinimumSize = new Size(620, 480);
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Font;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }

            var tabs = new TabControl { Dock = DockStyle.Fill, Padding = new Point(14, 6) };
            tabs.TabPages.Add(BuildBluetoothTab());
            tabs.TabPages.Add(BuildWifiTab());
            tabs.TabPages.Add(BuildClockTab());
            tabs.TabPages.Add(BuildBootTab());

            var header = new Label { Text = Strings.T("app.subtitle"), Dock = DockStyle.Top, Height = 34,
                                     Font = new Font("Segoe UI", 12, FontStyle.Bold), Padding = new Padding(10, 8, 0, 0) };
            // grows with the text, so nothing is cut at 125-150% display scaling
            var footer = new FlowLayoutPanel { Dock = DockStyle.Bottom, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
                                               WrapContents = true, Padding = new Padding(8, 2, 8, 8) };
            footer.Controls.Add(linuxLine);
            footer.Controls.Add(busy);
            Controls.Add(tabs);
            Controls.Add(footer);
            Controls.Add(header);
            Shown += (s, e) => RefreshAll();
        }

        TabPage BuildBluetoothTab()
        {
            var page = new TabPage(Strings.T("tab.bluetooth")) { Padding = new Padding(12) };
            devices.Columns.Add(Strings.T("bt.col.name"), 210);
            devices.Columns.Add(Strings.T("bt.col.address"), 140);
            devices.Columns.Add(Strings.T("bt.col.kind"), 110);
            devices.Columns.Add(Strings.T("bt.col.state"), 200);

            importBtn.Text = Strings.T("bt.import");
            discardBtn.Text = Strings.T("bt.discard");
            importBtn.Click += (s, e) => DoImport();
            discardBtn.Click += (s, e) => RunAgent(new Dictionary<string, object> { { "op", "discard" }, { "message_id", pendingId } }, r => null);
            var pendingDesc = new Label { Text = Strings.T("bt.pending.desc"), Dock = DockStyle.Top, Height = 36 };
            var pendingButtons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 38, FlowDirection = FlowDirection.LeftToRight };
            pendingButtons.Controls.Add(importBtn);
            pendingButtons.Controls.Add(discardBtn);
            pendingBox.Controls.Add(pendingList);
            pendingBox.Controls.Add(pendingButtons);
            pendingBox.Controls.Add(pendingDesc);

            exportBtn.Text = Strings.T("bt.export");
            new ToolTip().SetToolTip(exportBtn, Strings.T("bt.export.tip"));
            exportBtn.Click += (s, e) => RunAgent(new Dictionary<string, object> { { "op", "export" } },
                r => Strings.T("bt.exported", r.ContainsKey("devices") ? r["devices"] : 0));
            restoreBtn.Text = Strings.T("bt.restore");
            restoreBtn.Click += (s, e) => RunAgent(new Dictionary<string, object> { { "op", "restore" } }, r => Strings.T("bt.restored"));
            refreshBtn.Text = Strings.T("refresh");
            refreshBtn.Click += (s, e) => RefreshAll();
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 42, Padding = new Padding(0, 6, 0, 0) };
            buttons.Controls.AddRange(new Control[] { exportBtn, restoreBtn, refreshBtn });

            var title = new Label { Text = Strings.T("bt.devices"), Dock = DockStyle.Top, Height = 26, Font = new Font("Segoe UI", 10, FontStyle.Bold) };
            page.Controls.Add(devices);
            page.Controls.Add(title);
            page.Controls.Add(new Panel { Dock = DockStyle.Top, Height = 8 });
            page.Controls.Add(pendingBox);
            page.Controls.Add(buttons);
            return page;
        }

        TabPage BuildWifiTab()
        {
            var page = new TabPage(Strings.T("tab.wifi")) { Padding = new Padding(12) };
            wifiList.Columns.Add(Strings.T("wifi.col.ssid"), 240);
            wifiList.Columns.Add(Strings.T("wifi.col.security"), 120);
            wifiList.Columns.Add(Strings.T("wifi.col.state"), 220);

            var import = new Button { AutoSize = true, Text = Strings.T("wifi.import") };
            var discard = new Button { AutoSize = true, Text = Strings.T("bt.discard") };
            import.Click += (s, e) =>
            {
                var chosen = wifiPendingList.CheckedIndices.Cast<int>().Select(i => (object)wifiPendingSsids[i]).ToArray();
                if (chosen.Length == 0 || wifiPendingId == null) return;
                RunAgent(new Dictionary<string, object> { { "op", "import_wifi" }, { "message_id", wifiPendingId }, { "ssids", chosen } },
                    r => Strings.T("wifi.imported", ((r["results"] as object[]) ?? new object[0]).Cast<Dictionary<string, object>>()
                                                    .Count(x => (x["result"] as string) == "added" || (x["result"] as string) == "updated")));
            };
            discard.Click += (s, e) => RunAgent(new Dictionary<string, object> { { "op", "discard" }, { "message_id", wifiPendingId } }, r => null);
            var pendingButtons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 38 };
            pendingButtons.Controls.Add(import);
            pendingButtons.Controls.Add(discard);
            wifiPendingBox.Controls.Add(wifiPendingList);
            wifiPendingBox.Controls.Add(pendingButtons);
            wifiPendingBox.Controls.Add(new Label { Text = Strings.T("wifi.pending.desc"), Dock = DockStyle.Top, Height = 30 });

            var send = new Button { AutoSize = true, Text = Strings.T("wifi.send") };
            send.Click += (s, e) =>
            {
                var chosen = wifiList.CheckedItems.Cast<ListViewItem>().Where(i => i.Tag is string).Select(i => (object)(string)i.Tag).ToArray();
                if (chosen.Length == 0) return;
                RunAgent(new Dictionary<string, object> { { "op", "export_wifi" }, { "ssids", chosen } },
                    r => Strings.T("wifi.sent", r.ContainsKey("networks") ? r["networks"] : 0));
            };
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 42, Padding = new Padding(0, 6, 0, 0) };
            buttons.Controls.Add(send);
            page.Controls.Add(wifiList);
            page.Controls.Add(new Label { Text = Strings.T("wifi.title"), Dock = DockStyle.Top, Height = 26, Font = new Font("Segoe UI", 10, FontStyle.Bold) });
            page.Controls.Add(new Panel { Dock = DockStyle.Top, Height = 8 });
            page.Controls.Add(wifiPendingBox);
            page.Controls.Add(buttons);
            return page;
        }

        TabPage BuildBootTab()
        {
            var page = new TabPage(Strings.T("tab.boot")) { Padding = new Padding(16), AutoScroll = true };
            fastBtn.Click += (s, e) =>
            {
                var turnOn = FastStartup.Enabled() == false;
                Busy(() => { FastStartup.Set(turnOn); return true; }, ok =>
                {
                    MessageBox.Show(this, Strings.T("fast.done"), "DualPair", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    RefreshAll();
                });
            };
            bootBtn.Text = Strings.T("boot.put_linux_first");
            bootBtn.Click += (s, e) => RunAgent(new Dictionary<string, object> { { "op", "boot_linux_first" } }, r => Strings.T("boot.done"));
            Func<string, Label> title = t => new Label { Text = t, Dock = DockStyle.Top, Height = 32, Font = new Font("Segoe UI", 13, FontStyle.Bold) };
            Func<string, int, Label> desc = (t, h) => new Label { Text = t, Dock = DockStyle.Top, Height = h };
            page.Controls.AddRange(new Control[] {   // docked Top: last added is on top
                bootBtn, new Panel { Dock = DockStyle.Top, Height = 8 }, bootKeep, bootState, desc(Strings.T("boot.desc"), 44), title(Strings.T("boot.title")),
                new Panel { Dock = DockStyle.Top, Height = 20 },
                fastBtn, new Panel { Dock = DockStyle.Top, Height = 6 }, fastState, desc(Strings.T("fast.desc"), 62), title(Strings.T("fast.title")) });
            return page;
        }

        TabPage BuildClockTab()
        {
            var page = new TabPage(Strings.T("tab.clock")) { Padding = new Padding(16) };
            utcBtn.Text = Strings.T("clock.set_utc");
            localBtn.Text = Strings.T("clock.set_local");
            syncBtn.Text = Strings.T("clock.sync");
            utcBtn.Click += (s, e) => SetClock(true);
            localBtn.Click += (s, e) => SetClock(false);
            syncBtn.Click += (s, e) => Busy(() => Clock.Resync(),
                ok => MessageBox.Show(this, Strings.T(ok ? "clock.synced" : "clock.not_synced"), "DualPair"));
            var controls = new Control[] {
                tzLabel, new Panel { Dock = DockStyle.Top, Height = 8 }, syncBtn, new Panel { Dock = DockStyle.Top, Height = 6 },
                localBtn, new Panel { Dock = DockStyle.Top, Height = 6 }, utcBtn, new Panel { Dock = DockStyle.Top, Height = 12 },
                clockLinux, clockState,
                new Label { Text = Strings.T("clock.desc"), Dock = DockStyle.Top, Height = 44 },
                new Label { Text = Strings.T("clock.title"), Dock = DockStyle.Top, Height = 32, Font = new Font("Segoe UI", 13, FontStyle.Bold) } };
            page.Controls.AddRange(controls);   // docked Top: last added is on top
            return page;
        }

        // ------------------------------------------------------------------ actions
        void Busy<T>(Func<T> work, Action<T> done)
        {
            UseWaitCursor = true;
            busy.Text = Strings.T("busy");
            Enabled = false;
            Task.Run(work).ContinueWith(t =>
            {
                UseWaitCursor = false;
                busy.Text = "";
                Enabled = true;
                if (t.IsFaulted) MessageBox.Show(this, t.Exception.GetBaseException().Message, "DualPair", MessageBoxButtons.OK, MessageBoxIcon.Error);
                else done(t.Result);
            }, TaskScheduler.FromCurrentSynchronizationContext());
        }

        void RunAgent(Dictionary<string, object> request, Func<Dictionary<string, object>, string> message)
        {
            Busy(() => Install.Ask(opt, request), r =>
            {
                object err;
                if (r.TryGetValue("error", out err)) MessageBox.Show(this, err as string, "DualPair", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                else
                {
                    var text = message(r);
                    if (text != null) MessageBox.Show(this, text, "DualPair", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                RefreshAll();
            });
        }

        void DoImport()
        {
            var chosen = pendingList.CheckedIndices.Cast<int>().Select(i => pendingDevices[i]["address"]).ToArray();
            if (chosen.Length == 0 || pendingId == null) return;
            RunAgent(new Dictionary<string, object> { { "op", "import" }, { "message_id", pendingId }, { "addresses", chosen } }, r =>
            {
                var results = (r["results"] as object[] ?? new object[0]).Cast<Dictionary<string, object>>().ToList();
                var ok = results.Count(x => (x["result"] as string) == "imported");
                var skipped = results.Where(x => (x["result"] as string) != "imported").Select(x => (x["name"] ?? x["address"]) as string).ToList();
                var text = Strings.T("bt.imported", ok);
                if (skipped.Count > 0) text += "\n\n" + Strings.T("bt.skipped", string.Join(", ", skipped));
                return text;
            });
        }

        void SetClock(bool utc)
        {
            Busy(() => { Clock.SetRtcUtc(utc); return Clock.Resync(); }, synced =>
            {
                MessageBox.Show(this, Strings.T(utc ? "clock.done_utc" : "clock.done_local") + "\n\n" +
                                Strings.T(synced ? "clock.synced" : "clock.not_synced"), "DualPair",
                                MessageBoxButtons.OK, MessageBoxIcon.Information);
                RefreshAll();   // also tells Linux, through the status file
            });
        }

        string agentError;

        void RefreshAll()
        {
            Busy(() =>
            {
                var r = Install.Ask(opt, new Dictionary<string, object> { { "op", "status" } });
                object err;
                agentError = r.TryGetValue("error", out err) ? err as string : null;
                try { return Protocol.ReadJsonFile(Path.Combine(opt.StateDir, "status.json")); }
                catch (Exception) { return null; }
            }, s => { status = s; Fill(); if (agentError != null) busy.Text = Strings.T("agent.failed", agentError); });
        }

        // ------------------------------------------------------------------ showing the status
        static object Get(Dictionary<string, object> d, params string[] path)
        {
            object cur = d;
            foreach (var p in path)
            {
                var dict = cur as Dictionary<string, object>;
                if (dict == null || !dict.TryGetValue(p, out cur)) return null;
            }
            return cur;
        }

        void Fill()
        {
            devices.Items.Clear();
            var states = ((Get(status, "device_states") as object[]) ?? new object[0]).Cast<Dictionary<string, object>>()
                .ToDictionary(d => d["address"] as string, d => d["state"] as string);
            foreach (Dictionary<string, object> d in (Get(status, "bluetooth", "devices") as object[]) ?? new object[0])
            {
                string st;
                states.TryGetValue(d["address"] as string, out st);
                var item = new ListViewItem(new[] { (d["name"] as string) ?? (d["address"] as string), d["address"] as string,
                                                    Strings.T("kind." + d["kind"]), Strings.T("state." + (st ?? "unknown")) });
                if (st == "different" || st == "windows_only") item.ForeColor = Color.DarkOrange;
                devices.Items.Add(item);
            }
            if (devices.Items.Count == 0) devices.Items.Add(new ListViewItem(Strings.T("bt.none")) { ForeColor = Color.DimGray });

            var pending = (Get(status, "pending") as object[]) ?? new object[0];
            pendingBox.Visible = pending.Length > 0;
            pendingList.Items.Clear();
            pendingDevices.Clear();
            pendingId = null;
            if (pending.Length > 0)
            {
                var last = (Dictionary<string, object>)pending.Last();
                pendingId = last["id"] as string;
                foreach (Dictionary<string, object> d in (object[])last["devices"])
                {
                    var label = ((d["name"] as string) ?? (d["address"] as string)) + "  (" + d["address"] + ")";
                    var paired = d["paired_in_windows"] is bool && (bool)d["paired_in_windows"];
                    var same = d["same"] is bool && (bool)d["same"];
                    if (!paired) label += " - " + Strings.T("bt.pending.not_paired");
                    else if (same) label += " - " + Strings.T("bt.pending.same");
                    pendingDevices.Add(d);
                    pendingList.Items.Add(label, paired && !same);
                }
                pendingBox.Text = Strings.T("bt.pending", pendingDevices.Count);
            }

            var linux = Get(status, "linux") as Dictionary<string, object>;
            if (!(Get(status, "esp") is bool) || !(bool)Get(status, "esp")) linuxLine.Text = Strings.T("esp.none");
            else if (linux == null) linuxLine.Text = Strings.T("linux.none");
            else
            {
                DateTime t;
                var when = DateTime.TryParse(linux["written"] as string, null, System.Globalization.DateTimeStyles.AdjustToUniversal, out t)
                    ? t.ToLocalTime().ToString("g") : (linux["written"] as string);
                linuxLine.Text = Strings.T("linux.seen", linux["version"], when);
            }

            var winUtc = Get(status, "clock", "rtc_utc") is bool && (bool)Get(status, "clock", "rtc_utc");
            var linuxUtc = Get(linux, "clock", "rtc_utc");
            var text = Strings.T(winUtc ? "clock.utc" : "clock.local");
            if (linuxUtc is bool) text += "\n" + Strings.T(((bool)linuxUtc) == winUtc ? "clock.ok" : "clock.conflict");
            clockState.Text = text;
            clockState.ForeColor = linuxUtc is bool && (bool)linuxUtc != winUtc ? Color.DarkOrange : (linuxUtc is bool ? Color.DarkGreen : SystemColors.ControlText);
            clockLinux.Text = linuxUtc is bool ? Strings.T((bool)linuxUtc ? "clock.linux.utc" : "clock.linux.local") : Strings.T("clock.linux.unknown");
            utcBtn.Enabled = !winUtc;
            localBtn.Enabled = winUtc;
            tzLabel.Text = Strings.T("clock.tz", Get(status, "clock", "timezone") ?? Clock.TimeZoneName());
            FillWifi();
            FillBoot();
        }

        void FillWifi()
        {
            wifiList.Items.Clear();
            var states = ((Get(status, "wifi_states") as object[]) ?? new object[0]).Cast<Dictionary<string, object>>()
                .ToDictionary(d => d["ssid"] as string, d => d["state"] as string);
            foreach (Dictionary<string, object> n in (Get(status, "wifi", "networks") as object[]) ?? new object[0])
            {
                var ssid = n["ssid"] as string;
                string st;
                states.TryGetValue(ssid, out st);
                var item = new ListViewItem(new[] { ssid, Strings.T("wifi.sec." + n["security"]), Strings.T("wifi.state." + (st ?? "unknown")) }) { Tag = ssid };
                item.Checked = st == "windows_only" || st == "different";
                if (st == "windows_only" || st == "different") item.ForeColor = Color.DarkOrange;
                wifiList.Items.Add(item);
            }
            if (wifiList.Items.Count == 0)
            {
                var available = Get(status, "wifi", "available");
                var err = Get(status, "errors", "wifi") as string;
                string text;
                if (err == "wlan_service") text = Strings.T("wifi.err.service");
                else if (err == "no_adapter") text = Strings.T("wifi.err.adapter");
                else if (err != null) text = Strings.T("wifi.err.other", err);
                else text = Strings.T(available is bool && (bool)available ? "wifi.none_saved" : "wifi.none");
                wifiList.Items.Add(new ListViewItem(text) { ForeColor = err != null ? Color.DarkOrange : Color.DimGray });
            }

            var pending = (Get(status, "pending_wifi") as object[]) ?? new object[0];
            wifiPendingBox.Visible = pending.Length > 0;
            wifiPendingList.Items.Clear();
            wifiPendingSsids.Clear();
            wifiPendingId = null;
            if (pending.Length == 0) return;
            var last = (Dictionary<string, object>)pending.Last();
            wifiPendingId = last["id"] as string;
            foreach (Dictionary<string, object> n in (object[])last["networks"])
            {
                var st = n["state"] as string;
                var label = (n["ssid"] as string) + "  (" + Strings.T("wifi.sec." + n["security"]) + ")";
                if (st == "new") label += " - " + Strings.T("wifi.pending.new");
                else if (st == "different") label += " - " + Strings.T("wifi.pending.different");
                else if (st == "same") label += " - " + Strings.T("wifi.pending.same");
                wifiPendingSsids.Add(n["ssid"] as string);
                wifiPendingList.Items.Add(label, st != "same");
            }
            wifiPendingBox.Text = Strings.T("wifi.pending", wifiPendingSsids.Count);
        }

        void FillBoot()
        {
            var fast = Get(status, "power", "fast_startup");
            fastState.Text = Strings.T(fast is bool ? ((bool)fast ? "fast.on" : "fast.off") : "fast.unknown");
            fastState.ForeColor = fast is bool && !(bool)fast ? Color.DarkGreen : Color.DarkOrange;
            fastBtn.Text = Strings.T(fast is bool && !(bool)fast ? "fast.turn_on" : "fast.turn_off");

            var b = Get(status, "boot_state") as Dictionary<string, object>;
            var available = b != null && b["available"] is bool && (bool)b["available"];
            var linuxKnown = available && b["linux_loader"] is string;
            var firstLinux = available && b["first_is_linux"] is bool && (bool)b["first_is_linux"];
            var firstWindows = available && b["first_is_windows"] is bool && (bool)b["first_is_windows"];
            if (!available) bootState.Text = Strings.T("boot.unknown");
            else if (firstLinux) bootState.Text = Strings.T("boot.first_linux");
            else if (firstWindows) bootState.Text = Strings.T("boot.first_windows");
            else bootState.Text = Strings.T("boot.first_other", (b["first_loader"] as string) ?? "?");
            bootState.ForeColor = firstWindows ? Color.DarkOrange : (firstLinux ? Color.DarkGreen : SystemColors.ControlText);
            var keep = available && b["keep_linux_first"] is bool && (bool)b["keep_linux_first"];
            var text = !linuxKnown ? Strings.T("boot.no_linux") : Strings.T(keep ? "boot.keep_on" : "boot.keep_off");
            if (available && b["fixed_at"] is string)
            {
                DateTime t;
                if (DateTime.TryParse((string)b["fixed_at"], null, System.Globalization.DateTimeStyles.AdjustToUniversal, out t))
                    text += "\n" + Strings.T("boot.fixed", t.ToLocalTime().ToString("g"));
            }
            bootKeep.Text = text;
            bootBtn.Enabled = linuxKnown && !firstLinux;
        }
    }
}
