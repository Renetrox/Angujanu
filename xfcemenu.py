#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import re
import html
import configparser
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


CATEGORY_DEFINITIONS = [
    # key, label, icon, matcher
    ("browse", "Browse Internet", "internet-web-browser", "browser"),
    ("email", "E-mail", "internet-mail", "email"),
    ("all", "Applications", "applications-other", "all"),
    ("development", "Development", "applications-development", "Development"),
    ("games", "Games", "applications-games", "Game"),
    ("graphics", "Graphics", "applications-graphics", "Graphics"),
    ("internet", "Internet", "applications-internet", "Network"),
    ("multimedia", "Multimedia", "applications-multimedia", "AudioVideo;Audio;Video;Player;Recorder"),
    ("office", "Office", "applications-office", "Office"),
    ("system", "System", "applications-system", "System;Settings;PackageManager"),
    ("utilities", "Utilities", "applications-utilities", "Utility;Accessories;FileManager;Archiving;Compression;TextEditor;TerminalEmulator"),
    ("wine", "Wine", "applications-wine", "Wine;X-Wine"),
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


def load_desktop_apps():
    """
    Carga programas reales desde .desktop.
    Busca en sistema + usuario, filtra ocultos y evita duplicados.
    """
    apps = []
    seen = set()

    app_dirs = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        os.path.expanduser("~/.local/share/applications"),
    ]

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

            name = entry.get("Name", "").strip()
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
                comment=entry.get("Comment", "").strip(),
                desktop_file=desktop_path,
                categories=entry.get("Categories", "").strip()
            ))

    apps.sort(key=lambda app: app.name.lower())
    return apps



class XFCEMenuWindow(Gtk.Window):
    def __init__(self, theme):
        super().__init__(title="XFCEMenu")

        self.theme = theme
        self.background_pixbuf = None
        self.shape_applied = False

        # Program list / search widgets.
        self.apps = load_desktop_apps()
        self.categories = self.build_categories()
        self.filtered_apps = list(self.apps)
        self.current_view = "categories"
        self.current_category = None
        self.program_scrolled = None
        self.program_listbox = None
        self.search_entry = None

        # Avatar / user icon.
        self.avatar_image_widget = None
        self.avatar_frame_widget = None
        self.avatar_normal_pixbuf = None
        self.avatar_hover_timer = None

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)

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

        self.draw_user_icon()
        self.draw_buttons()
        self.draw_labels()

        self.connect("focus-out-event", self.on_focus_out)
        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", self.on_destroy)

        self.position_near_bottom_left()

        GLib.idle_add(self.present)

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

        .xfcemenu-program-label {{
            color: {program_text_color};
        }}

        .xfcemenu-program-message {{
            color: {program_message_color};
        }}

        #xfcemenu-program-row:selected .xfcemenu-program-label,
        #xfcemenu-program-row:selected .xfcemenu-program-message {{
            color: @theme_selected_fg_color;
        }}

        /* No tocamos el fondo de :hover ni de :selected.
         * Esas barras las dibuja el tema GTK, igual que GnoMenu.
         */

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

    def theme_path(self, filename):
        return os.path.join(self.theme.theme_dir, filename)

    def load_pixbuf(self, filename):
        if not filename:
            return None

        candidates = []

        if os.path.isabs(filename):
            candidates.append(filename)

        candidates.append(self.theme_path(filename))

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
        Carga iconos legacy o iconos del tema GTK del sistema.

        Ejemplos:
            Icon="folder-documents.png"
            Icon="computer.png"
            Icon="search.png"
        """
        if not icon_name:
            return None

        pixbuf = self.load_pixbuf(icon_name)

        if pixbuf:
            return self.scale_pixbuf_contain(pixbuf, size, size)

        icon_theme = Gtk.IconTheme.get_default()

        base_name = icon_name.strip()

        if base_name.lower().endswith((".png", ".svg", ".xpm")):
            base_name = os.path.splitext(base_name)[0]

        names_to_try = [base_name]

        aliases = {
            "back": "go-previous",
            "previous": "go-previous",
            "gtk-go-back": "go-previous",
            "go-back": "go-previous",
            "internet-web-browser": "web-browser",
            "web-browser": "applications-internet",
            "internet-mail": "mail-message-new",
            "applications-wine": "wine",
            "gtk-network": "network-workgroup",
            "gnome-network-properties": "preferences-system-network",
            "gnome-control-center": "preferences-system",
            "gnome-help": "help-browser",
            "emblem-package": "system-software-install",
            "folder-images": "folder-pictures",
            "document-open-recent": "document-open-recent",
            "search": "system-search",
            "run": "system-run",
            "computer": "computer",
            "folder-home": "user-home",
            "folder-documents": "folder-documents",
            "folder-music": "folder-music",
            "folder-videos": "folder-videos",
            "folder-pictures": "folder-pictures",
            "gtk-missing-image": "image-missing",
        }

        if base_name in aliases:
            names_to_try.append(aliases[base_name])

        for name in names_to_try:
            try:
                return icon_theme.load_icon(
                    name,
                    size,
                    Gtk.IconLookupFlags.FORCE_SIZE
                )
            except Exception:
                pass

        print(f"XFCEMenu: icono GTK no encontrado: {icon_name}")
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

            # En la vista inicial no mostramos categorías vacías, salvo Applications.
            if category.apps or key == "all":
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
        self.program_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.program_listbox.set_activate_on_single_click(True)
        self.program_listbox.connect("row-activated", self.on_program_row_activated)

        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        viewport.add(self.program_listbox)

        self.program_scrolled.add(viewport)
        self.fixed.put(self.program_scrolled, x, y)

        self.show_categories()

    def draw_search_widget(self):
        area = self.get_search_area()

        if not area:
            return

        x, y, w, h = area

        self.search_entry = Gtk.Entry()
        self.search_entry.set_name("xfcemenu-search-entry")
        self.search_entry.set_placeholder_text("Search")
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
        if not self.program_listbox:
            return

        first_row = self.program_listbox.get_row_at_index(0)
        if first_row and first_row.get_selectable():
            self.program_listbox.select_row(first_row)

    def create_base_row(self, item, icon_name, label_text):
        row = Gtk.ListBoxRow()
        row.set_name("xfcemenu-program-row")
        row.menu_item = item
        row.set_activatable(True)
        row.set_selectable(True)
        row.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK)
        row.connect("enter-notify-event", self.on_program_row_enter)
        row.connect("button-press-event", self.on_program_row_button_press)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(2)
        box.set_margin_bottom(2)

        icon_pixbuf = None
        if icon_name:
            icon_pixbuf = self.load_icon_pixbuf(icon_name, 24)

        if not icon_pixbuf:
            icon_pixbuf = self.load_icon_pixbuf("application-x-executable", 24)

        if icon_pixbuf:
            icon = Gtk.Image.new_from_pixbuf(icon_pixbuf)
        else:
            icon = Gtk.Image()

        icon.set_size_request(24, 24)

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
        Hace que la selección siga al mouse, pero la pinta GTK.
        Así la barra visual no es inventada por Cairo.
        """
        if self.program_listbox and row.get_selectable():
            self.program_listbox.select_row(row)

        return False

    def on_program_row_button_press(self, row, event):
        if event.button == 1 and self.program_listbox and row.get_selectable():
            self.program_listbox.select_row(row)

        return False

    def on_program_row_activated(self, listbox, row):
        item_type = getattr(row, "item_type", "")

        if item_type == "category":
            self.show_category_apps(getattr(row, "category", None))
            return

        if item_type == "back":
            if self.search_entry:
                self.search_entry.set_text("")
            self.show_categories()
            return

        if item_type == "app":
            app = getattr(row, "app", None)
            self.launch_app(app)

    def on_search_changed(self, entry):
        query = entry.get_text().strip()

        if query:
            self.show_search_results(query)
        else:
            self.show_categories()

    def on_search_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
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

        try:
            subprocess.Popen(app.exec_cmd, shell=True)
            self.destroy()
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

            if button.markup:
                try:
                    label.set_markup(button.markup.replace("[TEXT]", label_text))
                except Exception:
                    label.set_text(label_text)
            else:
                label.set_text(label_text)

            label.set_xalign(0)
            label.set_size_request(max(10, width - button.text_x - 4), height)
            container.put(label, button.text_x, button.text_y)

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

        if button.markup:
            plain = re.sub(r"<[^>]+>", "", button.markup)
            plain = html.unescape(plain).strip()

            if "[TEXT]" not in button.markup and plain == "":
                return ""

        return button.name

    def draw_labels(self):
        for label_def in self.theme.labels:
            text = label_def.name

            if label_def.command:
                text = self.run_label_command(label_def.command)

            label = Gtk.Label()
            label.set_use_markup(True)

            if label_def.markup:
                try:
                    label.set_markup(label_def.markup.replace("[TEXT]", text))
                except Exception:
                    label.set_text(text)
            else:
                label.set_text(text)

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

    def on_button_clicked(self, widget, event, button):
        run_command(button.command)

        if button.close_menu:
            self.destroy()

    def on_button_hover(self, widget, event, button):
        if button.command == ":ALLAPPS:":
            print("XFCEMenu: hover :ALLAPPS: todavía pendiente.")
        else:
            self.on_button_clicked(widget, event, button)

    def on_focus_out(self, widget, event):
        self.destroy()

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
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

    def position_near_bottom_left(self):
        try:
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor()

            if monitor is None:
                monitor = display.get_monitor(0)

            geometry = monitor.get_geometry()

            x = geometry.x
            y = geometry.y + geometry.height - self.theme.height - 32

        except Exception:
            screen = self.get_screen()
            monitor = screen.get_primary_monitor()
            geometry = screen.get_monitor_geometry(monitor)

            x = geometry.x
            y = geometry.y + geometry.height - self.theme.height - 32

        if y < 0:
            y = 0

        self.move(x, y)


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
    parser = argparse.ArgumentParser(description="XFCEMenu prototype")
    parser.add_argument(
        "--theme",
        default="Windows 7 Box",
        help="Nombre del tema de menú"
    )

    args = parser.parse_args()

    theme_dir = find_menu_theme(args.theme)

    if not theme_dir:
        print(f"No se encontró el tema: {args.theme}")
        print("Rutas buscadas:")
        print(f"  {os.path.join(THEMES_DIR, 'Menu', args.theme)}")
        print(f"  {os.path.join(THEMES_DIR, 'menus', args.theme)}")
        print(f"  {os.path.join(THEMES_DIR, args.theme)}")
        return 1

    try:
        theme = load_menu_theme(theme_dir)
    except Exception as e:
        print(f"Error cargando tema: {e}")
        return 1

    app = Gtk.Application(application_id="org.renetrox.xfcemenu")

    def on_activate(application):
        window = XFCEMenuWindow(theme)
        window.set_application(application)
        window.show_all()

    app.connect("activate", on_activate)

    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
