# Code signing policy

Free code signing on Windows provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/). *(Applies once the project has been accepted by SignPath
Foundation; until then the Windows files are not signed.)*

## What is signed

Only files built by this repository's GitHub Actions workflow
([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) from the source code in this repository:

- `DualPair.exe` (DualPair for Windows)
- `DualPair-Setup-<version>.exe` (its installer, built with Inno Setup)

Nothing built elsewhere, and no third-party binaries, are signed with this certificate.

## Team roles

| Role | Members |
|---|---|
| Committers and reviewers | [Diego Buono](https://github.com/Diego230) |
| Approvers (every signing request is approved by hand) | [Diego Buono](https://github.com/Diego230) |

All members use multi-factor authentication for GitHub and SignPath.

## Privacy

This program will not transfer any information to other networked systems unless specifically
requested by the user or the person installing or operating it.

DualPair works only on the computer it runs on. The two apps (Linux and Windows) exchange data
through a folder on the computer's own EFI system partition (`EFI/DualPair`); see
[protocol.md](protocol.md). Bluetooth keys and Wi-Fi passwords are written there only when the user
asks to send them, and are deleted once imported or after at most 7 days.

## System changes

DualPair changes system settings only when the user asks for it, in the app, after a description of
the change: Bluetooth pairing keys, Wi-Fi profiles, how Windows reads the hardware clock
(`RealTimeIsUniversal`), Windows Fast Startup (`HiberbootEnabled`) and the firmware boot order. The
installer lists what it installs before installing (a scheduled task that runs as SYSTEM, a protected
folder in `%ProgramData%\DualPair`, a logon notice) and the uninstaller removes all of it.
