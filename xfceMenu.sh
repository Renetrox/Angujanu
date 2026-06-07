#!/usr/bin/env bash

BASE_DIR="/home/Reneto/Público/XFCEMenu/XFCEMenu"
THEME="Win2-7Standard-Es"
PIDFILE="/tmp/xfcemenu-${USER}.pid"

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

python3 "$BASE_DIR/xfcemenu.py" --theme "$THEME" &
NEW_PID=$!

echo "$NEW_PID" > "$PIDFILE"

exit 0