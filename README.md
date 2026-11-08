# DualPair

[![CI](https://github.com/Diego230/dualPair/actions/workflows/ci.yml/badge.svg)](https://github.com/Diego230/dualPair/actions/workflows/ci.yml)

Fixes what breaks when Windows and Linux share a PC (dual boot). Two apps, one per system: **DualPair for Linux** and **DualPair for Windows**. Each works alone for simple fixes; together they handle the rest, exchanging data through the EFI partition both systems can read.

- **Bluetooth**: use the same devices in both systems without pairing them again every time you switch.
- **Wi-Fi**: networks saved in one system can be used in the other, without typing the passwords again.
- **Clock**: stop the time being wrong in Windows after using Linux (and the other way round).
- **Fast Startup**: detect Windows Fast Startup (which leaves the Windows disk locked and out of date for Linux) and turn it off.
- **Boot order**: put Linux back first when a Windows update moves Windows first, and keep it there.

**Status: prototype (0.4.0).** Tested on one real dual-boot PC (see [Tested on](#tested-on)). Not yet tested on many machines.

## Why devices stop working

When you pair a device, the computer and the device agree on a secret key. Windows and Linux each create their own key for the same Bluetooth adapter, but the device only remembers the last one. So whichever system paired last works, and the other one is rejected.

DualPair makes both systems use the same key:

- **Paired last in Windows** → DualPair for Linux copies Windows' key into Linux (alone: it reads the Windows disk).
- **Paired last in Linux** → DualPair for Linux sends the key to DualPair for Windows, which imports it after you confirm (both apps).
- **Windows disk encrypted with BitLocker** → *Export for Linux* in DualPair for Windows, then DualPair for Linux imports the keys (both apps).

## The clock problem

The PC has one hardware clock (RTC), shared by both systems. Linux reads it as UTC, Windows as local time, so after switching the time is off by the time zone offset (1-2 hours in Italy). DualPair shows how each system reads it (**Clock** tab) and offers both fixes:

- **Windows in UTC (recommended).** Registry value `RealTimeIsUniversal=1`. With both apps: click *Apply* in the Linux app and DualPair for Windows applies it at the next Windows start. Otherwise *Use UTC* in DualPair for Windows, or the `reg add` command the Linux app shows with a copy button.
- **Linux in local time.** One click in the Linux app (`timedatectl set-local-rtc 1`). systemd does not recommend it: the time can be wrong for a while after daylight-saving changes.

If you later put Windows in UTC after having set Linux to local time, the app notices and offers to put Linux back to UTC.

## Wi-Fi networks

Each app lists the networks saved in its system (NetworkManager on Linux, Windows profiles) and compares them with the other system's by fingerprint, so passwords never leave their system just for the comparison. To share networks, select them and click *Send to Windows* / *Send selected to Linux*: the other app shows them at the next start and imports only those you confirm (for a network already saved with another password, the old Linux file is backed up first). Open, WPA/WPA2-Personal and WPA3-Personal networks are shared; enterprise (802.1X) and WEP networks are not, and on Linux neither are networks whose password is kept in a user keyring.

## Fast Startup and boot order

- **Fast Startup**: when it is on, shutting Windows down actually hibernates it; Linux then sees the Windows disk as locked and may read old data. DualPair for Linux reads the setting from the Windows registry and checks whether Windows is hibernated right now (`hiberfil.sys`); it can ask DualPair for Windows to turn Fast Startup off at the next Windows start. DualPair for Windows also has a button for it.
- **Boot order**: DualPair for Linux shows what starts first (`efibootmgr`) and can put Linux back first. With *Keep Linux first* on, DualPair for Windows checks the firmware boot order at every Windows start (`bcdedit /enum firmware`, read without depending on the Windows language) and puts Linux back first if an update moved Windows first. Before putting Linux first, DualPair for Linux checks that the GRUB menu has a Windows entry and says how to add it if not.

## DualPair for Windows

Download `DualPair-Setup-<version>.exe` from the releases (or the `dualpair-windows` artifact of a CI run) and install it. It needs nothing else: it uses .NET Framework 4.8, already part of Windows 10 and 11. Until the installer is signed, Windows shows *Windows protected your PC*: click *More info*, then *Run anyway*. With **Smart App Control** on (Windows Security → App & browser control), unsigned programs are blocked outright: turn it off while trying DualPair, until signed builds are available.

- **Bluetooth tab**: devices paired in Windows and whether Linux has the same key (compared by fingerprint, keys never leave their system for this); keys sent from Linux, to import after confirming; *Export for Linux*; *Undo last import*.
- **Wi-Fi tab**: saved networks and whether Linux has them with the same password; networks sent from Linux, to import after confirming; *Send selected to Linux*.
- **Clock tab**: how Windows and Linux read the hardware clock; *Use UTC*, *Back to local time*, *Sync the time now*.
- **Startup tab**: Fast Startup on/off; the firmware boot order and *Put Linux first now*.
- At logon, a small notice when Linux sent keys or networks, or when DualPair applied something at startup (clock, Fast Startup, boot order).

How it is built: the window runs as administrator; the Bluetooth keys are readable only by SYSTEM, so a scheduled task (`DualPair\Agent`, SYSTEM) does that work. It runs at every Windows start (to apply clock requests from Linux and publish the status) and when the window asks. The window talks to it through `%ProgramData%\DualPair`, which only SYSTEM and administrators can write. Uninstalling removes the task and that folder.

## Working together

The two apps exchange small JSON files in `EFI/DualPair/` on the EFI System Partition: a status file each (no keys, no passwords: versions, clock, Wi-Fi and key fingerprints, Fast Startup, boot order) and messages (`keys`, `wifi`, `set_clock`, `set_fast_startup`) that expire after 7 days and are deleted once handled. Keys are imported only after the user confirms them in the receiving app, and Windows only updates devices already paired in Windows. Details: [docs/protocol.md](docs/protocol.md).

## Tested on

One dual-boot PC (Windows + Ubuntu, Windows on NVMe, no BitLocker), November 2026:

| Device | Type | Case | Result |
|---|---|---|---|
| TK-MS317 5.0 mouse | Bluetooth LE, static address, legacy pairing | Keys already copied by hand | Detected as *Works on both* |
| JBL LIVE460NC headphones | Classic | *Keys differ* → synced | Works in Linux, then Windows, then Linux again, without pairing again |
| JBL Go 3 speaker | Classic | *Only in Windows* → imported (experimental) | Not tested yet |

Also checked on the same PC (DualPair 0.4):

| Feature | Result |
|---|---|
| Wi-Fi | 7 networks (WPA3 and open) listed on both sides; the Linux (NetworkManager) and Windows fingerprints match, so both apps report *same password* |
| Clock | *Use UTC* in DualPair for Windows; both systems now read the hardware clock as UTC, the time stays right after switching |
| Exchange through the EFI partition | each app shows the other's status (versions, clock, Bluetooth and Wi-Fi fingerprints) |
| Fast Startup | read as *off* from the Windows registry |
| Boot order | Linux entry (`\efi\ubuntu\grubx64.efi`) found and first; *Keep Linux first* turned on |

Not tried on a real PC yet: changing the boot order, importing Wi-Fi networks, restoring Linux first after a Windows update.

Windows was found and read automatically. After syncing, audio devices may need one click on *Connect* in Linux: when they turn on, they reconnect to the last computer they were connected to, so after using Windows that is Windows. This is not a key problem: Connect works without pairing again.

## How to use it

1. In **Windows**, pair your devices as usual.
2. Shut Windows down completely: hold **Shift** while clicking *Shut down*, or turn off *Fast Startup*.
3. Start **Linux**, open **DualPair** and click **Scan**. Enter your password when asked.
4. Check the devices you want and click **Sync**. Move or use the devices to reconnect.

If you later pair a device again in Windows, run DualPair again. If you pair it again in Linux, DualPair shows it under *Paired last on Linux*: with DualPair for Windows installed, click *Send to Windows*.

To undo the last sync, open the menu and choose **Undo last sync**.

## How it works

- Linux reads the Windows registry file (`Windows/System32/config/SYSTEM`) straight from the Windows partition. The partition is mounted **read-only**: **Windows is never modified**.
- The keys are in `ControlSet00N\Services\BTHPORT\Parameters\Keys`. Classic Bluetooth devices have a link key. Bluetooth LE devices have LTK, EDIV, ERand and IRK.
- DualPair writes them into BlueZ (`/var/lib/bluetooth/<adapter>/<device>/info`). It keeps everything else in the existing file and backs up every file it changes to `/var/lib/dualpair/backups`.
- The window runs as your user. Reading and writing system files is done by small helpers started with `pkexec` (see [Security](#security)).

Device states:

| State | Meaning | Action |
|---|---|---|
| Keys differ | Paired on both systems, but Linux has an old key | Copied from Windows |
| Only in Windows | Not paired in Linux | Imported into Linux |
| Works on both | Same key on both systems | Nothing to do |
| Only in Linux | Not paired in Windows | Pair it in Windows, then sync |

## Security

**Where keys are stored.** Windows keeps them in the `SYSTEM` registry file, readable by anyone who can read the disk unless BitLocker is on. Linux keeps them in `/var/lib/bluetooth`, readable by root. Both store them unencrypted. DualPair adds one more copy: backups in `/var/lib/dualpair/backups` (root only).

**What a stolen key allows.** It works only for that computer and that device. Someone nearby who has it can decrypt the traffic (keystrokes, for a keyboard), or pretend to be the device or the computer by also copying its Bluetooth address. Getting the keys already requires root on Linux, administrator rights on Windows, or physical access to an unencrypted disk. The real protection is disk encryption on both systems (BitLocker and LUKS).

**What DualPair does to stay out of the way:**

- Windows is mounted read-only (`ro,nosuid,nodev,noexec`) and never modified. The registry file is parsed by a pure-Python, read-only parser: a malformed file can make it fail, not run code.
- Two helpers, two polkit actions. `dualpair-helper-read` (scan, list backups) can only read and never prints keys; the password is remembered for a few minutes. `dualpair-helper` (sync, restore) asks for the password every time.
- Started through `pkexec`, the helpers refuse every option that changes paths (`--win`, `--bluez-dir`, `--state-dir`) and `--show-keys`. Otherwise a program running as your user could steer them to read, write or delete files as root.
- The EFI partition is writable only by root and administrators, who can already read their own system's keys. Through it, each system can only ask the other a fixed list of things (update keys of devices already paired there, add Wi-Fi networks, set the clock standard, turn Fast Startup on or off, keep Linux first in the boot order); messages are validated and expire, and keys and networks need the user's confirmation. The status files carry fingerprints, not keys or passwords. Wi-Fi passwords exported on Windows go through `%ProgramData%\\DualPair` (SYSTEM and administrators only) and are deleted right away.
- Restore only accepts backups whose names, paths and target folder are exactly what DualPair writes: no `..`, no symlinks, no other folders.
- `--dry-run` hides keys (`Key=<hidden>`). `--show-keys` works only for root through `sudo`, never through `pkexec`.
- Device names from Windows are stripped of control characters, so a name cannot add lines to BlueZ files.
- Old backups hold old keys: only the newest 5 are kept, and none older than 30 days (except the newest).
- Files are written atomically, with mode 600, without following symlinks.

The test data in this repository uses fake keys.

## Command line

```
sudo dualpair-cli scan                 # list devices and their state
sudo dualpair-cli sync --all           # copy every key that needs it
sudo dualpair-cli sync FC:C2:07:3C:8A:D2
sudo dualpair-cli sync --all --dry-run # show the files it would write (keys hidden; add --show-keys to see them)
sudo dualpair-cli backups
sudo dualpair-cli restore              # undo the last sync
sudo dualpair-cli --win /path/to/SYSTEM scan   # use a specific hive file or Windows folder
sudo dualpair-cli clock                # how Linux and Windows read the hardware clock
sudo dualpair-cli clock --set linux-local   # or linux-utc; windows-utc/windows-local: ask DualPair for Windows
sudo dualpair-cli send-to-windows A4:BF:C6:D0:E5:FF   # keys of a device paired last on Linux
sudo dualpair-cli pending [--cancel ID]  # what is waiting for Windows
sudo dualpair-cli wifi [--send SSID... | --import ID [SSID...] | --discard ID]
sudo dualpair-cli power [--set-fast-startup off|on]
sudo dualpair-cli boot [--linux-first] [--keep on|off]
```

Add `--json` for machine-readable output.

## Known limitations

- **BitLocker**: if the Windows disk is encrypted, Linux cannot read it. DualPair says so; unlock the disk first. A Windows companion that exports the keys is planned.
- **Fast Startup / hibernation**: if Windows was not fully shut down, the registry file can be out of date. DualPair detects this and refuses to sync (`--force` overrides it in the CLI).
- **New classic devices** (paired only in Windows, e.g. headphones) are imported with a guessed key type and marked *experimental*. Devices already paired in Linux keep their key type and are reliable.
- **Devices that change address on every pairing** (some BLE devices): they show up as a new device. Importing it works, and the old Linux entry stays as *Only in Linux*.
- **IRK byte order**: copied as stored by Windows, like most existing tools do. It only matters for devices that use private addresses.
- Linux only, BlueZ only. Packaged as a `.deb` for Ubuntu 22.04+ and Debian 12+ (needs libadwaita ≥ 1.1).

## Building and testing

```
packaging/build-deb.sh                     # -> dist/dualpair_<version>_all.deb
python3 -m unittest discover -s tests -t .
python3.12 tests/make_fixtures.py          # rebuild test hives (needs python3-hivex)
```

DualPair for Windows (on Windows, with the .NET SDK; the installer needs Inno Setup 6.3+):

```
dotnet build windows/app/DualPair.csproj -c Release
dotnet build windows/tests/Tests.csproj -c Release
windows\tests\bin\Release\net48\DualPair.Tests.exe tests\protocol_vectors.json   # as administrator
iscc windows\installer\DualPair.iss                                            # -> dist\DualPair-Setup-<version>.exe
```

On Linux, Mono can compile and run the Windows tests (its registry is emulated):
`mcs -out:Tests.exe -main:DualPair.Tests.Tests -r:System.Windows.Forms -r:System.Drawing -r:System.Web.Extensions -r:System.ServiceProcess windows/app/*.cs windows/tests/Tests.cs && mono Tests.exe tests/protocol_vectors.json`

To try the window on fake data without root:

```
DUALPAIR_HELPER="python3 -m dualpair --win tests/fixtures/SYSTEM --bluez-dir /tmp/bt --state-dir /tmp/state" \
python3 -c "from dualpair.gui import main; main()"
```

## Continuous integration

On every push and pull request, GitHub Actions:

- runs the Python tests on Ubuntu 22.04 and 24.04, builds the `.deb`, installs it and checks the installed package;
- on Windows, builds DualPair for Windows, runs its tests (test registry path, never the real keys), cross-checks the protocol with the Python side in both directions, builds the installer, installs it, has the SYSTEM task answer a request, and uninstalls it.

The `.deb` and the Windows installer can be downloaded from the run page (artifacts `dualpair-deb` and `dualpair-windows`).

To publish a release with the `.deb` and the Windows installer attached, create a release on GitHub (CI attaches the files when it is published), or push a version tag:

```
git tag v0.4.0
git push origin v0.4.0
```

## Layout

| File | What it does |
|---|---|
| `dualpair/regf.py` | Read-only parser for Windows registry hives (pure Python) |
| `dualpair/windows.py` | Finds the Windows partition and reads the Bluetooth keys |
| `dualpair/bluez.py` | Reads and writes BlueZ `info` files |
| `dualpair/sync.py` | Compares, syncs, backs up, restores |
| `dualpair/cli.py` | Command line and privileged helper (`--json`) |
| `dualpair/clock.py` | Hardware clock check and Linux-side fix |
| `dualpair/mailbox.py` | Exchange with DualPair for Windows through the EFI partition |
| `dualpair/wifi.py` | NetworkManager Wi-Fi networks |
| `dualpair/boot.py` | Firmware boot order (efibootmgr), GRUB check |
| `dualpair/gui.py` | GTK4 / libadwaita window (Bluetooth and Clock tabs) |
| `windows/app/` | DualPair for Windows (C#, .NET Framework 4.8, Windows Forms) |
| `windows/installer/` | Inno Setup installer |
| `windows/tests/`, `tests/cross_check.py` | Windows tests and Python ↔ C# protocol cross-check |
| `docs/protocol.md` | Exchange protocol between the two apps |
| `dualpair/i18n.py` | English and Italian strings |

## Code signing and privacy

See the [code signing policy](docs/code-signing-policy.md). DualPair does not use the network.

## License

Copyright © 2026 Diego Buono.

DualPair is free software: you can redistribute it and/or modify it under the terms of the [GNU General Public License](LICENSE) as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; see the license for details.
