#!/usr/bin/env bash

CONFIG_DIR="$HOME/.config/xfcemenu"
CONFIG_FILE="$CONFIG_DIR/config.ini"

INSTALL_DIR="$HOME/.local/share/xfcemenu"
BASE_THEMES_DIR="$INSTALL_DIR/themes"

MENU_THEMES_DIR="$BASE_THEMES_DIR/Menu"
BUTTON_THEMES_DIR="$BASE_THEMES_DIR/Button"
SOUND_THEMES_DIR="$BASE_THEMES_DIR/Sound"
ICON_THEMES_DIR="$BASE_THEMES_DIR/Icon"

# Fallbacks por si algún paquete de temas no usa subcarpetas legacy.
[ -d "$MENU_THEMES_DIR" ] || MENU_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$BUTTON_THEMES_DIR" ] || BUTTON_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$SOUND_THEMES_DIR" ] || SOUND_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$ICON_THEMES_DIR" ] || ICON_THEMES_DIR="$BASE_THEMES_DIR"

BIN_FILE="$HOME/.local/bin/xfcemenu"

DIALOG_CANCEL=1
DIALOG_ESC=255

mkdir -p "$CONFIG_DIR"

# ------------------------------------------------------------
# Dependencias
# ------------------------------------------------------------

if ! command -v dialog >/dev/null 2>&1; then
	echo "Falta dialog."
	echo ""
	echo "Instala con:"
	echo "  sudo apt install dialog"
	exit 1
fi

# ------------------------------------------------------------
# Crear config si no existe
# ------------------------------------------------------------

create_default_config() {
	cat > "$CONFIG_FILE" <<EOF
[theme]
menu_theme = Menu
icon_theme = Win7_Icons_1.1
button_theme = Win2-7
sound_theme = Win2-7

[behavior]
close_on_focus_out = true
play_sounds = true
show_avatar = true
panel_mode = true

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
EOF
}

if [ ! -f "$CONFIG_FILE" ]; then
	create_default_config
fi

# ------------------------------------------------------------
# Utilidades INI simples
# ------------------------------------------------------------

get_ini_value() {
	local section="$1"
	local key="$2"

	awk -F '=' -v section="[$section]" -v key="$key" '
		$0 == section { found=1; next }
		/^\[/ { found=0 }
		found {
			k=$1
			v=$2
			gsub(/^[ \t]+|[ \t]+$/, "", k)
			gsub(/^[ \t]+|[ \t]+$/, "", v)

			if (k == key) {
				print v
				exit
			}
		}
	' "$CONFIG_FILE"
}

set_ini_value() {
	local section="$1"
	local key="$2"
	local value="$3"
	local tmp_file="$CONFIG_FILE.tmp"

	if [ ! -f "$CONFIG_FILE" ]; then
		create_default_config
	fi

	# Si no existe la sección, agregarla al final.
	if ! grep -q "^\[$section\]" "$CONFIG_FILE"; then
		{
			cat "$CONFIG_FILE"
			echo ""
			echo "[$section]"
			echo "$key = $value"
		} > "$tmp_file"

		mv "$tmp_file" "$CONFIG_FILE"
		return
	fi

	# Si existe la sección y existe la clave, reemplazarla.
	if awk -F '=' -v section="[$section]" -v key="$key" '
		$0 == section { found=1; next }
		/^\[/ { found=0 }
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

		awk -F '=' -v section="[$section]" -v key="$key" -v value="$value" '
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

			{ print }
		' "$CONFIG_FILE" > "$tmp_file"

		mv "$tmp_file" "$CONFIG_FILE"
		return
	fi

	# Si existe la sección pero no la clave, agregarla dentro de la sección.
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

		{ print }

		END {
			if (found && !inserted) {
				print key " = " value
			}
		}
	' "$CONFIG_FILE" > "$tmp_file"

	mv "$tmp_file" "$CONFIG_FILE"
}

pause_msg() {
	dialog --title "$1" --msgbox "$2" 12 72
}

# ------------------------------------------------------------
# Selector genérico de carpetas de tema
# ------------------------------------------------------------

select_theme_from_dir() {
	local title="$1"
	local section="$2"
	local key="$3"
	local dir="$4"

	if [ ! -d "$dir" ]; then
		pause_msg "Error" "No se encontró la carpeta:\n\n$dir"
		return
	fi

	local current_value
	current_value="$(get_ini_value "$section" "$key")"

	local options=()
	local count=0

	while IFS= read -r theme_path; do
		local theme_name
		theme_name="$(basename "$theme_path")"

		case "$theme_name" in
			__pycache__|.git|Menu|Button|Sound|Icon|Icons)
				continue
				;;
		esac

		if [ "$theme_name" = "$current_value" ]; then
			options+=("$theme_name" "actual")
		else
			options+=("$theme_name" "disponible")
		fi

		count=$((count + 1))
	done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d | sort)

	if [ "$count" -eq 0 ]; then
		pause_msg "Sin opciones" "No se encontraron opciones en:\n\n$dir"
		return
	fi

	local selected
	selected=$(dialog \
		--clear \
		--title "$title" \
		--menu "Actual: $current_value\nCarpeta: $dir" \
		22 78 14 \
		"${options[@]}" \
		3>&1 1>&2 2>&3)

	local status=$?

	if [ "$status" -eq 0 ] && [ -n "$selected" ]; then
		set_ini_value "$section" "$key" "$selected"

		# Actualizar rutas útiles.
		set_ini_value paths install_dir "$INSTALL_DIR"
		set_ini_value paths base_themes_dir "$BASE_THEMES_DIR"
		set_ini_value paths menu_themes_dir "$MENU_THEMES_DIR"
		set_ini_value paths button_themes_dir "$BUTTON_THEMES_DIR"
		set_ini_value paths sound_themes_dir "$SOUND_THEMES_DIR"
		set_ini_value paths icon_themes_dir "$ICON_THEMES_DIR"

		pause_msg "Cambiado" "Nueva opción seleccionada:\n\n$selected"
	fi
}

# ------------------------------------------------------------
# Selectores específicos
# ------------------------------------------------------------

select_menu_theme() {
	select_theme_from_dir "Seleccionar tema de menú" "theme" "menu_theme" "$MENU_THEMES_DIR"
}

select_button_theme() {
	select_theme_from_dir "Seleccionar tema de botón" "theme" "button_theme" "$BUTTON_THEMES_DIR"
}

select_sound_theme() {
	select_theme_from_dir "Seleccionar tema de sonido" "theme" "sound_theme" "$SOUND_THEMES_DIR"
}

select_icon_theme() {
	select_theme_from_dir "Seleccionar tema de iconos" "theme" "icon_theme" "$ICON_THEMES_DIR"
}

# ------------------------------------------------------------
# Sonidos
# ------------------------------------------------------------

toggle_sounds() {
	local current
	current="$(get_ini_value behavior play_sounds)"

	if [ "$current" = "true" ]; then
		dialog --title "Sonidos" \
			--yesno "Los sonidos están ACTIVADOS.\n\n¿Quieres desactivarlos?" \
			10 60

		if [ "$?" -eq 0 ]; then
			set_ini_value behavior play_sounds "false"
			pause_msg "Sonidos" "Sonidos desactivados."
		fi
	else
		dialog --title "Sonidos" \
			--yesno "Los sonidos están DESACTIVADOS.\n\n¿Quieres activarlos?" \
			10 60

		if [ "$?" -eq 0 ]; then
			set_ini_value behavior play_sounds "true"
			pause_msg "Sonidos" "Sonidos activados."
		fi
	fi
}

# ------------------------------------------------------------
# Rutas
# ------------------------------------------------------------

show_paths() {
	local content

	content="Rutas usadas por XFCEMenu Config:

Instalación:
$INSTALL_DIR

Temas base:
$BASE_THEMES_DIR

Temas de menú:
$MENU_THEMES_DIR

Temas de botón:
$BUTTON_THEMES_DIR

Temas de sonido:
$SOUND_THEMES_DIR

Temas de iconos:
$ICON_THEMES_DIR

Config:
$CONFIG_FILE

Lanzador:
$BIN_FILE"

	dialog \
		--title "Rutas detectadas" \
		--msgbox "$content" \
		22 78
}

# ------------------------------------------------------------
# Ver configuración
# ------------------------------------------------------------

show_config() {
	local content
	content="$(cat "$CONFIG_FILE")"

	dialog \
		--title "Configuración actual" \
		--msgbox "$content" \
		22 78
}

# ------------------------------------------------------------
# Editar manualmente
# ------------------------------------------------------------

edit_config() {
	local editor_cmd

	if command -v nano >/dev/null 2>&1; then
		editor_cmd="nano"
	elif command -v mousepad >/dev/null 2>&1; then
		editor_cmd="mousepad"
	elif command -v xed >/dev/null 2>&1; then
		editor_cmd="xed"
	elif command -v geany >/dev/null 2>&1; then
		editor_cmd="geany"
	else
		pause_msg "Editor" "No encontré nano, mousepad, xed ni geany.\n\nPuedes editar manualmente:\n\n$CONFIG_FILE"
		return
	fi

	clear
	"$editor_cmd" "$CONFIG_FILE"
}

# ------------------------------------------------------------
# Restaurar config
# ------------------------------------------------------------

reset_config() {
	dialog --title "Restaurar configuración" \
		--yesno "Esto reemplazará tu config.ini actual por una configuración básica.\n\n¿Continuar?" \
		10 70

	if [ "$?" -eq 0 ]; then
		create_default_config
		pause_msg "Restaurado" "Se restauró la configuración básica."
	fi
}

# ------------------------------------------------------------
# Probar XFCEMenu
# ------------------------------------------------------------

test_xfcemenu() {
	if [ -x "$BIN_FILE" ]; then
		"$BIN_FILE" &
		pause_msg "Prueba" "Se lanzó XFCEMenu."
	else
		pause_msg "Error" "No se encontró el lanzador:\n\n$BIN_FILE\n\nEjecuta primero el instalador."
	fi
}

# ------------------------------------------------------------
# Menú principal
# ------------------------------------------------------------

main_menu() {
	while true; do
		local menu_theme
		local sounds

		menu_theme="$(get_ini_value theme menu_theme)"
		sounds="$(get_ini_value behavior play_sounds)"

		[ -n "$menu_theme" ] || menu_theme="sin definir"
		[ -n "$sounds" ] || sounds="sin definir"

		local choice
		choice=$(dialog \
			--clear \
			--title "XFCEMenu Config" \
			--menu "Menú: $menu_theme | Sonidos: $sounds" \
			22 78 12 \
			"1" "Cambiar tema de menú" \
			"2" "Cambiar tema de botón" \
			"3" "Cambiar tema de sonidos" \
			"4" "Cambiar tema de iconos" \
			"5" "Activar / desactivar sonidos" \
			"6" "Ver config.ini" \
			"7" "Editar config.ini manualmente" \
			"8" "Restaurar configuración básica" \
			"9" "Ver rutas detectadas" \
			"10" "Probar XFCEMenu" \
			"0" "Salir" \
			3>&1 1>&2 2>&3)

		local status=$?

		if [ "$status" -eq "$DIALOG_CANCEL" ] || [ "$status" -eq "$DIALOG_ESC" ]; then
			clear
			exit 0
		fi

		case "$choice" in
			1) select_menu_theme ;;
			2) select_button_theme ;;
			3) select_sound_theme ;;
			4) select_icon_theme ;;
			5) toggle_sounds ;;
			6) show_config ;;
			7) edit_config ;;
			8) reset_config ;;
			9) show_paths ;;
			10) test_xfcemenu ;;
			0)
				clear
				exit 0
				;;
		esac
	done
}

main_menu