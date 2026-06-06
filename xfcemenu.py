#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import re
import html

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

        self.setup_transparency()

        self.background_pixbuf = self.load_pixbuf(self.theme.background)

        self.connect("draw", self.on_draw)
        self.connect("realize", self.on_realize)

        self.fixed = Gtk.Fixed()
        self.fixed.set_name("xfcemenu-root")

        try:
            self.fixed.set_has_window(False)
        except Exception:
            pass

        self.fixed.set_size_request(theme.width, theme.height)
        self.add(self.fixed)

        # Temporalmente desactivado hasta crear lista real transparente.
        # self.draw_program_list_placeholder()

        self.draw_user_icon()
        self.draw_buttons()
        self.draw_labels()

        self.connect("focus-out-event", self.on_focus_out)
        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", self.on_destroy)

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
        if event.keyval == 65307:
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
