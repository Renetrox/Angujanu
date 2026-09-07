#!/usr/bin/env bash

CONFIG_DIR="$HOME/.config/xfcemenu"
CONFIG_FILE="$CONFIG_DIR/config.ini"
INSTALL_DIR="$HOME/.local/share/xfcemenu"
BASE_THEMES_DIR="$INSTALL_DIR/themes"
MENU_THEMES_DIR="$BASE_THEMES_DIR/Menu"
BUTTON_THEMES_DIR="$BASE_THEMES_DIR/Button"
SOUND_THEMES_DIR="$BASE_THEMES_DIR/Sound"
ICON_THEMES_DIR="$BASE_THEMES_DIR/Icon"
BIN_FILE="$HOME/.local/bin/xfcemenu"
DIALOG_CANCEL=1
DIALOG_ESC=255
UI_LANG=""

[ -d "$MENU_THEMES_DIR" ] || MENU_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$BUTTON_THEMES_DIR" ] || BUTTON_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$SOUND_THEMES_DIR" ] || SOUND_THEMES_DIR="$BASE_THEMES_DIR"
[ -d "$ICON_THEMES_DIR" ] || ICON_THEMES_DIR="$BASE_THEMES_DIR"
mkdir -p "$CONFIG_DIR"

if ! command -v dialog >/dev/null 2>&1; then
    printf '%s\n\n%s\n  sudo apt install dialog\n' \
        'dialog is required / Falta dialog.' \
        'Install with / Instala con:'
    exit 1
fi

create_default_config() {
    cat > "$CONFIG_FILE" <<EOF_CONFIG
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
config_language =
icon_size = 24
program_text_auto_color = true

[paths]
install_dir = $INSTALL_DIR
base_themes_dir = $BASE_THEMES_DIR
menu_themes_dir = $MENU_THEMES_DIR
button_themes_dir = $BUTTON_THEMES_DIR
sound_themes_dir = $SOUND_THEMES_DIR
icon_themes_dir = $ICON_THEMES_DIR
EOF_CONFIG
}

[ -f "$CONFIG_FILE" ] || create_default_config

get_ini_value() {
    awk -F '=' -v section="[$1]" -v key="$2" '
        $0==section {found=1; next}
        /^\[/ {found=0}
        found {k=$1; v=$2; gsub(/^[ \t]+|[ \t]+$/, "", k); gsub(/^[ \t]+|[ \t]+$/, "", v); if(k==key){print v; exit}}
    ' "$CONFIG_FILE"
}

set_ini_value() {
    local section="$1" key="$2" value="$3" tmp="$CONFIG_FILE.tmp"
    [ -f "$CONFIG_FILE" ] || create_default_config
    awk -v section="[$section]" -v key="$key" -v value="$value" '
        BEGIN {insec=0; section_seen=0; key_seen=0}
        $0==section {insec=1; section_seen=1; print; next}
        /^\[/ {
            if(insec && !key_seen){print key " = " value; key_seen=1}
            insec=0; print; next
        }
        insec {
            split($0,a,"="); k=a[1]; gsub(/^[ \t]+|[ \t]+$/, "", k)
            if(k==key){print key " = " value; key_seen=1; next}
        }
        {print}
        END {
            if(insec && !key_seen) print key " = " value
            else if(!section_seen){print ""; print section; print key " = " value}
        }
    ' "$CONFIG_FILE" > "$tmp" && mv "$tmp" "$CONFIG_FILE"
}

update_paths_in_config() {
    set_ini_value paths install_dir "$INSTALL_DIR"
    set_ini_value paths base_themes_dir "$BASE_THEMES_DIR"
    set_ini_value paths menu_themes_dir "$MENU_THEMES_DIR"
    set_ini_value paths button_themes_dir "$BUTTON_THEMES_DIR"
    set_ini_value paths sound_themes_dir "$SOUND_THEMES_DIR"
    set_ini_value paths icon_themes_dir "$ICON_THEMES_DIR"
}

msg() { dialog --title "$1" --msgbox "$2" 12 72; }

choose_language() {
    local selected status
    selected="$(dialog --clear --title 'Language / Idioma' \
        --menu 'Choose language / Seleccione idioma' 12 54 4 \
        en English es Español 3>&1 1>&2 2>&3)"
    status=$?
    if [ "$status" -eq "$DIALOG_CANCEL" ] || [ "$status" -eq "$DIALOG_ESC" ] || [ -z "$selected" ]; then
        clear; return 1
    fi
    UI_LANG="$selected"
    set_ini_value interface config_language "$UI_LANG"
}

init_language() {
    UI_LANG="$(get_ini_value interface config_language)"
    case "$UI_LANG" in en|es) ;; *) choose_language || exit 0 ;; esac
}

change_language() {
    local old="$UI_LANG"
    choose_language || { UI_LANG="$old"; return; }
    [ "$UI_LANG" = es ] && msg Idioma 'El configurador ahora usa Español.' || msg Language 'The configurator now uses English.'
}

find_theme_preview() {
    local d="$1" f
    for f in themepreview.png themepreview.jpg themepreview.jpeg theme-preview.png theme-preview.jpg preview.png preview.jpg preview.jpeg screenshot.png screenshot.jpg screenshot.jpeg; do
        [ -f "$d/$f" ] && { printf '%s\n' "$d/$f"; return 0; }
    done
    find "$d" -maxdepth 1 -type f \( -iname 'themepreview.*' -o -iname 'theme-preview.*' -o -iname 'preview.*' -o -iname 'screenshot.*' \) -print -quit 2>/dev/null
}

show_theme_preview() {
    local name="$1" dir="$MENU_THEMES_DIR/$1" file
    file="$(find_theme_preview "$dir")"
    if [ -z "$file" ] || [ ! -f "$file" ]; then
        [ "$UI_LANG" = es ] && msg 'Vista previa' "No se encontró una vista previa para:\n\n$name\n\nRuta revisada:\n$dir" || msg Preview "No preview was found for:\n\n$name\n\nChecked path:\n$dir"
        return 1
    fi
    clear
    for viewer in ristretto viewnior pix eog; do command -v "$viewer" >/dev/null 2>&1 && { "$viewer" "$file"; return; }; done
    if command -v feh >/dev/null 2>&1; then feh --scale-down --auto-zoom --image-bg black "$file"; return; fi
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$file" >/dev/null 2>&1 &
        [ "$UI_LANG" = es ] && msg 'Vista previa abierta' "La vista previa fue abierta con el visor predeterminado.\n\nTema:\n$name" || msg 'Preview opened' "The preview was opened with the default image viewer.\n\nTheme:\n$name"
        return
    fi
    [ "$UI_LANG" = es ] && msg 'Visor no disponible' "Vista encontrada:\n\n$file\n\nInstala Ristretto con:\n\nsudo apt install ristretto" || msg 'Viewer unavailable' "Preview found:\n\n$file\n\nInstall Ristretto with:\n\nsudo apt install ristretto"
}

select_theme_from_dir() {
    local title="$1" section="$2" key="$3" dir="$4" current options=() path name selected status label
    [ -d "$dir" ] || { [ "$UI_LANG" = es ] && msg Error "No se encontró la carpeta:\n\n$dir" || msg Error "Folder not found:\n\n$dir"; return; }
    current="$(get_ini_value "$section" "$key")"
    while IFS= read -r path; do
        name="$(basename "$path")"
        case "$name" in __pycache__|.git|Menu|Button|Sound|Icon|Icons) continue;; esac
        if [ "$UI_LANG" = es ]; then [ "$name" = "$current" ] && label=actual || label=disponible; else [ "$name" = "$current" ] && label=current || label=available; fi
        options+=("$name" "$label")
    done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d -print | sort)
    [ ${#options[@]} -gt 0 ] || { [ "$UI_LANG" = es ] && msg 'Sin opciones' "No se encontraron opciones en:\n\n$dir" || msg 'No options' "No options were found in:\n\n$dir"; return; }
    if [ "$UI_LANG" = es ]; then
        selected="$(dialog --clear --title "$title" --menu "Actual: $current\nCarpeta: $dir" 22 78 14 "${options[@]}" 3>&1 1>&2 2>&3)"
    else
        selected="$(dialog --clear --title "$title" --menu "Current: $current\nFolder: $dir" 22 78 14 "${options[@]}" 3>&1 1>&2 2>&3)"
    fi
    status=$?
    if [ "$status" -eq 0 ] && [ -n "$selected" ]; then
        set_ini_value "$section" "$key" "$selected"; update_paths_in_config
        [ "$UI_LANG" = es ] && msg Cambiado "Nueva opción seleccionada:\n\n$selected" || msg Changed "New option selected:\n\n$selected"
    fi
}

select_menu_theme() {
    local current options path name st selected status action preview
    while true; do
        current="$(get_ini_value theme menu_theme)"; options=()
        while IFS= read -r path; do
            name="$(basename "$path")"; case "$name" in __pycache__|.git|Menu|Button|Sound|Icon|Icons) continue;; esac
            preview="$(find_theme_preview "$path")"
            if [ "$UI_LANG" = es ]; then [ -n "$preview" ] && st='vista disponible' || st='sin vista'; [ "$name" = "$current" ] && st="actual · $st"; else [ -n "$preview" ] && st='preview available' || st='no preview'; [ "$name" = "$current" ] && st="current · $st"; fi
            options+=("$name" "$st")
        done < <(find "$MENU_THEMES_DIR" -mindepth 1 -maxdepth 1 -type d -print | sort)
        [ ${#options[@]} -gt 0 ] || { [ "$UI_LANG" = es ] && msg 'Sin temas' "No se encontraron temas en:\n\n$MENU_THEMES_DIR" || msg 'No themes' "No menu themes were found in:\n\n$MENU_THEMES_DIR"; return; }
        if [ "$UI_LANG" = es ]; then selected="$(dialog --clear --title 'Seleccionar tema de menú' --menu "Tema actual: $current\n\nSelecciona un tema para ver sus opciones." 22 82 14 "${options[@]}" 3>&1 1>&2 2>&3)"; else selected="$(dialog --clear --title 'Select menu theme' --menu "Current theme: $current\n\nSelect a theme to view its options." 22 82 14 "${options[@]}" 3>&1 1>&2 2>&3)"; fi
        status=$?; [ "$status" -eq 0 ] && [ -n "$selected" ] || return
        while true; do
            preview="$(find_theme_preview "$MENU_THEMES_DIR/$selected")"
            if [ "$UI_LANG" = es ]; then
                [ -n "$preview" ] && st='Vista previa disponible' || st='Este tema no tiene vista previa reconocida'
                action="$(dialog --clear --title "$selected" --menu "$st\n\n¿Qué quieres hacer?" 16 72 6 1 'Ver vista previa' 2 'Aplicar este tema' 3 'Elegir otro tema' 0 'Volver al menú principal' 3>&1 1>&2 2>&3)"
            else
                [ -n "$preview" ] && st='Preview available' || st='This theme has no recognized preview'
                action="$(dialog --clear --title "$selected" --menu "$st\n\nWhat do you want to do?" 16 72 6 1 'View preview' 2 'Apply this theme' 3 'Choose another theme' 0 'Back to main menu' 3>&1 1>&2 2>&3)"
            fi
            status=$?; [ "$status" -eq 0 ] || break
            case "$action" in 1) show_theme_preview "$selected";; 2) set_ini_value theme menu_theme "$selected"; update_paths_in_config; clear; return;; 3) break;; 0) return;; esac
        done
    done
}

select_button_theme() {
    local before after title
    before="$(get_ini_value theme button_theme)"; [ "$UI_LANG" = es ] && title='Seleccionar tema de botón' || title='Select button theme'
    select_theme_from_dir "$title" theme button_theme "$BUTTON_THEMES_DIR"; after="$(get_ini_value theme button_theme)"
    [ -n "$after" ] && [ "$after" != "$before" ] || return
    if command -v xfce4-panel >/dev/null 2>&1; then
        xfce4-panel -r >/dev/null 2>&1 &
        [ "$UI_LANG" = es ] && msg 'Panel reiniciado' "Tema de botón:\n\n$before → $after\n\nxfce4-panel fue reiniciado para actualizar Kesú." || msg 'Panel restarted' "Button theme:\n\n$before → $after\n\nxfce4-panel was restarted to update Kesú."
    else
        [ "$UI_LANG" = es ] && msg 'Tema cambiado' "Tema de botón:\n\n$before → $after\n\nNo se encontró xfce4-panel." || msg 'Theme changed' "Button theme:\n\n$before → $after\n\nxfce4-panel was not found."
    fi
}

select_sound_theme() { local t; [ "$UI_LANG" = es ] && t='Seleccionar tema de sonido' || t='Select sound theme'; select_theme_from_dir "$t" theme sound_theme "$SOUND_THEMES_DIR"; }
select_icon_theme() { local t; [ "$UI_LANG" = es ] && t='Seleccionar tema de iconos' || t='Select icon theme'; select_theme_from_dir "$t" theme icon_theme "$ICON_THEMES_DIR"; }

select_icon_source() {
    local current selected status
    current="$(get_ini_value icons source)"; case "$current" in theme|system|auto);; *) current=auto;; esac
    if [ "$UI_LANG" = es ]; then selected="$(dialog --clear --title 'Fuente de iconos' --menu "Actual: $current\n\nauto: tema legacy y sistema como respaldo.\ntheme: solo tema XFCEMenu/GnoMenu.\nsystem: tema GTK/XFCE." 18 78 6 auto 'Tema legacy primero, sistema si falla' theme 'Solo iconos del tema' system 'Solo iconos del sistema' 3>&1 1>&2 2>&3)"; else selected="$(dialog --clear --title 'Icon source' --menu "Current: $current\n\nauto: legacy theme first, system as fallback.\ntheme: XFCEMenu/GnoMenu theme only.\nsystem: GTK/XFCE theme." 18 78 6 auto 'Legacy theme first, system fallback' theme 'Theme icons only' system 'System icons only' 3>&1 1>&2 2>&3)"; fi
    status=$?; if [ "$status" -eq 0 ] && [ -n "$selected" ]; then set_ini_value icons source "$selected"; [ "$UI_LANG" = es ] && msg 'Fuente de iconos' "Nueva fuente:\n\n$selected" || msg 'Icon source' "New source:\n\n$selected"; fi
}

toggle_sounds() {
    local current status; current="$(get_ini_value behavior play_sounds)"
    if [ "$current" = true ]; then
        [ "$UI_LANG" = es ] && dialog --title Sonidos --yesno 'Los sonidos están ACTIVADOS.\n\n¿Quieres desactivarlos?' 10 60 || dialog --title Sounds --yesno 'Sounds are ENABLED.\n\nDo you want to disable them?' 10 60; status=$?
        if [ "$status" -eq 0 ]; then set_ini_value behavior play_sounds false; [ "$UI_LANG" = es ] && msg Sonidos 'Sonidos desactivados.' || msg Sounds 'Sounds disabled.'; fi
    else
        [ "$UI_LANG" = es ] && dialog --title Sonidos --yesno 'Los sonidos están DESACTIVADOS.\n\n¿Quieres activarlos?' 10 60 || dialog --title Sounds --yesno 'Sounds are DISABLED.\n\nDo you want to enable them?' 10 60; status=$?
        if [ "$status" -eq 0 ]; then set_ini_value behavior play_sounds true; [ "$UI_LANG" = es ] && msg Sonidos 'Sonidos activados.' || msg Sounds 'Sounds enabled.'; fi
    fi
}

show_paths() {
    local c
    if [ "$UI_LANG" = es ]; then c="Instalación: $INSTALL_DIR\n\nTemas base: $BASE_THEMES_DIR\n\nMenú: $MENU_THEMES_DIR\nBotón: $BUTTON_THEMES_DIR\nSonido: $SOUND_THEMES_DIR\nIconos: $ICON_THEMES_DIR\n\nConfig: $CONFIG_FILE\nLanzador: $BIN_FILE"; msg 'Rutas detectadas' "$c"; else c="Installation: $INSTALL_DIR\n\nBase themes: $BASE_THEMES_DIR\n\nMenu: $MENU_THEMES_DIR\nButton: $BUTTON_THEMES_DIR\nSound: $SOUND_THEMES_DIR\nIcons: $ICON_THEMES_DIR\n\nConfig: $CONFIG_FILE\nLauncher: $BIN_FILE"; msg 'Detected paths' "$c"; fi
}

show_config() { local c; c="$(cat "$CONFIG_FILE")"; [ "$UI_LANG" = es ] && dialog --title 'Configuración actual' --msgbox "$c" 22 78 || dialog --title 'Current configuration' --msgbox "$c" 22 78; }

edit_config() {
    local e; for e in nano mousepad xed geany; do command -v "$e" >/dev/null 2>&1 && { clear; "$e" "$CONFIG_FILE"; return; }; done
    [ "$UI_LANG" = es ] && msg Editor "No encontré nano, mousepad, xed ni geany.\n\nEdita manualmente:\n\n$CONFIG_FILE" || msg Editor "nano, mousepad, xed and geany were not found.\n\nEdit manually:\n\n$CONFIG_FILE"
}

reset_config() {
    local status
    [ "$UI_LANG" = es ] && dialog --title 'Restaurar configuración' --yesno 'Esto reemplazará tu config.ini por una configuración básica.\n\n¿Continuar?' 10 70 || dialog --title 'Reset configuration' --yesno 'This will replace config.ini with a basic configuration.\n\nContinue?' 10 70; status=$?
    if [ "$status" -eq 0 ]; then create_default_config; set_ini_value interface config_language "$UI_LANG"; [ "$UI_LANG" = es ] && msg Restaurado 'Se restauró la configuración básica.' || msg Restored 'The basic configuration was restored.'; fi
}

test_xfcemenu() {
    if [ -x "$BIN_FILE" ]; then "$BIN_FILE" & [ "$UI_LANG" = es ] && msg Prueba 'Se lanzó XFCEMenu.' || msg Test 'XFCEMenu was launched.'; else [ "$UI_LANG" = es ] && msg Error "No se encontró el lanzador:\n\n$BIN_FILE" || msg Error "Launcher not found:\n\n$BIN_FILE"; fi
}

main_menu() {
    local menu sounds icons choice status
    while true; do
        menu="$(get_ini_value theme menu_theme)"; sounds="$(get_ini_value behavior play_sounds)"; icons="$(get_ini_value icons source)"
        [ -n "$icons" ] || icons=auto
        if [ "$UI_LANG" = es ]; then
            [ -n "$menu" ] || menu='sin definir'; [ -n "$sounds" ] || sounds='sin definir'
            choice="$(dialog --clear --title 'XFCEMenu Config' --menu "Menú: $menu | Sonidos: $sounds | Iconos: $icons" 24 82 14 \
                1 'Cambiar tema de menú / Ver vista previa' 2 'Cambiar tema de botón' 3 'Cambiar tema de sonidos' 4 'Cambiar tema de iconos' 5 'Fuente de iconos: auto / tema / sistema' 6 'Activar / desactivar sonidos' 7 'Ver config.ini' 8 'Editar config.ini manualmente' 9 'Restaurar configuración básica' 10 'Ver rutas detectadas' 11 'Probar XFCEMenu' 12 'Idioma del configurador' 0 Salir 3>&1 1>&2 2>&3)"
        else
            [ -n "$menu" ] || menu=undefined; [ -n "$sounds" ] || sounds=undefined
            choice="$(dialog --clear --title 'XFCEMenu Config' --menu "Menu: $menu | Sounds: $sounds | Icons: $icons" 24 82 14 \
                1 'Change menu theme / View preview' 2 'Change button theme' 3 'Change sound theme' 4 'Change icon theme' 5 'Icon source: auto / theme / system' 6 'Enable / disable sounds' 7 'View config.ini' 8 'Edit config.ini manually' 9 'Restore basic configuration' 10 'View detected paths' 11 'Test XFCEMenu' 12 'Configurator language' 0 Exit 3>&1 1>&2 2>&3)"
        fi
        status=$?; if [ "$status" -eq "$DIALOG_CANCEL" ] || [ "$status" -eq "$DIALOG_ESC" ]; then clear; exit 0; fi
        case "$choice" in
            1) select_menu_theme;; 2) select_button_theme;; 3) select_sound_theme;; 4) select_icon_theme;;
            5) select_icon_source;; 6) toggle_sounds;; 7) show_config;; 8) edit_config;; 9) reset_config;;
            10) show_paths;; 11) test_xfcemenu;; 12) change_language;; 0) clear; exit 0;;
        esac
    done
}

init_language
main_menu
