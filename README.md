<img width="1491" height="1055" alt="ChatGPT Image Jun 14, 2026, 12_57_41 PM" src="https://github.com/user-attachments/assets/f02b8a04-bd7a-43c4-8707-1b8c838b565d" />


<img width="821" height="737" alt="Legacy GnoMenu style menu theme preview" src="https://github.com/user-attachments/assets/86bf513d-b1f3-4e50-af07-26003328347a" />

**Angujanú** is a modern XFCE port of the classic **GnoMenu** experience, focused on preserving its vintage theme engine, visual behavior and community-made skins on a modern GTK3 / Python 3 desktop.

The goal is to bring back the skinnable desktop-menu experience of the GNOME 2 era for lightweight Linux desktops, while adapting legacy GnoMenu-style themes to modern XFCE instead of reviving the old GNOME Panel stack.

Angujanú is the public name, installer name and visual identity of the project.

The internal application is still called **XFCEMenu**, and its executable, configuration paths and theme structure currently remain unchanged for compatibility.

XFCEMenu is a working Python 3 / GTK3 / Cairo prototype for XFCE and MX Linux. It can load several legacy-style GnoMenu themes, render the menu window with transparency, show application categories, launch programs, and use a local user installer with a dialog-based configuration menu.

## Why Angujanú?

**Angujanú** is inspired by **anguja**, a Guaraní word for **mouse**.

The name also connects naturally with **XFCE**, a lightweight desktop environment commonly associated with a mouse mascot. Since this project is mainly designed as a classic XFCE panel menu, the mouse became a fitting visual identity.

Angujanú combines three ideas:

* the mouse reference from XFCE
* the Guaraní word *anguja*
* the retro Linux desktop spirit of GnoMenu-style customization

In short:

* **Angujanú** is the public project name, installer name and visual identity.
* **XFCEMenu** is the current internal engine and application name.
* The project keeps the existing `xfcemenu` command, configuration paths and local installation structure for compatibility.

## What is this?

Angujanú is **not** a fork of GnoMenu.

GnoMenu was a Python 2 / GTK2 / GNOME Panel menu from the GNOME 2 era. It allowed users to create highly customized Start Menu skins using XML layouts and PNG assets.

XFCEMenu is a new project built for modern XFCE systems. It aims to reuse the visual idea and part of the legacy theme format of GnoMenu while avoiding old GNOME Panel, Bonobo, gconf and Python 2 dependencies.

Angujanú / XFCEMenu is intended as a small legacy theme renderer and classic Start Menu experiment, not as a replacement for Whisker Menu or the native XFCE menu.

## Project goals

* Create a classic Start Menu for XFCE.
* Support legacy GnoMenu menu themes.
* Support legacy GnoMenu button/orb themes.
* Support legacy GnoMenu sound and icon themes where possible.
* Import old `.tar` and `.tar.gz` theme packages.
* Render XML-based layouts with PNG assets.
* Provide a real application launcher with categories.
* Keep the project lightweight and suitable for XFCE / MX Linux.
* Preserve abandoned GnoMenu visual themes when possible.
* Provide a local user installer without requiring system-wide installation.

## Current status

The project is still experimental, but it is already usable as a personal XFCE panel menu and its GnoMenu compatibility is considerably broader than the original prototype.

Currently working:

* Loads legacy GnoMenu `themedata.xml` menu themes.
* Reads `WindowDimensions` and can derive the menu size from the actual `Background` image, matching original GnoMenu behavior more closely.
* Reads and renders `Background`, `IconSettings`, `ProgramListSettings`, `Button`, `Label` and standalone legacy `Image` elements.
* Supports the original `ImageBack` + `Image` button-layer model for normal and hover/selected states.
* Supports legacy button icon coordinates and size through `ButtonIconX`, `ButtonIconY` and `ButtonIconSize`.
* Supports button `TextAlignment`.
* Reads `Capabilities` including `HasSearch`, `HasIcon` and `HasFadeTransition`.
* Reads `Tab` elements and old `IconX` / `IconY` / `IconSize` aliases used by older themes.
* Applies RGBA transparency, alpha-based window shape and input shape handling.
* Loads programs and categories from the desktop application database.
* Shows a categorized application list with scrolling and launches installed applications.
* Maps old GnoMenu/GNOME commands to modern XFCE equivalents.
* Supports shutdown, logout and session actions through command mapping.
* Supports user avatar rendering and icon preview behavior in the legacy avatar area.
* Supports top and bottom XFCE panels with legacy GnoMenu vertical orientation behavior.
* Flips the main legacy skin and reflects legacy element coordinates for a top panel while keeping text and internal icons upright.
* Can receive the real launcher geometry from the native **Kesu** XFCE panel plugin and open next to the actual button position instead of assuming the left edge of the panel.
* Supports toggle behavior: clicking the launcher opens the menu, clicking again closes it.
* Uses a user configuration file at `~/.config/xfcemenu/config.ini`.
* Includes a dialog-based configuration tool.
* Allows changing menu, button, sound and icon themes from the configuration tool.
* Installs locally under `~/.local/share/xfcemenu`.
* Creates launcher commands under `~/.local/bin`.
* Creates desktop entries for XFCEMenu and XFCEMenu Settings.

Tested with themes such as:

* `Windows 7 Box`
* `Win7forG2`
* `Win2-7Blue`
* `Win2-7Standard-Es`
* `Avio`
* `Win2-7MurrineBlack`
* several classic GnoMenu-style button/orb themes through Kesu

## Not implemented or incomplete yet

* Full compatibility with every GnoMenu theme and every unusual XML variant.
* Selection of multiple `<theme color="...">` variants; the current compatibility layer still follows the first theme block used by the base loader.
* Exact Cairo-era rendering of all `SearchBarSettings` visual properties.
* Full `Tab` text/alignment/selection-color parity with original GnoMenu.
* Full `Label` alignment and top-panel baseline parity with original GnoMenu.
* Complete sound event parity for every legacy theme.
* Complete icon theme parity for every legacy theme.
* Favorites.
* Recent applications.
* Full graphical theme manager.
* Theme export manager.
* Complete GnoMenu XML compatibility.
* In the companion Kesu panel plugin, original GnoMenu `Top="1"` button themes still need the separate transparent top/overlay window used by the old two-window orb implementation.

## Why not use Whisker Menu?

Whisker Menu is a great XFCE menu, but it is not designed to load old GnoMenu themes.

GnoMenu themes are based on XML layout files with absolute coordinates, PNG backgrounds, custom buttons, labels, icons and separate menu/button/icon themes.

Angujanú / XFCEMenu is intended as a small legacy theme renderer and classic Start Menu experiment, not as a replacement for Whisker Menu.

## Directory structure

Current development structure:

```text
XFCEMenu/
├── xfcemenu.py
├── xfcemenu_anchor.py
├── xfcemenu-config.sh
├── xfceMenu.sh
├── legacy_loader.py
├── legacy_compat.py
├── command_mapper.py
├── importer.py
├── install_xfcemenu.sh
├── XFCEmenu.png
├── Settings.png
├── README.md
└── themes/
    ├── Menu/
    ├── Button/
    ├── Sound/
    └── Icon/
```

Example legacy theme layout:

```text
themes/
├── Menu/
│   └── Windows 7 Box/
│       ├── themedata.xml
│       ├── start-menu.png
│       ├── m_button.png
│       └── ...
├── Button/
│   └── Win2-7Orb/
│       ├── themedata.xml
│       ├── start-here.png
│       └── ...
├── Sound/
│   └── Win2-7/
│       └── ...
└── Icon/
    └── Win7_Icons_1.1/
        └── ...
```

## Dependencies

On Debian / MX Linux / XFCE:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-cairo rsync
```

For the dialog-based configuration menu:

```bash
sudo apt install dialog
```

Optional for future features:

```bash
sudo apt install python3-xdg
```

## Installing locally

From the project directory:

```bash
chmod +x install_xfcemenu.sh
./install_xfcemenu.sh
```

The installer copies XFCEMenu to:

```text
~/.local/share/xfcemenu
```

Creates configuration under:

```text
~/.config/xfcemenu/config.ini
```

Creates launcher commands:

```text
~/.local/bin/xfcemenu
~/.local/bin/xfcemenu-config
~/.local/bin/xfcemenu-config-terminal
```

Creates desktop entries:

```text
~/.local/share/applications/xfcemenu.desktop
~/.local/share/applications/xfcemenu-config.desktop
```

After installing, you can run:

```bash
xfcemenu
```

To open the configuration tool:

```bash
xfcemenu-config
```

Or launch it with an automatic terminal wrapper:

```bash
xfcemenu-config-terminal
```

## Panel launcher behavior

The installed `xfcemenu` command works as a toggle launcher.

If the menu is closed, it opens XFCEMenu.

If the menu is already open, it closes the running instance using a PID file:

```text
/tmp/xfcemenu-$USER.pid
```

This makes it suitable for use as an XFCE panel launcher.

When launched by the native Kesu XFCE panel plugin, the compatibility bridge can also receive the launcher's real screen geometry and panel edge. This allows the menu to follow Kesu when the button is moved across the panel.

## Configuration file

XFCEMenu uses:

```text
~/.config/xfcemenu/config.ini
```

Example:

```ini
[theme]
menu_theme = Windows 7 Box
icon_theme = Win7_Icons_1.1
button_theme = Win2-7
sound_theme = Win2-7

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
install_dir = /home/user/.local/share/xfcemenu
base_themes_dir = /home/user/.local/share/xfcemenu/themes
menu_themes_dir = /home/user/.local/share/xfcemenu/themes/Menu
button_themes_dir = /home/user/.local/share/xfcemenu/themes/Button
sound_themes_dir = /home/user/.local/share/xfcemenu/themes/Sound
icon_themes_dir = /home/user/.local/share/xfcemenu/themes/Icon
```

## Configuration menu

XFCEMenu includes a terminal/dialog-based configuration menu.

It can currently:

* Change menu theme.
* Change button theme.
* Change sound theme.
* Change icon theme.
* Enable or disable sounds.
* View the current `config.ini`.
* Edit `config.ini` manually.
* Restore the default configuration.
* Show detected installation paths.
* Launch XFCEMenu for testing.

Run it with:

```bash
xfcemenu-config
```

From a desktop menu entry, the installer uses:

```bash
xfcemenu-config-terminal
```

This wrapper opens a terminal first, because `dialog` needs a terminal environment.

## Importing a legacy theme

Place a GnoMenu theme package in the project directory and run:

```bash
python3 importer.py "160104-Windows 7 Box.tar"
```

The importer detects whether the package is a menu theme or button theme by reading:

```xml
<content type="Menu">
```

or:

```xml
<content type="Button">
```

Imported themes are placed under the proper theme folders, such as:

```text
themes/Menu/
themes/Button/
```

## Running from the development folder

For development, you can run directly:

```bash
python3 xfcemenu.py
```

There is also a development launcher:

```bash
./xfceMenu.sh
```

The development launcher may point to the local project folder and is useful while testing without reinstalling.

For normal use, run the installed command instead:

```bash
xfcemenu
```

## Legacy GnoMenu theme support

The current compatibility layer is intentionally split into three levels so the README does not imply either full parity or less support than the code actually has.

### Compatible now

* `Background`, including dimensions derived from the actual image when available.
* `WindowDimensions`.
* `IconSettings`.
* `ProgramListSettings`.
* `Button`.
  * `ImageBack` as the permanent normal-state background.
  * `Image` as the hover/selected overlay.
  * `ButtonIcon` and `ButtonIconSel`.
  * `ButtonIconX`, `ButtonIconY` and `ButtonIconSize`.
  * `TextAlignment`.
* Standalone legacy `Image` elements.
* `Capabilities.HasSearch`.
* `Capabilities.HasIcon`.
* Basic `Label` rendering and a small safe subset of read-only legacy label commands.
* RGBA transparency.
* Alpha-based shaped menu windows and input shape handling.
* Legacy command mapping to XFCE equivalents.
* User avatar area and legacy icon-preview behavior.
* Legacy top/bottom orientation.
* Real launcher anchoring through Kesu, including horizontal button position.
* Separate Menu / Button / Sound / Icon theme selection.
* Import of legacy theme packages.

### Partially compatible

* `SearchBarSettings`.
  * Position, dimensions and search behavior work.
  * `TextColor`, `BackColor`, `BorderColor` and `RoundAngle` are read by the compatibility layer.
  * The modern GTK entry does not yet reproduce every Cairo visual detail of the original widget.
* `Tab`.
  * Normal/selected assets and tab icons are supported by the modern renderer.
  * Deprecated `IconX`, `IconY` and `IconSize` aliases are accepted.
  * Full `TextAlignment` and `InvertTextColorOnSel` rendering parity is still incomplete.
* `Label`.
  * Markup, position and safe legacy command output are supported.
  * `TextAlignment` is parsed, but exact original anchor/baseline behavior is still being completed.
* `Capabilities.HasFadeTransition` is parsed, but full original fade-transition behavior is not yet reproduced.
* Sound and icon themes work in common cases, but not every legacy event or theme-specific behavior is guaranteed.
* Left/right panel edges can be used for launcher positioning, but legacy menu skins are not rotated 90 degrees.

### Still pending

* Selection and switching of multiple `<theme color="...">` variants.
* Exact original Cairo search rendering.
* Full `Tab` behavior parity.
* Full `Label` alignment/baseline parity.
* Every obscure or malformed GnoMenu XML variation.
* Complete sound event mapping.
* Complete theme export/management tooling.
* Kesu support for GnoMenu button themes with `Top="1"` and their separate `<Top>` overlay window.

## Command mapping

Some old GnoMenu commands were designed for GNOME 2. XFCEMenu maps some of them to modern XFCE equivalents.

Examples:

```text
Home              → xdg-open "$HOME"
Documents         → xdg-open "$HOME/Documents"
Pictures          → xdg-open "$HOME/Pictures"
Music             → xdg-open "$HOME/Music"
Computer          → thunar
Control Panel     → xfce4-settings-manager
Network Config    → nm-connection-editor
Logout            → xfce4-session-logout --logout
Shutdown          → xfce4-session-logout --halt
```

## Design philosophy

Angujanú / XFCEMenu does not try to revive GNOME 2.

It tries to preserve the useful part of GnoMenu:

* the XML theme format
* the skinnable Start Menu idea
* the separate menu, button, sound and icon themes
* the huge library of abandoned community-made skins
* the classic desktop customization feeling

The code is new. The inspiration is old.

## Roadmap

### 0.1 alpha

* Load a legacy GnoMenu theme.
* Draw the background.
* Draw buttons and labels.
* Run basic XFCE commands.
* Handle transparency and window shape.

### 0.2

* Add real application list.
* Support application categories.
* Add scrolling program list.
* Improve command mapping.

### 0.3

* Add local user installer.
* Add toggle panel launcher behavior.
* Add desktop entries.
* Add dialog-based configuration menu.

### 0.4

* Improve menu, button, sound and icon theme selection.
* Improve theme path handling.
* Improve legacy theme import behavior.
* Improve visual compatibility with Windows 7 style themes.

### 0.5

* Add search bar support.
* Add favorites.
* Add recent applications.
* Improve hover states.

### Current compatibility work

* Continue auditing original GnoMenu widget semantics against the GTK3 renderer.
* Finish exact `Label` alignment/baseline behavior.
* Finish `Tab` alignment and selected-text behavior.
* Improve search visual parity without depending on the old GTK2/Cairo widget implementation.
* Add legacy color-variant selection.
* Continue integration with Kesu for native XFCE panel geometry and vintage button-theme behavior.

### Future

* Favorites.
* Recent applications.
* More complete sound support.
* Theme export/import manager.
* More complete GnoMenu compatibility.

## Current panel behavior

With the compatibility bridge, Angujanú now supports both **bottom and top horizontal XFCE panels** using the original GnoMenu-style vertical orientation behavior.

For a bottom panel, the legacy theme is rendered in its normal orientation. For a top panel, the main background is vertically flipped and the outer Y coordinates of the legacy menu regions, buttons, tabs, labels and standalone images are reflected. Internal text and icons remain upright.

When Angujanú is launched from the native **Kesu** XFCE panel plugin, Kesu passes the real launcher coordinates, size and panel edge. The menu therefore follows the button horizontally instead of always opening at the left side of the screen. The final position is clamped to the monitor work area so the menu does not run off-screen.

Left and right panel edges can be used for placement, but the legacy skin itself is not rotated 90 degrees. Full vertical-panel skin rotation is not currently a compatibility goal because it was not equivalent to GnoMenu's original top/bottom theme-orientation mechanism.

## License

This project is intended to be released as free software.

Legacy GnoMenu was released under the GNU General Public License. Angujanú / XFCEMenu should respect the licenses of any original GnoMenu code, themes or assets used for reference or testing.

Themes may have their own licenses. Always check the original theme package before redistribution.

The Angujanú branding, logo and mascot are original project assets, unless otherwise stated.

## Credits

Inspired by:

* GnoMenu
* The old GNOME 2 / MATE / XFCE classic menu era
* Community themes from GNOME-Look
* Windows XP / Vista / 7 style menu layouts
* Lightweight Linux desktop customization
* XFCE and its mouse identity
* Paraguayan / Guaraní language inspiration through the word *anguja*

Angujanú / XFCEMenu is an experimental project by Renetrox.
