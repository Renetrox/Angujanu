#!/usr/bin/env python3
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LegacyButton:
    name: str = ""
    markup: str = ""
    text_x: int = 0
    text_y: int = 0
    image: str = ""
    button_icon: str = ""
    button_icon_sel: str = ""
    x: int = 0
    y: int = 0
    submenu: int = 0
    command: str = ""
    close_menu: int = 1
    execute_on_hover: int = 0


@dataclass
class LegacyLabel:
    name: str = ""
    markup: str = ""
    x: int = 0
    y: int = 0
    command: str = ""


@dataclass
class ProgramListSettings:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    only_recent: int = 0
    only_favs: int = 0


@dataclass
class LegacyMenuTheme:
    name: str = "Unknown"
    author: str = ""
    theme_dir: str = ""
    width: int = 380
    height: int = 497
    background: str = ""
    program_list: Optional[ProgramListSettings] = None
    buttons: List[LegacyButton] = field(default_factory=list)
    labels: List[LegacyLabel] = field(default_factory=list)


def _int_attr(node, name: str, default: int = 0) -> int:
    try:
        return int(node.attrib.get(name, default))
    except ValueError:
        return default


def _str_attr(node, name: str, default: str = "") -> str:
    return node.attrib.get(name, default)


def find_theme_xml(theme_dir: str) -> Optional[str]:
    """
    Busca el XML principal del tema.
    GnoMenu normalmente usa themedata.xml.
    """
    preferred = [
        "themedata.xml",
        "theme.xml",
        "menu.xml",
        "button.xml",
    ]

    for filename in preferred:
        path = os.path.join(theme_dir, filename)
        if os.path.isfile(path):
            return path

    for filename in os.listdir(theme_dir):
        if filename.lower().endswith(".xml"):
            return os.path.join(theme_dir, filename)

    return None


def load_menu_theme(theme_dir: str) -> LegacyMenuTheme:
    xml_path = find_theme_xml(theme_dir)

    if not xml_path:
        raise FileNotFoundError(f"No se encontró XML de tema en: {theme_dir}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    content_type = root.attrib.get("type", "")

    if content_type.lower() != "menu":
        raise ValueError(f"El tema no es de tipo Menu: {content_type}")

    theme_node = root.find("theme")

    if theme_node is None:
        raise ValueError("XML inválido: no contiene <theme>")

    menu = LegacyMenuTheme()
    menu.theme_dir = theme_dir

    content_data = theme_node.find("ContentData")
    if content_data is not None:
        menu.name = _str_attr(content_data, "Name", os.path.basename(theme_dir))
        menu.author = _str_attr(content_data, "Author", "")

    background = theme_node.find("Background")
    if background is not None:
        menu.background = _str_attr(background, "Image", "")

    dimensions = theme_node.find("WindowDimensions")
    if dimensions is not None:
        menu.width = _int_attr(dimensions, "Width", 380)
        menu.height = _int_attr(dimensions, "Height", 497)

    program_settings = theme_node.find("ProgramListSettings")
    if program_settings is not None:
        menu.program_list = ProgramListSettings(
            x=_int_attr(program_settings, "X", 0),
            y=_int_attr(program_settings, "Y", 0),
            width=_int_attr(program_settings, "Width", 0),
            height=_int_attr(program_settings, "Height", 0),
            only_recent=_int_attr(program_settings, "OnlyShowRecentApps", 0),
            only_favs=_int_attr(program_settings, "OnlyShowFavs", 0),
        )

    for button_node in theme_node.findall("Button"):
        button = LegacyButton(
            name=_str_attr(button_node, "Name", ""),
            markup=_str_attr(button_node, "Markup", ""),
            text_x=_int_attr(button_node, "TextX", 0),
            text_y=_int_attr(button_node, "TextY", 0),
            image=_str_attr(button_node, "Image", ""),
            button_icon=_str_attr(button_node, "ButtonIcon", ""),
            button_icon_sel=_str_attr(button_node, "ButtonIconSel", ""),
            x=_int_attr(button_node, "ButtonX", 0),
            y=_int_attr(button_node, "ButtonY", 0),
            submenu=_int_attr(button_node, "SubMenu", 0),
            command=_str_attr(button_node, "Command", ""),
            close_menu=_int_attr(button_node, "CloseMenu", 1),
            execute_on_hover=_int_attr(button_node, "ExecuteOnHover", 0),
        )
        menu.buttons.append(button)

    for label_node in theme_node.findall("Label"):
        label = LegacyLabel(
            name=_str_attr(label_node, "Name", ""),
            markup=_str_attr(label_node, "Markup", ""),
            x=_int_attr(label_node, "LabelX", 0),
            y=_int_attr(label_node, "LabelY", 0),
            command=_str_attr(label_node, "Command", ""),
        )
        menu.labels.append(label)

    return menu