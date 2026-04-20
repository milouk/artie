#!/bin/sh
# HELP: Artie Art Scraper
# ICON: artie
# GRID: Artie

# STAGE_OVERLAY=0 disables muOS's automatic libmustage SDL overlay injection.
# That overlay hooks SDL render calls and can cause black-screen hangs on
# Jacaranda. We set this before sourcing func.sh so SETUP_APP sees it.
STAGE_OVERLAY=0 . /opt/muos/script/var/func.sh

APP_BIN="app"

# ---------------------------------------------------------------------------
# Resolve the application directory the way muOS itself would.
# SETUP_APP is available on Jacaranda and newer; it sets up the standard
# /run/muos/storage/application abstraction. On older muOS versions we fall
# back to resolving paths relative to this script (works on SD1 or SD2).
# ---------------------------------------------------------------------------
if command -v SETUP_APP >/dev/null 2>&1; then
    SETUP_APP "$APP_BIN" ""
    APP_DIR="/run/muos/storage/application/Artie"
    if [ ! -d "$APP_DIR" ]; then
        # SETUP_APP didn't provide the expected location; fall back.
        APP_DIR="$(dirname "$(realpath "$0")")"
    fi
else
    # Legacy muOS (pre-Jacaranda). SETUP_SDL_ENVIRONMENT sets up scaler/rotation.
    if command -v SETUP_SDL_ENVIRONMENT >/dev/null 2>&1; then
        SETUP_SDL_ENVIRONMENT
    fi
    APP_DIR="$(dirname "$(realpath "$0")")"
fi

ARTIE_DIR="$APP_DIR/.artie"
STATICDIR="$ARTIE_DIR/static/"
BINDIR="$ARTIE_DIR/bin"

# Kill background music if running (frees the audio device for SDL_mixer)
if pgrep -f "playbgm.sh" >/dev/null; then
    killall -q "playbgm.sh" "mpg123"
fi

echo app >/tmp/act_go

# ---------------------------------------------------------------------------
# Environment.
# pygame-ce's PyPI wheel bundles a headless SDL2 (offscreen/dummy only).
# muOS ships a proper SDL2 at /usr/lib/libSDL2-2.0.so.0 with the 'mali'
# video driver compiled in. We LD_PRELOAD it so pygame picks it up instead
# of its own headless copy, which otherwise leaves the screen blank.
# ---------------------------------------------------------------------------
export SDL_GAMECONTROLLERCONFIG_FILE="/usr/lib/gamecontrollerdb.txt"
export SDL_ASSERT=always_ignore
export XDG_DATA_HOME="$STATICDIR"
export HOME="$STATICDIR"
export LD_LIBRARY_PATH="$BINDIR/libs.aarch64:$LD_LIBRARY_PATH"

SYSTEM_SDL2="/usr/lib/libSDL2-2.0.so.0"
if [ -f "$SYSTEM_SDL2" ]; then
    export LD_PRELOAD="$SYSTEM_SDL2:$LD_PRELOAD"
fi

cd "$ARTIE_DIR" || exit 1

if command -v SET_VAR >/dev/null 2>&1; then
    SET_VAR "system" "foreground_process" "$APP_BIN"
fi

# Device resolution
if command -v GET_VAR >/dev/null 2>&1; then
    SCREEN_WIDTH=$(GET_VAR device mux/width 2>/dev/null)
    SCREEN_HEIGHT=$(GET_VAR device mux/height 2>/dev/null)
fi
SCREEN_WIDTH="${SCREEN_WIDTH:-640}"
SCREEN_HEIGHT="${SCREEN_HEIGHT:-480}"
SCREEN_RESOLUTION="${SCREEN_WIDTH}x${SCREEN_HEIGHT}"

program="./app"
log_file="${ARTIE_DIR}/log.txt"

# Fresh log each launch
>"$log_file"

# Run Application — pygame/SDL2 handles controller input directly.
# Exit code 42 = restart after OTA update; anything else = normal exit.
while true; do
    $program "${SCREEN_RESOLUTION}" >>"$log_file" 2>&1
    exit_code=$?

    if [ "$exit_code" -ne 42 ]; then
        break
    fi

    echo "Restarting after update..." >>"$log_file"
    sleep 1
done
