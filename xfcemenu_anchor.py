#!/usr/bin/env python3
"""Compatibility bridge between the XFCE panel launcher (Kesu) and XFCEMenu.

The main renderer stays in xfcemenu.py. This module consumes optional launcher
geometry arguments, applies the legacy GnoMenu top-panel orientation when
needed, and overrides window positioning. Without anchor arguments it uses the
real monitor workarea instead of assuming a 32 px panel.
"""

import argparse
import copy
import os
import sys

import xfcemenu as core


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

        # GnoMenu used the same XML for top and bottom panels. For a top panel
        # it vertically flipped the menu skin and reflected the outer Y
        # coordinates of theme objects. Work on a copy so the parsed theme
        # remains untouched for normal/bottom launches.
        if self.panel_position == "top":
            args, kwargs = self._prepare_top_theme_args(args, kwargs)

        super().__init__(*args, **kwargs)

    def _prepare_top_theme_args(self, args, kwargs):
        theme = args[0] if args else kwargs.get("theme")

        if theme is None:
            return args, kwargs

        oriented_theme = copy.deepcopy(theme)
        self._orient_theme_for_top(oriented_theme)

        if args:
            args = (oriented_theme,) + tuple(args[1:])
        else:
            kwargs = dict(kwargs)
            kwargs["theme"] = oriented_theme

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

        # Preserve the original coordinate for compatibility heuristics that
        # describe the XML semantics rather than the rendered position.
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

        # Fixed-size outer regions.
        for block_name in ("program_list", "search_bar", "icon_settings"):
            block = getattr(theme, block_name, None)
            if block is None:
                continue

            block_h = int(getattr(block, "height", 0) or 0)
            self._reflect_outer_y(theme_height, block, block_h)

        # Menu buttons: GnoMenu reflected ButtonY using the source image height.
        for button in getattr(theme, "buttons", []) or []:
            image_h = self._theme_image_height(
                theme,
                getattr(button, "image", ""),
                26,
            )
            self._reflect_outer_y(theme_height, button, image_h)

        # Tabs follow the same rule. If Image is missing, ImageSel is a useful
        # legacy fallback because XFCEMenu can render either.
        for tab in getattr(theme, "tabs", []) or []:
            image_name = getattr(tab, "image", "") or getattr(tab, "image_sel", "")
            image_h = self._theme_image_height(theme, image_name, 96)
            self._reflect_outer_y(theme_height, tab, image_h)

        # GnoMenu treated LabelY as an anchor point, not a sized rectangle.
        for label in getattr(theme, "labels", []) or []:
            if not hasattr(label, "y"):
                continue
            try:
                original_y = int(getattr(label, "y", 0) or 0)
            except Exception:
                continue
            setattr(label, "_angujanu_original_y", original_y)
            label.y = int(theme_height - original_y)

        # Future compatibility: if LegacyImage objects are added to the loader,
        # orient them automatically with the same legacy rule.
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

        # Only the main menu skin is flipped here. Buttons, tab icons, labels
        # and GTK content stay upright; their outer Y coordinates were already
        # reflected above.
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

    def extract_label_text(self, button):
        """Keep legacy icon-only heuristics based on the XML's original Y."""
        original_y = getattr(button, "_angujanu_original_y", None)

        if self.panel_position != "top" or original_y is None:
            return super().extract_label_text(button)

        rendered_y = getattr(button, "y", 0)

        try:
            button.y = original_y
            return super().extract_label_text(button)
        finally:
            button.y = rendered_y

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

        # GTK3 fallback for older bindings.
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

        # Use the launcher centre to choose the correct monitor in multi-monitor
        # setups. The returned workarea also keeps the menu away from panel struts.
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
        else:  # bottom
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
            # Last-resort compatibility fallback from the old implementation.
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
