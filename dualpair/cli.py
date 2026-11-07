"""Command line interface. The GUI runs this as root through pkexec, with --json."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, bluez, sync
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
    sub.add_parser("backups", help="list backups")
    r = sub.add_parser("restore", help="undo a sync (default: the latest)")
    r.add_argument("backup", nargs="?")
    return p


def _print_scan(s: sync.Scan):
    print(t("cli.source", source=s.windows.source))
    for n in s.notes:
        print("! " + t("note." + n["code"], **n))
    if not s.plans:
        print(t("cli.none"))
        return
    for p in s.plans:
        exp = f" [{t('experimental')}]" if p.experimental else ""
        print(f"  {p.address}  {(p.name or '?')[:28]:28}  {t('kind.' + p.kind):14}  {t('status.' + p.status)}{exp}")
    if any(p.status in sync.ACTIONABLE for p in s.plans):
        print(t("cli.hint_sync"))


READ_ONLY_COMMANDS = ("scan", "backups")


def check_allowed(a, read_only: bool):
    """Started through pkexec, the helper runs as root on behalf of a user who may only be
    trusted with the fixed job: no custom paths (they would let the caller pick what root reads,
    writes or deletes) and no printing of keys."""
    if read_only and a.cmd not in READ_ONLY_COMMANDS:
        raise DualPairError("read_only", command=a.cmd)
    if "PKEXEC_UID" in os.environ:
        custom = [opt for opt, used in (("--win", a.win), ("--bluez-dir", a.bluez_dir != bluez.BLUEZ_DIR),
                                        ("--state-dir", a.state_dir != sync.STATE_DIR),
                                        ("--show-keys", getattr(a, "show_keys", False))) if used]
        if custom:
            raise DualPairError("option_not_allowed", option=", ".join(custom))


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
        print(json.dumps(res) if a.json else t("cli.restored", backup=res["restored"]))
        return 0

    s = sync.scan(load_windows(a.win), a.bluez_dir)
    if a.cmd == "scan":
        if a.json:
            print(json.dumps(s.to_dict()))
        else:
            _print_scan(s)
        return 0

    res = sync.apply(s, None if a.all else a.addresses, a.state_dir, restart, a.force, a.dry_run, a.show_keys)
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
