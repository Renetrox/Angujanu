#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import re
import html
import configparser
import json
import shlex
import shutil

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
import cairo

from legacy_loader import load_menu_theme
from command_mapper import run_command


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THEMES_DIR = os.path.join(BASE_DIR, "themes")


CONFIG_DIR = os.path.expanduser("~/.config/xfcemenu")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.ini")

CACHE_DIR = os.path.expanduser("~/.cache/xfcemenu")
APPS_CACHE_FILE = os.path.join(CACHE_DIR, "apps.cache.json")
APPS_CACHE_VERSION = 2

FAVORITES_FILE = os.path.join(CONFIG_DIR, "favorites.txt")

# Corrección global para textos legacy dibujados sobre botones PNG.
# Los temas de GnoMenu/GTK2 tienden a quedar un poco grandes y bajos en GTK3.
# Esto se aplica desde el motor, no por tema, para mantener coherencia entre skins.
LEGACY_BUTTON_TEXT_SCALE = 0.94
LEGACY_BUTTON_TEXT_BASELINE_OFFSET_Y = -2
LEGACY_MENU_PANEL_GAP = 8
LEGACY_MENU_LAUNCHER_GUESS_SIZE = 32

THEME_KINDS = {
    "menu": "Menu",
    "icon": "Icon",
    "button": "Button",
    "sound": "Sound",
}

DEFAULT_CONFIG = {
    "theme": {
        "menu_theme": "Win2-7Standard-Es",
        "icon_theme": "Vista",
        "button_theme": "Win2-7",
        "sound_theme": "Win2-7",
    },
    "icons": {
        "source": "auto",
    },
    "behavior": {
        "close_on_focus_out": "true",
        "play_sounds": "true",
        "show_avatar": "true",
        "panel_mode": "true",
    },
    "interface": {
        "language": "auto",
        "icon_size": "24",
        "program_text_auto_color": "true",
    },
}


def ensure_config_file():
    """
    Crea ~/.config/xfcemenu/config.ini si todavía no existe.
    El archivo guarda solo nombres de carpetas; los temas se detectan en themes/*.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)

    if os.path.isfile(CONFIG_FILE):
        return

    config = configparser.ConfigParser()
    for section, values in DEFAULT_CONFIG.items():
        config[section] = values

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config.write(f)

        print(f"XFCEMenu: config creado en {CONFIG_FILE}")
    except Exception as e:
        print(f"XFCEMenu: no se pudo crear config.ini: {e}")


def load_xfcemenu_config():
    ensure_config_file()

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    changed = False

    # Completar claves faltantes sin borrar preferencias existentes.
    for section, values in DEFAULT_CONFIG.items():
        if section not in config:
            config[section] = {}
            changed = True

        for key, value in values.items():
            if key not in config[section]:
                config[section][key] = value
                changed = True

    if changed:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                config.write(f)
        except Exception as e:
            print(f"XFCEMenu: no se pudo actualizar config.ini: {e}")

    return config


def config_bool(config, section, key, fallback=True):
    try:
        return config.getboolean(section, key, fallback=fallback)
    except Exception:
        return fallback


def config_int(config, section, key, fallback=24):
    try:
        return config.getint(section, key, fallback=fallback)
    except Exception:
        return fallback


def theme_root(kind):
    return os.path.join(THEMES_DIR, THEME_KINDS.get(kind, kind))


def read_theme_metadata(path):
    """
    Lee datos básicos de themedata.xml si existe.
    Si el XML no existe o falla, se usa el nombre de carpeta.
    """
    info = {
        "folder": os.path.basename(path),
        "name": os.path.basename(path),
        "author": "",
        "type": "",
        "path": path,
    }

    themedata = os.path.join(path, "themedata.xml")

    if not os.path.isfile(themedata):
        return info

    try:
        import xml.etree.ElementTree as ET

        root = ET.parse(themedata).getroot()
        info["type"] = root.attrib.get("type", "")

        content_data = root.find(".//ContentData")
        if content_data is not None:
            info["name"] = content_data.attrib.get("Name", info["name"])
            info["author"] = content_data.attrib.get("Author", "")

    except Exception as e:
        print(f"XFCEMenu: no se pudo leer metadata de tema {themedata}: {e}")

    return info


def list_theme_packages(kind):
    root = theme_root(kind)

    if not os.path.isdir(root):
        return []

    packages = []

    try:
        folders = sorted(os.listdir(root), key=lambda item: item.lower())
    except Exception:
        return []

    for folder in folders:
        path = os.path.join(root, folder)

        if not os.path.isdir(path):
            continue

        info = read_theme_metadata(path)

        # Si themedata declara tipo, validamos sin ser demasiado estrictos.
        declared = (info.get("type") or "").strip().lower()
        expected = THEME_KINDS.get(kind, kind).strip().lower()

        if declared and declared != expected:
            continue

        packages.append(info)

    return packages


def package_exists(kind, name):
    if not name:
        return False

    return os.path.isdir(os.path.join(theme_root(kind), name))


def first_theme_package(kind):
    packages = list_theme_packages(kind)
    if packages:
        return packages[0]["folder"]
    return ""


def guess_related_package(kind, menu_theme_name):
    """
    Intenta deducir paquetes relacionados.
    Ejemplo:
        Win2-7Standard-Es -> Win2-7
    """
    if not menu_theme_name:
        return ""

    root = theme_root(kind)
    if not os.path.isdir(root):
        return ""

    candidates = []
    candidates.append(menu_theme_name)

    if menu_theme_name.lower().startswith("win2-7"):
        candidates.append("Win2-7")

    simplified = re.sub(
        r"(standard|basic|classic|black|blue|green|red|purple|pink|turquoise|human|murrine|crystal).*",
        "",
        menu_theme_name,
        flags=re.IGNORECASE
    ).strip("-_ ")

    if simplified:
        candidates.append(simplified)

    for candidate in candidates:
        if os.path.isdir(os.path.join(root, candidate)):
            return candidate

    return ""


def resolve_theme_choice(kind, requested, fallback="", menu_theme_name=""):
    """
    Resuelve un paquete existente:
    1. valor pedido por argumento/config
    2. fallback explícito
    3. deducción desde el menú
    4. primer paquete detectado
    """
    for value in (requested, fallback):
        value = (value or "").strip()
        if value and package_exists(kind, value):
            return value

    guessed = guess_related_package(kind, menu_theme_name)
    if guessed:
        return guessed

    return first_theme_package(kind)


def print_available_themes():
    for kind in ("menu", "icon", "button", "sound"):
        print(f"\n[{THEME_KINDS[kind]}]")
        packages = list_theme_packages(kind)

        if not packages:
            print("  (sin paquetes detectados)")
            continue

        for info in packages:
            author = f" — {info['author']}" if info.get("author") else ""
            print(f"  {info['folder']}  ({info['name']}{author})")



class DesktopApp:
    def __init__(self, name, exec_cmd, icon="", comment="", desktop_file="", categories=""):
        self.name = name
        self.exec_cmd = exec_cmd
        self.icon = icon
        self.comment = comment
        self.desktop_file = desktop_file
        self.categories = categories


class MenuCategory:
    def __init__(self, key, name, icon, matcher):
        self.key = key
        self.name = name
        self.icon = icon
        self.matcher = matcher
        self.apps = []


class BackItem:
    def __init__(self, label="Volver"):
        self.name = label
        # Usamos el icono GTK/tema, no un símbolo en el texto.
        # Si el tema tiene su propio icono de volver, load_icon_pixbuf() lo prioriza.
        self.icon = "go-previous"


class PlaceItem:
    def __init__(self, name, icon, xdg_key=None, path=None):
        self.name = name
        self.icon = icon
        self.xdg_key = xdg_key
        self.path = path


class ActionItem:
    def __init__(self, name, icon, command):
        self.name = name
        self.icon = icon
        self.command = command


class SoundManager:
    """
    Reproductor simple para temas Sound legacy de GnoMenu/XFCEMenu.
    Busca nombres fijos:
        show-menu.ogg
        hide-menu.ogg
        button-pressed.ogg
        tab-pressed.ogg
    """
    EVENT_FILES = {
        "show": ("show-menu.ogg", "show-menu.wav"),
        "hide": ("hide-menu.ogg", "hide-menu.wav"),
        "button": ("button-pressed.ogg", "button-pressed.wav", "button.wav", "click.wav"),
        "tab": ("tab-pressed.ogg", "tab-pressed.wav"),
    }

    def __init__(self, sound_theme="", enabled=True):
        self.sound_theme = sound_theme or ""
        self.enabled = bool(enabled)
        self.sound_dir = os.path.join(theme_root("sound"), self.sound_theme) if self.sound_theme else ""
        self._last_play_us = {}
        self.cooldown_us = 120000

    def get_sound_path(self, event_name):
        if not self.enabled or not self.sound_dir or not os.path.isdir(self.sound_dir):
            return None

        for filename in self.EVENT_FILES.get(event_name, ()):
            path = os.path.join(self.sound_dir, filename)
            if os.path.isfile(path):
                return path

        return None

    def play(self, event_name):
        path = self.get_sound_path(event_name)

        if not path:
            return False

        # Evita ráfagas si GTK dispara el mismo evento varias veces seguidas.
        try:
            now = GLib.get_monotonic_time()
            last = self._last_play_us.get(event_name, 0)
            if now - last < self.cooldown_us:
                return False
            self._last_play_us[event_name] = now
        except Exception:
            pass

        players = [
            ["paplay", path],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
            ["mpv", "--no-video", "--really-quiet", path],
            ["cvlc", "--play-and-exit", "--quiet", path],
        ]

        for cmd in players:
            if not shutil.which(cmd[0]):
                continue

            try:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                pass

        print(f"XFCEMenu: no hay reproductor disponible para sonido: {path}")
        return False


def detect_language():
    """
    Detecta idioma básico desde variables de entorno.
    Por ahora soporta es/pt/en y cae a es.
    """
    lang = (
        os.environ.get("XFCEMENU_LANG")
        or os.environ.get("LANGUAGE")
        or os.environ.get("LC_ALL")
        or os.environ.get("LC_MESSAGES")
        or os.environ.get("LANG")
        or ""
    ).lower()

    if lang.startswith("pt"):
        return "pt"

    if lang.startswith("en"):
        return "en"

    return "es"


def get_locale_candidates_for_desktop():
    """
    Devuelve sufijos de idioma para leer claves traducidas de archivos .desktop.

    Ejemplo:
        LANG=es_PY.UTF-8 -> ["es_PY", "es"]
        LANG=pt_BR.UTF-8 -> ["pt_BR", "pt"]

    También respeta XFCEMENU_LANG para pruebas:
        XFCEMENU_LANG=pt
        XFCEMENU_LANG=es
    """
    raw = (
        os.environ.get("XFCEMENU_LANG")
        or os.environ.get("LC_ALL")
        or os.environ.get("LC_MESSAGES")
        or os.environ.get("LANG")
        or ""
    )

    raw = raw.strip()

    if not raw:
        lang = detect_language()
        return [lang] if lang else []

    # LANGUAGE puede venir como es:en_US:en; tomamos el primero.
    raw = raw.split(":")[0]

    # Quitar codificación y modificador.
    raw = raw.split(".")[0]
    raw = raw.split("@")[0]
    raw = raw.replace("-", "_")

    result = []

    if raw:
        result.append(raw)

        if "_" in raw:
            result.append(raw.split("_")[0])

    base = detect_language()

    if base and base not in result:
        result.append(base)

    # Quitar duplicados conservando orden.
    clean = []
    seen = set()

    for item in result:
        item = item.strip()

        if item and item not in seen:
            seen.add(item)
            clean.append(item)

    return clean


def get_localized_desktop_value(entry, key, default=""):
    """
    Lee una clave traducida de .desktop:
        Name[es_PY], Name[es], Name
        Comment[es_PY], Comment[es], Comment

    Si no existe traducción, cae al valor base.
    """
    for locale in get_locale_candidates_for_desktop():
        localized_key = f"{key}[{locale}]"

        if localized_key in entry:
            value = entry.get(localized_key, "").strip()

            if value:
                return value

    return entry.get(key, default).strip()


LANG_CATEGORY_LABELS = {
    "es": {
        "browse": "Navegar por Internet",
        "email": "Correo electrónico",
        "all": "Aplicaciones",
        "development": "Desarrollo",
        "games": "Juegos",
        "graphics": "Gráficos",
        "internet": "Internet",
        "multimedia": "Sonido y video",
        "office": "Oficina",
        "software": "Centro de software",
        "places": "Lugares",
        "system": "Sistema",
        "utilities": "Accesorios",
        "wine": "Wine",
    },
    "pt": {
        "browse": "Navegar na Internet",
        "email": "E-mail",
        "all": "Aplicações",
        "development": "Desenvolvimento",
        "games": "Jogos",
        "graphics": "Gráficos",
        "internet": "Internet",
        "multimedia": "Som & Vídeo",
        "office": "Escritório",
        "software": "Centro de Software",
        "places": "Locais",
        "system": "Sistema",
        "utilities": "Acessórios",
        "wine": "Wine",
    },
    "en": {
        "browse": "Browse Internet",
        "email": "E-mail",
        "all": "Applications",
        "development": "Development",
        "games": "Games",
        "graphics": "Graphics",
        "internet": "Internet",
        "multimedia": "Sound & Video",
        "office": "Office",
        "software": "Software Center",
        "places": "Places",
        "system": "System",
        "utilities": "Accessories",
        "wine": "Wine",
    },
}


def tr_category(key, fallback):
    lang = detect_language()
    return LANG_CATEGORY_LABELS.get(lang, LANG_CATEGORY_LABELS["es"]).get(key, fallback)


UI_LABELS = {
    "es": {
        "home": "Carpeta personal",
        "desktop": "Escritorio",
        "documents": "Documentos",
        "downloads": "Descargas",
        "music": "Música",
        "pictures": "Imágenes",
        "videos": "Videos",
        "settings": "Configuración",
        "lock": "Bloquear pantalla",
        "logout": "Cerrar sesión",
        "restart": "Reiniciar",
        "shutdown": "Apagar",
        "no_favorites": "Sin favoritos",
        "recent_pending": "Elementos recientes pendiente",
    },
    "pt": {
        "home": "Pasta pessoal",
        "desktop": "Área de trabalho",
        "documents": "Documentos",
        "downloads": "Downloads",
        "music": "Música",
        "pictures": "Imagens",
        "videos": "Vídeos",
        "settings": "Configurações",
        "lock": "Trancar",
        "logout": "Sair",
        "restart": "Reiniciar",
        "shutdown": "Desligar",
        "no_favorites": "Sem favoritos",
        "recent_pending": "Itens recentes pendente",
    },
    "en": {
        "home": "Home Folder",
        "desktop": "Desktop",
        "documents": "Documents",
        "downloads": "Downloads",
        "music": "Music",
        "pictures": "Pictures",
        "videos": "Videos",
        "settings": "Settings",
        "lock": "Lock Screen",
        "logout": "Log Out",
        "restart": "Restart",
        "shutdown": "Shut Down",
        "no_favorites": "No favorites",
        "recent_pending": "Recent items pending",
    },
}


def tr_ui(key, fallback):
    lang = detect_language()
    return UI_LABELS.get(lang, UI_LABELS["es"]).get(key, fallback)



LEGACY_BUTTON_LABELS = {
    "es": {
        "home": "Carpeta personal",
        "documents": "Documentos",
        "pictures": "Imágenes",
        "music": "Música",
        "videos": "Videos",
        "games": "Juegos",
        "computer": "Equipo",
        "network": "Red",
        "network config": "Conectar al servidor",
        "control panel": "Configuración",
        "package manager": "Gestor de paquetes",
        "help": "Ayuda",
        "search": "Buscar",
        "run": "Ejecutar...",
        "power": "Apagar",
        "aux": "",
        "lock": "Bloquear",
        "logoutnow": "Cerrar sesión",
        "logout": "Cerrar sesión",
        "shutdown": "Apagar",
        "restart": "Reiniciar",
        "reboot": "Reiniciar",
        "suspend": "Suspender",
        "hibernate": "Hibernar",
        "switch user": "Cambiar usuario",
    },
    "pt": {
        "home": "Pasta pessoal",
        "documents": "Documentos",
        "pictures": "Imagens",
        "music": "Música",
        "videos": "Vídeos",
        "games": "Jogos",
        "computer": "Computador",
        "network": "Rede",
        "network config": "Conectar ao servidor",
        "control panel": "Configurações",
        "package manager": "Gerenciador de pacotes",
        "help": "Ajuda",
        "search": "Procurar",
        "run": "Executar...",
        "power": "Desligar",
        "aux": "",
        "lock": "Trancar",
        "logoutnow": "Sair",
        "logout": "Sair",
        "shutdown": "Desligar",
        "restart": "Reiniciar",
        "reboot": "Reiniciar",
        "suspend": "Suspender",
        "hibernate": "Hibernar",
        "switch user": "Trocar usuário",
    },
    "en": {
        "home": "Home Folder",
        "documents": "Documents",
        "pictures": "Pictures",
        "music": "Music",
        "videos": "Videos",
        "games": "Games",
        "computer": "Computer",
        "network": "Network",
        "network config": "Connect to Server",
        "control panel": "Control Center",
        "package manager": "Package Manager",
        "help": "Help",
        "search": "Search",
        "run": "Run...",
        "power": "Shut Down",
        "aux": "",
        "lock": "Lock",
        "logoutnow": "Log Out",
        "logout": "Log Out",
        "shutdown": "Shut Down",
        "restart": "Restart",
        "reboot": "Restart",
        "suspend": "Suspend",
        "hibernate": "Hibernate",
        "switch user": "Switch User",
    },
}


def tr_legacy_button_label(command, fallback):
    command_key = (command or "").strip().lower()
    fallback_key = (fallback or "").strip().lower()
    lang = detect_language()

    # Algunos temas legacy tienen errores: Videos con Command="Games".
    # En esos casos, el Name del botón es más confiable que el Command.
    if fallback_key in LEGACY_BUTTON_LABELS.get(lang, {}):
        return LEGACY_BUTTON_LABELS[lang][fallback_key]

    if command_key in LEGACY_BUTTON_LABELS.get(lang, {}):
        return LEGACY_BUTTON_LABELS[lang][command_key]

    if fallback_key in LEGACY_BUTTON_LABELS.get("es", {}):
        return LEGACY_BUTTON_LABELS["es"][fallback_key]

    if command_key in LEGACY_BUTTON_LABELS.get("es", {}):
        return LEGACY_BUTTON_LABELS["es"][command_key]

    return fallback


CATEGORY_DEFINITIONS = [
    # key, label, icon, matcher
    ("browse", tr_category("browse", "Browse Internet"), "internet-web-browser", "browser"),
    ("email", tr_category("email", "E-mail"), "internet-mail", "email"),

    # Categorías principales estilo GnoMenu.
    ("all", tr_category("all", "Applications"), "applications-other", "all"),
    ("utilities", tr_category("utilities", "Utilities"), "applications-utilities", "Utility;Accessories;FileManager;Archiving;Compression;TextEditor;TerminalEmulator"),
    ("office", tr_category("office", "Office"), "applications-office", "Office"),
    ("graphics", tr_category("graphics", "Graphics"), "applications-graphics", "Graphics"),
    ("internet", tr_category("internet", "Internet"), "applications-internet", "Network"),
    ("games", tr_category("games", "Games"), "applications-games", "Game"),
    ("multimedia", tr_category("multimedia", "Multimedia"), "applications-multimedia", "AudioVideo;Audio;Video;Player;Recorder"),
    ("development", tr_category("development", "Development"), "applications-development", "Development"),
    ("software", tr_category("software", "Software Center"), "system-software-install", "PackageManager;System;Settings"),
    ("places", tr_category("places", "Places"), "folder", "places"),
    ("system", tr_category("system", "System"), "applications-system", "System;Settings"),
    ("wine", tr_category("wine", "Wine"), "applications-wine", "Wine;X-Wine"),
]


def split_categories(categories):
    return {item.strip() for item in (categories or "").split(";") if item.strip()}


def app_matches_category(app, matcher):
    cats = split_categories(getattr(app, "categories", ""))
    name = (getattr(app, "name", "") or "").lower()
    cmd = (getattr(app, "exec_cmd", "") or "").lower()
    desktop_file = (getattr(app, "desktop_file", "") or "").lower()

    if matcher == "all":
        return True

    if matcher == "browser":
        return (
            "WebBrowser" in cats
            or "Browser" in cats
            or "webbrowser" in desktop_file
            or "firefox" in cmd
            or "chromium" in cmd
            or "google-chrome" in cmd
        )

    if matcher == "email":
        return (
            "Email" in cats
            or "Mail" in cats
            or "thunderbird" in cmd
            or "mail" in name
        )

    wanted = {item.strip() for item in matcher.split(";") if item.strip()}

    if cats & wanted:
        return True

    if "Wine" in wanted or "X-Wine" in wanted:
        return "wine" in cmd or "wine" in desktop_file

    return False


def clean_desktop_exec(exec_cmd):
    """
    Limpia los códigos de campo de archivos .desktop.
    Ejemplos:
        firefox %u -> firefox
        thunar %F -> thunar
        libreoffice --writer %U -> libreoffice --writer
    """
    if not exec_cmd:
        return ""

    # %i, %c y %k pueden expandirse con icono/nombre/ruta, pero para este menú
    # es más seguro quitarlos y ejecutar el comando base.
    exec_cmd = re.sub(r"\s+%[fFuUdDnNickvm]", "", exec_cmd)
    exec_cmd = exec_cmd.replace("%%", "%")

    return exec_cmd.strip()


def desktop_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes")


def desktop_environment_allows(entry):
    """
    Respeta un poco las claves estándar de .desktop sin ponerse demasiado estricto.
    En XFCE conviene ocultar lo marcado NotShowIn=XFCE, pero no bloquear todo
    lo que no tenga OnlyShowIn.
    """
    current = {"XFCE", "X-Cinnamon", "GNOME", "GTK"}

    not_show = entry.get("NotShowIn", "")
    if not_show:
        blocked = {item.strip() for item in not_show.split(";") if item.strip()}
        if "XFCE" in blocked:
            return False

    only_show = entry.get("OnlyShowIn", "")
    if only_show:
        allowed = {item.strip() for item in only_show.split(";") if item.strip()}
        if allowed and not (allowed & current):
            return False

    return True


def tryexec_available(try_exec):
    if not try_exec:
        return True

    try:
        parts = shlex.split(try_exec)
    except Exception:
        parts = try_exec.split()

    if not parts:
        return True

    command = parts[0]

    if os.path.isabs(command):
        return os.path.exists(command) and os.access(command, os.X_OK)

    return shutil.which(command) is not None


def get_xdg_user_dir(key, fallback):
    if key == "HOME":
        return os.path.expanduser("~")

    try:
        output = subprocess.check_output(
            ["xdg-user-dir", key],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=1
        ).strip()

        if output:
            return os.path.expanduser(output)
    except Exception:
        pass

    return os.path.expanduser(fallback or "~")


def open_path(path):
    if not path:
        return

    try:
        subprocess.Popen(
            ["xdg-open", os.path.expanduser(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"XFCEMenu: no se pudo abrir ruta '{path}': {e}")


def append_unique_path(paths, path):
    path = os.path.expanduser(path or "").strip()

    if not path:
        return

    normalized = os.path.normpath(path)

    if normalized not in paths:
        paths.append(normalized)


def get_xdg_data_dirs():
    """
    Devuelve carpetas base XDG respetando la sesión actual.

    Flatpak y Snap agregan lanzadores fuera de las rutas clásicas en varias
    distros, por eso se suman explícitamente más abajo.
    """
    paths = []

    data_home = os.environ.get(
        "XDG_DATA_HOME",
        os.path.expanduser("~/.local/share")
    )
    append_unique_path(paths, data_home)

    data_dirs = os.environ.get(
        "XDG_DATA_DIRS",
        "/usr/local/share:/usr/share"
    )

    for path in data_dirs.split(":"):
        append_unique_path(paths, path)

    return paths


def get_desktop_app_dirs():
    """
    Carpetas de aplicaciones .desktop que XFCEMenu escanea.

    Se mantiene en una función para que el cache y el escaneo real usen
    exactamente la misma lista.
    """
    app_dirs = []

    for base_dir in get_xdg_data_dirs():
        append_unique_path(app_dirs, os.path.join(base_dir, "applications"))

    # Lanzadores exportados por Flatpak.
    append_unique_path(
        app_dirs,
        "~/.local/share/flatpak/exports/share/applications"
    )
    append_unique_path(
        app_dirs,
        "/var/lib/flatpak/exports/share/applications"
    )

    # Lanzadores exportados por Snap.
    append_unique_path(app_dirs, "/var/lib/snapd/desktop/applications")

    # Compatibilidad con sesiones antiguas que no declaran XDG_DATA_DIRS.
    append_unique_path(app_dirs, "/usr/share/applications")
    append_unique_path(app_dirs, "/usr/local/share/applications")
    append_unique_path(app_dirs, "~/.local/share/applications")

    return app_dirs


def build_apps_cache_signature(app_dirs=None):
    """
    Crea una firma liviana del estado de los .desktop.

    No parsea los archivos; solo revisa nombres, tamaño y mtime. Así se puede
    saber si el cache sigue siendo válido sin repetir todo el trabajo pesado.
    """
    if app_dirs is None:
        app_dirs = get_desktop_app_dirs()

    signature = {
        "version": APPS_CACHE_VERSION,
        "locale": get_locale_candidates_for_desktop(),
        "dirs": [],
    }

    for app_dir in app_dirs:
        dir_info = {
            "path": app_dir,
            "exists": os.path.isdir(app_dir),
            "files": [],
        }

        if not os.path.isdir(app_dir):
            signature["dirs"].append(dir_info)
            continue

        try:
            filenames = sorted(
                filename for filename in os.listdir(app_dir)
                if filename.endswith(".desktop")
            )
        except Exception:
            signature["dirs"].append(dir_info)
            continue

        for filename in filenames:
            path = os.path.join(app_dir, filename)

            try:
                stat = os.stat(path)
            except Exception:
                continue

            dir_info["files"].append({
                "name": filename,
                "mtime_ns": getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1000000000)),
                "size": stat.st_size,
            })

        signature["dirs"].append(dir_info)

    return signature


def desktop_app_to_cache_dict(app):
    return {
        "name": app.name,
        "exec_cmd": app.exec_cmd,
        "icon": app.icon,
        "comment": app.comment,
        "desktop_file": app.desktop_file,
        "categories": app.categories,
    }


def desktop_app_from_cache_dict(data):
    return DesktopApp(
        name=data.get("name", ""),
        exec_cmd=data.get("exec_cmd", ""),
        icon=data.get("icon", ""),
        comment=data.get("comment", ""),
        desktop_file=data.get("desktop_file", ""),
        categories=data.get("categories", ""),
    )


def load_apps_cache_if_valid(signature):
    if not os.path.isfile(APPS_CACHE_FILE):
        return None

    try:
        with open(APPS_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None

    if payload.get("version") != APPS_CACHE_VERSION:
        return None

    if payload.get("signature") != signature:
        return None

    apps_data = payload.get("apps", [])

    if not isinstance(apps_data, list):
        return None

    apps = []

    for item in apps_data:
        if not isinstance(item, dict):
            continue

        app = desktop_app_from_cache_dict(item)

        if app.name and app.exec_cmd:
            apps.append(app)

    apps.sort(key=lambda app: app.name.lower())
    print(f"XFCEMenu: apps cargadas desde cache ({len(apps)})")
    return apps


def save_apps_cache(signature, apps):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)

        payload = {
            "version": APPS_CACHE_VERSION,
            "signature": signature,
            "apps": [desktop_app_to_cache_dict(app) for app in apps],
        }

        tmp_path = APPS_CACHE_FILE + ".tmp"

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        os.replace(tmp_path, APPS_CACHE_FILE)
        print(f"XFCEMenu: cache de apps actualizado ({len(apps)})")
    except Exception as e:
        print(f"XFCEMenu: no se pudo guardar cache de apps: {e}")


def scan_desktop_apps():
    """
    Carga programas reales desde .desktop.
    Busca en sistema + usuario, filtra ocultos y evita duplicados.
    """
    apps = []
    seen = set()

    app_dirs = get_desktop_app_dirs()

    for app_dir in app_dirs:
        if not os.path.isdir(app_dir):
            continue

        try:
            filenames = sorted(os.listdir(app_dir))
        except Exception:
            continue

        for filename in filenames:
            if not filename.endswith(".desktop"):
                continue

            desktop_path = os.path.join(app_dir, filename)

            parser = configparser.ConfigParser(
                interpolation=None,
                strict=False
            )

            # Mantener mayúsculas/minúsculas en claves por si algún .desktop raro depende de eso.
            parser.optionxform = str

            try:
                parser.read(desktop_path, encoding="utf-8")
            except Exception:
                continue

            if "Desktop Entry" not in parser:
                continue

            entry = parser["Desktop Entry"]

            if entry.get("Type", "Application") != "Application":
                continue

            if desktop_bool(entry.get("NoDisplay", "false")):
                continue

            if desktop_bool(entry.get("Hidden", "false")):
                continue

            if not desktop_environment_allows(entry):
                continue

            if not tryexec_available(entry.get("TryExec", "")):
                continue

            name = get_localized_desktop_value(entry, "Name", "")

            if not name:
                name = get_localized_desktop_value(entry, "GenericName", "")

            exec_cmd = clean_desktop_exec(entry.get("Exec", "").strip())

            if not name or not exec_cmd:
                continue

            # Evita duplicados por archivo desktop y por nombre+comando.
            key = (filename.lower(), name.lower(), exec_cmd.lower())
            name_key = (name.lower(), exec_cmd.lower())

            if key in seen or name_key in seen:
                continue

            seen.add(key)
            seen.add(name_key)

            apps.append(DesktopApp(
                name=name,
                exec_cmd=exec_cmd,
                icon=entry.get("Icon", "").strip(),
                comment=get_localized_desktop_value(entry, "Comment", ""),
                desktop_file=desktop_path,
                categories=entry.get("Categories", "").strip()
            ))

    apps.sort(key=lambda app: app.name.lower())
    return apps


def load_desktop_apps():
    """
    Carga programas usando cache si el estado de los .desktop no cambió.

    Primera apertura:
        escanea .desktop y guarda ~/.cache/xfcemenu/apps.cache.json

    Siguientes aperturas:
        valida firma ligera y carga directamente desde cache.
    """
    signature = build_apps_cache_signature()

    cached_apps = load_apps_cache_if_valid(signature)
    if cached_apps is not None:
        return cached_apps

    apps = scan_desktop_apps()
    save_apps_cache(signature, apps)
    return apps



class XFCEMenuWindow(Gtk.Window):
    def __init__(
        self,
        theme,
        icon_theme="",
        button_theme="",
        sound_theme="",
        play_sounds=True,
        close_on_focus_out=True,
        show_avatar=True,
        icon_size=24,
        icon_source="auto",
    ):
        super().__init__(title="XFCEMenu")

        self.theme = theme
        self.icon_theme = icon_theme or ""
        self.button_theme = button_theme or ""
        self.sound_theme = sound_theme or ""
        self.icon_source = (icon_source or "auto").strip().lower()
        if self.icon_source not in ("auto", "theme", "system"):
            self.icon_source = "auto"
        self.play_sounds = bool(play_sounds)
        self.close_on_focus_out = bool(close_on_focus_out)

        # Capabilities legacy de GnoMenu.
        # La preferencia del usuario sigue mandando, pero el tema puede indicar
        # que no dispone de avatar o búsqueda.
        capabilities = getattr(self.theme, "capabilities", None)
        self.theme_has_icon = bool(
            getattr(capabilities, "has_icon", 1)
            if capabilities is not None else 1
        )
        self.theme_has_search = bool(
            getattr(capabilities, "has_search", 1)
            if capabilities is not None else 1
        )
        self.theme_has_fade_transition = bool(
            getattr(capabilities, "has_fade_transition", 0)
            if capabilities is not None else 0
        )

        self.show_avatar = bool(show_avatar) and self.theme_has_icon
        self.icon_size = max(12, int(icon_size or 24))
        self.sound = SoundManager(self.sound_theme, enabled=self.play_sounds)
        self.close_requested = False
        self.hide_sound_started = False
        self.background_pixbuf = None
        self.shape_applied = False

        # Program list / search widgets.
        self.apps = load_desktop_apps()
        self.categories = self.build_categories()
        self.filtered_apps = list(self.apps)
        self.current_view = "categories"
        self.current_category = None
        self.current_tab_command = "1"
        self.active_tab_event = None
        self.program_scrolled = None
        self.program_listbox = None
        self.search_entry = None

        # Avatar / user icon.
        self.avatar_image_widget = None
        self.avatar_frame_widget = None
        self.avatar_normal_pixbuf = None
        self.avatar_hover_timer = None
        self.avatar_click_area = None
        self.app_context_menu = None
        self.context_menu_focus_guard = False

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)
        # XFCEMenu: no usar POPUP_MENU porque XFCE/GTK puede posicionarlo
        # como menú contextual cerca del puntero.
        # self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)

        self.set_size_request(theme.width, theme.height)
        self.set_default_size(theme.width, theme.height)

        # Cargamos primero el fondo para poder detectar si el área de programas
        # es clara u oscura. En temas negros, el texto GTK normal puede quedar
        # negro sobre negro; por eso ajustamos solo el color del texto, sin tocar
        # la selección ni la scrollbar del tema GTK.
        self.background_pixbuf = self.load_pixbuf(self.theme.background)
        self.program_area_is_dark = self.detect_program_area_is_dark()

        self.setup_transparency()

        self.connect("draw", self.on_draw)
        self.connect("realize", self.on_realize)

        self.add_events(Gdk.EventMask.KEY_PRESS_MASK)

        self.fixed = Gtk.Fixed()
        self.fixed.set_name("xfcemenu-root")

        try:
            self.fixed.set_has_window(False)
        except Exception:
            pass

        self.fixed.set_size_request(theme.width, theme.height)
        self.add(self.fixed)

        self.draw_program_widgets()
        self.draw_tabs()

        if self.show_avatar:
            self.draw_user_icon()
        self.draw_buttons()
        self.draw_labels()

        self.connect("focus-out-event", self.on_focus_out)
        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", self.on_destroy)

        self.position_near_bottom_left()

        GLib.idle_add(self.present)
        GLib.idle_add(self.play_show_sound_once)

    def play_show_sound_once(self):
        # GLib.idle_add repite el callback si devuelve True.
        # El reproductor devuelve True cuando pudo lanzar el sonido, así que
        # esta función siempre debe devolver False para sonar una sola vez.
        self.play_event_sound("show")
        return False

    def detect_program_area_is_dark(self):
        """
        Detecta si el área ProgramListSettings del PNG es oscura.

        GnoMenu usaba widgets GTK reales encima del skin. En temas claros, el
        color de texto GTK normal funciona bien; en temas negros puede quedar
        ilegible. Esta detección solo decide el color del texto de las filas.
        La selección, el hover y la scrollbar siguen siendo del tema GTK.
        """
        if not self.background_pixbuf:
            return False

        area = self.get_program_area()
        if not area:
            return False

        x, y, w, h = area

        bg_w = self.background_pixbuf.get_width()
        bg_h = self.background_pixbuf.get_height()

        x0 = max(0, min(bg_w, int(x)))
        y0 = max(0, min(bg_h, int(y)))
        x1 = max(0, min(bg_w, int(x + w)))
        y1 = max(0, min(bg_h, int(y + h)))

        if x1 <= x0 or y1 <= y0:
            return False

        rowstride = self.background_pixbuf.get_rowstride()
        n_channels = self.background_pixbuf.get_n_channels()
        has_alpha = self.background_pixbuf.get_has_alpha()
        pixels = self.background_pixbuf.get_pixels()

        # Muestreo ligero para no recorrer cada píxel en temas grandes.
        step_x = max(1, int((x1 - x0) / 32))
        step_y = max(1, int((y1 - y0) / 32))

        total = 0.0
        count = 0

        for py in range(y0, y1, step_y):
            for px in range(x0, x1, step_x):
                offset = py * rowstride + px * n_channels

                try:
                    r = pixels[offset]
                    g = pixels[offset + 1]
                    b = pixels[offset + 2]
                    a = pixels[offset + 3] if has_alpha and n_channels >= 4 else 255
                except Exception:
                    continue

                # Saltamos píxeles casi transparentes porque ahí manda el fondo
                # del escritorio, no el skin del menú.
                if a < 40:
                    continue

                luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
                total += luminance
                count += 1

        if count == 0:
            return False

        average = total / float(count)
        is_dark = average < 100.0

        print(
            "XFCEMenu: ProgramListSettings luminosidad promedio "
            f"{average:.1f} -> {'tema oscuro' if is_dark else 'tema claro'}"
        )

        return is_dark

    def get_program_text_colors(self):
        if getattr(self, "program_area_is_dark", False):
            return "#f2f2f2", "#cfcfcf", "#ffffff"

        return "#202020", "#555555", "#000000"

    def setup_transparency(self):
        screen = self.get_screen()

        try:
            visual = screen.get_rgba_visual()
            if visual is not None:
                self.set_visual(visual)
            else:
                print("XFCEMenu: no hay visual RGBA disponible.")
        except Exception as e:
            print(f"XFCEMenu: no se pudo activar visual RGBA: {e}")

        rgba = Gdk.RGBA()
        rgba.red = 0.0
        rgba.green = 0.0
        rgba.blue = 0.0
        rgba.alpha = 0.0

        try:
            self.override_background_color(Gtk.StateFlags.NORMAL, rgba)
        except Exception:
            pass

        program_text_color, program_message_color, search_text_color = self.get_program_text_colors()

        css = f"""
        window,
        GtkWindow,
        #xfcemenu-root {{
            background-color: transparent;
            background-image: none;
            border: none;
            box-shadow: none;
        }}

        fixed,
        frame,
        label,
        eventbox,
        box {{
            background-color: transparent;
            background-image: none;
            border: none;
            box-shadow: none;
        }}

        /*
         * La lista de programas usa widgets GTK reales, como GnoMenu.
         * Solo hacemos transparente el contenedor para que se vea el PNG del tema.
         * No anulamos :hover ni :selected; esas barras las dibuja el tema GTK.
         */
        #xfcemenu-program-scroll,
        #xfcemenu-program-scroll viewport,
        #xfcemenu-program-list {{
            background-color: transparent;
            background-image: none;
            border: none;
            box-shadow: none;
        }}

        #xfcemenu-program-scroll {{
            padding: 0px;
        }}

        #xfcemenu-program-row {{
            background-color: transparent;
            background-image: none;
        }}

        /*
         * Fallback visual solo para hover.
         * Quitamos :selected para evitar barras pegadas o estilos raros
         * cuando Gtk.ListBox mantiene una fila seleccionada.
         */
        #xfcemenu-program-row:hover {{
            background-color: alpha(@theme_selected_bg_color, 0.35);
            background-image: none;
        }}

        .xfcemenu-program-label {{
            color: {program_text_color};
        }}

        .xfcemenu-program-message {{
            color: {program_message_color};
        }}

        #xfcemenu-search-entry {{
            min-height: 0px;
            padding: 1px 4px;
            color: {search_text_color};
        }}
        """.encode("utf-8")

        provider = Gtk.CssProvider()
        provider.load_from_data(css)

        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_realize(self, widget):
        GLib.idle_add(self.apply_window_shape)

    def on_destroy(self, widget):
        self.cancel_avatar_hover_timer()

        if not self.hide_sound_started:
            self.play_event_sound("hide")

    def play_event_sound(self, event_name):
        if getattr(self, "sound", None):
            return self.sound.play(event_name)

        return False

    def close_menu(self, delay_ms=120):
        if self.close_requested:
            return False

        self.close_requested = True
        self.hide_sound_started = self.play_event_sound("hide")

        if self.hide_sound_started and delay_ms > 0:
            GLib.timeout_add(delay_ms, self.destroy_now)
        else:
            self.destroy_now()

        return False

    def destroy_now(self):
        try:
            Gtk.Window.destroy(self)
        except Exception:
            pass

        return False

    def theme_path(self, filename):
        return os.path.join(self.theme.theme_dir, filename)

    def load_pixbuf(self, filename):
        if not filename:
            return None

        candidates = []

        if os.path.isabs(filename):
            candidates.append(filename)

        candidates.append(self.theme_path(filename))

        # Prioridad configurada: Button/Icon/Menu elegidos por config.ini o argumentos.
        # Luego se mantienen los fallbacks generales para compatibilidad con temas viejos.
        for configured_kind, configured_name in (
            ("Button", getattr(self, "button_theme", "")),
            ("Icon", getattr(self, "icon_theme", "")),
            ("Menu", os.path.basename(getattr(self.theme, "theme_dir", "") or "")),
        ):
            if configured_name:
                candidates.append(os.path.join(THEMES_DIR, configured_kind, configured_name, filename))

        icon_root = os.path.join(THEMES_DIR, "Icon")
        if os.path.isdir(icon_root):
            for icon_theme in os.listdir(icon_root):
                candidates.append(os.path.join(icon_root, icon_theme, filename))

        button_root = os.path.join(THEMES_DIR, "Button")
        if os.path.isdir(button_root):
            for button_theme in os.listdir(button_root):
                candidates.append(os.path.join(button_root, button_theme, filename))

        menu_root = os.path.join(THEMES_DIR, "Menu")
        if os.path.isdir(menu_root):
            for menu_theme in os.listdir(menu_root):
                candidates.append(os.path.join(menu_root, menu_theme, filename))

        for subdir in ("icons", "buttons", "menus"):
            root = os.path.join(THEMES_DIR, subdir)
            if os.path.isdir(root):
                for theme_dir in os.listdir(root):
                    candidates.append(os.path.join(root, theme_dir, filename))

        checked = set()

        for path in candidates:
            if path in checked:
                continue

            checked.add(path)

            if os.path.isfile(path):
                try:
                    return GdkPixbuf.Pixbuf.new_from_file(path)
                except Exception as e:
                    print(f"XFCEMenu: no se pudo cargar imagen {path}: {e}")
                    return None

        if filename:
            print(f"XFCEMenu: imagen no encontrada: {filename}")

        return None

    def load_icon_pixbuf(self, icon_name, size=28):
        """
        Carga iconos según configuración:

            [icons]
            source = auto    -> legacy primero, GTK si falla
            source = theme   -> solo legacy/tema XFCEMenu
            source = system  -> solo tema GTK/XFCE

        Ejemplos:
            Icon="folder-documents.png"
            Icon="computer.png"
            Icon="search.png"
            Icon="applications-office"
        """
        if not icon_name:
            return None

        icon_source = getattr(self, "icon_source", "auto") or "auto"
        icon_source = icon_source.strip().lower()

        if icon_source not in ("auto", "theme", "system"):
            icon_source = "auto"

        base_name = icon_name.strip()

        # Si viene como archivo legacy, quitamos extensión para buscar equivalente GTK.
        gtk_base_name = base_name
        if gtk_base_name.lower().endswith((".png", ".svg", ".xpm", ".jpg", ".jpeg")):
            gtk_base_name = os.path.splitext(gtk_base_name)[0]

        aliases = {
            "back": "go-previous",
            "previous": "go-previous",
            "gtk-go-back": "go-previous",
            "go-back": "go-previous",

            "internet-web-browser": "web-browser",
            "web-browser": "applications-internet",
            "internet-mail": "mail-message-new",

            "applications-other": "applications-accessories",
            "applications-accessories": "applications-accessories",
            "applications-development": "applications-development",
            "applications-games": "applications-games",
            "applications-graphics": "applications-graphics",
            "applications-internet": "applications-internet",
            "applications-multimedia": "applications-multimedia",
            "applications-office": "applications-office",
            "applications-system": "applications-system",
            "applications-utilities": "applications-utilities",
            "applications-wine": "wine",

            "folder-download": "folder-downloads",
            "folder-downloads": "folder-downloads",
            "folder-images": "folder-pictures",
            "folder-home": "user-home",
            "folder-documents": "folder-documents",
            "folder-music": "folder-music",
            "folder-videos": "folder-videos",
            "folder-pictures": "folder-pictures",

            "user-desktop": "user-desktop",
            "gtk-network": "network-workgroup",
            "gnome-network-properties": "preferences-system-network",
            "gnome-control-center": "preferences-system",
            "gnome-help": "help-browser",
            "emblem-package": "system-software-install",

            "document-open-recent": "document-open-recent",
            "search": "system-search",
            "run": "system-run",
            "computer": "computer",

            "lock": "system-lock-screen",
            "logout": "system-log-out",
            "logoutnow": "system-log-out",
            "shutdown": "system-shutdown",
            "power": "system-shutdown",
            "restart": "system-reboot",
            "reboot": "system-reboot",
            "suspend": "system-suspend",

            "system-lock-screen": "system-lock-screen",
            "system-log-out": "system-log-out",
            "system-reboot": "system-reboot",
            "system-shutdown": "system-shutdown",
            "system-suspend": "system-suspend",

            "gtk-missing-image": "image-missing",
        }

        def load_from_legacy_theme():
            looks_like_file = (
                os.path.isabs(base_name)
                or "/" in base_name
                or base_name.lower().endswith((".png", ".svg", ".xpm", ".jpg", ".jpeg"))
            )

            names_to_try = [base_name]

            # En modo theme, si viene sin extensión igual probamos variantes comunes.
            if not looks_like_file:
                names_to_try.extend([
                    base_name + ".png",
                    base_name + ".svg",
                    base_name + ".xpm",
                ])

            for candidate in names_to_try:
                pixbuf = self.load_pixbuf(candidate)

                if pixbuf:
                    return self.scale_pixbuf_contain(pixbuf, size, size)

            return None

        def load_from_system_theme():
            icon_theme = Gtk.IconTheme.get_default()

            names_to_try = [gtk_base_name]

            alias = aliases.get(gtk_base_name)
            if alias and alias not in names_to_try:
                names_to_try.append(alias)

            # Algunos temas legacy usan nombres capitalizados o raros;
            # probamos una versión normalizada.
            normalized = gtk_base_name.lower().replace("_", "-").replace(" ", "-")
            if normalized not in names_to_try:
                names_to_try.append(normalized)

            alias = aliases.get(normalized)
            if alias and alias not in names_to_try:
                names_to_try.append(alias)

            for name in names_to_try:
                try:
                    return icon_theme.load_icon(
                        name,
                        size,
                        Gtk.IconLookupFlags.FORCE_SIZE
                    )
                except Exception:
                    pass

            return None

        if icon_source == "theme":
            pixbuf = load_from_legacy_theme()
            if not pixbuf:
                print(f"XFCEMenu: icono legacy no encontrado: {icon_name}")
            return pixbuf

        if icon_source == "system":
            pixbuf = load_from_system_theme()
            if not pixbuf:
                print(f"XFCEMenu: icono GTK no encontrado: {icon_name}")
            return pixbuf

        # auto: comportamiento compatible.
        pixbuf = load_from_legacy_theme()
        if pixbuf:
            return pixbuf

        pixbuf = load_from_system_theme()
        if pixbuf:
            return pixbuf

        print(f"XFCEMenu: icono no encontrado: {icon_name}")
        return None

    def on_draw(self, widget, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if self.background_pixbuf:
            Gdk.cairo_set_source_pixbuf(cr, self.background_pixbuf, 0, 0)
            cr.paint()

        return False

    def add_icon_area_to_shape_region(self, region):
        """
        Si el PNG del menú tiene un hueco transparente para el avatar,
        el shape de la ventana recorta esa zona y el avatar no se ve.
        Esta función agrega el área IconSettings al shape visible.
        """
        settings = getattr(self.theme, "icon_settings", None)

        if not settings:
            return

        x = int(getattr(settings, "x", 0))
        y = int(getattr(settings, "y", 0))
        w = int(getattr(settings, "width", 0))
        h = int(getattr(settings, "height", 0))

        if w <= 0 or h <= 0:
            return

        try:
            rect = cairo.RectangleInt(x, y, w, h)
            icon_region = cairo.Region(rect)
            region.union(icon_region)
            print(f"XFCEMenu: área de avatar agregada al shape: {x},{y} {w}x{h}")
        except Exception as e:
            print(f"XFCEMenu: no se pudo agregar área de avatar al shape: {e}")

    def apply_window_shape(self):
        if self.shape_applied:
            return False

        if not self.background_pixbuf:
            print("XFCEMenu: no hay background para aplicar shape.")
            return False

        gdk_window = self.get_window()
        if not gdk_window:
            return True

        if not self.background_pixbuf.get_has_alpha():
            print("XFCEMenu: el background no tiene canal alfa.")
            return False

        width = self.background_pixbuf.get_width()
        height = self.background_pixbuf.get_height()
        rowstride = self.background_pixbuf.get_rowstride()
        n_channels = self.background_pixbuf.get_n_channels()
        pixels = self.background_pixbuf.get_pixels()

        region = cairo.Region()
        alpha_threshold = 80

        for y in range(height):
            x = 0

            while x < width:
                offset = y * rowstride + x * n_channels
                alpha = pixels[offset + 3]

                if alpha > alpha_threshold:
                    start_x = x

                    while x < width:
                        offset = y * rowstride + x * n_channels
                        alpha = pixels[offset + 3]

                        if alpha <= alpha_threshold:
                            break

                        x += 1

                    rect = cairo.RectangleInt(start_x, y, x - start_x, 1)

                    try:
                        row_region = cairo.Region(rect)
                        region.union(row_region)
                    except Exception as e:
                        print(f"XFCEMenu: no se pudo unir región shape: {e}")
                else:
                    x += 1

        self.add_icon_area_to_shape_region(region)

        try:
            gdk_window.shape_combine_region(region, 0, 0)
            print("XFCEMenu: shape aplicado desde alfa del PNG.")
        except Exception as e:
            print(f"XFCEMenu: no se pudo aplicar shape_combine_region: {e}")

        try:
            gdk_window.input_shape_combine_region(region, 0, 0)
            print("XFCEMenu: input shape aplicado.")
        except Exception:
            pass

        self.shape_applied = True
        return False

    def draw_program_list_placeholder(self):
        if not self.theme.program_list:
            return

        area = self.theme.program_list

        frame = Gtk.Frame()
        frame.set_name("xfcemenu-program-placeholder")
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.set_size_request(area.width, area.height)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_start(8)
        box.set_margin_end(8)

        title = Gtk.Label(label="XFCEMenu 0.1")
        title.set_xalign(0)

        subtitle = Gtk.Label(label="Lista de apps pendiente")
        subtitle.set_xalign(0)

        box.pack_start(title, False, False, 0)
        box.pack_start(subtitle, False, False, 0)

        frame.add(box)
        self.fixed.put(frame, area.x, area.y)

    def get_program_area(self):
        area = getattr(self.theme, "program_list", None)

        if not area:
            return None

        x = int(getattr(area, "x", 0))
        y = int(getattr(area, "y", 0))
        w = int(getattr(area, "width", 0))
        h = int(getattr(area, "height", 0))

        if w <= 0 or h <= 0:
            return None

        return x, y, w, h

    def get_search_area(self):
        area = getattr(self.theme, "search_bar", None)

        if not area:
            return None

        x = int(getattr(area, "x", 0))
        y = int(getattr(area, "y", 0))
        w = int(getattr(area, "width", 0))
        h = int(getattr(area, "height", 0))

        if w <= 0 or h <= 0:
            return None

        return x, y, w, h

    def build_categories(self):
        categories = []

        for key, name, icon, matcher in CATEGORY_DEFINITIONS:
            category = MenuCategory(key, name, icon, matcher)
            category.apps = [app for app in self.apps if app_matches_category(app, matcher)]

            # En la vista inicial no mostramos categorías vacías, salvo Applications y Places/Locais.
            if category.apps or key in ("all", "places"):
                category.apps.sort(key=lambda app: app.name.lower())
                categories.append(category)

        return categories

    def filter_apps(self, query):
        query = (query or "").strip().lower()

        if not query:
            return list(self.apps)

        result = []

        for app in self.apps:
            haystack = " ".join([
                app.name or "",
                app.comment or "",
                app.categories or "",
                app.exec_cmd or "",
            ]).lower()

            if query in haystack:
                result.append(app)

        result.sort(key=lambda app: app.name.lower())
        return result

    def draw_program_widgets(self):
        """
        Crea la lista real usando GTK.

        Modo GnoMenu:
        - Vista inicial: categorías.
        - Clic en categoría: programas de esa categoría.
        - Buscar: filtra todas las apps.
        - La scrollbar y la selección/hover las dibuja el tema GTK.
        """
        self.draw_program_list_widget()
        self.draw_search_widget()

    def draw_program_list_widget(self):
        area = self.get_program_area()

        if not area:
            print("XFCEMenu: el tema no tiene ProgramListSettings.")
            return

        x, y, w, h = area

        self.program_scrolled = Gtk.ScrolledWindow()
        self.program_scrolled.set_name("xfcemenu-program-scroll")
        self.program_scrolled.set_shadow_type(Gtk.ShadowType.NONE)
        self.program_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.program_scrolled.set_overlay_scrolling(False)
        self.program_scrolled.set_size_request(w, h)

        try:
            self.program_scrolled.set_has_frame(False)
        except Exception:
            pass

        self.program_listbox = Gtk.ListBox()
        self.program_listbox.set_name("xfcemenu-program-list")
        self.program_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.program_listbox.set_activate_on_single_click(True)
        self.program_listbox.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.program_listbox.connect("row-activated", self.on_program_row_activated)
        self.program_listbox.connect(
            "button-press-event",
            self.on_program_list_button_press,
        )
        self.program_listbox.connect(
            "popup-menu",
            self.on_program_list_popup_menu,
        )

        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        viewport.add(self.program_listbox)

        self.program_scrolled.add(viewport)
        self.fixed.put(self.program_scrolled, x, y)

        self.show_initial_program_view()

    def show_initial_program_view(self):
        """
        Respeta ProgramListSettings de los temas legacy:

        OnlyShowFavs="1"       -> abre mostrando favoritos.
        OnlyShowRecentApps="1" -> abre mostrando aplicaciones recientes.
        Sin flags              -> abre mostrando categorías.
        """
        settings = getattr(self.theme, "program_list", None)

        if settings is not None:
            if int(getattr(settings, "only_favs", 0) or 0) == 1:
                self.show_favorites()
                return

            if int(getattr(settings, "only_recent", 0) or 0) == 1:
                self.show_recent_apps()
                return

        self.show_categories()

    def draw_search_widget(self):
        # Algunos temas declaran un área de búsqueda con tamaño cero y además
        # Capabilities HasSearch="0". En ambos casos no se crea el Gtk.Entry.
        if not getattr(self, "theme_has_search", True):
            return

        area = self.get_search_area()

        if not area:
            return

        x, y, w, h = area

        self.search_entry = Gtk.Entry()
        self.search_entry.set_name("xfcemenu-search-entry")
        self.search_entry.set_placeholder_text("Procurar" if detect_language() == "pt" else ("Search" if detect_language() == "en" else "Buscar"))
        self.search_entry.set_has_frame(False)
        self.search_entry.set_size_request(w, h)
        self.search_entry.connect("changed", self.on_search_changed)
        self.search_entry.connect("key-press-event", self.on_search_key_press)

        self.fixed.put(self.search_entry, x, y)

    def clear_program_listbox(self):
        if not self.program_listbox:
            return

        for child in list(self.program_listbox.get_children()):
            self.program_listbox.remove(child)

    def reset_program_scroll(self):
        if self.program_scrolled:
            adjustment = self.program_scrolled.get_vadjustment()
            if adjustment:
                adjustment.set_value(0)

    def show_categories(self):
        self.current_view = "categories"
        self.current_category = None
        self.populate_category_list(self.categories)

    def show_all_apps(self):
        self.current_view = "all_apps"
        self.current_category = None
        self.populate_app_list(self.apps, include_back=False)

    def show_category_apps(self, category):
        if not category:
            return

        self.current_view = "category"
        self.current_category = category
        self.populate_app_list(category.apps, include_back=True)

    def show_search_results(self, query):
        self.current_view = "search"
        self.current_category = None
        apps = self.filter_apps(query)
        self.populate_app_list(apps, include_back=False)

    def populate_category_list(self, categories):
        if not self.program_listbox:
            return

        self.clear_program_listbox()

        if not categories:
            self.add_message_row("Sin categorías")
            return

        for category in categories:
            row = self.create_category_row(category)
            self.program_listbox.add(row)

        self.program_listbox.show_all()
        self.select_first_row()
        self.reset_program_scroll()

    def populate_app_list(self, apps, include_back=False):
        if not self.program_listbox:
            return

        self.clear_program_listbox()
        self.filtered_apps = list(apps)

        if include_back:
            back_row = self.create_back_row()
            self.program_listbox.add(back_row)

        if not self.filtered_apps:
            self.add_message_row("Sin resultados")
        else:
            for app in self.filtered_apps:
                row = self.create_program_row(app)
                self.program_listbox.add(row)

        self.program_listbox.show_all()
        self.select_first_row()
        self.reset_program_scroll()

    def add_message_row(self, text):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)

        label = Gtk.Label(label=text)
        label.get_style_context().add_class("xfcemenu-program-message")
        label.set_xalign(0)
        label.set_margin_start(6)
        label.set_margin_end(6)
        label.set_margin_top(6)
        label.set_margin_bottom(6)

        row.add(label)
        self.program_listbox.add(row)
        self.program_listbox.show_all()

    def select_first_row(self):
        # Sin estado :selected: no marcamos ninguna fila al abrir/cambiar vista.
        # El resaltado visual queda a cargo de :hover para evitar la barra azul GTK.
        return

    def create_base_row(self, item, icon_name, label_text):
        row = Gtk.ListBoxRow()
        row.set_name("xfcemenu-program-row")
        row.menu_item = item
        row.set_activatable(True)
        row.set_selectable(True)
        row.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK
        )
        row.connect("enter-notify-event", self.on_program_row_enter)
        row.connect("button-press-event", self.on_program_row_button_press)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(2)
        box.set_margin_bottom(2)

        icon_pixbuf = None
        if icon_name:
            icon_pixbuf = self.load_icon_pixbuf(icon_name, self.icon_size)

        if not icon_pixbuf:
            icon_pixbuf = self.load_icon_pixbuf("application-x-executable", self.icon_size)

        if icon_pixbuf:
            icon = Gtk.Image.new_from_pixbuf(icon_pixbuf)
        else:
            icon = Gtk.Image()

        icon.set_size_request(self.icon_size, self.icon_size)

        label = Gtk.Label(label=label_text)
        label.get_style_context().add_class("xfcemenu-program-label")
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_single_line_mode(True)

        box.pack_start(icon, False, False, 0)
        box.pack_start(label, True, True, 0)

        row.add(box)
        return row

    def create_category_row(self, category):
        row = self.create_base_row(category, category.icon, category.name)
        row.item_type = "category"
        row.category = category
        return row

    def create_back_row(self):
        # El icono ya indica "volver"; dejamos el texto limpio para que no aparezca doble flecha.
        item = BackItem("Volver")
        row = self.create_base_row(item, item.icon, item.name)
        row.item_type = "back"
        return row

    def create_program_row(self, app):
        row = self.create_base_row(app, app.icon, app.name)
        row.item_type = "app"
        row.app = app
        return row

    def on_program_row_enter(self, row, event):
        """
        No seleccionamos la fila al pasar el mouse.
        Gtk.ListBox pintaba :selected con una barra azul propia del tema GTK.
        Ahora solo usamos el estado :hover definido en CSS.
        """
        return False

    def on_program_list_button_press(self, listbox, event):
        """
        Captura el clic derecho desde la lista completa.

        En algunos temas GTK los widgets hijos de Gtk.ListBoxRow consumen el
        evento antes de que llegue a la fila. Consultar la fila por coordenada
        desde la propia Gtk.ListBox es más fiable.
        """
        if event.button != 3:
            return False

        row = listbox.get_row_at_y(int(event.y))

        if not row:
            return False

        if getattr(row, "item_type", "") != "app":
            return False

        app = getattr(row, "app", None)

        if not app:
            return False

        self.show_app_context_menu(app, event)
        return True

    def on_program_list_popup_menu(self, listbox):
        """
        Abre el menú contextual con la tecla Menú o Shift+F10.
        """
        row = listbox.get_selected_row()

        if not row or getattr(row, "item_type", "") != "app":
            return False

        app = getattr(row, "app", None)

        if not app:
            return False

        self.show_app_context_menu(app, None)
        return True

    def on_program_row_button_press(self, row, event):
        # Clic derecho sobre una aplicación: agregar/quitar favorito.
        if event.button == 3 and getattr(row, "item_type", "") == "app":
            app = getattr(row, "app", None)

            if app:
                self.show_app_context_menu(app, event)
                return True

        return False

    def favorite_id_for_app(self, app):
        """
        Usa el nombre del archivo .desktop como identificador estable.
        Si no existe, cae a nombre + comando.
        """
        desktop_file = (getattr(app, "desktop_file", "") or "").strip()

        if desktop_file:
            return os.path.basename(desktop_file)

        name = (getattr(app, "name", "") or "").strip()
        command = (getattr(app, "exec_cmd", "") or "").strip()
        return f"{name}|{command}"

    def load_favorite_ids(self):
        if not os.path.isfile(FAVORITES_FILE):
            return []

        favorites = []

        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    value = line.strip()

                    if value and not value.startswith("#"):
                        favorites.append(value)
        except Exception as error:
            print(f"XFCEMenu: no se pudieron leer favoritos: {error}")

        return favorites

    def save_favorite_ids(self, favorites):
        os.makedirs(CONFIG_DIR, exist_ok=True)

        clean = []
        seen = set()

        for value in favorites:
            value = (value or "").strip()

            if value and value not in seen:
                seen.add(value)
                clean.append(value)

        try:
            tmp_path = FAVORITES_FILE + ".tmp"

            with open(tmp_path, "w", encoding="utf-8") as handle:
                for value in clean:
                    handle.write(value + "\n")

            os.replace(tmp_path, FAVORITES_FILE)
            return True
        except Exception as error:
            print(f"XFCEMenu: no se pudieron guardar favoritos: {error}")
            return False

    def is_favorite_app(self, app):
        favorite_id = self.favorite_id_for_app(app).lower()
        return favorite_id in {item.lower() for item in self.load_favorite_ids()}

    def toggle_favorite_app(self, app):
        favorite_id = self.favorite_id_for_app(app)
        favorites = self.load_favorite_ids()

        matching_index = None

        for index, value in enumerate(favorites):
            if value.lower() == favorite_id.lower():
                matching_index = index
                break

        if matching_index is None:
            favorites.append(favorite_id)
            added = True
        else:
            favorites.pop(matching_index)
            added = False

        if self.save_favorite_ids(favorites):
            print(
                f"XFCEMenu: {'favorito agregado' if added else 'favorito eliminado'}: "
                f"{getattr(app, 'name', favorite_id)}"
            )

            if self.current_view == "favorites":
                self.show_favorites()

        return added

    def show_app_context_menu(self, app, event):
        # Guardar una referencia evita que PyGObject destruya el menú
        # contextual antes de que GTK llegue a mostrarlo.
        menu = Gtk.Menu()
        self.app_context_menu = menu
        is_favorite = self.is_favorite_app(app)

        if is_favorite:
            label = {
                "es": "Quitar de favoritos",
                "pt": "Remover dos favoritos",
                "en": "Remove from favorites",
            }.get(detect_language(), "Quitar de favoritos")
        else:
            label = {
                "es": "Agregar a favoritos",
                "pt": "Adicionar aos favoritos",
                "en": "Add to favorites",
            }.get(detect_language(), "Agregar a favoritos")

        favorite_item = Gtk.MenuItem(label=label)
        favorite_item.connect(
            "activate",
            lambda _item: self.toggle_favorite_app(app)
        )
        menu.append(favorite_item)

        launch_item = Gtk.MenuItem(
            label={
                "es": "Abrir",
                "pt": "Abrir",
                "en": "Open",
            }.get(detect_language(), "Abrir")
        )
        launch_item.connect("activate", lambda _item: self.launch_app(app))
        menu.append(launch_item)

        menu.connect(
            "deactivate",
            self.on_app_context_menu_deactivate,
        )
        menu.show_all()

        try:
            if event is not None:
                menu.popup_at_pointer(event)
            else:
                menu.popup_at_widget(
                    self.program_listbox,
                    Gdk.Gravity.SOUTH_WEST,
                    Gdk.Gravity.NORTH_WEST,
                    None,
                )
        except Exception:
            button = int(getattr(event, "button", 0) or 0)
            event_time = int(getattr(event, "time", Gtk.get_current_event_time()) or 0)

            menu.popup(
                None,
                None,
                None,
                None,
                button,
                event_time,
            )

    def on_program_row_activated(self, listbox, row):
        self.play_event_sound("button")
        item_type = getattr(row, "item_type", "")

        if item_type == "category":
            category = getattr(row, "category", None)

            if category and getattr(category, "key", "") == "places":
                self.show_computer_items()
                return

            self.show_category_apps(category)
            return

        if item_type == "back":
            if self.search_entry:
                self.search_entry.set_text("")
            self.show_initial_program_view()
            return

        if item_type == "place":
            item = getattr(row, "place_item", None)

            if item:
                path = item.path

                if item.xdg_key:
                    path = get_xdg_user_dir(item.xdg_key, item.path or "~")

                open_path(path)
                self.close_menu()

            return

        if item_type == "action":
            item = getattr(row, "action_item", None)

            if item and item.command:
                # Los ActionItem internos usan nombres legacy como Shutdown, Restart,
                # LogoutNow, Lock, etc. No deben ejecutarse literalmente como
                # binarios del sistema; primero pasan por el mismo traductor de
                # comandos que usan los botones del tema.
                handled = self.handle_legacy_button_action(item.command)

                if not handled:
                    handled = self.handle_internal_menu_command(item.command)

                if not handled:
                    run_command(item.command)

                # Si el comando abrió un submenú interno, dejamos el menú visible.
                # Para acciones reales de sesión/aplicaciones, cerramos.
                if (item.command or "").strip().lower() not in ("power", "aux", "3"):
                    self.close_menu()

            return

        if item_type == "app":
            app = getattr(row, "app", None)
            self.launch_app(app)

    def on_search_changed(self, entry):
        query = entry.get_text().strip()

        if query:
            self.show_search_results(query)
        else:
            self.show_initial_program_view()

    def on_search_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close_menu()
            return True

        if event.keyval == Gdk.KEY_BackSpace:
            text = widget.get_text()
            if not text and self.current_view == "category":
                self.show_categories()
                return True

        return False

    def launch_app(self, app):
        if not app or not app.exec_cmd:
            return

        home = os.path.expanduser("~")

        try:
            # Lanzar desde HOME evita que Terminal y otras apps hereden
            # ~/.local/share/xfcemenu como directorio de trabajo.
            subprocess.Popen(app.exec_cmd, shell=True, cwd=home)
            self.close_menu()
        except Exception as e:
            print(f"XFCEMenu: no se pudo abrir '{app.name}': {e}")

    def find_user_image_path(self):
        home = os.path.expanduser("~")

        candidates = [
            os.path.join(home, ".face"),
            os.path.join(home, ".face.icon"),
            os.path.join(home, "Imágenes", "avatar.png"),
            os.path.join(home, "Imágenes", "avatar.jpg"),
            os.path.join(home, "Imágenes", "avatar.jpeg"),
            os.path.join(home, "Pictures", "avatar.png"),
            os.path.join(home, "Pictures", "avatar.jpg"),
            os.path.join(home, "Pictures", "avatar.jpeg"),
        ]

        for path in candidates:
            if os.path.isfile(path):
                return path

        return None

    def scale_pixbuf_cover_center(self, pixbuf, target_w, target_h):
        if not pixbuf or target_w <= 0 or target_h <= 0:
            return None

        w = pixbuf.get_width()
        h = pixbuf.get_height()

        if w <= 0 or h <= 0:
            return None

        scale = max(target_w / float(w), target_h / float(h))
        scaled_w = max(1, int(w * scale))
        scaled_h = max(1, int(h * scale))

        scaled = pixbuf.scale_simple(
            scaled_w,
            scaled_h,
            GdkPixbuf.InterpType.BILINEAR
        )

        crop_x = max(0, int((scaled_w - target_w) / 2))
        crop_y = max(0, int((scaled_h - target_h) / 2))

        try:
            return scaled.new_subpixbuf(crop_x, crop_y, target_w, target_h)
        except Exception:
            return scaled

    def scale_pixbuf_contain(self, pixbuf, target_w, target_h):
        if not pixbuf or target_w <= 0 or target_h <= 0:
            return None

        w = pixbuf.get_width()
        h = pixbuf.get_height()

        if w <= 0 or h <= 0:
            return None

        scale = min(target_w / float(w), target_h / float(h))
        scaled_w = max(1, int(w * scale))
        scaled_h = max(1, int(h * scale))

        return pixbuf.scale_simple(
            scaled_w,
            scaled_h,
            GdkPixbuf.InterpType.BILINEAR
        )

    def load_user_avatar_pixbuf(self, width, height):
        avatar_path = self.find_user_image_path()

        if avatar_path:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(avatar_path)
                return self.scale_pixbuf_cover_center(pixbuf, width, height)
            except Exception as e:
                print(f"XFCEMenu: no se pudo cargar avatar {avatar_path}: {e}")

        fallback_names = [
            "gtk-missing-image.png",
            "no-user-image.png",
            "user.png",
            "avatar.png",
        ]

        for name in fallback_names:
            pixbuf = self.load_pixbuf(name)
            if pixbuf:
                return self.scale_pixbuf_cover_center(pixbuf, width, height)

        fallback_icon = self.load_icon_pixbuf("image-missing", max(width, height))

        if fallback_icon:
            return self.scale_pixbuf_cover_center(fallback_icon, width, height)

        return None

    def create_user_frame_overlay_pixbuf(self, settings):
        """
        Crea un overlay del marco del usuario tomando esa zona del background.
        La foto queda debajo y el marco vuelve a dibujarse arriba.
        """
        if not self.background_pixbuf:
            return None

        frame_x = int(settings.x)
        frame_y = int(settings.y)
        frame_w = int(settings.width)
        frame_h = int(settings.height)

        if frame_w <= 0 or frame_h <= 0:
            return None

        bg_w = self.background_pixbuf.get_width()
        bg_h = self.background_pixbuf.get_height()

        if frame_x < 0 or frame_y < 0:
            return None

        if frame_x + frame_w > bg_w or frame_y + frame_h > bg_h:
            return None

        overlay = GdkPixbuf.Pixbuf.new(
            GdkPixbuf.Colorspace.RGB,
            True,
            8,
            frame_w,
            frame_h
        )

        overlay.fill(0x00000000)

        inner_x = max(0, int(settings.inset_x))
        inner_y = max(0, int(settings.inset_y))
        inner_w = int(settings.inset_width) if settings.inset_width > 0 else frame_w
        inner_h = int(settings.inset_height) if settings.inset_height > 0 else frame_h

        inner_right = min(frame_w, inner_x + inner_w)
        inner_bottom = min(frame_h, inner_y + inner_h)

        if inner_y > 0:
            self.background_pixbuf.copy_area(
                frame_x,
                frame_y,
                frame_w,
                inner_y,
                overlay,
                0,
                0
            )

        bottom_h = frame_h - inner_bottom
        if bottom_h > 0:
            self.background_pixbuf.copy_area(
                frame_x,
                frame_y + inner_bottom,
                frame_w,
                bottom_h,
                overlay,
                0,
                inner_bottom
            )

        if inner_x > 0 and inner_h > 0:
            self.background_pixbuf.copy_area(
                frame_x,
                frame_y + inner_y,
                inner_x,
                inner_h,
                overlay,
                0,
                inner_y
            )

        right_w = frame_w - inner_right
        if right_w > 0 and inner_h > 0:
            self.background_pixbuf.copy_area(
                frame_x + inner_right,
                frame_y + inner_y,
                right_w,
                inner_h,
                overlay,
                inner_right,
                inner_y
            )

        return overlay

    def load_user_frame_pixbuf(self, settings):
        """
        GnoMenu usa user-image-frame.png dentro del tema Menu.
        Si existe, lo usamos como overlay.
        Si no existe, reconstruimos el marco desde el background.
        """
        frame = self.load_pixbuf("user-image-frame.png")

        if frame:
            frame_w = int(settings.width)
            frame_h = int(settings.height)

            if frame_w > 0 and frame_h > 0:
                try:
                    return frame.scale_simple(
                        frame_w,
                        frame_h,
                        GdkPixbuf.InterpType.BILINEAR
                    )
                except Exception:
                    return frame

            return frame

        return self.create_user_frame_overlay_pixbuf(settings)

    def draw_user_icon(self):
        """
        Dibuja la foto/avatar del usuario usando IconSettings.

        IconSettings:
            X/Y/Width/Height = zona total reservada por el tema.
            InsetX/InsetY/InsetWidth/InsetHeight = zona real de la foto.
        """
        settings = getattr(self.theme, "icon_settings", None)

        if not settings:
            print("XFCEMenu: el tema no tiene IconSettings.")
            return

        if settings.width <= 0 or settings.height <= 0:
            return

        inset_x = int(settings.inset_x)
        inset_y = int(settings.inset_y)

        draw_w = int(settings.inset_width) if settings.inset_width > 0 else int(settings.width)
        draw_h = int(settings.inset_height) if settings.inset_height > 0 else int(settings.height)

        avatar_x = int(settings.x) + inset_x
        avatar_y = int(settings.y) + inset_y

        avatar = self.load_user_avatar_pixbuf(draw_w, draw_h)

        if avatar:
            self.avatar_normal_pixbuf = avatar
            self.avatar_image_widget = Gtk.Image.new_from_pixbuf(avatar)
            self.fixed.put(self.avatar_image_widget, avatar_x, avatar_y)
            print(f"XFCEMenu: avatar dibujado en {avatar_x},{avatar_y} {draw_w}x{draw_h}")
        else:
            print("XFCEMenu: no se encontró avatar ni fallback.")

        frame_overlay = self.load_user_frame_pixbuf(settings)

        if frame_overlay:
            self.avatar_frame_widget = Gtk.Image.new_from_pixbuf(frame_overlay)
            self.fixed.put(self.avatar_frame_widget, int(settings.x), int(settings.y))

        # Zona transparente encima del avatar y su marco.
        # Un clic abre Mugshot cuando está instalado.
        click_area = Gtk.EventBox()
        click_area.set_visible_window(False)
        click_area.set_size_request(int(settings.width), int(settings.height))
        click_area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.ENTER_NOTIFY_MASK
        )
        click_area.set_tooltip_text(
            {
                "es": "Cambiar imagen de perfil",
                "pt": "Alterar imagem do perfil",
                "en": "Change profile picture",
            }.get(detect_language(), "Cambiar imagen de perfil")
        )
        click_area.connect("button-press-event", self.on_avatar_button_press)

        self.avatar_click_area = click_area
        self.fixed.put(click_area, int(settings.x), int(settings.y))
        click_area.show()

    def on_avatar_button_press(self, widget, event):
        if event.button != 1:
            return False

        if shutil.which("mugshot"):
            try:
                subprocess.Popen(
                    ["mugshot"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.close_menu()
                return True
            except Exception as error:
                print(f"XFCEMenu: no se pudo abrir Mugshot: {error}")
                return True

        print(
            "XFCEMenu: Mugshot no está instalado. "
            "Instala con: sudo apt install mugshot"
        )
        return True

    def cancel_avatar_hover_timer(self):
        if self.avatar_hover_timer:
            try:
                GLib.source_remove(self.avatar_hover_timer)
            except Exception:
                pass

            self.avatar_hover_timer = None

    def start_avatar_hover_timer(self, button):
        """
        Imita GnoMenu:
        espera 300 ms sobre un botón y cambia el avatar grande
        por el Icon de esa opción.
        """
        self.cancel_avatar_hover_timer()

        if not getattr(button, "icon", ""):
            return

        self.avatar_hover_timer = GLib.timeout_add(
            300,
            self.apply_button_avatar_icon,
            button
        )

    def apply_button_avatar_icon(self, button):
        self.avatar_hover_timer = None

        settings = getattr(self.theme, "icon_settings", None)

        if not settings or not self.avatar_image_widget:
            return False

        draw_w = int(settings.inset_width) if settings.inset_width > 0 else int(settings.width)
        draw_h = int(settings.inset_height) if settings.inset_height > 0 else int(settings.height)

        icon_name = getattr(button, "icon", "")

        if not icon_name:
            return False

        pixbuf = self.load_icon_pixbuf(icon_name, max(draw_w, draw_h))

        if not pixbuf:
            return False

        pixbuf = self.scale_pixbuf_contain(pixbuf, draw_w, draw_h)

        if pixbuf:
            self.avatar_image_widget.set_from_pixbuf(pixbuf)
            print(f"XFCEMenu: avatar temporal cambiado por icono: {icon_name}")

        return False

    def restore_user_avatar(self):
        if self.avatar_image_widget and self.avatar_normal_pixbuf:
            self.avatar_image_widget.set_from_pixbuf(self.avatar_normal_pixbuf)

    def draw_tabs(self):
        tabs = getattr(self.theme, "tabs", [])

        if not tabs:
            return

        for tab in tabs:
            self.draw_tab(tab)

    def get_tab_attr(self, tab, *names, default=None):
        for name in names:
            if hasattr(tab, name):
                value = getattr(tab, name)
                if value is not None and value != "":
                    return value

        return default

    def draw_tab(self, tab):
        event = Gtk.EventBox()
        event.set_visible_window(False)

        container = Gtk.Fixed()

        try:
            container.set_has_window(False)
        except Exception:
            pass

        normal_pixbuf = self.load_pixbuf(self.get_tab_attr(tab, "image", "Image", default=""))
        selected_pixbuf = self.load_pixbuf(self.get_tab_attr(tab, "image_sel", "imageSel", "ImageSel", default=""))

        if not selected_pixbuf:
            selected_pixbuf = normal_pixbuf

        width = 96
        height = 96
        bg_widget = None

        if normal_pixbuf:
            bg_widget = Gtk.Image.new_from_pixbuf(normal_pixbuf)
            container.put(bg_widget, 0, 0)
            width = max(width, normal_pixbuf.get_width())
            height = max(height, normal_pixbuf.get_height())

        icon_name = self.get_tab_attr(tab, "tab_icon", "tabIcon", "TabIcon", "icon", "Icon", default="")
        icon_size = int(self.get_tab_attr(tab, "tab_icon_size", "tabIconSize", "TabIconSize", default=32) or 32)
        icon_x = int(self.get_tab_attr(tab, "tab_icon_x", "tabIconX", "TabIconX", default=0) or 0)
        icon_y = int(self.get_tab_attr(tab, "tab_icon_y", "tabIconY", "TabIconY", default=0) or 0)

        icon_pixbuf = self.load_icon_pixbuf(icon_name, icon_size)

        if icon_pixbuf:
            icon = Gtk.Image.new_from_pixbuf(icon_pixbuf)
            container.put(icon, icon_x, icon_y)

        label_text = self.extract_tab_label_text(tab)

        if label_text:
            label = Gtk.Label()
            label.set_use_markup(True)

            markup = self.get_tab_attr(tab, "markup", "Markup", default="")

            # Los tabs legacy suelen estar sobre zonas oscuras del skin.
            # Calculamos el fondo debajo del texto y forzamos un color legible.
            tab_x_abs = int(self.get_tab_attr(tab, "x", "tab_x", "tabX", "TabX", default=0) or 0)
            tab_y_abs = int(self.get_tab_attr(tab, "y", "tab_y", "tabY", "TabY", default=0) or 0)
            text_x_abs = int(self.get_tab_attr(tab, "text_x", "textX", "TextX", default=0) or 0)
            text_y_abs = int(self.get_tab_attr(tab, "text_y", "textY", "TextY", default=0) or 0)

            forced_color = self.readable_text_color_for_area(
                tab_x_abs + text_x_abs,
                tab_y_abs + text_y_abs,
                width,
                24
            )

            self.safe_set_markup_or_text(label, markup, label_text, forced_color=forced_color)

            label.set_xalign(0.5)

            text_x = int(self.get_tab_attr(tab, "text_x", "textX", "TextX", default=0) or 0)
            text_y = int(self.get_tab_attr(tab, "text_y", "textY", "TextY", default=0) or 0)

            label.set_size_request(width, 22)
            container.put(label, text_x, text_y)

        event.add(container)
        event.set_size_request(width, height)

        event.normal_pixbuf = normal_pixbuf
        event.selected_pixbuf = selected_pixbuf
        event.bg_widget = bg_widget
        event.tab = tab

        event.connect("button-press-event", self.on_tab_clicked, tab, event)
        event.connect("enter-notify-event", self.on_tab_enter, tab, event)
        event.connect("leave-notify-event", self.on_tab_leave, tab, event)

        x = int(self.get_tab_attr(tab, "x", "tab_x", "tabX", "TabX", default=0) or 0)
        y = int(self.get_tab_attr(tab, "y", "tab_y", "tabY", "TabY", default=0) or 0)

        self.fixed.put(event, x, y)

        command = str(self.get_tab_attr(tab, "command", "Command", default="")).strip()

        if command == self.current_tab_command:
            self.active_tab_event = event
            self.set_tab_selected(event, True)

    def extract_tab_label_text(self, tab):
        name = self.get_tab_attr(tab, "name", "Name", default="") or ""
        markup = self.get_tab_attr(tab, "markup", "Markup", default="") or ""

        if markup:
            plain = re.sub(r"<[^>]+>", "", str(markup))
            plain = html.unescape(plain).strip()

            if plain:
                return plain

        return str(name)

    def set_tab_selected(self, event, selected):
        bg_widget = getattr(event, "bg_widget", None)

        if not bg_widget:
            return

        pixbuf = getattr(event, "selected_pixbuf", None) if selected else getattr(event, "normal_pixbuf", None)

        if pixbuf:
            bg_widget.set_from_pixbuf(pixbuf)

    def clear_active_tab(self):
        if self.active_tab_event:
            self.set_tab_selected(self.active_tab_event, False)

        self.active_tab_event = None

    def select_tab_event(self, event):
        self.clear_active_tab()
        self.active_tab_event = event
        self.set_tab_selected(event, True)

    def on_tab_enter(self, widget, event, tab, tab_event):
        self.set_tab_selected(tab_event, True)
        return False

    def on_tab_leave(self, widget, event, tab, tab_event):
        if tab_event is not self.active_tab_event:
            self.set_tab_selected(tab_event, False)

        return False

    def on_tab_clicked(self, widget, event, tab, tab_event):
        if event.button != 1:
            return False

        self.play_event_sound("tab")
        self.activate_tab(tab)
        self.select_tab_event(tab_event)
        return True

    def activate_tab(self, tab):
        command = str(self.get_tab_attr(tab, "command", "Command", default="")).strip()

        if self.search_entry:
            self.search_entry.set_text("")

        self.current_tab_command = command

        if command == "1":
            self.show_categories()
            return

        if command == "2":
            self.show_recent_apps()
            return

        if command == "4":
            self.show_recent_items()
            return

        if command == "7":
            self.show_favorites()
            return

        if command == "8":
            self.show_computer_items()
            return

        if command == "9":
            self.show_leave_items()
            return

        if command == "10":
            self.show_web_bookmarks()
            return

        print(f"XFCEMenu: tab command no soportado todavía: {command}")

    def show_recent_items(self):
        self.current_view = "recent"
        self.current_category = None
        self.clear_program_listbox()
        self.add_message_row(tr_ui("recent_pending", "Recent items pendiente"))
        self.select_first_row()
        self.reset_program_scroll()

    def show_recent_apps(self):
        self.current_view = "recent_apps"
        self.current_category = None

        # Fallback liviano: mostramos las primeras apps ordenadas.
        # Más adelante se puede reemplazar por historial real.
        recent_apps = self.apps[:12]
        self.populate_app_list(recent_apps, include_back=False)

    def show_web_bookmarks(self):
        self.current_view = "web_bookmarks"
        self.current_category = None

        # GnoMenu tenía soporte para marcadores del navegador.
        # Por ahora dejamos accesos web comunes sin depender de Firefox/Chrome internamente.
        items = [
            ActionItem("Abrir navegador", "internet-web-browser", "xdg-open https://www.google.com"),
            ActionItem("Google", "internet-web-browser", "xdg-open https://www.google.com"),
            ActionItem("YouTube", "applications-internet", "xdg-open https://www.youtube.com"),
            ActionItem("Wikipedia", "applications-internet", "xdg-open https://www.wikipedia.org"),
        ]

        self.populate_special_item_list(items)

    def show_leave_items(self):
        self.current_view = "leave"
        self.current_category = None

        # En pruebas conviene que Apagar/Reiniciar pasen por el diálogo/sesión XFCE,
        # no por comandos directos peligrosos.
        items = [
            ActionItem(tr_ui("lock", "Bloquear pantalla"), "system-lock-screen", "Lock"),
            ActionItem(tr_ui("logout", "Cerrar sesión"), "system-log-out", "LogoutNow"),
            ActionItem(tr_ui("restart", "Reiniciar"), "system-reboot", "Restart"),
            ActionItem(tr_ui("shutdown", "Apagar"), "system-shutdown", "Shutdown"),
        ]

        self.populate_special_item_list(items)

    def show_power_items(self):
        self.current_view = "power"
        self.current_category = None

        items = [
            ActionItem(tr_ui("lock", "Bloquear pantalla"), "system-lock-screen", "Lock"),
            ActionItem(tr_ui("logout", "Cerrar sesión"), "system-log-out", "LogoutNow"),
            ActionItem(tr_ui("suspend", "Suspender"), "system-suspend", "Suspend"),
            ActionItem(tr_ui("restart", "Reiniciar"), "system-reboot", "Restart"),
            ActionItem(tr_ui("shutdown", "Apagar"), "system-shutdown", "Shutdown"),
        ]

        self.populate_special_item_list(items)

    def load_favorite_desktop_ids(self):
        """
        Compatibilidad con el nombre anterior del método.
        Los favoritos se guardan en:
            ~/.config/xfcemenu/favorites.txt
        """
        return [item.lower() for item in self.load_favorite_ids()]

    def show_favorites(self):
        self.current_view = "favorites"
        self.current_category = None

        configured = {
            item.lower()
            for item in self.load_favorite_ids()
        }

        favorites = []

        for app in self.apps:
            favorite_id = self.favorite_id_for_app(app).lower()

            if favorite_id in configured:
                favorites.append(app)

        favorites.sort(key=lambda app: (app.name or "").lower())

        if not favorites:
            self.clear_program_listbox()
            self.add_message_row(
                tr_ui("no_favorites", "Sin favoritos") +
                " — clic derecho sobre una aplicación para agregarla"
            )
            self.select_first_row()
            self.reset_program_scroll()
            return

        self.populate_app_list(favorites, include_back=False)

    def show_computer_items(self):
        self.current_view = "computer"
        self.current_category = None

        items = [
            PlaceItem(tr_ui("home", "Carpeta personal"), "user-home", "HOME", "~"),
            PlaceItem(tr_ui("desktop", "Escritorio"), "user-desktop", "DESKTOP", "~/Escritorio"),
            PlaceItem(tr_ui("documents", "Documentos"), "folder-documents", "DOCUMENTS", "~/Documentos"),
            PlaceItem(tr_ui("downloads", "Descargas"), "folder-download", "DOWNLOAD", "~/Descargas"),
            PlaceItem(tr_ui("music", "Música"), "folder-music", "MUSIC", "~/Música"),
            PlaceItem(tr_ui("pictures", "Imágenes"), "folder-pictures", "PICTURES", "~/Imágenes"),
            PlaceItem(tr_ui("videos", "Videos"), "folder-videos", "VIDEOS", "~/Vídeos"),
            ActionItem(tr_ui("settings", "Configuración"), "preferences-system", "xfce4-settings-manager"),
        ]

        self.populate_special_item_list(items)

    def populate_special_item_list(self, items):
        if not self.program_listbox:
            return

        self.clear_program_listbox()

        for item in items:
            row = self.create_special_item_row(item)
            self.program_listbox.add(row)

        self.program_listbox.show_all()
        self.select_first_row()
        self.reset_program_scroll()

    def create_special_item_row(self, item):
        row = self.create_base_row(item, item.icon, item.name)

        if isinstance(item, PlaceItem):
            row.item_type = "place"
            row.place_item = item
        elif isinstance(item, ActionItem):
            row.item_type = "action"
            row.action_item = item
        else:
            row.item_type = "special"

        return row


    def scale_legacy_markup_font_desc(self, markup, scale=LEGACY_BUTTON_TEXT_SCALE):
        """
        Reduce suavemente font_desc="... 10" / font_desc='... 10'
        dentro del Markup legacy, sin tocar colores ni otros atributos.
        """
        markup = str(markup or "")

        if not markup or scale == 1.0:
            return markup

        def repl(match):
            quote = match.group(1)
            font_desc = match.group(2)

            def scale_number(number_match):
                original = float(number_match.group(1))
                suffix = number_match.group(2) or ""
                scaled = max(1.0, original * float(scale))

                # Mantener entero cuando queda muy cerca de entero; si no, un decimal.
                if abs(scaled - round(scaled)) < 0.05:
                    value = str(int(round(scaled)))
                else:
                    value = f"{scaled:.1f}".rstrip("0").rstrip(".")

                return value + suffix

            # Escalamos el último número del font_desc, que normalmente es el tamaño.
            new_font_desc = re.sub(
                r"(\d+(?:\.\d+)?)(\s*(?:px|pt)?)\s*$",
                scale_number,
                font_desc
            )

            return f"font_desc={quote}{new_font_desc}{quote}"

        return re.sub(
            r"font_desc\s*=\s*(['\"])([^'\"]*)\1",
            repl,
            markup
        )

    def apply_legacy_label_font_scale(self, label, scale=LEGACY_BUTTON_TEXT_SCALE):
        """
        Ajuste global de tamaño para labels legacy sin font_desc explícito.
        Si el Markup ya traía font_desc, scale_legacy_markup_font_desc() hace el trabajo.
        """
        if not label or scale == 1.0:
            return

        try:
            context = label.get_style_context()
            font_desc = context.get_font(Gtk.StateFlags.NORMAL).copy()
            size = font_desc.get_size()

            if size > 0:
                font_desc.set_size(max(1, int(size * float(scale))))
                label.override_font(font_desc)
        except Exception:
            pass

    def safe_set_markup_or_text(self, label, markup, text, forced_color=None, legacy_text_correction=False):
        """
        Los temas legacy a veces guardan en Markup cadenas decorativas inválidas
        para Pango/GTK, por ejemplo "<>", "<s><>" o "< ><>".

        Regla segura:
        - Si el Markup contiene [TEXT], lo usamos como plantilla Pango y escapamos el texto.
        - Si forced_color está definido, reemplazamos el foreground del tema.
        - Si no contiene [TEXT], ignoramos ese Markup y mostramos texto plano.
        - Si Pango falla igual, caemos siempre a texto plano.
        """
        plain_text = str(text or "")
        markup_text = str(markup or "")

        if forced_color:
            try:
                label.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA())
            except Exception:
                pass

        if markup_text and "[TEXT]" in markup_text:
            try:
                if forced_color:
                    markup_text = self.sanitize_markup_foreground(markup_text, forced_color)

                if legacy_text_correction:
                    markup_text = self.scale_legacy_markup_font_desc(markup_text)

                label.set_markup(markup_text.replace("[TEXT]", html.escape(plain_text)))

                if legacy_text_correction:
                    self.apply_legacy_label_font_scale(label)

                return
            except Exception:
                pass

        label.set_text(plain_text)

        if forced_color:
            rgba = Gdk.RGBA()
            if rgba.parse(forced_color):
                try:
                    label.override_color(Gtk.StateFlags.NORMAL, rgba)
                except Exception:
                    pass

        if legacy_text_correction:
            self.apply_legacy_label_font_scale(label)

    def draw_buttons(self):
        for button in self.theme.buttons:
            self.draw_button(button)

    def get_display_icon_pixbuf(self, pixbuf, has_label):
        if not pixbuf:
            return None

        if has_label and pixbuf.get_width() > 64:
            crop_w = min(28, pixbuf.get_width())
            crop_h = min(26, pixbuf.get_height())

            try:
                return pixbuf.new_subpixbuf(0, 0, crop_w, crop_h)
            except Exception:
                return pixbuf

        return pixbuf

    def get_background_luminance_at(self, x, y, w, h):
        """
        Devuelve luminosidad promedio del PNG de fondo en una zona.
        Sirve para elegir texto claro/oscuro en botones legacy.
        """
        if not self.background_pixbuf:
            return 255.0

        bg_w = self.background_pixbuf.get_width()
        bg_h = self.background_pixbuf.get_height()

        x0 = max(0, min(bg_w, int(x)))
        y0 = max(0, min(bg_h, int(y)))
        x1 = max(0, min(bg_w, int(x + max(1, w))))
        y1 = max(0, min(bg_h, int(y + max(1, h))))

        if x1 <= x0 or y1 <= y0:
            return 255.0

        rowstride = self.background_pixbuf.get_rowstride()
        n_channels = self.background_pixbuf.get_n_channels()
        has_alpha = self.background_pixbuf.get_has_alpha()
        pixels = self.background_pixbuf.get_pixels()

        step_x = max(1, int((x1 - x0) / 16))
        step_y = max(1, int((y1 - y0) / 16))

        total = 0.0
        count = 0

        for py in range(y0, y1, step_y):
            for px in range(x0, x1, step_x):
                offset = py * rowstride + px * n_channels

                try:
                    r = pixels[offset]
                    g = pixels[offset + 1]
                    b = pixels[offset + 2]
                    a = pixels[offset + 3] if has_alpha and n_channels >= 4 else 255
                except Exception:
                    continue

                if a < 40:
                    continue

                luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
                total += luminance
                count += 1

        if count == 0:
            return 255.0

        return total / float(count)

    def readable_text_color_for_area(self, x, y, w, h):
        luminance = self.get_background_luminance_at(x, y, w, h)

        # Umbral un poco alto porque muchos temas legacy tienen fondos con textura.
        if luminance < 145.0:
            return "#f2f2f2"

        return "#202020"

    def sanitize_markup_foreground(self, markup, forced_color):
        """
        Reemplaza foreground='...' o foreground="..." en Markup legacy.
        Si no trae foreground pero trae [TEXT], lo envuelve en span.
        """
        markup = str(markup or "")

        if not markup:
            return markup

        markup = re.sub(
            r"foreground\s*=\s*(['\"])[^'\"]*\1",
            f"foreground='{forced_color}'",
            markup
        )

        if "foreground=" not in markup and "[TEXT]" in markup:
            markup = f"<span foreground='{forced_color}'>" + markup + "</span>"

        return markup

    def draw_button(self, button):
        if button.name == ":SEPARATOR:":
            pixbuf = self.load_pixbuf(button.image)
            if pixbuf:
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                self.fixed.put(image, button.x, button.y)
            return

        event = Gtk.EventBox()
        event.set_visible_window(False)

        container = Gtk.Fixed()

        try:
            container.set_has_window(False)
        except Exception:
            pass

        bg_pixbuf = self.load_pixbuf(button.image)

        label_text = self.extract_label_text(button)
        has_label = bool(label_text)

        width = 120
        height = 26

        bg_widget = None
        icon_widget = None
        icon_pixbuf = None
        icon_sel_pixbuf = None

        # Regla fiel a GnoMenu:
        # ButtonIcon / ButtonIconSel = icono chico del botón.
        # Icon = icono para cambiar el avatar grande al hacer hover.
        # Por eso NO usamos button.icon como icono chico.
        icon_pixbuf_raw = None
        icon_sel_pixbuf_raw = None

        if getattr(button, "button_icon", ""):
            icon_pixbuf_raw = self.load_pixbuf(button.button_icon)

        if getattr(button, "button_icon_sel", ""):
            icon_sel_pixbuf_raw = self.load_pixbuf(button.button_icon_sel)

        if not icon_sel_pixbuf_raw:
            icon_sel_pixbuf_raw = icon_pixbuf_raw

        icon_pixbuf = self.get_display_icon_pixbuf(icon_pixbuf_raw, has_label)
        icon_sel_pixbuf = self.get_display_icon_pixbuf(icon_sel_pixbuf_raw, has_label)

        if bg_pixbuf:
            bg_widget = Gtk.Image.new_from_pixbuf(bg_pixbuf)

            # Si el botón tiene texto, la imagen del botón funciona como fondo hover.
            # Si no tiene texto, se muestra siempre, como los botones Power/Aux.
            if has_label:
                bg_widget.set_no_show_all(True)
                bg_widget.hide()

            container.put(bg_widget, 0, 0)

            width = max(width, bg_pixbuf.get_width())
            height = max(height, bg_pixbuf.get_height())

        if icon_pixbuf:
            icon_widget = Gtk.Image.new_from_pixbuf(icon_pixbuf)

            if has_label:
                container.put(icon_widget, 4, 2)
            else:
                container.put(icon_widget, 0, 0)

            width = max(width, icon_pixbuf.get_width())
            height = max(height, icon_pixbuf.get_height())

        if label_text:
            label = Gtk.Label()
            label.set_use_markup(True)

            # Color automático por zona del fondo. Esto corrige temas como Whise/Gray
            # donde el XML fuerza texto oscuro sobre panel oscuro.
            forced_color = self.readable_text_color_for_area(
                button.x + button.text_x,
                button.y + button.text_y,
                max(10, width - button.text_x - 4),
                height
            )

            self.safe_set_markup_or_text(
                label,
                button.markup,
                label_text,
                forced_color=forced_color,
                legacy_text_correction=True
            )

            label.set_xalign(0)
            label.set_yalign(0.5)

            text_x = int(button.text_x)
            text_y = int(button.text_y + LEGACY_BUTTON_TEXT_BASELINE_OFFSET_Y)
            text_w = max(10, width - text_x - 4)
            text_h = max(1, height - min(0, text_y))

            label.set_size_request(text_w, text_h)
            container.put(label, text_x, text_y)

        event.add(container)
        event.set_size_request(width, height)

        event.connect("button-press-event", self.on_button_clicked, button)

        event.connect(
            "enter-notify-event",
            self.on_button_enter,
            button,
            bg_widget,
            icon_widget,
            icon_pixbuf,
            icon_sel_pixbuf
        )

        event.connect(
            "leave-notify-event",
            self.on_button_leave,
            button,
            bg_widget,
            icon_widget,
            icon_pixbuf
        )

        self.fixed.put(event, button.x, button.y)

    def on_button_enter(self, widget, event, button, bg_widget, icon_widget,
                        icon_pixbuf, icon_sel_pixbuf):
        if bg_widget:
            bg_widget.show()

        if icon_widget and icon_sel_pixbuf:
            icon_widget.set_from_pixbuf(icon_sel_pixbuf)

        if getattr(button, "execute_on_hover", 0):
            self.on_button_hover(widget, event, button)

        if getattr(button, "icon", ""):
            self.start_avatar_hover_timer(button)

        return False

    def on_button_leave(self, widget, event, button, bg_widget, icon_widget,
                        icon_pixbuf):
        if bg_widget:
            bg_widget.hide()

        if icon_widget and icon_pixbuf:
            icon_widget.set_from_pixbuf(icon_pixbuf)

        self.cancel_avatar_hover_timer()
        self.restore_user_avatar()

        return False

    def extract_label_text(self, button):
        if not button.name or button.name.startswith(":"):
            return ""

        name_lower = button.name.strip().lower()
        command_lower = button.command.strip().lower() if button.command else ""

        markup_plain = ""

        if button.markup:
            markup_plain = re.sub(r"<[^>]+>", "", button.markup)
            markup_plain = html.unescape(markup_plain).strip()

            if "[TEXT]" not in button.markup and markup_plain == "":
                return ""

        # Si el XML trae texto explícito en Markup, se respeta.
        # Si la traducción devuelve vacío (por ejemplo Command=Power en
        # algunos temas legacy), usamos el texto original del Markup.
        if markup_plain:
            translated = tr_legacy_button_label(command_lower, markup_plain)
            return translated if translated else markup_plain

        icon_only_names = {
            "power",
            "aux",
            "lock",
            "logout",
            "log off",
            "shutdown",
            "shut down",
            "apagar",
            "cerrar sesión",
            "cerrar sesion",
            "bloquear",
        }

        icon_only_commands = {
            "power",
            "shutdown",
            "logout",
            "lock",
            "gnome-session-quit --power-off",
            "gnome-session-quit --logout",
            "xfce4-session-logout --halt",
            "xfce4-session-logout --logout",
        }

        if name_lower in icon_only_names:
            return ""

        if command_lower in icon_only_commands:
            return ""

        if button.y > (self.theme.height - 60) and (button.image or button.button_icon):
            return ""

        translated = tr_legacy_button_label(command_lower, button.name)
        return translated

    def draw_labels(self):
        for label_def in self.theme.labels:
            text = label_def.name

            if label_def.command:
                text = self.run_label_command(label_def.command)

            label = Gtk.Label()
            label.set_use_markup(True)

            self.safe_set_markup_or_text(label, label_def.markup, text)

            self.fixed.put(label, label_def.x, label_def.y)

    def run_label_command(self, command):
        try:
            output = subprocess.check_output(
                command,
                shell=True,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
            return output.decode("utf-8").strip()
        except Exception:
            return ""

    def handle_legacy_button_action(self, command):
        """
        Ejecuta acciones legacy conocidas por Command.
        Esto evita depender de rutas escritas en inglés dentro del XML.
        """
        command = (command or "").strip()
        command_lower = command.lower()

        folder_map = {
            "home": ("HOME", "~"),
            "documents": ("DOCUMENTS", "~/Documentos"),
            "pictures": ("PICTURES", "~/Imágenes"),
            "music": ("MUSIC", "~/Música"),
            "videos": ("VIDEOS", "~/Vídeos"),
        }

        if command_lower in folder_map:
            key, fallback = folder_map[command_lower]
            open_path(get_xdg_user_dir(key, fallback))
            return True

        # Algunos temas viejos usan Games por error en el botón Videos.
        # No lo tratamos como carpeta para no romper botones reales de juegos.

        if command_lower == "computer":
            open_path(os.path.expanduser("~"))
            return True

        if command_lower == "network":
            run_command("thunar network:///")
            return True

        if command_lower == "network config":
            run_command("exo-open --launch WebBrowser")
            return True

        if command_lower == "control panel":
            run_command("xfce4-settings-manager")
            return True

        if command_lower in (
            "package manager",
            "software center",
            "software-center",
            "software manager",
            "gestor de paquetes",
            "centro de software",
        ):
            run_command("software-center")
            return True

        if command_lower in ("printer", "printers"):
            run_command("Printer")
            return True

        if command_lower == "help":
            if shutil.which("xfhelp4"):
                run_command("xfhelp4")
            else:
                run_command("exo-open --launch WebBrowser https://docs.xfce.org/")
            return True

        if command_lower == "run":
            if shutil.which("xfce4-appfinder"):
                run_command("xfce4-appfinder --collapsed")
            else:
                run_command("xfrun4")
            return True

        # Órdenes de energía/sesión.
        # Power y Aux se interpretan como submenú seguro, no como apagado directo.
        if command_lower in ("power", "aux", "3"):
            self.show_power_items()
            return True

        if command_lower in ("lock", "lock screen"):
            run_command("xflock4")
            return True

        if command_lower in ("logout", "logoutnow", "log out", "logoff", "log off"):
            run_command("xfce4-session-logout --logout")
            return True

        if command_lower in ("shutdown", "shut down", "halt"):
            # Si querés máxima seguridad, cambiar por: xfce4-session-logout
            run_command("xfce4-session-logout --halt")
            return True

        if command_lower in ("restart", "reboot"):
            run_command("xfce4-session-logout --reboot")
            return True

        if command_lower == "suspend":
            run_command("xfce4-session-logout --suspend")
            return True

        if command_lower == "hibernate":
            run_command("xfce4-session-logout --hibernate")
            return True

        return False


    def handle_internal_menu_command(self, command):
        """
        Interpreta comandos internos heredados de GnoMenu.
        Estos no deben ejecutarse como binarios del sistema.
        """
        command = (command or "").strip()
        command_lower = command.lower()

        if command_lower in ("1", ":applications:", "applications", "apps", "categories"):
            self.show_categories()
            return True

        if command_lower in ("2", ":recentapps:", ":recent_apps:", "recentapps", "recent apps"):
            self.show_recent_apps()
            return True

        if command_lower in ("4", ":recent:", ":recentfiles:", ":recent_files:", "recent", "recent files", "recently used"):
            self.show_recent_items()
            return True

        if command_lower in ("7", ":favorites:", "favorites", "favourites", "favoritos"):
            self.show_favorites()
            return True

        if command_lower in ("8", ":computer:", "computer", "places", "equipo"):
            self.show_computer_items()
            return True

        if command_lower in ("3", ":aux:", "aux", "session", "session options"):
            self.show_power_items()
            return True

        if command_lower in ("9", ":leave:", "leave", "salir"):
            self.show_leave_items()
            return True

        if command_lower in ("power-menu", ":power-menu:", "shutdown-menu"):
            self.show_power_items()
            return True

        if command_lower in ("10", ":bookmarks:", ":webbookmarks:", "web bookmarks", "bookmarks"):
            self.show_web_bookmarks()
            return True

        if command_lower in (":allapps:", ":all_apps:", "allapps", "all apps", "all applications", "todas", "todas las aplicaciones"):
            self.show_all_apps()
            return True

        return False

    def on_button_clicked(self, widget, event, button):
        if getattr(event, "type", None) == Gdk.EventType.BUTTON_PRESS:
            self.play_event_sound("button")

        command = (getattr(button, "command", "") or "").strip()
        command_lower = command.lower()

        # :ALLAPPS: es navegación interna y nunca debe enviarse al sistema.
        if command_lower in (
            ":allapps:",
            ":all_apps:",
            "allapps",
            "all apps",
            "all applications",
            "todas",
            "todas las aplicaciones",
        ):
            self.show_all_apps()
            return

        # Botones legacy de carpetas/sistema.
        if self.handle_legacy_button_action(command):
            # Power/Aux abren un submenú interno, no deben cerrar la ventana.
            if command_lower not in ("power", "aux", "3") and button.close_menu:
                self.close_menu()
            return

        # Botones legacy que no son comandos reales del sistema.
        if self.handle_internal_menu_command(command):
            return

        # En temas como Gray, Command="Search" debe enfocar el buscador,
        # no intentar ejecutar un binario llamado "Search".
        if command_lower in ("search", ":search:", "find", "buscar"):
            if self.search_entry:
                self.search_entry.grab_focus()
            return

        if command_lower in ("", "none", "noop", ":none:"):
            return

        run_command(command)

        if button.close_menu:
            self.close_menu()

    def on_button_hover(self, widget, event, button):
        command = (getattr(button, "command", "") or "").strip()
        command_lower = command.lower()

        if command_lower in (
            ":allapps:",
            ":all_apps:",
            "allapps",
            "all apps",
            "all applications",
            "todas",
            "todas las aplicaciones",
        ):
            if self.current_view != "all_apps":
                self.show_all_apps()
            return

        if self.handle_internal_menu_command(command):
            return

        self.on_button_clicked(widget, event, button)

    def on_app_context_menu_deactivate(self, menu):
        # Gtk.Menu emite "deactivate" antes de terminar de procesar el clic
        # sobre el elemento elegido. Conservamos una protección breve para que
        # el focus-out de ese mismo clic no cierre la ventana principal.
        self.context_menu_focus_guard = True

        GLib.timeout_add(250, self.finish_context_menu_close)

    def finish_context_menu_close(self):
        self.app_context_menu = None

        if not self.close_requested:
            try:
                self.present()
                self.grab_focus()

                if self.program_listbox:
                    self.program_listbox.grab_focus()
            except Exception:
                pass

        GLib.timeout_add(250, self.clear_context_menu_focus_guard)
        return False

    def clear_context_menu_focus_guard(self):
        self.context_menu_focus_guard = False
        return False

    def on_focus_out(self, widget, event):
        # Gtk.Menu usa una ventana temporal. También ignoramos el breve
        # focus-out que ocurre al pulsar una opción del menú contextual.
        if getattr(self, "app_context_menu", None) is not None:
            return False

        if getattr(self, "context_menu_focus_guard", False):
            return False

        if self.close_on_focus_out:
            self.close_menu()

        return False

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close_menu()
            return True

        # Al escribir estando el foco fuera del buscador, mandamos el texto al Entry.
        # Así el filtrado se siente como menú real.
        char_code = Gdk.keyval_to_unicode(event.keyval)
        state = event.state
        blocked_mods = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK

        if self.search_entry and char_code > 0 and not (state & blocked_mods):
            char = chr(char_code)
            if char.isprintable():
                self.search_entry.grab_focus()
                current = self.search_entry.get_text()
                self.search_entry.set_text(current + char)
                self.search_entry.set_position(-1)
                return True

        return False

    def get_monitor_geometry_for_point(self, point_x=None, point_y=None):
        """
        Devuelve la geometría del monitor donde está el puntero/lanzador.
        Si no se puede detectar, usa el monitor primario como fallback.
        """
        try:
            display = Gdk.Display.get_default()

            if display is not None and point_x is not None and point_y is not None:
                try:
                    monitor = display.get_monitor_at_point(int(point_x), int(point_y))
                    if monitor is not None:
                        return monitor.get_geometry()
                except Exception:
                    pass

            if display is not None:
                monitor = display.get_primary_monitor()

                if monitor is None:
                    monitor = display.get_monitor(0)

                if monitor is not None:
                    return monitor.get_geometry()
        except Exception:
            pass

        screen = self.get_screen()
        monitor = screen.get_primary_monitor()
        return screen.get_monitor_geometry(monitor)

    def get_pointer_position(self):
        """
        Usa la posición del puntero como referencia del lanzador.
        Al abrir desde el panel, normalmente el mouse queda sobre el botón.
        """
        try:
            display = Gdk.Display.get_default()
            seat = display.get_default_seat() if display else None
            pointer = seat.get_pointer() if seat else None

            if pointer:
                result = pointer.get_position()

                # PyGObject/GDK3 puede devolver (screen, x, y) o (x, y)
                # según versión/bindings.
                if isinstance(result, tuple):
                    if len(result) >= 3:
                        return int(result[1]), int(result[2])
                    if len(result) >= 2:
                        return int(result[0]), int(result[1])
        except Exception:
            pass

        try:
            screen = self.get_screen()
            result = screen.get_root_window().get_pointer()

            if isinstance(result, tuple):
                if len(result) >= 3:
                    return int(result[1]), int(result[2])
                if len(result) >= 2:
                    return int(result[0]), int(result[1])
        except Exception:
            pass

        return None, None

    def clamp_menu_position_to_monitor(self, x, y, geometry):
        left = int(geometry.x)
        top = int(geometry.y)
        right = int(geometry.x + geometry.width)
        bottom = int(geometry.y + geometry.height)

        x = max(left, min(int(x), right - int(self.theme.width)))
        y = max(top, min(int(y), bottom - int(self.theme.height)))

        return x, y

    def position_near_launcher(self):
        """
        Posicionamiento inteligente tipo menú real:
        - toma el puntero como referencia del lanzador del panel;
        - si el panel está arriba, abre hacia abajo;
        - si el panel está abajo, abre hacia arriba;
        - corrige bordes para que el menú no salga de pantalla.
        """
        pointer_x, pointer_y = self.get_pointer_position()
        geometry = self.get_monitor_geometry_for_point(pointer_x, pointer_y)

        # Fallback seguro: esquina inferior izquierda del monitor.
        if pointer_x is None or pointer_y is None:
            x = int(geometry.x)
            y = int(geometry.y + geometry.height - self.theme.height - LEGACY_MENU_PANEL_GAP)
            x, y = self.clamp_menu_position_to_monitor(x, y, geometry)
            self.move(x, y)
            return

        monitor_mid_y = int(geometry.y + (geometry.height / 2))
        panel_is_top = int(pointer_y) < monitor_mid_y

        # Alineamos cerca del lanzador, pero no exactamente bajo el puntero
        # para evitar que el menú quede corrido si se hace clic en el borde del botón.
        x = int(pointer_x) - LEGACY_MENU_PANEL_GAP

        if panel_is_top:
            y = int(pointer_y) + LEGACY_MENU_LAUNCHER_GUESS_SIZE + LEGACY_MENU_PANEL_GAP
        else:
            y = int(pointer_y) - int(self.theme.height) - LEGACY_MENU_PANEL_GAP

        x, y = self.clamp_menu_position_to_monitor(x, y, geometry)
        self.move(x, y)

    def position_near_bottom_left(self):
        """
        Posiciona XFCEMenu abajo a la izquierda del monitor principal.

        Importante:
        - No usa el puntero.
        - No usa position_near_launcher().
        - Esto evita que el menú aparezca donde está el mouse.
        """
        try:
            display = Gdk.Display.get_default()
            monitor = None

            if display is not None:
                try:
                    monitor = display.get_primary_monitor()
                except Exception:
                    monitor = None

                if monitor is None:
                    try:
                        monitor = display.get_monitor(0)
                    except Exception:
                        monitor = None

            if monitor is not None:
                geometry = monitor.get_geometry()
                x = int(geometry.x)
                y = int(geometry.y + geometry.height - self.theme.height - 32)
            else:
                raise RuntimeError("No monitor geometry")

        except Exception:
            try:
                screen = self.get_screen()
                monitor_index = screen.get_primary_monitor()
                geometry = screen.get_monitor_geometry(monitor_index)

                x = int(geometry.x)
                y = int(geometry.y + geometry.height - self.theme.height - 32)
            except Exception:
                x = 0
                y = 0

        if y < 0:
            y = 0

        self.move(x, y)
        return False


def find_menu_theme(theme_name):
    candidates = [
        os.path.join(THEMES_DIR, "Menu", theme_name),
        os.path.join(THEMES_DIR, "menus", theme_name),
        os.path.join(THEMES_DIR, theme_name),
        os.path.join(BASE_DIR, theme_name),
    ]

    for path in candidates:
        if os.path.isdir(path):
            return path

    return None


def main():
    config = load_xfcemenu_config()

    parser = argparse.ArgumentParser(description="XFCEMenu")
    parser.add_argument(
        "--theme",
        default=None,
        help="Nombre de carpeta del tema de menú dentro de themes/Menu"
    )
    parser.add_argument(
        "--icon-theme",
        default=None,
        help="Nombre de carpeta del paquete de iconos dentro de themes/Icon"
    )
    parser.add_argument(
        "--icon-source",
        choices=("auto", "theme", "system"),
        default=None,
        help="Fuente de iconos: auto, theme o system"
    )
    parser.add_argument(
        "--button-theme",
        default=None,
        help="Nombre de carpeta del paquete de botones dentro de themes/Button"
    )
    parser.add_argument(
        "--sound-theme",
        default=None,
        help="Nombre de carpeta del paquete de sonidos dentro de themes/Sound"
    )
    parser.add_argument(
        "--no-sounds",
        action="store_true",
        help="Desactiva sonidos para esta ejecución"
    )
    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="Lista paquetes detectados en themes/Menu, Icon, Button y Sound"
    )

    args = parser.parse_args()

    if args.list_themes:
        print_available_themes()
        return 0

    configured_menu = config.get("theme", "menu_theme", fallback=DEFAULT_CONFIG["theme"]["menu_theme"])
    configured_icon = config.get("theme", "icon_theme", fallback=DEFAULT_CONFIG["theme"]["icon_theme"])
    configured_button = config.get("theme", "button_theme", fallback=DEFAULT_CONFIG["theme"]["button_theme"])
    configured_sound = config.get("theme", "sound_theme", fallback=DEFAULT_CONFIG["theme"]["sound_theme"])
    configured_icon_source = config.get(
        "icons",
        "source",
        fallback=DEFAULT_CONFIG["icons"]["source"]
    ).strip().lower()

    if configured_icon_source not in ("auto", "theme", "system"):
        configured_icon_source = "auto"

    menu_theme = resolve_theme_choice(
        "menu",
        args.theme or configured_menu,
        DEFAULT_CONFIG["theme"]["menu_theme"]
    )

    icon_theme = resolve_theme_choice(
        "icon",
        args.icon_theme or configured_icon,
        DEFAULT_CONFIG["theme"]["icon_theme"],
        menu_theme
    )

    button_theme = resolve_theme_choice(
        "button",
        args.button_theme or configured_button,
        configured_button,
        menu_theme
    )

    sound_theme = resolve_theme_choice(
        "sound",
        args.sound_theme or configured_sound,
        DEFAULT_CONFIG["theme"]["sound_theme"],
        menu_theme
    )

    icon_source = args.icon_source or configured_icon_source

    if not menu_theme:
        print("XFCEMenu: no se encontró ningún tema de menú en:")
        print(f"  {os.path.join(THEMES_DIR, 'Menu')}")
        return 1

    theme_dir = find_menu_theme(menu_theme)

    if not theme_dir:
        print(f"No se encontró el tema: {menu_theme}")
        print("Rutas buscadas:")
        print(f"  {os.path.join(THEMES_DIR, 'Menu', menu_theme)}")
        print(f"  {os.path.join(THEMES_DIR, 'menus', menu_theme)}")
        print(f"  {os.path.join(THEMES_DIR, menu_theme)}")
        return 1

    play_sounds = config_bool(config, "behavior", "play_sounds", True) and not args.no_sounds
    close_on_focus_out = config_bool(config, "behavior", "close_on_focus_out", True)
    show_avatar = config_bool(config, "behavior", "show_avatar", True)
    icon_size = config_int(config, "interface", "icon_size", 24)

    print("XFCEMenu: configuración activa")
    print(f"  Config: {CONFIG_FILE}")
    print(f"  Menu:   {menu_theme}")
    print(f"  Icon:   {icon_theme or '(fallback GTK)'}")
    print(f"  Source: {icon_source}")
    print(f"  Button: {button_theme or '(auto)'}")
    print(f"  Sound:  {sound_theme or '(sin sonidos)'}")
    print(f"  Temas:  {THEMES_DIR}")

    try:
        theme = load_menu_theme(theme_dir)
    except Exception as e:
        print(f"Error cargando tema: {e}")
        return 1

    app = Gtk.Application(application_id="org.renetrox.xfcemenu")

    def on_activate(application):
        window = XFCEMenuWindow(
            theme,
            icon_theme=icon_theme,
            button_theme=button_theme,
            sound_theme=sound_theme,
            play_sounds=play_sounds,
            close_on_focus_out=close_on_focus_out,
            show_avatar=show_avatar,
            icon_size=icon_size,
            icon_source=icon_source
        )
        window.set_application(application)
        window.show_all()

    app.connect("activate", on_activate)

    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
