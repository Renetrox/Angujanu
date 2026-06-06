#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import cairo

from legacy_loader import load_menu_theme
from command_mapper import run_command


BASE_DIR = "/home/Reneto/XFCEMenu"
THEMES_DIR = os.path.join(BASE_DIR, "themes")


class XFCEMenuWindow(Gtk.Window):
    def __init__(self, theme):
        super().__init__(title="XFCEMenu")

        self.theme = theme
        self.background_pixbuf = None
        self.shape_applied = False

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)

        self.set_size_request(theme.width, theme.height)
        self.set_default_size(theme.width, theme.height)

        # Parecido a GnoMenu: ventana RGBA + dibujo Cairo.
        self.setup_transparency()

        # Truco heredado de GnoMenu:
        # fuerza al compositor a tratar la ventana como translúcida.
        try:
            self.set_opacity(0.99)
        except Exception:
            pass

        # El fondo legacy se dibuja con Cairo, no como Gtk.Image.
        self.background_pixbuf = self.load_pixbuf(self.theme.background)

        self.connect("draw", self.on_draw)
        self.connect("realize", self.on_realize)

        self.fixed = Gtk.Fixed()
        self.fixed.set_name("xfcemenu-root")

        # Importante: que Fixed no cree una ventana propia opaca.
        try:
            self.fixed.set_has_window(False)
        except Exception:
            pass

        self.fixed.set_size_request(theme.width, theme.height)
        self.add(self.fixed)

        # Para probar transparencia, lo dejamos desactivado por ahora.
        # Este placeholder usa widgets GTK y puede pintar fondo propio.
        # self.draw_program_list_placeholder()

        self.draw_buttons()
        self.draw_labels()

        self.connect("focus-out-event", self.on_focus_out)
        self.connect("key-press-event", self.on_key_press)

        self.position_near_bottom_left()

        GLib.idle_add(self.present)

    def setup_transparency(self):
        """
        Transparencia real para temas legacy con PNG RGBA.
        Requiere compositor activo en XFCE.
        """
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

        css = b"""
        window,
        GtkWindow,
        #xfcemenu-root {
            background-color: transparent;
            background-image: none;
            border: none;
            box-shadow: none;
        }

        fixed,
        frame,
        label,
        eventbox,
        box {
            background-color: transparent;
            background-image: none;
            border: none;
            box-shadow: none;
        }
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css)

        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_realize(self, widget):
        """
        Cuando la ventana ya existe en X11/GDK, recién ahí se puede aplicar shape.
        """
        GLib.idle_add(self.apply_window_shape)

    def theme_path(self, filename):
        return os.path.join(self.theme.theme_dir, filename)

    def load_pixbuf(self, filename):
        if not filename:
            return None

        path = self.theme_path(filename)

        if not os.path.isfile(path):
            print(f"XFCEMenu: imagen no encontrada: {path}")
            return None

        try:
            return GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception as e:
            print(f"XFCEMenu: no se pudo cargar imagen {path}: {e}")
            return None

    def on_draw(self, widget, cr):
        """
        Dibuja el fondo principal con Cairo.
        """
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if self.background_pixbuf:
            Gdk.cairo_set_source_pixbuf(cr, self.background_pixbuf, 0, 0)
            cr.paint()

        return False

    def apply_window_shape(self):
        """
        Recorta la ventana usando el canal alfa del PNG de fondo.
        Esto replica la idea de shape/mask del GnoMenu original.
        """
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

        # Alfa va de 0 a 255.
        # 8 = respeta sombras suaves.
        # 80/120 = recorta más agresivo.
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
                    region.union_rectangle(rect)
                else:
                    x += 1

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
        """
        Primera versión:
        dibuja un espacio visual donde luego irá la lista real de apps.
        """
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

    def draw_buttons(self):
        for button in self.theme.buttons:
            self.draw_button(button)

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
        icon_pixbuf = self.load_pixbuf(button.button_icon)

        width = 120
        height = 26

        if bg_pixbuf:
            bg = Gtk.Image.new_from_pixbuf(bg_pixbuf)
            container.put(bg, 0, 0)
            width = max(width, bg_pixbuf.get_width())
            height = max(height, bg_pixbuf.get_height())

        if icon_pixbuf:
            icon = Gtk.Image.new_from_pixbuf(icon_pixbuf)
            container.put(icon, 4, 2)
            width = max(width, icon_pixbuf.get_width())
            height = max(height, icon_pixbuf.get_height())

        label_text = self.extract_label_text(button)

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

        if button.execute_on_hover:
            event.connect("enter-notify-event", self.on_button_hover, button)

        self.fixed.put(event, button.x, button.y)

    def extract_label_text(self, button):
        if button.name.startswith(":"):
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

    def on_focus_out(self, widget, event):
        # En algunos XFCE esto puede cerrar demasiado rápido.
        # Si molesta, comentar esta línea.
        self.destroy()

    def on_key_press(self, widget, event):
        if event.keyval == 65307:  # ESC
            self.destroy()

    def position_near_bottom_left(self):
        """
        Posiciona el menú abajo a la izquierda.
        Usa API moderna si está disponible, con fallback a la API vieja de GTK3.
        """
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
        os.path.join(THEMES_DIR, "menus", theme_name),
        os.path.join(THEMES_DIR, theme_name),
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

    # argparse ya consumió --theme. GTK no debe recibirlo.
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
