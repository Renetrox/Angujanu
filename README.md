# XFCEMenu
<img width="821" height="737" alt="93057-1-1366698742" src="https://github.com/user-attachments/assets/86bf513d-b1f3-4e50-af07-26003328347a" />

**XFCEMenu** is an experimental classic Start Menu for XFCE, inspired by the old **GnoMenu** project.

The goal is to bring back a skinnable desktop menu experience for lightweight Linux desktops, with special focus on reading and adapting legacy GnoMenu themes.

## What is this?

XFCEMenu is not a fork of GnoMenu.

GnoMenu was a Python 2 / GTK2 / GNOME Panel menu from the GNOME 2 era. It allowed users to create highly customized Start Menu skins using XML layouts and PNG assets.

XFCEMenu is a new project built for modern XFCE systems. It aims to reuse the visual idea and theme format of GnoMenu while avoiding old GNOME Panel, Bonobo, gconf and Python 2 dependencies.

## Project goals

* Create a classic Start Menu for XFCE.
* Support legacy GnoMenu menu themes.
* Support legacy GnoMenu button/orb themes.
* Import old `.tar`, `.tar.gz` theme packages.
* Render XML-based layouts with PNG assets.
* Keep the project lightweight and suitable for XFCE.
* Preserve abandoned GnoMenu visual themes when possible.

## Current status

This project is currently in an early experimental stage.

Working prototype features:

* Loads legacy GnoMenu `themedata.xml` menu themes.
* Reads `WindowDimensions`.
* Reads `Background`.
* Reads basic `Button` elements.
* Reads basic `Label` elements.
* Draws the menu background using Cairo.
* Applies RGBA transparency and shape handling.
* Maps some old GnoMenu/GNOME commands to XFCE equivalents.
* Can import basic legacy GnoMenu `.tar` theme packages.

Tested with:

* `Windows 7 Box`
* `Win7forG2`
* `WinOrb` button theme package, partially analyzed

## Not implemented yet

* Real application list.
* Search bar functionality.
* Favorites.
* Recent applications.
* Avatar / user image preview behavior.
* Large icon preview on hover.
* Full button/orb integration.
* Sound themes.
* Icon themes.
* Native XFCE panel plugin.
* Theme selector GUI.
* Complete compatibility with all GnoMenu themes.

## Why not use Whisker Menu?

Whisker Menu is a great XFCE menu, but it is not designed to load old GnoMenu themes.

GnoMenu themes are based on XML layout files with absolute coordinates, PNG backgrounds, custom buttons, labels, icons and separate menu/button/icon themes.

XFCEMenu is intended as a small legacy theme renderer and Start Menu experiment, not as a replacement for Whisker Menu.

## Directory structure

Current development structure:

```text
/home/Reneto/XFCEMenu/
├── xfcemenu.py
├── legacy_loader.py
├── command_mapper.py
├── importer.py
├── README.md
└── themes/
    ├── menus/
    └── buttons/
```

Example theme layout:

```text
themes/
├── menus/
│   └── Windows 7 Box/
│       ├── themedata.xml
│       ├── start-menu.png
│       ├── m_button.png
│       └── ...
└── buttons/
    └── WinOrb/
        ├── themedata.xml
        ├── start-here.png
        ├── start-here-glow.png
        └── start-here-depressed.png
```

## Dependencies

On Debian / MX Linux / XFCE:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-cairo
```

Optional for future features:

```bash
sudo apt install python3-xdg
```

## Importing a legacy theme

Place a GnoMenu theme package in the project directory and run:

```bash
cd /home/Reneto/XFCEMenu
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

Imported themes are placed under:

```text
themes/menus/
themes/buttons/
```

## Running XFCEMenu

Example:

```bash
cd /home/Reneto/XFCEMenu
python3 xfcemenu.py --theme "Windows 7 Box"
```

Another example:

```bash
python3 xfcemenu.py --theme "Win7forG2"
```

## Legacy GnoMenu theme support

XFCEMenu currently supports a small subset of the GnoMenu XML format:

Supported:

* `Background`
* `WindowDimensions`
* `ProgramListSettings`, placeholder only
* `Button`
* `Label`
* basic command execution
* basic image loading from the theme folder

Planned:

* `IconSettings`
* `SearchBarSettings`
* `Capabilities`
* `Image`
* `Tab`
* application lists
* icon themes
* button themes
* sounds

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
* the separate menu and button themes
* the huge library of abandoned community-made skins

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
* Support “All Programs”.
* Add transparent program list area.
* Improve hover states.

### 0.3

* Add search bar support.
* Add favorites.
* Add recent applications.

### 0.4

* Add avatar / icon preview area.
* Show large app icon on hover, similar to Windows 7 / GnoMenu behavior.

### 0.5

* Add button/orb theme support.
* Support normal, hover and pressed button states.

### Future

* XFCE panel launcher.
* Possible native xfce4-panel plugin.
* Theme selector GUI.
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
