"""GTK4 / libadwaita interface. Runs as the normal user; all privileged work goes through
the helper (dualpair-cli --json) started with pkexec. Compatible with libadwaita >= 1.1."""
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
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import __version__  # noqa: E402
from .i18n import t  # noqa: E402

APP_ID = "io.github.dualpair.DualPair"
INSTALLED_HELPER = "/usr/lib/dualpair/dualpair-helper"


def helper_command() -> list[str]:
    override = os.environ.get("DUALPAIR_HELPER")   # for development and tests: no pkexec
    if override:
        return shlex.split(override)
    if os.path.exists(INSTALLED_HELPER):
        return ["pkexec", INSTALLED_HELPER]
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return ["pkexec", "env", f"PYTHONPATH={pkg_parent}", sys.executable, "-m", "dualpair"]


def run_helper(*args) -> dict:
    cmd = helper_command() + ["--json", *args]
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


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=t("app.title"))
        self.set_default_size(580, 680)
        self.checks: dict[str, Gtk.CheckButton] = {}

        header = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title=t("app.title"), subtitle="")
        header.set_title_widget(self.title)
        self.refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=t("gui.rescan"))
        self.refresh.connect("clicked", lambda *_: self.scan())
        self.refresh.set_sensitive(False)
        header.pack_start(self.refresh)
        menu = Gio.Menu()
        menu.append(t("gui.restore"), "app.restore")
        menu.append(t("gui.about"), "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.toasts = Adw.ToastOverlay(child=self.stack)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(header)
        box.append(self.toasts)
        self.set_content(box)

        self.stack.add_named(self._status_page("bluetooth-active-symbolic", t("gui.start.title"),
                                               t("gui.start.desc"), t("gui.scan"), self.scan), "start")
        busy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, valign=Gtk.Align.CENTER, vexpand=True)
        spinner = Gtk.Spinner(spinning=True, width_request=40, height_request=40)
        self.busy_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.busy_label.add_css_class("dim-label")
        busy.append(spinner)
        busy.append(self.busy_label)
        self.stack.add_named(busy, "busy")
        self.error_page = self._status_page("dialog-warning-symbolic", t("gui.error.title"), "",
                                            t("gui.retry"), self.scan)
        self.stack.add_named(self.error_page, "error")
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack.add_named(self.results_box, "results")
        self.stack.set_visible_child_name("start")

    # -- helpers -----------------------------------------------------------
    def _status_page(self, icon, title, desc, button_label, callback):
        page = Adw.StatusPage(icon_name=icon, title=title, description=desc, vexpand=True)
        btn = Gtk.Button(label=button_label, halign=Gtk.Align.CENTER)
        btn.add_css_class("pill")
        btn.add_css_class("suggested-action")
        btn.connect("clicked", lambda *_: callback())
        page.set_child(btn)
        return page

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=esc(text), timeout=6))

    def busy(self, text):
        self.busy_label.set_label(text)
        self.stack.set_visible_child_name("busy")
        self.refresh.set_sensitive(False)

    def show_error(self, err):
        self.error_page.set_description(esc(error_text(err)))
        self.stack.set_visible_child_name("error")
        self.refresh.set_sensitive(True)

    def in_thread(self, fn, done):
        def work():
            res = fn()
            GLib.idle_add(done, res)
        threading.Thread(target=work, daemon=True).start()

    # -- actions -----------------------------------------------------------
    def scan(self):
        self.busy(t("gui.scanning"))
        self.in_thread(lambda: run_helper("scan"), self.on_scan)

    def on_scan(self, res):
        if "error" in res:
            self.show_error(res["error"])
            return
        self.refresh.set_sensitive(True)
        self.title.set_subtitle(t("gui.source", source=res["windows"]["source"]))
        self.build_results(res)
        self.stack.set_visible_child_name("results")

    def sync(self, *_):
        addrs = [a for a, c in self.checks.items() if c.get_active()]
        if not addrs:
            return
        self.busy(t("gui.syncing"))
        self.in_thread(lambda: run_helper("sync", *addrs), self.on_sync)

    def on_sync(self, res):
        if "error" in res:
            self.show_error(res["error"])
            return
        self.toast(t("gui.done", n=len(res.get("applied", []))))
        self.scan()

    def restore(self):
        self.busy(t("gui.syncing"))
        self.in_thread(lambda: run_helper("restore"), self.on_restore)

    def on_restore(self, res):
        if "error" in res:
            self.show_error(res["error"])
            return
        self.toast(t("gui.restored"))
        self.scan()

    # -- results page ------------------------------------------------------
    def build_results(self, res):
        child = self.results_box.get_first_child()
        while child:
            self.results_box.remove(child)
            child = self.results_box.get_first_child()
        self.checks = {}
        self.blocked = res["windows"].get("hive_dirty", False)  # the helper would refuse to sync
        devices = res["devices"]
        todo = [d for d in devices if d["status"] in ("needs_sync", "windows_only")]
        ok = [d for d in devices if d["status"] == "in_sync"]
        lin = [d for d in devices if d["status"] == "linux_only"]

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24,
                          margin_top=18, margin_bottom=18, margin_start=12, margin_end=12)
        for note in res.get("notes", []):
            content.append(self._note(t("note." + note["code"], **note)))
        if not todo:
            page = Adw.StatusPage(icon_name="emblem-ok-symbolic", title=t("gui.all_ok.title"),
                                  description=t("gui.all_ok.desc"))
            page.add_css_class("compact")
            content.append(page)
        else:
            content.append(self._group(t("gui.group.todo"), t("gui.group.todo.desc"), todo, "todo"))
        if ok:
            content.append(self._group(t("gui.group.ok"), None, ok, "ok"))
        if lin:
            content.append(self._group(t("gui.group.linux"), None, lin, "linux"))

        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(Adw.Clamp(maximum_size=640, child=content))
        self.results_box.append(scroll)

        if todo:
            bar = Gtk.Box(halign=Gtk.Align.CENTER, margin_top=12, margin_bottom=18)
            self.sync_btn = Gtk.Button()
            self.sync_btn.add_css_class("pill")
            self.sync_btn.add_css_class("suggested-action")
            self.sync_btn.connect("clicked", self.sync)
            bar.append(self.sync_btn)
            self.results_box.append(bar)
            self._update_sync_button()

    def _note(self, text):
        box = Gtk.Box(spacing=12)
        box.add_css_class("card")
        icon = Gtk.Image(icon_name="dialog-warning-symbolic", margin_start=14, valign=Gtk.Align.START,
                         margin_top=14)
        icon.add_css_class("warning")
        label = Gtk.Label(label=text, wrap=True, xalign=0, hexpand=True,
                          margin_top=12, margin_bottom=12, margin_end=14)
        box.append(icon)
        box.append(label)
        return box

    def _group(self, title, desc, devices, kind):
        g = Adw.PreferencesGroup(title=esc(title))
        if desc:
            g.set_description(esc(desc))
        for d in devices:
            name = d.get("name") or d["address"]
            sub = f"{d['address']} · {t('kind.' + d['kind'])}"
            if kind == "todo":
                sub += f"\n{t('status.' + d['status'])}"
            elif kind == "linux":
                sub += f"\n{t('status.linux_only')}"
            row = Adw.ActionRow(title=esc(name), subtitle=esc(sub))
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
                icon = "emblem-ok-symbolic" if kind == "ok" else "dialog-information-symbolic"
                img = Gtk.Image(icon_name=icon)
                if kind == "ok":
                    img.add_css_class("success")
                row.add_prefix(img)
            g.add(row)
        return g

    def _update_sync_button(self):
        n = sum(1 for c in self.checks.values() if c.get_active())
        self.sync_btn.set_label(t("gui.sync_n", n=n) if n else t("gui.sync_none"))
        self.sync_btn.set_sensitive(n > 0 and not self.blocked)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS
                         if hasattr(Gio.ApplicationFlags, "DEFAULT_FLAGS") else Gio.ApplicationFlags.FLAGS_NONE)
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
        self.win.present()

    def about(self, *_):
        Gtk.AboutDialog(transient_for=self.win, modal=True, program_name="DualPair", version=__version__,
                        logo_icon_name=APP_ID, comments=t("gui.start.desc")).present()


def main():
    Gtk.Window.set_default_icon_name(APP_ID)
    return App().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
