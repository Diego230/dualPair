# DualPair

[![CI](https://github.com/Diego230/dualPair/actions/workflows/ci.yml/badge.svg)](https://github.com/Diego230/dualPair/actions/workflows/ci.yml)

Fixes what breaks when Windows and Linux share a PC (dual boot). Two apps, one per system: each works alone for simple fixes.

- **Bluetooth**: use the same devices in both systems without pairing them again every time you switch.
- **Clock**: stop the time being wrong in Windows after using Linux (and the other way round).

**Status: prototype (0.2.0).** Tested on one real dual-boot PC (see [Tested on](#tested-on)). Not yet tested on many machines.

## Why devices stop working

When you pair a device, the computer and the device agree on a secret key. Windows and Linux each create their own key for the same Bluetooth adapter, but the device only remembers the last one. So whichever system paired last works, and the other one is rejected.

DualPair fixes this by copying Windows' keys into Linux. Both systems then use the same key.

## The clock problem

The PC has one hardware clock (RTC), shared by both systems. Linux reads it as UTC, Windows as local time, so after switching the time is off by the time zone offset (1-2 hours in Italy). DualPair shows how each system reads it (**Clock** tab) and offers both fixes:

- **Windows in UTC (recommended).** Done once in Windows: registry value `RealTimeIsUniversal=1`. Use **DualPair for Windows** (*Use UTC*), or the `reg add` command the Linux app shows with a copy button.
- **Linux in local time.** One click in the Linux app (`timedatectl set-local-rtc 1`). systemd does not recommend it: the time can be wrong for a while after daylight-saving changes.

If you later put Windows in UTC after having set Linux to local time, the app notices and offers to put Linux back to UTC.

## DualPair for Windows

The `windows/` folder (or `dualpair-windows-<version>.zip` from the releases) holds a small Windows app: double-click `DualPair.cmd`, accept the administrator prompt. For now it handles the clock (*Use UTC*, *Back to local time*, *Sync the time now*). It also works from the command line: `DualPair.ps1 -Status`, `-SetUtc`, `-SetLocal`, `-Resync`, `-Json`.

## Tested on

One dual-boot PC (Windows + Ubuntu, Windows on NVMe, no BitLocker), November 2026:

| Device | Type | Case | Result |
|---|---|---|---|
| TK-MS317 5.0 mouse | Bluetooth LE, static address, legacy pairing | Keys already copied by hand | Detected as *Works on both* |
| JBL LIVE460NC headphones | Classic | *Keys differ* → synced | Works in Linux, then Windows, then Linux again, without pairing again |
| JBL Go 3 speaker | Classic | *Only in Windows* → imported (experimental) | Not tested yet |

Windows was found and read automatically. After syncing, audio devices may need one click on *Connect* in Linux: when they turn on, they reconnect to the last computer they were connected to, so after using Windows that is Windows. This is not a key problem: Connect works without pairing again.

## How to use it

1. In **Windows**, pair your devices as usual.
2. Shut Windows down completely: hold **Shift** while clicking *Shut down*, or turn off *Fast Startup*.
3. Start **Linux**, open **DualPair** and click **Scan**. Enter your password when asked.
4. Check the devices you want and click **Sync**. Move or use the devices to reconnect.

If you later pair a device again (on either system), pair it in Windows and run DualPair again.

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
sudo dualpair-cli clock --set linux-local   # or linux-utc
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
packaging/build-windows-zip.sh             # -> dist/dualpair-windows-<version>.zip
python3 -m unittest discover -s tests -t .
python3.12 tests/make_fixtures.py          # rebuild test hives (needs python3-hivex)
```

To try the window on fake data without root:

```
DUALPAIR_HELPER="python3 -m dualpair --win tests/fixtures/SYSTEM --bluez-dir /tmp/bt --state-dir /tmp/state" \
python3 -c "from dualpair.gui import main; main()"
```

## Continuous integration

On every push and pull request, GitHub Actions runs the tests on Ubuntu 22.04 and 24.04, builds the `.deb`, installs it and runs a quick check on the installed package. A Windows job runs DualPair for Windows on a real Windows machine (status, *Use UTC*, back to local time). The `.deb` and the Windows zip can be downloaded from the run page (artifacts `dualpair-deb` and `dualpair-windows`).

To publish a release with the `.deb` and the Windows zip attached, push a version tag:

```
git tag v0.2.0
git push origin v0.2.0
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
| `dualpair/gui.py` | GTK4 / libadwaita window (Bluetooth and Clock tabs) |
| `windows/` | DualPair for Windows (PowerShell + Windows Forms) |
| `dualpair/i18n.py` | English and Italian strings |

License: not chosen yet.
