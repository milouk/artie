#!/bin/sh
echo app >/tmp/act_go

ARTIE_DIR="/mnt/mmc/MUOS/application/Artie/.artie"

cd "$ARTIE_DIR" || exit

echo "app" >/tmp/fg_proc

program="./app"
log_file="${ARTIE_DIR}/log.txt"

>"$log_file"

if ! $program >"$log_file" 2>&1; then
    echo "Error: Failed to execute $program"
    exit 1
fi
