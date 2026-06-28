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

[icons]
source = auto

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
		$0 == section {
			found=1
			next
		}

		/^\[/ {
			found=0
		}

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
		return
	fi

	# Si existe la sección pero no la clave, agregarla dentro.
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

update_paths_in_config() {
	set_ini_value paths install_dir "$INSTALL_DIR"
	set_ini_value paths base_themes_dir "$BASE_THEMES_DIR"
	set_ini_value paths menu_themes_dir "$MENU_THEMES_DIR"
	set_ini_value paths button_themes_dir "$BUTTON_THEMES_DIR"
	set_ini_value paths sound_themes_dir "$SOUND_THEMES_DIR"
	set_ini_value paths icon_themes_dir "$ICON_THEMES_DIR"
}

pause_msg() {
	dialog \
		--title "$1" \
		--msgbox "$2" \
		12 72
}

# ------------------------------------------------------------
# Vista previa de temas
# ------------------------------------------------------------

find_theme_preview() {
	local theme_dir="$1"
	local candidate

	# Nombres conocidos, priorizando el formato usado por GnoMenu.
	for candidate in \
		"themepreview.png" \
		"themepreview.jpg" \
		"themepreview.jpeg" \
		"theme-preview.png" \
		"theme-preview.jpg" \
		"preview.png" \
		"preview.jpg" \
		"preview.jpeg" \
		"screenshot.png" \
		"screenshot.jpg" \
		"screenshot.jpeg"
	do
		if [ -f "$theme_dir/$candidate" ]; then
			printf '%s\n' "$theme_dir/$candidate"
			return 0
		fi
	done

	# Búsqueda sin distinguir mayúsculas y minúsculas.
	candidate="$(
		find "$theme_dir" \
			-maxdepth 1 \
			-type f \
			\( \
				-iname "themepreview.png" -o \
				-iname "themepreview.jpg" -o \
				-iname "themepreview.jpeg" -o \
				-iname "theme-preview.png" -o \
				-iname "theme-preview.jpg" -o \
				-iname "preview.png" -o \
				-iname "preview.jpg" -o \
				-iname "preview.jpeg" -o \
				-iname "screenshot.png" -o \
				-iname "screenshot.jpg" -o \
				-iname "screenshot.jpeg" \
			\) \
			-print \
			-quit 2>/dev/null
	)"

	if [ -n "$candidate" ]; then
		printf '%s\n' "$candidate"
		return 0
	fi

	return 1
}

show_theme_preview() {
	local theme_name="$1"
	local theme_dir="$MENU_THEMES_DIR/$theme_name"
	local preview_file

	preview_file="$(find_theme_preview "$theme_dir")"

	if [ -z "$preview_file" ] || [ ! -f "$preview_file" ]; then
		pause_msg \
			"Vista previa" \
			"No se encontró una vista previa para:\n\n$theme_name\n\nRuta revisada:\n$theme_dir"
		return 1
	fi

	clear

	if command -v ristretto >/dev/null 2>&1; then
		ristretto "$preview_file"
		return 0
	fi

	if command -v viewnior >/dev/null 2>&1; then
		viewnior "$preview_file"
		return 0
	fi

	if command -v feh >/dev/null 2>&1; then
		feh \
			--scale-down \
			--auto-zoom \
			--image-bg black \
			"$preview_file"
		return 0
	fi

	if command -v pix >/dev/null 2>&1; then
		pix "$preview_file"
		return 0
	fi

	if command -v eog >/dev/null 2>&1; then
		eog "$preview_file"
		return 0
	fi

	if command -v xdg-open >/dev/null 2>&1; then
		xdg-open "$preview_file" >/dev/null 2>&1 &

		pause_msg \
			"Vista previa abierta" \
			"La vista previa fue abierta con el visor predeterminado.\n\nTema:\n$theme_name\n\nCierra el visor cuando termines de verla."
		return 0
	fi

	pause_msg \
		"Visor no disponible" \
		"Se encontró la vista previa:\n\n$preview_file\n\nPero no hay un visor compatible instalado.\n\nPuedes instalar Ristretto con:\n\nsudo apt install ristretto"

	return 1
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
	local theme_path
	local theme_name

	while IFS= read -r theme_path; do
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
	done < <(
		find "$dir" \
			-mindepth 1 \
			-maxdepth 1 \
			-type d \
			-print |
		sort
	)

	if [ "$count" -eq 0 ]; then
		pause_msg "Sin opciones" "No se encontraron opciones en:\n\n$dir"
		return
	fi

	local selected
	selected="$(
		dialog \
			--clear \
			--title "$title" \
			--menu "Actual: $current_value\nCarpeta: $dir" \
			22 78 14 \
			"${options[@]}" \
			3>&1 1>&2 2>&3
	)"

	local status=$?

	if [ "$status" -eq 0 ] && [ -n "$selected" ]; then
		set_ini_value "$section" "$key" "$selected"
		update_paths_in_config

		pause_msg \
			"Cambiado" \
			"Nueva opción seleccionada:\n\n$selected"
	fi
}

# ------------------------------------------------------------
# Selector de temas de menú con vista previa
# ------------------------------------------------------------

select_menu_theme() {
	if [ ! -d "$MENU_THEMES_DIR" ]; then
		pause_msg \
			"Error" \
			"No se encontró la carpeta:\n\n$MENU_THEMES_DIR"
		return
	fi

	while true; do
		local current_value
		current_value="$(get_ini_value theme menu_theme)"

		local options=()
		local count=0
		local theme_path
		local theme_name
		local status_text
		local preview_file

		while IFS= read -r theme_path; do
			theme_name="$(basename "$theme_path")"

			case "$theme_name" in
				__pycache__|.git|Menu|Button|Sound|Icon|Icons)
					continue
					;;
			esac

			if preview_file="$(find_theme_preview "$theme_path")"; then
				status_text="vista disponible"
			else
				status_text="sin vista"
			fi

			if [ "$theme_name" = "$current_value" ]; then
				status_text="actual · $status_text"
			fi

			options+=("$theme_name" "$status_text")
			count=$((count + 1))
		done < <(
			find "$MENU_THEMES_DIR" \
				-mindepth 1 \
				-maxdepth 1 \
				-type d \
				-print |
			sort
		)

		if [ "$count" -eq 0 ]; then
			pause_msg \
				"Sin temas" \
				"No se encontraron temas de menú en:\n\n$MENU_THEMES_DIR"
			return
		fi

		local selected
		selected="$(
			dialog \
				--clear \
				--title "Seleccionar tema de menú" \
				--menu "Tema actual: $current_value\n\nSelecciona un tema para ver sus opciones." \
				22 82 14 \
				"${options[@]}" \
				3>&1 1>&2 2>&3
		)"

		local status=$?

		if [ "$status" -eq "$DIALOG_CANCEL" ] ||
		   [ "$status" -eq "$DIALOG_ESC" ] ||
		   [ -z "$selected" ]; then
			return
		fi

		while true; do
			local preview_path
			local preview_status

			preview_path="$(find_theme_preview "$MENU_THEMES_DIR/$selected")"

			if [ -n "$preview_path" ]; then
				preview_status="Vista previa disponible"
			else
				preview_status="Este tema no tiene vista previa reconocida"
			fi

			local action
			action="$(
				dialog \
					--clear \
					--title "$selected" \
					--menu "$preview_status\n\n¿Qué quieres hacer?" \
					16 72 6 \
					"1" "Ver vista previa" \
					"2" "Aplicar este tema" \
					"3" "Elegir otro tema" \
					"0" "Volver al menú principal" \
					3>&1 1>&2 2>&3
			)"

			local action_status=$?

			if [ "$action_status" -eq "$DIALOG_CANCEL" ] ||
			   [ "$action_status" -eq "$DIALOG_ESC" ]; then
				break
			fi

			case "$action" in
				1)
					show_theme_preview "$selected"
					;;

				2)
	set_ini_value theme menu_theme "$selected"
	update_paths_in_config
	clear
	return
	;;

				3)
					break
					;;

				0)
					return
					;;
			esac
		done
	done
}

# ------------------------------------------------------------
# Selectores específicos
# ------------------------------------------------------------

select_button_theme() {
	local before_theme
	local after_theme

	before_theme="$(get_ini_value theme button_theme)"

	select_theme_from_dir \
		"Seleccionar tema de botón" \
		"theme" \
		"button_theme" \
		"$BUTTON_THEMES_DIR"

	after_theme="$(get_ini_value theme button_theme)"

	# kesu-button lee el tema de botón al cargarse dentro de xfce4-panel.
	# Por ahora reiniciamos el panel solo si realmente cambió button_theme.
	if [ -n "$after_theme" ] && [ "$after_theme" != "$before_theme" ]; then
		if command -v xfce4-panel >/dev/null 2>&1; then
			xfce4-panel -r >/dev/null 2>&1 &
			pause_msg \
				"Panel reiniciado" \
				"Se cambió el tema de botón:\n\n$before_theme → $after_theme\n\nSe reinició xfce4-panel para actualizar kesu-button."
		else
			pause_msg \
				"Tema cambiado" \
				"Se cambió el tema de botón:\n\n$before_theme → $after_theme\n\nNo se encontró xfce4-panel para reiniciar automáticamente."
		fi
	fi
}

select_sound_theme() {
	select_theme_from_dir \
		"Seleccionar tema de sonido" \
		"theme" \
		"sound_theme" \
		"$SOUND_THEMES_DIR"
}

select_icon_theme() {
	select_theme_from_dir \
		"Seleccionar tema de iconos" \
		"theme" \
		"icon_theme" \
		"$ICON_THEMES_DIR"
}

# ------------------------------------------------------------
# Fuente de iconos
# ------------------------------------------------------------

select_icon_source() {
	local current
	current="$(get_ini_value icons source)"

	case "$current" in
		theme|system|auto)
			;;
		*)
			current="auto"
			;;
	esac

	local selected
	selected="$(
		dialog \
			--clear \
			--title "Fuente de iconos" \
			--menu "Actual: $current

auto: usa iconos legacy y cae al sistema si falta alguno.
theme: solo usa iconos del tema XFCEMenu/GnoMenu.
system: usa iconos del tema GTK/XFCE." \
			18 78 6 \
			"auto" "Tema legacy primero, sistema si falla" \
			"theme" "Solo iconos del tema" \
			"system" "Solo iconos del sistema" \
			3>&1 1>&2 2>&3
	)"

	local status=$?

	if [ "$status" -eq 0 ] && [ -n "$selected" ]; then
		set_ini_value icons source "$selected"
		pause_msg \
			"Fuente de iconos" \
			"Nueva fuente de iconos:

$selected"
	fi
}

# ------------------------------------------------------------
# Sonidos
# ------------------------------------------------------------

toggle_sounds() {
	local current
	current="$(get_ini_value behavior play_sounds)"

	if [ "$current" = "true" ]; then
		dialog \
			--title "Sonidos" \
			--yesno "Los sonidos están ACTIVADOS.\n\n¿Quieres desactivarlos?" \
			10 60

		if [ "$?" -eq 0 ]; then
			set_ini_value behavior play_sounds "false"
			pause_msg "Sonidos" "Sonidos desactivados."
		fi
	else
		dialog \
			--title "Sonidos" \
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
		pause_msg \
			"Editor" \
			"No encontré nano, mousepad, xed ni geany.\n\nPuedes editar manualmente:\n\n$CONFIG_FILE"
		return
	fi

	clear
	"$editor_cmd" "$CONFIG_FILE"
}

# ------------------------------------------------------------
# Restaurar config
# ------------------------------------------------------------

reset_config() {
	dialog \
		--title "Restaurar configuración" \
		--yesno "Esto reemplazará tu config.ini actual por una configuración básica.\n\n¿Continuar?" \
		10 70

	if [ "$?" -eq 0 ]; then
		create_default_config
		pause_msg \
			"Restaurado" \
			"Se restauró la configuración básica."
	fi
}

# ------------------------------------------------------------
# Probar XFCEMenu
# ------------------------------------------------------------

test_xfcemenu() {
	if [ -x "$BIN_FILE" ]; then
		"$BIN_FILE" &

		pause_msg \
			"Prueba" \
			"Se lanzó XFCEMenu."
	else
		pause_msg \
			"Error" \
			"No se encontró el lanzador:\n\n$BIN_FILE\n\nEjecuta primero el instalador."
	fi
}

# ------------------------------------------------------------
# Menú principal
# ------------------------------------------------------------

main_menu() {
	while true; do
		local menu_theme
		local sounds
		local icon_source

		menu_theme="$(get_ini_value theme menu_theme)"
		sounds="$(get_ini_value behavior play_sounds)"
		icon_source="$(get_ini_value icons source)"

		[ -n "$menu_theme" ] || menu_theme="sin definir"
		[ -n "$sounds" ] || sounds="sin definir"
		[ -n "$icon_source" ] || icon_source="auto"

		local choice
		choice="$(
			dialog \
				--clear \
				--title "XFCEMenu Config" \
				--menu "Menú: $menu_theme | Sonidos: $sounds | Iconos: $icon_source" \
				23 78 13 \
				"1" "Cambiar tema de menú / Ver vista previa" \
				"2" "Cambiar tema de botón" \
				"3" "Cambiar tema de sonidos" \
				"4" "Cambiar tema de iconos" \
				"5" "Fuente de iconos: auto / tema / sistema" \
				"6" "Activar / desactivar sonidos" \
				"7" "Ver config.ini" \
				"8" "Editar config.ini manualmente" \
				"9" "Restaurar configuración básica" \
				"10" "Ver rutas detectadas" \
				"11" "Probar XFCEMenu" \
				"0" "Salir" \
				3>&1 1>&2 2>&3
		)"

		local status=$?

		if [ "$status" -eq "$DIALOG_CANCEL" ] ||
		   [ "$status" -eq "$DIALOG_ESC" ]; then
			clear
			exit 0
		fi

		case "$choice" in
			1)
				select_menu_theme
				;;

			2)
				select_button_theme
				;;

			3)
				select_sound_theme
				;;

			4)
				select_icon_theme
				;;

			5)
				select_icon_source
				;;

			6)
				toggle_sounds
				;;

			7)
				show_config
				;;

			8)
				edit_config
				;;

			9)
				reset_config
				;;

			10)
				show_paths
				;;

			11)
				test_xfcemenu
				;;

			0)
				clear
				exit 0
				;;
		esac
	done
}

main_menu
