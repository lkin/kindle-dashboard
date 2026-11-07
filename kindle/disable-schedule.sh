#!/bin/sh
set -eu
KRON="${KINDLE_ROOT:-/mnt/us}/kron/kron"
if [ -x "$KRON" ]; then
    "$KRON" remove scribe-dashboard
else
    echo 'KindleCron binary missing; no job removed' >&2
fi
