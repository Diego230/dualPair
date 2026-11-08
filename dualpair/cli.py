# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Diego Buono
"""Command line interface. The GUI runs this as root through pkexec, with --json."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, bluez, boot, clock, mailbox, sync, wifi
from .errors import DualPairError
from .i18n import t
from .windows import load_windows


def _parser():
    p = argparse.ArgumentParser(prog="dualpair-cli",
                                description="Copy Bluetooth pairing keys from Windows to Linux (dual boot).")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--win", metavar="PATH", help="Windows SYSTEM hive file or mounted Windows folder")
    p.add_argument("--bluez-dir", default=bluez.BLUEZ_DIR, help=argparse.SUPPRESS)
    p.add_argument("--state-dir", default=sync.STATE_DIR, help=argparse.SUPPRESS)
    p.add_argument("--mailbox-dir", default=None, help=argparse.SUPPRESS)
    p.add_argument("--nm-dir", default=wifi.NM_DIR, help=argparse.SUPPRESS)
    p.add_argument("--no-restart", action="store_true", help="do not restart the bluetooth service")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="show devices and what needs syncing")
    s = sub.add_parser("sync", help="copy keys from Windows")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="every device that needs it")
    g.add_argument("addresses", nargs="*", default=[], metavar="MAC")
    s.add_argument("--dry-run", action="store_true", help="show the new files, change nothing")
    s.add_argument("--force", action="store_true", help="sync even if Windows was not fully shut down")
    s.add_argument("--show-keys", action="store_true", help="with --dry-run: print the keys too (not via pkexec)")
    c = sub.add_parser("clock", help="check (or change) how Linux and Windows read the hardware clock")
    c.add_argument("--set", choices=("linux-local", "linux-utc", "windows-utc", "windows-local"),
                   help="linux-*: change Linux now; windows-*: ask DualPair for Windows to change it at the next start")
    w = sub.add_parser("send-to-windows", help="send Linux keys to DualPair for Windows (devices paired last on Linux)")
    w.add_argument("addresses", nargs="+", metavar="MAC")
    wf = sub.add_parser("wifi", help="saved Wi-Fi networks, compared with Windows")
    wg = wf.add_mutually_exclusive_group()
    wg.add_argument("--send", nargs="+", metavar="SSID", help="send these networks (with passwords) to DualPair for Windows")
    wg.add_argument("--import", dest="import_id", metavar="ID", help="import networks sent by DualPair for Windows")
    wg.add_argument("--discard", metavar="ID", help="delete networks sent by DualPair for Windows without importing")
    wf.add_argument("ssids", nargs="*", metavar="SSID", help="with --import: only these networks")
    po = sub.add_parser("power", help="Windows Fast Startup")
    po.add_argument("--set-fast-startup", choices=("on", "off"),
                    help="ask DualPair for Windows to turn Fast Startup on or off at the next start")
    bo = sub.add_parser("boot", help="firmware boot order")
    bo.add_argument("--linux-first", action="store_true", help="put Linux first in the boot order now")
    bo.add_argument("--keep", choices=("on", "off"),
                    help="keep Linux first: DualPair for Windows restores it after Windows updates")
    pe = sub.add_parser("pending", help="messages waiting for DualPair for Windows")
    pe.add_argument("--cancel", metavar="ID", help="withdraw a message")
    sub.add_parser("backups", help="list backups")
    r = sub.add_parser("restore", help="undo a sync (default: the latest)")
    r.add_argument("backup", nargs="?")
    return p


def _print_clock(c: dict):
    print(t("cli.clock", linux=t("clock.std." + c["linux"]), windows=t("clock.std." + c["windows"])))
    print("  " + t("clock.state." + c["state"]))
    if c["state"] == clock.CONFLICT:
        print("  " + t("cli.clock.fix_windows", command=c["windows_command"]))
        print("  " + t("cli.clock.fix_linux"))
    elif c["state"] == clock.CONFLICT_REVERSE:
        print("  " + t("cli.clock.fix_reverse"))
    if c.get("pending") is not None:
        print("  " + t("cli.clock.pending"))


def _print_scan(s: sync.Scan):
    print(t("cli.source", source=s.windows.source))
    for n in s.notes:
        print("! " + t("note." + n["code"], **n))
    if not s.plans:
        print(t("cli.none"))
        return
    for p in s.plans:
        exp = f" [{t('experimental')}]" if p.experimental else ""
        newer = f" ({t('newer.' + p.newer)})" if p.newer else ""
        print(f"  {p.address}  {(p.name or '?')[:28]:28}  {t('kind.' + p.kind):14}  {t('status.' + p.status)}{exp}{newer}")
    if any(p.status in sync.ACTIONABLE for p in s.plans):
        print(t("cli.hint_sync"))


READ_ONLY_COMMANDS = ("scan", "backups", "clock", "pending", "wifi", "power", "boot")


def check_allowed(a, read_only: bool):
    """Started through pkexec, the helper runs as root on behalf of a user who may only be
    trusted with the fixed job: no custom paths (they would let the caller pick what root reads,
    writes or deletes) and no printing of keys."""
    writes = any(getattr(a, k, None) for k in ("set", "cancel", "send", "import_id", "discard", "set_fast_startup",
                                                "linux_first", "keep"))
    if read_only and (a.cmd not in READ_ONLY_COMMANDS or writes):
        raise DualPairError("read_only", command=a.cmd)
    if "PKEXEC_UID" in os.environ:
        custom = [opt for opt, used in (("--win", a.win), ("--bluez-dir", a.bluez_dir != bluez.BLUEZ_DIR),
                                        ("--state-dir", a.state_dir != sync.STATE_DIR),
                                        ("--mailbox-dir", a.mailbox_dir),
                                        ("--nm-dir", a.nm_dir != wifi.NM_DIR),
                                        ("--show-keys", getattr(a, "show_keys", False))) if used]
        if custom:
            raise DualPairError("option_not_allowed", option=", ".join(custom))


def load(a, mb) -> "WindowsData":
    """Windows data: from the Windows disk if Linux can read it, otherwise (BitLocker) from what
    DualPair for Windows exported to the ESP."""
    try:
        return load_windows(a.win)
    except DualPairError as e:
        if e.code not in ("bitlocker", "no_windows") or a.win:
            raise
        data = mailbox.windows_from_mailbox(mb)
        if data is None:
            raise
        return data


def wifi_status(nm_dir: str) -> dict:
    nets = wifi.networks(nm_dir)
    return {"available": nets is not None,
            "networks": [{"ssid": n.network.ssid, "security": n.network.security, "hidden": n.network.hidden,
                          "fingerprint": n.network.fingerprint()} for n in (nets or [])]}


def boot_status(state_dir: str) -> dict | None:
    st = boot.state(boot.read(), boot.load_settings(state_dir))
    if not st["available"]:
        return None
    return {"linux_loader": st["linux_loader"], "keep_linux_first": st["keep_linux_first"],
            "first_is_linux": st["first_is_linux"]}


def publish(mb, s: "sync.Scan | None", bluez_root: str, nm_dir: str = wifi.NM_DIR, state_dir: str = sync.STATE_DIR):
    """Tell DualPair for Windows how Linux stands (no keys). Best effort."""
    if not mb:
        return
    try:
        devices = []
        for ad in bluez.adapters(bluez_root):
            for d in bluez.devices(ad, bluez_root).values():
                if d.paired:
                    k = d.keys()
                    devices.append({"adapter": ad, "address": d.address, "name": d.name, "kind": d.kind,
                                    "fingerprint": mailbox.fingerprint(k.link_key, k.le.ltk if k.le else None,
                                                                       k.le.ediv if k.le else None,
                                                                       k.le.rand if k.le else None),
                                    "paired_at": mailbox.iso(d.paired_at)})
        mailbox.write_status(mb, not clock.linux_rtc_local(), clock.linux_timezone(), devices,
                             bool(bluez.adapters(bluez_root)), wifi=wifi_status(nm_dir),
                             boot=boot_status(state_dir) if bluez_root == bluez.BLUEZ_DIR else None)
    except OSError:
        pass


def pending_list(mb) -> list[dict]:
    out = []
    for m in mailbox.list_messages(mb, "windows"):
        item = {"id": m["id"], "type": m["type"], "created": m["created"]}
        if m["type"] == "keys":
            item["devices"] = [d.name or d.address for d in m["_devices"]]
        elif m["type"] == "wifi":
            item["networks"] = [n.ssid for n in m["_networks"]]
        elif m["type"] == "set_clock":
            item["windows_utc"] = m["payload"]["windows_utc"]
        else:
            item["enabled"] = m["payload"]["enabled"]
        out.append(item)
    return out


def windows_app(mb) -> dict | None:
    st = mailbox.read_status(mb, "windows")
    if not st:
        return None
    bt = st.get("bluetooth") or {}
    return {"version": st.get("version"), "written": st.get("written"), "clock": st.get("clock"),
            "devices": len(bt.get("devices") or [])}


def wifi_info(mb, nm_dir: str) -> dict:
    nets = wifi.networks(nm_dir)
    info = {"available": nets is not None}
    info.update(wifi.compare([n.network for n in (nets or [])], mailbox.read_status(mb, "windows")))
    saved = {n.network.ssid: n.network for n in (nets or [])}
    info["from_windows"] = [{"id": m["id"], "created": m["created"], "networks": [
        {"ssid": n.ssid, "security": n.security,
         "state": "new" if n.ssid not in saved else ("same" if saved[n.ssid].fingerprint() == n.fingerprint() else "different")}
        for n in m["_networks"]]} for m in mailbox.list_messages(mb, "linux") if m["type"] == "wifi"]
    return info


def power_info(win, mb) -> dict:
    st = mailbox.read_status(mb, "windows") or {}
    fs = win.fast_startup
    if fs is None and isinstance((st.get("power") or {}).get("fast_startup"), bool):
        fs = st["power"]["fast_startup"]
    pending = next((m["payload"]["enabled"] for m in mailbox.list_messages(mb, "windows")
                    if m["type"] == "set_fast_startup"), None)
    return {"fast_startup": fs, "hibernated": win.hibernated, "pending": pending,
            "windows_app": bool(st)}


def boot_info(state_dir: str, mb) -> dict:
    st = boot.state(boot.read(), boot.load_settings(state_dir))
    win = (mailbox.read_status(mb, "windows") or {}).get("boot") or {}
    st["windows_fixed_at"] = win.get("fixed_at")
    return st


def clock_info(win, mb) -> dict:
    c = clock.status(win)
    c["pending"] = next((m["windows_utc"] for m in pending_list(mb) if m["type"] == "set_clock"), None)
    c["windows_app"] = mailbox.read_status(mb, "windows") is not None
    return c


def run(a) -> int:
    restart = not a.no_restart and a.bluez_dir == bluez.BLUEZ_DIR
    if a.cmd == "backups":
        res = sync.list_backups(a.state_dir)
        if a.json:
            print(json.dumps({"backups": res}))
        else:
            print("\n".join(f"{b['id']}  {', '.join(b['devices'])}" for b in res) or t("cli.no_backups"))
        return 0
    if a.cmd == "restore":
        res = sync.restore(a.backup, a.state_dir, restart, a.bluez_dir)
        with mailbox.open_mailbox(a.mailbox_dir, disabled=a.bluez_dir != bluez.BLUEZ_DIR) as mb:
            publish(mb, None, a.bluez_dir, a.nm_dir, a.state_dir)
        print(json.dumps(res) if a.json else t("cli.restored", backup=res["restored"]))
        return 0

    # with a fake BlueZ folder (tests) the real ESP is left alone unless --mailbox-dir is given
    with mailbox.open_mailbox(a.mailbox_dir, create=True, disabled=a.bluez_dir != bluez.BLUEZ_DIR) as mb:
        if a.cmd == "pending":
            if a.cancel:
                if not mb:
                    raise DualPairError("no_esp")
                mailbox.delete(mb, "windows", a.cancel)
            res = pending_list(mb)
            print(json.dumps({"pending": res}) if a.json else
                  ("\n".join(f"{m['id']}  {m['type']}  {', '.join(m.get('devices', []))}" for m in res)
                   or t("cli.no_pending")))
            return 0

        if a.cmd == "wifi":
            if a.send:
                if not mb:
                    raise DualPairError("no_esp")
                saved = {n.network.ssid: n.network for n in (wifi.networks(a.nm_dir) or [])}
                missing = [x for x in a.send if x not in saved]
                if missing:
                    raise DualPairError("unknown_network", ssid=", ".join(missing))
                mid = mailbox.send(mb, "windows", "wifi", {"networks": [mailbox.wifi_to_json(saved[x]) for x in a.send]})
                res = {"sent": a.send, "message_id": mid}
            elif a.import_id or a.discard:
                mid = a.import_id or a.discard
                msg = next((m for m in mailbox.list_messages(mb, "linux") if m["type"] == "wifi" and m["id"] == mid), None)
                if msg is None:
                    raise DualPairError("unknown_message", id=mid)
                res = {"results": []}
                if a.import_id:
                    chosen = [n for n in msg["_networks"] if not a.ssids or n.ssid in a.ssids]
                    res["results"] = wifi.import_networks(chosen, a.nm_dir, a.state_dir,
                                                          reload=a.nm_dir == wifi.NM_DIR)
                mailbox.delete(mb, "linux", mid)        # passwords do not stay on the ESP
            else:
                res = wifi_info(mb, a.nm_dir)
            publish(mb, None, a.bluez_dir, a.nm_dir, a.state_dir)
            print(json.dumps({"wifi": res}) if a.json else json.dumps(res, indent=1, ensure_ascii=False))
            return 0

        if a.cmd == "boot":
            settings = boot.load_settings(a.state_dir)
            if a.linux_first:
                info = boot.read()
                if not info:
                    raise DualPairError("boot_unknown")
                boot.put_linux_first(info)
            if a.keep:
                settings["keep_linux_first"] = a.keep == "on"
                boot.save_settings(a.state_dir, settings)
            if a.linux_first or a.keep:
                publish(mb, None, a.bluez_dir, a.nm_dir, a.state_dir)
            res = boot_info(a.state_dir, mb)
            print(json.dumps({"boot": res}) if a.json else json.dumps(res, indent=1))
            return 0

        if a.cmd == "power":
            win = load(a, mb)
            if a.set_fast_startup:
                if not mb:
                    raise DualPairError("no_esp")
                mailbox.send(mb, "windows", "set_fast_startup", {"enabled": a.set_fast_startup == "on"})
            res = power_info(win, mb)
            print(json.dumps({"power": res}) if a.json else json.dumps(res, indent=1))
            return 0

        if a.cmd == "clock":
            win = load(a, mb)
            if a.set in ("linux-local", "linux-utc"):
                clock.set_linux(local=a.set == "linux-local")
                publish(mb, None, a.bluez_dir, a.nm_dir, a.state_dir)
            elif a.set:
                if not mb:
                    raise DualPairError("no_esp")
                mailbox.send(mb, "windows", "set_clock", {"windows_utc": a.set == "windows-utc"})
            c = clock_info(win, mb)
            if a.json:
                print(json.dumps({"clock": c}))
            else:
                _print_clock(c)
            return 0

        s = sync.scan(load(a, mb), a.bluez_dir)

        if a.cmd == "send-to-windows":
            if not mb:
                raise DualPairError("no_esp")
            wanted = {x.upper() for x in a.addresses}
            plans = [p for p in s.plans if p.address in wanted and p.linux and p.linux.paired]
            missing = sorted(wanted - {p.address for p in plans})
            if missing:
                raise DualPairError("unknown_device", address=", ".join(missing))
            devices = []
            for p in plans:
                k = p.linux.keys()
                k.adapter = p.adapter_windows or p.adapter_linux   # Windows' name for the adapter
                devices.append(mailbox.device_to_json(k))
            mid = mailbox.send(mb, "windows", "keys", {"devices": devices})
            res = {"sent": [p.to_dict() for p in plans], "message_id": mid}
            print(json.dumps(res) if a.json else t("cli.sent", n=len(plans)))
            return 0

        if a.cmd == "scan":
            publish(mb, s, a.bluez_dir, a.nm_dir, a.state_dir)
            if a.json:
                print(json.dumps(dict(s.to_dict(), clock=clock_info(s.windows, mb), windows_app=windows_app(mb),
                                      pending_to_windows=pending_list(mb),
                                      source_kind="export" if s.windows.export_id else "disk",
                                      wifi=wifi_info(mb, a.nm_dir), power=power_info(s.windows, mb),
                                      boot=boot_info(a.state_dir, mb)
                                      if a.bluez_dir == bluez.BLUEZ_DIR or os.environ.get("DUALPAIR_TEST_EFIBOOTMGR")
                                      else {"available": False})))
            else:
                _print_scan(s)
                print()
                _print_clock(clock_info(s.windows, mb))
                for m in pending_list(mb):
                    print("  " + t("cli.pending_item", id=m["id"], type=m["type"]))
            return 0

        res = sync.apply(s, None if a.all else a.addresses, a.state_dir, restart, a.force, a.dry_run, a.show_keys)
        if res["applied"] and not a.dry_run:
            if s.windows.export_id and mb:   # keys imported: do not leave them on the ESP
                mailbox.delete(mb, "linux", s.windows.export_id)
            publish(mb, None, a.bluez_dir, a.nm_dir, a.state_dir)
    if a.json:
        print(json.dumps(res))
    elif a.dry_run:
        for d in res["applied"]:
            print(f"# {d['adapter_linux']}/{d['address']}/info ({d['name'] or ''})\n{d['info']}")
    elif res["applied"]:
        print(t("cli.applied", n=len(res["applied"]), backup=res["backup_id"]))
    else:
        print(t("cli.nothing"))
    return 0


def main(argv=None, read_only: bool = False) -> int:
    a = _parser().parse_args(argv)
    try:
        check_allowed(a, read_only)
        return run(a)
    except Exception as e:  # noqa: BLE001 - always answer the GUI in JSON, never with a traceback
        err = e if isinstance(e, DualPairError) else DualPairError("internal", detail=f"{type(e).__name__}: {e}")
        if a.json:
            print(json.dumps({"error": err.to_dict()}))
        else:
            print(str(err), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
