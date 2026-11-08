# DualPair exchange protocol (version 1)

DualPair for Linux and DualPair for Windows work alone for simple fixes. For the rest they
exchange small JSON files through the **EFI System Partition (ESP)**: a FAT32 partition every
UEFI dual-boot PC has, readable and writable by both systems (by root / administrators only).

Folder: `<ESP>/EFI/DualPair/`

```
EFI/DualPair/
  status-linux.json      written by Linux at every scan/change (no keys)
  status-windows.json    written by Windows at every start and change (no keys)
  to-windows/<id>.json   messages from Linux, deleted by Windows once handled or expired
  to-linux/<id>.json     messages from Windows, deleted by Linux once handled or expired
```

All files are UTF-8 JSON, at most 64 KiB. Writers create `<name>.tmp` and rename it. Readers
ignore anything that does not validate, and never act on a message without the user's
confirmation, except `set_clock` (see below).

## Status files

```json
{
  "dualpair": 1,
  "system": "linux",                         // or "windows"
  "version": "0.3.0",
  "written": "2026-11-08T10:45:00Z",
  "clock": {"rtc_utc": true, "timezone": "Europe/Rome"},
  "bluetooth": {
    "available": true,
    "devices": [
      {"adapter": "C4:13:75:C0:E2:E6", "address": "FC:C2:07:3C:8A:D2", "name": "TK-MS317 5.0",
       "kind": "le", "fingerprint": "1a2b3c4d", "paired_at": "2026-11-07T10:40:00Z"}
    ]
  }
}
```

- `clock.rtc_utc`: true if this system reads the hardware clock as UTC.
Optional sections (since DualPair 0.4.0; readers must accept their absence):

```json
  "wifi": {"available": true, "networks": [
    {"ssid": "Casa", "security": "wpa-psk", "hidden": false, "fingerprint": "9f3a1b2c"}]},
  "power": {"fast_startup": true, "hibernated": false},          // Windows only
  "boot": {                                                      // written by Linux
    "linux_loader": "\\EFI\\ubuntu\\shimx64.efi", "keep_linux_first": true,
    "first_is_linux": true}
  "boot": {"first_loader": "\\EFI\\Microsoft\\Boot\\bootmgfw.efi", "fixed_at": null}   // written by Windows
```

- `wifi.networks[].security`: `open`, `wpa-psk` (WPA/WPA2-Personal) or `sae` (WPA3-Personal).
  Enterprise (802.1X) and WEP networks are not shared.
- `wifi.networks[].fingerprint`: first 8 hex digits of SHA-256 of
  `dualpair-fp-v1|wifi|<ssid>|<password>` (UTF-8; empty password for open networks).
- `power.fast_startup`: Windows Fast Startup (`HiberbootEnabled`); `null` if unknown.
  `power.hibernated`: Windows is hibernated right now (Linux side, from `hiberfil.sys`).
- `boot.keep_linux_first`: the user asked, in DualPair for Linux, to keep Linux first in the
  firmware boot order. DualPair for Windows then puts the entry whose loader is
  `boot.linux_loader` back first at each Windows start if Windows moved itself first.
- `kind`: `classic`, `le` or `dual`.
- `fingerprint`: lets each side tell whether both have the same key **without sharing it**:
  first 8 hex digits of SHA-256 of the ASCII text `dualpair-fp-v1|` followed by the key
  material, uppercase hex, joined with `|`:
  - classic: `<link_key>`
  - LE: `<ltk>|<ediv>|<rand>` (decimal numbers)
  - dual: `<link_key>|<ltk>|<ediv>|<rand>`
- `paired_at`: when this system last stored keys for the device (Windows: registry key time;
  Linux: `info` file time). Used to suggest which system paired last.

## Messages

```json
{
  "dualpair": 1,
  "id": "20261108-104500-a1b2c3",            // also the file name: <id>.json
  "type": "keys",                           // or "set_clock"
  "from": "linux",                          // or "windows"
  "created": "2026-11-08T10:45:00Z",
  "expires": "2026-11-15T10:45:00Z",        // at most 7 days after created
  "payload": { }
}
```

### `keys`

Pairing keys for devices, sent so the other system can use them.

```json
{"devices": [{
  "adapter": "C4:13:75:C0:E2:E6", "address": "FC:C2:07:3C:8A:D2", "name": "TK-MS317 5.0",
  "link_key": null,
  "le": {"ltk": "C190...", "enc_size": 16, "ediv": 38922, "rand": "11545418325281623645",
         "irk": "6DB8...", "address_type": "static", "authenticated": 0}
}]}
```

- `link_key`, `ltk`, `irk`: 32 uppercase hex digits, in the byte order Windows stores them
  (the same BlueZ uses). `rand` is a **string** (64-bit numbers do not fit in a JSON double).
- At most 64 devices. `enc_size` 7-16, `ediv` 0-65535, `authenticated` 0-4.
- Windows only updates devices that are already paired in Windows (a device must exist in
  Windows' device list; DualPair does not create it). Linux can import new devices.
- The receiver shows the devices and imports only those the user confirms, then deletes the
  message. Keys are never left on the ESP longer than needed: the sender deletes its own
  unhandled `keys` messages when it sends new ones, and expired messages are deleted.

### `wifi`

Saved Wi-Fi networks, with their passwords, sent so the other system can use them. Same rules
as `keys`: the receiver imports only what the user confirms, then deletes the message.

```json
{"networks": [{"ssid": "Casa", "security": "wpa-psk", "password": "una password", "hidden": false}]}
```

- At most 64 networks. `ssid`: 1 to 32 bytes in UTF-8, no control characters.
- `password`: `null` for `open`; otherwise 8 to 63 characters, or 64 hex digits.

### `set_fast_startup`

```json
{"enabled": false}
```

Sent by Linux when the user chooses to turn Windows Fast Startup off there. Applied by DualPair for
Windows at the next start (`HiberbootEnabled`), like `set_clock`.

### `set_clock`

```json
{"windows_utc": true}
```

Sent by Linux when the user chooses "Windows in UTC" there. DualPair for Windows applies it at
the next Windows start (`RealTimeIsUniversal`) without asking again, because the user already
chose it, and deletes the message. Only `set_clock` and `set_fast_startup` are applied this way.

## Validation

- `id`: `^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$`; the file name must be `<id>.json`.
- MAC addresses: `^([0-9A-F]{2}:){5}[0-9A-F]{2}$`.
- Names: control characters removed, at most 248 characters.
- Unknown `type`, unknown `dualpair` version, wrong `from` for the folder, `expires` in the
  past or more than 7 days after `created`: ignored (and deleted by the receiver).

## Trust

Anyone who can write the ESP is root on Linux or administrator on Windows, who can already read
the keys and Wi-Fi passwords of their own system. The protocol adds no new way to read them. It does
let one system ask the other for a fixed list of things (update keys of devices already paired
there, add Wi-Fi networks, set the clock standard, turn Fast Startup on or off, keep Linux first in
the boot order), each validated; keys and networks only with the user's confirmation.
