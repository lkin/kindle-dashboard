#!/bin/sh
# Tiny, conservative Scribe dashboard downloader. Works in the stock reader.
# Does NOT force the Kindle to wake, enable Wi-Fi, or modify Amazon files.
set -u
ROOT="${KINDLE_ROOT:-/mnt/us}"
BASE="${DASHBOARD_DIR:-$ROOT/kindle-dashboard}"
SS_DIR="${SCREEN_DIR:-$ROOT/screensavers}"
UPSTREAM="${CUSTOM_SS_DIR:-$ROOT/extensions/custom-screensaver}"
CONFIG="${DASHBOARD_CONFIG:-$BASE/config.sh}"
TARGET="$SS_DIR/dashboard.png"
TMP="$SS_DIR/.dashboard-download-$$.part"
LOCK="${DASHBOARD_LOCK:-/tmp/scribe-dashboard-update.lock}"
LOG="$BASE/update.log"
mkdir -p "$BASE" "$SS_DIR" || exit 1
log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
if ! mkdir "$LOCK" 2>/dev/null; then
    log 'skipped: update already in progress'
    exit 0
fi
cleanup() { rm -f "$TMP"; rmdir "$LOCK" 2>/dev/null || true; }
trap 'cleanup' 0
trap 'exit 1' 1 2 3 15
if [ ! -f "$CONFIG" ]; then log "configuration missing: $CONFIG"; exit 1; fi
# The config must be trusted and owned by you; never source a remote script.
. "$CONFIG"
IMAGE_URL="${IMAGE_URL:-}"
REDRAW_WHILE_ASLEEP="${REDRAW_WHILE_ASLEEP:-0}"
# Store the device credential in a separate local-only file. Never commit it.
SECRET_FILE="${DASHBOARD_SECRETS:-$BASE/secrets.sh}"
if [ ! -f "$SECRET_FILE" ]; then
    log "credentials missing: $SECRET_FILE"
    exit 1
fi
. "$SECRET_FILE"
READ_TOKEN="${READ_TOKEN:-}"
# The documented token generation is: openssl rand -hex 32
case "$READ_TOKEN" in
    ''|*[!0-9a-fA-F]*) log 'invalid READ_TOKEN: expected 64 hexadecimal characters'; exit 1;;
esac
if [ "${#READ_TOKEN}" -ne 64 ]; then
    log 'invalid READ_TOKEN length: expected 64 hexadecimal characters'
    exit 1
fi
case "$IMAGE_URL" in
    https://* ) ;;
    * ) log 'refused: set an HTTPS IMAGE_URL in config.sh'; exit 1;;
esac
case "$IMAGE_URL" in *YOUR-USERNAME*|*YOUR-REPO*|*YOUR-WORKER*|*YOUR-SUBDOMAIN*) log 'refused: placeholder URL'; exit 1;; esac

# Bound networking. Do not follow redirects or fall back to an
# unauthenticated downloader. --config - keeps the token out of curl argv.
if ! command -v curl >/dev/null 2>&1; then
    log 'curl is required for authenticated HTTPS downloads'
    exit 1
fi
if ! printf 'header = "Authorization: Bearer %s"\n' "$READ_TOKEN" | \
    curl -q --config - --fail --silent --show-error \
        --connect-timeout 8 --max-time 30 \
        --output "$TMP" "$IMAGE_URL" 2>>"$LOG"; then
    log 'download failed (network, authorization or TLS); last image kept'
    exit 0
fi

# Minimal PNG validation, no dependencies: signature, dimensions, and size.
# A server-created, valid PNG is assumed; on-device full CRC checks aren't done.
BYTES="$(wc -c < "$TMP" | tr -d ' ')"
case "$BYTES" in ''|*[!0-9]*) log 'download has invalid size'; exit 1;; esac
if [ "$BYTES" -lt 1024 ] || [ "$BYTES" -gt 4000000 ]; then
    log "rejected image size: $BYTES bytes"
    exit 1
fi
SIG="$(od -An -tx1 -N8 "$TMP" 2>/dev/null | tr -d ' \n')"
WH="$(od -An -tx1 -j16 -N8 "$TMP" 2>/dev/null | tr -d ' \n')"
if [ "$SIG" != '89504e470d0a1a0a' ] || [ "$WH" != '00000744000009b0' ]; then
    log "rejected invalid PNG or wrong size: sig=$SIG wh=$WH"
    exit 1
fi
if [ -f "$TARGET" ] && cmp -s "$TMP" "$TARGET"; then
    log 'unchanged image; no replacement needed'
    exit 0
fi
# Rename is atomic because .part and destination live in the same directory.
# Keep a previous copy in case of a renderer problem or a corrupted PNG.
if [ -f "$TARGET" ]; then cp "$TARGET" "$BASE/previous-dashboard.png" || exit 1; fi
if ! mv -f "$TMP" "$TARGET"; then
    log 'image replacement failed'
    exit 1
fi
log "updated $TARGET ($BYTES bytes)"

# Only touch the framebuffer if the existing Chengandre shield is active AND
# Kindle remains in the asleep state. Do not change powerd state here.
if [ "$REDRAW_WHILE_ASLEEP" = '1' ]; then
    STATE="$(lipc-get-prop com.lab126.powerd state 2>/dev/null | tr -d '\r\n' || true)"
    SHIELD_PID="$(cat /tmp/custom_ss_shield.pid 2>/dev/null || true)"
    case "$STATE" in
        screenSaver)
            if [ -n "$SHIELD_PID" ] && kill -0 "$SHIELD_PID" 2>/dev/null && \
               [ -x "$UPSTREAM/bin/screensaver_draw" ]; then
                # Recheck immediately before framebuffer operation.
                STATE2="$(lipc-get-prop com.lab126.powerd state 2>/dev/null | tr -d '\r\n' || true)"
                if [ "$STATE2" = 'screenSaver' ]; then
                    if "$UPSTREAM/bin/screensaver_draw" "$TARGET" >>"$LOG" 2>&1; then
                        log 'direct sleep-screen redraw completed'
                    else
                        log 'direct redraw failed; image will still be available at next sleep'
                    fi
                fi
            else
                log 'no active Chengandre shield; deferred redraw until next sleep'
            fi
            ;;
        *) log "screen state '${STATE:-unknown}'; deferred redraw until next sleep";;
    esac
fi
exit 0
