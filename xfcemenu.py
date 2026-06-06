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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

        # Temporalmente desactivado hasta crear lista real transparente.
        # self.draw_program_list_placeholder()

        self.draw_buttons()
        self.draw_labels()

        self.connect("focus-out-event", self.on_focus_out)
        self.connect("key-press-event", self.on_key_press)

        self.position_near_bottom_left()

        GLib.idle_add(self.present)

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
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if self.background_pixbuf:
            Gdk.cairo_set_source_pixbuf(cr, self.background_pixbuf, 0, 0)
            cr.paint()

        return False

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

                    try:
                        region.union_rectangle(rect)
                    except AttributeError:
                        row_region = cairo.Region(rect)
                        region.union(row_region)
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

    def get_display_icon_pixbuf(self, pixbuf, has_label):
        """
        Algunos temas GnoMenu usan ButtonIcon como imagen ancha completa.
        Para botones con texto, recortamos solo el icono izquierdo.
        """
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
        icon_pixbuf_raw = self.load_pixbuf(button.button_icon)
        icon_sel_pixbuf_raw = self.load_pixbuf(button.button_icon_sel)

        label_text = self.extract_label_text(button)
        has_label = bool(label_text)

        icon_pixbuf = self.get_display_icon_pixbuf(icon_pixbuf_raw, has_label)
        icon_sel_pixbuf = self.get_display_icon_pixbuf(icon_sel_pixbuf_raw, has_label)

        width = 120
        height = 26

        bg_widget = None
        icon_widget = None

        # Image suele ser hover/selección. Oculto por defecto.
        if bg_pixbuf:
            bg_widget = Gtk.Image.new_from_pixbuf(bg_pixbuf)
            bg_widget.set_no_show_all(True)
            bg_widget.hide()
            container.put(bg_widget, 0, 0)

            width = max(width, bg_pixbuf.get_width())
            height = max(height, bg_pixbuf.get_height())

        # Icono visible siempre.
        if icon_pixbuf:
            icon_widget = Gtk.Image.new_from_pixbuf(icon_pixbuf)

            if has_label:
                container.put(icon_widget, 4, 2)
            else:
                # Botones inferiores tipo apagar/bloquear.
                container.put(icon_widget, 0, 0)

            width = max(width, icon_pixbuf.get_width())
            height = max(height, icon_pixbuf.get_height())

        # Texto visible siempre.
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

        if button.execute_on_hover:
            event.connect("enter-notify-event", self.on_button_hover, button)

        self.fixed.put(event, button.x, button.y)

    def on_button_enter(self, widget, event, button, bg_widget, icon_widget,
                        icon_pixbuf, icon_sel_pixbuf):
        if bg_widget:
            bg_widget.show()

        if icon_widget and icon_sel_pixbuf:
            icon_widget.set_from_pixbuf(icon_sel_pixbuf)

        return False

    def on_button_leave(self, widget, event, button, bg_widget, icon_widget,
                        icon_pixbuf):
        if bg_widget:
            bg_widget.hide()

        if icon_widget and icon_pixbuf:
            icon_widget.set_from_pixbuf(icon_pixbuf)

        return False

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
        self.destroy()

    def on_key_press(self, widget, event):
        if event.keyval == 65307:  # ESC
            self.destroy()

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

    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
