#!/usr/bin/env python3
"""Compatibility bridge between the XFCE panel launcher (Kesu) and XFCEMenu.

This module keeps the main renderer in xfcemenu.py, adds runtime compatibility
for original GnoMenu XML fields, applies top-panel orientation, and positions
the menu from Kesu's real launcher geometry.
"""

import argparse
import copy
import getpass
import os
import re
import shlex
import shutil
import subprocess
import sys

import xfcemenu as core
from legacy_compat import enrich_theme


def parse_anchor_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--anchor-x", type=int, default=None)
    parser.add_argument("--anchor-y", type=int, default=None)
    parser.add_argument("--anchor-width", type=int, default=0)
    parser.add_argument("--anchor-height", type=int, default=0)
    parser.add_argument(
        "--panel-position",
        choices=("top", "bottom", "left", "right"),
        default="bottom",
    )
    return parser.parse_known_args(argv)


ANCHOR_ARGS, REMAINING_ARGS = parse_anchor_args(sys.argv[1:])
# Keep XFCEMenu's existing command-line interface untouched. Unknown/regular
# arguments (--theme, --icon-theme, etc.) continue to core.main().
sys.argv = [sys.argv[0]] + REMAINING_ARGS


class AnchoredXFCEMenuWindow(core.XFCEMenuWindow):
    def __init__(self, *args, **kwargs):
        # Set before super(): XFCEMenuWindow.__init__ loads the theme, creates
        # all widgets and calls position_near_bottom_left().
        self.anchor_x = ANCHOR_ARGS.anchor_x
        self.anchor_y = ANCHOR_ARGS.anchor_y
        self.anchor_width = max(0, int(ANCHOR_ARGS.anchor_width or 0))
        self.anchor_height = max(0, int(ANCHOR_ARGS.anchor_height or 0))
        self.panel_position = ANCHOR_ARGS.panel_position
        self._legacy_images_drawn = False

        args, kwargs = self._prepare_runtime_theme_args(args, kwargs)
        super().__init__(*args, **kwargs)

    def _prepare_runtime_theme_args(self, args, kwargs):
        theme = args[0] if args else kwargs.get("theme")

        if theme is None:
            return args, kwargs

        # Always work on a copy: compatibility enrichment and orientation must
        # never mutate the base object kept by core.main().
        runtime_theme = copy.deepcopy(theme)
        enrich_theme(runtime_theme)

        if self.panel_position == "top":
            self._orient_theme_for_top(runtime_theme)

        if args:
            args = (runtime_theme,) + tuple(args[1:])
        else:
            kwargs = dict(kwargs)
            kwargs["theme"] = runtime_theme

        return args, kwargs

    def _theme_image_height(self, theme, filename, fallback):
        """Return a legacy menu image height without changing the renderer."""
        filename = str(filename or "").strip()

        if not filename:
            return max(1, int(fallback))

        candidates = []

        if os.path.isabs(filename):
            candidates.append(filename)
        else:
            theme_dir = getattr(theme, "theme_dir", "") or ""
            if theme_dir:
                candidates.append(os.path.join(theme_dir, filename))

        for path in candidates:
            if not os.path.isfile(path):
                continue

            try:
                pixbuf = core.GdkPixbuf.Pixbuf.new_from_file(path)
                image_h = int(pixbuf.get_height())
                if image_h > 0:
                    return image_h
            except Exception:
                pass

        return max(1, int(fallback))

    def _reflect_outer_y(self, theme_height, obj, height):
        if obj is None or not hasattr(obj, "y"):
            return

        try:
            original_y = int(getattr(obj, "y", 0) or 0)
            item_h = max(0, int(height or 0))
        except Exception:
            return

        setattr(obj, "_angujanu_original_y", original_y)
        obj.y = int(theme_height - original_y - item_h)

    def _orient_theme_for_top(self, theme):
        """Apply the vertical orientation transform used by legacy GnoMenu."""
        try:
            theme_height = int(getattr(theme, "height", 0) or 0)
        except Exception:
            theme_height = 0

        if theme_height <= 0:
            return

        for block_name in ("program_list", "search_bar", "icon_settings"):
            block = getattr(theme, block_name, None)
            if block is None:
                continue

            block_h = int(getattr(block, "height", 0) or 0)
            self._reflect_outer_y(theme_height, block, block_h)

        # The original loader used Image height for ButtonY reflection.
        for button in getattr(theme, "buttons", []) or []:
            image_h = self._theme_image_height(
                theme,
                getattr(button, "image", "") or getattr(button, "image_back", ""),
                26,
            )
            self._reflect_outer_y(theme_height, button, image_h)

        for tab in getattr(theme, "tabs", []) or []:
            image_name = getattr(tab, "image", "") or getattr(tab, "image_sel", "")
            image_h = self._theme_image_height(theme, image_name, 96)
            self._reflect_outer_y(theme_height, tab, image_h)

        # Labels use Y as an anchor point in the old engine.
        for label in getattr(theme, "labels", []) or []:
            if not hasattr(label, "y"):
                continue
            try:
                original_y = int(getattr(label, "y", 0) or 0)
            except Exception:
                continue
            setattr(label, "_angujanu_original_y", original_y)
            label.y = int(theme_height - original_y)

        for image_def in getattr(theme, "images", []) or []:
            image_name = getattr(image_def, "image", "")
            image_h = self._theme_image_height(theme, image_name, 1)
            self._reflect_outer_y(theme_height, image_def, image_h)

        print(
            "XFCEMenu: orientación legacy GnoMenu aplicada "
            f"para panel superior ({theme_height}px)"
        )

    def load_pixbuf(self, filename):
        pixbuf = super().load_pixbuf(filename)

        # Flip only the main menu skin. Buttons, icons and text stay upright.
        if (
            pixbuf is not None
            and self.panel_position == "top"
            and filename
            and filename == getattr(self.theme, "background", "")
        ):
            try:
                return pixbuf.flip(False)
            except Exception as error:
                print(f"XFCEMenu: no se pudo invertir el fondo para panel superior: {error}")

        return pixbuf

    # ------------------------------------------------------------------
    # Legacy menu XML rendering missing from the modern core
    # ------------------------------------------------------------------

    def draw_program_widgets(self):
        # GnoMenu created MenuImage objects before interactive menu controls.
        if not self._legacy_images_drawn:
            self.draw_legacy_images()
            self._legacy_images_drawn = True

        return super().draw_program_widgets()

    def draw_legacy_images(self):
        for image_def in getattr(self.theme, "images", []) or []:
            filename = getattr(image_def, "image", "") or ""
            pixbuf = self.load_pixbuf(filename)

            if not pixbuf:
                continue

            image = core.Gtk.Image.new_from_pixbuf(pixbuf)
            x = int(getattr(image_def, "x", 0) or 0)
            y = int(getattr(image_def, "y", 0) or 0)
            self.fixed.put(image, x, y)

        if getattr(self.theme, "images", None):
            print(
                "XFCEMenu: imágenes legacy dibujadas: "
                f"{len(getattr(self.theme, 'images', []) or [])}"
            )

    def _scale_explicit_button_icon(self, pixbuf, size):
        if not pixbuf:
            return None

        try:
            size = int(size or 0)
        except Exception:
            size = 0

        if size <= 0:
            return pixbuf

        try:
            return pixbuf.scale_simple(
                size,
                size,
                core.GdkPixbuf.InterpType.BILINEAR,
            )
        except Exception:
            return pixbuf

    def draw_button(self, button):
        """Render ImageBack + Image using the original GnoMenu layer model."""
        if button.name == ":SEPARATOR:":
            pixbuf = self.load_pixbuf(
                getattr(button, "image", "") or getattr(button, "image_back", "")
            )
            if pixbuf:
                image = core.Gtk.Image.new_from_pixbuf(pixbuf)
                self.fixed.put(image, button.x, button.y)
            return

        event = core.Gtk.EventBox()
        event.set_visible_window(False)

        container = core.Gtk.Fixed()
        try:
            container.set_has_window(False)
        except Exception:
            pass

        # Original MenuButton:
        #   ImageBack -> permanent background
        #   Image     -> hover/selected overlay, cleared in normal state
        normal_pixbuf = self.load_pixbuf(getattr(button, "image_back", ""))
        hover_pixbuf = self.load_pixbuf(getattr(button, "image", ""))

        label_text = self.extract_label_text(button)
        has_label = bool(label_text)

        width = 1
        height = 1
        normal_widget = None
        hover_widget = None
        icon_widget = None

        if normal_pixbuf:
            normal_widget = core.Gtk.Image.new_from_pixbuf(normal_pixbuf)
            container.put(normal_widget, 0, 0)
            width = max(width, normal_pixbuf.get_width())
            height = max(height, normal_pixbuf.get_height())

        if hover_pixbuf:
            hover_widget = core.Gtk.Image.new_from_pixbuf(hover_pixbuf)
            hover_widget.set_no_show_all(True)
            hover_widget.hide()
            container.put(hover_widget, 0, 0)
            width = max(width, hover_pixbuf.get_width())
            height = max(height, hover_pixbuf.get_height())

        icon_pixbuf = None
        icon_sel_pixbuf = None

        if getattr(button, "button_icon", ""):
            icon_pixbuf = self.load_pixbuf(button.button_icon)

        if getattr(button, "button_icon_sel", ""):
            icon_sel_pixbuf = self.load_pixbuf(button.button_icon_sel)

        explicit_icon_size = int(getattr(button, "button_icon_size", 0) or 0)
        icon_pixbuf = self._scale_explicit_button_icon(icon_pixbuf, explicit_icon_size)

        if not icon_sel_pixbuf:
            icon_sel_pixbuf = icon_pixbuf
        else:
            icon_sel_pixbuf = self._scale_explicit_button_icon(
                icon_sel_pixbuf,
                explicit_icon_size,
            )

        icon_x = int(getattr(button, "button_icon_x", 0) or 0)
        icon_y = int(getattr(button, "button_icon_y", 0) or 0)

        if icon_pixbuf:
            icon_widget = core.Gtk.Image.new_from_pixbuf(icon_pixbuf)
            container.put(icon_widget, icon_x, icon_y)
            width = max(width, icon_x + icon_pixbuf.get_width())
            height = max(height, icon_y + icon_pixbuf.get_height())

        # Keep a practical minimum when a theme deliberately uses only text.
        width = max(width, 120 if has_label else 1)
        height = max(height, 26 if has_label else 1)

        if label_text:
            label = core.Gtk.Label()
            label.set_use_markup(True)

            forced_color = self.readable_text_color_for_area(
                button.x + button.text_x,
                button.y + button.text_y,
                max(10, width - button.text_x - 4),
                height,
            )

            self.safe_set_markup_or_text(
                label,
                button.markup,
                label_text,
                forced_color=forced_color,
                legacy_text_correction=True,
            )

            alignment = int(getattr(button, "text_alignment", 0) or 0)
            if alignment == 1:
                label.set_xalign(0.5)
            elif alignment >= 2:
                label.set_xalign(1.0)
            else:
                label.set_xalign(0.0)

            label.set_yalign(0.5)

            text_x = int(button.text_x)
            text_y = int(button.text_y + core.LEGACY_BUTTON_TEXT_BASELINE_OFFSET_Y)

            # Old GnoMenu used width - TextX*2 - 2.
            text_w = max(10, int(width - (text_x * 2) - 2))
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
            hover_widget,
            icon_widget,
            icon_pixbuf,
            icon_sel_pixbuf,
        )
        event.connect(
            "leave-notify-event",
            self.on_button_leave,
            button,
            hover_widget,
            icon_widget,
            icon_pixbuf,
        )

        self.fixed.put(event, int(button.x), int(button.y))

    def extract_label_text(self, button):
        """Keep icon-only heuristics based on the XML's original Y."""
        original_y = getattr(button, "_angujanu_original_y", None)

        if self.panel_position != "top" or original_y is None:
            return super().extract_label_text(button)

        rendered_y = getattr(button, "y", 0)

        try:
            button.y = original_y
            return super().extract_label_text(button)
        finally:
            button.y = rendered_y

    def run_label_command(self, command):
        """Run the small read-only command subset used by original GnoMenu labels."""
        command = str(command or "").strip()
        if not command:
            return ""

        if command == "whoami":
            return getpass.getuser()

        # Original documentation/themes use:
        # /sbin/ip route | grep 'src ' | cut -d c -f3
        # Reproduce the intent without invoking a shell pipeline.
        if "ip route" in command and "src" in command:
            ip_binary = shutil.which("ip")
            if not ip_binary and os.path.isfile("/sbin/ip"):
                ip_binary = "/sbin/ip"

            if ip_binary:
                try:
                    output = subprocess.check_output(
                        [ip_binary, "route"],
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=1,
                    )
                    match = re.search(r"\bsrc\s+(\S+)", output)
                    return match.group(1) if match else ""
                except Exception:
                    return ""

        expanded = os.path.expandvars(command)

        try:
            argv = shlex.split(expanded)
        except Exception:
            return ""

        if not argv:
            return ""

        executable = os.path.basename(argv[0])
        allowed = {
            "whoami",
            "hostname",
            "uname",
            "date",
            "uptime",
            "lsb_release",
        }

        if executable not in allowed:
            print(f"XFCEMenu: Label Command bloqueado por compat segura: {command}")
            return ""

        argv = [os.path.expanduser(value) for value in argv]

        try:
            output = subprocess.check_output(
                argv,
                shell=False,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
            )
            return output.strip()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Kesu launcher geometry
    # ------------------------------------------------------------------

    def has_launcher_anchor(self):
        return self.anchor_x is not None and self.anchor_y is not None

    def get_monitor_workarea_for_point(self, point_x=None, point_y=None):
        """Return the workarea of the monitor containing the launcher."""
        try:
            display = core.Gdk.Display.get_default()
            monitor = None

            if display is not None and point_x is not None and point_y is not None:
                try:
                    monitor = display.get_monitor_at_point(int(point_x), int(point_y))
                except Exception:
                    monitor = None

            if display is not None and monitor is None:
                try:
                    monitor = display.get_primary_monitor()
                except Exception:
                    monitor = None

            if display is not None and monitor is None:
                try:
                    monitor = display.get_monitor(0)
                except Exception:
                    monitor = None

            if monitor is not None:
                try:
                    return monitor.get_workarea()
                except Exception:
                    return monitor.get_geometry()
        except Exception:
            pass

        try:
            screen = self.get_screen()

            if point_x is not None and point_y is not None:
                monitor_index = screen.get_monitor_at_point(int(point_x), int(point_y))
            else:
                monitor_index = screen.get_primary_monitor()

            try:
                return screen.get_monitor_workarea(monitor_index)
            except Exception:
                return screen.get_monitor_geometry(monitor_index)
        except Exception:
            return None

    def position_from_launcher_anchor(self):
        if not self.has_launcher_anchor():
            return False

        anchor_x = int(self.anchor_x)
        anchor_y = int(self.anchor_y)
        anchor_w = int(self.anchor_width)
        anchor_h = int(self.anchor_height)
        edge = self.panel_position

        point_x = anchor_x + max(0, anchor_w // 2)
        point_y = anchor_y + max(0, anchor_h // 2)
        workarea = self.get_monitor_workarea_for_point(point_x, point_y)

        menu_w = int(self.theme.width)
        menu_h = int(self.theme.height)

        if edge == "top":
            x = anchor_x
            y = anchor_y + anchor_h
        elif edge == "left":
            x = anchor_x + anchor_w
            y = anchor_y
        elif edge == "right":
            x = anchor_x - menu_w
            y = anchor_y
        else:
            x = anchor_x
            y = anchor_y - menu_h

        if workarea is not None:
            x, y = self.clamp_menu_position_to_monitor(x, y, workarea)

        self.move(int(x), int(y))
        print(
            "XFCEMenu: anclaje Kesu "
            f"{edge} launcher={anchor_x},{anchor_y} "
            f"{anchor_w}x{anchor_h} -> menu={int(x)},{int(y)}"
        )
        return True

    def position_near_bottom_left(self):
        """Use Kesu geometry when available, otherwise the monitor workarea."""
        if self.position_from_launcher_anchor():
            return False

        workarea = self.get_monitor_workarea_for_point()

        if workarea is None:
            return super().position_near_bottom_left()

        x = int(workarea.x)
        y = int(workarea.y + workarea.height - self.theme.height)
        x, y = self.clamp_menu_position_to_monitor(x, y, workarea)
        self.move(x, y)
        print(f"XFCEMenu: posición fallback por workarea -> {x},{y}")
        return False


# main() resolves this symbol when it creates the window, so replacing it here
# keeps the renderer and the rest of its CLI unchanged.
core.XFCEMenuWindow = AnchoredXFCEMenuWindow


if __name__ == "__main__":
    sys.exit(core.main())
