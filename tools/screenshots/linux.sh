#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Screenshots of the Linux app on invented demo data, for the README.
# Needs: xvfb, xdotool, imagemagick, python3-hivex, GTK 4 + libadwaita for Python.
# Usage: tools/screenshots/linux.sh [output dir] [language]   (default: docs/screenshots, en)
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
OUT=${1:-$ROOT/docs/screenshots}
LANG_CODE=${2:-en}
PY=${PYTHON:-python3}
DEMO=$(mktemp -d)
trap 'rm -rf "$DEMO"' EXIT
mkdir -p "$OUT"
"$PY" "$HERE/demo.py" build "$DEMO" >/dev/null

for tab in bluetooth wifi clock boot; do
    xvfb-run -a -s "-screen 0 1000x900x24" sh -c '
        cd "$1"
        LANGUAGE=$5 LANG=C.UTF-8 GDK_BACKEND=x11 GSK_RENDERER=cairo DUALPAIR_AUTOSCAN=1 DUALPAIR_TAB=$2 \
        DUALPAIR_HELPER="$6 $3/demo.py helper $4" "$6" -m dualpair.gui &
        app=$!
        for i in $(seq 1 40); do
            win=$(xdotool search --name "^DualPair$" 2>/dev/null | tail -1) && [ -n "$win" ] && break
            sleep 0.5
        done
        sleep 4
        import -window "$win" "$7/linux-$2.png"
        kill $app' _ "$ROOT" "$tab" "$HERE" "$DEMO" "$LANG_CODE" "$PY" "$OUT"
    echo "$OUT/linux-$tab.png"
done
