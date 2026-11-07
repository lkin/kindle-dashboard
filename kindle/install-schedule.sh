#!/bin/sh
# Run manually on Kindle, after installing KindleCron v0.2.0.
set -eu
ROOT="${KINDLE_ROOT:-/mnt/us}"
KRON="$ROOT/kron/kron"
UPDATE="$ROOT/kindle-dashboard/update.sh"
if [ ! -x "$KRON" ]; then
    echo "Missing $KRON. Install KindleCron release v0.2.0 first." >&2
    exit 1
fi
if [ ! -f "$UPDATE" ]; then echo "Missing $UPDATE" >&2; exit 1; fi
# Cloud produces at :05 UTC, Kindle fetches at :15 local time.
# Daytime-only is deliberate to permit overnight hibernation.
"$KRON" add -timeout 90s scribe-dashboard '15 7-22 * * *' /bin/sh "$UPDATE"
echo 'Added scribe-dashboard job (hourly, 07:15–22:15 device-local).'
echo 'The daemon must be running: use KindleCron KUAL > Start or start kron daemon manually.'
"$KRON" list
