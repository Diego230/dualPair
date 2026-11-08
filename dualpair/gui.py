"""GTK4 / libadwaita interface. Runs as the normal user; all privileged work goes through
the helpers (dualpair-cli --json) started with pkexec. Compatible with libadwaita >= 1.1.

One scan reads Windows and Linux once; the results are shown in two tabs:
Bluetooth (pairing keys) and Clock (how each system reads the hardware clock)."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__  # noqa: E402
from .i18n import t  # noqa: E402

APP_ID = "io.github.dualpair.DualPair"
INSTALLED_HELPER = "/usr/lib/dualpair/dualpair-helper"            # changes: password every time
INSTALLED_READ_HELPER = "/usr/lib/dualpair/dualpair-helper-read"  # reads: password remembered briefly


def helper_command(write: bool = False) -> list[str]:
    override = os.environ.get("DUALPAIR_HELPER")   # for development and tests: no pkexec
    if override:
        return shlex.split(override)
    helper = INSTALLED_HELPER if write else INSTALLED_READ_HELPER
    if os.path.exists(helper):
        return ["pkexec", helper]
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return ["pkexec", "env", f"PYTHONPATH={pkg_parent}", sys.executable, "-m", "dualpair"]


WRITE_FLAGS = ("--set", "--cancel", "--send", "--import", "--discard", "--set-fast-startup", "--linux-first", "--keep")


def is_write(args) -> bool:
    return args[0] in ("sync", "restore", "send-to-windows") or any(a in WRITE_FLAGS for a in args)


def run_helper(*args) -> dict:
    cmd = helper_command(write=is_write(args)) + ["--json", *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": {"code": "helper_failed", "params": {"detail": str(e)}}}
    if p.returncode in (126, 127) and cmd[0] == "pkexec" and not p.stdout.strip():
        return {"error": {"code": "auth_cancelled", "params": {}}}
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        detail = (p.stderr or p.stdout).strip().splitlines()[-1:] or [f"exit {p.returncode}"]
        return {"error": {"code": "helper_failed", "params": {"detail": detail[0]}}}


def error_text(err: dict) -> str:
    return t("err." + err.get("code", "helper_failed"), **(err.get("params") or {}))


def esc(s: str) -> str:
    return GLib.markup_escape_text(s or "")


def clear(box: Gtk.Box):
    child = box.get_first_child()
    while child:
        box.remove(child)
        child = box.get_first_child()


def scrolled(content: Gtk.Widget) -> Gtk.ScrolledWindow:
    sw = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
    sw.set_child(Adw.Clamp(maximum_size=640, child=content))
    return sw


def page_box() -> Gtk.Box:
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24,
                   margin_top=18, margin_bottom=18, margin_start=12, margin_end=12)


def card(text: str, icon: str = "dialog-warning-symbolic", css: str = "warning") -> Gtk.Box:
    box = Gtk.Box(spacing=12)
    box.add_css_class("card")
    img = Gtk.Image(icon_name=icon, margin_start=14, margin_top=14, valign=Gtk.Align.START)
    img.add_css_class(css)
    box.append(img)
    box.append(Gtk.Label(label=text, wrap=True, xalign=0, hexpand=True,
                         margin_top=12, margin_bottom=12, margin_end=14))
    return box


def pill(label: str, callback, suggested=True) -> Gtk.Button:
    b = Gtk.Button(label=label, halign=Gtk.Align.CENTER)
    b.add_css_class("pill")
    if suggested:
        b.add_css_class("suggested-action")
    b.connect("clicked", lambda *_: callback())
    return b


class _Tabs:
    """Wi-Fi and Startup tabs (mixed into Window)."""

    # -- Wi-Fi tab ---------------------------------------------------------
    def build_wifi(self, res):
        clear(self.wifi_box)
        w = res.get("wifi") or {}
        content = page_box()
        self.wifi_send = {}
        has_app = bool(res.get("windows_app"))
        if not w.get("available"):
            content.append(card(t("gui.wifi.no_nm"), "dialog-information-symbolic", "accent"))
            self.wifi_box.append(scrolled(content))
            return
        for m in res.get("pending_to_windows", []):
            if m["type"] == "wifi":
                content.append(self._pending_card(t("gui.wifi.pending", networks=", ".join(m.get("networks", []))), m["id"]))
        incoming = w.get("from_windows") or []
        self.wifi_page.set_needs_attention(bool(incoming))
        for m in incoming[-1:]:
            g = Adw.PreferencesGroup(title=esc(t("gui.wifi.from_windows")), description=esc(t("gui.wifi.from_windows.desc")))
            checks = {}
            for n in m["networks"]:
                row = Adw.ActionRow(title=esc(n["ssid"]),
                                    subtitle=esc(f"{t('wifi.sec.' + n['security'])} · {t('gui.wifi.in.' + n['state'])}"))
                c = Gtk.CheckButton(active=n["state"] != "same", valign=Gtk.Align.CENTER)
                row.add_prefix(c)
                row.set_activatable_widget(c)
                checks[n["ssid"]] = c
                g.add(row)
            content.append(g)
            bar = Gtk.Box(spacing=8)
            imp = Gtk.Button(label=t("gui.wifi.import"))
            imp.add_css_class("suggested-action")
            mid = m["id"]
            imp.connect("clicked", lambda *_, mid=mid, checks=checks: self.run_change(
                ["wifi", "--import", mid, *[s for s, c in checks.items() if c.get_active()]],
                lambda r: t("gui.wifi.imported", n=sum(1 for x in r.get("wifi", {}).get("results", []) if x["result"] != "same")), "wifi"))
            dis = Gtk.Button(label=t("gui.wifi.discard"))
            dis.connect("clicked", lambda *_, mid=mid: self.run_change(["wifi", "--discard", mid], lambda r: t("gui.pending.cancelled"), "wifi"))
            bar.append(imp)
            bar.append(dis)
            content.append(bar)

        nets = w.get("networks") or []
        g = Adw.PreferencesGroup(title=esc(t("gui.wifi.saved")), description=esc(t("gui.wifi.saved.desc")))
        for n in nets:
            row = Adw.ActionRow(title=esc(n["ssid"]),
                                subtitle=esc(f"{t('wifi.sec.' + n['security'])} · {t('gui.wifi.state.' + n['state'])}"))
            c = Gtk.CheckButton(active=has_app and n["state"] in ("only_linux", "different"), valign=Gtk.Align.CENTER,
                                sensitive=has_app)
            row.add_prefix(c)
            row.set_activatable_widget(c)
            self.wifi_send[n["ssid"]] = c
            g.add(row)
        if not nets:
            g.add(Adw.ActionRow(title=esc(t("gui.wifi.none"))))
        content.append(g)
        if nets:
            if has_app:
                send = Gtk.Button(label=t("gui.wifi.send"), halign=Gtk.Align.START)
                send.connect("clicked", lambda *_: self._send_wifi())
                content.append(send)
            else:
                hint = Gtk.Label(label=t("gui.wifi.need_app"), wrap=True, xalign=0)
                hint.add_css_class("dim-label")
                content.append(hint)
        only_win = w.get("only_windows") or []
        if only_win:
            g = Adw.PreferencesGroup(title=esc(t("gui.wifi.only_windows")), description=esc(t("gui.wifi.only_windows.desc")))
            for n in only_win:
                g.add(Adw.ActionRow(title=esc(n["ssid"]), subtitle=esc(t("wifi.sec." + (n.get("security") or "wpa-psk")))))
            content.append(g)
        self.wifi_box.append(scrolled(content))

    def _send_wifi(self):
        ssids = [s for s, c in self.wifi_send.items() if c.get_active()]
        if ssids:
            self.run_change(["wifi", "--send", *ssids], lambda r: t("gui.wifi.sent", n=len(ssids)), "wifi")

    # -- Startup tab -------------------------------------------------------
    def build_boot(self, res):
        clear(self.boot_box)
        content = page_box()
        p = res.get("power") or {}
        b = res.get("boot") or {}
        has_app = bool(res.get("windows_app"))
        attention = False

        g = Adw.PreferencesGroup(title=esc(t("gui.fast.title")), description=esc(t("gui.fast.desc")))
        fs = p.get("fast_startup")
        row = Adw.ActionRow(title=esc(t("gui.fast.state")))
        v = Gtk.Label(label=t("gui.fast.on" if fs else ("gui.fast.off" if fs is False else "gui.fast.unknown")), valign=Gtk.Align.CENTER)
        v.add_css_class("heading")
        row.add_suffix(v)
        g.add(row)
        content.append(g)
        if p.get("hibernated"):
            content.append(card(t("gui.fast.hibernated")))
            attention = True
        if p.get("pending") is not None:
            content.append(self._pending_card(t("gui.fast.pending_off" if p["pending"] is False else "gui.fast.pending_on"),
                                              next((m["id"] for m in res.get("pending_to_windows", []) if m["type"] == "set_fast_startup"), "")))
        elif fs:
            attention = True
            fix = Adw.PreferencesGroup()
            if has_app:
                r = Adw.ActionRow(title=esc(t("gui.fast.turn_off")), subtitle=esc(t("gui.fast.turn_off.desc")))
                btn = Gtk.Button(label=t("gui.clock.apply"), valign=Gtk.Align.CENTER)
                btn.add_css_class("suggested-action")
                btn.connect("clicked", lambda *_: self.run_change(["power", "--set-fast-startup", "off"],
                                                                   lambda r: t("gui.fast.sent"), "boot"))
                r.add_suffix(btn)
                fix.add(r)
            exp = Adw.ExpanderRow(title=esc(t("gui.fast.manual")), subtitle=esc(t("gui.fast.manual.desc")))
            lbl = Gtk.Label(label=t("gui.fast.manual.steps"), wrap=True, xalign=0, margin_top=10, margin_bottom=12,
                            margin_start=14, margin_end=14)
            exp.add_row(lbl)
            fix.add(exp)
            content.append(fix)

        g = Adw.PreferencesGroup(title=esc(t("gui.boot.title")), description=esc(t("gui.boot.desc")))
        if not b.get("available"):
            g.add(Adw.ActionRow(title=esc(t("gui.boot.unavailable"))))
            content.append(g)
        else:
            first = Adw.ActionRow(title=esc(t("gui.boot.first")))
            lab = Gtk.Label(label=b.get("first_label") or "?", valign=Gtk.Align.CENTER)
            lab.add_css_class("heading")
            first.add_suffix(lab)
            g.add(first)
            g.add(Adw.ActionRow(title=esc(t("gui.boot.linux_entry")),
                                subtitle=esc(f"{b.get('linux_label') or '?'} · {b.get('linux_loader') or ''}")))
            keep = Adw.ActionRow(title=esc(t("gui.boot.keep")),
                                 subtitle=esc(t("gui.boot.keep.desc" if has_app else "gui.boot.keep.need_app")))
            sw = Gtk.Switch(active=bool(b.get("keep_linux_first")), valign=Gtk.Align.CENTER)
            sw.connect("state-set", lambda _w, state: self.run_change(["boot", "--keep", "on" if state else "off"],
                                                                        lambda r: t("gui.boot.saved"), "boot") or False)
            keep.add_suffix(sw)
            keep.set_activatable_widget(sw)
            g.add(keep)
            content.append(g)
            if b.get("windows_fixed_at"):
                content.append(card(t("gui.boot.fixed", when=b["windows_fixed_at"]), "dialog-information-symbolic", "accent"))
            if not b.get("first_is_linux"):
                attention = True
                content.append(card(t("gui.boot.windows_first", first=b.get("first_label") or "?")))
                if b.get("grub_lists_windows") is False:
                    content.append(card(t("gui.boot.no_windows_in_grub")))
                fix = Adw.PreferencesGroup()
                r = Adw.ActionRow(title=esc(t("gui.boot.put_first")), subtitle=esc(t("gui.boot.put_first.desc")))
                btn = Gtk.Button(label=t("gui.clock.apply"), valign=Gtk.Align.CENTER)
                btn.add_css_class("suggested-action")
                btn.connect("clicked", lambda *_: self.run_change(["boot", "--linux-first", "--keep", "on"],
                                                                   lambda r: t("gui.boot.done"), "boot"))
                r.add_suffix(btn)
                fix.add(r)
                content.append(fix)
        self.boot_page.set_needs_attention(attention)
        self.boot_box.append(scrolled(content))


class Window(_Tabs, Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=t("app.title"))
        self.set_default_size(740, 720)
        self.checks: dict[str, Gtk.CheckButton] = {}
        self.blocked = False

        self.header = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title=t("app.title"), subtitle="")
        self.header.set_title_widget(self.title)
        self.refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=t("gui.rescan"))
        self.refresh.connect("clicked", lambda *_: self.scan())
        self.refresh.set_sensitive(False)
        self.header.pack_start(self.refresh)
        menu = Gio.Menu()
        menu.append(t("gui.restore"), "app.restore")
        menu.append(t("gui.about"), "app.about")
        self.header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.toasts = Adw.ToastOverlay(child=self.stack)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(self.header)
        outer.append(self.toasts)
        self.set_content(outer)

        start = Adw.StatusPage(icon_name="bluetooth-active-symbolic", title=t("gui.start.title"),
                               description=t("gui.start.desc"), vexpand=True)
        start.set_child(pill(t("gui.scan"), self.scan))
        self.stack.add_named(start, "start")

        busy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, valign=Gtk.Align.CENTER, vexpand=True)
        busy.append(Gtk.Spinner(spinning=True, width_request=40, height_request=40))
        self.busy_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.busy_label.add_css_class("dim-label")
        busy.append(self.busy_label)
        self.stack.add_named(busy, "busy")

        self.error_page = Adw.StatusPage(icon_name="dialog-warning-symbolic", title=t("gui.error.title"),
                                         vexpand=True)
        self.error_page.set_child(pill(t("gui.retry"), self.scan))
        self.stack.add_named(self.error_page, "error")

        # results: two tabs
        self.view = Adw.ViewStack()
        self.bt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.wifi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.boot_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.bt_page = self.view.add_titled(self.bt_box, "bluetooth", t("tab.bluetooth"))
        self.bt_page.set_icon_name("bluetooth-active-symbolic")
        self.wifi_page = self.view.add_titled(self.wifi_box, "wifi", t("tab.wifi"))
        self.wifi_page.set_icon_name("network-wireless-symbolic")
        self.clock_page = self.view.add_titled(self.clock_box, "clock", t("tab.clock"))
        self.clock_page.set_icon_name("preferences-system-time-symbolic")
        self.boot_page = self.view.add_titled(self.boot_box, "boot", t("tab.boot"))
        self.boot_page.set_icon_name("system-reboot-symbolic")
        self.switcher = Adw.ViewSwitcher(stack=self.view, policy=Adw.ViewSwitcherPolicy.WIDE)
        self.stack.add_named(self.view, "results")
        self.stack.set_visible_child_name("start")

    # -- plumbing ----------------------------------------------------------
    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=esc(text), timeout=6))

    def show(self, name):
        self.stack.set_visible_child_name(name)
        self.header.set_title_widget(self.switcher if name == "results" else self.title)
        self.refresh.set_sensitive(name in ("results", "error"))

    def busy(self, text):
        self.busy_label.set_label(text)
        self.show("busy")

    def show_error(self, err):
        self.error_page.set_description(esc(error_text(err)))
        self.show("error")

    def call(self, busy_text, args, on_ok):
        """Run the helper in a thread; errors go to the error page, results to on_ok."""
        self.busy(busy_text)

        def work():
            res = run_helper(*args)
            GLib.idle_add(lambda: self.show_error(res["error"]) if "error" in res else on_ok(res))
        threading.Thread(target=work, daemon=True).start()

    # -- actions -----------------------------------------------------------
    def scan(self):
        self.call(t("gui.scanning"), ["scan"], self.on_scan)

    def on_scan(self, res):
        self.title.set_subtitle(t("gui.source", source=res["windows"]["source"]))
        self.build_bluetooth(res)
        self.build_wifi(res)
        self.build_clock(res)
        self.build_boot(res)
        self.show("results")

    def sync(self, *_):
        addrs = [a for a, c in self.checks.items() if c.get_active()]
        if addrs:
            self.call(t("gui.syncing"), ["sync", *addrs], self.after_change(
                lambda r: t("gui.done", n=len(r.get("applied", [])))))

    def restore(self):
        self.call(t("gui.syncing"), ["restore"], self.after_change(lambda r: t("gui.restored")))

    def set_linux_clock(self, value):
        self.call(t("gui.syncing"), ["clock", "--set", value], self.after_change(
            lambda r: t("gui.clock.applied"), tab="clock"))

    def run_change(self, args, message, tab):
        self.call(t("gui.syncing"), args, self.after_change(message, tab=tab))

    def after_change(self, message, tab=None):
        def done(res):
            self.toast(message(res))
            self.scan()
            if tab:
                self.view.set_visible_child_name(tab)
        return done

    # -- Bluetooth tab -----------------------------------------------------
    def build_bluetooth(self, res):
        clear(self.bt_box)
        self.checks = {}
        self.send_checks = {}
        self.blocked = res["windows"].get("hive_dirty", False)  # the helper would refuse to sync
        self.windows_app = res.get("windows_app")
        devices = res["devices"]
        # paired last on Linux: the device now holds Linux's key, so copying Windows' key would break it
        to_windows = [d for d in devices if d["status"] == "needs_sync" and d.get("newer") == "linux"]
        todo = [d for d in devices if d["status"] in ("needs_sync", "windows_only") and d not in to_windows]
        ok = [d for d in devices if d["status"] == "in_sync"]
        lin = [d for d in devices if d["status"] == "linux_only"]
        self.bt_page.set_needs_attention(bool(todo or to_windows))

        content = page_box()
        if res.get("source_kind") == "export":
            content.append(card(t("gui.source.export"), "dialog-information-symbolic", "accent"))
        for note in res.get("notes", []):
            content.append(card(t("note." + note["code"], **note)))
        for m in res.get("pending_to_windows", []):
            if m["type"] == "keys":
                content.append(self._pending_card(t("gui.pending.keys", devices=", ".join(m.get("devices", []))), m["id"]))
        if not todo and not to_windows and devices:
            page = Adw.StatusPage(icon_name="object-select-symbolic", title=t("gui.all_ok.title"),
                                  description=t("gui.all_ok.desc"))
            page.add_css_class("compact")
            content.append(page)
        if todo:
            content.append(self._group(t("gui.group.todo"), t("gui.group.todo.desc"), todo, "todo"))
        if to_windows:
            content.append(self._send_group(to_windows))
        if ok:
            content.append(self._group(t("gui.group.ok"), None, ok, "ok"))
        if lin:
            content.append(self._group(t("gui.group.linux"), None, lin, "linux"))
        content.append(self._windows_app_line())
        self.bt_box.append(scrolled(content))

        if todo:
            bar = Gtk.Box(halign=Gtk.Align.CENTER, margin_top=12, margin_bottom=18)
            self.sync_btn = pill("", self.sync)
            bar.append(self.sync_btn)
            self.bt_box.append(bar)
            self._update_sync_button()

    def _windows_app_line(self):
        w = self.windows_app
        text = t("gui.winapp.seen", version=w.get("version") or "?", written=w.get("written") or "?") if w \
            else t("gui.winapp.none")
        label = Gtk.Label(label=text, wrap=True, xalign=0)
        label.add_css_class("dim-label")
        label.add_css_class("caption")
        return label

    def _pending_card(self, text, mid):
        box = card(text, "mail-send-symbolic", "accent")
        btn = Gtk.Button(label=t("gui.pending.cancel"), valign=Gtk.Align.CENTER, margin_end=12)
        btn.connect("clicked", lambda *_: self.call(t("gui.syncing"), ["pending", "--cancel", mid],
                                                     self.after_change(lambda r: t("gui.pending.cancelled"))))
        box.append(btn)
        return box

    def _send_group(self, devices):
        g = Adw.PreferencesGroup(title=esc(t("gui.group.to_windows")), description=esc(t("gui.group.to_windows.desc")))
        for d in devices:
            row = Adw.ActionRow(title=esc(d.get("name") or d["address"]),
                                subtitle=esc(f"{d['address']} · {t('kind.' + d['kind'])}\n{t('newer.linux')}"))
            check = Gtk.CheckButton(active=bool(self.windows_app), valign=Gtk.Align.CENTER,
                                    sensitive=bool(self.windows_app))
            row.add_prefix(check)
            row.set_activatable_widget(check)
            self.send_checks[d["address"]] = check
            g.add(row)
        if self.windows_app:
            btn = Gtk.Button(label=t("gui.send"), halign=Gtk.Align.START, margin_top=10)
            btn.connect("clicked", lambda *_: self.send_to_windows())
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.append(g)
            box.append(btn)
            return box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(g)
        hint = Gtk.Label(label=t("gui.send.need_app"), wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)
        return box

    def send_to_windows(self):
        addrs = [a for a, c in self.send_checks.items() if c.get_active()]
        if addrs:
            self.call(t("gui.syncing"), ["send-to-windows", *addrs],
                      self.after_change(lambda r: t("gui.sent", n=len(r.get("sent", [])))))

    def _group(self, title, desc, devices, kind):
        g = Adw.PreferencesGroup(title=esc(title))
        if desc:
            g.set_description(esc(desc))
        for d in devices:
            sub = f"{d['address']} · {t('kind.' + d['kind'])}"
            if kind == "todo":
                sub += f"\n{t('status.' + d['status'])}"
            elif kind == "linux":
                sub += f"\n{t('status.linux_only')}"
            row = Adw.ActionRow(title=esc(d.get("name") or d["address"]), subtitle=esc(sub))
            if kind == "todo":
                check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
                check.connect("toggled", lambda *_: self._update_sync_button())
                row.add_prefix(check)
                row.set_activatable_widget(check)
                self.checks[d["address"]] = check
                if d.get("experimental"):
                    tag = Gtk.Label(label=t("experimental"), valign=Gtk.Align.CENTER,
                                    tooltip_text=t("gui.experimental.tip"))
                    tag.add_css_class("caption")
                    tag.add_css_class("dim-label")
                    row.add_suffix(tag)
            else:
                img = Gtk.Image(icon_name="object-select-symbolic" if kind == "ok" else "dialog-information-symbolic")
                if kind == "ok":
                    img.add_css_class("success")
                row.add_prefix(img)
            g.add(row)
        return g

    def _update_sync_button(self):
        n = sum(1 for c in self.checks.values() if c.get_active())
        self.sync_btn.set_label(t("gui.sync_n", n=n) if n else t("gui.sync_none"))
        self.sync_btn.set_sensitive(n > 0 and not self.blocked)

    # -- Clock tab ---------------------------------------------------------
    def build_clock(self, res):
        clear(self.clock_box)
        c = res.get("clock")
        if not c:
            return
        state = c["state"]
        self.clock_page.set_needs_attention(state in ("conflict", "conflict_reverse"))
        content = page_box()
        if res["windows"].get("hive_dirty"):
            content.append(card(t("note.hive_dirty")))

        g = Adw.PreferencesGroup(title=esc(t("gui.clock.title")), description=esc(t("gui.clock.desc")))
        for label, value, sub in ((t("gui.clock.linux"), c["linux"], None),
                                  (t("gui.clock.windows"), c["windows"], c.get("windows_timezone"))):
            row = Adw.ActionRow(title=esc(label))
            if sub:
                row.set_subtitle(esc(sub))
            v = Gtk.Label(label=t("clock.std." + value), valign=Gtk.Align.CENTER)
            v.add_css_class("heading")
            row.add_suffix(v)
            g.add(row)
        content.append(g)

        ok = state in ("ok_utc", "ok_local")
        content.append(card(t("clock.state." + state),
                            "object-select-symbolic" if ok else "dialog-warning-symbolic",
                            "success" if ok else "warning"))

        pending = next((m for m in res.get("pending_to_windows", []) if m["type"] == "set_clock"), None)
        if pending:
            content.append(self._pending_card(
                t("gui.clock.pending_utc" if pending.get("windows_utc") else "gui.clock.pending_local"), pending["id"]))
        if state == "conflict" and not pending:
            fixes = Adw.PreferencesGroup(title=esc(t("gui.clock.fixes")))
            if c.get("windows_app"):
                row = Adw.ActionRow(title=esc(t("gui.clock.fix_win.title")), subtitle=esc(t("gui.clock.fix_win.next_boot")))
                btn = Gtk.Button(label=t("gui.clock.apply"), valign=Gtk.Align.CENTER)
                btn.add_css_class("suggested-action")
                btn.connect("clicked", lambda *_: self.set_linux_clock("windows-utc"))
                row.add_suffix(btn)
                fixes.add(row)
            fixes.add(self._windows_fix_row(t("gui.clock.fix_win.manual") if c.get("windows_app")
                                            else t("gui.clock.fix_win.title"), t("gui.clock.fix_win.desc"), c))
            fixes.add(self._apply_row(t("gui.clock.fix_linux.title"), t("gui.clock.fix_linux.desc"), "linux-local"))
            content.append(fixes)
        elif state == "conflict_reverse" and not pending:
            fixes = Adw.PreferencesGroup(title=esc(t("gui.clock.fixes")))
            fixes.add(self._apply_row(t("gui.clock.linux_utc.title"), t("gui.clock.linux_utc.desc"), "linux-utc"))
            content.append(fixes)
        elif state == "ok_local" and not pending:
            more = Adw.PreferencesGroup()
            more.add(self._windows_fix_row(t("gui.clock.to_utc.title"), t("gui.clock.to_utc.desc"), c))
            content.append(more)
        self.clock_box.append(scrolled(content))

    def _apply_row(self, title, desc, value):
        row = Adw.ActionRow(title=esc(title), subtitle=esc(desc))
        btn = Gtk.Button(label=t("gui.clock.apply"), valign=Gtk.Align.CENTER)
        btn.connect("clicked", lambda *_: self.set_linux_clock(value))
        row.add_suffix(btn)
        return row

    def _windows_fix_row(self, title, desc, c):
        row = Adw.ExpanderRow(title=esc(title), subtitle=esc(desc))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_top=12, margin_bottom=14, margin_start=14, margin_end=14)
        for text in (t("gui.clock.fix_win.step1"), t("gui.clock.fix_win.step2")):
            box.append(Gtk.Label(label=text, wrap=True, xalign=0))
        cmd_row = Gtk.Box(spacing=8)
        cmd = Gtk.Label(wrap=True, wrap_mode=2, xalign=0, hexpand=True, selectable=True, use_markup=True)
        cmd.set_markup('<span insert_hyphens="false">%s</span>' % esc(c["windows_command"]))  # no "-" when wrapping
        cmd.add_css_class("monospace")
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text=t("gui.clock.copy"), valign=Gtk.Align.CENTER)
        copy.connect("clicked", lambda *_: self.copy(c["windows_command"]))
        cmd_row.append(cmd)
        cmd_row.append(copy)
        box.append(cmd_row)
        after = Gtk.Label(label=t("gui.clock.after"), wrap=True, xalign=0)
        after.add_css_class("dim-label")
        box.append(after)
        row.add_row(box)
        return row

    def copy(self, text):
        provider = Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", GLib.Bytes.new(text.encode()))
        self.get_clipboard().set_content(provider)
        self.toast(t("gui.clock.copied"))


class App(Adw.Application):
    def __init__(self):
        flags = getattr(Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE)
        super().__init__(application_id=APP_ID, flags=flags)
        self.win = None
        for name, cb in (("restore", lambda *_: self.win.restore()), ("about", self.about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)

    def do_activate(self):
        if self.win is None:
            self.win = Window(self)
            if os.environ.get("DUALPAIR_AUTOSCAN"):
                self.win.scan()
            if os.environ.get("DUALPAIR_TAB"):
                self.win.view.set_visible_child_name(os.environ["DUALPAIR_TAB"])
        self.win.present()

    def about(self, *_):
        Gtk.AboutDialog(transient_for=self.win, modal=True, program_name="DualPair", version=__version__,
                        logo_icon_name=APP_ID, comments=t("gui.start.desc")).present()


def main():
    Gtk.Window.set_default_icon_name(APP_ID)
    return App().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
