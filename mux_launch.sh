#!/bin/sh
# HELP: Artie Art Scraper
# ICON: artie
# GRID: Artie

. /opt/muos/script/var/func.sh

APP_BIN="app"
SETUP_APP "$APP_BIN" ""

# Define global variables
SCREEN_WIDTH=$(GET_VAR device mux/width)
SCREEN_HEIGHT=$(GET_VAR device mux/height)
SCREEN_RESOLUTION="${SCREEN_WIDTH}x${SCREEN_HEIGHT}"

# Kill background music if running
if pgrep -f "playbgm.sh" >/dev/null; then
	killall -q "playbgm.sh" "mpg123"
fi

echo app >/tmp/act_go

# Define paths using runtime mount
ARTIE_DIR="$(GET_VAR "device" "storage/rom/mount")/MUOS/application/Artie/.artie"
GPTOKEYB="$(GET_VAR "device" "storage/rom/mount")/MUOS/emulator/gptokeyb/gptokeyb2.armhf"
STATICDIR="$ARTIE_DIR/static/"
BINDIR="$ARTIE_DIR/bin"

# Export environment variables
export SDL_GAMECONTROLLERCONFIG_FILE="/usr/lib/gamecontrollerdb.txt"
export XDG_DATA_HOME="$STATICDIR"
export HOME="$STATICDIR"
export LD_LIBRARY_PATH="$BINDIR/libs.aarch64:$LD_LIBRARY_PATH"

# Launcher
cd "$ARTIE_DIR" || exit

SET_VAR "system" "foreground_process" "$APP_BIN"

# Define program and log file
program="./app"
log_file="${ARTIE_DIR}/log.txt"

# Clear log file
>"$log_file"

# Run Application with gptokeyb for controller support
# Loop to support automatic restart after OTA updates
while true; do
    $GPTOKEYB "$APP_BIN" &

    $program "${SCREEN_RESOLUTION}" >>"$log_file" 2>&1
    exit_code=$?

    kill -9 "$(pidof gptokeyb2.armhf)" 2>/dev/null

    # Exit code 42 = restart after update; anything else = normal exit
    if [ "$exit_code" -ne 42 ]; then
        break
    fi

    echo "Restarting after update..." >>"$log_file"
    sleep 1
done
