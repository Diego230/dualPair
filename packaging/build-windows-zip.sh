#!/bin/bash
# Build dist/dualpair-windows-<version>.zip (DualPair for Windows)
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(sed -n "s/^\$Version = '\(.*\)'/\1/p" windows/DualPair.ps1 | tr -d '\r')
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/DualPair" dist
cp windows/DualPair.cmd windows/DualPair.ps1 windows/LEGGIMI.txt "$TMP/DualPair/"
OUT="$PWD/dist/dualpair-windows-${VERSION}.zip"
rm -f "$OUT"
(cd "$TMP" && zip -qrX "$OUT" DualPair)
echo "dist/dualpair-windows-${VERSION}.zip"
