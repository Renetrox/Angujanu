# XFCEMenu

<img width="821" height="737" alt="93057-1-1366698742" src="https://github.com/user-attachments/assets/86bf513d-b1f3-4e50-af07-26003328347a" />

**XFCEMenu** is an experimental classic Start Menu for XFCE, inspired by the old **GnoMenu** project.

The goal is to bring back a skinnable desktop menu experience for lightweight Linux desktops, with special focus on reading and adapting legacy GnoMenu themes.

XFCEMenu is currently a working Python 3 / GTK3 / Cairo prototype for XFCE and MX Linux. It can load several legacy-style GnoMenu themes, render the menu window with transparency, show application categories, launch programs, and use a local user installer with a dialog-based configuration menu.

## What is this?

XFCEMenu is **not** a fork of GnoMenu.

GnoMenu was a Python 2 / GTK2 / GNOME Panel menu from the GNOME 2 era. It allowed users to create highly customized Start Menu skins using XML layouts and PNG assets.

XFCEMenu is a new project built for modern XFCE systems. It aims to reuse the visual idea and part of the legacy theme format of GnoMenu while avoiding old GNOME Panel, Bonobo, gconf and Python 2 dependencies.

## Project goals

* Create a classic Start Menu for XFCE.
* Support legacy GnoMenu menu themes.
* Support legacy GnoMenu button/orb themes.
* Support legacy GnoMenu sound and icon themes where possible.
* Import old `.tar`, `.tar.gz` theme packages.
* Render XML-based layouts with PNG assets.
* Provide a real application launcher with categories.
* Keep the project lightweight and suitable for XFCE / MX Linux.
* Preserve abandoned GnoMenu visual themes when possible.
* Provide a local user installer without requiring system-wide installation.

## Current status

This project is currently experimental, but already usable as a personal XFCE panel menu.

Working prototype features:

* Loads legacy GnoMenu `themedata.xml` menu themes.
* Reads `WindowDimensions`.
* Reads `Background`.
* Reads basic `Button` elements.
* Reads basic `Label` elements.
* Draws the menu background using Cairo.
* Applies RGBA transparency and shape handling.
* Loads programs and categories from the desktop application database.
* Shows a categorized application list.
* Supports scrolling through the program list.
* Launches installed applications.
* Maps some old GnoMenu/GNOME commands to XFCE equivalents.
* Supports basic shutdown, logout and session commands through command mapping.
* Can work as an XFCE panel launcher.
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
* `WinOrb` button theme package, partially analyzed

## Not implemented or incomplete yet

* Full compatibility with all GnoMenu themes.
* Complete button/orb behavior for all legacy states.
* Complete sound theme behavior.
* Complete icon theme behavior.
* Search bar functionality.
* Favorites.
* Recent applications.
* Avatar / user image preview behavior.
* Large icon preview on hover.
* Native XFCE panel plugin.
* Full graphical theme manager.
* Export/import manager for themes.
* Complete GnoMenu XML compatibility.

## Why not use Whisker Menu?

Whisker Menu is a great XFCE menu, but it is not designed to load old GnoMenu themes.

GnoMenu themes are based on XML layout files with absolute coordinates, PNG backgrounds, custom buttons, labels, icons and separate menu/button/icon themes.

XFCEMenu is intended as a small legacy theme renderer and classic Start Menu experiment, not as a replacement for Whisker Menu.

## Directory structure

Current development structure:

```text
XFCEMenu/
├── xfcemenu.py
├── xfcemenu-config.sh
├── xfceMenu.sh
├── legacy_loader.py
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

XFCEMenu currently supports a subset of the GnoMenu XML format.

Supported or partially supported:

* `Background`
* `WindowDimensions`
* `IconSettings`
* `ProgramListSettings`
* `SearchBarSettings`, partial / placeholder behavior
* `Button`
* `Label`
* basic command execution
* basic image loading from the theme folder
* RGBA transparency
* shaped menu windows
* legacy command mapping

Planned or incomplete:

* `Capabilities`
* `Image`
* `Tab`
* complete search behavior
* complete icon preview behavior
* complete sound event mapping
* complete button/orb state integration

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

XFCEMenu does not try to revive GNOME 2.

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

### Future

* Avatar / user preview area.
* Large app icon preview on hover.
* More complete button/orb support.
* More complete sound support.
* Theme export/import manager.
* Possible native xfce4-panel plugin.
* More complete GnoMenu compatibility.

## License

This project is intended to be released as free software.

Legacy GnoMenu was released under the GNU General Public License. XFCEMenu should respect the licenses of any original GnoMenu code, themes or assets used for reference or testing.

Themes may have their own licenses. Always check the original theme package before redistribution.

## Credits

Inspired by:

* GnoMenu
* The old GNOME 2 / MATE / XFCE classic menu era
* Community themes from GNOME-Look
* Windows XP / Vista / 7 style menu layouts
* Lightweight Linux desktop customization

XFCEMenu is an experimental project by Renetrox.
