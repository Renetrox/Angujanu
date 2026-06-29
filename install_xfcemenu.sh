#!/usr/bin/env bash

set -e

APP_NAME="XFCEMenu"
APP_ID="xfcemenu"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INSTALL_DIR="$HOME/.local/share/xfcemenu"
CONFIG_DIR="$HOME/.config/xfcemenu"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

BIN_FILE="$BIN_DIR/xfcemenu"
CONFIG_BIN_FILE="$BIN_DIR/xfcemenu-config"
CONFIG_TERMINAL_BIN_FILE="$BIN_DIR/xfcemenu-config-terminal"

DESKTOP_FILE="$DESKTOP_DIR/xfcemenu.desktop"
CONFIG_DESKTOP_FILE="$DESKTOP_DIR/xfcemenu-config.desktop"

CONFIG_FILE="$CONFIG_DIR/config.ini"

echo "======================================"
echo " Instalador de $APP_NAME"
echo "======================================"
echo ""

# ------------------------------------------------------------
# Verificar estructura del proyecto
# ------------------------------------------------------------

echo "[1/7] Verificando estructura..."

if [ ! -f "$SRC_DIR/xfcemenu.py" ]; then
	echo "ERROR: No se encontró xfcemenu.py en:"
	echo "$SRC_DIR"
	exit 1
fi

if [ ! -d "$SRC_DIR/themes" ]; then
	echo "ERROR: No se encontró la carpeta themes en:"
	echo "$SRC_DIR"
	exit 1
fi

if [ ! -f "$SRC_DIR/legacy_loader.py" ]; then
	echo "ERROR: No se encontró legacy_loader.py en:"
	echo "$SRC_DIR"
	exit 1
fi

if [ ! -f "$SRC_DIR/command_mapper.py" ]; then
	echo "ERROR: No se encontró command_mapper.py en:"
	echo "$SRC_DIR"
	exit 1
fi

if [ ! -f "$SRC_DIR/xfcemenu-config.sh" ]; then
	echo "AVISO: No se encontró xfcemenu-config.sh en:"
	echo "$SRC_DIR"
	echo "       Se instalará XFCEMenu, pero el configurador mostrará error hasta que exista."
	echo ""
fi

echo "  Estructura OK"
echo ""

# ------------------------------------------------------------
# Verificar dependencias
# ------------------------------------------------------------

echo "[2/7] Verificando dependencias..."

missing=0

if ! command -v python3 >/dev/null 2>&1; then
	echo "  Falta: python3"
	missing=1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
PY
then
	echo "  Falta: python3-gi / gir1.2-gtk-3.0"
	missing=1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import cairo
PY
then
	echo "  Falta: python3-cairo"
	missing=1
fi

if ! command -v rsync >/dev/null 2>&1; then
	echo "  Falta: rsync"
	missing=1
fi

if [ "$missing" -eq 1 ]; then
	echo ""
	echo "Instala dependencias con:"
	echo ""
	echo "  sudo apt install python3 python3-gi python3-cairo gir1.2-gtk-3.0 rsync"
	echo ""
	echo "Opcional para el configurador:"
	echo ""
	echo "  sudo apt install dialog"
	echo ""
	exit 1
fi

echo "  Dependencias OK"
echo ""

# ------------------------------------------------------------
# Crear carpetas
# ------------------------------------------------------------

echo "[3/7] Creando carpetas..."

mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

echo "  Carpetas listas"
echo ""

# ------------------------------------------------------------
# Copiar archivos
# ------------------------------------------------------------

echo "[4/7] Copiando archivos..."

# Actualizar el programa sin borrar los temas añadidos manualmente.
rsync -a \
	--delete \
	--exclude ".git" \
	--exclude ".gitattributes" \
	--exclude "__pycache__" \
	--exclude "*.pyc" \
	--exclude "install_xfcemenu.sh" \
	--exclude "themes/" \
	"$SRC_DIR/" "$INSTALL_DIR/"

# Actualizar temas oficiales sin eliminar temas adicionales del usuario.
mkdir -p "$INSTALL_DIR/themes"

rsync -a \
	--exclude "__pycache__" \
	--exclude "*.pyc" \
	"$SRC_DIR/themes/" "$INSTALL_DIR/themes/"

echo "  Programa actualizado"
echo "  Temas oficiales actualizados"
echo "  Temas instalados manualmente conservados"
echo ""
echo "  Instalado en:"
echo "  $INSTALL_DIR"
echo ""

# ------------------------------------------------------------
# Detectar carpetas legacy de temas
# ------------------------------------------------------------

BASE_THEMES_DIR="$INSTALL_DIR/themes"

MENU_THEMES_DIR="$BASE_THEMES_DIR/Menu"
BUTTON_THEMES_DIR="$BASE_THEMES_DIR/Button"
SOUND_THEMES_DIR="$BASE_THEMES_DIR/Sound"
ICON_THEMES_DIR="$BASE_THEMES_DIR/Icon"

[ -d "$MENU_THEMES_DIR" ] || MENU_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$BUTTON_THEMES_DIR" ] || BUTTON_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$SOUND_THEMES_DIR" ] || SOUND_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$ICON_THEMES_DIR" ] || ICON_THEMES_DIR="$BASE_THEMES_DIR"

# ------------------------------------------------------------
# Utilidades simples para config.ini
# ------------------------------------------------------------

ensure_ini_section() {
	local section="$1"

	if ! grep -q "^\[$section\]" "$CONFIG_FILE"; then
		{
			echo ""
			echo "[$section]"
		} >> "$CONFIG_FILE"
	fi
}

ensure_ini_key() {
	local section="$1"
	local key="$2"
	local value="$3"
	local tmp_file="$CONFIG_FILE.tmp"

	ensure_ini_section "$section"

	if awk -F '=' -v section="[$section]" -v key="$key" '
		$0 == section {
			found=1
			next
		}

		/^\[/ {
			found=0
		}

		found {
			k=$1
			gsub(/^[ \t]+|[ \t]+$/, "", k)

			if (k == key) {
				foundkey=1
			}
		}

		END {
			exit foundkey ? 0 : 1
		}
	' "$CONFIG_FILE"; then
		return 0
	fi

	awk -v section="[$section]" -v key="$key" -v value="$value" '
		$0 == section {
			found=1
			inserted=0
			print
			next
		}

		/^\[/ && found && !inserted {
			print key " = " value
			inserted=1
			found=0
			print
			next
		}

		{
			print
		}

		END {
			if (found && !inserted) {
				print key " = " value
			}
		}
	' "$CONFIG_FILE" > "$tmp_file"

	mv "$tmp_file" "$CONFIG_FILE"
}

set_ini_key() {
	local section="$1"
	local key="$2"
	local value="$3"
	local tmp_file="$CONFIG_FILE.tmp"

	ensure_ini_section "$section"

	if awk -F '=' -v section="[$section]" -v key="$key" '
		$0 == section {
			found=1
			next
		}

		/^\[/ {
			found=0
		}

		found {
			k=$1
			gsub(/^[ \t]+|[ \t]+$/, "", k)

			if (k == key) {
				foundkey=1
			}
		}

		END {
			exit foundkey ? 0 : 1
		}
	' "$CONFIG_FILE"; then
		awk -F '=' \
			-v section="[$section]" \
			-v key="$key" \
			-v value="$value" '
			$0 == section {
				found=1
				print
				next
			}

			/^\[/ {
				found=0
				print
				next
			}

			found {
				k=$1
				gsub(/^[ \t]+|[ \t]+$/, "", k)

				if (k == key) {
					print key " = " value
					next
				}
			}

			{
				print
			}
		' "$CONFIG_FILE" > "$tmp_file"

		mv "$tmp_file" "$CONFIG_FILE"
	else
		ensure_ini_key "$section" "$key" "$value"
	fi
}

# ------------------------------------------------------------
# Crear configuración inicial
# ------------------------------------------------------------

echo "[5/7] Creando configuración..."

if [ ! -f "$CONFIG_FILE" ]; then
	cat > "$CONFIG_FILE" <<EOF
[theme]
menu_theme = Vista
icon_theme = Win7_Icons_1.1
button_theme = Win2-7
sound_theme = Win2-7

[behavior]
close_on_focus_out = true
play_sounds = true
show_avatar = true
panel_mode = true

[kesu-button]
label_position_scale = false
label_offset_x = 10
label_offset_y = 3

[interface]
language = auto
icon_size = 24
program_text_auto_color = true

[paths]
install_dir = $INSTALL_DIR
base_themes_dir = $BASE_THEMES_DIR
menu_themes_dir = $MENU_THEMES_DIR
button_themes_dir = $BUTTON_THEMES_DIR
sound_themes_dir = $SOUND_THEMES_DIR
icon_themes_dir = $ICON_THEMES_DIR
launcher = $BIN_FILE
EOF

	echo "  Configuración creada:"
	echo "  $CONFIG_FILE"
else
	echo "  Configuración existente conservada:"
	echo "  $CONFIG_FILE"

	# Mantener rutas actualizadas aunque se conserve la configuración existente.
	set_ini_key paths install_dir "$INSTALL_DIR"
	set_ini_key paths base_themes_dir "$BASE_THEMES_DIR"
	set_ini_key paths menu_themes_dir "$MENU_THEMES_DIR"
	set_ini_key paths button_themes_dir "$BUTTON_THEMES_DIR"
	set_ini_key paths sound_themes_dir "$SOUND_THEMES_DIR"
	set_ini_key paths icon_themes_dir "$ICON_THEMES_DIR"
	set_ini_key paths launcher "$BIN_FILE"
fi

# Asegurar valores nuevos para instalaciones existentes sin pisar ajustes del usuario.
ensure_ini_key kesu-button label_position_scale false
ensure_ini_key kesu-button label_offset_x 10
ensure_ini_key kesu-button label_offset_y 3
ensure_ini_key paths launcher "$BIN_FILE"

echo "  Configuración kesu-button verificada."
echo ""

# ------------------------------------------------------------
# Crear comandos
# ------------------------------------------------------------

echo "[6/7] Creando comandos..."

cat > "$BIN_FILE" <<EOF
#!/usr/bin/env bash

BASE_DIR="$INSTALL_DIR"
PIDFILE="/tmp/xfcemenu-\${USER}.pid"
PYTHON_BIN="python3"

# Asegurar que el menú vea aplicaciones exportadas por Flatpak y Snap
# aunque XFCE lance el panel con un entorno XDG incompleto.
export XDG_DATA_DIRS="\$HOME/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/var/lib/snapd/desktop:\${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export PATH="\$HOME/.local/bin:/snap/bin:\$PATH"

if [ -f "\$PIDFILE" ]; then
	OLD_PID="\$(cat "\$PIDFILE" 2>/dev/null)"

	if [ -n "\$OLD_PID" ] && kill -0 "\$OLD_PID" 2>/dev/null; then
		kill "\$OLD_PID" 2>/dev/null || true
		rm -f "\$PIDFILE"
		exit 0
	fi

	rm -f "\$PIDFILE"
fi

cd "\$BASE_DIR" || exit 1

"\$PYTHON_BIN" "\$BASE_DIR/xfcemenu.py" &
NEW_PID=\$!

echo "\$NEW_PID" > "\$PIDFILE"

exit 0
EOF

chmod +x "$BIN_FILE"

echo "  Comando creado:"
echo "  $BIN_FILE"

cat > "$CONFIG_BIN_FILE" <<EOF
#!/usr/bin/env bash

APP_DIR="$INSTALL_DIR"
CONFIG_SCRIPT="\$APP_DIR/xfcemenu-config.sh"

if [ ! -f "\$CONFIG_SCRIPT" ]; then
	echo "ERROR: No se encontró xfcemenu-config.sh"
	echo ""
	echo "Ruta esperada:"
	echo "  \$CONFIG_SCRIPT"
	echo ""
	echo "Reinstala XFCEMenu o verifica que el archivo exista en la carpeta del proyecto."
	read -r -p "Presiona Enter para salir..."
	exit 1
fi

if ! command -v dialog >/dev/null 2>&1; then
	echo "ERROR: Falta dialog."
	echo ""
	echo "Instala con:"
	echo "  sudo apt install dialog"
	echo ""
	read -r -p "Presiona Enter para salir..."
	exit 1
fi

cd "\$APP_DIR" || exit 1
exec bash "\$CONFIG_SCRIPT" "\$@"
EOF

chmod +x "$CONFIG_BIN_FILE"

echo "  Configurador creado:"
echo "  $CONFIG_BIN_FILE"

cat > "$CONFIG_TERMINAL_BIN_FILE" <<EOF
#!/usr/bin/env bash

CONFIG_CMD="$CONFIG_BIN_FILE"

if command -v exo-open >/dev/null 2>&1; then
	exo-open --launch TerminalEmulator "\$CONFIG_CMD"
	exit 0
fi

if command -v xfce4-terminal >/dev/null 2>&1; then
	xfce4-terminal --command="\$CONFIG_CMD"
	exit 0
fi

if command -v x-terminal-emulator >/dev/null 2>&1; then
	x-terminal-emulator -e "\$CONFIG_CMD"
	exit 0
fi

if command -v mate-terminal >/dev/null 2>&1; then
	mate-terminal -- "\$CONFIG_CMD"
	exit 0
fi

if command -v gnome-terminal >/dev/null 2>&1; then
	gnome-terminal -- "\$CONFIG_CMD"
	exit 0
fi

if command -v konsole >/dev/null 2>&1; then
	konsole -e "\$CONFIG_CMD"
	exit 0
fi

echo "ERROR: No se encontró un emulador de terminal compatible."
echo ""
echo "Ejecuta manualmente:"
echo "  \$CONFIG_CMD"
echo ""
read -r -p "Presiona Enter para salir..."
EOF

chmod +x "$CONFIG_TERMINAL_BIN_FILE"

echo "  Lanzador de configuración en terminal creado:"
echo "  $CONFIG_TERMINAL_BIN_FILE"
echo ""

# ------------------------------------------------------------
# Crear entradas .desktop
# ------------------------------------------------------------

echo "[7/7] Creando entradas de aplicación..."

ICON_FILE="$INSTALL_DIR/XFCEmenu.png"
CONFIG_ICON_FILE="$INSTALL_DIR/Settings.png"

if [ ! -f "$ICON_FILE" ]; then
	ICON_FILE="applications-system"
fi

if [ ! -f "$CONFIG_ICON_FILE" ]; then
	CONFIG_ICON_FILE="preferences-system"
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=XFCEMenu
Comment=Menú estilo GnoMenu para XFCE
Exec=$BIN_FILE
Icon=$ICON_FILE
Terminal=false
Type=Application
Categories=Utility;System;
StartupNotify=false
NoDisplay=false
EOF

chmod +x "$DESKTOP_FILE"

echo "  Entrada creada:"
echo "  $DESKTOP_FILE"

cat > "$CONFIG_DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=XFCEMenu Settings
Comment=Configurar temas y opciones de XFCEMenu
Exec=$CONFIG_TERMINAL_BIN_FILE
Icon=$CONFIG_ICON_FILE
Terminal=false
Type=Application
Categories=Settings;DesktopSettings;Utility;
StartupNotify=false
NoDisplay=false
EOF

chmod +x "$CONFIG_DESKTOP_FILE"

echo "  Entrada de configuración creada:"
echo "  $CONFIG_DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
	update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo ""
echo "======================================"
echo " Instalación completada"
echo "======================================"
echo ""
echo "Puedes ejecutar el menú con:"
echo ""
echo "  xfcemenu"
echo ""
echo "Puedes abrir el configurador con:"
echo ""
echo "  xfcemenu-config"
echo ""
echo "O con terminal automática:"
echo ""
echo "  xfcemenu-config-terminal"
echo ""
echo "Para usar kesu-button:"
echo ""
echo "  Instala kesu-button como plugin de xfce4-panel."
echo "  Luego agrégalo desde:"
echo "  Panel → Agregar nuevos elementos → Kesú"
echo ""
echo "Rutas:"
echo ""
echo "  Aplicación: $INSTALL_DIR"
echo "  Config:     $CONFIG_FILE"
echo "  Temas:      $BASE_THEMES_DIR"
echo ""
echo "Iconos:"
echo ""
echo "  Menú:       $ICON_FILE"
echo "  Settings:   $CONFIG_ICON_FILE"
echo ""
