#!/bin/sh
# Optional: move other screensavers aside (NEVER delete them).
set -eu
ROOT="${KINDLE_ROOT:-/mnt/us}"
SRC="$ROOT/screensavers"
DEST="$ROOT/screensavers-backup-$(date '+%Y%m%d-%H%M%S')"
if [ ! -f "$SRC/dashboard.png" ]; then
    echo 'Fetch dashboard.png first; nothing changed.' >&2
    exit 1
fi
mkdir -p "$DEST"
MOVED=0
for file in "$SRC"/*; do
    [ -f "$file" ] || continue
    case "$file" in
        "$SRC/dashboard.png") continue;;
        *.[pP][nN][gG]|*.[jJ][pP][gG]|*.[jJ][pP][eE][gG])
            mv "$file" "$DEST/"
            MOVED=$((MOVED + 1))
            ;;
    esac
done
printf 'Moved %s alternate images into %s\n' "$MOVED" "$DEST"
