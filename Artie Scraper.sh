#!/bin/sh
echo app >/tmp/act_go

ARTIE_DIR="$DC_STO_ROM_MOUNT/MUOS/application/.artie"

cd "$ARTIE_DIR" || exit

echo "app" >/tmp/fg_proc

./app
