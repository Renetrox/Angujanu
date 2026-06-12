#!/usr/bin/env python3
import os
import shlex
import shutil
import subprocess


def _launch_first(candidates):
    """
    Ejecuta la primera aplicación disponible.
    Cada candidato debe ser una lista: [programa, argumento, ...].
    """
    for command in candidates:
        if not command:
            continue

        executable = command[0]

        if not shutil.which(executable):
            continue

        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as error:
            print(f"XFCEMenu: no se pudo ejecutar {command}: {error}")

    return False


def run_command(command: str):
    """
    Traduce comandos antiguos de GnoMenu a acciones modernas.

    Los comandos internos de navegación, como :ALLAPPS:, se procesan
    dentro de xfcemenu.py y nunca deben ejecutarse como binarios.
    """
    if not command:
        return False

    command = command.strip()
    command_lower = command.lower()
    home = os.path.expanduser("~")

    if command_lower in (
        ":allapps:",
        ":all_apps:",
        "allapps",
        "all apps",
        "all applications",
        ":favorites:",
        "favorites",
        "favourites",
        "favoritos",
    ):
        print(f"XFCEMenu: comando interno recibido por mapper: {command}")
        return False

    if command_lower in (
        "software-center",
        "software center",
        "software manager",
        "package manager",
        "gestor de paquetes",
        "centro de software",
    ):
        launched = _launch_first([
            ["mx-packageinstaller"],
            ["gnome-software"],
            ["ubuntu-software"],
            ["pamac-manager"],
            ["plasma-discover"],
            ["synaptic-pkexec"],
            ["synaptic"],
        ])

        if not launched:
            print("XFCEMenu: no se encontró un gestor de software compatible.")

        return launched

    if command_lower in ("printer", "printers"):
        launched = _launch_first([
            ["system-config-printer"],
            ["gnome-control-center", "printers"],
            ["systemsettings5", "kcm_printer_manager"],
            ["systemsettings", "kcm_printer_manager"],
        ])

        if not launched:
            print("XFCEMenu: no se encontró una herramienta de impresoras.")

        return launched

    command_map = {
        "home": ["xdg-open", home],
        "documents": ["xdg-open", os.path.join(home, "Documents")],
        "pictures": ["xdg-open", os.path.join(home, "Pictures")],
        "music": ["xdg-open", os.path.join(home, "Music")],
        "videos": ["xdg-open", os.path.join(home, "Videos")],
        "computer": ["thunar"],
        "network": ["thunar", "network:///"],
        "control panel": ["xfce4-settings-manager"],
        "network config": ["nm-connection-editor"],
        "help": ["exo-open", "--launch", "WebBrowser"],
        "gnome-control-center": ["xfce4-settings-manager"],
        "gnome-control-center universal-access": ["xfce4-accessibility-settings"],
        "gnome-session-quit --logout": ["xfce4-session-logout", "--logout"],
        "gnome-session-quit --power-off": ["xfce4-session-logout", "--halt"],
        "xfce4-session-logout --logout": ["xfce4-session-logout", "--logout"],
        "xfce4-session-logout --halt": ["xfce4-session-logout", "--halt"],
        "xfce4-session-logout --reboot": ["xfce4-session-logout", "--reboot"],
    }

    if command_lower in command_map:
        mapped = command_map[command_lower]

        try:
            subprocess.Popen(mapped)
            return True
        except FileNotFoundError:
            print(f"XFCEMenu: comando no encontrado: {mapped[0]}")
            return False
        except Exception as error:
            print(f"XFCEMenu: no se pudo ejecutar {mapped}: {error}")
            return False

    try:
        subprocess.Popen(shlex.split(command))
        return True
    except Exception as error:
        print(f"XFCEMenu: no se pudo ejecutar '{command}': {error}")
        return False
