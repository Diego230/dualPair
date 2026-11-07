#!/bin/bash
# Build dist/dualpair_<version>_all.deb  (needs only dpkg-deb)
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' dualpair/__init__.py)
ROOT=$(mktemp -d)
chmod 755 "$ROOT"
trap 'rm -rf "$ROOT"' EXIT

install -d "$ROOT/DEBIAN" "$ROOT/usr/lib/dualpair/dualpair" "$ROOT/usr/bin" \
    "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/scalable/apps" \
    "$ROOT/usr/share/polkit-1/actions" "$ROOT/usr/share/doc/dualpair"
install -m 644 dualpair/*.py "$ROOT/usr/lib/dualpair/dualpair/"

cat > "$ROOT/usr/lib/dualpair/dualpair-helper" <<'EOF'
#!/usr/bin/python3
# Privileged helper: started by the DualPair window through pkexec, or by dualpair-cli.
import sys
sys.path.insert(0, "/usr/lib/dualpair")
from dualpair.cli import main
sys.exit(main())
EOF
cat > "$ROOT/usr/lib/dualpair/dualpair-helper-read" <<'EOF'
#!/usr/bin/python3
# Read-only helper (scan, backups): started by the DualPair window through pkexec.
import sys
sys.path.insert(0, "/usr/lib/dualpair")
from dualpair.cli import main
sys.exit(main(read_only=True))
EOF
cat > "$ROOT/usr/bin/dualpair" <<'EOF'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/lib/dualpair")
from dualpair.gui import main
sys.exit(main())
EOF
cat > "$ROOT/usr/bin/dualpair-cli" <<'EOF'
#!/bin/sh
# Command line version. Needs root: run it with sudo.
[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"
exec /usr/lib/dualpair/dualpair-helper "$@"
EOF
chmod 755 "$ROOT/usr/lib/dualpair/dualpair-helper" "$ROOT/usr/lib/dualpair/dualpair-helper-read" "$ROOT/usr/bin/dualpair" "$ROOT/usr/bin/dualpair-cli"
install -m 644 data/io.github.dualpair.DualPair.desktop "$ROOT/usr/share/applications/"
install -m 644 data/io.github.dualpair.DualPair.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/"
install -m 644 data/io.github.dualpair.policy "$ROOT/usr/share/polkit-1/actions/"
install -m 644 README.md "$ROOT/usr/share/doc/dualpair/"

SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<EOF
Package: dualpair
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, pkexec | policykit-1, bluez, util-linux
Recommends: ntfs-3g
Maintainer: DualPair <dualpair@localhost>
Description: Use the same Bluetooth devices in Windows and Linux (dual boot)
 Copies Bluetooth pairing keys from the Windows installation on the same
 computer into BlueZ, so devices paired in Windows also work in Linux
 without pairing them again. Windows is only read, never modified.
EOF
cat > "$ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
EOF
cat > "$ROOT/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "purge" ]; then rm -rf /var/lib/dualpair; fi
EOF
chmod 755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"

mkdir -p dist
dpkg-deb --root-owner-group --build "$ROOT" "dist/dualpair_${VERSION}_all.deb" >/dev/null
echo "dist/dualpair_${VERSION}_all.deb"
