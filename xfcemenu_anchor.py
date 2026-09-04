#!/usr/bin/env python3
"""Compatibility bridge between the XFCE panel launcher (Kesu) and XFCEMenu.

The main renderer stays in xfcemenu.py. This module only consumes optional
launcher geometry arguments, removes them before XFCEMenu parses its own CLI,
and overrides window positioning. Without anchor arguments it uses the real
monitor workarea instead of assuming a 32 px panel.
"""

import argparse
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
        # Set before super(): XFCEMenuWindow.__init__ calls
        # position_near_bottom_left(), which is overridden below.
        self.anchor_x = ANCHOR_ARGS.anchor_x
        self.anchor_y = ANCHOR_ARGS.anchor_y
        self.anchor_width = max(0, int(ANCHOR_ARGS.anchor_width or 0))
        self.anchor_height = max(0, int(ANCHOR_ARGS.anchor_height or 0))
        self.panel_position = ANCHOR_ARGS.panel_position
        super().__init__(*args, **kwargs)

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
