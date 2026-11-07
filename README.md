# DualPair

[![CI](https://github.com/Diego230/dualPair/actions/workflows/ci.yml/badge.svg)](https://github.com/Diego230/dualPair/actions/workflows/ci.yml)

Use the same Bluetooth devices in Windows and Linux on a dual-boot PC, without pairing them again every time you switch.

**Status: prototype (0.1.0).** Tested on fake data and on the logic used for one real device (a BLE mouse). Not yet tested on many real machines.

## Why devices stop working

When you pair a device, the computer and the device agree on a secret key. Windows and Linux each create their own key for the same Bluetooth adapter, but the device only remembers the last one. So whichever system paired last works, and the other one is rejected.

DualPair fixes this by copying Windows' keys into Linux. Both systems then use the same key.

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
- The window runs as your user. Reading and writing system files is done by a small helper started with `pkexec`.

Device states:

| State | Meaning | Action |
|---|---|---|
| Keys differ | Paired on both systems, but Linux has an old key | Copied from Windows |
| Only in Windows | Not paired in Linux | Imported into Linux |
| Works on both | Same key on both systems | Nothing to do |
| Only in Linux | Not paired in Windows | Pair it in Windows, then sync |

## Command line

```
sudo dualpair-cli scan                 # list devices and their state
sudo dualpair-cli sync --all           # copy every key that needs it
sudo dualpair-cli sync FC:C2:07:3C:8A:D2
sudo dualpair-cli sync --all --dry-run # show the files it would write
sudo dualpair-cli backups
sudo dualpair-cli restore              # undo the last sync
sudo dualpair-cli --win /path/to/SYSTEM scan   # use a specific hive file or Windows folder
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

To try the window on fake data without root:

```
DUALPAIR_HELPER="python3 -m dualpair --win tests/fixtures/SYSTEM --bluez-dir /tmp/bt --state-dir /tmp/state" \
python3 -c "from dualpair.gui import main; main()"
```

## Continuous integration

On every push and pull request, GitHub Actions runs the tests on Ubuntu 22.04 and 24.04, builds the `.deb`, installs it and runs a quick check on the installed package. The `.deb` can be downloaded from the run page (artifact `dualpair-deb`).

To publish a release with the `.deb` attached, push a version tag:

```
git tag v0.1.0
git push origin v0.1.0
```

## Layout

| File | What it does |
|---|---|
| `dualpair/regf.py` | Read-only parser for Windows registry hives (pure Python) |
| `dualpair/windows.py` | Finds the Windows partition and reads the Bluetooth keys |
| `dualpair/bluez.py` | Reads and writes BlueZ `info` files |
| `dualpair/sync.py` | Compares, syncs, backs up, restores |
| `dualpair/cli.py` | Command line and privileged helper (`--json`) |
| `dualpair/gui.py` | GTK4 / libadwaita window |
| `dualpair/i18n.py` | English and Italian strings |

License: not chosen yet.
