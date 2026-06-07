#!/usr/bin/env bash

BASE_DIR="/home/Reneto/Público/XFCEMenu/XFCEMenu"
PIDFILE="/tmp/xfcemenu-${USER}.pid"
PYTHON_BIN="python3"

# Si ya hay una instancia registrada, la cerramos.
if [ -f "$PIDFILE" ]; then
    OLD_PID="$(cat "$PIDFILE" 2>/dev/null)"

    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null
        rm -f "$PIDFILE"
        exit 0
    fi

    rm -f "$PIDFILE"
fi

cd "$BASE_DIR" || exit 1

# Arranca usando ~/.config/xfcemenu/config.ini.
# Si el config.ini no existe, xfcemenu.py debe crearlo con valores por defecto.
"$PYTHON_BIN" "$BASE_DIR/xfcemenu.py" &
NEW_PID=$!

echo "$NEW_PID" > "$PIDFILE"

exit 0
