#!/usr/bin/env python3
import os
import subprocess
import shlex


def run_command(command: str):
    """
    Traductor básico de comandos antiguos de GnoMenu a acciones modernas XFCE.
    Primera versión: simple, segura y suficiente para probar temas.
    """

    if not command:
        return

    command = command.strip()

    home = os.path.expanduser("~")

    command_map = {
        "Home": ["xdg-open", home],
        "Documents": ["xdg-open", os.path.join(home, "Documents")],
        "Pictures": ["xdg-open", os.path.join(home, "Pictures")],
        "Music": ["xdg-open", os.path.join(home, "Music")],
        "Videos": ["xdg-open", os.path.join(home, "Videos")],
        "Computer": ["thunar"],
        "Network": ["thunar", "network:///"],
        "Control Panel": ["xfce4-settings-manager"],
        "Network Config": ["nm-connection-editor"],
        "Help": ["exo-open", "--launch", "WebBrowser"],
        "software-center": ["mx-packageinstaller"],
        "gnome-control-center": ["xfce4-settings-manager"],
        "gnome-control-center universal-access": ["xfce4-accessibility-settings"],
        "gnome-session-quit --logout": ["xfce4-session-logout", "--logout"],
        "gnome-session-quit --power-off": ["xfce4-session-logout", "--halt"],
        "xfce4-session-logout --logout": ["xfce4-session-logout", "--logout"],
        "xfce4-session-logout --halt": ["xfce4-session-logout", "--halt"],
        "xfce4-session-logout --reboot": ["xfce4-session-logout", "--reboot"],
    }

    if command == ":ALLAPPS:":
        print("XFCEMenu: :ALLAPPS: todavía no implementado.")
        return

    if command in command_map:
        try:
            subprocess.Popen(command_map[command])
        except FileNotFoundError:
            print(f"XFCEMenu: comando no encontrado: {command_map[command][0]}")
        return

    # Fallback: ejecutar comando literal del tema.
    # Esto ayuda con temas viejos que traen comandos propios.
    try:
        subprocess.Popen(shlex.split(command))
    except Exception as e:
        print(f"XFCEMenu: no se pudo ejecutar '{command}': {e}")