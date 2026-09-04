#!/usr/bin/env bash

BASE_DIR="$HOME/.local/share/xfcemenu"
PIDFILE="/tmp/xfcemenu-${USER}.pid"
PYTHON_BIN="python3"

# Asegurar que el menú vea aplicaciones exportadas por Flatpak y Snap
# aunque XFCE lance el panel con un entorno XDG incompleto.
XDG_DATA_DIRS_DEFAULT="${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export XDG_DATA_DIRS="$HOME/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/var/lib/snapd/desktop:${XDG_DATA_DIRS_DEFAULT}"
export PATH="$HOME/.local/bin:/snap/bin:$PATH"

# Si ya hay una instancia registrada, la cerramos.
if [ -f "$PIDFILE" ]; then
	OLD_PID="$(cat "$PIDFILE" 2>/dev/null)"

	if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
		kill "$OLD_PID" 2>/dev/null || true
		rm -f "$PIDFILE"
		exit 0
	fi

	rm -f "$PIDFILE"
fi

cd "$BASE_DIR" || exit 1

# El puente consume --anchor-* / --panel-position y conserva todos los
# argumentos normales de XFCEMenu. Fallback compatible con instalaciones viejas.
ENTRYPOINT="$BASE_DIR/xfcemenu_anchor.py"
if [ ! -f "$ENTRYPOINT" ]; then
	ENTRYPOINT="$BASE_DIR/xfcemenu.py"
fi

"$PYTHON_BIN" "$ENTRYPOINT" "$@" &
NEW_PID=$!

echo "$NEW_PID" > "$PIDFILE"

exit 0
